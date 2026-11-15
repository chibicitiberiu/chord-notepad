"""Recovery copies of unsaved songs, so a crash or a kill doesn't lose them.

Each running instance of the app owns one slot in the recovery folder (the
app's data folder, ``recovery/``), named by a fresh id:

* ``<id>.lock``: created when the instance starts and locked by it until it
  closes (``fcntl.flock`` on Linux and macOS, ``msvcrt.locking`` on
  Windows). The OS drops the lock when the process dies, however it dies,
  so a slot whose lock can be taken belongs to no running instance.
* ``<id>.txt``: the song's text (UTF-8, ``\\n`` line endings), and
* ``<id>.json``: what the text belongs to: the document's id (its path on
  the desktop) or null for an untitled song, its name, where it is, and
  when the copy was written. Written after the text, so a slot with a
  readable ``.json`` has its text.

The encoding and line endings aren't kept: Save writes to the original file
in the encoding and line endings that file has (``FileService.save_file``).

:meth:`RecoveryStore.write` and :meth:`RecoveryStore.discard` only touch the
instance's own slot. :meth:`RecoveryStore.entries` lists the slots of
instances that are gone, newest first; reading or removing one first takes
its lock, so an instance never lists or removes another live instance's
copy. :meth:`RecoveryStore.prune` (at start-up) drops what is older than 30
days and keeps the 20 newest. A slot that can't be read is skipped, and
pruned by its files' age.

Stdlib only (the Android build could use it as it is). The calls of one
store run one at a time (a lock), so a front end can write from a worker
thread and list from its UI thread.
"""

import datetime
import functools
import json
import logging
import os
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

#: The folder under the app's data folder.
RECOVERY_FOLDER = "recovery"
#: At most this many copies of instances that are gone are kept.
MAX_ENTRIES = 20
#: Copies older than this are dropped at start-up.
MAX_AGE = datetime.timedelta(days=30)
#: The ``version`` field of the ``.json`` this module writes.
FORMAT_VERSION = 1

LOCK_SUFFIX = ".lock"
TEXT_SUFFIX = ".txt"
META_SUFFIX = ".json"
TEMP_SUFFIX = ".tmp"


@dataclass(frozen=True)
class RecoveredEntry:
    """A recovery copy left by an instance that is no longer running.

    Attributes:
        entry_id: The slot's id (hand it back to :meth:`RecoveryStore.read`
            and :meth:`RecoveryStore.remove`).
        display_name: The song's name when the copy was written
            (``song.txt``, or ``Untitled``).
        document_id: The document it belongs to (desktop: its path), or
            None for a song that was never saved.
        location: Where that document is, as the user sees it; None without one.
        written: When the copy was written (aware, UTC).
    """

    entry_id: str
    display_name: str
    document_id: Optional[str]
    location: Optional[str]
    written: datetime.datetime


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# -- the lock ---------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        """Lock the file's first byte without waiting; False if another
        handle holds it."""
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        """``flock`` the file without waiting; False if another open file
        holds it (in this process too: flock locks belong to the open file,
        not to the process, unlike ``lockf``)."""
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


class _Lock:
    """An exclusive lock on one slot's ``.lock`` file, held until :meth:`release`."""

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self._fd: Optional[int] = fd

    @classmethod
    def take(cls, path: Path, create: bool) -> Optional["_Lock"]:
        """The lock, or None if a running instance holds it (or, without
        ``create``, there is no such file)."""
        flags = os.O_RDWR | (os.O_CREAT if create else 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileNotFoundError:
            return None
        if not _try_lock(fd):
            os.close(fd)
            return None
        if create:
            # Windows locks a byte range; give it a byte to lock.
            try:
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\0")
            except OSError:
                pass
        return cls(path, fd)

    def release(self, delete: bool = False) -> None:
        """Unlock and close; then remove the file if ``delete`` (after closing:
        Windows can't remove a file that is open)."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        _unlock(fd)
        os.close(fd)
        if delete:
            _remove(self.path)


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("Couldn't remove %s: %s", path, e)


def _write_atomically(path: Path, data: bytes) -> None:
    """Write ``data`` to a temporary file next to ``path``, then put it in place."""
    temp = path.with_name(path.name + TEMP_SUFFIX)
    with open(temp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


# -- the store ----------------------------------------------------------------------


def _serialized(method):
    """Run ``method`` under the store's lock (one call at a time)."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._mutex:
            return method(self, *args, **kwargs)
    return wrapper


class RecoveryStore:
    """One instance's recovery slot, and the copies other instances left.

    Args:
        folder: The recovery folder (created if missing).
        now: The clock (tests); aware UTC datetimes.
        max_entries: How many copies :meth:`prune` keeps.
        max_age: How old a copy :meth:`prune` keeps.

    Raises:
        OSError: If the folder can't be created or the instance's lock file
            can't be made (the caller goes without recovery then).
    """

    def __init__(self, folder: Path, *, now: Callable[[], datetime.datetime] = _utc_now,
                 max_entries: int = MAX_ENTRIES,
                 max_age: datetime.timedelta = MAX_AGE) -> None:
        self._folder = Path(folder)
        self._now = now
        self._max_entries = max_entries
        self._max_age = max_age
        self._folder.mkdir(parents=True, exist_ok=True)
        self._id = f"{now().strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        lock = _Lock.take(self._path(self._id, LOCK_SUFFIX), create=True)
        if lock is None:
            # A fresh id: nobody else can hold it.
            raise OSError(f"Couldn't lock the recovery slot {self._id}")
        self._lock: Optional[_Lock] = lock
        self._has_copy = False
        self._mutex = threading.RLock()
        logger.info("Recovery copies in %s (this instance: %s)", self._folder, self._id)

    @property
    def folder(self) -> Path:
        return self._folder

    @property
    def instance_id(self) -> str:
        """This instance's slot."""
        return self._id

    @property
    def has_copy(self) -> bool:
        """Whether this instance's slot holds a copy now."""
        return self._has_copy

    def _path(self, entry_id: str, suffix: str) -> Path:
        return self._folder / f"{entry_id}{suffix}"

    # -- this instance's slot ---------------------------------------------------------

    @_serialized
    def write(self, text: str, *, display_name: str, document_id: Optional[str] = None,
              location: Optional[str] = None) -> None:
        """Write (or replace) this instance's copy.

        Raises:
            OSError: If it couldn't be written.
            RuntimeError: After :meth:`close`.
        """
        if self._lock is None:
            raise RuntimeError("the recovery store is closed")
        meta = {
            "version": FORMAT_VERSION,
            "display_name": str(display_name),
            "document_id": document_id,
            "location": location,
            "written": self._now().isoformat(),
        }
        _write_atomically(self._path(self._id, TEXT_SUFFIX), str(text).encode("utf-8"))
        _write_atomically(self._path(self._id, META_SUFFIX),
                          json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        self._has_copy = True

    @_serialized
    def discard(self) -> None:
        """Remove this instance's copy (the song was saved, or its changes
        were discarded). Nothing happens if there is none."""
        if self._lock is None:
            return
        self._remove_files(self._id)
        self._has_copy = False

    @_serialized
    def close(self, keep: bool = False) -> None:
        """Release this instance's slot (at exit), removing its copy unless
        ``keep``. A kept copy is listed by the next instance."""
        if self._lock is None:
            return
        if not keep:
            self._remove_files(self._id)
        lock, self._lock = self._lock, None
        # Without its lock file, a slot is one no running instance holds.
        lock.release(delete=True)

    # -- what other instances left --------------------------------------------------------

    @_serialized
    def entries(self) -> List[RecoveredEntry]:
        """The copies of instances that are no longer running, newest first.

        A slot that a running instance holds, or that can't be read, is left out.
        """
        found = []
        for entry_id in self._slot_ids():
            if entry_id == self._id:
                continue
            lock = self._take_other(entry_id)
            if lock is False:
                continue
            try:
                entry = self._read_meta(entry_id)
                if entry is not None and self._read_text(entry_id) is not None:
                    found.append(entry)
            finally:
                if lock is not None:
                    lock.release()
        found.sort(key=lambda e: e.written, reverse=True)
        return found

    @_serialized
    def read(self, entry_id: str) -> Optional[str]:
        """The text of another instance's copy; None if it is gone, can't be
        read, or its instance is still running."""
        if entry_id == self._id:
            return None
        lock = self._take_other(entry_id)
        if lock is False:
            return None
        try:
            return self._read_text(entry_id)
        finally:
            if lock is not None:
                lock.release()

    @_serialized
    def remove(self, entry_id: str) -> bool:
        """Remove another instance's copy. False (nothing removed) if its
        instance is still running, or ``entry_id`` is this instance's."""
        if entry_id == self._id:
            return False
        lock = self._take_other(entry_id)
        if lock is False:
            return False
        self._remove_files(entry_id)
        if lock is not None:
            lock.release(delete=True)
        return True

    @_serialized
    def clear(self) -> int:
        """Remove every copy :meth:`entries` lists; how many were removed."""
        return sum(1 for entry in self.entries() if self.remove(entry.entry_id))

    @_serialized
    def prune(self) -> int:
        """Drop the copies of instances that are gone that are older than
        ``max_age`` (by when they were written, or by their files' age if
        they can't be read) or beyond the ``max_entries`` newest, and the
        lock files those instances left without a copy. Returns how many
        slots were removed."""
        now = self._now()
        readable: List[RecoveredEntry] = []
        removed = 0
        for entry_id in self._slot_ids():
            if entry_id == self._id:
                continue
            lock = self._take_other(entry_id)
            if lock is False:
                continue
            try:
                entry = self._read_meta(entry_id)
                if entry is not None and self._read_text(entry_id) is None:
                    entry = None
                if entry is None:
                    files = self._files(entry_id)
                    meta_or_text = [p for p in files if p.suffix in (META_SUFFIX, TEXT_SUFFIX)]
                    if not meta_or_text or self._age(files, now) > self._max_age:
                        # A crashed instance that never wrote, or an old unreadable copy.
                        self._remove_files(entry_id)
                        if lock is not None:
                            lock.release(delete=True)
                            lock = None
                        removed += 1
                else:
                    readable.append(entry)
            finally:
                if lock is not None:
                    lock.release()
        readable.sort(key=lambda e: e.written, reverse=True)
        for index, entry in enumerate(readable):
            if index >= self._max_entries or now - entry.written > self._max_age:
                if self.remove(entry.entry_id):
                    removed += 1
        if removed:
            logger.info("Pruned %d recovery cop%s", removed, "y" if removed == 1 else "ies")
        return removed

    # -- helpers ------------------------------------------------------------------------

    def _slot_ids(self) -> List[str]:
        """Every slot id with a file in the folder."""
        ids = set()
        try:
            names = os.listdir(self._folder)
        except OSError as e:
            logger.warning("Couldn't list %s: %s", self._folder, e)
            return []
        for name in names:
            for suffix in (LOCK_SUFFIX, TEXT_SUFFIX, META_SUFFIX):
                if name.endswith(suffix) and len(name) > len(suffix):
                    ids.add(name[:-len(suffix)])
        return sorted(ids)

    def _files(self, entry_id: str) -> List[Path]:
        names = [entry_id + s for s in (LOCK_SUFFIX, TEXT_SUFFIX, META_SUFFIX,
                                        TEXT_SUFFIX + TEMP_SUFFIX, META_SUFFIX + TEMP_SUFFIX)]
        return [self._folder / n for n in names if (self._folder / n).exists()]

    @staticmethod
    def _age(files: List[Path], now: datetime.datetime) -> datetime.timedelta:
        newest = 0.0
        for path in files:
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                pass
        written = datetime.datetime.fromtimestamp(newest, datetime.timezone.utc)
        return now - written

    def _take_other(self, entry_id: str):
        """Another slot's lock: the lock, None if the slot has no lock file
        (nobody can hold it), or False if a running instance holds it."""
        path = self._path(entry_id, LOCK_SUFFIX)
        lock = _Lock.take(path, create=False)
        if lock is not None:
            return lock
        return False if path.exists() else None

    def _read_text(self, entry_id: str) -> Optional[str]:
        try:
            return self._path(entry_id, TEXT_SUFFIX).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Couldn't read the recovery copy %s: %s", entry_id, e)
            return None

    def _read_meta(self, entry_id: str) -> Optional[RecoveredEntry]:
        path = self._path(entry_id, META_SUFFIX)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            written = datetime.datetime.fromisoformat(str(data["written"]))
            if written.tzinfo is None:
                written = written.replace(tzinfo=datetime.timezone.utc)
            document_id = data.get("document_id")
            location = data.get("location")
            return RecoveredEntry(
                entry_id=entry_id,
                display_name=str(data["display_name"]),
                document_id=str(document_id) if document_id is not None else None,
                location=str(location) if location is not None else None,
                written=written,
            )
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            logger.warning("Skipping the unreadable recovery copy %s: %s", entry_id, e)
            return None

    def _remove_files(self, entry_id: str) -> None:
        for suffix in (META_SUFFIX, TEXT_SUFFIX, TEXT_SUFFIX + TEMP_SUFFIX,
                       META_SUFFIX + TEMP_SUFFIX):
            _remove(self._path(entry_id, suffix))


def recovery_folder(app_data_dir: Path) -> Path:
    """The recovery folder in the app's data folder."""
    return Path(app_data_dir) / RECOVERY_FOLDER

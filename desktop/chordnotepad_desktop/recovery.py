"""The open song's recovery copy, and File › Backups.

The copies themselves are the core's
:class:`~chordnotepad.services.recovery_store.RecoveryStore` (one slot per
running instance, in the data folder's ``recovery/``, locked for the
instance's lifetime). :class:`RecoveryModel` decides when to write and
remove this instance's copy, and lists what crashed instances left:

* **Writing.** While the document has unsaved changes
  (``DocumentState.is_modified``), the editor's text is written
  :data:`DELAY_MS` after the last change (typed, pasted or the session's
  edit), and at least every :data:`MAX_WAIT_MS` while changes keep coming.
  Every disk access (the writes, the removals, listing, reading and
  clearing copies, the start-up prune) runs on one worker thread, in the
  order asked, so a slow disk never holds the window up; results come back
  to the window's thread through a queued signal.
* **Removing.** When the document stops being modified (it was saved, or
  New or Open replaced it after Discard) and when the window closes after
  the session approved it (Discard or Save on quit). A crash or a kill
  leaves the copy for the next start.
* **Backups ›** lists the copies of instances that are gone (never
  another running instance's: the store checks its lock), newest first, as
  "song.txt, today at 14:32". The list is read when the app starts (after
  dropping copies older than 30 days and all but the 20 newest) and again
  when the File menu or the ☰ menu opens (the menu shows the last list
  until the new one arrives). Choosing one reads its text and
  sends ``open_recovered`` (the session asks about unsaved changes first,
  then opens it modified, bound to its file or untitled). Once the editor
  shows it, this instance's own copy is written at once and the chosen
  copy is removed. "Clear backups" removes every listed copy.

Without a store (the folder couldn't be made) nothing is written and the
menu stays empty.
"""

import datetime
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot

from chordnotepad.services.recovery_store import RecoveredEntry, RecoveryStore
from chordnotepad.session import formatting
from chordnotepad.session.bridge import to_json_value

logger = logging.getLogger(__name__)

#: A copy is written this long after the last change.
DELAY_MS = 5000
#: ...and at least this often while changes keep coming.
MAX_WAIT_MS = 30000
#: The menu's last row.
CLEAR_TEXT = "Clear backups"

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def when_label(written: datetime.datetime, now: datetime.datetime) -> str:
    """When a copy was written, in local time: "today at 14:32",
    "yesterday at 09:05", "12 Nov at 14:32", "12 Nov 2025 at 14:32"."""
    local = written.astimezone(now.tzinfo) if now.tzinfo is not None else written.astimezone()
    clock = f"{local.hour:02d}:{local.minute:02d}"
    days = (now.date() - local.date()).days
    if days == 0:
        return f"today at {clock}"
    if days == 1:
        return f"yesterday at {clock}"
    day = f"{local.day} {MONTHS[local.month - 1]}"
    if local.year != now.year:
        day += f" {local.year}"
    return f"{day} at {clock}"


def entry_label(entry: RecoveredEntry, now: datetime.datetime) -> str:
    """A row of the menu: "song.txt, today at 14:32"."""
    return f"{entry.display_name}, {when_label(entry.written, now)}"


def _local_now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


class RecoveryModel(QObject):
    """This instance's recovery copy, and the Backups menu.

    Args:
        store: The window's SessionStore.
        editor: The EditorBridge (its ``text`` and ``textChanged``).
        recovery: The recovery store, or None to go without.
        delay_ms: :data:`DELAY_MS` (tests).
        max_wait_ms: :data:`MAX_WAIT_MS` (tests).
        now: Local time, aware (tests).
    """

    #: The listed copies changed.
    entriesChanged = Signal()
    # From the worker thread to the window's: a new list, a copy's text read.
    _listed = Signal(object)
    _read = Signal(object, object)

    def __init__(self, store: Any, editor: Any, recovery: Optional[RecoveryStore], *,
                 delay_ms: int = DELAY_MS, max_wait_ms: int = MAX_WAIT_MS,
                 now: Callable[[], datetime.datetime] = _local_now,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self._recovery = recovery
        self._delay_ms = delay_ms
        self._max_wait_ms = max_wait_ms
        self._now = now
        self._entries: List[RecoveredEntry] = []
        self._labels: List[str] = []
        self._has_copy = False          # a write was queued since the last removal
        self._since: Optional[float] = None   # the first change not written yet
        # The copy being opened: (entry id, text, document id).
        self._pending: Optional[Tuple[str, str, Optional[str]]] = None
        self._closed = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._write_now)
        self._listed.connect(self._apply_entries, Qt.ConnectionType.QueuedConnection)
        self._read.connect(self._open_read, Qt.ConnectionType.QueuedConnection)
        if recovery is None:
            return
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recovery")
        # Old copies go first, before the first list is read.
        self._executor.submit(self._run, recovery.prune)
        editor.textChanged.connect(self._on_text)
        editor.documentReset.connect(self._on_reset)
        store.stateChanged.connect(self._on_state)

    # -- for QML ----------------------------------------------------------------------

    def _get_labels(self) -> list:
        return list(self._labels)

    #: One row per copy, newest first ("song.txt, today at 14:32").
    labels = Property("QVariantList", _get_labels, notify=entriesChanged)

    def _get_clear_text(self) -> str:
        return CLEAR_TEXT

    clearText = Property(str, _get_clear_text, constant=True)

    @Slot()
    def refresh(self) -> None:
        """Read the list of copies again (another instance may have crashed),
        on the worker; the labels change when it arrives."""
        if self._recovery is None or self._closed:
            return
        self._executor.submit(self._run, self._list)

    def _list(self) -> None:
        """On the worker: read the list and send it to the window's thread."""
        self._listed.emit(self._recovery.entries())

    @Slot(object)
    def _apply_entries(self, entries: List[RecoveredEntry]) -> None:
        now = self._now()
        labels = [entry_label(e, now) for e in entries]
        if entries != self._entries or labels != self._labels:
            self._entries, self._labels = entries, labels
            self.entriesChanged.emit()

    @Slot(int)
    def openEntry(self, index: int) -> None:  # noqa: N802 (Qt)
        """Open the copy at ``index`` (the session asks about unsaved changes
        first); its text is read on the worker."""
        if self._recovery is None or self._closed or not 0 <= index < len(self._entries):
            return
        entry = self._entries[index]

        def read() -> None:
            self._read.emit(entry, self._recovery.read(entry.entry_id))

        self._executor.submit(self._run, read)

    @Slot(object, object)
    def _open_read(self, entry: RecoveredEntry, text: Optional[str]) -> None:
        if self._closed:
            return
        if text is None:
            logger.warning("The recovery copy %s can't be read any more", entry.entry_id)
            self.refresh()
            return
        ref = None
        name = None
        if entry.document_id is not None:
            ref = self._store.direct("document_ref", entry.document_id)
        elif entry.display_name != formatting.UNTITLED:
            name = entry.display_name
        self._pending = (entry.entry_id, text, ref.id if ref is not None else None)
        self._store.submit("open_recovered", {"text": text, "document": to_json_value(ref),
                                              "name": name})

    @Slot()
    def clearAll(self) -> None:  # noqa: N802 (Qt)
        """Remove every listed copy (on the worker), then list again."""
        if self._recovery is None or self._closed:
            return
        self._executor.submit(self._run, self._recovery.clear)
        self.refresh()

    # -- this instance's copy -----------------------------------------------------------

    def _modified(self) -> bool:
        return self._store.state("DocumentState").value("is_modified") is True

    def _on_text(self) -> None:
        if self._closed:
            return
        now = time.monotonic()
        if self._since is None:
            self._since = now
        left = self._max_wait_ms - int((now - self._since) * 1000)
        self._timer.start(max(0, min(self._delay_ms, left)))

    def _on_state(self, type_name: str) -> None:
        if type_name != "DocumentState" or self._closed or self._modified():
            return
        # Saved, or replaced after Discard: nothing left to recover.
        self._timer.stop()
        self._since = None
        if self._has_copy:
            self._has_copy = False
            self._executor.submit(self._run, self._recovery.discard)

    def _write_now(self) -> None:
        self._timer.stop()
        self._since = None
        if self._closed or self._recovery is None or not self._modified():
            return
        doc = self._store.state("DocumentState")
        document_id = doc.value("document_id")
        kwargs = {"display_name": str(doc.value("display_name") or formatting.UNTITLED),
                  "document_id": str(document_id) if document_id is not None else None,
                  "location": doc.value("location")}
        self._has_copy = True
        self._executor.submit(self._run, self._recovery.write, self._editor.text, **kwargs)

    @staticmethod
    def _run(call, *args, **kwargs) -> None:
        """A store call on the worker thread; a failure is logged, not raised."""
        try:
            call(*args, **kwargs)
        except Exception:
            logger.warning("A recovery copy call (%s) failed",
                           getattr(call, "__name__", call), exc_info=True)

    def _on_reset(self) -> None:
        # Another text came in: if it is the copy being opened, check once
        # the session has published the document.
        if self._pending is not None:
            self._store.after_commands(self._check_opened)

    def _check_opened(self) -> None:
        pending, self._pending = self._pending, None
        if pending is None or self._closed:
            return
        entry_id, text, document_id = pending
        doc = self._store.state("DocumentState")
        if not (self._modified() and doc.value("document_id") == document_id
                and self._editor.text == text):
            return
        # This instance's copy takes over before the old one goes: the
        # worker runs the write, the removal and the new list in that order.
        self._write_now()
        self._executor.submit(self._run, self._recovery.remove, entry_id)
        self.refresh()

    # -- closing ------------------------------------------------------------------------

    def close(self, clean: bool) -> None:
        """Stop writing; release this instance's slot, removing its copy if
        ``clean`` (the window closed after the session approved it)."""
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        if self._executor is not None:
            self._executor.shutdown(wait=True)
        if self._recovery is not None:
            try:
                self._recovery.close(keep=not clean)
            except OSError:
                logger.warning("Closing the recovery slot failed", exc_info=True)

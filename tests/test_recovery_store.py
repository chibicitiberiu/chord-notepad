"""The recovery copies of unsaved songs (core/chordnotepad/services/recovery_store.py).

Two stores on one folder stand in for two running instances: flock locks
belong to the open file, so they exclude each other within one process as
they do between processes. A store that was closed with ``keep=True`` (or
whose lock was dropped without a clean close) is an instance that crashed.
"""

import datetime
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from chordnotepad.services.recovery_store import (
    LOCK_SUFFIX, META_SUFFIX, TEXT_SUFFIX, RecoveryStore, recovery_folder,
)

UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
CORE = Path(__file__).resolve().parents[1] / "core"


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += datetime.timedelta(**delta)


def crashed(folder, clock, text="C G\n", **meta):
    """A store that wrote a copy and then went away without cleaning up."""
    store = RecoveryStore(folder, now=clock)
    store.write(text, display_name=meta.pop("display_name", "song.txt"), **meta)
    store.close(keep=True)
    return store.instance_id


def test_the_folder_is_recovery_in_the_data_folder(tmp_path):
    assert recovery_folder(tmp_path) == tmp_path / "recovery"


def test_a_written_copy_is_listed_by_the_next_instance_after_a_crash(tmp_path):
    clock = Clock()
    entry_id = crashed(tmp_path, clock, "Am F\n", display_name="song.txt",
                       document_id="/songs/song.txt", location="~/songs/song.txt")
    later = RecoveryStore(tmp_path, now=clock)
    [entry] = later.entries()
    assert entry.entry_id == entry_id
    assert (entry.display_name, entry.document_id, entry.location) == (
        "song.txt", "/songs/song.txt", "~/songs/song.txt")
    assert entry.written == T0
    assert later.read(entry_id) == "Am F\n"


def test_the_text_and_metadata_files_are_utf8_json_and_text(tmp_path):
    store = RecoveryStore(tmp_path, now=Clock())
    store.write("Dó Ré\n", display_name="cântec.txt")
    meta = json.loads((tmp_path / f"{store.instance_id}{META_SUFFIX}").read_text("utf-8"))
    assert meta == {"version": 1, "display_name": "cântec.txt", "document_id": None,
                    "location": None, "named": True, "written": T0.isoformat()}
    assert (tmp_path / f"{store.instance_id}{TEXT_SUFFIX}").read_text("utf-8") == "Dó Ré\n"
    store.close()


def test_a_copy_says_whether_its_name_is_the_songs_own(tmp_path):
    clock = Clock()
    lyric = RecoveryStore(tmp_path, now=clock)
    lyric.write("C\nHey Jude\n", display_name="Hey Jude", named=False)
    lyric.close(keep=True)
    clock.advance(seconds=1)
    renamed = RecoveryStore(tmp_path, now=clock)
    renamed.write("C\n", display_name="Set list.txt")
    renamed.close(keep=True)
    later = RecoveryStore(tmp_path, now=clock)
    assert [(e.display_name, e.named) for e in later.entries()] == [
        ("Set list.txt", True), ("Hey Jude", False)]
    later.close()


def test_a_copy_written_before_the_named_field_reads_as_not_saying(tmp_path):
    entry_id = "20261116T120000-1-abcdef12"
    (tmp_path / f"{entry_id}{TEXT_SUFFIX}").write_text("C\n", encoding="utf-8")
    (tmp_path / f"{entry_id}{META_SUFFIX}").write_text(json.dumps(
        {"version": 1, "display_name": "Untitled", "document_id": None, "location": None,
         "written": T0.isoformat()}), encoding="utf-8")
    store = RecoveryStore(tmp_path, now=Clock())
    [entry] = store.entries()
    assert (entry.display_name, entry.named) == ("Untitled", None)
    store.close()


def test_a_second_write_replaces_the_first(tmp_path):
    clock = Clock()
    store = RecoveryStore(tmp_path, now=clock)
    store.write("one", display_name="a.txt")
    clock.advance(seconds=5)
    store.write("two", display_name="b.txt")
    store.close(keep=True)
    other = RecoveryStore(tmp_path, now=clock)
    [entry] = other.entries()
    assert entry.display_name == "b.txt" and entry.written == T0 + datetime.timedelta(seconds=5)
    assert other.read(entry.entry_id) == "two"


def test_an_instance_never_lists_its_own_copy(tmp_path):
    store = RecoveryStore(tmp_path, now=Clock())
    store.write("C", display_name="a.txt")
    assert store.entries() == []
    assert store.read(store.instance_id) is None
    assert store.remove(store.instance_id) is False


def test_a_live_instances_copy_is_neither_listed_read_nor_removed(tmp_path):
    clock = Clock()
    live = RecoveryStore(tmp_path, now=clock)
    live.write("live text", display_name="live.txt")
    other = RecoveryStore(tmp_path, now=clock)
    assert other.entries() == []
    assert other.read(live.instance_id) is None
    assert other.remove(live.instance_id) is False
    assert other.clear() == 0
    assert other.prune() == 0
    assert (tmp_path / f"{live.instance_id}{TEXT_SUFFIX}").read_text("utf-8") == "live text"
    # Once it has gone (without cleaning up), it is listed.
    live.close(keep=True)
    assert [e.entry_id for e in other.entries()] == [live.instance_id]


def test_a_live_instance_in_another_process_is_left_alone(tmp_path):
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(CORE)!r})
        from chordnotepad.services.recovery_store import RecoveryStore
        store = RecoveryStore({str(tmp_path)!r})
        store.write("theirs", display_name="theirs.txt")
        print("ID", store.instance_id, flush=True)
        sys.stdin.readline()
    """)
    child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
    try:
        # Other lines may come first (pyfluidsynth prints where it found the
        # library when CI is set).
        line = ""
        while not line.startswith("ID "):
            line = child.stdout.readline()
            assert line, "the child exited"
        their_id = line.split()[1]
        mine = RecoveryStore(tmp_path)
        assert mine.entries() == []
        assert mine.remove(their_id) is False
        # Killed: the OS drops the lock, and the copy shows.
        child.kill()
        child.wait(timeout=10)
        assert [e.entry_id for e in mine.entries()] == [their_id]
        assert mine.read(their_id) == "theirs"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)


def test_discard_removes_the_copy_and_keeps_the_slot(tmp_path):
    store = RecoveryStore(tmp_path, now=Clock())
    store.write("C", display_name="a.txt")
    assert store.has_copy
    store.discard()
    assert not store.has_copy
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [f"{store.instance_id}{LOCK_SUFFIX}"]
    store.write("D", display_name="a.txt")
    assert store.has_copy


def test_a_clean_close_removes_everything_of_the_instance(tmp_path):
    store = RecoveryStore(tmp_path, now=Clock())
    store.write("C", display_name="a.txt")
    store.close()
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(RuntimeError):
        store.write("C", display_name="a.txt")


def test_entries_are_newest_first(tmp_path):
    clock = Clock()
    first = crashed(tmp_path, clock, display_name="first.txt")
    clock.advance(minutes=3)
    second = crashed(tmp_path, clock, display_name="second.txt")
    clock.advance(minutes=3)
    assert [e.entry_id for e in RecoveryStore(tmp_path, now=clock).entries()] == [second, first]


def test_remove_and_clear(tmp_path):
    clock = Clock()
    a = crashed(tmp_path, clock, display_name="a.txt")
    crashed(tmp_path, clock, display_name="b.txt")
    crashed(tmp_path, clock, display_name="c.txt")
    store = RecoveryStore(tmp_path, now=clock)
    assert store.remove(a) is True
    assert sorted(e.display_name for e in store.entries()) == ["b.txt", "c.txt"]
    assert store.clear() == 2
    assert store.entries() == []
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{store.instance_id}{LOCK_SUFFIX}"]


def test_corrupt_or_half_written_entries_are_skipped(tmp_path):
    clock = Clock()
    good = crashed(tmp_path, clock, display_name="good.txt")
    bad_json = crashed(tmp_path, clock, display_name="bad.txt")
    (tmp_path / f"{bad_json}{META_SUFFIX}").write_text("{not json", encoding="utf-8")
    wrong_shape = crashed(tmp_path, clock, display_name="shape.txt")
    (tmp_path / f"{wrong_shape}{META_SUFFIX}").write_text("[1, 2]", encoding="utf-8")
    bad_date = crashed(tmp_path, clock, display_name="date.txt")
    (tmp_path / f"{bad_date}{META_SUFFIX}").write_text(
        json.dumps({"display_name": "date.txt", "written": "yesterday"}), encoding="utf-8")
    no_text = crashed(tmp_path, clock, display_name="notext.txt")
    (tmp_path / f"{no_text}{TEXT_SUFFIX}").unlink()
    bad_text = crashed(tmp_path, clock, display_name="bytes.txt")
    (tmp_path / f"{bad_text}{TEXT_SUFFIX}").write_bytes(b"\xff\xfe\xfa")
    # A text without its .json (killed between the two writes).
    (tmp_path / f"orphan{TEXT_SUFFIX}").write_text("C", encoding="utf-8")
    (tmp_path / "unrelated.png").write_bytes(b"")
    store = RecoveryStore(tmp_path, now=clock)
    listed = [e.entry_id for e in store.entries()]
    assert listed == [good]
    assert store.read(bad_text) is None
    # Recent unreadable copies stay (someone may want to dig them out).
    assert store.prune() == 0


def test_prune_drops_copies_older_than_30_days(tmp_path):
    clock = Clock()
    old = crashed(tmp_path, clock, display_name="old.txt")
    clock.advance(days=20)
    recent = crashed(tmp_path, clock, display_name="recent.txt")
    clock.advance(days=11)
    store = RecoveryStore(tmp_path, now=clock)
    assert store.prune() == 1
    assert [e.entry_id for e in store.entries()] == [recent]
    assert not any(p.name.startswith(old) for p in tmp_path.iterdir())


def test_prune_keeps_the_20_newest(tmp_path):
    clock = Clock()
    ids = []
    for i in range(23):
        ids.append(crashed(tmp_path, clock, display_name=f"{i}.txt"))
        clock.advance(minutes=1)
    store = RecoveryStore(tmp_path, now=clock)
    assert store.prune() == 3
    assert [e.entry_id for e in store.entries()] == list(reversed(ids[3:]))


def test_prune_leaves_a_live_instances_copy_even_when_old(tmp_path):
    clock = Clock()
    live = RecoveryStore(tmp_path, now=clock)
    live.write("C", display_name="a.txt")
    clock.advance(days=40)
    other = RecoveryStore(tmp_path, now=clock)
    assert other.prune() == 0
    assert (tmp_path / f"{live.instance_id}{TEXT_SUFFIX}").exists()


def test_prune_removes_lock_files_of_crashed_instances_that_never_wrote(tmp_path):
    clock = Clock()
    store = RecoveryStore(tmp_path, now=clock)
    store.close(keep=True)       # nothing written: nothing left but...
    stale = tmp_path / f"crashed{LOCK_SUFFIX}"
    stale.write_bytes(b"\0")    # ...a crashed instance leaves its lock file
    other = RecoveryStore(tmp_path, now=clock)
    assert other.prune() == 1
    assert not stale.exists()


def test_prune_removes_old_unreadable_copies(tmp_path):
    clock = Clock()
    bad = crashed(tmp_path, clock, display_name="bad.txt")
    (tmp_path / f"{bad}{META_SUFFIX}").write_text("{", encoding="utf-8")
    month_ago = (T0 - datetime.timedelta(days=31)).timestamp()
    for path in tmp_path.iterdir():
        os.utime(path, (month_ago, month_ago))
    store = RecoveryStore(tmp_path, now=clock)
    assert store.prune() == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{store.instance_id}{LOCK_SUFFIX}"]


def test_a_folder_that_cant_be_made_raises_oserror(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(OSError):
        RecoveryStore(blocker / "recovery")

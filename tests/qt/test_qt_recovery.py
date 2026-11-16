"""File › Backups and the open song's recovery copy (recovery.py).

The whole front end runs in the test process (QtAppHarness); its data folder
is under tmp_path, so the copies are in ``tmp_path/appdata/data/chord-notepad/
recovery``. A copy left by a crashed instance is made with the core's
RecoveryStore and closed with ``keep=True`` before the app starts. The store
itself (locks, pruning, unreadable copies) is tests/test_recovery_store.py,
the session's ``open_recovered`` tests/test_session_open_recovered.py.
"""

import datetime
import json

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, Qt  # noqa: E402

from chordnotepad.services.recovery_store import RecoveryStore  # noqa: E402
from chordnotepad_desktop import recovery as recovery_module  # noqa: E402
from tests.qt.test_qt_chrome import Chrome, menu_item_at, plain_text  # noqa: E402
from tests.qt.test_qt_editor import start  # noqa: E402

UTC = datetime.timezone.utc


def folder(tmp_path):
    return tmp_path / "appdata" / "data" / "chord-notepad" / "recovery"


def crashed(tmp_path, text, display_name, document_id=None, location=None, written=None):
    """A copy left by an instance that crashed; its id."""
    clock = (lambda: written) if written is not None else (lambda: datetime.datetime.now(UTC))
    store = RecoveryStore(folder(tmp_path), now=clock)
    store.write(text, display_name=display_name, document_id=document_id, location=location)
    store.close(keep=True)
    return store.instance_id


def copies(tmp_path):
    """The .json of every copy in the folder, by slot id."""
    return {p.stem: json.loads(p.read_text("utf-8")) for p in folder(tmp_path).glob("*.json")}


class Recovery(Chrome):
    @property
    def recovery(self):
        return self.harness.app.recovery

    def own_id(self):
        return self.recovery._recovery.instance_id


def settle(app):
    """Wait for the recovery worker's queue, then deliver what it sent back."""
    app.recovery._executor.submit(lambda: None).result(timeout=5)
    app.qtbot.wait(20)


def started(qapp, qtbot, tmp_path, delay_ms=150):
    harness = start(qapp, qtbot, tmp_path)
    app = Recovery(harness, qtbot)
    app.recovery._delay_ms = delay_ms
    qtbot.waitUntil(lambda: app.area.hasActiveFocus(), timeout=1000)
    settle(app)  # the start-up prune and the first list
    return app


def finish(app):
    warnings, unexpected = list(app.harness.app.warnings), list(app.harness.unexpected)
    app.harness.shutdown()
    app.qtbot.wait(1)
    assert warnings == [] and unexpected == []


@pytest.fixture
def app(qapp, qtbot, tmp_path):
    a = started(qapp, qtbot, tmp_path)
    yield a
    finish(a)


def submenu_row(menu, title):
    """The parent menu's row titled ``title`` (a submenu's row) and its index."""
    for i in range(menu.property("count")):
        item = menu_item_at(menu, i)
        if plain_text(item.property("text") or "") == title:
            return i, item
    raise AssertionError(title)


# -- the menu -------------------------------------------------------------------------------


def test_with_nothing_recovered_the_submenu_is_disabled_in_both_menus(app):
    for parent, name in (("appMenu", "appMenuRecovered"), ("fileMenu", "menuBarRecovered")):
        sub = app.obj(name)
        assert sub.property("enabled") is False
        index, row = submenu_row(app.obj(parent), "Backups")
        assert row.property("enabled") is False
        # Right after Open recent.
        recent_index, _ = submenu_row(app.obj(parent), "Open recent")
        assert index == recent_index + 1


def test_copies_crashed_instances_left_are_listed_newest_first(qapp, qtbot, tmp_path):
    now = datetime.datetime.now(UTC)
    crashed(tmp_path, "old\n", "old.txt", written=now - datetime.timedelta(days=2))
    crashed(tmp_path, "new\n", "new.txt", written=now - datetime.timedelta(minutes=1))
    app = started(qapp, qtbot, tmp_path)
    try:
        sub = app.obj("menuBarRecovered")
        assert sub.property("enabled") is True
        rows = app.menu_texts(sub)
        assert rows[0].startswith("new.txt, today at ") or rows[0].startswith("new.txt, yesterday")
        assert rows[1].startswith("old.txt, ")
        assert rows[2:] == ["---", "Clear backups"]
        assert app.menu_texts(app.obj("appMenuRecovered")) == rows
        _, row = submenu_row(app.obj("fileMenu"), "Backups")
        assert row.property("enabled") is True
    finally:
        finish(app)


def test_copies_older_than_30_days_are_dropped_at_start(qapp, qtbot, tmp_path):
    now = datetime.datetime.now(UTC)
    old = crashed(tmp_path, "old\n", "old.txt", written=now - datetime.timedelta(days=31))
    kept = crashed(tmp_path, "kept\n", "kept.txt", written=now - datetime.timedelta(days=29))
    app = started(qapp, qtbot, tmp_path)
    try:
        assert set(copies(tmp_path)) == {kept}
        assert old not in copies(tmp_path)
        assert len(app.recovery.labels) == 1
    finally:
        finish(app)


def test_a_copy_that_appears_while_running_shows_when_the_menu_opens(app, tmp_path):
    assert app.recovery.labels == []
    crashed(tmp_path, "C\n", "later.txt")
    app.key(Qt.Key.Key_F10)
    file_menu = app.obj("fileMenu")
    app.qtbot.waitUntil(lambda: file_menu.property("opened") is True, timeout=1000)
    # The list is read on the worker; the menu takes it when it arrives.
    app.qtbot.waitUntil(lambda: app.obj("menuBarRecovered").property("enabled") is True,
                        timeout=2000)
    assert app.menu_texts(app.obj("menuBarRecovered"))[0].startswith("later.txt, ")
    app.key(Qt.Key.Key_Escape)


def test_another_running_instances_copy_is_never_listed(app, tmp_path):
    live = RecoveryStore(folder(tmp_path))
    live.write("theirs\n", display_name="theirs.txt")
    try:
        app.recovery.refresh()
        settle(app)
        assert app.recovery.labels == []
        app.recovery.clearAll()
        settle(app)
        assert live.instance_id in copies(tmp_path)
    finally:
        live.close()


def test_opening_a_copy_of_a_saved_song_binds_it_to_the_file(qapp, qtbot, tmp_path):
    song = tmp_path / "Hymn.txt"
    song.write_text("G D\n", encoding="utf-8")
    entry = crashed(tmp_path, "G D Em\nAmazing grace\n", "Hymn.txt", document_id=str(song),
                    location=str(song))
    app = started(qapp, qtbot, tmp_path)
    try:
        QMetaObject.invokeMethod(app.obj("recovered:0"), "click")
        app.qtbot.waitUntil(lambda: app.text() == "G D Em\nAmazing grace\n", timeout=2000)
        doc = app.store.state("DocumentState")
        assert doc.value("is_modified") is True
        assert doc.value("document_id") == str(song)
        assert app.window.property("title") == "Hymn.txt* - Chord Notepad"
        # The chosen copy goes; this instance's own copy takes over at once.
        app.qtbot.waitUntil(lambda: entry not in copies(tmp_path), timeout=2000)
        own = copies(tmp_path)[app.own_id()]
        assert own["document_id"] == str(song) and own["display_name"] == "Hymn.txt"
        # The list refreshes on the worker thread.
        app.qtbot.waitUntil(lambda: app.recovery.labels == [], timeout=2000)
        # Save writes to the original file, and the copy goes.
        app.trigger("saveAction")
        app.qtbot.waitUntil(lambda: song.read_text("utf-8") == "G D Em\nAmazing grace\n",
                            timeout=2000)
        app.qtbot.waitUntil(lambda: copies(tmp_path) == {}, timeout=2000)
    finally:
        finish(app)


def test_opening_an_untitled_copy_with_unsaved_changes_asks_first(qapp, qtbot, tmp_path):
    entry = crashed(tmp_path, "Am F\n", "Untitled")
    app = started(qapp, qtbot, tmp_path)
    try:
        app.type("mine")
        app.qtbot.waitUntil(
            lambda: app.store.state("DocumentState").value("is_modified") is True, timeout=2000)
        QMetaObject.invokeMethod(app.obj("recovered:0"), "click")
        dialog = app.item("unsavedDialog")
        app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
        app.click_item(app.it("unsavedCancel"))
        app.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
        assert app.text() == "mine"
        assert entry in copies(tmp_path)
        # Again, and Don't save this time.
        QMetaObject.invokeMethod(app.obj("recovered:0"), "click")
        app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
        app.click_item(app.it("unsavedDiscard"))
        app.qtbot.waitUntil(lambda: app.text() == "Am F\n", timeout=2000)
        doc = app.store.state("DocumentState")
        assert (doc.value("display_name"), doc.value("is_modified"), doc.value("document_id")) == (
            "Untitled", True, None)
        app.qtbot.waitUntil(lambda: entry not in copies(tmp_path), timeout=2000)
        assert copies(tmp_path)[app.own_id()]["document_id"] is None
    finally:
        finish(app)


def test_clear_recovered_removes_every_listed_copy(qapp, qtbot, tmp_path):
    crashed(tmp_path, "a\n", "a.txt")
    crashed(tmp_path, "b\n", "b.txt")
    app = started(qapp, qtbot, tmp_path)
    try:
        assert len(app.recovery.labels) == 2
        QMetaObject.invokeMethod(app.obj("clearRecovered"), "click")
        app.qtbot.waitUntil(lambda: app.recovery.labels == [], timeout=1000)
        assert copies(tmp_path) == {}
        assert app.obj("menuBarRecovered").property("enabled") is False
    finally:
        finish(app)


# -- this instance's copy -------------------------------------------------------------------


def count_writes(app):
    store = app.recovery._recovery
    writes = []
    original = store.write

    def spy(*args, **kwargs):
        writes.append(args[0])
        return original(*args, **kwargs)

    store.write = spy
    return writes


def test_a_copy_is_written_once_a_while_after_the_last_change(app, tmp_path):
    writes = count_writes(app)
    app.type("C G Am")
    assert copies(tmp_path) == {}
    assert app.recovery._timer.isActive()
    app.qtbot.waitUntil(lambda: app.own_id() in copies(tmp_path), timeout=3000)
    assert writes == ["C G Am"]
    own = copies(tmp_path)[app.own_id()]
    assert (own["display_name"], own["document_id"]) == ("Untitled", None)
    text_file = folder(tmp_path) / f"{app.own_id()}.txt"
    assert text_file.read_text("utf-8") == "C G Am"


def test_changes_that_keep_coming_are_written_at_least_every_max_wait(app, tmp_path):
    app.recovery._delay_ms = 400
    app.recovery._max_wait_ms = 600
    writes = count_writes(app)
    for ch in "C G Am F C G":
        app.type(ch)
        app.run(100)
        if writes:
            break
    assert writes, "nothing written while the changes kept coming"


def test_an_unmodified_document_writes_no_copy(app, tmp_path):
    app.song("C G\n")          # a reset edit, not modified
    app.run(400)
    assert copies(tmp_path) == {}


def test_saving_removes_the_copy(app, tmp_path):
    app.type("C G")
    app.qtbot.waitUntil(lambda: app.own_id() in copies(tmp_path), timeout=3000)
    target = tmp_path / "song.txt"
    app.trigger("saveAction")
    app.wait_picker("Save File As")
    from tests.qt.test_qt_chrome import accept
    accept(app, target)
    app.qtbot.waitUntil(lambda: copies(tmp_path) == {}, timeout=2000)
    assert target.read_text("utf-8") == "C G"


def test_new_after_dont_save_removes_the_copy(app, tmp_path):
    app.type("C G")
    app.qtbot.waitUntil(lambda: app.own_id() in copies(tmp_path), timeout=3000)
    app.trigger("newAction")
    dialog = app.item("unsavedDialog")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    app.click_item(app.it("unsavedDiscard"))
    app.qtbot.waitUntil(lambda: copies(tmp_path) == {}, timeout=2000)


def test_quitting_after_dont_save_removes_the_copy(qapp, qtbot, tmp_path):
    app = started(qapp, qtbot, tmp_path)
    try:
        app.type("C G")
        app.qtbot.waitUntil(lambda: app.own_id() in copies(tmp_path), timeout=3000)
        app.trigger("quitAction")
        dialog = app.item("unsavedDialog")
        app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
        app.click_item(app.it("unsavedDiscard"))
        app.qtbot.waitUntil(lambda: app.window.isVisible() is False, timeout=2000)
    finally:
        finish(app)
    assert list(folder(tmp_path).iterdir()) == []


def test_an_exit_the_session_didnt_approve_keeps_the_copy(qapp, qtbot, tmp_path):
    app = started(qapp, qtbot, tmp_path)
    try:
        app.type("C G")
        app.qtbot.waitUntil(lambda: app.own_id() in copies(tmp_path), timeout=3000)
        own = app.own_id()
    finally:
        finish(app)        # as if killed: no close was approved
    assert own in copies(tmp_path)
    # The next start lists it.
    again = started(qapp, qtbot, tmp_path)
    try:
        assert again.menu_texts(again.obj("menuBarRecovered"))[0].startswith("Untitled, today at ")
    finally:
        finish(again)


def test_the_labels_say_when_in_local_time():
    now = datetime.datetime(2026, 11, 16, 15, 0).astimezone()
    at = lambda **d: now - datetime.timedelta(**d)  # noqa: E731
    assert recovery_module.when_label(at(minutes=28), now) == "today at 14:32"
    assert recovery_module.when_label(at(days=1), now) == "yesterday at 15:00"
    assert recovery_module.when_label(at(days=4), now) == "12 Nov at 15:00"
    assert recovery_module.when_label(at(days=365), now) == "16 Nov 2025 at 15:00"


def test_a_slow_disk_never_holds_the_window_up(app, tmp_path, monkeypatch):
    # Every store call runs on the worker: with each one taking 0.5 s, the
    # window's calls (a write, a list, a clear) all return at once.
    import threading
    import time

    store = app.recovery._recovery
    window_thread = threading.current_thread()
    seen = []

    def slow(name):
        real = getattr(store, name)

        def call(*args, **kwargs):
            seen.append((name, threading.current_thread() is window_thread))
            time.sleep(0.5)
            return real(*args, **kwargs)
        return call

    for name in ("write", "entries", "clear", "read", "remove", "discard"):
        monkeypatch.setattr(store, name, slow(name))
    app.type("C G")
    app.qtbot.waitUntil(
        lambda: app.store.state("DocumentState").value("is_modified") is True, timeout=2000)
    began = time.monotonic()
    app.recovery._write_now()
    app.recovery.refresh()
    app.recovery.clearAll()
    assert time.monotonic() - began < 0.2
    settle(app)
    assert {name for name, _ in seen} == {"write", "entries", "clear"}
    assert not any(on_window for _, on_window in seen)

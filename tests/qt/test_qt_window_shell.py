"""The window shell (plan step C4) and the start-up it runs on (C3).

The whole front end runs in the test process (``qt_app``, tests/qt/conftest.py):
a real session on the Qt host, a FakePlayer, the config under tmp_path.
"""

import json
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, QPointF, QRect, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.constants import WM_CLASS  # noqa: E402
from chordnotepad_desktop import application, window_geometry  # noqa: E402
from chordnotepad_desktop.application import DESKTOP_FILE_NAME, set_identity  # noqa: E402
from chordnotepad_desktop.error_presenter import format_message  # noqa: E402
from chordnotepad_desktop.window_geometry import placed_on_screens  # noqa: E402
from chordnotepad.models.window_geometry import WindowGeometry as Geometry  # noqa: E402
from tests.qt.conftest import PATHS, QtAppHarness, write_config  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DESKTOP_FILE = REPO / "packaging" / "linux" / f"{DESKTOP_FILE_NAME}.desktop"
SONG = "C   G   Am  F\nOne two three four\n"


def item(qt_app, name):
    found = qt_app.window.findChild(QQuickItem, name)
    assert found is not None, name
    return found


def popup(qt_app, name):
    from PySide6.QtCore import QObject

    found = qt_app.window.findChild(QObject, name)
    assert found is not None, name
    return found


def click(qt_app, quick_item):
    centre = quick_item.mapToScene(QPointF(quick_item.width() / 2, quick_item.height() / 2))
    QTest.mouseClick(qt_app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     centre.toPoint())


def shown(qt_app, qtbot):
    qtbot.waitUntil(lambda: qt_app.window.property("contentReady") is True, timeout=3000)


def focus(qt_app, qtbot):
    qt_app.window.requestActivate()
    qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is qt_app.window, timeout=1000)


def no_quick_start(tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False)


def edit(qt_app, qtbot, text=SONG):
    qt_app.store.submit("set_text", {"text": text, "client_token": 1})
    qtbot.waitUntil(lambda: qt_app.window.title() == "Untitled* - Chord Notepad", timeout=1000)


def saved_config(harness):
    return json.loads(harness.config_file().read_text(encoding="utf-8"))


@pytest.fixture
def shell(qapp, qtbot, tmp_path):
    """qt_app without Quick Start at startup (most tests don't want it)."""
    no_quick_start(tmp_path)
    harness = QtAppHarness(qapp, tmp_path).start()
    shown(harness, qtbot)
    yield harness
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


# -- start-up -----------------------------------------------------------------------------


def test_start_up_runs_in_the_tk_apps_order(qapp, qtbot, tmp_path, monkeypatch):
    order = []

    def record(name, real):
        def wrapper(*args, **kwargs):
            order.append(name)
            return real(*args, **kwargs)
        return wrapper

    from chordnotepad.services.playback_service import PlaybackService
    from chordnotepad_desktop.qt_host import QtHost
    from chordnotepad.session.session import AppSession

    monkeypatch.setattr(PlaybackService, "initialize_player",
                        record("audio", PlaybackService.initialize_player))
    monkeypatch.setattr(application, "create_session", record("session", application.create_session))
    monkeypatch.setattr(application, "load_main_window", record("window", application.load_main_window))
    monkeypatch.setattr(QtHost, "start", record("host", QtHost.start))
    monkeypatch.setattr(AppSession, "start", record("session.start", AppSession.start))
    no_quick_start(tmp_path)
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        assert order == ["audio", "session", "window", "host", "session.start"]
        assert harness.app.renderer == "software"           # QT_QUICK_BACKEND in the tests
    finally:
        harness.shutdown()


def test_start_up_logs_the_build_in_tks_block(qapp, tmp_path, caplog):
    no_quick_start(tmp_path)
    harness = QtAppHarness(qapp, tmp_path, build_info={
        "VERSION": "v0.6.0", "BUILD_TYPE": "release", "BUILD_NUMBER": "42",
        "COMMIT_SHORT": "abc1234", "BUILD_DATE": "2026-11-16"})
    with caplog.at_level("INFO", logger="chordnotepad_desktop.application"):
        harness.start()
    try:
        lines = [r.getMessage() for r in caplog.records
                 if r.name == "chordnotepad_desktop.application"]
        start = lines.index("Chord Notepad") - 1
        assert lines[start:start + 9] == [
            "=" * 60, "Chord Notepad", "=" * 60,
            "Version:      v0.6.0", "Build Type:   release", "Build Number: 42",
            "Commit:       abc1234", "Build Date:   2026-11-16", "=" * 60]
    finally:
        harness.shutdown()


def test_without_build_info_the_log_shows_the_dev_local_build(qapp, tmp_path, caplog):
    no_quick_start(tmp_path)
    harness = QtAppHarness(qapp, tmp_path)
    with caplog.at_level("INFO", logger="chordnotepad_desktop.application"):
        harness.start()
    try:
        lines = [r.getMessage() for r in caplog.records]
        assert f"Version:      v{PATHS.read_version()} (dev-local)" in lines
        assert "Build Type:   development" in lines
    finally:
        harness.shutdown()


def test_the_window_starts_hidden_until_the_ratio_settles(shell):
    assert shell.window.isVisible()
    assert shell.window.contentItem().opacity() == 1


def test_the_app_is_named_as_the_desktop_file_says(qapp):
    desktop = DESKTOP_FILE.read_text(encoding="utf-8")
    before = (qapp.applicationName(), qapp.desktopFileName(), qapp.windowIcon())
    try:
        set_identity(qapp, PATHS)
        # X11: Qt's window class is the application name (WM_CLASS).
        assert qapp.applicationName() == WM_CLASS
        assert f"StartupWMClass={WM_CLASS}" in desktop.splitlines()
        # Wayland: the app id is the desktop file's name.
        assert qapp.desktopFileName() == DESKTOP_FILE_NAME and DESKTOP_FILE.is_file()
        icon = qapp.windowIcon()
        assert not icon.isNull()
        assert {s.width() for s in icon.availableSizes()} >= {32, 128, 256}
    finally:
        qapp.setApplicationName(before[0])
        qapp.setDesktopFileName(before[1])
        qapp.setWindowIcon(before[2])


def test_no_icon_without_resources():
    from chordnotepad.app_paths import AppPaths

    assert application.window_icon(AppPaths()) is None


# -- the title and the tab strip ----------------------------------------------------------------


def test_the_title_and_the_unsaved_dot_follow_the_document(shell, qtbot):
    assert shell.window.title() == "Untitled - Chord Notepad"
    assert item(shell, "documentName").property("text") == "Untitled"
    assert not item(shell, "unsavedDot").isVisible()
    edit(shell, qtbot)
    assert item(shell, "unsavedDot").isVisible()


def test_the_tabs_switch_the_workspace(shell, qtbot):
    stack = item(shell, "workspaces")
    assert shell.window.property("mode") == "edit" and stack.property("currentIndex") == 0
    click(shell, item(shell, "playTab"))
    qtbot.waitUntil(lambda: shell.window.property("mode") == "play", timeout=1000)
    assert stack.property("currentIndex") == 1
    assert item(shell, "playWorkspace").isVisible() and not item(shell, "editWorkspace").isVisible()
    click(shell, item(shell, "editTab"))
    qtbot.waitUntil(lambda: shell.window.property("mode") == "edit", timeout=1000)


def test_ctrl_1_and_ctrl_2_switch_the_workspace(shell, qtbot):
    focus(shell, qtbot)
    QTest.keyClick(shell.window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: shell.window.property("mode") == "play", timeout=1000)
    assert item(shell, "workspaceTabs").property("currentIndex") == 1
    QTest.keyClick(shell.window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: shell.window.property("mode") == "edit", timeout=1000)


# -- closing --------------------------------------------------------------------------------------


def test_closing_without_changes_saves_the_geometry_and_closes(shell, qtbot):
    shell.window.resize(820, 540)
    qtbot.wait(20)
    shell.window.close()
    qtbot.waitUntil(lambda: not shell.window.isVisible(), timeout=2000)
    config = shell.app.core.config
    assert config.get("window_geometry").startswith("820x540")
    assert config.get("window_maximized") is False
    shell.shutdown()
    assert saved_config(shell)["window_geometry"].startswith("820x540")


def test_closing_with_changes_asks_first_and_cancel_keeps_the_window(shell, qtbot):
    edit(shell, qtbot)
    shell.window.close()
    dialog = popup(shell, "unsavedDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert shell.window.isVisible()
    assert dialog.property("title") == "Unsaved Changes"
    click(shell, item(shell, "unsavedCancel"))
    qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    qtbot.wait(50)
    assert shell.window.isVisible()
    assert shell.app._session.pending_request is None


def test_escape_is_cancel(shell, qtbot):
    edit(shell, qtbot)
    focus(shell, qtbot)
    shell.window.close()
    dialog = popup(shell, "unsavedDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    QTest.keyClick(shell.window, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    qtbot.waitUntil(lambda: shell.app._session.pending_request is None, timeout=1000)
    assert shell.window.isVisible()


def test_dont_save_closes_without_saving(shell, qtbot):
    edit(shell, qtbot)
    shell.window.close()
    dialog = popup(shell, "unsavedDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    click(shell, item(shell, "unsavedDiscard"))
    qtbot.waitUntil(lambda: not shell.window.isVisible(), timeout=2000)


def test_save_writes_the_document_then_closes(shell, qtbot, tmp_path):
    song = tmp_path / "song.txt"
    song.write_text("C\n", encoding="utf-8")
    shell.store.submit("open_document", {"ref": {"id": str(song), "display_name": "song.txt",
                                                 "location": str(song)}, "read_only": False})
    qtbot.waitUntil(lambda: shell.window.title() == "song.txt - Chord Notepad", timeout=2000)
    shell.store.submit("set_text", {"text": SONG, "client_token": 1})
    qtbot.waitUntil(lambda: shell.window.title() == "song.txt* - Chord Notepad", timeout=2000)
    shell.window.close()
    dialog = popup(shell, "unsavedDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    click(shell, item(shell, "unsavedSave"))
    qtbot.waitUntil(lambda: not shell.window.isVisible(), timeout=2000)
    assert song.read_text(encoding="utf-8") == SONG


def test_save_of_an_untitled_song_asks_where_and_a_cancel_keeps_the_window(shell, qtbot):
    edit(shell, qtbot)
    shell.window.close()
    dialog = popup(shell, "unsavedDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    click(shell, item(shell, "unsavedSave"))
    # The Save As picker (F3): cancelling it cancels the close.
    picker = popup(shell, "filePicker")
    qtbot.waitUntil(lambda: picker.property("visible") is True, timeout=2000)
    assert picker.property("title") == "Save File As"
    QMetaObject.invokeMethod(picker, "reject")
    qtbot.waitUntil(lambda: shell.app._session.pending_request is None, timeout=2000)
    qtbot.wait(50)
    assert shell.window.isVisible()


# -- geometry -------------------------------------------------------------------------------------


def test_the_saved_geometry_is_restored(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="1000x700+40+30")
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        assert (harness.window.width(), harness.window.height()) == (1000, 700)
        assert (harness.window.x(), harness.window.y()) == (40, 30)
    finally:
        harness.shutdown()


def test_a_saved_size_below_the_minimum_grows_to_it(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="300x200+40+30")
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        window = harness.window
        assert (window.width(), window.height()) == (window.minimumWidth(), window.minimumHeight())
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
        assert harness.app.core.config.get("window_geometry") == (
            f"{window.minimumWidth()}x{window.minimumHeight()}+40+30")
    finally:
        harness.shutdown()


def test_a_maximized_window_comes_back_maximized_and_keeps_its_normal_size(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="1000x700+40+30",
                 window_maximized=True)
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        qtbot.waitUntil(lambda: bool(harness.window.windowStates() & Qt.WindowState.WindowMaximized),
                        timeout=2000)
        harness.window.close()
        qtbot.waitUntil(lambda: not harness.window.isVisible(), timeout=2000)
        assert harness.app.core.config.get("window_geometry") == "1000x700+40+30"
        assert harness.app.core.config.get("window_maximized") is True
    finally:
        harness.shutdown()


def test_an_unreadable_geometry_falls_back_to_the_default_size(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="huge")
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        assert (harness.window.width(), harness.window.height()) == (900, 600)
    finally:
        harness.shutdown()


def test_the_window_opens_and_saves_in_logical_pixels(qapp, qtbot, tmp_path, monkeypatch):
    # Tk saved last, at 125%: its physical pixels become logical ones, and
    # on close Qt writes its neutral bounds and leaves Tk's string alone
    # (it still converts to the same place).
    monkeypatch.setattr(window_geometry, "tk_scale", lambda window: 1.25)
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="1250x875+50+25")
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        window = harness.window
        assert (window.width(), window.height(), window.x(), window.y()) == (1000, 700, 40, 20)
        window.resize(1100, 700)
        qtbot.wait(20)
        window.close()
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
        config = harness.app.core.config
        assert config.get("window_bounds") == {"width": 1100, "height": 700, "x": 40, "y": 20}
        assert config.get("window_geometry") == "1375x875+50+25"
        assert config.get("window_maximized") is False
    finally:
        harness.shutdown()


def test_qt_reads_its_own_bounds_before_tks_string(qapp, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(window_geometry, "tk_scale", lambda window: 1.25)
    write_config(tmp_path, show_quick_start_on_startup=False, window_geometry="1250x875+50+25",
                 window_bounds={"width": 960, "height": 640, "x": 10, "y": 12})
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        window = harness.window
        assert (window.width(), window.height(), window.x(), window.y()) == (960, 640, 10, 12)
    finally:
        harness.shutdown()


def test_a_place_off_every_screen_is_dropped():
    screens = [QRect(0, 0, 1920, 1080), QRect(1920, 0, 1280, 1024)]
    assert placed_on_screens(Geometry(800, 600, 2000, 100), screens).has_position
    assert placed_on_screens(Geometry(800, 600, -780, 10), screens).has_position is False
    assert placed_on_screens(Geometry(800, 600, 5000, 5000), screens) == Geometry(800, 600)
    assert placed_on_screens(Geometry(800, 600), screens) == Geometry(800, 600)


# -- dialogs --------------------------------------------------------------------------------------


def test_an_error_is_shown_in_the_window_and_the_next_waits(shell, qtbot):
    dialog = popup(shell, "errorDialog")
    shell.app.presenter.report_event("boom", "test")
    shell.app.presenter.show_message("Audio Error", "No sound")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert dialog.property("title") == "Error"
    assert dialog.property("message") == format_message("boom", shell.app.log_path)
    click(shell, item(shell, "errorOk"))
    qtbot.waitUntil(lambda: dialog.property("title") == "Audio Error", timeout=2000)
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    click(shell, item(shell, "errorOk"))
    qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    assert shell.app.presenter.showing is None
    shell.unexpected.clear()


def test_a_command_the_bridge_refuses_is_shown(shell, qtbot):
    dialog = popup(shell, "errorDialog")
    shell.store.submit("no_such_command")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert "unknown command 'no_such_command'" in dialog.property("message")
    assert shell.unexpected and shell.unexpected[0][0] == "bridge"
    shell.unexpected.clear()


def test_the_sessions_user_errors_and_audio_failures_are_shown(shell, qtbot):
    shell.app._on_event("UserError", {"title": "Could not open", "message": "Gone"})
    assert shell.app.presenter.showing == ("Could not open", "Gone")
    shell.app.presenter.dismissed()
    shell.app._on_event("AudioUnavailable", {"message": "No output", "from_click": True})
    assert shell.app.presenter.showing == ("Audio Error", "No output")


def test_quick_start_opens_at_startup_and_dont_show_again_sticks(qt_app, qtbot):
    dialog = popup(qt_app, "quickStartDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=3000)
    qtbot.waitUntil(lambda: item(qt_app, "quickStartPageIndicator").property("text").startswith("1 / "),
                    timeout=2000)
    assert item(qt_app, "quickStartPageTitle").property("text")
    assert not item(qt_app, "quickStartPrevious").isEnabled()
    click(qt_app, item(qt_app, "quickStartNext"))
    qtbot.waitUntil(lambda: item(qt_app, "quickStartPageIndicator").property("text").startswith("2 / "),
                    timeout=1000)
    click(qt_app, item(qt_app, "quickStartDontShow"))
    click(qt_app, item(qt_app, "quickStartClose"))
    qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    qtbot.waitUntil(lambda: qt_app.store.state("StartupState").value("screen") == "none", timeout=1000)
    assert qt_app.app.core.config.get("show_quick_start_on_startup") is False


def test_closing_quick_start_keeps_the_setting(qt_app, qtbot):
    dialog = popup(qt_app, "quickStartDialog")
    qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=3000)
    focus(qt_app, qtbot)
    QTest.keyClick(qt_app.window, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    qtbot.waitUntil(lambda: qt_app.store.state("StartupState").value("screen") == "none", timeout=1000)
    assert qt_app.app.core.config.get("show_quick_start_on_startup") is True


def test_no_quick_start_when_turned_off(shell, qtbot):
    qtbot.wait(300)
    assert popup(shell, "quickStartDialog").property("visible") is False
    assert shell.store.state("StartupState").value("screen") == "none"

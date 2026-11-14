"""The Qt window's chrome (plan steps F1-F4): the menus and their shortcuts,
the Edit toolbar, the file pickers and the recent list, the status bar.

The whole front end runs in the test process (QtAppHarness with a FakePlayer,
as in test_qt_editor.py). The core's side (the config keys, the commands,
EditRefused, the shared texts) is tests/test_session_chrome.py.
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import (  # noqa: E402
    Q_ARG, Q_RETURN_ARG, QCoreApplication, QEvent, QMetaObject, QObject, QPointF, Qt, QUrl,
)
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.session import formatting, toolbar_texts  # noqa: E402
from chordnotepad_desktop import chrome, files as files_module  # noqa: E402
from chordnotepad_desktop.main import QML_DIR  # noqa: E402
from chordnotepad_desktop.status_bar import READ_ONLY_NOTICE, refused_notice  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, Editor, start  # noqa: E402
from tests.qt.test_qt_value_picker import find  # noqa: E402

SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
SONG = "C   G   Am  F\nOne two three four\n"


class Chrome(Editor):
    """The editor harness plus the chrome's items, actions and menus."""

    @property
    def model(self):
        return self.harness.app.chrome

    @property
    def files(self):
        return self.model.files

    def obj(self, name):
        """A QObject child by objectName (Actions, Menus, the FileDialog)."""
        found = self.window.findChild(QObject, name)
        assert found is not None, name
        return found

    def it(self, name):
        """An item in the visual tree (menu rows sit under the overlay)."""
        found = find(self.window.contentItem(), name)
        assert found is not None, name
        return found

    def trigger(self, name):
        QMetaObject.invokeMethod(self.obj(name), "trigger")
        self.run()

    def click_item(self, it, modifier=NO_MODIFIER):
        centre = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, modifier, centre)
        self.run()

    def submitted_names(self):
        return [name for name, _ in self.submitted]

    def song(self, text=SONG):
        self.store.submit("restore_draft", {"text": text, "document": None, "modified": False,
                                            "read_only": False})
        self.qtbot.waitUntil(lambda: self.text() == text, timeout=2000)
        self.settle()

    def picker(self):
        return self.obj("filePicker")

    def wait_picker(self, title):
        picker = self.picker()
        self.qtbot.waitUntil(lambda: picker.property("visible") is True, timeout=2000)
        assert picker.property("title") == title
        return picker

    def menu_texts(self, menu):
        """A Menu's rows as shown: text, "---" for a separator, "[zoom]" for the zoom row."""
        rows = []
        for i in range(menu.property("count")):
            item = menu_item_at(menu, i)
            name = item.metaObject().className()
            if "MenuSeparator" in name:
                rows.append("---")
            elif item.objectName() == "appMenuZoom":
                rows.append("[zoom]")
            else:
                rows.append(item.property("text"))
        return rows


def menu_item_at(menu, index):
    """A Menu's index-th item (Container.itemAt; PySide can't hand a Menu's
    QML methods over directly)."""
    return QMetaObject.invokeMethod(menu, "itemAt", Q_RETURN_ARG("QQuickItem*"), Q_ARG(int, index))


def plain_text(text):
    """A menu text without its mnemonic."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


@pytest.fixture
def app(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    ed = Chrome(harness, qtbot)
    qtbot.waitUntil(lambda: ed.area.hasActiveFocus(), timeout=1000)
    yield ed
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def restarted(qapp, qtbot, tmp_path, **config):
    harness = start(qapp, qtbot, tmp_path, **config)
    return Chrome(harness, qtbot)


# -- F1: shortcuts -------------------------------------------------------------------------

#: The checklist's window shortcuts (§2), the F5 sidebars (Ctrl+Shift+D/I) and
#: E4's chord sheet (F9, Alt+1..4) aside.
WINDOW_SHORTCUTS = {
    "Ctrl+N": "AppActions.qml", "Ctrl+O": "AppActions.qml", "Ctrl+S": "AppActions.qml",
    "Ctrl+Shift+S": "AppActions.qml", "Ctrl+Q": "AppActions.qml", "Ctrl+A": "EditorPane.qml",
    "Ctrl+=": "EditorPane.qml", "Ctrl++": "EditorPane.qml", "Ctrl+-": "EditorPane.qml",
    "Ctrl+0": "EditorPane.qml", "F1": "AppActions.qml", "Ctrl+Z": "EditorPane.qml",
    "Ctrl+Y": "EditorPane.qml", "Ctrl+Shift+Z": "EditorPane.qml", "Ctrl+X": "EditorPane.qml",
    "Ctrl+C": "EditorPane.qml", "Ctrl+V": "EditorPane.qml", "Ctrl+1": "AppActions.qml",
    "Ctrl+2": "AppActions.qml", "F5": "PlaybackActions.qml", "Shift+F5": "PlaybackActions.qml",
    "Ctrl+Shift+L": "AppActions.qml", "Ctrl+Alt+=": "AppActions.qml",
    "Ctrl+Alt+-": "AppActions.qml", "Ctrl+Alt+0": "AppActions.qml", "F11": "AppActions.qml",
    "Ctrl+M": "PlaybackActions.qml", "Ctrl+]": "PlaybackActions.qml",
    "Ctrl+[": "PlaybackActions.qml", "Ctrl+\\": "PlaybackActions.qml",
    "Ctrl+T": "AppActions.qml", "Ctrl+,": "AppActions.qml", "Alt+Down": "EditorPane.qml",
    "F10": "AppActions.qml",
}


def declared_sequences():
    """Every key sequence a QML file declares: ``shortcut:``, ``sequence:``
    and the strings of ``sequences: [...]``, as (portable text, file)."""
    found = []
    for path in QML_DIR.rglob("*.qml"):
        code = "\n".join(line.split("//")[0] for line in path.read_text(encoding="utf-8").splitlines())
        keys = re.findall(r'\b(?:shortcut|sequence)\s*:\s*"((?:[^"\\]|\\.)+)"', code)
        for group in re.findall(r'\bsequences\s*:\s*\[([^\]]*)\]', code):
            keys += re.findall(r'"((?:[^"\\]|\\.)+)"', group)
        for key in keys:
            key = key.replace("\\\\", "\\")
            text = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)
            assert text, f"{path.name}: {key!r} isn't a key sequence"
            found.append((text, path.name))
    return found


def test_no_key_sequence_is_declared_twice():
    """Two Actions or Shortcuts with one sequence are ambiguous: neither fires."""
    keys = [k for k, _ in declared_sequences()]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    assert duplicates == [], [(k, f) for k, f in declared_sequences() if k in duplicates]


def test_every_window_shortcut_of_the_checklist_is_declared_where_expected():
    declared = set(declared_sequences())
    for key, file in WINDOW_SHORTCUTS.items():
        text = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)
        assert (text, file) in declared, key


def test_redo_is_ctrl_y_and_ctrl_shift_z(app):
    app.type("ab")
    app.settle()
    app.key(Qt.Key.Key_Z, CTRL)
    app.run()
    assert app.text() == ""
    app.key(Qt.Key.Key_Y, CTRL)
    app.qtbot.waitUntil(lambda: app.text() == "ab", timeout=1000)
    app.key(Qt.Key.Key_Z, CTRL)
    app.run()
    app.key(Qt.Key.Key_Z, CTRL | SHIFT)
    app.qtbot.waitUntil(lambda: app.text() == "ab", timeout=1000)


def press(app, key, modifiers, text=""):
    """A key press and release with ``text`` as typed (upper case with Caps Lock)."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(app.window, QKeyEvent(kind, key, modifiers, text))
    app.run()


def test_the_shortcuts_work_with_caps_lock_on(app):
    # Caps Lock changes the text, not the key or the modifiers.
    press(app, Qt.Key.Key_T, CTRL, "\x14")
    app.qtbot.waitUntil(lambda: app.obj("transposeDialog").property("opened") is True, timeout=2000)
    app.key(Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: app.obj("transposeDialog").property("visible") is False, timeout=2000)
    press(app, Qt.Key.Key_N, CTRL, "N")
    assert "new_document" in app.submitted_names()


def test_a_modal_dialog_blocks_the_window_shortcuts(app):
    app.trigger("transposeAction")
    app.qtbot.waitUntil(lambda: app.obj("transposeDialog").property("opened") is True, timeout=2000)
    app.key(Qt.Key.Key_N, CTRL)
    app.key(Qt.Key.Key_S, CTRL)
    assert "new_document" not in app.submitted_names()
    assert "save" not in app.submitted_names()


def test_the_file_shortcuts_send_their_commands(app):
    app.key(Qt.Key.Key_N, CTRL)
    app.key(Qt.Key.Key_S, CTRL | SHIFT)
    names = app.submitted_names()
    assert "new_document" in names and "save_as" in names
    app.wait_picker("Save File As")
    QMetaObject.invokeMethod(app.picker(), "reject")
    app.run()


def test_ctrl_1_and_2_switch_the_workspace(app):
    app.key(Qt.Key.Key_2, CTRL)
    assert app.window.property("mode") == "play"
    assert app.obj("playModeAction").property("checked") is True
    app.key(Qt.Key.Key_1, CTRL)
    assert app.window.property("mode") == "edit"
    assert app.obj("editModeAction").property("checked") is True


def test_ctrl_q_asks_to_close(app):
    app.key(Qt.Key.Key_Q, CTRL)
    assert "request_close" in app.submitted_names()


def test_f11_toggles_full_screen(app):
    app.key(Qt.Key.Key_F11)
    app.qtbot.waitUntil(lambda: app.obj("fullScreenAction").property("checked") is True, timeout=1000)
    app.key(Qt.Key.Key_F11)
    app.qtbot.waitUntil(lambda: app.obj("fullScreenAction").property("checked") is False, timeout=1000)


# -- F1: the ☰ menu ------------------------------------------------------------------------


def open_app_menu(app):
    menu = app.obj("appMenu")
    app.click_item(app.it("appMenuButton"))
    app.qtbot.waitUntil(lambda: menu.property("opened") is True, timeout=1000)
    return menu


def test_the_app_menu_has_the_groups_in_order(app):
    menu = open_app_menu(app)
    assert app.it("appMenuButton").property("checked") is True
    rows = [plain_text(r) if r not in ("---", "[zoom]") else r for r in app.menu_texts(menu)]
    assert rows == ["New", "Open…", "Open recent", "Save", "Save as…", "---", "[zoom]", "---",
                    "Export MIDI…", "---", "Show menu bar", "Dark theme", "---", "Settings…",
                    "---", "Help", "---", "Quit"]


def test_a_second_click_on_the_burger_closes_the_menu(app):
    menu = open_app_menu(app)
    app.click_item(app.it("appMenuButton"))
    app.qtbot.waitUntil(lambda: menu.property("visible") is False, timeout=1000)
    app.run(100)
    assert menu.property("visible") is False
    assert app.it("appMenuButton").property("checked") is False


#: A new minimum window size (it is in units, which follow the scale) is
#: passed on to the platform; the offscreen one says it can't (xcb can).
SIZE_HINTS = pytest.mark.qt_log_ignore("does not support propagateSizeHints")


@SIZE_HINTS
def test_the_zoom_row_scales_the_window_and_keeps_it(app):
    open_app_menu(app)
    app.run(150)                 # the menu's open transition
    app.click_item(app.it("scaleInButton"))
    app.qtbot.waitUntil(lambda: app.model.uiScale == pytest.approx(1.1), timeout=1000)
    assert app.it("scalePercent").property("text") == "110%"
    app.click_item(app.it("scaleResetButton"))
    app.qtbot.waitUntil(lambda: app.model.uiScale == pytest.approx(1.0), timeout=1000)
    assert "set_ui_scale" in app.submitted_names()


@SIZE_HINTS
def test_the_ui_scale_shortcuts_stay_within_70_and_200_percent(app):
    for _ in range(5):
        app.key(Qt.Key.Key_Minus, CTRL | ALT)
    app.qtbot.waitUntil(lambda: app.model.uiScale == pytest.approx(0.7), timeout=1000)
    assert app.obj("scaleDownAction").property("enabled") is False
    app.key(Qt.Key.Key_0, CTRL | ALT)
    for _ in range(12):
        app.key(Qt.Key.Key_Equal, CTRL | ALT)
    app.qtbot.waitUntil(lambda: app.model.uiScale == pytest.approx(2.0), timeout=1000)
    app.run()
    assert app.session.ui_scale == pytest.approx(2.0)


@SIZE_HINTS
def test_the_ui_scale_is_restored(qapp, qtbot, tmp_path):
    ed = restarted(qapp, qtbot, tmp_path, ui_scale=1.3)
    try:
        assert ed.model.uiScale == pytest.approx(1.3)
        assert ed.obj("scaleResetAction").property("enabled") is True
    finally:
        ed.harness.shutdown()


def test_dark_theme_toggles_and_is_kept(app):
    app.key(Qt.Key.Key_L, CTRL | SHIFT)
    app.qtbot.waitUntil(lambda: app.obj("darkAction").property("checked") is True, timeout=2000)
    assert app.session.settings_values().ui_theme == "dark"
    app.key(Qt.Key.Key_L, CTRL | SHIFT)
    app.qtbot.waitUntil(lambda: app.obj("darkAction").property("checked") is False, timeout=2000)
    assert app.session.settings_values().ui_theme == "light"


# -- F1: the menu bar ------------------------------------------------------------------------


def alt_tap(app):
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(app.window, QKeyEvent(kind, Qt.Key.Key_Alt, ALT))
    app.run()


def test_the_menu_bar_is_hidden_and_an_alt_tap_shows_it(app):
    bar = app.obj("appMenuBar")
    assert bar.property("visible") is False
    alt_tap(app)
    app.qtbot.waitUntil(lambda: bar.property("visible") is True, timeout=1000)
    app.key(Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: bar.property("visible") is False, timeout=1000)
    alt_tap(app)
    app.qtbot.waitUntil(lambda: bar.property("visible") is True, timeout=1000)
    alt_tap(app)
    app.qtbot.waitUntil(lambda: bar.property("visible") is False, timeout=1000)
    alt_tap(app)
    app.qtbot.waitUntil(lambda: bar.property("visible") is True, timeout=1000)
    app.click_item(app.area)                      # a click below it
    app.qtbot.waitUntil(lambda: bar.property("visible") is False, timeout=1000)


def test_a_shortcut_with_alt_in_it_isnt_an_alt_tap(app):
    # Qt hands the key to the shortcut, so the window never sees it; the
    # watcher learns of it from the ShortcutOverride.
    bar = app.obj("appMenuBar")
    app.key(Qt.Key.Key_0, CTRL | ALT)
    app.key(Qt.Key.Key_Down, ALT)
    app.run(50)
    assert bar.property("visible") is False


def test_alt_letter_opens_that_menu_while_the_bar_is_hidden(app):
    bar = app.obj("appMenuBar")
    app.key(Qt.Key.Key_P, ALT)
    playback = app.obj("playbackMenu")
    app.qtbot.waitUntil(lambda: playback.property("opened") is True, timeout=1000)
    assert bar.property("visible") is True
    app.key(Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: playback.property("visible") is False, timeout=1000)
    app.qtbot.waitUntil(lambda: bar.property("visible") is False, timeout=1000)


def test_f10_opens_the_file_menu(app):
    app.key(Qt.Key.Key_F10)
    file_menu = app.obj("fileMenu")
    app.qtbot.waitUntil(lambda: file_menu.property("opened") is True, timeout=1000)
    rows = [plain_text(r) for r in app.menu_texts(file_menu)]
    assert rows == ["New", "Open…", "Open recent", "---", "Save", "Save as…", "Export MIDI…",
                    "---", "Quit"]


def test_show_menu_bar_keeps_it_and_is_kept(qapp, qtbot, tmp_path):
    ed = restarted(qapp, qtbot, tmp_path)
    try:
        bar = ed.obj("appMenuBar")
        ed.trigger("menuBarAction")
        ed.qtbot.waitUntil(lambda: bar.property("visible") is True, timeout=1000)
        assert ed.obj("menuBarAction").property("checked") is True
        alt_tap(ed)                       # a tap doesn't hide a kept bar
        assert bar.property("visible") is True
        ed.run()
        assert ed.session.menu_bar_shown is True
    finally:
        ed.harness.shutdown()
    saved = json.loads(ed.harness.config_file().read_text(encoding="utf-8"))
    assert saved["menu_bar_shown"] is True
    ed = restarted(qapp, qtbot, tmp_path, menu_bar_shown=saved["menu_bar_shown"])
    try:
        assert ed.obj("appMenuBar").property("visible") is True
    finally:
        ed.harness.shutdown()


def test_the_menus_list_every_command(app):
    expect = {
        "editMenu": ["Undo", "Redo", "---", "Cut", "Copy", "Paste", "---", "Select all"],
        "viewMenu": ["Edit", "Play", "---", "Chord sheet under the text", "Chord sheet view", "---", "Word wrap",
                     "Larger text", "Smaller text", "Reset text size", "---",
                     "Zoom in (whole window)", "Zoom out (whole window)", "Reset zoom (100%)",
                     "Full screen", "---", "Show menu bar", "Dark theme"],
        "playbackMenu": ["Play", "Stop and rewind", "---", "Metronome", "Faster", "Slower",
                         "Normal speed (100%)", "---", "Voicing", "Instrument"],
        "toolsMenu": ["Transpose…", "Suggest capo…", "---", "Convert to American notation",
                      "Convert to European notation", "---", "Settings…"],
        "helpMenu": ["User guide", "Quick start", "Keyboard shortcuts", "---",
                     "Open source licences", "About Chord Notepad"],
    }
    for name, rows in expect.items():
        menu = app.obj(name)
        assert [plain_text(r) if r != "---" else r for r in app.menu_texts(menu)] == rows, name


def test_undo_and_redo_are_disabled_on_an_empty_stack_q3(app):
    undo, redo = app.obj("undoAction"), app.obj("redoAction")
    assert undo.property("enabled") is False and redo.property("enabled") is False
    assert app.it("undoButton").property("enabled") is False
    assert app.it("redoButton").property("enabled") is False
    app.type("a")
    app.settle()
    assert undo.property("enabled") is True and app.it("undoButton").property("enabled") is True
    app.click_item(app.it("undoButton"))
    app.qtbot.waitUntil(lambda: app.text() == "", timeout=1000)
    assert redo.property("enabled") is True and app.it("redoButton").property("enabled") is True


def test_the_voicing_submenu_is_disabled_while_playing(app):
    app.harness.player.auto_play = False
    app.song()
    voicing = app.obj("barVoicingMenu")
    assert voicing.property("enabled") is True
    app.store.submit("play_pause", {"from_offset": None})
    app.qtbot.waitUntil(lambda: voicing.property("enabled") is False, timeout=3000)
    app.store.submit("stop")
    app.qtbot.waitUntil(lambda: voicing.property("enabled") is True, timeout=3000)


def test_transpose_and_convert_stay_enabled_while_playing_as_in_tk(app):
    app.harness.player.auto_play = False
    app.song()
    app.store.submit("play_pause", {"from_offset": None})
    app.qtbot.waitUntil(lambda: app.harness.app.status_bar.playing, timeout=3000)
    for name in ("transposeAction", "suggestCapoAction", "toAmericanAction", "toEuropeanAction"):
        assert app.obj(name).property("enabled") is True, name
    app.store.submit("stop")


def test_the_mac_menu_bar_is_native_and_always_there():
    chrome.configure_menu_bar(mac=True)
    try:
        assert not QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)
    finally:
        chrome.configure_menu_bar(mac=False)
    assert QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)


def test_on_the_mac_the_bar_shows_and_show_menu_bar_is_off(app):
    model = chrome.ChromeModel(app.store, mac=True)
    assert model.mac is True
    # The QML reads chrome.mac: shown always, the toggle disabled (AppActions).
    code = (QML_DIR / "app" / "AppMenuBar.qml").read_text(encoding="utf-8")
    assert "bar.chrome.mac || bar.chrome.menuBarShown || bar.peek" in code
    assert "enabled: !acts.chrome.mac" in (QML_DIR / "app" / "AppActions.qml").read_text(encoding="utf-8")


def test_portal_dialogs_are_asked_for_on_linux_with_a_session_bus_only(tmp_path):
    socket = tmp_path / "bus"
    socket.write_text("")
    bus = {"DBUS_SESSION_BUS_ADDRESS": f"unix:path={socket}"}
    env = dict(bus)
    assert chrome.prefer_portal_file_dialogs(env, "linux") is True
    assert env["QT_QPA_PLATFORMTHEME"] == "xdgdesktopportal"
    assert chrome.prefer_portal_file_dialogs({**bus, "QT_QPA_PLATFORMTHEME": "kde"}, "linux") is False
    assert chrome.prefer_portal_file_dialogs({**bus, "CHORD_NOTEPAD_FILE_DIALOG": "qt"}, "linux") is False
    assert chrome.prefer_portal_file_dialogs(dict(bus), "win32") is False
    assert chrome.prefer_portal_file_dialogs(dict(bus), "darwin") is False
    assert chrome.prefer_portal_file_dialogs({}, "linux") is False
    assert chrome.prefer_portal_file_dialogs(
        {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"}, "linux") is False
    assert chrome.prefer_portal_file_dialogs(
        {"DBUS_SESSION_BUS_ADDRESS": "unix:abstract=/tmp/dbus-x,guid=1"}, "linux") is True


# -- F2: the Edit toolbar ------------------------------------------------------------------


def test_the_toolbar_has_labels_when_wide_and_icons_when_narrow(app):
    transpose = app.it("transposeButton")
    app.window.resize(1200, 600)
    app.qtbot.waitUntil(lambda: transpose.property("showLabel") is True, timeout=1000)
    assert app.it("convertButton").property("showLabel") is True
    app.window.resize(700, 600)
    app.qtbot.waitUntil(lambda: transpose.property("showLabel") is False, timeout=1000)
    assert app.it("toolbarPlay").property("showLabel") is True      # Play keeps its label
    assert app.it("toolbarSep1").property("visible") is True


def test_the_notation_toggle_has_tks_tooltips_and_switches(app):
    ab, do = app.it("notation:american"), app.it("notation:european")
    assert ab.property("checked") is True and do.property("checked") is False
    toggle = app.it("notationToggle")
    assert toggle.property("americanTip") == toolbar_texts.AMERICAN_TOOLTIP
    assert toggle.property("europeanTip") == toolbar_texts.EUROPEAN_TOOLTIP
    app.click_item(do)
    app.qtbot.waitUntil(lambda: do.property("checked") is True, timeout=1000)
    assert ("set_notation", {"notation": "european"}) in app.submitted


def test_convert_converts_to_the_other_notation(app):
    app.song()
    button = app.it("convertButton")
    assert button.property("tip") == toolbar_texts.convert_tooltip("european")
    app.click_item(button)
    app.qtbot.waitUntil(lambda: app.text().startswith("Do"), timeout=2000)
    app.qtbot.waitUntil(lambda: button.property("tip") == toolbar_texts.convert_tooltip("american"),
                        timeout=2000)


def test_transpose_on_the_toolbar_opens_the_dialog(app):
    app.click_item(app.it("transposeButton"))
    app.qtbot.waitUntil(lambda: app.obj("transposeDialog").property("opened") is True, timeout=2000)
    app.key(Qt.Key.Key_Escape)


def test_play_and_stop_on_the_toolbar(app):
    app.harness.player.auto_play = False
    app.song()
    play = app.it("toolbarPlay")
    assert play.property("tip") == app.harness.app.player.playTooltip("play")
    app.click_item(play)
    app.qtbot.waitUntil(lambda: play.property("text") == "Pause", timeout=3000)
    app.click_item(app.it("toolbarStop"))
    app.qtbot.waitUntil(lambda: play.property("text") == "Play", timeout=3000)
    assert app.it("toolbarStop").property("tip") == toolbar_texts.STOP_TOOLTIP
    assert "stop" in app.submitted_names()


def test_shift_click_on_play_plays_from_the_cursor(app):
    app.harness.player.auto_play = False
    app.song()
    app.set_cursor(8)
    app.click_item(app.it("toolbarPlay"), SHIFT)
    app.qtbot.waitUntil(lambda: app.harness.app.status_bar.playing, timeout=3000)
    plays = [args for name, args in app.submitted if name == "play_pause"]
    assert plays and plays[-1]["from_offset"] == 8
    app.store.submit("stop")


# -- F3: files -----------------------------------------------------------------------------


def _pending(app):
    """The request the open picker answers."""
    return app.files._pending


def choose(app, path):
    """Choose ``path`` in the open picker (FileDialogs.qml's Accepted path)."""
    picker = app.picker()
    QMetaObject.invokeMethod(app.obj("fileDialogs"), "choose",
                             Q_ARG("QVariant", QUrl.fromLocalFile(str(path)).toString()))
    app.qtbot.waitUntil(lambda: picker.property("visible") is False, timeout=2000)
    app.run()


def accept(app, path):
    """Choose ``path`` and wait for the session to have the answer."""
    choose(app, path)
    app.qtbot.waitUntil(lambda: app.session.pending_request is None, timeout=2000)


def test_open_shows_tks_picker_and_opens_the_file(app, tmp_path):
    song = tmp_path / "Hymn.txt"
    song.write_text("G D\nAmazing grace\n", encoding="utf-8")
    app.key(Qt.Key.Key_O, CTRL)
    picker = app.wait_picker("Open File")
    assert list(picker.property("nameFilters")) == ["Text Files (*.txt)", "All Files (*)"]
    assert app.text() == ""                      # Q4: Ctrl+O typed nothing
    accept(app, song)
    app.qtbot.waitUntil(lambda: app.text() == "G D\nAmazing grace\n", timeout=2000)
    assert app.window.title() == "Hymn.txt - Chord Notepad"


def test_save_as_suggests_the_name_with_its_extension_and_adds_it(app, tmp_path):
    app.type("C G")
    app.settle()
    app.trigger("saveAsAction")
    picker = app.wait_picker("Save File As")
    assert picker.property("selectedFile").fileName() == "Untitled.txt"
    accept(app, tmp_path / "mine")                # typed without ".txt"
    app.qtbot.waitUntil(lambda: (tmp_path / "mine.txt").exists(), timeout=2000)
    assert (tmp_path / "mine.txt").read_text(encoding="utf-8") == "C G"
    assert app.window.title() == "mine.txt - Chord Notepad"


def test_an_added_extension_that_names_a_file_asks_before_replacing_it(app, tmp_path):
    (tmp_path / "old.txt").write_text("keep", encoding="utf-8")
    app.type("C G")
    app.settle()
    app.trigger("saveAsAction")
    app.wait_picker("Save File As")
    choose(app, tmp_path / "old")
    dialog = app.obj("confirmReplaceDialog")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert dialog.property("title") == formatting.CONFIRM_REPLACE_TITLE
    assert app.it("confirmReplaceText").property("text") == formatting.confirm_replace_message("old.txt")
    app.click_item(app.it("replaceNo"))
    app.qtbot.waitUntil(lambda: app.session.pending_request is None, timeout=2000)
    assert (tmp_path / "old.txt").read_text(encoding="utf-8") == "keep"
    # Again, and replace it this time.
    app.trigger("saveAsAction")
    app.wait_picker("Save File As")
    choose(app, tmp_path / "old")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    app.click_item(app.it("replaceYes"))
    app.qtbot.waitUntil(lambda: (tmp_path / "old.txt").read_text(encoding="utf-8") == "C G",
                        timeout=2000)


def test_a_second_request_while_the_picker_is_open_is_cancelled(app):
    app.trigger("openAction")
    app.wait_picker("Open File")
    first = _pending(app)
    app.store.submit("export_midi")              # a song without chords: says so, asks nothing
    app.files._on_request("PickDocumentRequest", {"request_id": 999, "mode": "save",
                                                  "suggested_name": "x.txt"})
    app.run()
    assert _pending(app) == first
    assert ("respond", {"request_id": 999, "value": None}) in app.submitted
    QMetaObject.invokeMethod(app.picker(), "reject")
    app.qtbot.waitUntil(lambda: app.session.pending_request is None, timeout=2000)


def test_export_midi_without_chords_gets_the_existing_message(app):
    app.trigger("exportMidiAction")
    dialog = app.obj("errorDialog")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert app.it("errorMessage").property("text") == formatting.NO_CHORDS_TO_EXPORT_MESSAGE
    assert app.picker().property("visible") is False
    app.click_item(app.it("errorOk"))


def test_export_midi_suggests_the_mid_name_and_writes_it(app, tmp_path):
    app.song()
    app.trigger("exportMidiAction")
    picker = app.wait_picker("Export MIDI")
    assert picker.property("selectedFile").fileName() == "Untitled.mid"
    assert list(picker.property("nameFilters")) == ["MIDI files (*.mid)", "All files (*)"]
    accept(app, tmp_path / "song")
    app.qtbot.waitUntil(lambda: (tmp_path / "song.mid").exists(), timeout=10000)
    assert (tmp_path / "song.mid").read_bytes().startswith(b"MThd")


def test_the_recent_list_tells_same_names_apart_and_opens_one(app, tmp_path):
    for folder in ("Band", "Choir"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "song.txt").write_text(f"{folder}\n", encoding="utf-8")
        app.trigger("openAction")
        app.wait_picker("Open File")
        accept(app, tmp_path / folder / "song.txt")
        app.qtbot.waitUntil(lambda f=folder: app.text() == f"{f}\n", timeout=2000)
    labels = list(app.files.recentLabels)
    assert labels == ["song.txt — Choir", "song.txt — Band"]
    recent = app.obj("menuBarRecent")
    rows = app.menu_texts(recent)
    assert rows == ["song.txt — Choir", "song.txt — Band"]
    app.files.openRecent(1)
    app.qtbot.waitUntil(lambda: app.text() == "Band\n", timeout=2000)


def test_an_empty_recent_list_says_so_disabled(app):
    recent = app.obj("appMenuRecent")
    item = menu_item_at(recent, 0)
    assert item.property("text") == formatting.NO_RECENT_FILES
    assert item.property("enabled") is False


def test_the_filters_are_qts_form_of_tks():
    assert files_module.name_filters(formatting.TEXT_FILE_TYPES) == [
        "Text Files (*.txt)", "All Files (*)"]


def test_keyboard_shortcuts_opens_that_help_page(tmp_path):
    from chordnotepad_desktop.help_opener import HelpOpener
    (tmp_path / "index.html").write_text("i")
    (tmp_path / "shortcuts.html").write_text("s")
    opened = []
    opener = HelpOpener(tmp_path, open_url=lambda url: opened.append(url) or True, sandboxed=False)
    assert opener.open("shortcuts.html").endswith("/shortcuts.html")
    assert opener.open("missing.html").endswith("/index.html")
    assert opener.open("../x.html").endswith("/index.html")


# -- F4: the status bar ----------------------------------------------------------------------


def status(app):
    return app.harness.app.status_bar


def test_the_status_bar_starts_ready_with_ln_col_and_the_notation(app):
    assert app.it("statusText").property("text") == "Ready"
    assert app.it("caretPosition").property("text") == "Ln 1, Col 1"
    assert app.it("notationName").property("text") == "American"
    assert app.it("readOnlyNotice").property("visible") is False
    assert app.it("playingDot").property("visible") is False


def test_ln_col_follow_the_caret_in_characters(app):
    app.song("C G\nAm \U0001F600 F\n")
    app.set_cursor(len("C G\nAm \U0001F600 ".encode("utf-16-le")) // 2)
    app.qtbot.waitUntil(lambda: app.it("caretPosition").property("text") == "Ln 2, Col 6",
                        timeout=1000)


def test_the_notation_follows_the_song(app):
    app.click_item(app.it("notation:european"))
    app.qtbot.waitUntil(lambda: app.it("notationName").property("text") == "European", timeout=1000)


def test_while_playing_the_bar_says_read_only_and_how_to_stop(app):
    app.harness.player.auto_play = False
    app.song()
    app.store.submit("play_pause", {"from_offset": None})
    notice = app.it("readOnlyNotice")
    app.qtbot.waitUntil(lambda: notice.property("visible") is True, timeout=3000)
    assert notice.property("text") == READ_ONLY_NOTICE == "Read-only while playing · Shift+F5 stops"
    assert app.it("caretPosition").property("visible") is False
    assert app.it("playingDot").property("visible") is True
    assert status(app).noticeWarning is False
    app.key(Qt.Key.Key_F5, SHIFT)
    app.qtbot.waitUntil(lambda: notice.property("visible") is False, timeout=3000)
    assert app.it("caretPosition").property("visible") is True


def test_an_edit_refused_while_playing_says_so_q9(app):
    app.harness.player.auto_play = False
    app.song()
    app.store.submit("play_pause", {"from_offset": None})
    notice = app.it("readOnlyNotice")
    app.qtbot.waitUntil(lambda: notice.property("visible") is True, timeout=3000)
    app.trigger("toEuropeanAction")              # the session refuses it
    app.qtbot.waitUntil(lambda: status(app).noticeWarning is True, timeout=2000)
    assert notice.property("text") == refused_notice(formatting.EDIT_REFUSED_MESSAGE)
    assert app.text() == SONG
    app.store.submit("stop")
    app.qtbot.waitUntil(lambda: notice.property("visible") is False, timeout=3000)
    assert status(app).noticeWarning is False


def test_typing_into_the_locked_text_says_why(app):
    app.harness.player.auto_play = False
    app.song()
    app.store.submit("play_pause", {"from_offset": None})
    app.qtbot.waitUntil(lambda: status(app).playing, timeout=3000)
    app.area.forceActiveFocus()
    app.type("x")
    app.qtbot.waitUntil(lambda: status(app).noticeWarning is True, timeout=1000)
    assert app.text() == SONG
    app.store.submit("stop")

"""The rail and the Directives palette (plan step F5): sidebars.py, IconRail.qml,
SidebarActions.qml, DirectivePalette.qml and SnippetTile.qml.

The tiles' data, the template filling and ``insert_snippet`` are the core's
(tests/test_snippets.py); the open sidebar and its width are config keys
(tests/test_session_sidebars.py). These check the window: the rail, its
shortcuts and the gear, the kept width, the tiles, their tooltips, a click
or a key inserting at the caret with the value selected and the focus back
in the editor, the arrow keys, and the tiles locked while a song plays.
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtQml import qmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.session.snippets import PALETTE  # noqa: E402
from chordnotepad_desktop import sidebars  # noqa: E402
from chordnotepad_desktop.main import QML_DIR  # noqa: E402
from tests.qt.conftest import QtAppHarness  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, Editor, song, start  # noqa: E402
from tests.qt.test_qt_value_picker import find, texts_shown  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
TILE_IDS = [t.id for g in PALETTE for t in g.snippets]


class Window(Editor):
    """The started app with the sidebars' helpers."""

    def find(self, name):
        found = find(self.window.contentItem(), name)
        assert found is not None, name
        return found

    def centre(self, item):
        return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()

    def click_item(self, item, button=LEFT, modifier=NO_MODIFIER):
        QTest.mouseClick(self.window, button, modifier, self.centre(item))
        self.run()

    def hover(self, item, ms=700):
        # From somewhere else first: a move to where the pointer already is
        # (an earlier test's click) isn't a hover.
        QTest.mouseMove(self.window, self.centre(item) + QPoint(3, 3))
        self.run(10)
        QTest.mouseMove(self.window, self.centre(item))
        self.run(ms)

    @property
    def sidebars(self):
        return self.harness.app.sidebars

    def box_visible(self):
        return self.find("sidebarBox").isVisible()

    def tile(self, tile_id):
        return self.find("tileButton:" + tile_id)

    def unit(self):
        """Theme.u, the layout unit (Theme.px(n) is n of them, rounded)."""
        return qmlEngine(self.window).singletonInstance("CNTheme", "Theme").property("u")

    def focused_name(self):
        item = self.window.activeFocusItem()
        return item.objectName() if item is not None else None


def started(qapp, qtbot, tmp_path, **config):
    harness = start(qapp, qtbot, tmp_path, **config)
    w = Window(harness, qtbot)
    qtbot.waitUntil(lambda: w.area.hasActiveFocus(), timeout=1000)
    return w


def finish(w):
    warnings, unexpected = list(w.harness.app.warnings), list(w.harness.unexpected)
    w.harness.shutdown()
    w.qtbot.wait(1)
    assert warnings == [] and unexpected == []


@pytest.fixture
def win(qapp, qtbot, tmp_path):
    w = started(qapp, qtbot, tmp_path)
    yield w
    finish(w)


# -- the rail -----------------------------------------------------------------------------


def test_a_first_start_has_the_palette_open(win):
    assert win.sidebars.current == "directives"
    assert win.box_visible() and win.find("directivePalette").isVisible()
    assert not win.find("identifierPanel").isVisible()
    # 76 units wide (the mockup's), the editor beside it.
    box = win.find("sidebarBox")
    assert box.width() == pytest.approx(round(76 * win.unit()), abs=1)


def test_the_rail_switches_and_the_active_icon_collapses(win):
    win.click_item(win.find("rail:identifier"))
    assert win.sidebars.current == "identifier"
    win.qtbot.waitUntil(lambda: win.find("identifierPanel").isVisible(), timeout=1000)
    assert ("set_sidebar", {"sidebar": "identifier"}) in win.submitted
    win.click_item(win.find("rail:identifier"))
    assert win.sidebars.current == "" and not win.box_visible()
    assert win.session.sidebar == ""
    win.click_item(win.find("rail:directives"))
    assert win.sidebars.current == "directives" and win.box_visible()
    # The editor still fills the rest.
    assert win.area.isVisible()


def test_the_rail_icons_tooltips_name_their_shortcuts(win):
    win.hover(win.find("rail:directives"))
    assert any("Directives" in t and "Ctrl+Shift+D" in t for t in texts_shown(win.window.contentItem()))
    win.hover(win.find("rail:identifier"))
    assert any("Chord identifier" in t and "Ctrl+Shift+I" in t for t in texts_shown(win.window.contentItem()))


def test_the_gear_opens_settings(win):
    win.click_item(win.find("rail:settings"))
    settings = win.window.findChild(QQuickWindow, "settingsWindow")
    win.qtbot.waitUntil(lambda: settings.isVisible(), timeout=2000)
    settings.close()


def test_the_shortcuts_open_focus_and_collapse(win):
    win.key(Qt.Key.Key_I, CTRL_SHIFT)
    win.run()
    assert win.sidebars.current == "identifier"
    win.qtbot.waitUntil(lambda: win.focused_name() == "notesField", timeout=1000)
    win.key(Qt.Key.Key_D, CTRL_SHIFT)
    win.run()
    assert win.sidebars.current == "directives"
    win.qtbot.waitUntil(lambda: win.focused_name() == "tileButton:" + TILE_IDS[0], timeout=1000)
    # Escape goes back to the text, the sidebar stays.
    win.key(Qt.Key.Key_Escape)
    win.qtbot.waitUntil(lambda: win.area.hasActiveFocus(), timeout=1000)
    assert win.sidebars.current == "directives"
    # Again on the open one: collapsed, the editor keeps the focus.
    win.key(Qt.Key.Key_D, CTRL_SHIFT)
    win.run()
    assert win.sidebars.current == "" and win.area.hasActiveFocus()


def test_from_play_a_shortcut_goes_to_edit_with_that_sidebar(win):
    win.window.setProperty("mode", "play")
    win.run()
    win.key(Qt.Key.Key_D, CTRL_SHIFT)
    win.run()
    assert win.window.property("mode") == "edit" and win.sidebars.current == "directives"
    win.window.setProperty("mode", "play")
    win.run()
    win.key(Qt.Key.Key_I, CTRL_SHIFT)
    win.run()
    assert win.window.property("mode") == "edit" and win.sidebars.current == "identifier"


def test_the_actions_are_there_for_the_menus_and_declared_once():
    code = (QML_DIR / "app" / "SidebarActions.qml").read_text(encoding="utf-8")
    assert re.search(r'objectName: "directivesAction"[^}]*shortcut: "Ctrl\+Shift\+D"', code)
    assert re.search(r'objectName: "identifierAction"[^}]*shortcut: "Ctrl\+Shift\+I"', code)
    sequences = [s for p in QML_DIR.rglob("*.qml")
                 for s in re.findall(r'(?:shortcut|sequence):\s*"([^"]+)"', p.read_text(encoding="utf-8"))]
    assert sequences.count("Ctrl+Shift+D") == 1 and sequences.count("Ctrl+Shift+I") == 1


def test_the_actions_follow_the_open_sidebar(win):
    directives, identifier = win.item("directivesAction"), win.item("identifierAction")
    assert directives.property("checked") is True and identifier.property("checked") is False
    win.click_item(win.find("rail:identifier"))
    assert directives.property("checked") is False and identifier.property("checked") is True


def test_the_sidebar_and_its_width_are_kept(qapp, qtbot, tmp_path):
    w = started(qapp, qtbot, tmp_path, sidebar="identifier", sidebar_width=100)
    try:
        box = w.find("sidebarBox")
        u = w.unit()
        assert w.sidebars.current == "identifier" and w.find("identifierPanel").isVisible()
        assert box.width() == pytest.approx(round(100 * u), abs=1)
        # Drag the splitter 10 units to the right.
        y = box.height() / 2
        grip = box.mapToScene(QPointF(box.width() + 1, y)).toPoint()
        QTest.mousePress(w.window, LEFT, NO_MODIFIER, grip)
        for step in range(1, 11):
            QTest.mouseMove(w.window, grip + QPoint(round(step * u), 0))
            w.run(5)
        QTest.mouseRelease(w.window, LEFT, NO_MODIFIER, grip + QPoint(round(10 * u), 0))
        w.run()
        assert w.session.sidebar_width == pytest.approx(110, abs=0.6)
        # Too narrow stops at the minimum.
        w.sidebars.setWidth(10)
        w.run()
        assert w.session.sidebar_width == 56
    finally:
        finish(w)
    saved = json.loads(QtAppHarness(qapp, tmp_path).root.joinpath(
        "config", "chord-notepad", "settings.json").read_text(encoding="utf-8"))
    assert (saved["sidebar"], saved["sidebar_width"]) == ("identifier", 56)


@pytest.mark.qt_log_ignore("does not support propagateSizeHints")
def test_after_a_drag_the_sidebar_still_follows_the_ui_scale(qapp, qtbot, tmp_path):
    w = started(qapp, qtbot, tmp_path, sidebar="directives", sidebar_width=80)
    try:
        box = w.find("sidebarBox")
        u = w.unit()
        grip = box.mapToScene(QPointF(box.width() + 1, box.height() / 2)).toPoint()
        QTest.mousePress(w.window, LEFT, NO_MODIFIER, grip)
        for step in range(1, 11):
            QTest.mouseMove(w.window, grip + QPoint(round(step * u), 0))
            w.run(5)
        QTest.mouseRelease(w.window, LEFT, NO_MODIFIER, grip + QPoint(round(10 * u), 0))
        w.run()
        assert w.session.sidebar_width == pytest.approx(90, abs=0.6)
        kept = w.sidebars.width
        # F5's note feared the drag broke the width's binding. It doesn't (SplitView
        # writes the attached preferredWidth from C++), so a UI-scale change
        # still scales the kept units.
        w.harness.app.chrome.stepUiScale(1)
        w.qtbot.waitUntil(lambda: w.unit() > u, timeout=1000)
        w.run()
        assert box.width() == pytest.approx(round(kept * w.unit()), abs=1)
    finally:
        finish(w)


# -- the palette --------------------------------------------------------------------------


def test_the_tiles_are_the_cores_palette(win):
    groups = sidebars.palette_groups()
    assert [g["title"] for g in groups] == [g.title for g in PALETTE]
    assert len(TILE_IDS) == 16
    for tile_id in TILE_IDS:
        assert win.tile(tile_id).isVisible()
    for group in groups:
        assert win.find("paletteGroup:" + group["title"]).isVisible()


def test_a_tiles_tooltip_names_it_shows_the_syntax_and_says_what_a_click_does(win):
    tile = win.find("tile:loop-3")
    tip = tile.property("tip")
    assert "<b>Repeat ×3</b>" in tip and "{loop: verse 3}" in tip
    assert "Plays the labelled section this many times." in tip and "Click to insert" in tip
    win.hover(tile, 600)
    assert any("Repeat ×3" in t for t in texts_shown(win.window.contentItem()))


def test_a_click_inserts_at_the_caret_with_the_value_selected_and_the_focus_back(win):
    song(win, "C G\n")
    win.set_cursor(3)
    win.click_item(win.tile("tempo"))
    win.qtbot.waitUntil(lambda: "{bpm: 120}" in win.text(), timeout=2000)
    assert win.text() == "C G {bpm: 120}\n"
    assert win.area.property("selectedText") == "120"
    win.qtbot.waitUntil(lambda: win.area.hasActiveFocus(), timeout=1000)
    # Typing replaces the value; one undo takes the insert back.
    win.type("90")
    win.qtbot.waitUntil(lambda: win.session.text == "C G {bpm: 90}\n", timeout=2000)
    assert ("insert_snippet", {"offset": 3, "text": "{bpm: 120}", "snap": False}) in win.submitted


def test_the_template_is_filled_for_the_song(win):
    song(win, "{label: verse}\nDo Sol\n")
    win.store.submit("set_notation", {"notation": "european"})
    win.run()
    win.set_cursor(len(win.text()))
    win.click_item(win.tile("key-minor"))
    win.qtbot.waitUntil(lambda: "{key: Lam}" in win.text(), timeout=2000)
    win.set_cursor(len(win.text()))
    win.click_item(win.tile("label"))
    win.qtbot.waitUntil(lambda: "{label: verse2}" in win.text(), timeout=2000)
    assert win.area.property("selectedText") == "verse2"


def test_enter_and_space_insert_and_the_arrows_move(win):
    song(win, "C\n")
    win.set_cursor(1)
    first = win.tile(TILE_IDS[0])
    first.forceActiveFocus()
    win.key(Qt.Key.Key_Right)
    assert win.focused_name() == "tileButton:" + TILE_IDS[1]
    win.key(Qt.Key.Key_Left)
    assert win.focused_name() == "tileButton:" + TILE_IDS[0]
    # Left/Right cross the groups: the last tempo tile, then "time".
    win.tile("tempo-reset").forceActiveFocus()
    win.key(Qt.Key.Key_Right)
    assert win.focused_name() == "tileButton:time"
    # Down: the nearest tile in the next row; Up comes back.
    start_tile = win.tile("tempo")
    start_tile.forceActiveFocus()
    win.key(Qt.Key.Key_Down)
    below = win.window.activeFocusItem()
    assert below.objectName() != "tileButton:tempo"
    assert below.mapToScene(QPointF(0, 0)).y() > start_tile.mapToScene(QPointF(0, 0)).y()
    assert abs(below.mapToScene(QPointF(0, 0)).x() - start_tile.mapToScene(QPointF(0, 0)).x()) < start_tile.width()
    win.key(Qt.Key.Key_Up)
    assert win.focused_name() == "tileButton:tempo"
    # Enter inserts and gives the editor the focus.
    win.tile("rest").forceActiveFocus()
    win.key(Qt.Key.Key_Return)
    win.qtbot.waitUntil(lambda: win.text() == "C NC\n", timeout=2000)
    assert win.area.hasActiveFocus()
    win.set_cursor(len("C NC"))
    win.tile("capo").forceActiveFocus()
    win.key(Qt.Key.Key_Space)
    win.qtbot.waitUntil(lambda: "{capo: 3}" in win.text(), timeout=2000)
    assert win.area.property("selectedText") == "3" and win.area.hasActiveFocus()


def test_the_tiles_are_locked_while_playing_and_say_why(win):
    win.harness.player.auto_play = False
    song(win, "C G\n")
    win.store.submit("play_pause", {"from_offset": None})
    win.qtbot.waitUntil(lambda: win.area.property("readOnly") is True, timeout=3000)
    for tile_id in TILE_IDS:
        assert win.tile(tile_id).property("enabled") is False
    tile = win.find("tile:tempo")
    assert sidebars.LOCKED_REASON in tile.property("tip")
    win.hover(tile, 600)
    assert any(sidebars.LOCKED_REASON in t for t in texts_shown(win.window.contentItem()))
    win.click_item(win.tile("tempo"))
    assert not any(name == "insert_snippet" for name, _ in win.submitted)
    win.store.submit("stop")
    win.qtbot.waitUntil(lambda: win.tile("tempo").property("enabled") is True, timeout=3000)

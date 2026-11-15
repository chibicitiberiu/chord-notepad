"""Drag and drop from the sidebars into the text (the mockup's; parity checklist §12).

A palette tile or an identifier candidate dragged over the text: the chip by
the pointer, the closed hand where it can drop and the no-drop sign
elsewhere, the drop caret where it would go in (snapped off the middle of a
word or directive by the core's ``snippets.drop_offset``), and the drop as
one ``insert_snippet`` (one undo step). A click still inserts as before.
Nothing drags while the editor is read-only, and a drop over the locked text
is refused. The snap and the insert text are the core's
(tests/test_snippets.py).
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad_desktop import sidebars  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, song  # noqa: E402
from tests.qt.test_qt_identifier import Panel  # noqa: E402
from tests.qt.test_qt_sidebars import finish, started  # noqa: E402
from tests.qt.test_qt_value_picker import texts_shown  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
SONG = "{bpm: 90}\nAm      G   F\nRemember me to one who lives there\n"
REMEMBER = SONG.index("Remember")


@pytest.fixture
def win(qapp, qtbot, tmp_path):
    w = started(qapp, qtbot, tmp_path)
    p = Panel(w.harness, qtbot)
    song(p, SONG)
    yield p
    while QGuiApplication.overrideCursor() is not None:     # a failed test's drag
        QGuiApplication.restoreOverrideCursor()
    finish(p)


def override(w):
    cursor = QGuiApplication.overrideCursor()
    return cursor.shape() if cursor is not None else None


def chip(w):
    return w.window.findChild(QQuickItem, "dragChip")


def drop_pos(w):
    return w.find("editorPane").property("dropPos")


def press_and_move(w, source, target, steps=12):
    a, b = w.centre(source), target
    QTest.mousePress(w.window, LEFT, NO_MODIFIER, a)
    w.run(20)
    for i in range(1, steps + 1):
        QTest.mouseMove(w.window, QPoint(round(a.x() + (b.x() - a.x()) * i / steps),
                                         round(a.y() + (b.y() - a.y()) * i / steps)))
        w.run(10)
    QTest.mouseMove(w.window, b)
    w.run(30)


def release(w, at):
    QTest.mouseRelease(w.window, LEFT, NO_MODIFIER, at)
    w.run(60)


def show_candidates(w):
    w.sidebars.show("identifier")
    w.qtbot.waitUntil(lambda: w.find("identifierPanel").isVisible(), timeout=1000)
    w.type_notes("C E G")
    w.qtbot.waitUntil(lambda: w.model.property("candidates")[:1] == ["C"], timeout=1000)
    w.area.forceActiveFocus()


def test_a_tile_dragged_into_a_word_lands_before_it_with_its_value_selected(win):
    source = win.find("tileDrag:key-major")
    on_the_way = win.centre(win.find("tileDrag:capo"))
    press_and_move(win, source, on_the_way)
    # Over the sidebar: the chip, the no-drop sign, no drop caret.
    assert chip(win).isVisible() and win.find("dragChipText").property("text") == "{key: G}"
    assert override(win) == Qt.CursorShape.ForbiddenCursor and drop_pos(win) == -1
    target = win.point_of(REMEMBER + 2)                    # Re|member: nearer its start
    for p in (target + QPoint(-1, 0), target):
        QTest.mouseMove(win.window, p)
        win.run(30)
    assert override(win) == Qt.CursorShape.ClosedHandCursor
    assert drop_pos(win) == REMEMBER and win.find("dropCaret").isVisible()
    release(win, target)
    win.qtbot.waitUntil(lambda: win.text() == SONG.replace("Remember", "{key: G} Remember"), timeout=2000)
    assert ("insert_snippet", {"offset": REMEMBER, "text": "{key: G}", "snap": True}) in win.submitted
    assert win.area.property("selectedText") == "G" and win.area.hasActiveFocus()
    # The drag is over: no chip, no caret, the pointer the items' own again.
    assert not chip(win).isVisible() and override(win) is None and drop_pos(win) == -1
    QTest.keyClick(win.window, Qt.Key.Key_Z, CTRL)
    win.qtbot.waitUntil(lambda: win.text() == SONG, timeout=1000)


def test_a_tile_dropped_off_the_text_inserts_nothing(win):
    source = win.find("tileDrag:tempo")
    elsewhere = win.centre(win.find("tileDrag:capo"))
    press_and_move(win, source, elsewhere)
    assert chip(win).isVisible() and override(win) == Qt.CursorShape.ForbiddenCursor
    release(win, elsewhere)
    assert not chip(win).isVisible() and override(win) is None
    assert win.text() == SONG and not [n for n, _ in win.submitted if n == "insert_snippet"]


def test_a_tile_click_still_inserts_at_the_caret(win):
    win.set_cursor(len(SONG))
    win.click_item(win.find("tileDrag:capo"))
    win.qtbot.waitUntil(lambda: win.text().endswith("{capo: 3}"), timeout=2000)
    assert ("insert_snippet", {"offset": len(SONG), "text": "{capo: 3}", "snap": False}) in win.submitted
    assert win.area.property("selectedText") == "3" and not chip(win).isVisible()


def test_the_tooltips_say_a_tile_or_chord_can_be_dragged(win):
    assert sidebars.TILE_ACTION == "Click to insert · drag to place"
    assert "Click to insert · drag to place" in win.find("tile:tempo").property("tip")
    show_candidates(win)
    win.hover(win.candidate("C"), 1000)
    assert "Click to play, double-click to insert at the caret, or drag into the text." in texts_shown(win.window.contentItem())


def test_a_candidate_dragged_into_the_text_goes_in_spaced_as_one_undo_step(win):
    show_candidates(win)
    target = win.gap_point(SONG.index("G   F") + 2)        # in the spaces after G: no snap
    press_and_move(win, win.find("candidate:C"), target)
    assert chip(win).isVisible() and win.find("dragChipText").property("text") == "C"
    assert override(win) == Qt.CursorShape.ClosedHandCursor
    assert drop_pos(win) == SONG.index("G   F") + 2
    release(win, target)
    win.qtbot.waitUntil(lambda: win.text() == SONG.replace("G   F", "G C  F"), timeout=2000)
    assert not [n for n, _ in win.submitted if n == "insert_chord"]
    QTest.keyClick(win.window, Qt.Key.Key_Z, CTRL)
    win.qtbot.waitUntil(lambda: win.text() == SONG, timeout=1000)


def test_a_candidate_double_click_and_play_still_work(win):
    show_candidates(win)
    win.set_cursor(SONG.index("\nRemember"))
    QTest.mouseDClick(win.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      win.centre(win.candidate("C")))
    win.run()
    win.qtbot.waitUntil(lambda: win.text() == SONG.replace("F\n", "F C \n"), timeout=2000)
    assert ("insert_chord", {"at": SONG.index("\nRemember"), "chord": "C"}) in win.submitted
    win.hover(win.candidate("C"), 50)
    win.click_item(win.find("hear:C"))
    assert [a for n, a in win.submitted if n == "play_identified_chord"] == [
        {"chord": "C", "rolled": False}, {"chord": "C", "rolled": False}]      # the first click, then ▶
    assert not chip(win).isVisible()


def play(w):
    w.harness.player.auto_play = False
    w.store.submit("play_pause", {"from_offset": None})
    w.qtbot.waitUntil(lambda: w.area.property("readOnly") is True, timeout=3000)


def test_nothing_drags_while_the_editor_is_read_only(win):
    show_candidates(win)
    play(win)
    target = win.point_of(REMEMBER)
    press_and_move(win, win.find("candidate:C"), target)
    assert not chip(win).isVisible() and override(win) is None
    release(win, target)
    win.sidebars.show("directives")
    win.qtbot.waitUntil(lambda: win.find("directivePalette").isVisible(), timeout=1000)
    press_and_move(win, win.find("tile:tempo"), target)
    assert not chip(win).isVisible() and override(win) is None
    release(win, target)
    assert win.text() == SONG
    assert not [n for n, _ in win.submitted if n in ("insert_snippet", "insert_chord")]


def test_a_drop_on_text_that_locked_during_the_drag_is_refused(win):
    show_candidates(win)
    source = win.find("candidate:C")
    start_ = win.centre(source)
    press_and_move(win, source, start_ + QPoint(-40, 0), steps=4)
    assert chip(win).isVisible()
    play(win)
    target = win.point_of(REMEMBER)
    for i in range(1, 9):
        QTest.mouseMove(win.window, QPoint(round(start_.x() - 40 + (target.x() - start_.x() + 40) * i / 8),
                                           round(start_.y() + (target.y() - start_.y()) * i / 8)))
        win.run(10)
    assert override(win) == Qt.CursorShape.ForbiddenCursor and drop_pos(win) == -1
    assert not win.find("dropCaret").isVisible()
    release(win, target)
    assert win.text() == SONG and override(win) is None
    assert not [n for n, _ in win.submitted if n == "insert_snippet"]


def test_the_drop_caret_is_where_the_core_puts_the_drop(win):
    bridge = win.bridge
    inside = SONG.index("{bpm: 90}") + 7                   # {bpm: 9|0}: out to the right
    assert bridge.dropPosition(inside) == SONG.index("}") + 1
    assert bridge.dropPosition(REMEMBER + 6) == REMEMBER + 8   # Rememb|er: the end is nearer
    assert bridge.dropPosition(-1) == -1
    # Positions are Qt's (UTF-16): an emoji before counts two.
    song(win, "\U0001F600 Am7 G\n")
    assert bridge.dropPosition(4) == 3 and bridge.dropPosition(5) == 6


def test_the_drag_cursor_is_the_whole_windows_and_goes_back(win):
    bridge = win.bridge
    bridge.setDragCursor(True)
    assert override(win) == Qt.CursorShape.ClosedHandCursor
    bridge.setDragCursor(False)
    assert override(win) == Qt.CursorShape.ForbiddenCursor
    bridge.clearDragCursor()
    assert override(win) is None
    bridge.clearDragCursor()
    assert override(win) is None

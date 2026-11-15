"""The editor under the mouse: the pointer's shape and selecting by dragging.

Tibi's report (KDE Wayland, 2026-11-15): no I-beam over the text, and
selecting text didn't work reliably. Causes: the middle-click MouseArea over
the text set the arrow (a MouseArea always has a shape, and a child's wins
over the TextArea's hover handler, pitfall 28); and the TextArea held each press back
until the pointer moved sideways (pitfall 29, ``text_mouse.py``).
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from tests.qt.test_qt_editor import Editor, song, start  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
TEXT = "{bpm: 90}\n" + "".join(f"C   G   Am  F\nOne two three four {i}\n" for i in range(40))
WORDS = TEXT.index("One two")
NEXT_WORDS = TEXT.index("One two", WORDS + 1)


@pytest.fixture
def ed(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    editor = Editor(harness, qtbot)
    qtbot.waitUntil(lambda: editor.area.hasActiveFocus(), timeout=1000)
    song(editor, TEXT)
    yield editor
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def shape(ed):
    return ed.window.cursor().shape()


def hover(ed, point):
    # Two moves: the window works the shape out from a move.
    QTest.mouseMove(ed.window, point + QPoint(1, 0))
    ed.run(20)
    QTest.mouseMove(ed.window, point)
    ed.run(40)


def centre(item):
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


def selection(ed):
    return ed.area.property("selectionStart"), ed.area.property("selectionEnd")


def flickable(ed):
    return ed.item("editorScroll").property("contentItem")


def drag(ed, points, hold=0):
    QTest.mousePress(ed.window, LEFT, NO_MODIFIER, points[0])
    if hold:
        ed.run(hold)
    for p in points[1:]:
        QTest.mouseMove(ed.window, p)
        ed.run(15)
    QTest.mouseRelease(ed.window, LEFT, NO_MODIFIER, points[-1])
    ed.run(40)


def steps(a, b, n=10):
    return [QPoint(round(a.x() + (b.x() - a.x()) * i / n), round(a.y() + (b.y() - a.y()) * i / n))
            for i in range(n + 1)]


# -- the pointer ---------------------------------------------------------------------------


def test_the_pointer_is_an_ibeam_over_text_and_a_hand_over_chords(ed):
    hover(ed, ed.point_of(WORDS + 5))
    assert shape(ed) == Qt.CursorShape.IBeamCursor
    hover(ed, ed.point_of(TEXT.index("G   Am")))
    assert shape(ed) == Qt.CursorShape.PointingHandCursor
    hover(ed, ed.point_of(TEXT.index("G   Am") + 2))        # the spaces between chords
    assert shape(ed) == Qt.CursorShape.IBeamCursor
    hover(ed, ed.point_of(3))                               # a directive
    assert shape(ed) == Qt.CursorShape.IBeamCursor


def test_the_pointer_is_an_arrow_over_the_value_chip_and_its_picker(ed):
    hover(ed, ed.point_of(3))
    chip = ed.item("pickChip")
    ed.qtbot.waitUntil(chip.isVisible, timeout=1000)
    hover(ed, centre(chip))
    assert shape(ed) == Qt.CursorShape.ArrowCursor
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, centre(chip))
    picker = ed.item("valuePicker")
    ed.qtbot.waitUntil(lambda: picker.property("opened"), timeout=1000)
    hover(ed, centre(picker.property("contentItem")))
    assert shape(ed) == Qt.CursorShape.ArrowCursor


# -- selecting -----------------------------------------------------------------------------


def test_a_drag_down_across_lines_selects(ed):
    # Mostly down, less than the drag distance sideways: the TextArea kept the
    # press until the release, so nothing was selected.
    a, b = ed.gap_point(WORDS + 4), ed.gap_point(NEXT_WORDS + 3)
    assert abs(b.x() - a.x()) < 10 < b.y() - a.y()
    drag(ed, steps(a, b))
    assert selection(ed) == (WORDS + 4, NEXT_WORDS + 3)


def test_a_press_held_still_then_dragged_selects(ed):
    # Held past the press-and-hold time (800 ms), the TextArea dropped the press.
    a, b = ed.gap_point(WORDS + 4), ed.gap_point(WORDS + 13)
    drag(ed, steps(a, b), hold=1000)
    assert selection(ed) == (WORDS + 4, WORDS + 13)


def test_a_click_after_a_double_click_only_moves_the_caret(ed):
    # The press the TextArea handed on late had no timestamp, so it counted as
    # the third click of a triple click and selected the line.
    p = ed.point_of(WORDS + 5)
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, p)
    ed.run(40)
    assert ed.area.property("selectedText") == "two"
    ed.run(600)
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, p, 600)
    ed.run(40)
    start_, end = selection(ed)
    assert start_ == end and WORDS + 4 <= start_ <= WORDS + 7


def test_a_drag_held_below_the_text_keeps_scrolling_and_selecting(ed):
    view = ed.item("editorScroll")
    below = view.mapToScene(QPointF(view.width() / 3, view.height() + 10)).toPoint()
    a = ed.gap_point(WORDS + 4)
    QTest.mousePress(ed.window, LEFT, NO_MODIFIER, a)
    for p in steps(a, below)[1:]:
        QTest.mouseMove(ed.window, p)
        ed.run(15)
    y0, end0 = flickable(ed).property("contentY"), selection(ed)[1]
    ed.run(500)                     # the pointer held still below the text
    y1, end1 = flickable(ed).property("contentY"), selection(ed)[1]
    assert y1 > y0 and end1 > end0
    QTest.mouseRelease(ed.window, LEFT, NO_MODIFIER, below)
    ed.run(40)
    y2, kept = flickable(ed).property("contentY"), selection(ed)
    ed.run(300)
    assert flickable(ed).property("contentY") == y2 and selection(ed) == kept
    assert kept[0] == WORDS + 4


def test_a_drag_still_selects_after_a_chord_click(ed):
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(TEXT.index("G   Am")))
    ed.run(100)
    a, b = ed.gap_point(WORDS + 4), ed.gap_point(NEXT_WORDS + 3)
    drag(ed, steps(a, b))
    assert selection(ed) == (WORDS + 4, NEXT_WORDS + 3)


def test_the_editor_scroll_view_is_found_by_the_mouse_filter(ed):
    from chordnotepad_desktop.text_mouse import _viewport
    view = _viewport(ed.area)
    assert isinstance(view, QQuickItem) and view is flickable(ed)

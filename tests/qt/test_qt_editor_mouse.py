"""The editor under the mouse: the pointer's shape and selecting by dragging.

Tibi's report (KDE Wayland, 2026-11-15): no I-beam over the text. Cause:
the middle-click MouseArea over the text set the arrow (a MouseArea always
has a shape, and a child's wins over the TextArea's hover handler, pitfall 28).
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
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

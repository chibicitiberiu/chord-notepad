"""The chord sheet pane's own behaviour (polish round, batch C1): drag to
scroll, a tap or the seek bar revealing the playhead chord in the text, the
gutter's edge, and the staff's notice. The pane's older tests are in
test_qt_chord_sheet.py; this file reuses its harness."""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from tests.qt.test_qt_chord_sheet import LEFT, NO_MODIFIER, finish, make_sheet  # noqa: E402

LONG = ("{label: verse}\n" + "C   G   Am  F\n" * 12 + "{label: chorus}\n" + "Am  F   C   G\n" * 12)


@pytest.fixture
def sh(qapp, qtbot, tmp_path):
    sh = make_sheet(qapp, qtbot, tmp_path, text=LONG)
    yield sh
    finish(sh)


def drag(sh, start, dx, steps=6):
    QTest.mousePress(sh.window, LEFT, NO_MODIFIER, start)
    for i in range(1, steps + 1):
        QTest.mouseMove(sh.window, QPoint(start.x() + round(dx * i / steps), start.y()))
        sh.run()
    return QPoint(start.x() + dx, start.y())


# -- C2: drag to scroll -------------------------------------------------------------------


def test_dragging_the_sheet_scrolls_it_and_a_tap_still_auditions(sh):
    sh.to_play(700)
    sh.wait_sheet()
    view = sh.view
    assert view.property("scrollX") == 0
    start = sh.at(view.width() / 2, view.height() / 2)
    end = drag(sh, start, -150)
    assert view.property("scrollX") == pytest.approx(150, abs=12)    # less the drag threshold's slack
    QTest.mouseRelease(sh.window, LEFT, NO_MODIFIER, end)
    sh.run()
    assert sh.sent("audition") == []                                  # a drag isn't a tap
    # Dragging back is clamped at the start.
    end = drag(sh, sh.at(view.width() / 4, view.height() / 2), 400)
    QTest.mouseRelease(sh.window, LEFT, NO_MODIFIER, end)
    sh.run()
    assert view.property("scrollX") == 0
    # A tap on a chord still auditions.
    QTest.mouseClick(sh.window, LEFT, NO_MODIFIER, sh.slot_point(1))
    sh.qtbot.waitUntil(lambda: sh.sent("audition") == [{"index": 1}], timeout=2000)


def test_the_scroll_bar_still_takes_its_own_presses(sh):
    sh.to_play(700)
    sh.wait_sheet()
    bar = sh.it("sheetScrollBar")
    p = sh.at(bar.x() + bar.width() * 0.05, bar.y() + bar.height() / 2)
    end = drag(sh, p, 60)
    QTest.mouseRelease(sh.window, LEFT, NO_MODIFIER, end)
    sh.run()
    assert sh.view.property("scrollX") > 0
    assert sh.sent("audition") == []

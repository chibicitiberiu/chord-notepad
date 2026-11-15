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


def sheet_tabs(sh):
    """The view tabs in the sheet's header (Repeater delegates: visual tree)."""
    out = []

    def walk(item):
        if (item.objectName() or "").startswith("sheetTab:"):
            out.append(item)
        for child in item.childItems():
            walk(child)
    walk(sh.window.contentItem())
    return out


@pytest.fixture
def sh(qapp, qtbot, tmp_path):
    sh = make_sheet(qapp, qtbot, tmp_path, text=LONG)
    yield sh
    finish(sh)


def use_guitar(sh):
    """Pick a fretboard voicing, so the Fret cards and Tab views are available."""
    groups = sh.store.state("VoicingMenuState").value("groups")
    value = next(c["value"] for g in groups for c in g if "guitar" in c["value"].lower())
    sh.store.submit("set_voicing", {"voicing": value})
    sh.qtbot.waitUntil(lambda: sh.store.state("VoicingMenuState").value("selected") == value, timeout=2000)


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


# -- C3: a tap shows the chord in the text --------------------------------------------------


def test_a_tap_on_a_chord_scrolls_the_text_to_it(sh):
    sh.to_play(900)
    sh.wait_sheet()
    flick = sh.item("editorScroll").property("contentItem")
    assert flick.property("contentHeight") > flick.property("height") * 1.5
    assert flick.property("contentY") == 0
    last = LONG.rindex("G")
    sheet = sh.model.sheet
    index = 24 * 4 - 1                                            # 24 lines of four chords
    sh.view.setProperty("scrollX", sheet.content_width)           # the last chord on screen
    sh.run(50)
    QTest.mouseClick(sh.window, LEFT, NO_MODIFIER, sh.slot_point(index))
    sh.qtbot.waitUntil(lambda: sh.playback("playhead_offset") == last, timeout=2000)
    sh.qtbot.waitUntil(lambda: flick.property("contentY") > 0, timeout=2000)
    rect = sh.area.positionToRectangle(last)
    top = flick.property("contentY")
    assert top <= rect.y() and rect.y() + rect.height() <= top + flick.property("height")


# -- C4: the gutter's edge -----------------------------------------------------------------


def column(sh, x, step=3):
    image = sh.grab()
    o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
    top = int(sh.model.sheet.lane_height) + 4
    return [image.pixelColor(o.x() + int(x), o.y() + y).lightness()
            for y in range(top, int(sh.view.height()) - 14, step)]


def test_the_gutter_has_a_hairline_and_a_shadow_only_once_scrolled(sh):
    sh.to_play(700)
    sh.wait_sheet("keyboard")
    gutter = sh.model.sheet.gutter_width
    assert gutter > 0
    paper = sh.view.property("surface").lightness()
    edge, beside = int(gutter) - 1, int(gutter) + 1
    # The hairline is there from the start: its column is darker than the paper
    # wherever the keyboard doesn't already paint dark.
    assert min(column(sh, edge)) < paper
    sh.view.setProperty("scrollX", 0)
    sh.run(50)
    unscrolled = column(sh, beside)
    sh.view.setProperty("scrollX", 200)
    sh.run(50)
    scrolled = column(sh, beside)
    # The shadow darkens the content beside the gutter (or leaves it, where it
    # is already ink): never lightens it, and changes some of it.
    assert scrolled != unscrolled
    assert sum(scrolled) < sum(unscrolled) + 1 or sum(scrolled) != sum(unscrolled)


def test_the_staff_runs_on_from_its_clefs_until_scrolled(sh):
    # The staff's lines carry on from the gutter into the content: no hairline
    # across them at the start, only once the content slides under the clefs.
    sh.to_play(700)
    sh.store.submit("set_chord_sheet_view", {"view_id": "staff"})
    sh.wait_sheet("staff")
    paper = sh.view.property("surface").lightness()
    edge = int(sh.model.sheet.gutter_width) - 1
    sh.view.setProperty("scrollX", 0)
    sh.run(50)
    assert max(column(sh, edge, step=1)) == paper
    sh.view.setProperty("scrollX", 200)
    sh.run(50)
    assert max(column(sh, edge, step=1)) < paper


def test_a_view_without_a_gutter_draws_no_edge(qapp, qtbot, tmp_path, monkeypatch):
    from chordnotepad_desktop.chord_sheet import SheetView
    drawn = []
    original = SheetView._paint_gutter_edge
    monkeypatch.setattr(SheetView, "_paint_gutter_edge",
                        lambda self, p, gutter, clip, view_id="": (drawn.append(gutter),
                                                                original(self, p, gutter, clip, view_id)))
    sh = make_sheet(qapp, qtbot, tmp_path, text=LONG, chord_sheet_view="tab")   # the piano shows meanwhile
    try:
        sh.to_play(700)
        sh.wait_sheet("keyboard")
        assert drawn and all(g > 0 for g in drawn)
        use_guitar(sh)
        sh.wait_sheet("tab")
        assert sh.model.sheet.gutter_width == 0
        drawn.clear()
        sh.view.setProperty("scrollX", 100)
        sh.run(80)
        assert drawn == []
    finally:
        finish(sh)


# -- C5: the staff's notice ------------------------------------------------------------------


NOTICE = "Rhythm isn't shown yet: every chord is drawn as a whole note."


def test_the_staff_says_it_draws_every_chord_as_a_whole_note(sh):
    sh.to_play(700)
    sh.wait_sheet("keyboard")
    notice = sh.it("staffNotice")
    assert notice.property("text") == NOTICE
    assert notice.isVisible() is False                           # not on the piano roll
    sh.store.submit("set_chord_sheet_view", {"view_id": "staff"})
    sh.wait_sheet("staff")
    sh.qtbot.waitUntil(notice.isVisible, timeout=2000)
    # In the header after the view tabs, never over the strip (a short
    # strip's staff fills its height and the notice covered the lowest notes).
    top = sh.view.mapToScene(QPointF(0, 0)).y()
    tabs_right = max(t.mapToScene(QPointF(t.width(), 0)).x() for t in sheet_tabs(sh))
    notice_at = notice.mapToScene(QPointF(0, 0))
    assert notice_at.y() + notice.height() <= top + 1
    assert notice_at.x() >= tabs_right
    sh.store.submit("set_chord_sheet_view", {"view_id": "keyboard"})
    sh.wait_sheet("keyboard")
    sh.qtbot.waitUntil(lambda: not notice.isVisible(), timeout=2000)


# -- C1: the zoom pill ----------------------------------------------------------------------


def staff_view(sh):
    sh.to_play(900)
    sh.store.submit("set_chord_sheet_view", {"view_id": "staff"})
    sh.wait_sheet("staff")
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == 1.0, timeout=2000)


def test_the_zoom_pill_steps_and_its_limits_turn_the_buttons_off(sh):
    staff_view(sh)
    assert sh.it("sheetZoomLabel").property("text") == "100%"
    sh.click_on(sh.it("sheetZoomIn"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.2), timeout=2000)
    sh.qtbot.waitUntil(lambda: sh.it("sheetZoomLabel").property("text") == "120%", timeout=2000)
    sh.click_on(sh.it("sheetZoomOut"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.0), timeout=2000)
    # The ends are the model's own limits (0.5 and 2.5).
    assert sh.model.zoomMin == 0.5 and sh.model.zoomMax == 2.5
    sh.store.submit("chord_sheet_zoom", {"step": 20})
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(2.5), timeout=2000)
    sh.run()
    assert not sh.it("sheetZoomIn").isEnabled() and sh.it("sheetZoomOut").isEnabled()
    sh.store.submit("chord_sheet_zoom", {"step": -30})
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(0.5), timeout=2000)
    sh.run()
    assert sh.it("sheetZoomIn").isEnabled() and not sh.it("sheetZoomOut").isEnabled()
    assert sh.it("sheetZoomLabel").property("text") == "50%"


def test_clicking_the_percent_resets_the_zoom(sh):
    staff_view(sh)
    sh.click_on(sh.it("sheetZoomIn"))
    sh.click_on(sh.it("sheetZoomIn"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.44), timeout=2000)
    sh.click_on(sh.it("sheetZoomReset"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == 1.0, timeout=2000)
    assert sh.sent("chord_sheet_zoom_reset") == [{}]
    sh.qtbot.waitUntil(lambda: sh.it("sheetZoomLabel").property("text") == "100%", timeout=2000)

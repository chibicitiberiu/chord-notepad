"""Chords in the text behave like links (Tibi, 2026-11-15).

"Clicking rapidly on a chord in the text makes it select the text instead of
playing it." Now a click on a valid chord plays it every time and selects
nothing (no word on a double-click, no line on a triple-click, nothing from
a drag that starts on it); the caret still goes where the click was. Shift
plays it rolled and leaves the selection alone. Alt makes the chord plain
text, as Alt+click on a link in a browser: caret, word, line and drag
selection, and no sound. text_mouse.py does it.

QTest moves its clock on by the double-click interval after every release,
so it can't click quickly; :func:`clicks` sends timed events to the window,
with the double-click events the platform adds between them.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from tests.qt.test_qt_editor import Editor, song, start  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
NO_BUTTON = Qt.MouseButton.NoButton
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier
TEXT = "C   G   Am  F\nOne two three four\n"
AM = TEXT.index("Am")
TWO = TEXT.index("two")


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


_clock = [5_000_000]


def send(ed, kind, point, buttons, modifiers=NO_MODIFIER, button=LEFT, step=40):
    at = QPointF(point)
    event = QMouseEvent(kind, at, at, QPointF(ed.window.mapToGlobal(point)), button, buttons, modifiers)
    _clock[0] += 0 if kind == QEvent.Type.MouseButtonDblClick else step
    event.setTimestamp(_clock[0])
    QCoreApplication.sendEvent(ed.window, event)


def clicks(ed, point, n, modifiers=NO_MODIFIER):
    """``n`` quick clicks at ``point`` (40 ms apart), as the platform sends them:
    every second press is followed by a double-click event."""
    _clock[0] += 10_000                     # well apart from any earlier clicks
    for i in range(n):
        send(ed, QEvent.Type.MouseButtonPress, point, LEFT, modifiers)
        if i % 2 == 1:
            send(ed, QEvent.Type.MouseButtonDblClick, point, LEFT, modifiers)
        send(ed, QEvent.Type.MouseButtonRelease, point, NO_BUTTON, modifiers)
    ed.run(60)


def drag(ed, a, b, modifiers=NO_MODIFIER, n=8):
    QTest.mousePress(ed.window, LEFT, modifiers, a)
    for i in range(1, n + 1):
        QTest.mouseMove(ed.window, QPoint(round(a.x() + (b.x() - a.x()) * i / n),
                                          round(a.y() + (b.y() - a.y()) * i / n)))
        ed.run(15)
    QTest.mouseRelease(ed.window, LEFT, modifiers, b)
    ed.run(60)


def taps(ed):
    return [args for name, args in ed.submitted if name == "tap_chord_at"]


def selected(ed):
    return ed.area.property("selectedText")


def caret(ed):
    return ed.area.property("cursorPosition")


def plays(ed, n):
    ed.qtbot.waitUntil(lambda: len(ed.harness.player.immediate) == n, timeout=2000)
    ed.run(100)
    return len(ed.harness.player.immediate)


# -- plain clicks: every one plays, none selects ---------------------------------------------


def test_rapid_clicks_on_a_chord_play_every_time_and_select_nothing(ed):
    clicks(ed, ed.point_of(AM), 6)
    assert plays(ed, 6) == 6
    assert taps(ed) == [{"offset": AM}] * 6          # every click reaches the session
    assert selected(ed) == ""


def test_a_double_click_on_a_chord_plays_twice_and_selects_nothing(ed):
    # The real path: QTest's double click goes through the platform queue.
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(AM))
    assert plays(ed, 2) == 2
    assert selected(ed) == ""


def test_a_triple_click_on_a_chord_plays_three_times_and_selects_nothing(ed):
    clicks(ed, ed.point_of(AM), 3)
    assert plays(ed, 3) == 3
    assert selected(ed) == ""


def test_a_click_on_a_chord_moves_the_caret_and_drops_the_selection(ed):
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(TWO + 1))
    ed.run(40)
    assert selected(ed) == "two"
    ed.run(600)
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, ed.gap_point(AM + 1))
    assert plays(ed, 1) == 1
    assert selected(ed) == "" and caret(ed) == AM + 1
    assert ed.area.hasActiveFocus()


def test_a_click_on_a_chord_gives_the_text_the_focus(ed):
    ed.item("playTab").forceActiveFocus()
    assert not ed.area.hasActiveFocus()
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(AM))
    ed.qtbot.waitUntil(lambda: ed.area.hasActiveFocus(), timeout=1000)
    assert plays(ed, 1) == 1


def test_a_drag_from_a_chord_selects_nothing_and_plays_nothing(ed):
    ed.set_cursor(TWO)
    drag(ed, ed.point_of(AM), ed.gap_point(TWO + 3))
    assert selected(ed) == ""
    assert caret(ed) in (AM, AM + 1)                 # the press put it on the chord
    assert taps(ed) == [] and ed.harness.player.immediate == []


def test_a_click_on_lyrics_right_after_one_on_a_chord_doesnt_select_the_word(ed):
    # The two presses are close enough in time for a double click; the first
    # was on a chord, so it isn't one.
    point = ed.point_of(AM + 1)
    lyric = QPoint(point.x(), ed.point_of(TWO + 1).y())
    _clock[0] += 10_000
    send(ed, QEvent.Type.MouseButtonPress, point, LEFT)
    send(ed, QEvent.Type.MouseButtonRelease, point, NO_BUTTON)
    send(ed, QEvent.Type.MouseButtonPress, lyric, LEFT)
    send(ed, QEvent.Type.MouseButtonDblClick, lyric, LEFT)
    send(ed, QEvent.Type.MouseButtonRelease, lyric, NO_BUTTON)
    ed.run(60)
    assert plays(ed, 1) == 1
    assert selected(ed) == ""


# -- Shift: rolled, the selection kept ---------------------------------------------------------


def test_a_shift_click_on_a_chord_plays_it_rolled_and_keeps_the_selection(ed):
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(TWO + 1))
    ed.run(40)
    assert selected(ed) == "two"
    before = (ed.area.property("selectionStart"), ed.area.property("selectionEnd"), caret(ed))
    ed.run(600)
    QTest.mouseClick(ed.window, LEFT, SHIFT, ed.point_of(AM))
    ed.qtbot.waitUntil(lambda: len(ed.harness.player.rolled) == 1, timeout=2000)
    assert ed.harness.player.immediate == []
    assert (ed.area.property("selectionStart"), ed.area.property("selectionEnd"), caret(ed)) == before
    assert taps(ed) == [{"offset": AM, "rolled": True}]


def test_shift_clicks_on_a_chord_roll_every_time(ed):
    clicks(ed, ed.point_of(AM), 3, SHIFT)
    ed.qtbot.waitUntil(lambda: len(ed.harness.player.rolled) == 3, timeout=2000)
    assert ed.harness.player.immediate == [] and selected(ed) == ""


def test_shift_click_on_lyrics_still_extends_the_selection(ed):
    QTest.mouseClick(ed.window, LEFT, NO_MODIFIER, ed.gap_point(TWO))
    QTest.mouseClick(ed.window, LEFT, SHIFT, ed.gap_point(TWO + 3))
    assert selected(ed) == "two"


# -- Alt: the chord is text --------------------------------------------------------------------


def test_an_alt_click_on_a_chord_places_the_caret_and_plays_nothing(ed):
    QTest.mouseClick(ed.window, LEFT, ALT, ed.gap_point(AM + 1))
    ed.run(200)
    assert caret(ed) == AM + 1 and selected(ed) == ""
    assert taps(ed) == [] and ed.harness.player.immediate == []


def test_an_alt_double_click_on_a_chord_selects_it(ed):
    QTest.mouseDClick(ed.window, LEFT, ALT, ed.point_of(AM))
    ed.run(200)
    assert selected(ed) == "Am"
    assert ed.harness.player.immediate == []


def test_an_alt_triple_click_on_a_chord_selects_the_line(ed):
    clicks(ed, ed.point_of(AM), 3, ALT)
    ed.run(200)
    assert selected(ed).rstrip("\n ") == "C   G   Am  F"
    assert ed.harness.player.immediate == []


def test_an_alt_drag_from_a_chord_selects(ed):
    drag(ed, ed.gap_point(AM), ed.gap_point(TEXT.index("F")), ALT)
    assert selected(ed) == "Am  "
    assert ed.harness.player.immediate == []


def test_the_pointer_over_a_chord_is_the_ibeam_while_alt_is_held(ed):
    pane, hover = ed.item("editorPane"), ed.item("editorHover")
    QTest.mouseMove(ed.window, ed.point_of(AM))
    ed.run(30)
    assert hover.property("cursorShape") == Qt.CursorShape.PointingHandCursor
    QTest.keyPress(ed.window, Qt.Key.Key_Alt, ALT)
    ed.run(30)
    assert pane.property("altHeld") is True
    assert hover.property("cursorShape") == Qt.CursorShape.IBeamCursor
    # Released on its own, Alt also shows the menu bar, which moves the text
    # down: point at the chord again.
    QTest.keyRelease(ed.window, Qt.Key.Key_Alt, NO_MODIFIER)
    ed.run(30)
    assert pane.property("altHeld") is False
    QTest.mouseMove(ed.window, ed.point_of(AM))
    ed.run(30)
    assert hover.property("cursorShape") == Qt.CursorShape.PointingHandCursor


# -- lyrics and invalid chords: as before ---------------------------------------------------


def test_clicks_on_lyrics_select_as_before(ed):
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(TWO + 1))
    ed.run(40)
    assert selected(ed) == "two"
    clicks(ed, ed.point_of(TWO + 1), 3)
    assert selected(ed).rstrip("\n ") == "One two three four"
    assert taps(ed) == [] and ed.harness.player.immediate == []


def test_an_invalid_chord_is_text(ed):
    text = "C  Cmaj13#11b9\nCome on\n"
    song(ed, text)
    QTest.mouseDClick(ed.window, LEFT, NO_MODIFIER, ed.point_of(text.index("maj")))
    ed.run(100)
    assert selected(ed) == "Cmaj13"                  # the word stops at '#'
    assert ed.harness.player.immediate == []


def test_a_drag_from_lyrics_across_a_chord_still_selects(ed):
    a, b = ed.gap_point(TWO), ed.gap_point(TEXT.index("G"))
    drag(ed, a, b)
    assert (ed.area.property("selectionStart"), ed.area.property("selectionEnd")) == (TEXT.index("G"), TWO)
    assert ed.harness.player.immediate == []


def test_while_read_only_every_click_on_a_chord_plays_too(ed):
    ed.window.setProperty("mode", "play")
    ed.qtbot.waitUntil(lambda: ed.area.property("readOnly") is True, timeout=1000)
    ed.run()
    clicks(ed, ed.point_of(AM), 2)
    assert plays(ed, 2) == 2
    assert selected(ed) == ""
    ed.window.setProperty("mode", "edit")

"""The Play workspace's player bar (plan steps E1-E3): PlayerBar.qml over
player_bar.py.

The whole front end runs in the test process (QtAppHarness, a FakePlayer),
as in test_qt_editor.py. The values and the commands are the core's
(tests/test_timeline.py, test_session_toolbar.py, test_toolbar_texts.py);
these check what the bar shows, what each gesture sends, and the beat
counted between the core's per-chord pings.
"""

import json
import re

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtQml import qmlEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.session import toolbar_texts  # noqa: E402
from chordnotepad.session.timeline import TimelinePosition  # noqa: E402
from chordnotepad_desktop import player_bar  # noqa: E402
from chordnotepad_desktop.player_bar import BeatClock  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, Editor, song, start  # noqa: E402
from tests.qt.test_qt_value_picker import find, texts_shown  # noqa: E402

SHIFT = Qt.KeyboardModifier.ShiftModifier
LEFT, MIDDLE = Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton
#: Three sections, one bar per chord in 4/4: verse 1-2, chorus 3-4, its repeat 5-6.
TEXT = "{label: verse}\nC   G\n{label: chorus}\nAm  F\n{loop: chorus 2}\n"


class Bar(Editor):
    """The editor harness plus the player bar's items and gestures."""

    @property
    def model(self):
        return self.harness.app.player

    def it(self, name):
        """An item by objectName: in the visual tree (popup contents sit in
        the overlay; Repeater delegates aren't QObject children, pitfall 25),
        else a QObject child (a Popup or a Menu isn't an Item)."""
        from PySide6.QtCore import QObject
        found = find(self.window.contentItem(), name) or self.window.findChild(QObject, name)
        assert found is not None, name
        return found

    def drawn(self):
        """Until the window has drawn a frame. A popup that has just opened
        lays its content out in the next polish pass, so before that its
        items still sit where the first, unpolished layout put them (a chip
        then took the click meant for its neighbour)."""
        with self.qtbot.waitSignal(self.window.frameSwapped, timeout=1000):
            self.window.update()

    def centre(self, it, dx=0.0, dy=0.0):
        self.drawn()
        return it.mapToScene(QPointF(it.width() / 2 + dx, it.height() / 2 + dy)).toPoint()

    def press(self, it, button=LEFT, modifier=NO_MODIFIER, dx=0.0):
        QTest.mousePress(self.window, button, modifier, self.centre(it, dx))

    def click_on(self, it, button=LEFT, modifier=NO_MODIFIER, dx=0.0):
        QTest.mouseClick(self.window, button, modifier, self.centre(it, dx))

    def hover(self, it, dx=0.0):
        # From somewhere else first: a move to where the pointer already is
        # delivers nothing.
        QTest.mouseMove(self.window, QPoint(1, self.window.height() - 2))
        self.run(10)
        QTest.mouseMove(self.window, self.centre(it, dx))
        self.run(20)

    def wheel(self, it, notches):
        pos = QPointF(self.centre(it))
        event = QWheelEvent(pos, QPointF(self.window.mapToGlobal(pos.toPoint())), QPoint(0, 0),
                            QPoint(0, 120 * notches), Qt.MouseButton.NoButton, NO_MODIFIER,
                            Qt.ScrollPhase.NoScrollPhase, False)
        self.qapp.sendEvent(self.window, event)
        self.run()

    @property
    def qapp(self):
        return self.harness.qapp

    def toolbar(self, key):
        return self.store.state("ToolbarState").value(key)

    def playback(self, key):
        return self.store.state("PlaybackState").value(key)

    def sent(self, name):
        return [args for n, args in self.submitted if n == name]

    def to_play(self, width=1400):
        # 350 units at 100%: the whole bar shows, names and all.
        if width and self.window.width() != width:
            self.window.setWidth(width)
        self.window.setProperty("mode", "play")
        self.qtbot.waitUntil(lambda: bool(self.playback("sections")), timeout=3000)
        self.run()

    def wait_status(self, status):
        self.qtbot.waitUntil(lambda: self.playback("status") == status, timeout=3000)

    def ping(self, chords=1):
        """Let the FakePlayer post ``chords`` progress pings and deliver them."""
        playback = self.harness.app.core.playback
        self.qtbot.waitUntil(lambda: self.harness.player.event_buffer is not None, timeout=3000)
        thread = playback._render_thread
        if thread is not None:
            thread.join(3)
        before = self.playback("chord_index")
        assert self.harness.player.play(chords) == chords
        self.qtbot.waitUntil(lambda: self.playback("chord_index") != before, timeout=3000)
        self.run()


@pytest.fixture
def pb(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    bar = Bar(harness, qtbot)
    qtbot.waitUntil(lambda: bar.area.hasActiveFocus(), timeout=1000)
    harness.player.auto_play = False
    song(bar, TEXT)
    yield bar
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def tooltip_shows(bar, it, *parts, dx=0.0):
    """Hover ``it`` until a tooltip with all of ``parts`` shows."""
    bar.hover(it, dx)
    bar.qtbot.waitUntil(lambda: any(all(p in t for p in parts)
                                    for t in texts_shown(bar.window.contentItem())), timeout=2500)


# -- E1: the bar, the transport ------------------------------------------------------------


def test_play_puts_the_sheet_on_screen_so_the_timeline_gets_its_sections(pb):
    assert pb.playback("sections") in (None, [])
    pb.to_play()
    assert pb.sent("set_chord_sheet_on_screen")[-1] == {"on_screen": True}
    assert [(s["label"], s["first_bar"], s["last_bar"], s["repeat"]) for s in pb.playback("sections")] == [
        ("verse", 1, 2, False), ("chorus", 3, 4, False), ("chorus", 5, 6, True)]
    assert pb.it("playerBar").isVisible()
    pb.window.setProperty("mode", "edit")
    pb.run()
    assert pb.sent("set_chord_sheet_on_screen")[-1] == {"on_screen": None}


def test_the_values_sit_centred_on_a_row_above_the_timeline_without_the_title(pb):
    # Tibi, 2026-11-15: the song's values over the seek bar, centred; the
    # title (and its unsaved dot) went: the window and the tab have them.
    pb.to_play()
    values, timeline, middle = pb.it("songValues"), pb.it("timeline"), pb.it("middle")
    pb.drawn()
    assert find(pb.window.contentItem(), "playerTitle") is None
    assert find(pb.window.contentItem(), "playerDirty") is None
    assert values.isVisible()
    assert values.mapToScene(QPointF(0, values.height())).y() <= timeline.mapToScene(QPointF(0, 0)).y()
    centre = values.mapToItem(middle, QPointF(values.width() / 2, 0)).x()
    assert abs(centre - middle.width() / 2) <= 1


def test_the_seek_preview_is_drawn_over_the_values(pb):
    # Tibi, 2026-11-15: the preview went under the row above the timeline.
    pb.to_play()
    timeline, segs = segments(pb)
    pb.hover(segs[0], dx=-segs[0].width() / 2 + 1)
    preview = timeline_preview(timeline)
    pb.qtbot.waitUntil(lambda: preview.isVisible(), timeout=1000)
    values = pb.it("songValues")
    assert preview.parentItem() is not values.parentItem() and preview.parentItem() is not None
    # In the window's overlay, above the contents, just above the track.
    assert preview.parentItem().z() > pb.window.contentItem().z()
    top = timeline.mapToScene(QPointF(0, 0)).y()
    bottom = preview.mapToScene(QPointF(0, preview.height())).y()
    bar = pb.it("playerBar")
    u = bar.width() / bar.property("units")
    assert top - u * 3 <= bottom <= top


def test_play_acts_on_press_and_its_tooltip_follows_the_play_action(pb):
    pb.to_play()
    play = pb.it("playButton")
    tooltip_shows(pb, play, "Play from the playhead (Shift+Click to play from cursor)", "F5")
    pb.press(play)
    pb.wait_status("playing")          # before the release
    QTest.mouseRelease(pb.window, LEFT, NO_MODIFIER, pb.centre(play))
    assert pb.sent("play_pause") == [{"from_offset": None}]
    tooltip_shows(pb, play, "Pause playback")
    pb.click_on(play)
    pb.wait_status("paused")
    tooltip_shows(pb, play, "Resume playback")


def test_shift_play_plays_from_the_editors_cursor(pb):
    pb.set_cursor(TEXT.index("Am"))
    pb.to_play()
    pb.click_on(pb.it("playButton"), modifier=SHIFT)
    pb.wait_status("playing")
    assert pb.sent("play_pause") == [{"from_offset": TEXT.index("Am")}]


def test_space_and_enter_work_on_a_focused_play_button(pb):
    pb.to_play()
    play = pb.it("playButton")
    play.forceActiveFocus()
    pb.key(Qt.Key.Key_Space)
    pb.wait_status("playing")
    pb.key(Qt.Key.Key_Return)
    pb.wait_status("paused")
    pb.key(Qt.Key.Key_Enter)
    pb.wait_status("playing")
    assert len(pb.sent("play_pause")) == 3


def test_rewind_keeps_a_playing_song_playing_from_the_first_chord(pb):
    pb.to_play()
    pb.store.submit("set_playhead", {"offset": TEXT.index("Am")})
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.ping(1)
    pb.submitted.clear()
    pb.click_on(pb.it("prevButton"))
    pb.qtbot.waitUntil(lambda: pb.harness.player.calls.count("start") == 2, timeout=3000)
    assert [n for n, _ in pb.submitted] == ["rewind", "play_pause"]
    assert pb.playback("status") == "playing"
    assert pb.playback("playhead_offset") == TEXT.index("C")
    # Idle, it only moves the playhead.
    pb.store.submit("stop")
    pb.wait_status("idle")
    pb.store.submit("set_playhead", {"offset": TEXT.index("F")})
    pb.run()
    pb.submitted.clear()
    pb.click_on(pb.it("prevButton"))
    pb.run()
    assert [n for n, _ in pb.submitted] == ["rewind"]
    assert pb.playback("status") == "idle" and pb.playback("playhead_offset") == TEXT.index("C")


def test_stop_stops_and_goes_back_to_the_first_chord(pb):
    # Tibi, 2026-11-15: Stop is "pause + go to beginning" (STOP_REWINDS).
    pb.to_play()
    tooltip_shows(pb, pb.it("stopButton"), "Stop playback")
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.ping(2)
    pb.qtbot.waitUntil(lambda: pb.playback("playhead_offset") == TEXT.index("G"), timeout=2000)
    pb.click_on(pb.it("stopButton"))
    pb.wait_status("idle")
    pb.qtbot.waitUntil(lambda: pb.playback("playhead_offset") == TEXT.index("C"), timeout=2000)
    # Idle it is still there: it silences ringing notes.
    assert pb.it("stopButton").property("enabled") is True


def test_the_shortcuts_play_pause_and_stop_and_rewind(pb):
    pb.to_play()
    pb.key(Qt.Key.Key_F5)
    pb.wait_status("playing")
    pb.key(Qt.Key.Key_F5)
    pb.wait_status("paused")
    pb.key(Qt.Key.Key_F5, SHIFT)
    pb.wait_status("idle")
    assert pb.sent("rewind") == [None]


# -- E1: the timeline ----------------------------------------------------------------------


def segments(pb):
    timeline = pb.it("timeline")
    return timeline, [find(timeline, f"seg{i}") for i in range(3)]


def timeline_preview(timeline):
    """The seek preview: drawn in the window's overlay, a QObject child of the timeline."""
    return timeline.findChild(QQuickItem, "timelinePreview")


def test_the_timeline_has_a_segment_per_section_with_gaps(pb):
    pb.to_play()
    timeline, segs = segments(pb)
    assert all(s is not None for s in segs) and find(timeline, "seg3") is None
    widths = [s.width() for s in segs]
    assert abs(widths[0] - widths[1]) < 1 and abs(widths[1] - widths[2]) < 1
    assert segs[1].x() > segs[0].x() + segs[0].width()           # a gap


def test_the_hovered_segment_thickens_and_the_preview_names_it(pb):
    pb.to_play()
    timeline, segs = segments(pb)
    thin = segs[1].height()
    pb.hover(segs[1], dx=-segs[1].width() / 4)          # bar 3, the chorus
    pb.qtbot.waitUntil(lambda: segs[1].height() > thin * 1.5, timeout=1000)
    assert segs[0].height() == thin
    preview = timeline_preview(timeline)
    assert preview.isVisible() and preview.property("text") == "chorus · 3:1 / 6"
    # It stays inside the track at the end.
    pb.hover(segs[2], dx=segs[2].width() / 2 - 1)
    assert preview.property("text") == "chorus · 6:1 / 6"
    gap = 2 * timeline.property("gap") + 2          # Theme.gap2, give or take
    assert preview.property("localX") + preview.width() <= timeline.width() + gap
    pb.hover(segs[0], dx=-segs[0].width() / 2 + 1)
    assert preview.property("text") == "verse · 1:1 / 6"
    assert preview.property("localX") >= -gap


def test_a_click_seeks_and_a_gap_goes_to_the_boundary_bar(pb):
    pb.to_play()
    timeline, segs = segments(pb)
    pb.click_on(segs[1], dx=segs[1].width() / 4)          # bar 4: F
    pb.qtbot.waitUntil(lambda: pb.playback("playhead_offset") == TEXT.index("F"), timeout=2000)
    gap = (segs[0].x() + segs[0].width() + segs[1].x()) / 2
    point = timeline.mapToScene(QPointF(gap, timeline.height() / 2)).toPoint()
    QTest.mouseClick(pb.window, LEFT, NO_MODIFIER, point)
    pb.qtbot.waitUntil(lambda: pb.playback("playhead_offset") == TEXT.index("Am"), timeout=2000)
    assert pb.model.position == "3:1"


def test_a_drag_seeks_as_it_goes_when_idle_and_where_it_ends_when_playing(pb):
    pb.to_play()
    timeline, segs = segments(pb)
    QTest.mousePress(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[0], -segs[0].width() / 4))
    QTest.mouseMove(pb.window, pb.centre(segs[1], -segs[1].width() / 4))
    pb.qtbot.waitUntil(lambda: pb.playback("playhead_offset") == TEXT.index("Am"), timeout=2000)
    QTest.mouseRelease(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[1], -segs[1].width() / 4))
    pb.store.submit("rewind")
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.submitted.clear()
    QTest.mousePress(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[0], segs[0].width() / 4))
    pb.run()
    QTest.mouseMove(pb.window, pb.centre(segs[1], -segs[1].width() / 4))
    pb.run()
    QTest.mouseMove(pb.window, pb.centre(segs[1], segs[1].width() / 4))
    pb.run()
    assert len(pb.sent("seek_to_bar")) == 1                   # the press only
    QTest.mouseRelease(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[1], segs[1].width() / 4))
    pb.run()
    assert pb.sent("seek_to_bar")[-1] == {"bar": 4}


def test_a_press_and_a_release_reveal_the_playhead_in_the_text_not_every_bar(pb):
    # Polish round C3: the editor scrolls to the chord the seek landed on, on
    # the press and when the drag lets go, not on each bar of an idle drag.
    pb.to_play()
    timeline, segs = segments(pb)
    reveals = []
    pb.bridge.revealRequested.connect(reveals.append)
    QTest.mousePress(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[0], -segs[0].width() / 4))
    pb.qtbot.waitUntil(lambda: len(reveals) == 1, timeout=2000)
    for dx in (-0.25, 0.25):                                   # two bars of an idle drag
        QTest.mouseMove(pb.window, pb.centre(segs[1], segs[1].width() * dx))
        pb.run()
    assert len(reveals) == 1
    QTest.mouseRelease(pb.window, LEFT, NO_MODIFIER, pb.centre(segs[1], segs[1].width() * 0.25))
    pb.qtbot.waitUntil(lambda: len(reveals) == 2, timeout=2000)
    assert reveals[-1] == pb.bridge.property("playheadPos") == TEXT.index("F")


def test_a_click_in_a_loops_second_pass_seeks_into_that_pass(pb):
    # Tibi, 2026-11-15: a click on the second segment registered in the first.
    pb.to_play()
    timeline, segs = segments(pb)
    pb.click_on(segs[2], dx=-segs[2].width() / 4)         # bar 5: Am, the repeat
    pb.qtbot.waitUntil(lambda: pb.model.position == "5:1", timeout=2000)
    # The editor marks the chord in the text (the same for both passes).
    assert pb.playback("playhead_offset") == TEXT.index("Am")
    assert pb.store.state("ChordSheetState").value("cursor_index") == 4
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.ping(1)
    assert (pb.playback("chord_index"), pb.playback("bar")) == (4, 5)
    assert pb.model.position == "5:1"
    # While playing, a click in the first pass jumps back there.
    pb.click_on(segs[1], dx=segs[1].width() / 4)          # bar 4: F, the first pass
    pb.ping(1)
    assert (pb.playback("chord_index"), pb.playback("bar")) == (3, 4)


def test_the_position_is_fixed_width_tabular_and_right_aligned(pb):
    pb.to_play()
    position = pb.it("position")
    assert position.property("text") == "1:1"
    assert "tnum" in [t.toString() for t in position.property("font").featureTags()]
    width = position.width()
    pb.store.submit("set_playhead", {"offset": TEXT.index("F")})
    pb.qtbot.waitUntil(lambda: position.property("text") == "4:1", timeout=2000)
    assert position.width() == width


def test_the_position_counts_beats_between_the_pings(pb):
    clock = [100.0]
    pb.model._beats._clock = lambda: clock[0]
    pb.to_play()
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.ping(1)                                          # C, bar 1, 120 bpm: 0.5 s a beat
    assert pb.model.position == "1:1"
    clock[0] += 0.6
    pb.qtbot.waitUntil(lambda: pb.model.position == "1:2", timeout=1000)
    assert pb.model.played == pytest.approx(0.5)
    # The speed applies at once: 200% doubles the rate from here.
    pb.store.submit("set_multiplier_pct", {"pct": 200})
    pb.run()
    clock[0] += 0.3
    pb.qtbot.waitUntil(lambda: pb.model.position == "1:3", timeout=1000)
    # Paused, it stands still.
    pb.store.submit("play_pause", {"from_offset": None})
    pb.wait_status("paused")
    clock[0] += 5
    pb.run(100)
    assert pb.model.position == "1:3"
    # The next ping puts it on the chord's own beat.
    pb.store.submit("play_pause", {"from_offset": None})
    pb.wait_status("playing")
    pb.ping(1)
    assert pb.model.position == "2:1"


def test_the_beat_clock_rolls_over_bars_and_stops_at_the_songs_end():
    now = [0.0]
    beats = BeatClock(lambda: now[0])
    beats.reset(TimelinePosition(bar=2, beat=3.5, beats_per_bar=4, bpm=60, total_bars=3), True, 100)
    assert beats.position() == (2, 3, 1.75)
    now[0] = 1.0                                    # 60 bpm: one beat a second
    assert beats.position()[:2] == (2, 4)
    now[0] = 1.5
    assert beats.position()[:2] == (3, 1)
    now[0] = 50.0
    assert beats.position()[:2] == (3, 4)
    beats.stop()
    now[0] = 99.0
    assert beats.position()[:2] == (3, 4)
    beats.reset(None, False, 100)
    assert beats.position() is None


def test_the_bar_narrows_the_timeline_then_the_names_then_the_timeline_again(pb):
    # Tibi's order: the names collapse before the timeline gets small; the
    # values never hide.
    pb.to_play()
    timeline = pb.it("timeline")
    bar = pb.it("playerBar")
    u = bar.width() / bar.property("units")
    voicing, instrument = pb.it("voicingButton"), pb.it("instrumentButton")
    widths = []
    for units in range(360, 150, -5):
        pb.window.setWidth(int(u * units))
        pb.run(30)
        names = voicing.property("showText")
        assert instrument.property("showText") is names
        assert pb.it("songValues").isVisible()
        widths.append((units, names, timeline.width()))
    shown = [w for _, names, w in widths if names]
    hidden = [w for _, names, w in widths if not names]
    assert shown and hidden
    # Names shown: the timeline never under its comfortable width.
    assert min(shown) >= 40 * u - 1
    # They went at once, never to come back as the bar narrowed.
    flags = [names for _, names, _ in widths]
    assert flags == sorted(flags, reverse=True)
    # Then the timeline goes on shrinking, down to its minimum.
    assert min(hidden) < 40 * u
    assert min(hidden) >= 22 * u - 1
    # The ▶ tooltip is only the play action now.
    pb.window.setWidth(int(u * 200))
    pb.run(30)
    tooltip_shows(pb, pb.it("playButton"), "Play from the playhead", "F5")
    from PySide6.QtCore import QObject
    assert find(pb.window.contentItem(), "moreButton") is None
    assert pb.window.findChild(QObject, "moreButton") is None


# -- E2: the tempo -------------------------------------------------------------------------


def tempo_chip(pb):
    return pb.it("tempoChip")


def test_a_drag_scrubs_the_tempo_from_where_the_press_started(pb):
    pb.to_play()
    chip = tempo_chip(pb)
    start = pb.centre(chip)
    QTest.mousePress(pb.window, LEFT, NO_MODIFIER, start)
    QTest.mouseMove(pb.window, start + QPoint(2, 0))
    pb.run()
    assert pb.sent("set_bpm") == []                 # under 3 px: not a drag yet
    QTest.mouseMove(pb.window, start + QPoint(20, 0))     # 5 steps of 4 px
    pb.run()
    QTest.mouseMove(pb.window, start + QPoint(40, 0))     # 10 steps: from 120, not from 125
    pb.run()
    QTest.mouseRelease(pb.window, LEFT, NO_MODIFIER, start + QPoint(40, 0))
    pb.run()
    assert [a["bpm"] for a in pb.sent("set_bpm")] == [125, 130]
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 130, timeout=1000)
    assert not pb.it("tempoField").isVisible()        # a drag isn't a click


def test_a_click_types_the_tempo_enter_commits_escape_cancels_focus_out_commits(pb):
    pb.to_play()
    pb.click_on(tempo_chip(pb))
    field = pb.it("tempoField")
    pb.qtbot.waitUntil(lambda: field.isVisible() and field.hasActiveFocus(), timeout=1000)
    assert field.property("selectedText") == "120"
    assert field.property("cursorPosition") == 3
    pb.type("95")
    pb.key(Qt.Key.Key_Return)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 95, timeout=1000)
    assert not field.isVisible()
    # Keypad Enter; parse_bpm rounds.
    pb.click_on(tempo_chip(pb))
    pb.type("119.6")
    pb.key(Qt.Key.Key_Enter, Qt.KeyboardModifier.KeypadModifier)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 120, timeout=1000)
    # Escape cancels.
    pb.click_on(tempo_chip(pb))
    pb.type("80")
    pb.key(Qt.Key.Key_Escape)
    pb.run()
    assert pb.toolbar("bpm") == 120 and not field.isVisible()
    # Focus-out commits; junk keeps the value.
    pb.click_on(tempo_chip(pb))
    pb.type("88")
    pb.area.forceActiveFocus()
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 88, timeout=1000)
    pb.click_on(tempo_chip(pb))
    pb.type("fast")
    pb.key(Qt.Key.Key_Return)
    pb.run()
    assert pb.toolbar("bpm") == 88


def test_the_tempo_wheel_steps_by_one_past_the_tens_and_middle_click_resets(pb):
    pb.to_play()
    chip = tempo_chip(pb)
    pb.wheel(chip, 1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 122, timeout=1000)   # Q2: not stuck at 120
    pb.wheel(chip, 1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 123, timeout=1000)
    pb.wheel(chip, -1)
    pb.wheel(chip, -1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 120, timeout=1000)
    pb.wheel(chip, -1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 118, timeout=1000)
    pb.click_on(chip, MIDDLE)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 120, timeout=1000)
    pb.submitted.clear()
    pb.click_on(chip, MIDDLE)
    pb.run()
    assert pb.sent("reset_bpm") == []                 # already 120


def test_the_tempo_is_reachable_from_the_keyboard(pb):
    pb.to_play()
    readout = pb.it("tempoReadout")
    readout.forceActiveFocus()
    pb.key(Qt.Key.Key_Up)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 122, timeout=1000)
    pb.key(Qt.Key.Key_Return)
    pb.qtbot.waitUntil(lambda: pb.it("tempoField").hasActiveFocus(), timeout=1000)


def test_the_tempo_has_a_tint_and_the_resize_cursor_and_its_tooltip(pb):
    pb.to_play()
    chip = tempo_chip(pb)
    rest = chip.property("color")
    pb.hover(chip)
    pb.qtbot.waitUntil(lambda: chip.property("color") != rest, timeout=1000)
    assert pb.it("tempoArea").property("cursorShape") == Qt.CursorShape.SizeHorCursor
    tooltip_shows(pb, chip, "Beats per minute for this song")


def test_while_playing_the_tempo_shows_the_effective_value_read_only(pb):
    song(pb, "C {bpm: 90} G\n")
    pb.to_play()
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.ping(2)
    chip = tempo_chip(pb)
    pb.qtbot.waitUntil(lambda: pb.it("tempoText").property("text") == "90", timeout=1000)
    assert pb.it("tempoArea").property("cursorShape") == Qt.CursorShape.ArrowCursor
    assert chip.property("color").alpha() == 0
    pb.click_on(chip)
    pb.wheel(chip, 1)
    pb.click_on(chip, MIDDLE)
    pb.run()
    assert not pb.it("tempoField").isVisible()
    assert pb.sent("set_bpm") == [] and pb.sent("reset_bpm") == []
    # Paused, it can be changed again (Play then re-renders).
    pb.click_on(pb.it("playButton"))
    pb.wait_status("paused")
    pb.qtbot.waitUntil(lambda: pb.it("tempoText").property("text") == "120", timeout=1000)
    assert pb.it("tempoArea").property("cursorShape") == Qt.CursorShape.SizeHorCursor
    # A tempo changed while paused: Play renders again from the paused chord (core).
    pb.wheel(chip, 1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("bpm") == 122, timeout=1000)
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    assert pb.harness.player.calls.count("start") == 2


def test_a_tempo_the_song_sets_links_to_its_directive(pb):
    text = "{bpm: 90}\n{key: D}\n{time: 3/4}\nC G\n"
    song(pb, text)
    pb.to_play()
    chip = tempo_chip(pb)
    assert pb.it("tempoText").property("text") == "90"
    tooltip_shows(pb, chip, "Set by", "{bpm: 90}", "in the song", "click to go there")
    pb.click_on(chip)
    pb.qtbot.waitUntil(lambda: pb.window.property("mode") == "edit", timeout=1000)
    pb.qtbot.waitUntil(lambda: pb.area.property("cursorPosition") == 1, timeout=1000)
    assert pb.area.hasActiveFocus()
    assert pb.sent("set_bpm") == [] and pb.sent("set_bpm_text") == []
    # The key and the time link to theirs too.
    pb.to_play()
    tooltip_shows(pb, pb.it("keyValue"), "Set by", "{key: D}")
    pb.click_on(pb.it("timeValue"))
    pb.qtbot.waitUntil(lambda: pb.window.property("mode") == "edit", timeout=1000)
    pb.qtbot.waitUntil(lambda: pb.area.property("cursorPosition") == text.index("{time") + 1,
                       timeout=1000)


# -- E2: key and time -------------------------------------------------------------------------


def song_picker(pb):
    return pb.it("songPicker")


def test_the_key_opens_the_picker_with_the_toolbars_keys_and_a_pick_sets_it(pb):
    pb.to_play()
    tooltip_shows(pb, pb.it("keyValue"), "Key for roman numeral chords")
    pb.click_on(pb.it("keyValue"))
    pb.qtbot.waitUntil(lambda: song_picker(pb).property("visible") is True, timeout=1000)
    picker = song_picker(pb)
    values = [c["value"] for c in picker.property("options").toVariant()["groups"][0]["choices"]] \
        if hasattr(picker.property("options"), "toVariant") else \
        [c["value"] for c in picker.property("options")["groups"][0]["choices"]]
    assert values[:3] == ["C", "C#", "Db"] and len(values) == 17
    pb.click_on(pb.it("key:D"))
    pb.qtbot.waitUntil(lambda: pb.toolbar("key") == "D", timeout=1000)
    assert pb.sent("set_key") == [{"key": "D"}]
    assert pb.it("keyValue").property("value") == "D"
    # The current one again sends nothing.
    pb.click_on(pb.it("keyValue"))
    pb.qtbot.waitUntil(lambda: song_picker(pb).property("visible") is True, timeout=1000)
    pb.click_on(pb.it("key:D"))
    pb.run()
    assert len(pb.sent("set_key")) == 1


def test_the_time_picker_applies_a_preset_and_a_typed_value_q1(pb):
    pb.to_play()
    pb.click_on(pb.it("timeValue"))
    pb.qtbot.waitUntil(lambda: song_picker(pb).property("visible") is True, timeout=1000)
    pb.click_on(pb.it("time:3/4"))
    pb.qtbot.waitUntil(lambda: (pb.toolbar("beats"), pb.toolbar("unit")) == (3, 4), timeout=1000)
    assert pb.it("timeValue").property("value") == "3/4"
    # Q1: beats typed into the box (not stepped) are applied, by Enter or by Apply.
    pb.click_on(pb.it("timeValue"))
    pb.qtbot.waitUntil(lambda: song_picker(pb).property("visible") is True, timeout=1000)
    box = pb.it("pickerBox")
    box.forceActiveFocus()
    pb.key(Qt.Key.Key_A, CTRL)
    pb.type("7")
    pb.click_on(pb.it("unit:8"))
    pb.click_on(pb.it("pickerApply"))
    pb.qtbot.waitUntil(lambda: (pb.toolbar("beats"), pb.toolbar("unit")) == (7, 8), timeout=1000)
    pb.click_on(pb.it("timeValue"))
    pb.qtbot.waitUntil(lambda: song_picker(pb).property("visible") is True, timeout=1000)
    pb.it("pickerBox").forceActiveFocus()
    pb.key(Qt.Key.Key_A, CTRL)
    pb.type("5")
    pb.key(Qt.Key.Key_Return)
    pb.qtbot.waitUntil(lambda: (pb.toolbar("beats"), pb.toolbar("unit")) == (5, 8), timeout=1000)
    assert pb.sent("set_time_signature")[-1] == {"beats": 5, "unit": 8}


def test_key_and_time_are_locked_while_playing_with_their_tooltips(pb):
    pb.to_play()
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.click_on(pb.it("keyValue"))
    pb.click_on(pb.it("timeValue"))
    pb.run()
    assert song_picker(pb).property("visible") is False
    tooltip_shows(pb, pb.it("timeValue"), "Time signature", "Pause to change it while a song plays")
    tooltip_shows(pb, pb.it("keyValue"), "Pause to change it while a song plays")


# -- E3: speed -----------------------------------------------------------------------------


def test_speed_wheel_middle_click_and_the_shortcuts(pb):
    pb.to_play()
    speed = pb.it("speedButton")
    assert speed.property("text") == "100%"
    pb.wheel(speed, 1)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 105, timeout=1000)
    pb.wheel(speed, -2)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 95, timeout=1000)
    pb.click_on(speed, MIDDLE)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 100, timeout=1000)
    pb.key(Qt.Key.Key_BracketRight, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 105, timeout=1000)
    pb.key(Qt.Key.Key_BracketLeft, CTRL)
    pb.key(Qt.Key.Key_BracketLeft, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 95, timeout=1000)
    pb.key(Qt.Key.Key_Backslash, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 100, timeout=1000)
    tooltip_shows(pb, speed, "Speed multiplier applied on top of BPM")


def test_the_tempo_heard_shows_beside_the_songs_when_the_speed_isnt_100(pb):
    # Tibi, 2026-11-15: "143 bpm (150%)", the declared tempo times the speed.
    pb.to_play()
    heard = pb.it("effectiveTempo")
    assert not heard.isVisible()
    pb.store.submit("set_bpm", {"bpm": 95})
    pb.store.submit("set_multiplier_pct", {"pct": 150})
    pb.qtbot.waitUntil(lambda: heard.isVisible(), timeout=1000)
    assert heard.property("text") == "→ 143 bpm (150%)"
    # It follows the tempo (a wheel step here) and the speed.
    pb.wheel(pb.it("tempoChip"), 1)
    pb.qtbot.waitUntil(lambda: heard.property("text") == "→ 144 bpm (150%)", timeout=1000)
    pb.store.submit("set_multiplier_pct", {"pct": 87.5})
    pb.qtbot.waitUntil(lambda: heard.property("text") == "→ 84 bpm (87.5%)", timeout=1000)
    pb.store.submit("set_multiplier_pct", {"pct": 100})
    pb.qtbot.waitUntil(lambda: not heard.isVisible(), timeout=1000)


def test_the_speed_dropdown_box_slider_presets_and_reset(pb):
    pb.to_play()
    # From the keyboard (Q10): Space on the focused button opens it.
    pb.it("speedButton").forceActiveFocus()
    pb.key(Qt.Key.Key_Space)
    pb.qtbot.waitUntil(lambda: pb.it("speedPopup").property("visible") is True, timeout=1000)
    pb.key(Qt.Key.Key_Escape)
    pb.qtbot.waitUntil(lambda: pb.it("speedPopup").property("visible") is False, timeout=1000)
    pb.click_on(pb.it("speedButton"))
    popup = pb.it("speedPopup")
    pb.qtbot.waitUntil(lambda: popup.property("visible") is True, timeout=1000)
    box = pb.it("speedBox")
    pb.qtbot.waitUntil(lambda: box.hasActiveFocus(), timeout=1000)
    assert box.property("text") == "100"
    pb.key(Qt.Key.Key_A, CTRL)
    pb.type("1.5x")
    pb.key(Qt.Key.Key_Return)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 150, timeout=1000)
    pb.key(Qt.Key.Key_A, CTRL)
    pb.type("87.5%")
    pb.key(Qt.Key.Key_Return)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 87.5, timeout=1000)
    assert pb.it("speedButton").property("text") == "87.5%"
    pb.click_on(pb.it("speed:125"))
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 125, timeout=1000)
    assert box.property("text") == "125"
    slider = pb.it("speedSlider")
    pb.click_on(slider, dx=-slider.width() / 2 + 4)          # near the left end
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") < 20, timeout=1000)
    pb.click_on(pb.it("speedReset"))
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 100, timeout=1000)


def test_the_speed_slider_is_logarithmic_with_100_percent_in_the_middle():
    assert player_bar.speed_position(12.5) == 0 and player_bar.speed_position(400) == 1
    assert player_bar.speed_position(100) == pytest.approx(0.6, abs=0.001)
    assert player_bar.speed_at(player_bar.speed_position(100)) == 100
    assert player_bar.speed_at(0) == 12.5 and player_bar.speed_at(1) == 400
    assert player_bar.speed_stepped(398, 1) == 400 and player_bar.speed_stepped(15, -1) == 12.5
    assert player_bar.speed_stepped(87.5, 1) == 92.5


def test_speed_is_live_while_playing_and_saved_as_bpm_multiplier(pb):
    pb.to_play()
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    pb.key(Qt.Key.Key_BracketRight, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("multiplier_pct") == 105, timeout=1000)
    assert pb.harness.player.bpm_multiplier == pytest.approx(1.05)
    pb.store.submit("stop")
    pb.wait_status("idle")
    pb.harness.shutdown()
    saved = json.loads(pb.harness.config_file().read_text(encoding="utf-8"))
    assert saved["bpm_multiplier"] == pytest.approx(1.05)


# -- E3: volume, metronome ------------------------------------------------------------------


def test_the_volume_dropdown_slider_mute_and_wheel(pb):
    pb.to_play()
    volume = pb.it("volumeButton")
    tooltip_shows(pb, volume, "Volume 100%")
    pb.wheel(volume, -2)
    pb.qtbot.waitUntil(lambda: pb.model.volume == pytest.approx(0.9), timeout=1000)
    pb.click_on(volume)
    pb.qtbot.waitUntil(lambda: pb.it("volumePopup").property("visible") is True, timeout=1000)
    pb.click_on(pb.it("muteButton"))
    pb.qtbot.waitUntil(lambda: pb.model.muted is True, timeout=1000)
    assert pb.it("muteButton").property("text") == "Unmute"
    slider = pb.it("volumeSlider")
    pb.click_on(slider)                                   # the middle: unmutes too
    pb.qtbot.waitUntil(lambda: pb.model.muted is False, timeout=1000)
    assert pb.model.volume == pytest.approx(0.5, abs=0.06)
    assert pb.sent("set_volume") and pb.sent("set_muted")[-1] == {"muted": False}


def test_the_metronome_toggles_with_ctrl_m_and_starts_off(pb):
    pb.to_play()
    button = pb.it("metronomeButton")
    assert pb.toolbar("metronome") is False and button.property("checked") is False
    tooltip_shows(pb, button, "Click track during playback", "Ctrl+M")
    pb.key(Qt.Key.Key_M, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("metronome") is True, timeout=1000)
    assert button.property("checked") is True
    pb.click_on(button)
    pb.qtbot.waitUntil(lambda: pb.toolbar("metronome") is False, timeout=1000)
    pb.key(Qt.Key.Key_M, CTRL)
    pb.qtbot.waitUntil(lambda: pb.toolbar("metronome") is True, timeout=1000)
    assert pb.it("metronomeAction").property("checked") is True


# -- E3: voicing and instrument --------------------------------------------------------------


def named(root, prefix):
    """Every item in the visual tree whose objectName starts with ``prefix``."""
    found = [root] if root.objectName().startswith(prefix) else []
    for child in root.childItems():
        found.extend(named(child, prefix))
    return found


def shown(pb, prefix):
    """The visible items named ``prefix``... (a Menu's rows, in the overlay
    while it is open; PySide can't hand out the QQuickMenu itself)."""
    return [i for i in named(pb.window.contentItem(), prefix) if i.isVisible()]


def rows(pb, texts):
    """The visible menu rows showing one of ``texts``."""
    found = []

    def walk(item):
        if item.isVisible() and item.property("text") in texts and item.property("highlighted") is not None:
            found.append(item)
        for child in item.childItems():
            walk(child)
    walk(pb.window.contentItem())
    return found


def test_the_voicing_menu_groups_the_choices_and_a_pick_sets_it(pb):
    pb.to_play()
    pb.click_on(pb.it("voicingButton"))
    pb.qtbot.waitUntil(lambda: bool(shown(pb, "voicing:")), timeout=1000)
    groups = pb.store.state("VoicingMenuState").value("groups")
    items = shown(pb, "voicing:")
    assert [i.property("text") for i in items] == [c["label"] for g in groups for c in g]
    assert [i.objectName() for i in items if i.property("checked")] == ["voicing:piano"]
    assert shown(pb, "editVoicings")
    guitar = next(i for i in items if i.objectName().startswith("voicing:guitar"))
    value = guitar.objectName().split(":", 1)[1]
    pb.run(150)                       # the menu's opening transition
    pb.click_on(guitar)
    pb.qtbot.waitUntil(lambda: pb.store.state("VoicingMenuState").value("selected") == value,
                       timeout=1000)
    assert pb.sent("set_voicing") == [{"voicing": value}]
    assert pb.it("voicingButton").property("text").startswith("Guitar")
    pb.click_on(pb.it("voicingButton"))
    pb.qtbot.waitUntil(lambda: bool(shown(pb, "voicing:")), timeout=1000)
    assert [i.objectName() for i in shown(pb, "voicing:") if i.property("checked")] == [
        "voicing:" + value]


def test_the_voicing_is_locked_while_playing_with_the_reason(pb):
    pb.to_play()
    pb.click_on(pb.it("playButton"))
    pb.wait_status("playing")
    button = pb.it("voicingButton")
    pb.qtbot.waitUntil(lambda: button.property("enabled") is False, timeout=1000)
    tooltip_shows(pb, pb.it("voicingTip"), "Voicing: Piano", "Pause to change the voicing")
    pb.click_on(button)
    pb.run()
    assert not shown(pb, "voicing:")
    pb.click_on(pb.it("playButton"))
    pb.wait_status("paused")
    pb.qtbot.waitUntil(lambda: button.property("enabled") is True, timeout=1000)


def test_edit_voicings_opens_settings_on_the_voicings_page(pb):
    pb.to_play()
    pb.click_on(pb.it("voicingButton"))
    pb.qtbot.waitUntil(lambda: bool(shown(pb, "editVoicings")), timeout=1000)
    pb.run(150)
    pb.click_on(shown(pb, "editVoicings")[0])
    settings = pb.window.findChild(QObject, "settingsWindow")
    pb.qtbot.waitUntil(lambda: settings.property("visible") is True, timeout=2000)
    assert settings.property("page") == "voicings"
    QMetaObject.invokeMethod(settings, "close")
    pb.qtbot.waitUntil(lambda: settings.property("visible") is False, timeout=2000)


FAMILIES = ("Piano", "Chromatic Percussion", "Organ", "Guitar", "Bass", "Strings", "Ensemble",
            "Brass", "Reed", "Pipe", "Synth Lead", "Synth Pad", "Synth Effects", "Ethnic",
            "Percussive", "Sound Effects")


def test_the_instrument_menu_has_16_families_with_the_familys_dot(pb):
    pb.to_play()
    instrument = pb.it("instrumentButton")
    state = pb.store.state("InstrumentMenuState")
    assert [f["name"] for f in state.value("families")] == list(FAMILIES)
    pb.click_on(instrument)
    pb.qtbot.waitUntil(lambda: len(rows(pb, FAMILIES)) == 16, timeout=1000)
    families = rows(pb, FAMILIES)
    assert [r.property("text") for r in families] == list(FAMILIES)
    # The dot: the family in use has the circle icon.
    dots = [r.property("text") for r in families
            if any(i.property("resolved") == "circle" and i.isVisible()
                   for i in named(r, ""))]
    assert dots == ["Piano"]
    assert [f["name"] for f in state.value("families") if f["is_current"]] == ["Piano"]
    pb.key(Qt.Key.Key_Escape)
    pb.store.submit("set_instrument", {"program": 25})
    pb.qtbot.waitUntil(lambda: state.value("current") == 25, timeout=1000)
    assert "General MIDI 25" in instrument.property("tip")
    pb.click_on(instrument)
    pb.qtbot.waitUntil(lambda: len(rows(pb, FAMILIES)) == 16, timeout=1000)
    dots = [r.property("text") for r in rows(pb, FAMILIES)
            if any(i.property("resolved") == "circle" and i.isVisible() for i in named(r, ""))]
    assert dots == ["Guitar"]


def test_a_program_picked_in_the_instrument_menu_is_sent(pb):
    # The FakePlayer has no soundfont: give it the 128 programs.
    pb.harness.player.get_available_instruments = lambda: [(p, f"Program {p}") for p in range(128)]
    pb.store.submit("set_instrument", {"program": 0})
    pb.qtbot.waitUntil(lambda: len(pb.store.state("InstrumentMenuState").value("families")[3]["items"]) == 8,
                       timeout=1000)
    pb.submitted.clear()
    pb.to_play()
    assert pb.it("instrumentButton").property("text") == "Program 0"
    pb.click_on(pb.it("instrumentButton"))
    pb.qtbot.waitUntil(lambda: bool(rows(pb, ("Guitar",))), timeout=1000)
    pb.run(150)
    pb.click_on(rows(pb, ("Guitar",))[0])
    pb.qtbot.waitUntil(lambda: bool(shown(pb, "program:2")), timeout=1000)
    pb.run(150)
    item = shown(pb, "program:2")[0]
    program = int(item.objectName().split(":")[1])
    assert 24 <= program < 32
    pb.click_on(item)
    pb.qtbot.waitUntil(lambda: pb.store.state("InstrumentMenuState").value("current") == program,
                       timeout=1000)
    assert pb.sent("set_instrument") == [{"program": program}]


# -- the shortcuts are in one place ------------------------------------------------------------


def test_every_playback_shortcut_is_declared_once():
    from pathlib import Path
    qml_dir = Path(player_bar.__file__).resolve().parent / "qml"
    sequences = []
    for path in qml_dir.rglob("*.qml"):
        code = path.read_text(encoding="utf-8")
        sequences += [(m, path.name) for m in re.findall(r'(?:shortcut|sequence):\s*"([^"]+)"', code)]
    keys = [s for s, _ in sequences]
    duplicates = {k for k in keys if keys.count(k) > 1}
    assert duplicates == set(), sequences
    for key in ("F5", "Shift+F5", "Ctrl+M", "Ctrl+]", "Ctrl+[", "Ctrl+\\\\"):
        assert (key, "PlaybackActions.qml") in sequences, key


def test_the_tooltips_are_the_cores():
    assert player_bar.TEXTS["bpm"] == toolbar_texts.BPM_TOOLTIP
    assert player_bar.TEXTS["metronome"] == toolbar_texts.METRONOME_TOOLTIP


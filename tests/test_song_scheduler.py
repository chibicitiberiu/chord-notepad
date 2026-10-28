"""SongScheduler: compiled song -> sequencer ticks, pings, pause/resume/speed.

The fake sequencer models FluidSynth's queue closely enough to check what
would actually sound: events wait in a queue until the clock passes their
tick, ``remove(source)`` drops queued events of one client, and at the same
tick note-offs are played before note-ons.
"""

import pytest

from audio.song_scheduler import (
    CLICK_TICKS, LOOKAHEAD_TICKS, MAX_WAIT_TICKS, START_LEAD_TICKS, ClickSound, SongScheduler,
)
from models.playback_event_internal import MidiEvent, MidiEventType

SONG = 5
CLICK = ClickSound()


class FakeSequencer:
    def __init__(self):
        self.tick = 0
        self.queue = []   # (tick, order, kind, channel, key, velocity, source)
        self.played = []  # (tick, kind, channel, key)
        self._order = 0

    def now(self):
        return self.tick

    def note_on(self, tick, channel, key, velocity, source):
        self._push(tick, "on", channel, key, velocity, source)

    def note_off(self, tick, channel, key, source):
        self._push(tick, "off", channel, key, 0, source)

    def _push(self, tick, kind, channel, key, velocity, source):
        self._order += 1
        self.queue.append((max(tick, 0), self._order, kind, channel, key, velocity, source))

    def remove(self, source):
        self.queue = [e for e in self.queue if e[6] != source]

    def advance(self, to):
        """Render up to tick ``to``: play everything due, offs first per tick."""
        self.tick = to
        due = sorted((e for e in self.queue if e[0] <= to),
                     key=lambda e: (e[0], 0 if e[2] == "off" else 1, e[1]))
        self.queue = [e for e in self.queue if e[0] > to]
        # Past-due events play at the current tick
        self.played.extend((max(e[0], 0), e[2], e[3], e[4]) for e in due)

    def notes(self, channel=0):
        return [(t, kind, key) for t, kind, ch, key in self.played if ch == channel]


def chord(start, end, notes, index, ticks=()):
    """The events compile_events makes for one chord."""
    meta = {'has_callback': True, 'chord_index': index}
    events = [MidiEvent(t, MidiEventType.METRONOME_TICK, metadata={'is_downbeat': i == 0})
              for i, t in enumerate(ticks)]
    events.append(MidiEvent(start, MidiEventType.NOTE_ON, list(notes), 100, dict(meta)))
    events.append(MidiEvent(end, MidiEventType.NOTE_OFF, list(notes), 0, {}))
    return events


def two_chords():
    return (chord(0.0, 0.5, [60, 64], 0) + chord(0.5, 1.0, [60, 67], 1)
            + [MidiEvent(1.0, MidiEventType.END_OF_SONG)])


def make(events, multiplier=1.0, now=0):
    seq = FakeSequencer()
    seq.tick = now
    sched = SongScheduler(events, seq, source=SONG, channel=0, click=CLICK, multiplier=multiplier)
    sched.start(now)
    return seq, sched


def run(seq, sched, until, step=10):
    """Advance the clock, pumping like the clock thread; return pings by tick."""
    pings = []
    tick = seq.tick
    while tick < until:
        tick = min(until, tick + step)
        seq.advance(tick)
        result = sched.pump(tick)
        pings += [(tick, e.metadata['chord_index']) for e in result.pings]
        seq.advance(tick)  # anything the pump sent for "now" plays now
    return pings


def test_notes_play_at_absolute_ticks_from_the_start_lead():
    seq, sched = make(two_chords())
    run(seq, sched, 2000)
    lead = START_LEAD_TICKS
    assert seq.notes() == [
        (lead, "on", 60), (lead, "on", 64),
        (lead + 500, "off", 60), (lead + 500, "off", 64),   # release before the next attack
        (lead + 500, "on", 60), (lead + 500, "on", 67),
        (lead + 1000, "off", 60), (lead + 1000, "off", 67),
    ]


def test_pings_come_when_their_tick_is_reached():
    seq, sched = make(two_chords())
    pings = run(seq, sched, 2000, step=10)
    assert pings == [(20, 0), (520, 1)]


def test_finishes_at_the_last_event_and_not_before():
    seq, sched = make(two_chords())
    seq.advance(1019)
    sched.pump(1019)
    assert not sched.pump(1019).finished
    seq.advance(1020)
    assert sched.pump(1020).finished


def test_wait_targets_the_next_ping():
    seq, sched = make(two_chords())
    result = sched.pump(0)
    assert result.wait_s == pytest.approx(0.020)
    seq.advance(25)
    result = sched.pump(25)
    assert result.wait_s == pytest.approx(MAX_WAIT_TICKS / 1000)  # next ping is 495 ms away, capped


def test_only_the_lookahead_window_is_sent():
    events = []
    for i in range(20):
        events += chord(i * 1.0, i * 1.0 + 1.0, [60], i)
    seq, sched = make(events)
    sched.pump(0)
    sent = sorted(e[0] for e in seq.queue)
    assert max(sent) <= LOOKAHEAD_TICKS
    assert min(sent) == START_LEAD_TICKS


def test_metronome_clicks_are_short_notes_on_the_drum_channel():
    events = chord(0.0, 1.0, [60], 0, ticks=[0.0, 0.5])
    seq, sched = make(events)
    run(seq, sched, 2000)
    assert seq.notes(channel=9) == [
        (20, "on", CLICK.downbeat_note), (20 + CLICK_TICKS, "off", CLICK.downbeat_note),
        (520, "on", CLICK.offbeat_note), (520 + CLICK_TICKS, "off", CLICK.offbeat_note),
    ]


def test_rest_pings_without_sound():
    events = [MidiEvent(0.0, MidiEventType.REST, metadata={'has_callback': True, 'chord_index': 0})]
    events += chord(1.0, 2.0, [62], 1)
    seq, sched = make(events)
    pings = run(seq, sched, 3000)
    assert pings == [(20, 0), (1020, 1)]
    assert seq.notes() == [(1020, "on", 62), (2020, "off", 62)]


def test_events_without_callback_do_not_ping():
    events = chord(0.0, 0.5, [60], 0)
    events[0].metadata['has_callback'] = False
    seq, sched = make(events)
    assert run(seq, sched, 1000) == []


def test_pause_drops_queued_notes_and_resume_continues_from_there():
    seq, sched = make(two_chords())
    run(seq, sched, 270)
    pings = sched.pause(270)
    assert pings == []  # the first ping was already handed out
    assert seq.queue == []
    run(seq, sched, 5000)  # paused: nothing is sent
    assert seq.notes() == [(20, "on", 60), (20, "on", 64)]

    sched.resume(5000)
    run(seq, sched, 7000)
    # 0.25 s of song were left before the second chord
    resume = 5000 + START_LEAD_TICKS
    assert seq.notes()[2:] == [
        (resume + 250, "off", 60), (resume + 250, "off", 64),
        (resume + 250, "on", 60), (resume + 250, "on", 67),
        (resume + 750, "off", 60), (resume + 750, "off", 67),
    ]


def test_pause_returns_pings_that_were_due():
    seq, sched = make(two_chords())
    sched.pump(0)
    seq.advance(30)
    pings = sched.pause(30)
    assert [p.metadata['chord_index'] for p in pings] == [0]


def test_pause_before_the_first_note_resumes_at_the_start():
    seq, sched = make(two_chords())
    sched.pump(0)
    sched.pause(5)
    sched.resume(100)
    run(seq, sched, 200)
    assert seq.notes()[:2] == [(120, "on", 60), (120, "on", 64)]


def test_speed_change_reschedules_from_now():
    seq, sched = make(two_chords())
    run(seq, sched, 270)
    sched.set_multiplier(2.0, 270)
    run(seq, sched, 2000)
    # 0.25 s of song to the second chord, at double speed
    assert seq.notes()[2:] == [
        (395, "off", 60), (395, "off", 64), (395, "on", 60), (395, "on", 67),
        (645, "off", 60), (645, "off", 67),
    ]


def test_speed_change_keeps_pings_in_step():
    seq, sched = make(two_chords())
    pings = run(seq, sched, 270)
    sched.set_multiplier(0.5, 270)
    pings += run(seq, sched, 3000)
    assert pings == [(20, 0), (770, 1)]


def test_speed_change_while_paused_applies_on_resume():
    seq, sched = make(two_chords())
    run(seq, sched, 270)
    sched.pause(270)
    sched.set_multiplier(0.5, 300)
    sched.resume(1000)
    run(seq, sched, 3000)
    assert seq.notes()[2] == (1020 + 500, "off", 60)


def test_speed_change_releases_a_ringing_click():
    events = chord(0.0, 1.0, [60], 0, ticks=[0.0, 0.5])
    seq, sched = make(events)
    run(seq, sched, 30)
    sched.set_multiplier(1.5, 30)
    run(seq, sched, 2000)
    drum = seq.notes(channel=9)
    assert drum[0] == (20, "on", CLICK.downbeat_note)
    assert (30, "off", CLICK.downbeat_note) in drum  # its queued note-off was removed and re-sent


def test_event_at_the_cut_is_sent_again_rather_than_lost():
    seq, sched = make(two_chords())
    sched.pump(0)
    seq.tick = 520  # clock reached the second chord, but it hasn't played yet
    sched.set_multiplier(1.0, 520)
    run(seq, sched, 2000)
    assert (520, "on", 67) in seq.notes()
    assert seq.notes()[-1] == (1020, "off", 67)


def test_stop_drops_everything_queued():
    seq, sched = make(two_chords())
    sched.pump(0)
    sched.stop(10)
    seq.advance(5000)
    assert seq.played == []


def test_zero_length_chord_does_not_hang():
    events = chord(0.0, 0.0002, [60], 0)  # rounds to the same tick
    seq, sched = make(events)
    run(seq, sched, 500)
    assert seq.notes() == [(20, "on", 60), (21, "off", 60)]


def test_empty_song_finishes_right_away():
    seq, sched = make([MidiEvent(0.0, MidiEventType.END_OF_SONG)])
    seq.advance(START_LEAD_TICKS)
    assert sched.pump(START_LEAD_TICKS).finished


def test_song_starting_mid_way_plays_its_first_event_at_once():
    # Play from the cursor: the renderer's timestamps don't start at zero
    events = chord(12.0, 12.5, [60], 7)
    seq, sched = make(events)
    run(seq, sched, 1000)
    assert seq.notes() == [(20, "on", 60), (520, "off", 60)]


def test_other_sources_are_left_alone():
    seq, sched = make(two_chords())
    seq.note_off(3000, 0, 72, source=99)  # a click-to-hear release
    sched.pump(0)
    sched.stop(0)
    assert [e[6] for e in seq.queue] == [99]

"""NotePlayer on the sequencer: clock thread, pings, transport, click-to-hear.

No FluidSynth: the synth is a recorder and the sequencer is the queue model
from test_song_scheduler, whose clock the test moves by hand. The clock
thread is real, so waits are bounded polls.
"""

import threading
import time
from unittest.mock import patch

import pytest

from audio.event_buffer import EventBuffer
from models.playback_event_internal import MidiEvent, MidiEventType

from tests.test_song_scheduler import FakeSequencer, chord

TIMEOUT = 3.0


class FakeSynth:
    def __init__(self):
        self.calls = []
        self.audio_driver = None

    def noteon(self, channel, key, velocity):
        self.calls.append(("on", channel, key))

    def noteoff(self, channel, key):
        self.calls.append(("off", channel, key))

    def all_notes_off(self, channel):
        self.calls.append(("all_off", channel))

    def program_select(self, *args):
        return 0

    def cc(self, channel, control, value):
        self.calls.append(("cc", channel, control, value))

    def delete(self):
        self.calls.append(("delete",))


class LockedSequencer(FakeSequencer):
    """The fake queue, safe to drive from the test while the clock thread runs."""

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.removed = []

    def now(self):
        with self.lock:
            return self.tick

    def _push(self, *args):
        with self.lock:
            super()._push(*args)

    def remove(self, source):
        with self.lock:
            self.removed.append(source)
            super().remove(source)

    def advance(self, to):
        with self.lock:
            super().advance(to)

    def delete(self):
        pass


class App:
    """queue_ui_callback that runs callbacks at once."""

    def queue_ui_callback(self, cb):
        cb()


def wait_for(predicate, timeout=TIMEOUT):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@pytest.fixture
def player():
    from audio import player as mod

    with patch.object(mod.NotePlayer, "_initialize_fluidsynth", lambda self, *a: None), \
            patch.object(mod.os.path, "exists", lambda p: True):
        p = mod.NotePlayer(soundfont_path="fake.sf2")
    p.fs = FakeSynth()
    p.sfid = 1
    p._sequencer = LockedSequencer()
    p._song_source = 2
    p._click_source = 3
    yield p
    p.stop_playback()


def load(player, events, on_event=None):
    buffer = EventBuffer(capacity=len(events) + 1)
    for event in events:
        buffer.push_event(event)
    player.set_event_buffer(buffer)
    app = App()
    received = []
    player.set_event_callback(on_event or (lambda args: received.append(args)), app)
    finished = threading.Event()
    player.set_playback_finished_callback(finished.set)
    return received, finished


def two_chords():
    return (chord(0.0, 0.5, [60, 64], 0) + chord(0.5, 1.0, [60, 67], 1)
            + [MidiEvent(1.0, MidiEventType.END_OF_SONG)])


def step_clock(player, to):
    player._sequencer.advance(to)
    with player._wake:
        player._wake.notify_all()


def test_song_plays_pings_and_finishes(player):
    received, finished = load(player, two_chords())
    player.start_playback()
    assert player.is_playing
    seq = player._sequencer
    assert wait_for(lambda: len(seq.queue) == 8)  # whole song inside the look-ahead

    step_clock(player, 20)
    assert wait_for(lambda: len(received) == 1)
    assert received[0].chord_index == 0
    assert not finished.is_set()

    step_clock(player, 1020)
    assert finished.wait(TIMEOUT)
    assert [a.chord_index for a in received] == [0, 1]
    assert not player.is_playing
    assert ("all_off", 0) in player.fs.calls
    assert seq.notes()[-1] == (1020, "off", 67)


def test_nothing_is_played_from_python_threads(player):
    # Song notes go through the sequencer only; the synth sees no direct noteon
    load(player, two_chords())
    player.start_playback()
    step_clock(player, 1020)
    assert wait_for(lambda: not player.is_playing)
    assert not [c for c in player.fs.calls if c[0] == "on"]


def test_stop_removes_the_song_and_skips_the_finished_callback(player):
    received, finished = load(player, two_chords())
    player.start_playback()
    seq = player._sequencer
    assert wait_for(lambda: seq.queue)
    player.stop_playback()
    assert not player.is_playing
    assert seq.queue == []
    assert player.playback_thread is None or not player.playback_thread.is_alive()
    step_clock(player, 5000)
    time.sleep(0.05)
    assert not finished.is_set()
    assert seq.played == []


def test_pause_and_resume(player):
    received, finished = load(player, two_chords())
    player.start_playback()
    seq = player._sequencer
    step_clock(player, 270)
    assert wait_for(lambda: len(received) == 1)

    player.pause_playback()
    assert player.is_paused and player.is_playing
    assert seq.queue == []
    assert ("all_off", 0) in player.fs.calls

    step_clock(player, 3000)
    time.sleep(0.05)
    assert len(received) == 1 and not finished.is_set()

    player.resume_playback()
    assert not player.is_paused
    step_clock(player, 3020 + 250)
    assert wait_for(lambda: len(received) == 2)
    step_clock(player, 3020 + 750)
    assert finished.wait(TIMEOUT)


def test_speed_change_during_playback_is_rescheduled(player):
    received, _ = load(player, two_chords())
    player.start_playback()
    step_clock(player, 270)
    assert wait_for(lambda: len(received) == 1)
    player.set_bpm_multiplier(2.0)
    assert player._bpm_multiplier == 2.0
    seq = player._sequencer
    assert wait_for(lambda: any(e[0] == 395 and e[2] == "on" for e in seq.queue))


def test_multiplier_set_before_play_is_used(player):
    player.set_bpm_multiplier(0.5)
    load(player, two_chords())
    player.start_playback()
    seq = player._sequencer
    # at half speed the second chord starts 1 s of audio later
    assert wait_for(lambda: any(e[0] == 20 + 1000 and e[2] == "on" for e in seq.queue))


def test_start_without_a_synth_does_nothing(player):
    player._sequencer = None
    load(player, two_chords())
    player.start_playback()
    assert not player.is_playing


def test_click_to_hear_releases_through_the_sequencer(player):
    seq = player._sequencer
    seq.tick = 100
    player.play_notes_immediate([60, 64])
    assert player.fs.calls == [("on", 0, 60), ("on", 0, 64)]
    assert sorted((e[0], e[2], e[4], e[6]) for e in seq.queue) == [
        (2100, "off", 60, 3), (2100, "off", 64, 3),
    ]

    seq.tick = 500
    player.play_notes_immediate([62])
    # the first click's release is dropped and its notes stopped now
    assert [(e[0], e[4]) for e in seq.queue] == [(2500, 62)]
    assert player.fs.calls[2:] == [("off", 0, 60), ("off", 0, 64), ("on", 0, 62)]


def test_click_to_hear_does_not_start_threads(player):
    before = threading.active_count()
    for _ in range(5):
        player.play_notes_immediate([60])
    assert threading.active_count() == before


def test_stop_all_notes_drops_pending_click_releases_only(player):
    seq = player._sequencer
    player.play_notes_immediate([60])
    load(player, two_chords())
    player.start_playback()
    assert wait_for(lambda: len(seq.queue) == 9)
    player.stop_all_notes()
    assert {e[6] for e in seq.queue} == {2}


def test_cleanup_stops_playback_and_frees_in_order(player):
    load(player, two_chords())
    player.start_playback()
    freed = []
    player._sequencer.delete = lambda: freed.append("sequencer")
    player.fs.audio_driver = 1234
    with patch("audio.player.fluidsynth.delete_fluid_audio_driver", lambda h: freed.append("driver")):
        fs = player.fs
        player.cleanup()
    assert freed == ["driver", "sequencer"]
    assert fs.calls[-1] == ("delete",)
    assert not player.is_playing and player.fs is None


def test_metronome_channel_is_set_up_before_play(player):
    load(player, two_chords())
    player.start_playback()
    assert ("cc", 9, 7, 0) in player.fs.calls

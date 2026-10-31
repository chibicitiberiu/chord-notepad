"""The identifier's piano shows what sounds, and Play plays the selection.

Playing a candidate (or Play) publishes the MIDI notes it sent to the synth
as ``sounding``, which the piano highlights for a few seconds. A candidate
plays on the piano's keys (C4 to B5), anchored on the selected bass when the
chord starts there, and notes off either end get a marker. A long press (or
Shift+click on the desktop) plays the notes rolled: one at a time from the
lowest, on the synth's sequencer, so nothing waits on the session thread and
the next click stops what's left.
"""

from unittest.mock import MagicMock

import pytest

from audio.player import NotePlayer
from services.appdata_service import AppDataService
from session.bootstrap import build_core_services, create_session
from session.host import HostDispatch
from session.state import IdentifierState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.chord_identifier_viewmodel import (
    ROLL_GAP_SECONDS, SOUNDING_SECONDS, ChordIdentifierViewModel, midi_name, outside_piano,
)
from services.song_parser_service import SongParserService


class FakeAudio:
    """The audio service calls the identifier makes."""

    def __init__(self):
        self.chords = []
        self.rolled = []
        self.click_stops = 0

    def play_chord_from_midi(self, midi_notes, duration=2.0):
        self.chords.append(list(midi_notes))

    def play_notes_rolled(self, midi_notes, gap):
        self.rolled.append((list(midi_notes), gap))

    def stop_click_notes(self):
        self.click_stops += 1


@pytest.fixture
def audio():
    return FakeAudio()


@pytest.fixture
def vm(audio):
    model = ChordIdentifierViewModel(SongParserService(), audio)
    model.seen = []
    model.observe("sounding", model.seen.append)
    return model


# --- What sounds is what's published ------------------------------------------

def test_a_played_candidate_publishes_the_notes_it_sent(vm, audio):
    vm.set_notes_from_string("E4 G#4 B4 C5")
    vm.play_chord("Eaddb6")
    assert audio.chords == [[64, 68, 71, 72]]
    assert vm.sounding == (64, 68, 71, 72)
    assert vm.seen == [(64, 68, 71, 72)]


def test_each_play_gets_a_new_token(vm):
    vm.set_notes_from_string("C4 E4 G4")
    vm.play_chord("C")
    first = vm.sounding_token
    vm.play_chord("C")
    assert vm.sounding_token == first + 1
    assert SOUNDING_SECONDS == 3.0


def test_a_chord_that_doesnt_resolve_publishes_nothing(vm):
    vm.set_notes_from_string("C4 E4 G4")
    with pytest.raises(Exception):
        vm.play_chord("Xyz")
    assert vm.sounding == ()


# --- On the piano's keys --------------------------------------------------------

def test_a_chord_on_the_selected_bass_starts_on_that_key(vm, audio):
    vm.set_notes_from_string("E4 G#4 B4 C5")
    vm.play_chord("Caugmaj7/E")
    assert audio.chords[-1][0] == 64
    vm.set_notes_from_string("E5 G#5 B5")
    vm.play_chord("E")
    assert audio.chords[-1] == [76, 80, 83]


def test_a_chord_on_another_root_plays_in_octave_four(vm, audio):
    vm.set_notes_from_string("E4 G#4 B4 C5")
    vm.play_chord("Caugmaj7")
    assert audio.chords[-1] == [60, 64, 68, 71]


def test_a_low_bass_plays_low_and_is_marked(vm, audio):
    vm.set_notes_from_string("E3 G#3 B3 C4")
    vm.play_chord("Eaddb6")
    assert audio.chords[-1] == [52, 56, 59, 60]
    assert outside_piano(vm.sounding) == ("◂ E3 G#3 B3", None)


def test_notes_over_the_top_are_marked(vm, audio):
    vm.set_notes_from_string("G5 B5 D6")
    vm.play_chord("G")
    assert audio.chords[-1] == [79, 83, 86]
    assert outside_piano(vm.sounding) == (None, "D6 ▸")


def test_outside_piano_markers():
    assert outside_piano([60, 64, 67]) == (None, None)
    assert outside_piano([48, 59, 60, 83, 84]) == ("◂ C3 B3", "C6 ▸")
    assert outside_piano([]) == (None, None)
    assert midi_name(48) == "C3" and midi_name(61) == "C#4"


# --- Cleared when the notes change ----------------------------------------------

def test_new_notes_clear_the_highlight_at_once(vm):
    vm.set_notes_from_string("C4 E4 G4")
    vm.play_chord("C")
    vm.toggle_note("B", 4)
    assert vm.sounding == () and vm.seen[-1] == ()
    vm.play_chord("Cmaj7")
    vm.set_notes_from_string("C4 E4")
    assert vm.sounding == ()


def test_clear_removes_the_highlight_and_stops_a_roll(vm, audio):
    vm.set_notes_from_string("C4 E4 G4")
    vm.play_chord("C", rolled=True)
    vm.clear_selection()
    assert vm.sounding == () and vm.seen[-1] == ()
    assert audio.click_stops == 1
    # Nothing was sounding: nothing to stop.
    vm.clear_selection()
    assert audio.click_stops == 1


# --- Play and rolled playback ---------------------------------------------------

def test_play_sounds_exactly_the_selected_keys(vm, audio):
    vm.set_notes([("G", 4), ("C", 4), ("E", 5)])
    vm.play_selected_notes()
    assert audio.chords == [[60, 67, 76]]
    assert vm.sounding == (60, 67, 76)


def test_play_with_nothing_selected_does_nothing(vm, audio):
    vm.play_selected_notes()
    vm.play_selected_notes(rolled=True)
    assert audio.chords == [] and audio.rolled == [] and vm.sounding == ()


def test_rolled_plays_lowest_first_with_the_roll_gap(vm, audio):
    vm.set_notes([("G", 4), ("C", 4), ("E", 4)])
    vm.play_selected_notes(rolled=True)
    assert audio.rolled == [([60, 64, 67], ROLL_GAP_SECONDS)]
    assert vm.sounding == (60, 64, 67)
    vm.play_chord("C", rolled=True)
    assert audio.rolled[-1] == ([60, 64, 67], ROLL_GAP_SECONDS)
    assert 0.05 <= ROLL_GAP_SECONDS <= 0.08


# --- The roll on the synth ------------------------------------------------------

class FakeSequencer:
    """Records timed events per source, like ``SynthSequencer``."""

    def __init__(self, now=5000):
        self.t = now
        self.events = []

    def now(self):
        return self.t

    def note_on(self, tick, channel, key, velocity, source):
        self.events.append(("on", tick, key, source))

    def note_off(self, tick, channel, key, source):
        self.events.append(("off", tick, key, source))

    def remove(self, source):
        self.events = [e for e in self.events if e[3] != source]


@pytest.fixture
def synth():
    player = NotePlayer.__new__(NotePlayer)
    player.fs = MagicMock()
    player.channel = 0
    player._sequencer = FakeSequencer()
    player._click_source = 7
    player._immediate_notes = []
    return player


def test_a_roll_is_scheduled_lowest_first_a_gap_apart(synth):
    synth.play_notes_rolled([60, 64, 67], 0.06, duration=2.0)
    synth.fs.noteon.assert_called_once_with(0, 60, 100)  # the first sounds at once
    ons = [(tick, key) for kind, tick, key, _ in synth._sequencer.events if kind == "on"]
    assert ons == [(5060, 64), (5120, 67)]
    offs = {(tick, key) for kind, tick, key, _ in synth._sequencer.events if kind == "off"}
    assert offs == {(7120, 60), (7120, 64), (7120, 67)}  # all held past the last
    assert all(source == 7 for *_, source in synth._sequencer.events)


def test_the_next_click_stops_a_roll_still_going(synth):
    synth.play_notes_rolled([60, 64, 67], 0.06)
    synth.play_notes_immediate([62])
    # The roll's pending notes are gone, and its notes were released.
    assert not any(kind == "on" for kind, *_ in synth._sequencer.events)
    released = {c.args[1] for c in synth.fs.noteoff.call_args_list}
    assert {60, 64, 67} <= released


def test_stopping_click_notes_drops_the_rest_of_a_roll(synth):
    synth.play_notes_rolled([60, 64, 67], 0.06)
    synth.stop_immediate_notes()
    assert synth._sequencer.events == []
    assert {c.args[1] for c in synth.fs.noteoff.call_args_list} == {60, 64, 67}


def test_one_note_or_no_sequencer_plays_at_once(synth):
    synth.play_notes_rolled([60], 0.06)
    assert not any(kind == "on" for kind, *_ in synth._sequencer.events)
    synth._sequencer = None
    synth.play_notes_rolled([60, 64], 0.06)
    assert [c.args[1] for c in synth.fs.noteon.call_args_list][-2:] == [60, 64]


# --- Through the session (Android) ----------------------------------------------

def make(tmp_path):
    host = ManualHost()
    player = FakePlayer()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host), player=player)
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform="android")
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, player, recorder


def test_the_session_publishes_what_the_candidate_played(tmp_path):
    session, player, recorder = make(tmp_path)
    session.identifier_set_notes_text("E3 G#3 B3 C4")
    session.play_identified_chord("Eaddb6")
    state = recorder.last(IdentifierState)
    assert state.sounding == tuple(player.immediate[-1]) == (52, 56, 59, 60)
    assert state.sounding_token == 1
    assert state.sounding_seconds == SOUNDING_SECONDS
    assert (state.sounding_below, state.sounding_above) == ("◂ E3 G#3 B3", None)

    session.play_identified_chord("Eaddb6", rolled=True)
    state = recorder.last(IdentifierState)
    assert player.rolled[-1] == ([52, 56, 59, 60], ROLL_GAP_SECONDS)
    assert state.sounding_token == 2

    session.identifier_toggle_note("E", 4)
    state = recorder.last(IdentifierState)
    assert state.sounding == () and state.sounding_below is None


def test_the_session_play_button(tmp_path):
    session, player, recorder = make(tmp_path)
    published = len(recorder.of_type(IdentifierState))
    session.identifier_play_selection(rolled=False)
    assert player.immediate == [] and len(recorder.of_type(IdentifierState)) == published

    session.identifier_set_notes_text("C4 E4 G4")
    session.identifier_play_selection(rolled=True)
    assert player.rolled == [([60, 64, 67], ROLL_GAP_SECONDS)]
    assert recorder.last(IdentifierState).sounding == (60, 64, 67)

    session.identifier_clear()
    assert recorder.last(IdentifierState).sounding == ()
    assert player.click_stops == 1

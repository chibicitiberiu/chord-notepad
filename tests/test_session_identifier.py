"""The chord identifier through the session (the Android screen's path).

Notes are toggled or typed, the IdentifierState carries the selection and
the candidates, notes and chords sound through the click-to-hear policy, and
the shared note helpers give the desktop dialog's answers.
"""

import pytest

from services.appdata_service import AppDataService
from session.bootstrap import build_core_services, create_session
from session.events import AudioUnavailable, UserError
from session.host import HostDispatch
from session.state import IdentifierNote, IdentifierState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.chord_identifier_viewmodel import (
    SELECT_NOTES_PROMPT, bass_note, note_to_midi, parse_notes,
)
from session import formatting


def make(tmp_path, audio_works=True, platform="desktop"):
    host = ManualHost()
    player = FakePlayer()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=player if audio_works else None)
    if not audio_works:
        def fail(soundfont_path=None, audio_options=None):
            services.playback._init_error = "no audio driver"
            return False
        services.playback.initialize_player = fail
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=platform)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, player, recorder


def test_the_empty_identifier_is_published_from_the_start(tmp_path):
    _, _, recorder = make(tmp_path)
    state = recorder.last(IdentifierState)
    assert state == IdentifierState((), "", None, (), SELECT_NOTES_PROMPT)
    assert formatting.IDENTIFIER_PROMPT == SELECT_NOTES_PROMPT


def test_toggling_keys_identifies_and_sounds_new_keys(tmp_path):
    session, player, recorder = make(tmp_path)
    for note, octave in (("C", 4), ("E", 4), ("G", 4)):
        session.identifier_toggle_note(note, octave)
    state = recorder.last(IdentifierState)
    assert [n.midi for n in state.notes] == [60, 64, 67]
    assert state.notes[0] == IdentifierNote("C", 4, 60)
    assert state.notes_text == "C E G"
    assert state.candidates[0] == "C"
    assert state.message is None and state.typed_text_error is None
    assert player.immediate == [[60], [64], [67]]

    # Deselecting is silent.
    session.identifier_toggle_note("E", 4)
    assert player.immediate == [[60], [64], [67]]
    state = recorder.last(IdentifierState)
    assert state.notes_text == "C G" and "C" not in state.candidates


def test_a_flat_key_is_spelled_with_a_sharp_and_bad_keys_are_refused(tmp_path):
    session, _, recorder = make(tmp_path)
    session.identifier_toggle_note("Bb", 3)
    assert recorder.last(IdentifierState).notes == (IdentifierNote("A#", 3, 58),)
    with pytest.raises(ValueError):
        session.identifier_toggle_note("H", 4)
    with pytest.raises(ValueError):
        session.play_note("C", 11)


def test_typed_notes_keep_their_octaves_and_report_what_isnt_a_note(tmp_path):
    session, player, recorder = make(tmp_path)
    session.identifier_set_notes_text("E3, g4 c5")
    state = recorder.last(IdentifierState)
    assert [(n.name, n.octave) for n in state.notes] == [("E", 3), ("G", 4), ("C", 5)]
    assert state.notes_text == "C E G"
    assert "C/E" in state.candidates
    assert state.typed_text_error is None
    assert player.immediate == []                       # typing makes no sound

    session.identifier_set_notes_text("C E H x7")
    state = recorder.last(IdentifierState)
    assert state.typed_text_error == "Not notes: H, x7"
    assert [n.name for n in state.notes] == ["C", "E"]
    # A key toggle clears the typed-text error.
    session.identifier_toggle_note("G", 4)
    assert recorder.last(IdentifierState).typed_text_error is None


def test_no_chord_and_clear_say_so_in_the_message(tmp_path):
    session, _, recorder = make(tmp_path)
    session.identifier_set_notes_text("C C# D")
    state = recorder.last(IdentifierState)
    assert state.candidates == ()
    assert "No standard chord found." in state.message
    session.identifier_clear()
    assert recorder.last(IdentifierState) == IdentifierState((), "", None, (), SELECT_NOTES_PROMPT)


def test_play_without_selecting_and_play_a_candidate(tmp_path):
    session, player, recorder = make(tmp_path)
    session.play_note("A", 4)
    assert player.immediate == [[69]]
    assert recorder.last(IdentifierState).notes == ()
    session.play_identified_chord("Am")
    assert len(player.immediate) == 2 and len(player.immediate[1]) >= 3
    session.play_identified_chord("Xyz")
    error = recorder.last(UserError)
    assert error.title == "Identify Chord" and "Xyz" in error.message


def test_audio_failures_follow_the_click_policy(tmp_path):
    session, _, recorder = make(tmp_path, audio_works=False, platform="android")
    session.identifier_toggle_note("C", 4)
    session.play_note("C", 4)
    session.play_identified_chord("C")
    failures = recorder.of_type(AudioUnavailable)
    assert len(failures) == 1 and failures[0].from_click
    assert failures[0].message.endswith("Tapped chords won't play until this is fixed.")
    # The selection still went through.
    assert recorder.last(IdentifierState).notes[0].name == "C"


def test_the_shared_note_helpers():
    assert note_to_midi("C", 4) == 60 and note_to_midi("B", -1) == 11
    assert bass_note([("G", 4), ("E", 3), ("C", 4)]) == "E"
    assert bass_note([]) is None
    assert parse_notes("C, Db4 e5 Cm Q") == ([("C", 4), ("C#", 4), ("E", 5), ("C", 4)],
                                             ["Cm", "Q"])


def test_the_desktop_viewmodel_answers_as_before(tmp_path):
    """The desktop dialog's list keeps its explanation lines."""
    session, _, _ = make(tmp_path)
    model = session.chord_identifier_model()
    model.set_notes_from_string("C C# D")
    assert model.identified_chords[0] == "Notes: C, C#, D"
    assert model.identified_chords[2:] == ["No standard chord found.",
                                           "Try adding or removing notes."]
    assert model.candidates == [] and model.info_lines == model.identified_chords
    model.set_notes_from_string("C E G")
    assert model.candidates == model.identified_chords and model.info_lines == []
    assert model.parse_note_string("c, Eb g7") == [("C", 4), ("D#", 4), ("G", 7)]
    assert model.normalize_note_name("gb") == "F#"

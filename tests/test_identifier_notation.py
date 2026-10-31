"""The chord identifier names chords in the open song's notation.

A European song (the toolbar's Do switch) gets European candidates, notes,
markers and messages; a tapped candidate plays as shown and an inserted one
goes in as shown. Typed notes may use either notation. Identification and the
likelihood order stay American underneath.
"""

import pytest

from services.appdata_service import AppDataService
from services.song_parser_service import SongParserService
from session.bootstrap import build_core_services, create_session
from session.events import TextEdited
from session.host import HostDispatch
from session.state import IdentifierState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.chord_identifier_viewmodel import (
    ChordIdentifierViewModel, midi_name, outside_piano, parse_notes, spell,
    spelling_preference,
)


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


def european(tmp_path):
    session, player, recorder = make(tmp_path)
    session.set_notation("european")
    return session, player, recorder


def test_a_european_song_gets_european_names(tmp_path):
    session, _, recorder = european(tmp_path)
    assert recorder.last(IdentifierState).notation == "european"
    for note, octave in (("A", 4), ("C", 5), ("E", 5), ("G", 5)):
        session.identifier_toggle_note(note, octave)
    state = recorder.last(IdentifierState)
    assert state.notation == "european"
    assert state.notes_text == "Do Mi Sol La"
    assert state.candidates[0] == "Lam7"
    assert "Do6/La" in state.candidates
    # The notes keep the American sharps the piano sends.
    assert [n.name for n in state.notes] == ["A", "C", "E", "G"]


def test_added_tones_and_slash_basses_convert(tmp_path):
    session, _, recorder = european(tmp_path)
    session.identifier_set_notes_text("Mi Sol# Si Do")
    candidates = recorder.last(IdentifierState).candidates
    assert candidates[0] == "Miaddb6"
    assert "Doaugmaj7/Mi" in candidates
    session.identifier_set_notes_text("E3 C4 G4 B4")
    assert "Domaj7/Mi" in recorder.last(IdentifierState).candidates


def test_the_ranking_is_the_american_one(tmp_path):
    session, _, recorder = make(tmp_path)
    session.identifier_set_notes_text("E G# B C")
    american = recorder.last(IdentifierState).candidates
    session.set_notation("european")
    assert recorder.last(IdentifierState).candidates == tuple(spell(c, "european") for c in american)


def test_a_european_candidate_plays_and_inserts_as_shown(tmp_path):
    session, player, recorder = european(tmp_path)
    session.identifier_set_notes_text("La Do Mi")
    session.play_identified_chord("Lam")
    assert player.immediate[-1] == [69, 72, 76]
    assert recorder.last(IdentifierState).sounding == (69, 72, 76)
    session.identifier_set_notes_text("Si Re Fa")
    session.play_identified_chord("Sidim")
    assert player.immediate[-1] == [71, 74, 77]
    # Played as shown, also with a flat and a slash bass.
    session.identifier_set_notes_text("Re3 Sib3 Fa4")
    shown = recorder.last(IdentifierState).candidates
    assert "Sib/Re" in shown
    session.play_identified_chord("Sib/Re")
    assert player.immediate[-1][0] % 12 == 2 and set(m % 12 for m in player.immediate[-1]) == {10, 2, 5}

    session.insert_chord(0, "Lam")
    assert recorder.last(TextEdited).replacement == "Lam "


def test_switching_the_notation_respells_at_once(tmp_path):
    session, _, recorder = make(tmp_path)
    session.identifier_set_notes_text("E3 G#3 B3 C4")
    session.play_identified_chord("Eaddb6")
    state = recorder.last(IdentifierState)
    assert state.candidates[0] == "Eaddb6" and state.sounding_below == "◂ E3 G#3 B3"

    session.set_notation("european")
    state = recorder.last(IdentifierState)
    assert state.notation == "european"
    assert state.candidates[0] == "Miaddb6"
    assert state.notes_text == "Do Mi Sol# Si"
    assert state.sounding_below == "◂ Mi3 Sol#3 Si3"
    assert state.sounding == (52, 56, 59, 60)        # still lit

    session.set_notation("american")
    assert recorder.last(IdentifierState).candidates[0] == "Eaddb6"


def test_the_empty_identifier_follows_the_notation_too(tmp_path):
    session, _, recorder = make(tmp_path)
    session.set_notation("european")
    state = recorder.last(IdentifierState)
    assert state.notation == "european" and state.notes == ()


def test_messages_name_notes_in_the_notation(tmp_path):
    session, _, recorder = european(tmp_path)
    session.identifier_set_notes_text("C Db D")
    assert recorder.last(IdentifierState).message.splitlines()[0] == "Notes: Do, Reb, Re"
    session.set_notation("american")
    assert recorder.last(IdentifierState).message.splitlines()[0] == "Notes: C, Db, D"


def test_typed_notes_in_either_notation():
    assert parse_notes("Do Mi Sol") == ([("C", 4), ("E", 4), ("G", 4)], [])
    assert parse_notes("sol3, SI3 re4") == ([("G", 3), ("B", 3), ("D", 4)], [])
    assert parse_notes("Sib Re Fa")[0] == [("A#", 4), ("D", 5), ("F", 5)]
    assert parse_notes("Ré Fa# La")[0] == [("D", 4), ("F#", 4), ("A", 4)]
    assert parse_notes("Do# E Lab")[0] == [("C#", 4), ("E", 4), ("G#", 4)]
    # Do and Fa are syllables, not D and F with something after them.
    assert parse_notes("Do Fa") == ([("C", 4), ("F", 4)], [])
    assert parse_notes("Dox Q") == ([("C", 4)], ["Dox", "Q"])
    assert spelling_preference("Sib Re Fa") == "flats"
    assert spelling_preference("Do# Mi Sol#") == "sharps"


def test_flats_typed_in_solfege_name_the_chord_with_flats(tmp_path):
    session, _, recorder = european(tmp_path)
    session.identifier_set_notes_text("Sib Re Fa")
    assert recorder.last(IdentifierState).candidates[0] == "Sib"


def test_the_note_helpers_spell_in_a_notation():
    assert spell("C#", "european") == "Do#" and spell("Bb4", "european") == "Sib4"
    assert spell("Cmaj7/E", "european") == "Domaj7/Mi"
    assert spell("Cmaj7/E", "american") == "Cmaj7/E"
    assert midi_name(55, "european") == "Sol3" and midi_name(55) == "G3"
    assert outside_piano([48, 86], notation="european") == ("◂ Do3", "Re6 ▸")


def test_the_desktop_model_follows_the_song_notation(tmp_path):
    session, _, _ = make(tmp_path)
    model = session.chord_identifier_model()
    seen = []
    model.observe("notation", seen.append)
    shown = []
    model.observe("identified_chords", shown.append)
    model.set_notes_from_string("A C E")
    assert model.identified_chords[0] == "Am"

    session.set_notation("european")
    assert seen == ["european"] and model.notation == "european"
    assert shown[-1][0] == "Lam" == model.candidates[0]
    # The dialog plays what its list shows.
    assert model.american_chord("Lam") == "Am"

    # A model handed out while the song is European starts European.
    assert session.chord_identifier_model().notation == "european"


def test_the_viewmodel_plays_a_european_candidate():
    played = []

    class Audio:
        def play_chord_from_midi(self, midi, duration=2.0):
            played.append(list(midi))

    model = ChordIdentifierViewModel(SongParserService(), Audio())
    model.set_notation("european")
    model.set_notes([("A", 4), ("C", 5), ("E", 5)])
    model.play_chord("Lam")
    assert played == [[69, 72, 76]]
    # Not a candidate: read as European.
    assert model.american_chord("Rem7") == "Dm7"
    with pytest.raises(ValueError):
        model.set_notation("german")

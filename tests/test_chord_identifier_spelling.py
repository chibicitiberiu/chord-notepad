"""Chord Identifier naming chords that need flats (todo #1).

The identifier works on piano keys (spelled with sharps), but music21 finds a
chord's root from the spelling: A# D F isn't stacked in thirds, so it used to
come out as D. The notes are now respelled so the chord stacks in thirds, and
the answer is spelled the way the notes were typed (flats in, flats out).
"""

import pytest

from services.song_parser_service import SongParserService
from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel


@pytest.fixture(scope="module")
def vm():
    return ChordIdentifierViewModel(SongParserService())


def typed(vm, text):
    vm.set_notes_from_string(text)
    return vm.candidates


def keys(vm, *notes):
    """Piano keys: sharps, explicit octaves, lowest first."""
    vm.set_notes([(name, octave) for name, octave in notes])
    return vm.candidates


# Typed with flats: (notes, the first answer, an answer that must not appear)
FLAT_TYPED = [
    ("Bb4 D5 F5", "Bb", "D"),
    ("Eb4 G4 Bb4", "Eb", "G"),
    ("Ab4 C5 Eb5", "Ab", "C"),
    ("Db4 F4 Ab4", "Db", "F"),
    ("Bb4 Db5 F5", "Bbm", "Fm"),
    ("Eb4 Gb4 Bb4", "Ebm", "D#m"),
    ("F4 Ab4 C5", "Fm", None),
    ("C4 Eb4 G4", "Cm", None),
    ("G4 Bb4 D5", "Gm", None),
    ("Bb4 D5 F5 Ab5", "Bb7", "D7"),
    ("Eb4 G4 Bb4 Db5", "Eb7", None),
    ("Ab4 C5 Eb5 Gb5", "Ab7", None),
    ("Eb4 G4 Bb4 D5", "Ebmaj7", "Gmaj7"),
    ("Bb4 Db5 F5 Ab5", "Bbm7", None),
    ("C4 Eb4 Gb4", "Cdim", "D#dim"),
    ("Bb4 Db5 Fb5", None, None),          # Fb isn't a note the field takes
    ("Gb4 Bb4 Db5", "Gb", "F#"),
]


@pytest.mark.parametrize("text,first,never", FLAT_TYPED)
def test_typed_flats_are_named_with_flats(vm, text, first, never):
    found = typed(vm, text)
    if first is None:
        return
    assert found and found[0] == first, found
    assert never not in found
    assert not any("#" in name or "-" in name for name in found), found


# Piano keys (always sharps): (notes, expected first answer)
PIANO = [
    ((("A#", 3), ("D", 4), ("F", 4)), "Bb"),
    ((("D#", 4), ("G", 4), ("A#", 4)), "Eb"),
    ((("G#", 3), ("C", 4), ("D#", 4)), "Ab"),
    ((("C#", 4), ("F", 4), ("G#", 4)), "Db"),
    ((("A#", 3), ("C#", 4), ("F", 4)), "Bbm"),
    ((("D#", 4), ("F#", 4), ("A#", 4)), "Ebm"),
    ((("C#", 4), ("E", 4), ("G#", 4)), "C#m"),
    ((("G#", 3), ("B", 3), ("D#", 4)), "G#m"),
    ((("F#", 4), ("A#", 4), ("C#", 5)), "F#"),
    ((("A#", 3), ("D", 4), ("F", 4), ("G#", 4)), "Bb7"),
    ((("D#", 4), ("G", 4), ("A#", 4), ("D", 5)), "Ebmaj7"),
    ((("C", 4), ("D#", 4), ("F#", 4)), "Cdim"),
    ((("A", 3), ("C", 4), ("D#", 4)), "Adim"),
    ((("C", 4), ("E", 4), ("G", 4)), "C"),
    ((("A", 3), ("C", 4), ("E", 4)), "Am"),
    ((("G", 3), ("B", 3), ("D", 4), ("F", 4)), "G7"),
    ((("D", 4), ("F#", 4), ("A", 4), ("C", 5)), "D7"),
    ((("E", 4), ("G#", 4), ("B", 4)), "E"),
    ((("C", 4), ("E", 4), ("G#", 4)), "Caug"),
]


@pytest.mark.parametrize("notes,first", PIANO)
def test_piano_keys_are_named_by_the_chord_they_make(vm, notes, first):
    found = keys(vm, *notes)
    assert found and found[0] == first, found
    assert not any("-" in name for name in found), found


def test_slash_bass_is_spelled_like_the_chord(vm):
    # Bb major with D in the bass, from the piano.
    found = keys(vm, ("D", 3), ("F", 3), ("A#", 3))
    assert "Bb/D" in found and "D" not in found
    # Eb major over Bb, typed.
    found = typed(vm, "Bb3 Eb4 G4")
    assert "Eb/Bb" in found and not any("#" in n for n in found)


def test_sharps_in_sharps_out(vm):
    assert typed(vm, "F#4 A#4 C#5")[0] == "F#"
    assert typed(vm, "D#4 F#4 A#4")[0] == "D#m"


def test_the_typed_spelling_is_forgotten_after_a_key_tap(vm):
    typed(vm, "Eb4 Gb4 Bb4")
    assert vm.candidates[0] == "Ebm"
    vm.toggle_note("A#", 4)            # deselect Bb with the piano
    vm.toggle_note("A#", 4)            # and select it again
    assert vm.candidates[0] == "Ebm"   # the piano's own choice, still Eb


def test_diminished_sevenths_use_the_typed_spelling(vm):
    found = typed(vm, "C4 Eb4 Gb4 A4")
    assert {"Cdim7", "Ebdim7", "Gbdim7", "Adim7"} <= set(found)
    assert not any("#" in n for n in found)


def test_no_chord_lists_the_notes_as_typed(vm):
    vm.set_notes_from_string("C4 Db4 D4")
    assert vm.candidates == []
    assert vm.info_lines[0] == "Notes: C, Db, D"


def test_a_root_in_the_bass_gives_no_slash_chord(vm):
    assert typed(vm, "Eb4 G4 Bb4") == ["Eb"]
    assert typed(vm, "Db4 F4 Ab4") == ["Db"]
    assert keys(vm, ("D#", 4), ("F#", 4), ("A#", 4)) == ["Ebm"]


def test_sharps_that_cant_make_the_chord_give_way_to_flats(vm):
    assert typed(vm, "A#4 D5 F5")[0] == "Bb"

"""Tests for the shared note-name parser in chord/midi_converter."""

import pytest

from chord.midi_converter import parse_note_to_semitone


class TestPlainNaturals:
    @pytest.mark.parametrize("name,expected", [
        ("C", 0), ("D", 2), ("E", 4), ("F", 5),
        ("G", 7), ("A", 9), ("B", 11),
    ])
    def test_natural_letters_map_to_semitone(self, name, expected):
        assert parse_note_to_semitone(name) == expected

    def test_lowercase_letters_also_accepted(self):
        assert parse_note_to_semitone("c") == 0
        assert parse_note_to_semitone("g") == 7


class TestSingleAccidentals:
    @pytest.mark.parametrize("name,expected", [
        ("C#", 1), ("D#", 3), ("F#", 6), ("G#", 8), ("A#", 10),
        ("Db", 1), ("Eb", 3), ("Gb", 6), ("Ab", 8), ("Bb", 10),
    ])
    def test_standard_sharps_and_flats(self, name, expected):
        assert parse_note_to_semitone(name) == expected


class TestEnharmonicEdgeCases:
    @pytest.mark.parametrize("name,expected", [
        ("E#", 5),   # = F
        ("B#", 0),   # = C
        ("Cb", 11),  # = B
        ("Fb", 4),   # = E
    ])
    def test_white_key_enharmonics(self, name, expected):
        assert parse_note_to_semitone(name) == expected


class TestDoubleAccidentals:
    @pytest.mark.parametrize("name,expected", [
        ("C##", 2),   # = D
        ("D##", 4),   # = E
        ("F##", 7),   # = G
        ("Cbb", 10),  # = A#
        ("Ebb", 2),   # = D
        ("Abb", 7),   # = G
    ])
    def test_double_sharps_and_flats(self, name, expected):
        assert parse_note_to_semitone(name) == expected

    def test_octave_wrap_for_high_accidentals(self):
        # B + ## should wrap: 11 + 2 = 13 -> 1
        assert parse_note_to_semitone("B##") == 1
        # C + bb should wrap: 0 - 2 = -2 -> 10
        assert parse_note_to_semitone("Cbb") == 10


class TestMusic21StyleFlats:
    def test_dash_accepted_as_flat(self):
        assert parse_note_to_semitone("B-") == 10
        assert parse_note_to_semitone("E-") == 3


class TestInvalidInput:
    def test_empty_string(self):
        assert parse_note_to_semitone("") is None

    def test_unknown_letter(self):
        assert parse_note_to_semitone("H") is None
        assert parse_note_to_semitone("X#") is None

    def test_garbage_accidentals(self):
        assert parse_note_to_semitone("C$") is None
        assert parse_note_to_semitone("C#x") is None

    def test_none_returns_none(self):
        # None and empty strings short-circuit to None; we never raise on bad input.
        assert parse_note_to_semitone(None) is None

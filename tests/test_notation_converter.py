"""Tests for the per-chord NotationConverter functions.

For whole-text conversion, see tests/test_song_parser_service.py.
"""

import pytest

from chord.converter import NotationConverter


class TestChordAmericanToEuropean:
    def test_major(self):
        assert NotationConverter.chord_american_to_european("C") == "Do"

    def test_minor(self):
        assert NotationConverter.chord_american_to_european("Am") == "Lam"

    def test_with_seventh(self):
        assert NotationConverter.chord_american_to_european("G7") == "Sol7"

    def test_maj7(self):
        # The converter keeps the literal "maj" suffix.
        assert NotationConverter.chord_american_to_european("Cmaj7") == "Domaj7"

    def test_sharp_root(self):
        assert NotationConverter.chord_american_to_european("F#m") == "Fa#m"

    def test_flat_root(self):
        assert NotationConverter.chord_american_to_european("Bb") == "Sib"

    def test_slash_chord(self):
        assert NotationConverter.chord_american_to_european("C/G") == "Do/Sol"

    def test_slash_with_quality(self):
        assert NotationConverter.chord_american_to_european("Am7/E") == "Lam7/Mi"

    def test_unknown_letter_unchanged(self):
        """Letters outside the chord alphabet pass through unchanged."""
        assert NotationConverter.chord_american_to_european("X") == "X"


class TestChordEuropeanToAmerican:
    def test_major(self):
        assert NotationConverter.chord_european_to_american("Do") == "C"

    def test_minor_via_lowercase(self):
        # Lowercase European root means minor.
        assert NotationConverter.chord_european_to_american("lam") == "Am"

    def test_uppercase_with_m(self):
        assert NotationConverter.chord_european_to_american("Lam") == "Am"

    def test_seventh(self):
        assert NotationConverter.chord_european_to_american("Sol7") == "G7"

    def test_maj_uppercase_M_becomes_maj(self):
        # The converter normalizes M -> maj for PyChord compatibility.
        assert NotationConverter.chord_european_to_american("DoM7") == "Cmaj7"

    def test_sharp_root(self):
        assert NotationConverter.chord_european_to_american("Fa#m") == "F#m"

    def test_flat_root(self):
        assert NotationConverter.chord_european_to_american("Sib") == "Bb"

    def test_slash_chord(self):
        assert NotationConverter.chord_european_to_american("Do/Sol") == "C/G"

    def test_accents_stripped(self):
        # Accents on the root are normalized away before lookup.
        assert NotationConverter.chord_european_to_american("Dó") == "C"
        assert NotationConverter.chord_european_to_american("Fá7") == "F7"


class TestFormatForDisplay:
    def test_american_default_passthrough(self):
        assert NotationConverter.format_for_display("Cmaj7") == "Cmaj7"

    def test_european_display(self):
        assert NotationConverter.format_for_display("Cmaj7", notation="european") == "Domaj7"

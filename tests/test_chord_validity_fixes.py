"""Half-diminished Roman numerals play; run-together extensions are invalid."""
import pytest

from chord.detector import ChordDetector
from chord.helper import ChordHelper


@pytest.mark.parametrize("roman, key, notes", [
    ("viiø", "C", ["B", "D", "F", "A"]),
    ("viiø7", "C", ["B", "D", "F", "A"]),
    ("iiø7", "C", ["D", "F", "Ab", "C"]),
    ("iiø", "Am", ["B", "D", "F", "A"]),
    ("VIIø", "G", ["F#", "A", "C", "E"]),
])
def test_half_diminished_roman_numerals_resolve(roman, key, notes):
    result = ChordHelper().compute_chord_notes(roman, key=key, is_relative=True)
    assert result is not None
    assert result.notes == notes


@pytest.mark.parametrize("chord", ["C77", "C79", "C711", "C99", "C47", "Am77", "Do79"])
def test_run_together_extensions_are_invalid(chord):
    assert not ChordHelper().is_valid_chord(chord)


@pytest.mark.parametrize("chord", ["C7", "C9", "C11", "C13", "C69", "C6", "C5", "C2", "Cadd4",
                                   "Cm7b5", "C7#9", "C13#11", "C9sus4", "Cmaj9", "C6add9",
                                   "C7(b9)", "Cmaj13#11", "Csus2", "C7sus4", "Cm11", "Do7",
                                   "C7♭9", "Cdim7", "Caug7", "Bbm9", "Cm69"])
def test_real_chords_stay_valid(chord):
    assert ChordHelper().is_valid_chord(chord)


def test_detector_marks_c77_invalid():
    chords = ChordDetector().detect_chords_in_text("C77 G")
    assert [(c.chord, c.is_valid) for c in chords] == [("C77", False), ("G", True)]

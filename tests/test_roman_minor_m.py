"""Roman numerals with an ``m`` for minor: ``iim7`` and ``IIm7`` both mean the
minor seventh on degree 2 (Dm7 in C), like ``ii7``."""
import pytest

from audio.chord_picker import ChordNotePicker
from chord.detector import ChordDetector
from chord.helper import ChordHelper
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from services.transpose_service import transpose_text


@pytest.mark.parametrize("roman, key, symbol", [
    ("iim7", "C", "Dm7"), ("IIm7", "C", "Dm7"), ("ii7", "C", "Dm7"),
    ("VIm", "C", "Am"), ("IIIm7", "G", "Bm7"), ("bIIIm7", "C", "Ebm7"),
    ("#ivm7b5", "C", "F#m7b5"), ("IIm7/V", "C", "Dm7/G"), ("vim/IV", "C", "Am/F"),
    ("Imaj7", "C", "Cmaj7"), ("iim7b5", "C", "Dm7b5"), ("vii°", "C", "Bdim"),
])
def test_resolution(roman, key, symbol):
    notes = ChordHelper().compute_chord_notes(roman, key=key, is_relative=True)
    assert notes is not None
    assert notes.resolved_symbol == symbol


@pytest.mark.parametrize("notation", ["american", "european"])
@pytest.mark.parametrize("roman", ["iim7", "IIm7", "VIm", "IIIm7", "bIIIm7", "#ivm7b5",
                                   "IIm7/V", "Im"])
def test_detected_as_roman_numerals(roman, notation):
    chords = ChordDetector(notation=notation).detect_chords_in_text(f"I {roman} V7 I")
    assert [(c.chord, c.is_relative, c.is_valid) for c in chords] == [
        ("I", True, True), (roman, True, True), ("V7", True, True), ("I", True, True)]


def test_ii_dash_7_stays_unsupported():
    chords = ChordDetector().detect_chords_in_text("I ii-7 V7 I")
    assert "ii-7" not in [c.chord for c in chords]


def test_plays_the_minor_chord():
    lines = SongParserService().detect_chords_in_text("{key: C}\nIIm7 V7 I")
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    assert [rc.chord_notes.notes for rc in song.chords][0] == ["D", "F", "A", "C"]


def test_transpose_and_convert_leave_them_alone():
    text = "{key: C}\nIIm7 V7 Im\nC G"
    parser = SongParserService()
    assert transpose_text(text, 2, "american").splitlines()[1] == "IIm7 V7 Im"
    assert parser.convert_to_european(text).splitlines()[1] == "IIm7 V7 Im"


@pytest.mark.parametrize("roman", ["IIm7", "VIm", "iim7", "bIIIm7"])
def test_parser_recognises_them(roman):
    assert SongParserService().is_roman_numeral_chord(roman)

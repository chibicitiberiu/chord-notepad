"""Roman-numeral roots are spelled by degree: bVI in C is Ab, not G#.

The letter comes from the scale degree (VI of C is A), the accidental from
the numeral's # or b. Only the spelling changes; the pitches are the same.
"""
import pytest

from chord.helper import ChordHelper
from chord.midi_converter import parse_note_to_semitone


CASES = [
    ("bVI", "C", "Ab"), ("bIII", "C", "Eb"), ("bVII", "C", "Bb"), ("bII", "C", "Db"),
    ("#IV", "C", "F#"), ("#iv°", "C", "F#"), ("bVI", "F", "Db"), ("bIII", "F", "Ab"),
    ("bVII", "Bb", "Ab"), ("IV", "Bb", "Eb"), ("V", "Bb", "F"), ("bII", "G", "Ab"),
    ("#IV", "F", "B"), ("bVI", "D", "Bb"), ("IV", "F#", "B"), ("vii°", "F#", "E#"),
    ("bVII", "Eb", "Db"), ("bVI", "Ab", "Fb"), ("V", "Db", "Ab"), ("iii", "E", "G#"),
    ("bIII", "Am", "C"), ("bVI", "Am", "F"), ("#IV", "F#", "B#"),
    # A double accidental (Bbb, C##) is written as its plain enharmonic.
    ("bVI", "Db", "A"), ("bIII", "Gb", "A"), ("#IV", "C#", "G"),
]


@pytest.mark.parametrize("roman, key, root", CASES)
def test_roman_root_spelling(roman, key, root):
    notes = ChordHelper().compute_chord_notes(roman, key=key, is_relative=True)
    assert notes is not None
    assert notes.root == root
    assert notes.resolved_symbol.startswith(root)


@pytest.mark.parametrize("roman, key", [(r, k) for r, k, _ in CASES])
def test_spelling_keeps_the_pitch(roman, key):
    """The root's pitch class is the key's plus the degree's semitones."""
    helper = ChordHelper()
    notes = helper.compute_chord_notes(roman, key=key, is_relative=True)
    major = [0, 2, 4, 5, 7, 9, 11]
    degrees = {'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6}
    accidental = {'b': -1, '#': 1}.get(roman[0], 0)
    numeral = roman.lstrip('#b').rstrip('°').upper()
    tonic = parse_note_to_semitone(key.rstrip('m'))
    expected = (tonic + major[degrees[numeral]] + accidental) % 12
    assert parse_note_to_semitone(notes.root) % 12 == expected


def test_slash_bass_is_spelled_by_degree_too():
    notes = ChordHelper().compute_chord_notes("I/bVII", key="C", is_relative=True)
    assert notes.bass_note == "Bb"

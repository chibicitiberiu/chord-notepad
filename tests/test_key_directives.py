"""Key names: ``{key}`` must name a real key, and European keys work.

A key is a note name (American C..B or European Do..Si, with an optional
#/b) and an optional ``m`` for minor. Anything else is an invalid directive,
and Roman numerals after it resolve against the key in effect before it.
"""
import pytest

from audio.chord_picker import ChordNotePicker
from chord.helper import ChordHelper
from chord.keys import american_key
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


@pytest.mark.parametrize("key, expected", [
    ("C", "C"), ("Am", "Am"), ("F#", "F#"), ("Bbm", "Bbm"), ("Eb", "Eb"),
    ("Do", "C"), ("Lam", "Am"), ("Sib", "Bb"), ("Fa#m", "F#m"), ("Sol", "G"),
    ("Ré", "D"), ("Mib", "Eb"), ("F♯", "F#"), ("B♭m", "Bbm"), (" G ", "G"),
])
def test_valid_keys(key, expected):
    assert american_key(key) == expected


@pytest.mark.parametrize("key", ["Xyz", "H", "", None, "C major", "Cmaj", "am", "C7",
                                 "Dox", "Lamm", "C##"])
def test_invalid_keys(key):
    assert american_key(key) is None


@pytest.mark.parametrize("value, valid", [("G", True), ("Lam", True), ("Xyz", False),
                                          ("C7", False)])
def test_key_directive_validity(value, valid):
    [directive] = SongParserService().parse_directives(f"{{key: {value}}}")
    assert directive.is_valid is valid


def _played(text, key="C", notation="american"):
    lines = SongParserService().detect_chords_in_text(text, notation)
    song = SongRenderer().render(lines=lines, initial_key=key, initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    return [(rc.chord_info.chord, rc.chord_notes.root, rc.key) for rc in song.chords]


def test_an_invalid_key_is_ignored_by_roman_numerals():
    assert _played("{key: G}\nI\n{key: Xyz}\nV") == [("I", "G", "G"), ("V", "D", "G")]


def test_an_invalid_key_falls_back_to_the_toolbar_key():
    assert _played("{key: Xyz}\nI V", key="F") == [("I", "F", "F"), ("V", "C", "F")]


@pytest.mark.parametrize("key, root", [("Do", "C"), ("Lam", "A"), ("Sib", "Bb"), ("Re", "D")])
def test_roman_numerals_resolve_in_european_keys(key, root):
    notes = ChordHelper().compute_chord_notes("I", key=key, is_relative=True)
    assert notes.root == root


def test_european_song_with_roman_numerals():
    played = _played("{key: Sol}\nI IV V", key="Do", notation="european")
    assert [root for _c, root, _k in played] == ["G", "C", "D"]


def test_no_key_leaves_roman_numerals_unresolved():
    assert _played("I V C", key=None) == [("C", "C", None)]

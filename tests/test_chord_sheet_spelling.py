"""A reference test for the chord sheet's note spelling (``chord_sheet/spelling.py``).

Note spelling is music theory, so the expected names here are written from
first principles, not read back from the code:

- a key signature adds sharps in the order F C G D A E B and flats in the
  order B E A D G C F; the seven letters with those accidentals are the
  key's scale;
- a pitch class outside the scale is a sharp in C and sharp keys and a flat
  in flat keys;
- the octave number goes with the letter: MIDI 60 is C4, so B#3 and C4 are
  the same key, as are Cb5 and B4, and E#4 is F4.

Every MIDI note (0-127) is checked in F# major (6 sharps), Gb major (6
flats) and C, in both notations, as a note outside any chord. A few chords
then check that a chord's notes are spelled as one stack from its root.
"""

import pytest

from chordnotepad.audio.chord_picker import ChordNotePicker
from chordnotepad.chord_sheet.spelling import key_fifths, note_name, spell_midi
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.song_renderer import SongRenderer

#: Letter -> its natural pitch class.
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
#: The European (fixed-do) syllable of each letter.
SOLFEGE = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}

#: Pitch class -> written (letter, accidental), worked out by hand per key.
#: F# major: F# G# A# B C# D# E#. The five pitch classes outside it are the
#: white keys C D E G A, which a sharp key writes as naturals.
F_SHARP_MAJOR = {
    0: ("C", 0),    # not in the scale (C# is): plain C
    1: ("C", 1),    # C#, scale
    2: ("D", 0),    # not in the scale: D
    3: ("D", 1),    # D#, scale
    4: ("E", 0),    # not in the scale (E# is): E
    5: ("E", 1),    # E#, scale: the leading note, never F
    6: ("F", 1),    # F#, tonic
    7: ("G", 0),    # not in the scale: G
    8: ("G", 1),    # G#, scale
    9: ("A", 0),    # not in the scale: A
    10: ("A", 1),   # A#, scale
    11: ("B", 0),   # B, scale
}
#: Gb major: Gb Ab Bb Cb Db Eb F; the rest are flats or naturals.
G_FLAT_MAJOR = {
    0: ("C", 0),    # not in the scale (Cb is): C
    1: ("D", -1),   # Db, scale
    2: ("D", 0),    # not in the scale: D
    3: ("E", -1),   # Eb, scale
    4: ("E", 0),    # not in the scale: E
    5: ("F", 0),    # F, scale
    6: ("G", -1),   # Gb, tonic
    7: ("G", 0),    # not in the scale: G
    8: ("A", -1),   # Ab, scale
    9: ("A", 0),    # not in the scale: A
    10: ("B", -1),  # Bb, scale
    11: ("C", -1),  # Cb, scale: the fourth degree, never B
}
#: C major: naturals, and sharps for the black keys.
C_MAJOR = {
    0: ("C", 0), 1: ("C", 1), 2: ("D", 0), 3: ("D", 1), 4: ("E", 0), 5: ("F", 0),
    6: ("F", 1), 7: ("G", 0), 8: ("G", 1), 9: ("A", 0), 10: ("A", 1), 11: ("B", 0),
}

KEYS = {"F#": F_SHARP_MAJOR, "Gb": G_FLAT_MAJOR, "C": C_MAJOR}


def _written_octave(midi, letter, accidental):
    """The octave number of ``letter`` + ``accidental`` sounding at ``midi``:
    the octave of the natural letter the accidental is applied to."""
    natural = midi - accidental          # the natural note the accidental alters
    assert natural % 12 == NATURAL[letter]
    return natural // 12 - 1


def _expected(midi, table, notation):
    letter, accidental = table[midi % 12]
    octave = _written_octave(midi, letter, accidental)
    mark = "#" if accidental > 0 else "b" if accidental < 0 else ""
    name = SOLFEGE[letter] if notation == "european" else letter
    return f"{name}{mark}{octave}"


def test_the_seams_by_hand():
    # Spot checks of the helper itself, so the tables above mean what they say.
    assert _expected(60, C_MAJOR, "american") == "C4"
    assert _expected(65, F_SHARP_MAJOR, "american") == "E#4"
    assert _expected(71, G_FLAT_MAJOR, "american") == "Cb5"
    assert _expected(59, G_FLAT_MAJOR, "european") == "Dob4"
    assert _expected(0, C_MAJOR, "american") == "C-1"
    assert _expected(127, C_MAJOR, "european") == "Sol9"


@pytest.mark.parametrize("notation", ["american", "european"])
@pytest.mark.parametrize("key", list(KEYS))
def test_every_midi_note_outside_a_chord(key, notation):
    table = KEYS[key]
    got = [note_name(midi, None, key, notation) for midi in range(128)]
    want = [_expected(midi, table, notation) for midi in range(128)]
    assert got == want


@pytest.mark.parametrize("key, minor", [("F#", "D#m"), ("Gb", "Ebm"), ("C", "Am")])
def test_a_minor_key_spells_like_its_relative_major(key, minor):
    assert key_fifths(minor) == key_fifths(key)
    assert [note_name(m, None, minor) for m in range(128)] == [
        note_name(m, None, key) for m in range(128)]


def test_european_keys_read_as_their_american_spelling():
    assert [note_name(m, None, "Solb", "european") for m in range(128)] == [
        _expected(m, G_FLAT_MAJOR, "european") for m in range(128)]


def test_no_key_spells_sharps():
    assert [note_name(m, None, None) for m in range(128)] == [
        _expected(m, C_MAJOR, "american") for m in range(128)]


def test_the_octave_follows_the_spelling():
    # B#3 sounds as C4 (60): the B position, one octave number lower.
    note = spell_midi(60, None, key_fifths("C#"))
    assert (note.letter, note.accidental, note.octave) == ("B", 1, 3)
    assert note.diatonic_index == 3 * 7 + 6
    # Cb5 sounds as B4 (71).
    note = spell_midi(71, None, key_fifths("Gb"))
    assert (note.letter, note.accidental, note.octave) == ("C", -1, 5)
    assert note.diatonic_index == 5 * 7


# -- chords: one stack of thirds from the root ------------------------------------

def _chords(text):
    lines = SongParserService().detect_chords_in_text(text)
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    return song.chords


@pytest.mark.parametrize("text, notes, american, european", [
    # Db is diatonic to F# as C#: the chord is C# E# G#.
    ("{key: F#}\nDb", [61, 65, 68], ["C#4", "E#4", "G#4"], ["Do#4", "Mi#4", "Sol#4"]),
    # B is chromatic in Db: it keeps its own spelling, a major third up is D#.
    ("{key: Db}\nB", [59, 63, 66], ["B3", "D#4", "F#4"], ["Si3", "Re#4", "Fa#4"]),
    # Gbm would need Bbb: spelled from F# instead.
    ("{key: C}\nGbm", [57, 61, 66], ["A3", "C#4", "F#4"], ["La3", "Do#4", "Fa#4"]),
    # G#7's third is B#, written in octave 3 though it sounds as C4.
    ("{key: E}\nG#7", [60, 63, 66, 68], ["B#3", "D#4", "F#4", "G#4"],
     ["Si#3", "Re#4", "Fa#4", "Sol#4"]),
    # Abm's third is Cb, written in octave 4 though it sounds as B3.
    ("{key: Ab}\nAbm", [59, 63, 68], ["Cb4", "Eb4", "Ab4"], ["Dob4", "Mib4", "Lab4"]),
])
def test_a_chord_is_spelled_from_its_root(text, notes, american, european):
    [chord] = _chords(text)
    assert set(notes) <= set(chord.midi_notes)
    assert [note_name(m, chord.chord_notes, chord.key) for m in notes] == american
    assert [note_name(m, chord.chord_notes, chord.key, "european") for m in notes] == european

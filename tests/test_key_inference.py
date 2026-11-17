"""Reference tests for key inference (chord.key_inference).

The expected keys and leading tones are written out by hand for every
major and minor key, not computed with the module's own tables, so a
wrong scale degree or a wrong leading tone can't agree with itself.
"""

import pytest

from chordnotepad.chord.helper import ChordHelper
from chordnotepad.chord.key_inference import infer_keys, triad_quality

_HELPER = ChordHelper()

_PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6,
       'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}


def _keys(progression, window=4):
    return infer_keys([_HELPER.compute_chord_notes(s) for s in progression.split()], window)


# I IV V7 I in every major key, with the leading tone spelled out.
MAJOR = [
    ('C', 'C F G7 C', 'B'), ('G', 'G C D7 G', 'F#'), ('D', 'D G A7 D', 'C#'),
    ('A', 'A D E7 A', 'G#'), ('E', 'E A B7 E', 'D#'), ('B', 'B E F#7 B', 'A#'),
    ('F#', 'F# B C#7 F#', 'E#'), ('Db', 'Db Gb Ab7 Db', 'C'), ('Ab', 'Ab Db Eb7 Ab', 'G'),
    ('Eb', 'Eb Ab Bb7 Eb', 'D'), ('Bb', 'Bb Eb F7 Bb', 'A'), ('F', 'F Bb C7 F', 'E'),
]

# i iv V7 i in every minor key: the leading tone is the raised seventh.
MINOR = [
    ('A', 'Am Dm E7 Am', 'G#'), ('E', 'Em Am B7 Em', 'D#'), ('B', 'Bm Em F#7 Bm', 'A#'),
    ('F#', 'F#m Bm C#7 F#m', 'E#'), ('C#', 'C#m F#m G#7 C#m', 'B#'),
    ('G#', 'G#m C#m D#7 G#m', 'F##'), ('Eb', 'Ebm Abm Bb7 Ebm', 'D'),
    ('Bb', 'Bbm Ebm F7 Bbm', 'A'), ('F', 'Fm Bbm C7 Fm', 'E'), ('C', 'Cm Fm G7 Cm', 'B'),
    ('G', 'Gm Cm D7 Gm', 'F#'), ('D', 'Dm Gm A7 Dm', 'C#'),
]


def _pc(name):
    base = _PC[name[0]]
    return (base + name[1:].count('#') - name[1:].count('b')) % 12


@pytest.mark.parametrize('tonic, progression, leading_tone', MAJOR + MINOR)
def test_cadence_in_every_key(tonic, progression, leading_tone):
    for estimate in _keys(progression):
        assert estimate.tonic_pc == _pc(tonic), progression
        assert estimate.leading_tone_pc == _pc(leading_tone), progression
        assert estimate.confidence >= 0.25, (progression, estimate)


def test_a_diatonic_loop_is_confident_enough():
    keys = _keys('C G Am F C G Am F')
    assert min(k.confidence for k in keys) >= 0.2, [round(k.confidence, 2) for k in keys]


def test_relative_minor_is_told_from_its_major():
    # Same chords' pitch classes, different centre: the E major chord and the
    # cadence to Am make A minor (leading tone G#); C G Am F stays in C.
    assert {k.tonic_pc for k in _keys('Am G F E Am G F E')} == {9}
    assert {k.tonic_pc for k in _keys('C G Am F C G Am F')} == {0}


def test_a_modulation_moves_the_key():
    keys = _keys('C F G7 C Am D7 G Em Am D7 G C D7 G')
    assert keys[1].tonic_pc == 0 and keys[2].tonic_pc == 0
    assert all(k.tonic_pc == 7 for k in keys[5:])


@pytest.mark.parametrize('progression', [
    'C E Ab C E Ab C E',        # major-third cycle
    'C Eb Gb A C Eb Gb A',      # minor-third cycle
    'C B Bb A Ab G F# F',       # chromatic planing
])
def test_chromatic_passages_score_low(progression):
    keys = _keys(progression)
    inner = keys[2:-2]  # the song's ends see half a window
    # The ensemble voicer applies a key's rules from 0.15, fully from 0.25.
    assert max(k.confidence for k in inner) < 0.25, [round(k.confidence, 2) for k in keys]
    assert sum(k.confidence for k in inner) / len(inner) < 0.15


def test_empty_and_unreadable_chords_get_none():
    chords = [_HELPER.compute_chord_notes('C'), _HELPER.compute_chord_notes('G7')]
    from chordnotepad.models.chord_notes import ChordNotes
    chords.insert(1, ChordNotes(notes=[], bass_note=None, root=None))
    keys = infer_keys(chords)
    assert keys[1] is None and keys[0] is not None and keys[2] is not None


@pytest.mark.parametrize('intervals, quality', [
    ([0, 4, 7], 'maj'), ([0, 4, 7, 10], 'maj'), ([0, 4, 7, 11, 14], 'maj'),
    ([0, 3, 7], 'min'), ([0, 3, 7, 10], 'min'), ([0, 3, 6], 'dim'),
    ([0, 3, 6, 9], 'dim'), ([0, 3, 6, 10], 'dim'), ([0, 4, 8], 'aug'),
    ([0, 5, 7], 'other'), ([0, 2, 7], 'other'), ([0, 4], 'maj'), ([0, 4, 6, 10], 'other'),
])
def test_triad_quality(intervals, quality):
    assert triad_quality(intervals) == quality

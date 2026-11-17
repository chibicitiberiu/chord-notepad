"""Reference tests for the shared low-interval table (audio.low_intervals).

Each limit is written out as a note name, from the arranging table, and
converted with the app's own note-name parser, so a wrong MIDI number in the
table can't agree with itself.
"""

import pytest

from chordnotepad.audio.low_intervals import LOW_INTERVAL_LIMITS, semitones_below_limit
from chordnotepad.models.ensemble_spec import parse_note_name

TABLE = {
    'minor second': (1, 'E3'), 'major second': (2, 'Eb3'), 'minor third': (3, 'C3'),
    'major third': (4, 'Bb2'), 'perfect fourth': (5, 'A2'), 'tritone': (6, 'Bb2'),
    'perfect fifth': (7, 'Bb1'), 'minor sixth': (8, 'G2'), 'major sixth': (9, 'F2'),
    'minor seventh': (10, 'F2'), 'major seventh': (11, 'F2'), 'minor ninth': (13, 'E2'),
    'major ninth': (14, 'Eb2'), 'minor tenth': (15, 'C2'), 'major tenth': (16, 'Bb1'),
}


@pytest.mark.parametrize('name', sorted(TABLE))
def test_each_limit(name):
    size, note = TABLE[name]
    assert LOW_INTERVAL_LIMITS[size] == parse_note_name(note), name


def test_the_table_has_nothing_else():
    assert set(LOW_INTERVAL_LIMITS) == {size for size, _note in TABLE.values()}


def test_semitones_below_limit():
    c3, eb3 = parse_note_name('C3'), parse_note_name('Eb3')
    assert semitones_below_limit(c3, eb3) == 0                  # a minor third from C3: clear
    assert semitones_below_limit(c3 - 2, eb3 - 2) == 2          # from Bb2: two under
    assert semitones_below_limit(36, 38 + 12) == 3              # C2 to D3, a major ninth: Eb2 - C2
    assert semitones_below_limit(36, 36) == 0                   # a unison has no limit
    assert semitones_below_limit(36, 48) == 0                   # nor an octave
    assert semitones_below_limit(36, 36 + 17) == 0              # nor anything wider than a tenth
    assert semitones_below_limit(40, 44, offset=-3) == 3        # E2-G#2, limit lowered to G2
    assert semitones_below_limit(40, 44, intervals=(1, 2)) == 0  # a third, not asked about

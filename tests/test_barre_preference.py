"""Regression tests for the interior-mute recalibration (barre preference).

Reported case: in standard tuning, the Ebm / Db / B progression came out as
contorted shapes with a dead string buried inside the strum (Db as
``x-4-x-1-2-1``, B as ``x-2-1-x-0-2``, Ebm as ``x-x-1-3-x-2``) where any
guitarist would reach for the A-shape barre chords. The old
``interior_mute_penalty`` of -2.0 undervalued how hard a buried mute is to
execute; at -4.0 the practical shapes win while every open-position
progression keeps its canonical cowboy voicings (guarded here alongside the
frozen characterization goldens).
"""

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from chord.helper import ChordHelper


@pytest.fixture(scope="module")
def helper():
    return ChordHelper()


def _sequence(helper, symbols):
    chords = []
    for symbol in symbols:
        chord_notes = helper.compute_chord_notes(symbol)
        assert chord_notes is not None, f"could not resolve {symbol}"
        chords.append(chord_notes)
    return chords


def _fingerings_by_symbol(helper, symbols):
    picker = GuitarChordPicker('standard')
    details = picker.voice_sequence_details(_sequence(helper, symbols))
    result = {}
    for symbol, voiced in zip(symbols, details):
        result.setdefault(symbol, voiced.fingering)
    return result


def _has_interior_mute(fingering):
    sounding = [s for s, f in enumerate(fingering) if f >= 0]
    return any(fingering[s] == -1 for s in range(sounding[0] + 1, sounding[-1]))


class TestFlatKeyBarrePreference:
    """The reported Ebm/Db/B progression picks strummable, mute-free shapes."""

    SYMBOLS = ['Ebm', 'Db', 'B', 'Db', 'Ebm', 'Db', 'B', 'Ebm', 'Db']

    def test_no_chord_buries_a_muted_string(self, helper):
        for symbol, fingering in _fingerings_by_symbol(helper, self.SYMBOLS).items():
            assert not _has_interior_mute(fingering), (
                f"{symbol} voiced with an interior mute: {fingering}")

    def test_db_is_the_a_shape_barre(self, helper):
        fingerings = _fingerings_by_symbol(helper, self.SYMBOLS)
        assert fingerings['Db'] == [-1, 4, 6, 6, 6, 4]


class TestOpenPositionShapesUnchanged:
    """The recalibration must not disturb canonical open-position voicings."""

    CASES = {
        'G': [3, 2, 0, 0, 0, 3],
        'C': [-1, 3, 2, 0, 1, 0],
        'D': [-1, -1, 0, 2, 3, 2],
        'Em': [0, 2, 2, 0, 0, 0],
        'Am': [-1, 0, 2, 2, 1, 0],
        'E': [0, 2, 2, 1, 0, 0],
        'A': [-1, 0, 2, 2, 2, 0],
    }

    def test_cowboy_progressions_keep_their_shapes(self, helper):
        progressions = [
            ['G', 'C', 'D', 'Em', 'G', 'C', 'D', 'G'],
            ['C', 'Am', 'G', 'C', 'Am', 'G', 'C'],
            ['E', 'A', 'E', 'A', 'E'],
        ]
        for symbols in progressions:
            fingerings = _fingerings_by_symbol(helper, symbols)
            for symbol, fingering in fingerings.items():
                assert fingering == self.CASES[symbol], (
                    f"{symbol} drifted to {fingering} in {symbols}")

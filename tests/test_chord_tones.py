"""Unit tests for the shared chord-tone role taxonomy."""

import pytest

from chordnotepad.audio.chord_tones import (
    classify_role, is_diminished_seventh, is_named_extension, DEFAULT_OMIT_PENALTY)


class TestClassifyRole:
    """Direct tests of :func:`classify_role` boundaries."""

    def test_root(self) -> None:
        assert classify_role(0) == 'root'

    @pytest.mark.parametrize('interval', [3, 4])
    def test_third(self, interval: int) -> None:
        assert classify_role(interval) == 'third'

    def test_fifth(self) -> None:
        assert classify_role(7) == 'fifth'

    @pytest.mark.parametrize('interval', [6, 8])
    def test_altered_fifth_is_colour(self, interval: int) -> None:
        # The b5 of m7b5/7b5 and the #5 of aug/7#5 define the chord.
        assert classify_role(interval) == 'color'

    @pytest.mark.parametrize('name, intervals', [
        ('m7b5', [0, 3, 6, 10]), ('7b5', [0, 4, 6, 10]), ('dim', [0, 3, 6]),
        ('aug', [0, 4, 8]), ('7#5', [0, 4, 8, 10]), ('addb5', [0, 4, 7, 6]),
    ])
    def test_altered_fifth_in_its_chord_is_colour(self, name, intervals) -> None:
        for interval in intervals:
            if interval in (6, 8):
                assert classify_role(interval, intervals) == 'color', name

    def test_diminished_seventh_b5_is_a_fifth(self) -> None:
        # Any three tones of a dim7 sound the same chord, so its b5 may go.
        dim7 = [0, 3, 6, 9]
        assert is_diminished_seventh(dim7)
        assert classify_role(6, dim7) == 'fifth'
        assert classify_role(9, dim7) == 'color'
        assert not is_diminished_seventh([0, 3, 6, 10])
        assert not is_diminished_seventh([0, 4, 7, 9])  # C6

    def test_addb5_keeps_the_perfect_fifth_as_fifth(self) -> None:
        assert classify_role(7, [0, 4, 7, 6]) == 'fifth'

    @pytest.mark.parametrize('interval', [10, 11])
    def test_seventh(self, interval: int) -> None:
        assert classify_role(interval) == 'seventh'

    @pytest.mark.parametrize('interval', [2, 5, 9])
    def test_color(self, interval: int) -> None:
        # sus2 (2), sus4 (5) and the added 6th (9) are the chord's character.
        assert classify_role(interval) == 'color'

    def test_extension_at_octave(self) -> None:
        assert classify_role(12) == 'extension'

    @pytest.mark.parametrize('interval', [13, 14, 17, 21])
    def test_extension_above_octave(self, interval: int) -> None:
        # Everything >= 12 is upper structure, regardless of pitch class.
        assert classify_role(interval) == 'extension'


class TestNamedExtension:
    """Which extension a chord symbol spells (hand-written from the names)."""

    @pytest.mark.parametrize('name, intervals, named, stacked', [
        ('G13', [0, 4, 7, 10, 14, 21], {21}, {14}),
        ('Am11', [0, 3, 7, 10, 14, 17], {17}, {14}),
        ('C9', [0, 4, 7, 10, 14], {14}, set()),
        ('Cadd9', [0, 4, 7, 14], {14}, set()),
        ('Cmaj9', [0, 4, 7, 11, 14], {14}, set()),
        ('C7b9', [0, 4, 7, 10, 13], {13}, set()),
        ('C7#9', [0, 4, 7, 10, 15], {15}, set()),
        ('C13b9', [0, 4, 7, 10, 13, 21], {13, 21}, set()),
        ('C9#11', [0, 4, 7, 10, 14, 18], {14, 18}, set()),
        ('C7b13', [0, 4, 7, 10, 20], {20}, set()),
        ('C13 with an 11', [0, 4, 7, 10, 14, 17, 21], {21}, {14, 17}),
    ])
    def test_named_and_stacked(self, name, intervals, named, stacked) -> None:
        exts = {iv for iv in intervals if iv >= 12}
        assert {iv for iv in exts if is_named_extension(iv, intervals)} == named, name
        assert {iv for iv in exts if not is_named_extension(iv, intervals)} == stacked, name

    def test_core_tones_are_never_extensions(self) -> None:
        assert not any(is_named_extension(iv, [0, 4, 7, 9]) for iv in [0, 4, 7, 9])


class TestDefaultOmitPenalty:
    """The default penalty table covers exactly the six roles."""

    def test_has_six_role_keys(self) -> None:
        assert set(DEFAULT_OMIT_PENALTY) == {
            'root', 'third', 'fifth', 'seventh', 'color', 'extension',
        }

    def test_every_classified_role_has_a_penalty(self) -> None:
        for interval in range(0, 24):
            assert classify_role(interval) in DEFAULT_OMIT_PENALTY

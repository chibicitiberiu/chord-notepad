"""Unit tests for the shared chord-tone role taxonomy."""

import pytest

from audio.chord_tones import classify_role, DEFAULT_OMIT_PENALTY


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
    def test_altered_fifth(self, interval: int) -> None:
        assert classify_role(interval) == 'fifth'

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


class TestDefaultOmitPenalty:
    """The default penalty table covers exactly the six roles."""

    def test_has_six_role_keys(self) -> None:
        assert set(DEFAULT_OMIT_PENALTY) == {
            'root', 'third', 'fifth', 'seventh', 'color', 'extension',
        }

    def test_every_classified_role_has_a_penalty(self) -> None:
        for interval in range(0, 24):
            assert classify_role(interval) in DEFAULT_OMIT_PENALTY

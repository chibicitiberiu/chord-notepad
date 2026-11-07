"""Transposing and converting there and back gives the text back (C12, C3).

services.aligned_rewrite keeps each chord over its syllable while the names
change length, and undoes on the way back what it did on the way there: the
spaces a chord took or gave, and the fill it put into the lyric. The fill
in a word is a middle dot, never a "-", so the song's own hyphens are left
alone both ways.
"""

import random
import re

import pytest

from services.aligned_rewrite import FILL, insert_into_lyric, take_from_lyric
from services.song_parser_service import SongParserService
from services.transpose_service import transpose_text

_PARSER = SongParserService()


def there_and_back(text, shift, notation="american"):
    up = transpose_text(text, shift, notation)
    return up, transpose_text(up, -shift, notation)


def columns(line):
    return [m.start() for m in re.finditer(r'\S+', line)]


def assert_aligned(before, after):
    """Every chord of ``before`` sits over the same lyric character in ``after``."""
    (chords_b, lyric_b), (chords_a, lyric_a) = before.split('\n')[:2], after.split('\n')[:2]

    def under(lyric, col):
        return lyric[col] if col < len(lyric) else ' '
    assert [under(lyric_b, c) for c in columns(chords_b)] == [
        under(lyric_a, c) for c in columns(chords_a)], (before, after)


class TestTransposeRoundTrip:
    def test_the_reported_song(self):
        # Pass 2: up a semitone stretched "hello there"; down again it's back.
        text = "C Am F G E7 B7\nhello there\n"
        up, back = there_and_back(text, 1)
        assert up == f"Db Bbm Gb Ab F7 C7\nhe{FILL}llo   the{FILL}re\n"
        assert back == text

    @pytest.mark.parametrize("shift", range(-11, 12))
    def test_every_shift_of_a_packed_line(self, shift):
        text = "{key: C}\nC Am F G Em Dm7 G7 C\nhello there my old friend\n"
        up, back = there_and_back(text, shift)
        assert_aligned(text.split('\n', 1)[1], up.split('\n', 1)[1])
        assert back == text

    def test_the_songs_own_hyphens_stay(self):
        # A "-" right before a chord's syllable is the song's: a shorter chord
        # before it pads, it doesn't take the hyphen out.
        text = "C#m E\nHal-le\n"
        up, back = there_and_back(text, -1)
        assert up == "Cm  Eb\nHal-le\n"
        assert back == text

    def test_a_gap_a_chord_grew_into_is_given_back(self):
        # Am -> C#m eats one of the two spaces; back down it's padded again,
        # and the hyphenated lyric isn't touched either way.
        text = "{key: C}\nAm  B  C\nhal-le-lu-jah\n"
        up, back = there_and_back(text, 4)
        assert up.split('\n')[2] == "hal-le-lu-jah"
        assert back == text

    def test_a_line_of_chords_alone(self):
        text = "{key: C}\nC G Am F\n\nC   G   Am   F\n"
        for shift in (1, 3, -2, 6):
            assert there_and_back(text, shift)[1] == text

    def test_the_listed_exception_a_narrowed_gap_without_a_lyric(self):
        # With nothing below, a gap a longer chord narrowed to one space reads
        # like a gap it grew into: on the way back it stays one space.
        up, back = there_and_back("{key: C}\nAm  F\n", 1)
        assert up == "{key: Db}\nBbm Gb\n"
        assert back == "{key: C}\nAm F\n"

    def test_the_listed_exception_hand_spaced_lyrics(self):
        # Two spaces in the lyric under a gap a longer chord narrowed: on the
        # way back the shorter chord takes one (the chords stay aligned).
        up, back = there_and_back("{key: C}\nAm  F\nmy  love\n", 1)
        assert up == "{key: Db}\nBbm Gb\nmy  love\n"
        assert back == "{key: C}\nAm F\nmy love\n"

    def test_a_chord_at_the_end_of_a_line_leaves_no_trailing_spaces(self):
        up = transpose_text("Db  Ab\nwords here\n", -1, "american")
        assert up == "C   G\nwords here\n"

    def test_seeded_sample_of_single_spaced_lyrics(self):
        # Chords anywhere over a single-spaced lyric that runs past them:
        # every shift there and back gives the text back.
        rng = random.Random(7)
        chords = ['C', 'Dm', 'Em', 'F', 'G7', 'Am', 'Bdim', 'Cmaj7', 'Dm7', 'G/B', 'C/E', 'E7']
        words = ['hello', 'there', 'a', 'sing', 'well-known', 'hal-le-lu-jah', 'my', 'love', 'oh']
        for _ in range(300):
            line, col = '', 0
            while col < 30:
                chord = rng.choice(chords)
                gap = rng.choice([1, 1, 2, 3])
                line, col = line + chord + ' ' * gap, col + len(chord) + gap
            lyric = ' '.join(rng.choice(words) for _ in range(12))
            text = "{key: C}\n" + line.rstrip() + "\n" + lyric + "\n"
            shift = rng.choice([1, 2, 3, 4, 5, 6, -1, -2, -3, -5])
            up, back = there_and_back(text, shift)
            assert_aligned(text.split('\n', 1)[1], up.split('\n', 1)[1])
            assert back == text, (text, shift, up)


class TestConvertRoundTrip:
    def test_european_to_american_keeps_the_columns(self):
        # Pass 1: Rem Sol7 Do La7 at columns 0/8/16/24 moved left to 0/7/13/20.
        text = "Rem     Sol7    Do      La7\nquiero cantar contigo hoy amor\n"
        american = _PARSER.convert_to_american(text)
        assert american == "Dm      G7      C       A7\nquiero cantar contigo hoy amor\n"
        assert columns(american.split('\n')[0]) == [0, 8, 16, 24]
        assert _PARSER.convert_to_european(american) == text

    def test_american_to_european_stretches_and_comes_back(self):
        text = "C D E\nhello there\n"
        european = _PARSER.convert_to_european(text)
        assert_aligned(text, european)
        assert _PARSER.convert_to_american(european) == text

    def test_a_packed_line_over_a_lyric(self):
        text = "{key: Dm}\nDm G7 C A7 Dm\nhello there my friend\n"
        european = _PARSER.convert_to_european(text)
        assert european.split('\n')[0] == "{key: Rem}"
        assert_aligned(text.split('\n', 1)[1], european.split('\n', 1)[1])
        assert _PARSER.convert_to_american(european) == text

    def test_a_chord_just_past_the_lyric_end_stays_past_it(self):
        # Fuzz find: closing up after a shorter chord would have put Do*4's C
        # over the lyric, and the way back would then have stretched it.
        text = "Do\u266d(no3) DoM7*2    NC   sol\u266dmaj7 Do*4\nAmazing grace how sweet the sound\n"
        american = _PARSER.convert_to_american(text)
        assert american.split('\n')[1] == "Amazing grace how sweet the sound"
        assert _PARSER.convert_to_european(american) == text

    def test_a_directive_line_keeps_its_gaps(self):
        text = "{key: Bb }  {bpm: 90}\nBb\n"
        assert _PARSER.convert_to_european(text) == "{key: Sib }  {bpm: 90}\nSib\n"


class TestFill:
    def test_a_fill_goes_in_before_the_next_syllable(self):
        lyric = list("singer")
        insert_into_lyric(lyric, 0, 3, 2)
        assert ''.join(lyric) == f"sin{FILL} ger"

    def test_a_word_gap_takes_spaces(self):
        lyric = list("aa bb")
        insert_into_lyric(lyric, 0, 3, 2)
        assert ''.join(lyric) == "aa   bb"

    @pytest.mark.parametrize("lyric, lo, hi, count", [
        ("singer", 0, 3, 1), ("singer", 0, 3, 3), ("aa bb", 0, 3, 1), ("aa bb", 0, 3, 2),
        ("hello there", 2, 6, 1), ("a b", 0, 2, 2),
    ])
    def test_taking_undoes_inserting(self, lyric, lo, hi, count):
        chars = list(lyric)
        insert_into_lyric(chars, lo, hi, count)
        assert take_from_lyric(chars, lo, hi + count, count) == count
        assert ''.join(chars) == lyric

    def test_a_hyphen_is_not_a_fill(self):
        chars = list("hal-le")
        assert take_from_lyric(chars, 0, 4, 1) == 0
        assert ''.join(chars) == "hal-le"

    def test_partial_take_leaves_the_dot_last(self):
        chars = list(f"sin{FILL}  ger")
        assert take_from_lyric(chars, 0, 6, 2) == 2
        assert ''.join(chars) == f"sin{FILL}ger"

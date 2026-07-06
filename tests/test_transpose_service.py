"""Tests for the headless chord transposition service."""

import pytest

from services.transpose_service import (
    transpose_text,
    transpose_chord_token,
    transpose_key,
)
from models.notation import Notation


# --- basic American roots / slash chords ------------------------------------

class TestAmericanChords:
    def test_simple_root_up(self):
        assert transpose_chord_token("C", 2, "american") == "D"

    def test_root_down(self):
        assert transpose_chord_token("D", -2, "american") == "C"

    def test_quality_preserved(self):
        assert transpose_chord_token("Cmaj7", 2, "american") == "Dmaj7"
        assert transpose_chord_token("Am7", 2, "american") == "Bm7"

    def test_slash_chord_both_notes_shift(self):
        assert transpose_chord_token("C/G", 2, "american") == "D/A"

    def test_slash_with_quality(self):
        assert transpose_chord_token("Cmaj7/E", 2, "american") == "Dmaj7/F#"

    def test_half_diminished_example(self):
        assert transpose_chord_token("F#m7b5", 1, "american") == "Gm7b5"

    def test_parentheses_preserved(self):
        assert transpose_chord_token("Cadd9(no3)", 2, "american") == "Dadd9(no3)"

    def test_lowercase_minor_shorthand_case_preserved(self):
        assert transpose_chord_token("c", 2, "american") == "d"

    def test_in_text_wraps(self):
        text = "C  Am  F  G\n"
        assert transpose_text(text, 2, "american") == "D  Bm  G  A\n"


# --- enharmonic policy ------------------------------------------------------

class TestEnharmonic:
    def test_default_black_key_from_natural(self):
        # C +1 -> C# (default table)
        assert transpose_chord_token("C", 1, "american") == "C#"
        # G +1 -> Ab (default table, flat)
        assert transpose_chord_token("G", 1, "american") == "Ab"

    def test_default_table_all_black_keys(self):
        assert transpose_chord_token("C", 3, "american") == "Eb"   # pc3 default flat
        assert transpose_chord_token("C", 6, "american") == "F#"   # pc6 default sharp
        assert transpose_chord_token("C", 8, "american") == "Ab"   # pc8 default flat
        assert transpose_chord_token("C", 10, "american") == "Bb"  # pc10 default flat

    def test_sharp_style_preserved(self):
        # C# +2 -> D# (keep sharp), not Eb
        assert transpose_chord_token("C#", 2, "american") == "D#"

    def test_flat_style_preserved(self):
        # Db +2 -> Eb (flat kept, also the default)
        assert transpose_chord_token("Db", 2, "american") == "Eb"
        # Ab -> +2 -> Bb
        assert transpose_chord_token("Ab", 2, "american") == "Bb"

    def test_style_ignored_on_white_result(self):
        assert transpose_chord_token("Bb", 1, "american") == "B"   # 10+1 = 11 white
        assert transpose_chord_token("F#", 1, "american") == "G"   # 6+1 = 7 white
        assert transpose_chord_token("Bb", 2, "american") == "C"   # wrap to C

    def test_no_forbidden_spellings(self):
        # Sweep every root over +/-12 semitones and assert no double accidentals
        # or E#/Cb/Fb/B# ever appear.
        forbidden = {"E#", "Cb", "Fb", "B#"}
        roots = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#",
                 "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
        for r in roots:
            for s in range(-12, 13):
                out = transpose_chord_token(r, s, "american")
                assert "##" not in out and "bb" not in out
                assert out not in forbidden


# --- European notation ------------------------------------------------------

class TestEuropean:
    def test_major_up(self):
        assert transpose_chord_token("Do", 2, "european") == "Re"

    def test_minor_lowercase_preserved(self):
        # rem (D minor) +2 -> mim (E minor)
        assert transpose_chord_token("rem", 2, "european") == "mim"

    def test_accidental_european(self):
        assert transpose_chord_token("Fa", 1, "european") == "Fa#"
        assert transpose_chord_token("Sib", 1, "european") == "Si"

    def test_accented_source_normalized(self):
        # Dó (accented) +2 -> Re
        assert transpose_chord_token("Dó", 2, "european") == "Re"

    def test_european_slash(self):
        assert transpose_chord_token("Do/Sol", 2, "european") == "Re/La"

    def test_european_in_text(self):
        text = "Do  Re  Mi\n"
        assert transpose_text(text, 2, "european") == "Re  Mi  Fa#\n"


# --- what does NOT transpose ------------------------------------------------

class TestUntouched:
    def test_roman_numerals_untouched(self):
        text = "I  IV  V  vi\n"
        assert transpose_text(text, 2, "american") == text

    def test_nc_rest_untouched(self):
        text = "C  NC  G\n"
        assert transpose_text(text, 2, "american") == "D  NC  A\n"

    def test_comment_untouched(self):
        text = "C  Am  // play softly on C\n"
        out = transpose_text(text, 2, "american")
        assert "// play softly on C" in out
        assert out.startswith("D  Bm")

    def test_lyric_line_untouched(self):
        text = "C       G\nA week ago today\n"
        out = transpose_text(text, 2, "american")
        assert "A week ago today" in out


# --- key directives ---------------------------------------------------------

class TestKeyDirectives:
    def test_major_key_directive(self):
        text = "{key: C}\nI  IV  V\n"
        out = transpose_text(text, 2, "american")
        assert "{key: D}" in out

    def test_minor_key_directive_form_preserved(self):
        text = "{key: Am}\nvi  ii\n"
        out = transpose_text(text, 2, "american")
        assert "{key: Bm}" in out

    def test_key_directive_spacing_preserved(self):
        text = "{key:C}\n"
        out = transpose_text(text, 2, "american")
        assert out == "{key:D}\n"

    def test_key_directive_european(self):
        text = "{key: Do}\n"
        out = transpose_text(text, 2, "european")
        assert out == "{key: Re}\n"

    def test_transpose_key_helper(self):
        assert transpose_key("Am", 2, "american") == "Bm"
        assert transpose_key("C", 2, "american") == "D"
        assert transpose_key("Lam", 2, "european") == "Sim"

    def test_key_result_must_name_a_real_signature(self):
        # Style preservation would spell these Gbm / D# / G# / A# -- keys that
        # don't exist (8+ accidentals). The enharmonic twin is used instead.
        assert transpose_key("Ebm", 3, "american") == "F#m"
        assert transpose_key("Bbm", 8, "american") == "F#m"
        assert transpose_key("Ebm", 10, "american") == "C#m"   # not Dbm
        assert transpose_key("C#", 2, "american") == "Eb"      # not D#
        assert transpose_key("F#", 2, "american") == "Ab"      # not G#
        assert transpose_key("F#", 4, "american") == "Bb"      # not A#
        assert transpose_key("mibm", 3, "european") == "fa#m"

    def test_valid_style_preserved_keys_still_kept(self):
        # Both enharmonic keys exist here; the source style wins as before.
        assert transpose_key("Ebm", 2, "american") == "Fm"
        assert transpose_key("C#m", 2, "american") == "D#m"    # 6 sharps, real
        assert transpose_key("Db", 2, "american") == "Eb"
        assert transpose_key("F#", 1, "american") == "G"


# --- duration suffixes ------------------------------------------------------

class TestDuration:
    def test_duration_suffix_preserved(self):
        assert transpose_text("C*2  Am*4.5\n", 2, "american") == "D*2  Bm*4.5\n"


# --- region semantics -------------------------------------------------------

class TestRegion:
    def test_only_region_transposes(self):
        # "C  Am  F  G" -> transpose only "Am" (chars 3..5)
        text = "C  Am  F  G\n"
        # region covering just "Am"
        start = text.index("Am")
        region = (start, start + 2)
        out = transpose_text(text, 2, "american", region)
        assert out == "C  Bm  F  G\n"

    def test_chord_straddling_region_edge_transposes(self):
        # region ends in the middle of the second chord; intersecting chord
        # still transposes.
        text = "C  Am\n"
        start = text.index("Am")
        region = (0, start + 1)  # ends inside "Am"
        out = transpose_text(text, 2, "american", region)
        assert out == "D  Bm\n"

    def test_region_excludes_non_intersecting(self):
        text = "C  Am\n"
        # region only covers the first chord
        region = (0, 1)
        out = transpose_text(text, 2, "american", region)
        assert out == "D  Am\n"


# --- idempotence ------------------------------------------------------------

class TestIdempotence:
    def test_diatonic_round_trip(self):
        # Naturals landing on naturals round-trip exactly.
        text = "C  Am  F  G\nlyrics here\n"
        up = transpose_text(text, 5, "american")
        back = transpose_text(up, -5, "american")
        assert back == text

    def test_zero_is_noop(self):
        text = "C  Am\nwords\n"
        assert transpose_text(text, 0, "american") == text


# --- alignment: chord-above-syllable ---------------------------------------

class TestAlignment:
    @staticmethod
    def _token_cols(line):
        import re
        return [(m.start(), m.group()) for m in re.finditer(r'\S+', line)]

    def _char_under(self, lyric, col):
        return lyric[col] if 0 <= col < len(lyric) else ' '

    def _assert_alignment_preserved(self, chord_before, lyric_before, semitones, notation):
        """Every chord must sit above the SAME lyric character after transpose.

        Returns (transposed_chord_line, transposed_lyric_line).
        """
        src = chord_before + "\n" + lyric_before + "\n"
        out = transpose_text(src, semitones, notation)
        cb, lb, _ = out.split("\n")
        before = self._token_cols(chord_before)
        after = self._token_cols(cb)
        assert len(before) == len(after), (before, after)
        for (bc, _), (ac, _) in zip(before, after):
            assert self._char_under(lyric_before, bc) == self._char_under(lb, ac), (
                f"chord at src col {bc} -> {ac}: "
                f"{self._char_under(lyric_before, bc)!r} != {self._char_under(lb, ac)!r}\n"
                f"{cb!r}\n{lb!r}"
            )
        return cb, lb

    def test_shrink_pads_and_keeps_columns(self):
        # Sol (3) -> Fa (2): chord line shrinks; following chord column stable,
        # lyric untouched.
        cb, lb = self._assert_alignment_preserved(
            "Sol     Do", "singing there now", -2, "european"
        )
        assert lb == "singing there now"  # lyric untouched on shrink

    def test_grow_absorbs_space_no_lyric_change(self):
        # Fa -> Sol (+2) with >=2 trailing spaces: growth absorbed by eating one
        # space; next chord keeps its column and the lyric is untouched.
        cb, lb = self._assert_alignment_preserved(
            "Fa    Do", "here we go now now", 2, "european"
        )
        assert lb == "here we go now now"

    def test_grow_stretches_lyric_at_word_gap(self):
        # Fa -> Sol (+2) with a single space gap cannot absorb; a space is
        # inserted at the word gap in the lyric.
        cb, lb = self._assert_alignment_preserved("Fa Do", "aa bb", 2, "european")
        assert cb.startswith("Sol")
        assert len(lb) == len("aa bb") + 1
        assert "  " in lb  # widened gap

    def test_grow_stretches_lyric_with_hyphen_midword(self):
        # No word gap between the syllables -> a hyphen is inserted mid-word.
        cb, lb = self._assert_alignment_preserved("Fa La", "singer", 2, "european")
        assert cb.startswith("Sol")
        assert "-" in lb
        assert len(lb) == len("singer") + 1
        assert "sin-ger" in lb

    def test_no_paired_lyric_line_accepts_drift(self):
        # Chord line followed by a blank line -> no lyric to misalign; growth
        # just drifts, no crash.
        out = transpose_text("Fa Do\n\n", 2, "european")
        assert out.startswith("Sol")

    def test_multiple_growths_accumulate(self):
        # Fa -> Sol and Mi -> Fa# both grow (+1 char); Do -> Re is unchanged.
        # The lyric stretches so every chord keeps its syllable.
        cb, lb = self._assert_alignment_preserved(
            "Fa Do Mi", "aa bb cc", 2, "european"
        )
        # last chord's start column still carries "cc"
        last_col = self._token_cols(cb)[-1][0]
        assert lb[last_col:last_col + 2] == "cc"

    def test_american_single_char_growth_absorbs(self):
        # C -> C# (+1 char) with room absorbs; columns stable, lyric untouched.
        cb, lb = self._assert_alignment_preserved(
            "C     G", "hello there", 1, "american"
        )
        assert lb == "hello there"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Unit tests for chord note computation with key context and slash chords."""

import pytest
from chord.helper import ChordHelper
from models.chord_notes import ChordNotes


class TestAbsoluteChords:
    """Tests for absolute (non-roman numeral) chord computation."""

    def test_simple_major_chord(self, chord_helper):
        """Test simple major chord."""
        result = chord_helper.compute_chord_notes("C")

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        assert "C" in result.notes
        assert "E" in result.notes
        assert "G" in result.notes

    def test_minor_chord(self, chord_helper):
        """Test minor chord."""
        result = chord_helper.compute_chord_notes("Am")

        assert result is not None
        assert result.root == "A"
        assert result.bass_note == "A"
        assert "A" in result.notes
        assert "C" in result.notes
        assert "E" in result.notes

    def test_seventh_chord(self, chord_helper):
        """Test seventh chord."""
        result = chord_helper.compute_chord_notes("Cmaj7")

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        assert len(result.notes) == 4

    def test_slash_chord(self, chord_helper):
        """Test slash chord with different bass note."""
        result = chord_helper.compute_chord_notes("C/G")

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "G"
        assert "C" in result.notes
        assert "E" in result.notes
        assert "G" in result.notes

    def test_complex_slash_chord(self, chord_helper):
        """Test complex slash chord."""
        result = chord_helper.compute_chord_notes("Cmaj7/E")

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "E"
        assert len(result.notes) == 4


class TestRomanNumeralChords:
    """Tests for roman numeral chord resolution."""

    def test_major_I_in_C(self, chord_helper):
        """Test I chord in C major."""
        result = chord_helper.compute_chord_notes("I", key="C", is_relative=True)

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        assert "C" in result.notes
        assert "E" in result.notes
        assert "G" in result.notes

    def test_minor_i_in_C(self, chord_helper):
        """Test i chord (minor) in C."""
        result = chord_helper.compute_chord_notes("i", key="C", is_relative=True)

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        # Should be Cm
        assert "C" in result.notes
        assert "E-" in result.notes or "D#" in result.notes or "Eb" in result.notes  # Eb

    def test_V_in_C(self, chord_helper):
        """Test V chord in C major."""
        result = chord_helper.compute_chord_notes("V", key="C", is_relative=True)

        assert result is not None
        assert result.root == "G"
        assert result.bass_note == "G"
        assert "G" in result.notes

    def test_IV_in_G(self, chord_helper):
        """Test IV chord in G major."""
        result = chord_helper.compute_chord_notes("IV", key="G", is_relative=True)

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        assert "C" in result.notes

    def test_vi_in_C(self, chord_helper):
        """Test vi chord (minor) in C major."""
        result = chord_helper.compute_chord_notes("vi", key="C", is_relative=True)

        assert result is not None
        assert result.root == "A"
        assert result.bass_note == "A"
        # Should be Am
        assert "A" in result.notes

    def test_V7_in_C(self, chord_helper):
        """Test V7 chord in C major."""
        result = chord_helper.compute_chord_notes("V7", key="C", is_relative=True)

        assert result is not None
        assert result.root == "G"
        assert result.bass_note == "G"
        assert len(result.notes) == 4  # G7 has 4 notes

    def test_lowercase_seventh_is_minor(self, chord_helper):
        """A bare seventh on a lowercase numeral is minor, not dominant.

        ``ii7`` in C is Dm7 (D F A C), not the dominant D7 (D F# A C).
        """
        result = chord_helper.compute_chord_notes("ii7", key="C", is_relative=True)
        assert result is not None
        assert result.root == "D"
        assert set(result.notes) == {"D", "F", "A", "C"}

    def test_lowercase_extensions_stay_minor(self, chord_helper):
        """Extensions on lowercase numerals keep the minor third."""
        cases = {
            "ii9": {"D", "F", "A", "C", "E"},   # Dm9
            "ii6": {"D", "F", "A", "B"},        # Dm6
            "iiadd9": {"D", "F", "A", "E"},     # Dm(add9)
            "ii7b5": {"D", "F", "Ab", "C"},     # Dm7b5 (half-diminished)
            "vi7": {"A", "C", "E", "G"},        # Am7
        }
        for roman, expected in cases.items():
            result = chord_helper.compute_chord_notes(roman, key="C", is_relative=True)
            assert result is not None, roman
            assert set(result.notes) == expected, f"{roman}: {result.notes}"

    def test_uppercase_seventh_is_dominant(self, chord_helper):
        """An uppercase numeral with a seventh stays dominant.

        ``II7`` in C is a D dominant seventh (D F# A C), a secondary dominant.
        """
        result = chord_helper.compute_chord_notes("II7", key="C", is_relative=True)
        assert result is not None
        assert result.root == "D"
        assert set(result.notes) == {"D", "F#", "A", "C"}

    def test_lowercase_sus_and_maj7_not_forced_minor(self, chord_helper):
        """sus and maj7 qualities are not turned into minor chords."""
        # sus has no third, so it isn't rewritten into a (nonexistent) minor-sus
        sus = chord_helper.compute_chord_notes("iisus4", key="C", is_relative=True)
        assert sus is not None
        assert set(sus.notes) == {"D", "G", "A"}
        # maj7 keeps its major third, matching the absolute 'dmaj7' spelling
        maj7 = chord_helper.compute_chord_notes("iimaj7", key="C", is_relative=True)
        assert maj7 is not None
        assert set(maj7.notes) == {"D", "F#", "A", "C#"}

    def test_roman_different_keys(self, chord_helper):
        """Test same roman numeral in different keys."""
        # I in C = C
        result_c = chord_helper.compute_chord_notes("I", key="C", is_relative=True)
        assert result_c.root == "C"

        # I in G = G
        result_g = chord_helper.compute_chord_notes("I", key="G", is_relative=True)
        assert result_g.root == "G"

        # I in D = D
        result_d = chord_helper.compute_chord_notes("I", key="D", is_relative=True)
        assert result_d.root == "D"

    def test_all_scale_degrees(self, chord_helper):
        """Test all 7 scale degrees in C major."""
        expected_roots = ["C", "D", "E", "F", "G", "A", "B"]
        romans = ["I", "II", "III", "IV", "V", "VI", "VII"]

        for roman, expected_root in zip(romans, expected_roots):
            result = chord_helper.compute_chord_notes(roman, key="C", is_relative=True)
            assert result is not None
            assert result.root == expected_root


class TestRomanNumeralWithAccidentals:
    """Tests for roman numerals with flat and sharp accidentals."""

    def test_flat_III_in_C(self, chord_helper):
        """Test ♭III in C major (Eb major)."""
        result = chord_helper.compute_chord_notes("♭III", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Eb", "D#"]
        assert result.bass_note in ["Eb", "D#"]

    def test_flat_VII_in_C(self, chord_helper):
        """Test ♭VII in C major (Bb major)."""
        result = chord_helper.compute_chord_notes("♭VII", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Bb", "A#"]

    def test_flat_II_in_C(self, chord_helper):
        """Test ♭II in C major (Db major)."""
        result = chord_helper.compute_chord_notes("♭II", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Db", "C#"]

    def test_flat_VI_in_C(self, chord_helper):
        """Test ♭VI in C major (Ab major)."""
        result = chord_helper.compute_chord_notes("♭VI", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Ab", "G#"]

    def test_flat_V_in_C(self, chord_helper):
        """Test ♭V in C major (Gb major)."""
        result = chord_helper.compute_chord_notes("♭V", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Gb", "F#"]

    def test_ascii_flat_III(self, chord_helper):
        """Test bIII (ASCII flat) in C major."""
        result = chord_helper.compute_chord_notes("bIII", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Eb", "D#"]

    def test_ascii_flat_VII(self, chord_helper):
        """Test bVII (ASCII flat) in C major."""
        result = chord_helper.compute_chord_notes("bVII", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Bb", "A#"]

    def test_sharp_iv_in_C(self, chord_helper):
        """Test #iv in C major (F# minor)."""
        result = chord_helper.compute_chord_notes("#iv", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["F#", "Gb"]
        # Should be minor
        assert "A" in result.notes  # F# minor has F#, A, C#

    def test_sharp_IV_in_C(self, chord_helper):
        """Test #IV in C major (F# major)."""
        result = chord_helper.compute_chord_notes("#IV", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["F#", "Gb"]
        # Should be major
        assert "A#" in result.notes or "Bb" in result.notes  # F# major has F#, A#, C#


class TestRomanNumeralWithDiminished:
    """Tests for roman numerals with diminished symbols."""

    def test_viio_in_C(self, chord_helper):
        """Test viio (vii diminished) in C major (Bdim)."""
        result = chord_helper.compute_chord_notes("viio", key="C", is_relative=True)

        assert result is not None
        assert result.root == "B"
        # B diminished has B, D, F
        assert "B" in result.notes
        assert "D" in result.notes
        assert "F" in result.notes
        assert len(result.notes) == 3

    def test_viio7_in_C(self, chord_helper):
        """Test viio7 (vii diminished 7th) in C major (Bdim7)."""
        result = chord_helper.compute_chord_notes("viio7", key="C", is_relative=True)

        assert result is not None
        assert result.root == "B"
        # B diminished 7th has 4 notes
        assert len(result.notes) == 4

    def test_io_in_C(self, chord_helper):
        """Test io (i diminished) in C (Cdim)."""
        result = chord_helper.compute_chord_notes("io", key="C", is_relative=True)

        assert result is not None
        assert result.root == "C"
        # C diminished has C, Eb, Gb
        assert "C" in result.notes
        assert len(result.notes) == 3

    def test_iio_in_C(self, chord_helper):
        """Test iio (ii diminished) in C major (Ddim)."""
        result = chord_helper.compute_chord_notes("iio", key="C", is_relative=True)

        assert result is not None
        assert result.root == "D"
        assert len(result.notes) == 3

    def test_unicode_diminished_viio(self, chord_helper):
        """Test vii° (unicode diminished) in C major."""
        result = chord_helper.compute_chord_notes("vii°", key="C", is_relative=True)

        assert result is not None
        assert result.root == "B"
        assert len(result.notes) == 3

    def test_vo_in_C(self, chord_helper):
        """Test vo (v diminished) in C major (Gdim)."""
        result = chord_helper.compute_chord_notes("vo", key="C", is_relative=True)

        assert result is not None
        assert result.root == "G"
        assert len(result.notes) == 3


class TestRomanNumeralCombinations:
    """Tests for combinations of accidentals and diminished symbols."""

    def test_flat_IIIo_in_C(self, chord_helper):
        """Test ♭IIIo in C major (Ebdim)."""
        result = chord_helper.compute_chord_notes("♭IIIo", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Eb", "D#"]
        assert len(result.notes) == 3

    def test_sharp_ivo_in_C(self, chord_helper):
        """Test #ivo in C major (F#dim)."""
        result = chord_helper.compute_chord_notes("#ivo", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["F#", "Gb"]
        assert len(result.notes) == 3

    def test_flat_viio_in_C(self, chord_helper):
        """Test ♭viio in C major (Bbdim)."""
        result = chord_helper.compute_chord_notes("♭viio", key="C", is_relative=True)

        assert result is not None
        assert result.root in ["Bb", "A#"]
        assert len(result.notes) == 3


class TestModalMixtureChords:
    """Tests for modal mixture (borrowed chords) from different modes."""

    def test_dorian_chords_in_C(self, chord_helper):
        """Test Dorian mode chords: i ii ♭III IV v vio ♭VII."""
        # i in C Dorian = Cm
        result_i = chord_helper.compute_chord_notes("i", key="C", is_relative=True)
        assert result_i is not None
        assert result_i.root == "C"

        # ♭III in C Dorian = Eb
        result_bIII = chord_helper.compute_chord_notes("♭III", key="C", is_relative=True)
        assert result_bIII is not None
        assert result_bIII.root in ["Eb", "D#"]

        # ♭VII in C Dorian = Bb
        result_bVII = chord_helper.compute_chord_notes("♭VII", key="C", is_relative=True)
        assert result_bVII is not None
        assert result_bVII.root in ["Bb", "A#"]

    def test_phrygian_chords_in_C(self, chord_helper):
        """Test Phrygian mode chords: i ♭II ♭III iv vo ♭VI ♭vii."""
        # ♭II in C Phrygian = Db
        result_bII = chord_helper.compute_chord_notes("♭II", key="C", is_relative=True)
        assert result_bII is not None
        assert result_bII.root in ["Db", "C#"]

        # vo in C Phrygian = Gdim
        result_vo = chord_helper.compute_chord_notes("vo", key="C", is_relative=True)
        assert result_vo is not None
        assert result_vo.root == "G"
        assert len(result_vo.notes) == 3

        # ♭VI in C Phrygian = Ab
        result_bVI = chord_helper.compute_chord_notes("♭VI", key="C", is_relative=True)
        assert result_bVI is not None
        assert result_bVI.root in ["Ab", "G#"]

    def test_lydian_chords_in_C(self, chord_helper):
        """Test Lydian mode chords: I II iii #ivo V vi vii."""
        # #ivo in C Lydian = F#dim
        result_sharpivo = chord_helper.compute_chord_notes("#ivo", key="C", is_relative=True)
        assert result_sharpivo is not None
        assert result_sharpivo.root in ["F#", "Gb"]
        assert len(result_sharpivo.notes) == 3

    def test_mixolydian_chords_in_C(self, chord_helper):
        """Test Mixolydian mode chords: I ii iiio IV v vi ♭VII."""
        # iiio in C Mixolydian = Edim
        result_iiio = chord_helper.compute_chord_notes("iiio", key="C", is_relative=True)
        assert result_iiio is not None
        assert result_iiio.root == "E"
        assert len(result_iiio.notes) == 3

    def test_locrian_chords_in_C(self, chord_helper):
        """Test Locrian mode chords: io ♭II ♭iii iv ♭V ♭VI ♭vii."""
        # io in C Locrian = Cdim
        result_io = chord_helper.compute_chord_notes("io", key="C", is_relative=True)
        assert result_io is not None
        assert result_io.root == "C"
        assert len(result_io.notes) == 3

        # ♭V in C Locrian = Gb
        result_bV = chord_helper.compute_chord_notes("♭V", key="C", is_relative=True)
        assert result_bV is not None
        assert result_bV.root in ["Gb", "F#"]


class TestRomanNumeralSlashChords:
    """Tests for roman numeral slash chords."""

    def test_I_over_V(self, chord_helper):
        """Test I/V in C major."""
        result = chord_helper.compute_chord_notes("I/V", key="C", is_relative=True)

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "G"
        assert "C" in result.notes

    def test_IV_over_I(self, chord_helper):
        """Test IV/I in C major."""
        result = chord_helper.compute_chord_notes("IV/I", key="C", is_relative=True)

        assert result is not None
        assert result.root == "F"
        assert result.bass_note == "C"

    def test_vi_over_IV(self, chord_helper):
        """Test vi/IV in C major."""
        result = chord_helper.compute_chord_notes("vi/IV", key="C", is_relative=True)

        assert result is not None
        assert result.root == "A"
        assert result.bass_note == "F"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_chord(self, chord_helper):
        """Test invalid chord name."""
        result = chord_helper.compute_chord_notes("XYZ")

        assert result is None

    def test_relative_without_key(self, chord_helper):
        """Test roman numeral without providing key."""
        result = chord_helper.compute_chord_notes("I", is_relative=True)

        assert result is None

    def test_empty_chord_name(self, chord_helper):
        """Test empty chord name."""
        result = chord_helper.compute_chord_notes("")

        assert result is None

    def test_sharp_accidentals(self, chord_helper):
        """Test chords with sharp accidentals."""
        result = chord_helper.compute_chord_notes("C#")

        assert result is not None
        assert result.root == "C#"
        assert result.bass_note == "C#"

    def test_flat_accidentals(self, chord_helper):
        """Test chords with flat accidentals."""
        result = chord_helper.compute_chord_notes("Bb")

        assert result is not None
        assert result.root == "Bb" or result.root == "B-"  # Both notations valid

    def test_complex_quality_with_slash(self, chord_helper):
        """Test complex chord quality with slash."""
        result = chord_helper.compute_chord_notes("Dm7b5/F")

        assert result is not None
        assert result.root == "D"
        assert result.bass_note == "F"
        assert len(result.notes) == 4


class TestChordNotesDataClass:
    """Tests for ChordNotes dataclass."""

    def test_chordnotes_structure(self, chord_helper):
        """Test that ChordNotes has correct structure."""
        result = chord_helper.compute_chord_notes("C/G")

        assert hasattr(result, 'notes')
        assert hasattr(result, 'bass_note')
        assert hasattr(result, 'root')
        assert isinstance(result.notes, list)
        assert isinstance(result.bass_note, str)
        assert isinstance(result.root, str)

    def test_bass_equals_root_when_no_slash(self, chord_helper):
        """Test that bass_note equals root when no slash chord."""
        result = chord_helper.compute_chord_notes("Am")

        assert result.bass_note == result.root

    def test_bass_differs_from_root_when_slash(self, chord_helper):
        """Test that bass_note differs from root for slash chords."""
        result = chord_helper.compute_chord_notes("C/G")

        assert result.bass_note != result.root
        assert result.bass_note == "G"
        assert result.root == "C"


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_song_progression_in_C(self, chord_helper):
        """Test a complete chord progression in C major."""
        progression = ["I", "vi", "IV", "V"]
        expected_roots = ["C", "A", "F", "G"]

        for roman, expected_root in zip(progression, expected_roots):
            result = chord_helper.compute_chord_notes(roman, key="C", is_relative=True)
            assert result is not None
            assert result.root == expected_root

    def test_song_progression_in_G_with_slash(self, chord_helper):
        """Test chord progression in G with slash chords."""
        # I - IV - I/V - V
        chords = ["I", "IV", "I/V", "V"]
        expected = [
            ("G", "G"),
            ("C", "C"),
            ("G", "D"),
            ("D", "D"),
        ]

        for chord, (exp_root, exp_bass) in zip(chords, expected):
            result = chord_helper.compute_chord_notes(chord, key="G", is_relative=True)
            assert result is not None
            assert result.root == exp_root
            assert result.bass_note == exp_bass

    def test_mixed_absolute_and_relative(self, chord_helper):
        """Test both absolute and relative chords."""
        # Absolute chord
        abs_result = chord_helper.compute_chord_notes("C")
        assert abs_result.root == "C"

        # Relative chord
        rel_result = chord_helper.compute_chord_notes("I", key="C", is_relative=True)
        assert rel_result.root == "C"

        # Both should give same root
        assert abs_result.root == rel_result.root

    def test_transpose_via_key_change(self, chord_helper):
        """Test transposing progression by changing key."""
        # I-IV-V in C
        prog_c_I = chord_helper.compute_chord_notes("I", key="C", is_relative=True)
        prog_c_IV = chord_helper.compute_chord_notes("IV", key="C", is_relative=True)
        prog_c_V = chord_helper.compute_chord_notes("V", key="C", is_relative=True)

        assert prog_c_I.root == "C"
        assert prog_c_IV.root == "F"
        assert prog_c_V.root == "G"

        # Same progression in G
        prog_g_I = chord_helper.compute_chord_notes("I", key="G", is_relative=True)
        prog_g_IV = chord_helper.compute_chord_notes("IV", key="G", is_relative=True)
        prog_g_V = chord_helper.compute_chord_notes("V", key="G", is_relative=True)

        assert prog_g_I.root == "G"
        assert prog_g_IV.root == "C"
        assert prog_g_V.root == "D"


class TestParenthesesNotation:
    """Tests for parentheses-based chord notation."""

    def test_maj7_with_ninth(self, chord_helper):
        """Test Cmaj7(9) becomes Cmaj9."""
        result = chord_helper.compute_chord_notes("Cmaj7(9)")

        assert result is not None
        assert result.root == "C"
        # Cmaj9 has C, E, G, B, D
        assert len(result.notes) == 5

    def test_dominant_seventh_flat_nine(self, chord_helper):
        """Test C7(b9) becomes C7b9."""
        result = chord_helper.compute_chord_notes("C7(b9)")

        assert result is not None
        assert result.root == "C"
        # C7b9 has 5 notes: C, E, G, Bb, Db
        assert len(result.notes) == 5

    def test_minor_seventh_eleventh(self, chord_helper):
        """Test Dm7(11) becomes Dm11."""
        result = chord_helper.compute_chord_notes("Dm7(11)")

        assert result is not None
        assert result.root == "D"
        # Dm11 should have at least 4 notes
        assert len(result.notes) >= 4

    def test_major_with_added_ninth(self, chord_helper):
        """Test C(9) becomes Cadd9 (no 7th)."""
        result = chord_helper.compute_chord_notes("C(9)")

        assert result is not None
        assert result.root == "C"
        # Cadd9 has C, E, G, D (4 notes, no 7th)
        assert len(result.notes) == 4
        assert "B" not in result.notes  # Should NOT have the 7th

    def test_minor_with_added_ninth(self, chord_helper):
        """Test Dm(9) becomes Dmadd9 (no 7th)."""
        result = chord_helper.compute_chord_notes("Dm(9)")

        assert result is not None
        assert result.root == "D"
        # Dmadd9 has D, F, A, E (4 notes, no 7th)
        assert len(result.notes) == 4

    def test_parentheses_with_sharp(self, chord_helper):
        """Test C7(#9) becomes C7#9."""
        result = chord_helper.compute_chord_notes("C7(#9)")

        assert result is not None
        assert result.root == "C"
        assert len(result.notes) >= 4

    def test_minor_major_seventh_parenthesised(self, chord_helper):
        """Cm(maj7) is a minor-major seventh (= CmM7), not a bare minor triad."""
        result = chord_helper.compute_chord_notes("Cm(maj7)")

        assert result is not None
        assert result.root == "C"
        assert set(result.notes) == {"C", "Eb", "G", "B"}

    def test_major_seventh_parenthesised(self, chord_helper):
        """C(maj7) adds a major seventh to the major triad: = Cmaj7."""
        result = chord_helper.compute_chord_notes("C(maj7)")

        assert result is not None
        assert result.root == "C"
        assert set(result.notes) == {"C", "E", "G", "B"}


class TestSymbolNotation:
    """Tests for symbol-based chord notation (°, ø, +)."""

    def test_diminished_symbol(self, chord_helper):
        """Test diminished symbol: C° becomes Cdim."""
        result = chord_helper.compute_chord_notes("C°")

        assert result is not None
        assert result.root == "C"
        # Diminished triad: C, Eb, Gb
        assert len(result.notes) == 3

    def test_diminished_seventh_symbol(self, chord_helper):
        """Test diminished seventh: C°7 becomes Cdim7."""
        result = chord_helper.compute_chord_notes("C°7")

        assert result is not None
        assert result.root == "C"
        # Diminished seventh: 4 notes
        assert len(result.notes) == 4

    def test_half_diminished_symbol(self, chord_helper):
        """Test half-diminished: Cø becomes Cm7b5."""
        result = chord_helper.compute_chord_notes("Cø")

        assert result is not None
        assert result.root == "C"
        # Half-diminished = m7b5: 4 notes
        assert len(result.notes) == 4

    def test_half_diminished_seventh_symbol(self, chord_helper):
        """Test half-diminished seventh: Cø7 becomes Cm7b5."""
        result = chord_helper.compute_chord_notes("Cø7")

        assert result is not None
        assert result.root == "C"
        assert len(result.notes) == 4

    def test_augmented_symbol(self, chord_helper):
        """Test augmented: C+ becomes Caug."""
        result = chord_helper.compute_chord_notes("C+")

        assert result is not None
        assert result.root == "C"
        # Augmented triad: C, E, G#
        assert len(result.notes) == 3

    def test_symbols_with_accidentals(self, chord_helper):
        """Test symbols work with sharps/flats: F#° becomes F#dim."""
        result = chord_helper.compute_chord_notes("F#°")

        assert result is not None
        assert result.root in ["F#", "Gb"]
        assert len(result.notes) == 3


class TestLowercaseNotation:
    """Tests for lowercase chord notation (c = Cm, d = Dm)."""

    def test_lowercase_major_becomes_minor(self, chord_helper):
        """Test that lowercase 'c' becomes 'Cm' (C minor)."""
        result = chord_helper.compute_chord_notes("c")

        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "C"
        # C minor has C, Eb, G
        assert "C" in result.notes
        assert any(note in ["Eb", "D#"] for note in result.notes)  # Eb or D#
        assert "G" in result.notes

    def test_lowercase_with_seventh(self, chord_helper):
        """Test lowercase with seventh: 'd7' becomes 'Dm7'."""
        result = chord_helper.compute_chord_notes("d7")

        assert result is not None
        assert result.root == "D"
        # D minor 7 has D, F, A, C
        assert "D" in result.notes
        assert "F" in result.notes
        assert "A" in result.notes
        assert "C" in result.notes

    def test_lowercase_with_sharp(self, chord_helper):
        """Test lowercase with sharp: 'c#' becomes 'C#m'."""
        result = chord_helper.compute_chord_notes("c#")

        assert result is not None
        assert result.root in ["C#", "Db"]  # Either enharmonic spelling
        # C# minor has C#, E, G#
        assert len(result.notes) == 3

    def test_lowercase_natural_notes_only(self, chord_helper):
        """Test that lowercase works for natural notes: 'a', 'b', 'e', etc."""
        # Test lowercase b (B minor)
        result_b = chord_helper.compute_chord_notes("b")
        assert result_b is not None
        assert result_b.root == "B"
        assert len(result_b.notes) == 3  # B minor: B, D, F#

        # Test lowercase a (A minor)
        result_a = chord_helper.compute_chord_notes("a")
        assert result_a is not None
        assert result_a.root == "A"

    def test_lowercase_already_has_minor(self, chord_helper):
        """Test lowercase that already has 'm': 'cm7' becomes 'Cm7'."""
        result = chord_helper.compute_chord_notes("cm7")

        assert result is not None
        assert result.root == "C"
        # Should be C minor 7, not double minor
        assert len(result.notes) == 4

    def test_uppercase_stays_major(self, chord_helper):
        """Test that uppercase stays major: 'C' is C major, not modified."""
        result = chord_helper.compute_chord_notes("C")

        assert result is not None
        assert result.root == "C"
        # C major has C, E, G (not Eb)
        assert "C" in result.notes
        assert "E" in result.notes
        assert "G" in result.notes
        assert "Eb" not in result.notes and "D#" not in result.notes


class TestEuropeanNotationExtensions:
    """Tests for European notation with special extensions."""

    def test_european_lowercase_minor(self, chord_helper):
        """Test lowercase European: 'do' becomes 'Cm' (Do minor)."""
        from chord.converter import NotationConverter

        # First convert European to American, then test
        american = NotationConverter.chord_european_to_american("do")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "C"
        # C minor has C, Eb, G
        assert "C" in result.notes
        assert any(note in ["Eb", "D#"] for note in result.notes)

    def test_european_with_symbols(self, chord_helper):
        """Test European with symbols: 'Do°' becomes 'Cdim'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("Do°")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "C"
        assert len(result.notes) == 3  # Diminished triad

    def test_european_with_parentheses(self, chord_helper):
        """Test European with parentheses: 'Domaj7(9)' becomes 'Cmaj9'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("Domaj7(9)")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "C"
        assert len(result.notes) == 5  # Cmaj9 has 5 notes

    def test_european_half_diminished(self, chord_helper):
        """Test European half-diminished: 'Solø' becomes 'Gm7b5'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("Solø")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "G"
        assert len(result.notes) == 4  # Half-diminished has 4 notes

    def test_european_augmented_with_extension(self, chord_helper):
        """Test European augmented: 'Re+' becomes 'Daug'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("Re+")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "D"
        assert len(result.notes) == 3  # Augmented triad

    def test_european_add_chord(self, chord_helper):
        """Test European add chord: 'Mi(9)' becomes 'Eadd9'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("Mi(9)")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "E"
        assert len(result.notes) == 4  # Add9 has 4 notes (no 7th)

    def test_european_lowercase_with_seventh(self, chord_helper):
        """Test European lowercase with seventh: 'rem7' becomes 'Dm7'."""
        from chord.converter import NotationConverter

        american = NotationConverter.chord_european_to_american("rem7")
        result = chord_helper.compute_chord_notes(american)

        assert result is not None
        assert result.root == "D"
        assert len(result.notes) == 4  # Dm7 has 4 notes

    def test_european_with_accents(self, chord_helper):
        """Test European notation with accents: 'Dó', 'Ré', 'Fá', 'Lá' are normalized."""
        from chord.converter import NotationConverter

        # Test accented Do (Dó -> Do -> C)
        american_do = NotationConverter.chord_european_to_american("Dó")
        result_do = chord_helper.compute_chord_notes(american_do)
        assert result_do is not None
        assert result_do.root == "C"

        # Test accented Re with chord quality (Rém -> Rem -> Dm)
        american_re = NotationConverter.chord_european_to_american("Rém")
        result_re = chord_helper.compute_chord_notes(american_re)
        assert result_re is not None
        assert result_re.root == "D"
        assert "F" in result_re.notes  # D minor has D, F, A

        # Test accented Fa with seventh (Fá7 -> Fa7 -> F7)
        american_fa = NotationConverter.chord_european_to_american("Fá7")
        result_fa = chord_helper.compute_chord_notes(american_fa)
        assert result_fa is not None
        assert result_fa.root == "F"
        assert len(result_fa.notes) == 4  # F7 has 4 notes

        # Test accented La major (Lá -> La -> A)
        american_la = NotationConverter.chord_european_to_american("Lá")
        result_la = chord_helper.compute_chord_notes(american_la)
        assert result_la is not None
        assert result_la.root == "A"
        assert "C#" in result_la.notes or "Db" in result_la.notes  # A major has A, C#, E


class TestEnharmonicNormalization:
    """Tests for enharmonic equivalent normalization."""

    def test_cb_to_b(self, chord_helper):
        """Test Cb normalized to B."""
        result = chord_helper.compute_chord_notes("Cb")
        assert result is not None
        assert result.root == "B"

    def test_esharp_to_f(self, chord_helper):
        """Test E# normalized to F."""
        result = chord_helper.compute_chord_notes("E#")
        assert result is not None
        assert result.root == "F"

    def test_fb_to_e(self, chord_helper):
        """Test Fb normalized to E."""
        result = chord_helper.compute_chord_notes("Fb")
        assert result is not None
        assert result.root == "E"

    def test_bsharp_to_c(self, chord_helper):
        """Test B# normalized to C."""
        result = chord_helper.compute_chord_notes("B#")
        assert result is not None
        assert result.root == "C"

    def test_enharmonic_with_quality(self, chord_helper):
        """Test enharmonic normalization preserves chord quality: Cbmaj7 → Bmaj7."""
        result = chord_helper.compute_chord_notes("Cbmaj7")
        assert result is not None
        assert result.root == "B"
        assert len(result.notes) == 4


class TestUnicodeSymbols:
    """Tests for unicode musical symbols normalization."""

    def test_unicode_flat(self, chord_helper):
        """Test unicode flat symbol: C♭ becomes Cb, then normalized to B."""
        result = chord_helper.compute_chord_notes("C♭")
        assert result is not None
        assert result.root == "B"  # Cb is normalized to enharmonic B

    def test_unicode_sharp(self, chord_helper):
        """Test unicode sharp symbol: C♯ becomes C#."""
        result = chord_helper.compute_chord_notes("C♯")
        assert result is not None
        assert result.root == "C#"

    def test_unicode_delta_major7(self, chord_helper):
        """Test unicode delta for major 7th: CΔ7 becomes Cmaj7."""
        result = chord_helper.compute_chord_notes("CΔ7")
        assert result is not None
        assert len(result.notes) == 4
        assert result.root == "C"

    def test_unicode_delta_bare_is_major7(self, chord_helper):
        """A bare triangle means major 7th, not a plain major triad: CΔ = Cmaj7."""
        result = chord_helper.compute_chord_notes("CΔ")
        assert result is not None
        assert result.root == "C"
        assert set(result.notes) == {"C", "E", "G", "B"}

    def test_unicode_delta_with_extension(self, chord_helper):
        """A number after the triangle carries the extension: CΔ9 = Cmaj9."""
        result = chord_helper.compute_chord_notes("CΔ9")
        assert result is not None
        assert set(result.notes) == {"C", "E", "G", "B", "D"}

    def test_unicode_delta_minor_major7(self, chord_helper):
        """A triangle on a minor chord is a minor-major seventh: CmΔ = CmM7."""
        result = chord_helper.compute_chord_notes("CmΔ")
        assert result is not None
        assert set(result.notes) == {"C", "Eb", "G", "B"}

    def test_unicode_flat_in_alteration(self, chord_helper):
        """Test unicode flat in chord alteration: C7♭5 becomes C7b5."""
        result = chord_helper.compute_chord_notes("C7♭5")
        assert result is not None
        assert result.root == "C"
        assert len(result.notes) == 4

    def test_unicode_combined(self, chord_helper):
        """Test multiple unicode symbols: Cm7♭5 becomes Cm7b5 (half-diminished)."""
        result = chord_helper.compute_chord_notes("Cm7♭5")
        assert result is not None
        assert len(result.notes) == 4


class TestAlternativeQualities:
    """Tests for alternative chord quality notations."""

    def test_minus_for_minor(self, chord_helper):
        """Test minus sign for minor: C- becomes Cm."""
        result = chord_helper.compute_chord_notes("C-")
        assert result is not None
        assert "Eb" in result.notes or "D#" in result.notes

    def test_min_for_minor(self, chord_helper):
        """Test 'min' for minor: Cmin7 becomes Cm7."""
        result = chord_helper.compute_chord_notes("Cmin7")
        assert result is not None
        assert len(result.notes) == 4

    def test_mi_for_minor(self, chord_helper):
        """Test 'mi' for minor: Cmi becomes Cm."""
        result = chord_helper.compute_chord_notes("Cmi")
        assert result is not None
        assert "Eb" in result.notes or "D#" in result.notes

    def test_M7_for_major7(self, chord_helper):
        """Test M7 for major 7th: CM7 becomes Cmaj7."""
        result = chord_helper.compute_chord_notes("CM7")
        assert result is not None
        assert len(result.notes) == 4
        assert "B" in result.notes  # Natural 7th

    def test_dom7_for_dominant(self, chord_helper):
        """Test dom7 for dominant 7th: Cdom7 becomes C7."""
        result = chord_helper.compute_chord_notes("Cdom7")
        assert result is not None
        assert len(result.notes) == 4
        assert "Bb" in result.notes or "A#" in result.notes

    def test_alt_for_altered(self, chord_helper):
        """Test alt for altered dominant: Calt becomes C7b9b13."""
        result = chord_helper.compute_chord_notes("Calt")
        assert result is not None
        assert len(result.notes) >= 5  # Altered chord has many notes

    def test_7alt_for_altered(self, chord_helper):
        """Test 7alt for altered dominant: C7alt becomes C7b9b13."""
        result = chord_helper.compute_chord_notes("C7alt")
        assert result is not None
        assert len(result.notes) >= 5


class TestOmitNotationExtended:
    """Tests for omit notation with complex chords."""

    def test_dominant_no_third(self, chord_helper):
        """Test omitting 3rd from dominant 7th: C7(no3) becomes C7omit3."""
        result = chord_helper.compute_chord_notes("C7(no3)")
        assert result is not None
        # Should have root, 5th, and 7th (no 3rd)
        assert "C" in result.notes
        assert "G" in result.notes
        assert "Bb" in result.notes or "A#" in result.notes
        assert "E" not in result.notes  # 3rd should be omitted

    def test_major_no_fifth(self, chord_helper):
        """Test omitting 5th: C(no5) becomes Comit5."""
        result = chord_helper.compute_chord_notes("C(no5)")
        assert result is not None
        assert "C" in result.notes
        assert "E" in result.notes
        assert "G" not in result.notes  # 5th should be omitted

    def test_add_with_parentheses(self, chord_helper):
        """Test add notation in parentheses: C(add9) becomes Cadd9."""
        result = chord_helper.compute_chord_notes("C(add9)")
        assert result is not None
        assert len(result.notes) == 4
        assert "D" in result.notes  # 9th = D

    def test_omit_vs_no_synonyms(self, chord_helper):
        """Test that (omit3) and (no3) are equivalent."""
        result_omit = chord_helper.compute_chord_notes("C(omit3)")
        result_no = chord_helper.compute_chord_notes("C(no3)")
        assert result_omit is not None
        assert result_no is not None
        assert set(result_omit.notes) == set(result_no.notes)


class TestParenthesesWithSevenths:
    """Tests for parentheses notation with 7th chords."""

    def test_dominant_with_ninth(self, chord_helper):
        """Test C7(9) becomes C9 (full ninth chord with 7th)."""
        result = chord_helper.compute_chord_notes("C7(9)")
        assert result is not None
        assert len(result.notes) == 5  # C9 has 5 notes
        assert "Bb" in result.notes or "A#" in result.notes  # Has the 7th
        assert "D" in result.notes  # Has the 9th

    def test_dominant_with_altered_ninth(self, chord_helper):
        """Test C7(b9) becomes C7b9."""
        result = chord_helper.compute_chord_notes("C7(b9)")
        assert result is not None
        assert "Bb" in result.notes or "A#" in result.notes
        assert "Db" in result.notes or "C#" in result.notes  # Flat 9th

    def test_minor_seventh_with_eleventh(self, chord_helper):
        """Test Cm7(11) becomes Cm11."""
        result = chord_helper.compute_chord_notes("Cm7(11)")
        assert result is not None
        assert len(result.notes) >= 5


class TestJazzVoicingConventions:
    """Tests for jazz theory voicing conventions."""

    def test_dominant_11th_omits_third(self, chord_helper):
        """Test C11 omits the 3rd (E) to avoid clash with 11th (F)."""
        result = chord_helper.compute_chord_notes("C11")
        assert result is not None
        # Should have: C (root), G (5th), Bb (b7), D (9), F (11)
        # Should NOT have: E (3rd) - clashes with F (11th)
        assert "C" in result.notes
        assert "G" in result.notes
        assert ("Bb" in result.notes or "A#" in result.notes)
        assert "D" in result.notes
        assert "F" in result.notes
        # Most importantly: NO 3rd
        assert "E" not in result.notes

    def test_minor_11th_includes_third(self, chord_helper):
        """Test Cm11 includes b3rd (Eb) - no clash with 11th."""
        result = chord_helper.compute_chord_notes("Cm11")
        assert result is not None
        # Should have: C, Eb (b3), G, Bb, D, F
        # Eb and F don't clash (whole step apart)
        assert "C" in result.notes
        assert ("Eb" in result.notes or "D#" in result.notes)  # b3rd is OK
        assert "F" in result.notes

    def test_dominant_13th_omits_11th(self, chord_helper):
        """Test C13 omits 11th (F) - practical voicing."""
        result = chord_helper.compute_chord_notes("C13")
        assert result is not None
        # Should have: C, E, G, Bb, D (9), A (13)
        # Should NOT have: F (11) - clashes a semitone above the major 3rd
        assert "C" in result.notes
        assert "E" in result.notes  # 3rd included
        assert "A" in result.notes  # 13th
        assert "F" not in result.notes  # 11th omitted for practical voicing

    def test_minor_13th_omits_11th(self, chord_helper):
        """Test Cm13 omits 11th (F) - practical voicing."""
        result = chord_helper.compute_chord_notes("Cm13")
        assert result is not None
        # Should have: C, Eb (b3), G, Bb (b7), D (9), A (13)
        assert "C" in result.notes
        assert ("Eb" in result.notes or "D#" in result.notes)  # b3rd
        assert "A" in result.notes  # 13th
        assert "F" not in result.notes  # 11th omitted

    def test_major_13th_omits_11th(self, chord_helper):
        """Test Cmaj13 omits 11th (F) - practical voicing."""
        result = chord_helper.compute_chord_notes("Cmaj13")
        assert result is not None
        # Should have: C, E, G, B (maj7), D (9), A (13)
        assert "C" in result.notes
        assert "E" in result.notes  # 3rd included
        assert "B" in result.notes  # maj7th
        assert "A" in result.notes  # 13th
        assert "F" not in result.notes  # 11th omitted

    def test_major_11th_omits_third(self, chord_helper):
        """Test Cmaj11 omits the 3rd (E) to avoid clash with 11th (F)."""
        result = chord_helper.compute_chord_notes("Cmaj11")
        assert result is not None
        # Should have: C (root), G (5th), B (maj7), D (9), F (11)
        # Should NOT have: E (3rd) - clashes a semitone under F (11th)
        assert "C" in result.notes
        assert "G" in result.notes
        assert "B" in result.notes  # maj7th
        assert "D" in result.notes  # 9th
        assert "F" in result.notes  # 11th
        assert "E" not in result.notes  # 3rd dropped, like the dominant 11th


class TestSeventhChordExtensions:
    """Tests for 7th chord types with parentheses extensions."""

    def test_half_diminished_with_ninth(self, chord_helper):
        """Test Cø7(9) or Cm7b5(9) becomes Cm9b5."""
        # Test symbol notation
        result1 = chord_helper.compute_chord_notes("Cø7(9)")
        assert result1 is not None

        # Test text notation
        result2 = chord_helper.compute_chord_notes("Cm7b5(9)")
        assert result2 is not None

    def test_minor_major_seventh_with_ninth(self, chord_helper):
        """Test CmM7(9) becomes CmM9."""
        result = chord_helper.compute_chord_notes("CmM7(9)")
        assert result is not None
        # Should be minor-major 9th
        assert result.root == "C"

    def test_diminished_seventh_with_ninth(self, chord_helper):
        """Test Cdim7(9) works (rare but valid)."""
        result = chord_helper.compute_chord_notes("Cdim7(9)")
        assert result is not None
        assert result.root == "C"

    def test_augmented_seventh_with_ninth(self, chord_helper):
        """Test Caug7(9) works (rare but valid)."""
        # This might not be supported by pychord, but should at least not crash
        result = chord_helper.compute_chord_notes("Caug7(9)")
        # Just verify it doesn't crash - result may be None if not supported


class TestCuratedParenthesisedVoicings:
    """Parenthesised voicings that live in QUALITY_INTERVALS with the
    parentheses intact. The libraries can't parse these, so the parenthesis
    normalizer must leave them alone and let the table resolve them instead of
    rewriting them into a symbol that erases or corrupts the chord.
    """

    def test_major_seven_sharp_five_add_nine(self, chord_helper):
        """Cmaj7#5(9) resolves to C E G# B D (not erased to None)."""
        result = chord_helper.compute_chord_notes("Cmaj7#5(9)")
        assert result is not None
        assert result.root == "C"
        assert "C" in result.notes
        assert "E" in result.notes             # major 3rd
        assert ("G#" in result.notes or "Ab" in result.notes)  # #5
        assert "B" in result.notes             # maj7
        assert "D" in result.notes             # 9

    def test_diminished_add_major_nine(self, chord_helper):
        """Cdim(maj9) keeps the maj9 instead of silently dropping it."""
        result = chord_helper.compute_chord_notes("Cdim(maj9)")
        assert result is not None
        assert result.root == "C"
        assert "C" in result.notes
        assert ("Eb" in result.notes or "D#" in result.notes)  # b3
        assert ("Gb" in result.notes or "F#" in result.notes)  # b5
        assert "B" in result.notes             # maj7
        assert "D" in result.notes             # 9

    def test_half_diminished_flat_nine(self, chord_helper):
        """Cm7b5(b9) keeps the b7 instead of collapsing to a wrong chord."""
        result = chord_helper.compute_chord_notes("Cm7b5(b9)")
        assert result is not None
        assert result.root == "C"
        assert "C" in result.notes
        assert ("Eb" in result.notes or "D#" in result.notes)  # b3
        assert ("Gb" in result.notes or "F#" in result.notes)  # b5
        assert ("Bb" in result.notes or "A#" in result.notes)  # b7 - must survive
        assert ("Db" in result.notes or "C#" in result.notes)  # b9

    def test_curated_paren_voicing_with_slash_bass(self, chord_helper):
        """Slash bass survives the curated paren voicing path."""
        result = chord_helper.compute_chord_notes("Cmaj7#5(9)/G")
        assert result is not None
        assert result.root == "C"
        assert result.bass_note == "G"

    def test_ordinary_paren_extensions_still_merge(self, chord_helper):
        """The curated skip must not disturb the normal (9)/(b9)/(11) merges."""
        # These qualities-with-parens are NOT table keys, so they must still be
        # rewritten by _normalize_parentheses as before.
        assert chord_helper.compute_chord_notes("Cmaj7(9)") is not None
        assert chord_helper.compute_chord_notes("C7(b9)") is not None
        assert chord_helper.compute_chord_notes("Cm7b5(9)") is not None  # -> Cm9b5
        assert chord_helper.compute_chord_notes("C(add9)") is not None


class TestAlteredDominantVariations:
    """Tests for altered dominant chord variations."""

    def test_7alt_contains_altered_tones(self, chord_helper):
        """Test C7alt expands to C7b9b13 (practical altered voicing)."""
        result = chord_helper.compute_chord_notes("C7alt")
        assert result is not None
        # Should contain altered 9th and 13th
        # C7b9b13 = C, E, G, Bb, Db, Ab
        assert result.root == "C"
        assert len(result.notes) >= 5  # At least 5 notes for altered chord

    def test_alt_shorthand(self, chord_helper):
        """Test Calt expands to C7alt then C7b9b13."""
        result = chord_helper.compute_chord_notes("Calt")
        assert result is not None
        assert result.root == "C"
        assert len(result.notes) >= 5

    def test_7alt_different_roots(self, chord_helper):
        """Test altered dominants on different roots."""
        for root in ["D", "Eb", "F#", "Bb"]:
            chord_name = f"{root}7alt"
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} should resolve"
            assert result.root.replace('b', '') == root.replace('b', '')


class TestComplexSeventhChordTypes:
    """Tests for complete coverage of 7th chord types."""

    def test_all_seventh_types_detected(self, chord_helper):
        """Test all seventh chord types are recognized."""
        seventh_chords = {
            'C7': 'Dominant 7th',
            'Cmaj7': 'Major 7th',
            'Cm7': 'Minor 7th',
            'Cdim7': 'Diminished 7th',
            'Cm7b5': 'Half-diminished',
            'CmM7': 'Minor-major 7th',
        }

        for chord_name, description in seventh_chords.items():
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} ({description}) should resolve"
            assert len(result.notes) == 4, f"{chord_name} should have 4 notes"


class TestComplexJazzChords:
    """Tests for complex jazz chord extensions and alterations."""

    def test_sharp_11_chords(self, chord_helper):
        """Test chords with #11 (Lydian sound)."""
        sharp_11_chords = [
            'Cmaj7#11',
            'Cmaj9#11',
            'C7#11',
            'C9#11',
            'C13#11',
            'Cmaj13#11',
        ]

        for chord_name in sharp_11_chords:
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} should resolve"
            assert result.root == "C", f"{chord_name} should have root C"

    def test_altered_dominant_chords(self, chord_helper):
        """Test altered dominant chords with multiple alterations."""
        altered_chords = [
            'C7b13',
            'C7#5',
            'C7b5',
            'C7#9#5',
            'C7b9b5',
            'C7b9b13',
            'C7#9b13',
            'C7b9#11',
            'C7#9#11',
            'C9b13',
            'C9#5',
        ]

        for chord_name in altered_chords:
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} should resolve"
            assert result.root == "C", f"{chord_name} should have root C"

    def test_thirteenth_chords(self, chord_helper):
        """Test thirteenth chord variants."""
        thirteenth_chords = [
            'C13',
            'Cm13',
            'Cmaj13',
        ]

        for chord_name in thirteenth_chords:
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} should resolve"
            assert result.root == "C", f"{chord_name} should have root C"
            # 13th chords typically have many notes
            assert len(result.notes) >= 4, f"{chord_name} should have at least 4 notes"

    def test_sus_chords_with_extensions(self, chord_helper):
        """Test suspended chords with extensions."""
        sus_chords = [
            'C7sus4',
            'C9sus4',
            'C13sus4',
        ]

        for chord_name in sus_chords:
            result = chord_helper.compute_chord_notes(chord_name)
            assert result is not None, f"{chord_name} should resolve"
            assert result.root == "C", f"{chord_name} should have root C"

    def test_complex_chords_with_different_roots(self, chord_helper):
        """Test complex chords work with various root notes."""
        complex_qualities = ['maj9#11', '7#9b13', '13#11', '7b9b13']

        for root in ['C', 'F#', 'Bb', 'Eb']:
            for quality in complex_qualities:
                chord_name = f"{root}{quality}"
                result = chord_helper.compute_chord_notes(chord_name)
                assert result is not None, f"{chord_name} should resolve"


class TestRegisterPreservingIntervals:
    """compute_chord_notes carries register-preserving intervals (semitones
    above the root), aligned with the note names, from whichever backend
    resolves the chord. This is what lets the voicer place extensions in the
    right octave instead of guessing from note order.
    """

    def test_intervals_present_and_aligned(self, chord_helper):
        """Every resolved chord carries intervals aligned with its notes."""
        for sym in ['C', 'Am', 'C7', 'Cmaj7', 'C9', 'C13', 'Cm7b5', 'Cadd9']:
            result = chord_helper.compute_chord_notes(sym)
            assert result is not None
            assert result.intervals is not None, f"{sym} missing intervals"
            assert len(result.intervals) == len(result.notes)
            assert result.intervals[0] == 0  # root at 0

    def test_extension_intervals_are_register_correct(self, chord_helper):
        """9th -> 14, 11th -> 17, 13th -> 21 (not folded into an octave)."""
        assert chord_helper.compute_chord_notes("C9").intervals == [0, 4, 7, 10, 14]
        assert chord_helper.compute_chord_notes("C11").intervals == [0, 7, 10, 14, 17]
        assert chord_helper.compute_chord_notes("C13").intervals == [0, 4, 7, 10, 14, 21]
        assert chord_helper.compute_chord_notes("Cadd9").intervals == [0, 4, 7, 14]

    def test_intervals_match_note_pitch_classes(self, chord_helper):
        """root_pitch_class + interval reproduces each note's pitch class."""
        from chord.midi_converter import parse_note_to_semitone
        for sym in ['C13', 'Cmaj11', 'F#9', 'Bbmaj7', 'Ebm11', 'Cmaj7#5(9)']:
            result = chord_helper.compute_chord_notes(sym)
            assert result is not None
            root_pc = parse_note_to_semitone(result.notes[0])
            for note, interval in zip(result.notes, result.intervals):
                assert (root_pc + interval) % 12 == parse_note_to_semitone(note), \
                    f"{sym}: {note} at interval {interval} does not match root"

    def test_curated_voicing_intervals_come_from_table(self, chord_helper):
        """Curated qualities keep the table's dropped-note register."""
        # maj11 drops the 3rd; 13 drops the 11th - the intervals reflect that.
        assert chord_helper.compute_chord_notes("Cmaj11").intervals == [0, 7, 11, 14, 17]
        assert chord_helper.compute_chord_notes("Cmaj13").intervals == [0, 4, 7, 11, 14, 21]

    def test_intervals_strictly_increasing_for_real_chords(self, chord_helper):
        """A real chord's intervals ascend - no extension below its predecessor."""
        for sym in ['C9', 'Cm9', 'C11', 'C13', 'Cmaj13', 'C13#11']:
            result = chord_helper.compute_chord_notes(sym)
            assert result is not None
            ivals = result.intervals
            assert all(b > a for a, b in zip(ivals, ivals[1:])), f"{sym}: {ivals}"


class TestAmericanEuropeanDisambiguation:
    """American chords that start with a European syllable ('Fa' = F, 'Do' = D)
    must not be mangled by the European->American conversion. Only 'Do' and 'Fa'
    collide with American roots; the converter runs first, and we fall back to
    the American spelling only when the conversion produces an invalid chord.
    """

    def test_f_aug_and_add_not_mangled(self, chord_helper):
        """'Faug'/'Fadd9' are F chords, not the 'Fug'/'Fdd9' the converter makes."""
        from chord.midi_converter import parse_note_to_semitone

        def pcs(sym):
            r = chord_helper.compute_chord_notes(sym)
            return sorted(parse_note_to_semitone(n) for n in r.notes) if r else None

        # F is 5 semitones above C; the F chord is the C chord transposed.
        for quality in ['aug', 'add9', 'add11', 'aug7', 'augmaj7', 'aug7b9']:
            c = pcs('C' + quality)
            f = pcs('F' + quality)
            assert f is not None, f"F{quality} should resolve"
            assert f == sorted((p + 5) % 12 for p in c), f"F{quality} wrong notes"

    def test_f_root_preserved(self, chord_helper):
        """The root stays F, not something the conversion left behind."""
        for quality in ['aug', 'add9', 'aug7', 'augmaj7']:
            result = chord_helper.compute_chord_notes('F' + quality)
            assert result is not None
            assert result.root == 'F'

    def test_do_stays_c_major_not_d_diminished(self, chord_helper):
        """'Do' is European C major, not D-diminished (lenient 'o' = dim)."""
        result = chord_helper.compute_chord_notes('Do')
        assert result is not None
        assert result.root == 'C'
        assert set(result.notes) == {'C', 'E', 'G'}

    def test_do7_stays_c7(self, chord_helper):
        """'Do7' is European C7, not D-diminished-7."""
        result = chord_helper.compute_chord_notes('Do7')
        assert result is not None
        assert result.root == 'C'
        # C7 = C E G Bb
        assert 'Bb' in result.notes or 'A#' in result.notes
        assert 'E' in result.notes

    def test_genuine_european_still_converts(self, chord_helper):
        """The fallback must not break real European notation."""
        expected = {
            'Fa': 'F', 'Fa7': 'F', 'Fam': 'F', 'Re': 'D', 'Mi': 'E',
            'Sol': 'G', 'La': 'A', 'Si': 'B', 'do': 'C', 'fa': 'F',
        }
        for european, root in expected.items():
            result = chord_helper.compute_chord_notes(european)
            assert result is not None, f"{european} should resolve"
            assert result.root == root, f"{european} -> root {result.root}, expected {root}"


@pytest.fixture
def chord_helper():
    """Create a ChordHelper instance."""
    return ChordHelper()

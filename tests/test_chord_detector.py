"""Unit tests for ChordDetector."""

import pytest
from chord.detector import ChordDetector
from models.chord import ChordInfo


class TestAmericanNotation:
    """Tests for American notation chord detection."""

    def test_basic_major_chords(self, american_detector):
        """Test detection of basic major chords."""
        text = "C F G"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "C"
        assert chords[1].chord == "F"
        assert chords[2].chord == "G"
        assert all(c.is_valid for c in chords)
        assert all(not c.is_relative for c in chords)

    def test_minor_chords(self, american_detector):
        """Test detection of minor chords."""
        text = "Am Dm Em"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "Am"
        assert chords[1].chord == "Dm"
        assert chords[2].chord == "Em"
        assert all(c.is_valid for c in chords)

    def test_seventh_chords(self, american_detector):
        """Test detection of seventh chords."""
        text = "C7 Am7 Dmaj7 G7"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "C7"
        assert chords[1].chord == "Am7"
        assert chords[2].chord == "Dmaj7"
        assert chords[3].chord == "G7"

    def test_slash_chords(self, american_detector):
        """Test detection of slash chords."""
        text = "C/G Am/C D/F#"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "C/G"
        assert chords[1].chord == "Am/C"
        assert chords[2].chord == "D/F#"

    def test_duration_parsing(self, american_detector):
        """Test parsing of chord durations."""
        text = "C*2 F*4 G*1.5"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "C"
        assert chords[0].duration == 2.0
        assert chords[1].chord == "F"
        assert chords[1].duration == 4.0
        assert chords[2].chord == "G"
        assert chords[2].duration == 1.5

    def test_mixed_chords_with_duration(self, american_detector):
        """Test mixed chords with and without duration."""
        text = "C*2 F G*4"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].duration == 2.0
        assert chords[1].duration is None
        assert chords[2].duration == 4.0


class TestRomanNumeralChords:
    """Tests for roman numeral chord detection."""

    def test_basic_roman_numerals(self, american_detector):
        """Test detection of basic roman numeral chords."""
        text = "I IV V"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "I"
        assert chords[1].chord == "IV"
        assert chords[2].chord == "V"
        assert all(c.is_relative for c in chords)
        assert all(c.is_valid for c in chords)

    def test_minor_roman_numerals(self, american_detector):
        """Test detection of minor roman numeral chords."""
        text = "i iv v vi"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "i"
        assert chords[1].chord == "iv"
        assert chords[2].chord == "v"
        assert chords[3].chord == "vi"
        assert all(c.is_relative for c in chords)

    def test_roman_numeral_qualities(self, american_detector):
        """Test roman numerals with quality markers."""
        text = "I7 V7 viidim"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "I7"
        assert chords[1].chord == "V7"
        assert chords[2].chord == "viidim"
        assert all(c.is_relative for c in chords)

    def test_roman_slash_chords(self, american_detector):
        """Test roman numeral slash chords."""
        text = "I/V vi/IV"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 2
        assert chords[0].chord == "I/V"
        assert chords[1].chord == "vi/IV"
        assert all(c.is_relative for c in chords)

    def test_roman_with_duration(self, american_detector):
        """Test roman numerals with duration."""
        text = "I*2 IV*4 V*1"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "I"
        assert chords[0].duration == 2.0
        assert chords[0].is_relative
        assert chords[1].chord == "IV"
        assert chords[1].duration == 4.0
        assert chords[2].chord == "V"
        assert chords[2].duration == 1.0


class TestEuropeanNotation:
    """Tests for European notation chord detection."""

    def test_basic_european_chords(self, european_detector):
        """Test detection of basic European chords."""
        text = "Do Re Mi Fa Sol La Si"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 7
        assert chords[0].chord == "Do"
        assert chords[1].chord == "Re"
        assert chords[2].chord == "Mi"
        assert chords[3].chord == "Fa"
        assert chords[4].chord == "Sol"
        assert chords[5].chord == "La"
        assert chords[6].chord == "Si"

    def test_european_minor_chords(self, european_detector):
        """Test detection of minor European chords."""
        text = "do rem mim"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "do"
        assert chords[1].chord == "rem"
        assert chords[2].chord == "mim"

    def test_european_seventh_chords(self, european_detector):
        """Test detection of European seventh chords."""
        text = "Do7 Rem7 Sol7"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 3
        assert chords[0].chord == "Do7"
        assert chords[1].chord == "Rem7"
        assert chords[2].chord == "Sol7"

    def test_european_with_duration(self, european_detector):
        """Test European chords with duration."""
        text = "Do*2 rem*4"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 2
        assert chords[0].chord == "Do"
        assert chords[0].duration == 2.0
        assert chords[1].chord == "rem"
        assert chords[1].duration == 4.0


class TestLineClassification:
    """Tests for chord line classification."""

    def test_pure_chord_line(self, american_detector):
        """Test that lines with only chords are classified correctly."""
        text = "C F G Am"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4

    def test_mixed_line_high_chord_percentage(self, american_detector):
        """Test line with high percentage of chords."""
        text = "C F G Am the"  # 80% chords, should be chord line
        chords = american_detector.detect_chords_in_text(text)

        # With 60% threshold, 80% should pass
        assert len(chords) == 4

    def test_lyric_line_not_detected(self, american_detector):
        """Test that lyric lines don't get detected as chord lines."""
        text = "This is a lyric line with some words"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 0

    def test_punctuation_ignored(self, american_detector):
        """Test that punctuation is ignored in chord percentage."""
        text = "C | F | G | Am"
        chords = american_detector.detect_chords_in_text(text)

        # Punctuation (|) should be excluded from percentage calculation
        assert len(chords) == 4

    def test_directives_excluded_from_percentage(self, american_detector):
        """Test that directives don't count toward chord percentage."""
        text = "{bpm: 120} C F G"
        chords = american_detector.detect_chords_in_text(text)

        # Directive shouldn't affect chord line classification
        assert len(chords) == 3


class TestChordPositions:
    """Tests for chord position tracking."""

    def test_chord_positions_single_line(self, american_detector):
        """Test that chord positions are tracked correctly."""
        text = "C F G"
        chords = american_detector.detect_chords_in_text(text)

        assert chords[0].start == 0
        assert chords[0].end == 1
        assert chords[1].start == 2
        assert chords[1].end == 3
        assert chords[2].start == 4
        assert chords[2].end == 5

    def test_chord_positions_multiline(self, american_detector):
        """Test chord positions across multiple lines."""
        text = "C F\nG Am"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        # First line: "C F\n" (positions 0-3)
        assert chords[0].start == 0  # C
        assert chords[1].start == 2  # F
        # Second line starts at position 4 (after newline)
        assert chords[2].start == 4  # G
        assert chords[3].start == 6  # Am

    def test_line_numbers(self, american_detector):
        """Test that line numbers are tracked correctly."""
        text = "C F\nG Am\nDm"
        chords = american_detector.detect_chords_in_text(text)

        assert chords[0].line == 1
        assert chords[1].line == 1
        assert chords[2].line == 2
        assert chords[3].line == 2
        assert chords[4].line == 3


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_text(self, american_detector):
        """Test handling of empty text."""
        text = ""
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 0

    def test_whitespace_only(self, american_detector):
        """Test handling of whitespace-only text."""
        text = "   \n  \n   "
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 0

    def test_invalid_chord_like_words(self, american_detector):
        """Test that invalid chord-like words aren't detected."""
        text = "The Can Fan Game"
        chords = american_detector.detect_chords_in_text(text)

        # None of these should be detected as chords
        assert len(chords) == 0

    def test_accidentals(self, american_detector):
        """Test chords with accidentals."""
        text = "C# Db F# Gb"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "C#"
        assert chords[1].chord == "Db"
        assert chords[2].chord == "F#"
        assert chords[3].chord == "Gb"

    def test_complex_chord_qualities(self, american_detector):
        """Test complex chord qualities."""
        text = "Cmaj7 Dm7b5 G7#9 Am9"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "Cmaj7"
        assert chords[1].chord == "Dm7b5"
        assert chords[2].chord == "G7#9"
        assert chords[3].chord == "Am9"


class TestDirectiveRegression:
    """Regression tests to ensure chords inside directives are not detected."""

    def test_key_directive_not_detected_as_chord(self, american_detector):
        """Test that {key: G} doesn't detect G as a chord."""
        text = "{key: G} C"
        chords = american_detector.detect_chords_in_text(text)

        # Should only detect C, not the G inside the directive
        assert len(chords) == 1
        assert chords[0].chord == "C"

    def test_bpm_directive_with_numbers(self, american_detector):
        """Test that {bpm: 120} doesn't interfere with chord detection."""
        text = "{bpm: 120} C G"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 2
        assert chords[0].chord == "C"
        assert chords[1].chord == "G"

    def test_multiple_directives_with_chord_like_content(self, american_detector):
        """Test multiple directives containing chord-like text."""
        text = "{label: verse} {key: D} {time: 3/4} C F G"
        chords = american_detector.detect_chords_in_text(text)

        # Should only detect C, F, G - not the D in {key: D}
        assert len(chords) == 3
        assert chords[0].chord == "C"
        assert chords[1].chord == "F"
        assert chords[2].chord == "G"

    def test_directive_with_roman_numeral(self, american_detector):
        """Test that roman numerals inside directives are ignored."""
        text = "{loop: verse 2} I V"
        chords = american_detector.detect_chords_in_text(text)

        # Should only detect I, V - not interpret "verse" as anything
        assert len(chords) == 2
        assert chords[0].chord == "I"
        assert chords[1].chord == "V"
        assert all(c.is_relative for c in chords)

    def test_chords_between_directives(self, american_detector):
        """Test chords positioned between directives."""
        text = "{bpm: 100} C {key: G} G {time: 4/4} D"
        chords = american_detector.detect_chords_in_text(text)

        # Should detect all three chords in their proper positions
        assert len(chords) == 3
        assert chords[0].chord == "C"
        assert chords[1].chord == "G"
        assert chords[2].chord == "D"

    def test_tempo_directive_synonym(self, american_detector):
        """Test that {tempo: 100} works like {bpm: 100}."""
        text = "{tempo: 100} Am Dm"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 2
        assert chords[0].chord == "Am"
        assert chords[1].chord == "Dm"


class TestAdvancedNotations:
    """Tests for advanced chord notations (unicode, symbols, omit, etc.)."""

    def test_unicode_symbols(self, american_detector):
        """Test detection of chords with unicode symbols."""
        text = "C♯ D♭ E♭maj7 F♯m7♭5"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "C♯"
        assert chords[1].chord == "D♭"
        assert chords[2].chord == "E♭maj7"
        assert chords[3].chord == "F♯m7♭5"
        assert all(c.is_valid for c in chords)

    def test_symbol_notation(self, american_detector):
        """Test detection of chords with symbols (°, ø, +)."""
        text = "C° D°7 Eø Gø7 A+"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 5
        assert chords[0].chord == "C°"
        assert chords[1].chord == "D°7"
        assert chords[2].chord == "Eø"
        assert chords[3].chord == "Gø7"
        assert chords[4].chord == "A+"
        assert all(c.is_valid for c in chords)

    def test_alternative_qualities(self, american_detector):
        """Test detection of alternative quality notations."""
        text = "C- Dmin Emi FM7 Gdom7 Aalt"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 6
        assert chords[0].chord == "C-"
        assert chords[1].chord == "Dmin"
        assert chords[2].chord == "Emi"
        assert chords[3].chord == "FM7"
        assert chords[4].chord == "Gdom7"
        assert chords[5].chord == "Aalt"
        assert all(c.is_valid for c in chords)

    def test_parentheses_notation(self, american_detector):
        """Test detection of parentheses notation."""
        text = "C(9) Dmaj7(9) E7(b9) Fm7(11)"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "C(9)"
        assert chords[1].chord == "Dmaj7(9)"
        assert chords[2].chord == "E7(b9)"
        assert chords[3].chord == "Fm7(11)"
        assert all(c.is_valid for c in chords)

    def test_omit_notation(self, american_detector):
        """Test detection of omit notation."""
        text = "C(no3) D(omit3) E(no5) F7(no3) G(add9)"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 5
        assert chords[0].chord == "C(no3)"
        assert chords[1].chord == "D(omit3)"
        assert chords[2].chord == "E(no5)"
        assert chords[3].chord == "F7(no3)"
        assert chords[4].chord == "G(add9)"
        assert all(c.is_valid for c in chords)

    def test_lowercase_notation(self, american_detector):
        """Test detection of lowercase chord notation."""
        text = "c d e7 f#m"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "c"
        assert chords[1].chord == "d"
        assert chords[2].chord == "e7"
        assert chords[3].chord == "f#m"
        assert all(c.is_valid for c in chords)

    def test_mixed_advanced_notations(self, american_detector):
        """Test detection of mixed advanced notations in one line."""
        text = "C7alt D♭maj7(9) E° Fm7(no3) g c-"
        chords = american_detector.detect_chords_in_text(text)

        assert len(chords) == 6
        assert chords[0].chord == "C7alt"
        assert chords[1].chord == "D♭maj7(9)"
        assert chords[2].chord == "E°"
        assert chords[3].chord == "Fm7(no3)"
        assert chords[4].chord == "g"
        assert chords[5].chord == "c-"
        # Note: Individual validation tested in compute_chord_notes tests


class TestEuropeanAdvanced:
    """Tests for European notation with advanced features."""

    def test_european_with_accents(self, european_detector):
        """Test detection of European notation with accents."""
        text = "Dó Rém Fá7 Lám"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "Dó"
        assert chords[1].chord == "Rém"
        assert chords[2].chord == "Fá7"
        assert chords[3].chord == "Lám"
        assert all(c.is_valid for c in chords)

    def test_european_with_symbols(self, european_detector):
        """Test detection of European notation with symbols."""
        text = "Do° Re+ Miø Solmaj7(9)"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "Do°"
        assert chords[1].chord == "Re+"
        assert chords[2].chord == "Miø"
        assert chords[3].chord == "Solmaj7(9)"
        assert all(c.is_valid for c in chords)

    def test_european_lowercase_minor(self, european_detector):
        """Test detection of lowercase European notation (minor)."""
        text = "do re mi7 fa#"
        chords = european_detector.detect_chords_in_text(text)

        assert len(chords) == 4
        assert chords[0].chord == "do"
        assert chords[1].chord == "re"
        assert chords[2].chord == "mi7"
        assert chords[3].chord == "fa#"
        assert all(c.is_valid for c in chords)

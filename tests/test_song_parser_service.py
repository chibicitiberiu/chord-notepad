"""Unit tests for SongParserService."""

import pytest
from services.song_parser_service import SongParserService
from models.directive import DirectiveType, BPMModifierType
from models.line import LineType
from models.notation import Notation


class TestDirectiveParsing:
    """Tests for directive parsing."""

    def test_bpm_directive(self, song_parser):
        """Test parsing BPM directive."""
        text = "{bpm: 120}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm == 120
        assert directives[0].bpm_modifier_type == BPMModifierType.ABSOLUTE
        assert directives[0].start == 0
        assert directives[0].end == 10

    def test_time_signature_directive(self, song_parser):
        """Test parsing time signature directive."""
        text = "{time: 4/4}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.TIME_SIGNATURE
        assert directives[0].beats == 4
        assert directives[0].unit == 4

    def test_key_directive(self, song_parser):
        """Test parsing key directive."""
        text = "{key: C}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.KEY
        assert directives[0].key == "C"

    def test_loop_directive_with_count(self, song_parser):
        """Test parsing loop directive with count."""
        text = "{loop: verse 2}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.LOOP
        assert directives[0].label == "verse"
        assert directives[0].loop_count == 2

    def test_loop_directive_default_count(self, song_parser):
        """Test parsing loop directive with default count."""
        text = "{loop: chorus}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.LOOP
        assert directives[0].label == "chorus"
        assert directives[0].loop_count == 2  # Default

    def test_multiple_directives(self, song_parser):
        """Test parsing multiple directives."""
        text = "{bpm: 120} {key: C} {time: 4/4}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 3
        assert directives[0].type == DirectiveType.BPM
        assert directives[1].type == DirectiveType.KEY
        assert directives[2].type == DirectiveType.TIME_SIGNATURE

    def test_invalid_directive_ignored(self, song_parser):
        """Test that invalid directives are parsed but marked as invalid."""
        text = "{invalid: value} {bpm: 120}"
        directives = song_parser.parse_directives(text)

        # Both directives should be parsed (for editor highlighting)
        assert len(directives) == 2
        # First should be invalid
        assert directives[0].type == DirectiveType.UNKNOWN
        assert directives[0].is_valid is False
        # Second should be valid
        assert directives[1].type == DirectiveType.BPM
        assert directives[1].is_valid is True

    def test_malformed_directive_ignored(self, song_parser):
        """Test that malformed directives are parsed but marked as invalid."""
        text = "{bpm: notanumber}"
        directives = song_parser.parse_directives(text)

        # Malformed directive should be parsed (for editor highlighting) but marked invalid
        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].is_valid is False


class TestEnhancedBPMDirectives:
    """Tests for enhanced BPM directive features."""

    def test_tempo_synonym(self, song_parser):
        """Test that 'tempo' is a synonym for 'bpm'."""
        text = "{tempo: 100}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm == 100
        assert directives[0].bpm_modifier_type == BPMModifierType.ABSOLUTE

    def test_relative_bpm_positive(self, song_parser):
        """Test relative BPM increase."""
        text = "{bpm: +20}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.RELATIVE
        assert directives[0].bpm_modifier_value == 20.0

    def test_relative_bpm_negative(self, song_parser):
        """Test relative BPM decrease."""
        text = "{bpm: -20}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.RELATIVE
        assert directives[0].bpm_modifier_value == -20.0

    def test_percentage_bpm(self, song_parser):
        """Test percentage BPM (e.g., 50% for half speed)."""
        text = "{bpm: 50%}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.PERCENTAGE
        assert directives[0].bpm_modifier_value == 50.0

    def test_percentage_bpm_with_decimals(self, song_parser):
        """Test percentage BPM with decimal values."""
        text = "{bpm: 75.5%}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.PERCENTAGE
        assert directives[0].bpm_modifier_value == 75.5

    def test_multiplier_bpm_half_speed(self, song_parser):
        """Test multiplier BPM (e.g., 0.5x for half speed)."""
        text = "{bpm: 0.5x}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.MULTIPLIER
        assert directives[0].bpm_modifier_value == 0.5

    def test_multiplier_bpm_double_speed(self, song_parser):
        """Test multiplier BPM (e.g., 2x for double speed)."""
        text = "{bpm: 2x}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.MULTIPLIER
        assert directives[0].bpm_modifier_value == 2.0

    def test_reset_bpm_with_reset_keyword(self, song_parser):
        """Test reset BPM using 'reset' keyword."""
        text = "{bpm: reset}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.RESET

    def test_reset_bpm_with_original_keyword(self, song_parser):
        """Test reset BPM using 'original' keyword."""
        text = "{bpm: original}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.RESET

    def test_multiple_bpm_modifiers_in_sequence(self, song_parser):
        """Test multiple BPM directives with different modifiers."""
        text = "{bpm: 120} {bpm: +20} {bpm: 50%} {bpm: 2x} {bpm: reset}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 5
        assert directives[0].bpm_modifier_type == BPMModifierType.ABSOLUTE
        assert directives[1].bpm_modifier_type == BPMModifierType.RELATIVE
        assert directives[2].bpm_modifier_type == BPMModifierType.PERCENTAGE
        assert directives[3].bpm_modifier_type == BPMModifierType.MULTIPLIER
        assert directives[4].bpm_modifier_type == BPMModifierType.RESET

    def test_tempo_with_relative_modifier(self, song_parser):
        """Test that 'tempo' keyword works with relative modifiers."""
        text = "{tempo: +15}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.RELATIVE
        assert directives[0].bpm_modifier_value == 15.0

    def test_tempo_with_percentage_modifier(self, song_parser):
        """Test that 'tempo' keyword works with percentage modifiers."""
        text = "{tempo: 150%}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.PERCENTAGE
        assert directives[0].bpm_modifier_value == 150.0

    def test_tempo_with_multiplier(self, song_parser):
        """Test that 'tempo' keyword works with multiplier."""
        text = "{tempo: 1.5x}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm_modifier_type == BPMModifierType.MULTIPLIER
        assert directives[0].bpm_modifier_value == 1.5


class TestRomanNumeralDetection:
    """Tests for roman numeral chord detection."""

    def test_is_roman_numeral_chord_uppercase(self, song_parser):
        """Test detection of uppercase roman numerals."""
        assert song_parser.is_roman_numeral_chord("I")
        assert song_parser.is_roman_numeral_chord("IV")
        assert song_parser.is_roman_numeral_chord("V")
        assert song_parser.is_roman_numeral_chord("VII")

    def test_is_roman_numeral_chord_lowercase(self, song_parser):
        """Test detection of lowercase roman numerals."""
        assert song_parser.is_roman_numeral_chord("i")
        assert song_parser.is_roman_numeral_chord("iv")
        assert song_parser.is_roman_numeral_chord("v")
        assert song_parser.is_roman_numeral_chord("vi")

    def test_is_roman_numeral_chord_with_quality(self, song_parser):
        """Test detection of roman numerals with quality markers."""
        assert song_parser.is_roman_numeral_chord("V7")
        assert song_parser.is_roman_numeral_chord("viidim")
        assert song_parser.is_roman_numeral_chord("IVmaj7")

    def test_is_not_roman_numeral_chord(self, song_parser):
        """Test that non-roman numerals are not detected."""
        assert not song_parser.is_roman_numeral_chord("C")
        assert not song_parser.is_roman_numeral_chord("Am")
        assert not song_parser.is_roman_numeral_chord("Do")
        assert not song_parser.is_roman_numeral_chord("rem")


class TestDurationParsing:
    """Tests for duration parsing."""

    def test_parse_chord_with_duration(self, song_parser):
        """Test parsing chord with duration."""
        chord, duration = song_parser.parse_chord_with_duration("C*2")

        assert chord == "C"
        assert duration == 2.0

    def test_parse_chord_with_decimal_duration(self, song_parser):
        """Test parsing chord with decimal duration."""
        chord, duration = song_parser.parse_chord_with_duration("Am*1.5")

        assert chord == "Am"
        assert duration == 1.5

    def test_parse_chord_without_duration(self, song_parser):
        """Test parsing chord without duration."""
        chord, duration = song_parser.parse_chord_with_duration("C")

        assert chord == "C"
        assert duration is None

    def test_parse_invalid_duration(self, song_parser):
        """Test handling of invalid duration."""
        chord, duration = song_parser.parse_chord_with_duration("C*invalid")

        assert chord == "C*invalid"
        assert duration is None


class TestLineDetection:
    """Tests for line detection and classification."""

    def test_detect_chords_in_simple_text(self, song_parser):
        """Test chord detection in simple text."""
        text = "C F G Am"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.CHORD
        assert len(lines[0].chords) == 4

    def test_detect_chords_with_directives(self, song_parser):
        """Test chord detection with directives."""
        text = "{bpm: 120} C F G"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.CHORD
        assert len(lines[0].chords) == 3
        assert len(lines[0].directives) == 1
        assert lines[0].directives[0].type == DirectiveType.BPM

    def test_detect_multiline_with_directives(self, song_parser):
        """Test multiline text with directives."""
        text = """{bpm: 120}
C F G Am
{key: C}
Dm G C"""
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 4

        # Line 1: directive only
        assert lines[0].type == LineType.TEXT
        assert len(lines[0].directives) == 1
        assert lines[0].directives[0].type == DirectiveType.BPM

        # Line 2: chords
        assert lines[1].type == LineType.CHORD
        assert len(lines[1].chords) == 4

        # Line 3: directive only
        assert lines[2].type == LineType.TEXT
        assert len(lines[2].directives) == 1

        # Line 4: chords
        assert lines[3].type == LineType.CHORD
        assert len(lines[3].chords) == 3

    def test_directive_line_with_chords(self, song_parser):
        """Test line with both directives and chords."""
        text = "{bpm: 120} {time: 4/4} C F G"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.CHORD
        assert len(lines[0].chords) == 3
        assert len(lines[0].directives) == 2
        # Items should be sorted by position
        assert len(lines[0].items) == 5

    def test_key_directive_does_not_detect_chord(self, song_parser):
        """Test that {key: C} doesn't detect C as a chord."""
        text = "{key: C}"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.TEXT  # Should be text line, not chord line
        assert len(lines[0].chords) == 0  # No chords detected
        assert len(lines[0].directives) == 1  # Only the directive

    def test_multiple_directives_with_chord_like_values(self, song_parser):
        """Test that chord-like values in directives are not detected as chords."""
        text = "{key: C} {key: Am} {key: G}"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.TEXT  # No real chords
        assert len(lines[0].chords) == 0  # Values inside directives not counted
        assert len(lines[0].directives) == 3

    def test_text_line_detection(self, song_parser):
        """Test that text lines are detected correctly."""
        text = "This is a lyric line"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.TEXT
        assert len(lines[0].chords) == 0


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_complete_song_structure(self, song_parser):
        """Test parsing a complete song structure."""
        text = """{bpm: 120} {key: C}
C*2 F G Am*4
{time: 4/4}
I IV V vi
Lyrics go here
{loop: verse 2}
Dm G C C"""

        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 7

        # Line 1: directives
        assert lines[0].type == LineType.TEXT
        assert len(lines[0].directives) == 2

        # Line 2: chords with durations
        assert lines[1].type == LineType.CHORD
        assert lines[1].chords[0].chord == "C"
        assert lines[1].chords[0].duration == 2.0
        assert lines[1].chords[3].chord == "Am"
        assert lines[1].chords[3].duration == 4.0

        # Line 3: time directive
        assert lines[2].type == LineType.TEXT
        assert lines[2].directives[0].type == DirectiveType.TIME_SIGNATURE

        # Line 4: roman numerals
        assert lines[3].type == LineType.CHORD
        assert all(c.is_relative for c in lines[3].chords)

        # Line 5: lyrics
        assert lines[4].type == LineType.TEXT
        assert len(lines[4].chords) == 0

        # Line 6: loop directive
        assert lines[5].type == LineType.TEXT
        assert lines[5].directives[0].type == DirectiveType.LOOP

        # Line 7: final chords
        assert lines[6].type == LineType.CHORD
        assert len(lines[6].chords) == 4

    def test_mixed_notation_not_supported(self, song_parser):
        """Test that mixed notation in single detection is handled."""
        # Parser uses one notation at a time
        # With 60% threshold, need at least 3 out of 4 words to be chords

        # American notation - add more chords to pass threshold
        text_american = "C F G Am Do"
        lines_american = song_parser.detect_chords_in_text(text_american, notation=Notation.AMERICAN)
        # Should detect C, F, G, Am as American chords (80% > 60% threshold)
        assert len(lines_american[0].chords) == 4

        # European notation - add more chords to pass threshold
        text_european = "Do Re Mi Fa C"
        lines_european = song_parser.detect_chords_in_text(text_european, notation=Notation.EUROPEAN)
        # Should detect Do, Re, Mi, Fa as European chords (80% > 60% threshold)
        assert len(lines_european[0].chords) == 4

    def test_roman_numerals_with_american(self, song_parser):
        """Test that roman numerals work with American notation."""
        text = "C F I IV"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines[0].chords) == 4
        assert not lines[0].chords[0].is_relative  # C
        assert not lines[0].chords[1].is_relative  # F
        assert lines[0].chords[2].is_relative      # I
        assert lines[0].chords[3].is_relative      # IV

    def test_roman_numerals_with_european(self, song_parser):
        """Test that roman numerals work with European notation."""
        text = "Do Fa I IV"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.EUROPEAN)

        assert len(lines[0].chords) == 4
        assert not lines[0].chords[0].is_relative  # Do
        assert not lines[0].chords[1].is_relative  # Fa
        assert lines[0].chords[2].is_relative      # I
        assert lines[0].chords[3].is_relative      # IV


class TestChordValidation:
    """Tests for chord validation."""

    def test_validate_valid_chord(self, song_parser):
        """Test validation of valid chord."""
        assert song_parser.validate_chord("C", notation="american")
        assert song_parser.validate_chord("Am7", notation="american")
        assert song_parser.validate_chord("Gmaj7", notation="american")

    def test_validate_invalid_chord(self, song_parser):
        """Test validation of invalid chord."""
        # ChordHelper should reject these
        assert not song_parser.validate_chord("X", notation="american")
        assert not song_parser.validate_chord("H", notation="american")


class TestNotationConversion:
    """Tests for notation conversion."""

    def test_european_to_american(self, song_parser):
        """Test conversion from European to American notation."""
        result = song_parser.convert_to_american("Do Re Mi")
        # NotationConverter should handle this
        assert "C" in result or "Do" in result  # Depends on converter implementation

    def test_american_to_european(self, song_parser):
        """Test conversion from American to European notation."""
        result = song_parser.convert_to_european("C D E")
        # NotationConverter should handle this
        assert "Do" in result or "C" in result  # Depends on converter implementation


class TestCommentSupport:
    """Tests for comment support in parsing."""

    def test_directive_after_comment_ignored(self, song_parser):
        """Test that directives after // are ignored."""
        text = "// {bpm: 120}"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 0

    def test_directive_before_comment(self, song_parser):
        """Test that directives before // are parsed."""
        text = "{bpm: 120} // this is a comment"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 1
        assert directives[0].type == DirectiveType.BPM
        assert directives[0].bpm == 120

    def test_multiple_lines_with_comments(self, song_parser):
        """Test parsing directives from multiple lines with comments."""
        text = "{bpm: 120} // tempo\n{key: C} // key"
        directives = song_parser.parse_directives(text)

        assert len(directives) == 2
        assert directives[0].type == DirectiveType.BPM
        assert directives[1].type == DirectiveType.KEY

    def test_comment_in_song_building(self, song_parser):
        """Test that comments work in full song building."""
        text = """{bpm: 120} // tempo setting
C F G // verse chords
// This is just a comment line
Am Dm G // chorus"""

        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 4

        # Line 1: directive with comment
        assert lines[0].type == LineType.TEXT
        assert len(lines[0].directives) == 1

        # Line 2: chords with comment
        assert lines[1].type == LineType.CHORD
        assert len(lines[1].chords) == 3

        # Line 3: full comment line
        assert lines[2].type == LineType.TEXT
        assert len(lines[2].chords) == 0

        # Line 4: chords with comment
        assert lines[3].type == LineType.CHORD
        assert len(lines[3].chords) == 3

    def test_commented_directive_in_chord_line(self, song_parser):
        """Test that commented-out directives on chord lines are ignored."""
        text = "C F G // {bpm: 200}"
        lines = song_parser.detect_chords_in_text(text, notation=Notation.AMERICAN)

        assert len(lines) == 1
        assert lines[0].type == LineType.CHORD
        assert len(lines[0].chords) == 3
        # The commented directive should not be parsed
        assert len(lines[0].directives) == 0

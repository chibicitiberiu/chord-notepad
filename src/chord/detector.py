"""
Chord detection using line-based classification and ChordHelper validation
"""

import re
from typing import List, Tuple, Optional, Literal, Dict
from chord.helper import ChordHelper
from chord.converter import NotationConverter
from models.chord import ChordInfo


class ChordDetector:
    """Detects chords in text using line-based classification"""

    # Comment pattern - matches // and everything after it
    COMMENT_PATTERN = re.compile(r'//.*$')

    # Basic chord pattern for initial detection (American notation, supports lowercase for minor)
    # Supports: ° (diminished), ø (half-diminished), + (augmented)
    # Supports unicode: ♯, ♭ (in addition to #, b)
    # Supports alterations: 7b5, 7#9, 9#11, etc.
    # Supports parentheses: dim(maj9), maj7#5(9), m7b5(b9), (no3), (omit5)
    # Supports M (uppercase) for minor-major: mM7, mM9
    # Supports duration: C*2, Am*4.5
    CHORD_PATTERN_AMERICAN = re.compile(
        r'\b([A-Ga-g][#b♯♭]?(?:°|ø|\+|Δ|-|m|M|maj|min|mi|dim|aug|dom|alt|sus[24]?|add\d+|no\d+|omit\d+|\d+|[#b♯♭]\d+|\([^)]+\))*(?:/[A-Ga-g][#b♯♭]?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
    )

    # European notation pattern (Do/do for Major/minor, DoM explicit major, Dom explicit minor)
    # Supports: ° (diminished), ø (half-diminished), + (augmented)
    # Supports unicode: ♯, ♭ (in addition to #, b)
    # Supports alterations: 7b5, 7#9, 9#11, etc.
    # Supports parentheses: dim(maj9), maj7#5(9), m7b5(b9), (no3), (omit5)
    # Supports accents: Dó, Ré, Fá, Lá
    # Supports duration: Do*2, rem*4.5
    CHORD_PATTERN_EUROPEAN = re.compile(
        r'\b((?:D[oóò]|R[eéèê]|Mi|F[aáà]|Sol|L[aáà]|Si|d[oóò]|r[eéèê]|mi|f[aáà]|sol|l[aáà]|si)[#b♯♭]?(?:°|ø|\+|Δ|M|m|maj|min|mi|dim|aug|dom|alt|sus[24]?|add\d+|no\d+|omit\d+|\d+|[#b♯♭]\d+|\([^)]+\))*(?:/(?:D[oóò]|R[eéèê]|Mi|F[aáà]|Sol|L[aáà]|Si|d[oóò]|r[eéèê]|mi|f[aáà]|sol|l[aáà]|si)[#b♯♭]?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
    )

    # Roman numeral chord pattern (I, ii, V7, vi/I, ♭III, #ivo, etc.)
    # Supports uppercase (major) and lowercase (minor) roman numerals
    # Supports accidentals BEFORE roman numeral: ♭III, bVII, #ivo
    # Supports quality markers: o, °, ø, +, maj, min, dim, aug, sus, add, and extensions
    # Supports duration: I*2, vi*4.5, ♭III*2
    # Note: Using lookbehind instead of \b to properly handle Unicode and # characters
    CHORD_PATTERN_ROMAN = re.compile(
        r'(?<![A-Za-z0-9#b♭♯])([#b♭♯]?[IViv]+(?:o|°|ø|\+|maj|min|dim|aug|sus[24]?|add\d+|\d+|[#b]\d+)*(?:/[#b♭♯]?[IViv]+(?:o|°)?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
    )

    def __init__(self, threshold: float = 0.6, notation: Literal['american', 'european'] = 'american') -> None:
        """
        Initialize chord detector

        Args:
            threshold: Percentage of words that must be chords for line classification (default 0.6)
            notation: 'american' or 'european'
        """
        self.threshold = threshold
        self.notation = notation
        self.chord_helper = ChordHelper()

    def _strip_comment(self, line: str) -> str:
        """Strip comment from a line.

        Comments start with // and continue to end of line.

        Args:
            line: Line that may contain a comment

        Returns:
            Line with comment removed
        """
        return self.COMMENT_PATTERN.sub('', line)

    def detect_chords_in_text(self, text: str) -> List[ChordInfo]:
        """
        Detect all chords in text with line-based classification

        Args:
            text: Full text content

        Returns:
            List of ChordInfo objects with attributes:
                chord: str - The chord string
                line: int - Line number (1-indexed) [dynamic attribute]
                start: int - Character position in full text
                end: int - End position in full text
                is_valid: bool - Whether chord is valid
                is_relative: bool - Whether this is a roman numeral chord
                duration: float - Duration in beats (if specified with chord*beats)
        """
        results = []
        lines = text.split('\n')

        char_offset = 0  # Track character position in full text

        for line_num, line in enumerate(lines, start=1):
            if self._is_chord_line(line):
                # Process all words on this chord line
                chords = self._extract_chords_from_line(line, line_num, char_offset)
                results.extend(chords)

            # Update offset for next line (include newline)
            char_offset += len(line) + 1

        return results

    def _remove_directives_and_map_positions(self, line: str) -> Tuple[str, Dict[int, int]]:
        """Remove directives and comments from line and create position mapping.

        Args:
            line: Original line with directives and/or comments

        Returns:
            Tuple of (cleaned_line, position_map) where position_map maps
            positions in cleaned_line to positions in original line
        """
        # Find all directive regions
        directives = []
        for match in re.finditer(r'\{[^}]+\}', line):
            directives.append((match.start(), match.end()))

        # Find comment region (// to end of line)
        comment_match = self.COMMENT_PATTERN.search(line)
        if comment_match:
            directives.append((comment_match.start(), comment_match.end()))

        # Build cleaned line and position map
        cleaned_parts = []
        position_map = {}
        cleaned_pos = 0
        original_pos = 0

        # Sort directives by start position
        directives.sort()

        for dir_start, dir_end in directives:
            # Add characters before this directive
            while original_pos < dir_start:
                cleaned_parts.append(line[original_pos])
                position_map[cleaned_pos] = original_pos
                cleaned_pos += 1
                original_pos += 1
            # Skip the directive
            original_pos = dir_end

        # Add remaining characters after last directive
        while original_pos < len(line):
            cleaned_parts.append(line[original_pos])
            position_map[cleaned_pos] = original_pos
            cleaned_pos += 1
            original_pos += 1

        cleaned_line = ''.join(cleaned_parts)
        return cleaned_line, position_map

    def _is_chord_line(self, line: str) -> bool:
        """
        Classify line as chord line using threshold

        Args:
            line: Single line of text

        Returns:
            True if line is a chord line (>= threshold of words are chords)
        """
        if not line.strip():
            return False

        # Remove comments before processing
        line = self._strip_comment(line)

        # Remove all directive text {keyword: value} before word splitting
        # This prevents content inside directives from being counted
        line_without_directives = re.sub(r'\{[^}]+\}', '', line)

        # Split into words
        words = line_without_directives.split()
        if not words:
            return False

        # Filter out punctuation-only words (like "-", "|", etc.)
        # Only count words that contain at least one alphanumeric character
        alphanumeric_words = [w for w in words if any(c.isalnum() for c in w)]

        if not alphanumeric_words:
            return False

        # Select patterns based on notation
        if self.notation == 'european':
            patterns = [self.CHORD_PATTERN_EUROPEAN, self.CHORD_PATTERN_ROMAN]
        else:
            patterns = [self.CHORD_PATTERN_AMERICAN, self.CHORD_PATTERN_ROMAN]

        # Count how many words match any chord pattern
        chord_count = 0
        for word in alphanumeric_words:
            # Strip duration suffix (e.g., "C*2" -> "C")
            word_without_duration = word.split('*')[0]

            for pattern in patterns:
                if pattern.fullmatch(word_without_duration):
                    chord_count += 1
                    break  # Count each word only once

        # Calculate percentage
        percentage = chord_count / len(alphanumeric_words)
        return percentage >= self.threshold

    def _extract_chords_from_line(self, line: str, line_num: int, line_offset: int) -> List[ChordInfo]:
        """
        Extract all chords from a chord line

        Args:
            line: Single line of text
            line_num: Line number (1-indexed)
            line_offset: Character offset of line start in full text

        Returns:
            List of ChordInfo objects (with additional line attribute)
        """
        results = []

        # Remove directives from the line and track position adjustments
        # This prevents content inside directives (like "G" in "{key: G}") from being detected as chords
        cleaned_line, position_map = self._remove_directives_and_map_positions(line)

        # Select patterns based on notation (include roman numeral pattern)
        if self.notation == 'european':
            patterns = [self.CHORD_PATTERN_EUROPEAN, self.CHORD_PATTERN_ROMAN]
        else:
            patterns = [self.CHORD_PATTERN_AMERICAN, self.CHORD_PATTERN_ROMAN]

        # Find all chord matches using all patterns on the cleaned line
        matches = []
        for pattern in patterns:
            for match in pattern.finditer(cleaned_line):
                matches.append((match.start(), match.end(), match.group(1), pattern))

        # Sort matches by position and remove overlaps
        matches.sort(key=lambda m: m[0])
        non_overlapping = []
        last_end = -1
        for start, end, chord_str, pattern in matches:
            if start >= last_end:
                non_overlapping.append((start, end, chord_str, pattern))
                last_end = end

        # Process each matched chord
        for start, end, chord_str_with_duration, pattern in non_overlapping:
            # Parse duration (e.g., "C*2" -> ("C", 2.0))
            duration = None
            if '*' in chord_str_with_duration:
                parts = chord_str_with_duration.split('*')
                chord_str = parts[0]
                try:
                    duration = float(parts[1])
                except (ValueError, IndexError):
                    chord_str = chord_str_with_duration  # Keep original if parse fails
            else:
                chord_str = chord_str_with_duration

            # Check if this is a roman numeral chord
            is_relative = (pattern == self.CHORD_PATTERN_ROMAN)

            # Validate chord (skip validation for roman numerals - they're context-dependent)
            if is_relative:
                is_valid = True
            else:
                is_valid = self._validate_chord(chord_str)

            # Map cleaned line positions back to original line positions
            original_start = position_map[start]
            original_end = position_map[end - 1] + 1  # Map end position

            # Calculate absolute positions in full text
            abs_start = line_offset + original_start
            abs_end = line_offset + original_end

            # Create ChordInfo object
            chord_info = ChordInfo(
                chord=chord_str,
                start=abs_start,
                end=abs_end,
                is_valid=is_valid,
                is_relative=is_relative,
                duration=duration
            )
            # Add line number as dynamic attribute
            chord_info.line = line_num

            results.append(chord_info)

        return results

    def _validate_chord(self, chord_str: str) -> bool:
        """
        Validate chord using ChordHelper

        Args:
            chord_str: Chord string (e.g., "Cmaj7", "Am/G", "c", "d", "A°7", "Bø7" or "Domaj7", "Lam/Sol")

        Returns:
            True if valid chord, False otherwise
        """
        try:
            # First convert symbols to text (° → dim, ø → m7b5)
            chord_str = self._convert_symbols_to_text(chord_str)

            # Convert to ChordHelper-compatible format
            if self.notation == 'european':
                # Convert European to American
                chord_for_validation = NotationConverter.european_to_american(chord_str)
            else:
                # Handle lowercase American notation (c = Cm, d = Dm)
                chord_for_validation = self._normalize_american_chord(chord_str)

            # Validate using ChordHelper
            is_valid = self.chord_helper.is_valid_chord(chord_for_validation)

            return is_valid
        except Exception:
            return False

    def _convert_symbols_to_text(self, chord_str: str) -> str:
        """
        Convert chord symbols to text equivalents

        Args:
            chord_str: Chord with symbols (e.g., "A°7", "Bø7", "C+")

        Returns:
            Chord with text (e.g., "Adim7", "Bm7b5", "Caug")
        """
        # ° = diminished
        # ø = half-diminished (m7b5)
        # + = augmented

        # Handle ° (diminished)
        if '°' in chord_str:
            chord_str = chord_str.replace('°', 'dim')

        # Handle ø (half-diminished)
        if 'ø' in chord_str:
            # ø means half-diminished, which is m7b5
            # But if there's a 7 after it, we need to handle it
            # Bø7 → Bm7b5
            # Bø → Bm7b5
            chord_str = chord_str.replace('ø7', 'm7b5')
            chord_str = chord_str.replace('ø', 'm7b5')

        # Handle + (augmented)
        if '+' in chord_str:
            chord_str = chord_str.replace('+', 'aug')

        return chord_str

    def _normalize_american_chord(self, chord_str: str) -> str:
        """Normalize American chord (lowercase = minor)"""
        if not chord_str:
            return chord_str

        # Check if root note is lowercase
        if chord_str[0].islower():
            # Lowercase = minor chord
            # Check for sharp/flat
            if len(chord_str) > 1 and chord_str[1] in ['#', 'b']:
                root = chord_str[:2].upper()
                suffix = chord_str[2:]
            else:
                root = chord_str[0].upper()
                suffix = chord_str[1:]

            # Add 'm' for minor if no quality is specified
            if not suffix or (len(suffix) > 0 and suffix[0] not in ['m', 'M'] and not suffix.startswith('maj') and not suffix.startswith('min')):
                return root + 'm' + suffix
            else:
                return root + suffix

        return chord_str

    def get_chord_notes(self, chord_str: str) -> Optional[List[str]]:
        """
        Get note list for a chord

        Args:
            chord_str: Chord string

        Returns:
            List of note names (e.g., ['C', 'E', 'G']) or None if invalid
        """
        is_valid = self._validate_chord(chord_str)
        if is_valid:
            # Convert chord to validation format and get notes
            chord_str = self._convert_symbols_to_text(chord_str)
            if self.notation == 'european':
                chord_for_validation = NotationConverter.european_to_american(chord_str)
            else:
                chord_for_validation = self._normalize_american_chord(chord_str)
            return self.chord_helper.get_notes(chord_for_validation)
        return None

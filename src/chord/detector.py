"""
Chord detection using line-based classification and PyChord validation
"""

import re
from pychord import Chord
from chord.converter import NotationConverter
from chord.chord_model import ChordInfo


class ChordDetector:
    """Detects chords in text using line-based classification"""

    # Basic chord pattern for initial detection (American notation, supports lowercase for minor)
    # Supports: ° (diminished), ø (half-diminished), + (augmented)
    # Supports alterations: 7b5, 7#9, 9#11, etc.
    CHORD_PATTERN_AMERICAN = re.compile(
        r'\b([A-Ga-g][#b]?(?:°|ø|\+|m|maj|min|dim|aug|sus[24]?|add\d+|\d+|[#b]\d+)*(?:/[A-Ga-g][#b]?)?)(?![A-Za-z0-9])'
    )

    # European notation pattern (Do/do for Major/minor, DoM explicit major, Dom explicit minor)
    # Supports: ° (diminished), ø (half-diminished), + (augmented)
    # Supports alterations: 7b5, 7#9, 9#11, etc.
    CHORD_PATTERN_EUROPEAN = re.compile(
        r'\b((?:Do|Re|Mi|Fa|Sol|La|Si|do|re|mi|fa|sol|la|si)[#b]?(?:°|ø|\+|M|m|maj|min|dim|aug|sus[24]?|add\d+|\d+|[#b]\d+)*(?:/(?:Do|Re|Mi|Fa|Sol|La|Si|do|re|mi|fa|sol|la|si)[#b]?)?)(?![A-Za-z0-9])'
    )

    def __init__(self, threshold=0.6, notation='american'):
        """
        Initialize chord detector

        Args:
            threshold: Percentage of words that must be chords for line classification (default 0.6)
            notation: 'american' or 'european'
        """
        self.threshold = threshold
        self.notation = notation

    def detect_chords_in_text(self, text):
        """
        Detect all chords in text with line-based classification

        Args:
            text: Full text content

        Returns:
            List of dicts with chord info: {
                'chord': str,
                'line': int,
                'start': int,
                'end': int,
                'is_valid': bool,
                'pychord_obj': Chord or None
            }
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

    def _is_chord_line(self, line):
        """
        Classify line as chord line using threshold

        Args:
            line: Single line of text

        Returns:
            True if line is a chord line (>= threshold of words are chords)
        """
        if not line.strip():
            return False

        # Split into words
        words = line.split()
        if not words:
            return False

        # Filter out punctuation-only words (like "-", "|", etc.)
        # Only count words that contain at least one alphanumeric character
        alphanumeric_words = [w for w in words if any(c.isalnum() for c in w)]

        if not alphanumeric_words:
            return False

        # Select pattern based on notation
        pattern = self.CHORD_PATTERN_EUROPEAN if self.notation == 'european' else self.CHORD_PATTERN_AMERICAN

        # Count how many words match chord pattern
        chord_count = 0
        for word in alphanumeric_words:
            if pattern.fullmatch(word):
                chord_count += 1

        # Calculate percentage
        percentage = chord_count / len(alphanumeric_words)
        return percentage >= self.threshold

    def _extract_chords_from_line(self, line, line_num, line_offset):
        """
        Extract all chords from a chord line

        Args:
            line: Single line of text
            line_num: Line number (1-indexed)
            line_offset: Character offset of line start in full text

        Returns:
            List of ChordInfo objects (with additional line, start, end attributes)
        """
        results = []

        # Select pattern based on notation
        pattern = self.CHORD_PATTERN_EUROPEAN if self.notation == 'european' else self.CHORD_PATTERN_AMERICAN

        for match in pattern.finditer(line):
            chord_str = match.group(1)
            start = line_offset + match.start()
            end = line_offset + match.end()

            # Validate with PyChord (convert European to American if needed)
            is_valid, pychord_obj = self._validate_chord(chord_str)

            # Create ChordInfo object
            chord_info = ChordInfo(
                chord=chord_str,
                line_offset=match.start(),  # Position within the line
                is_valid=is_valid,
                pychord_obj=pychord_obj
            )
            # Add extra attributes for full text positioning
            chord_info.line = line_num
            chord_info.start = start
            chord_info.end = end

            results.append(chord_info)

        return results

    def _validate_chord(self, chord_str):
        """
        Validate chord using PyChord

        Args:
            chord_str: Chord string (e.g., "Cmaj7", "Am/G", "c", "d", "A°7", "Bø7" or "Domaj7", "Lam/Sol")

        Returns:
            Tuple of (is_valid, pychord_obj or None)
        """
        try:
            # First convert symbols to text (° → dim, ø → m7b5)
            chord_str = self._convert_symbols_to_text(chord_str)

            # Convert to PyChord-compatible format
            if self.notation == 'european':
                # Convert European to American
                chord_for_validation = NotationConverter.european_to_american(chord_str)
            else:
                # Handle lowercase American notation (c = Cm, d = Dm)
                chord_for_validation = self._normalize_american_chord(chord_str)

            chord_obj = Chord(chord_for_validation)
            return (True, chord_obj)
        except Exception:
            return (False, None)

    def _convert_symbols_to_text(self, chord_str):
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

    def _normalize_american_chord(self, chord_str):
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
            if not suffix or (suffix[0] not in ['m', 'M'] and not suffix.startswith('maj') and not suffix.startswith('min')):
                return root + 'm' + suffix
            else:
                return root + suffix

        return chord_str

    def get_chord_notes(self, chord_str):
        """
        Get note list for a chord

        Args:
            chord_str: Chord string

        Returns:
            List of note names (e.g., ['C', 'E', 'G']) or None if invalid
        """
        is_valid, chord_obj = self._validate_chord(chord_str)
        if is_valid:
            return chord_obj.components()
        return None

"""Chord detection service wrapping chord detection logic."""

import logging
from typing import List

from chord.detector import ChordDetector
from chord.helper import ChordHelper
from chord.converter import NotationConverter
from chord.line_model import Line
from chord.chord_model import ChordInfo


class ChordDetectionService:
    """Manages chord detection operations.

    Provides a high-level interface for chord detection, validation, and conversion.
    """

    def __init__(self):
        self._detector = ChordDetector()
        self._helper = ChordHelper()
        self._converter = NotationConverter()
        self._logger = logging.getLogger(__name__)

    def detect_chords_in_text(self, text: str, notation: str = "american") -> List[Line]:
        """Detect chords in a block of text.

        Args:
            text: Text content to analyze
            notation: Notation system to use ("american" or "european")

        Returns:
            List of Line objects with detected chords
        """
        self._logger.debug(f"Detecting chords in text using {notation} notation")
        lines = self._detector.detect_chords(text, notation)
        self._logger.debug(f"Detected {len(lines)} lines")
        return lines

    def detect_chords_in_line(self, line_text: str, line_number: int, notation: str = "american") -> Line:
        """Detect chords in a single line.

        Args:
            line_text: Line content to analyze
            line_number: Line number (1-indexed)
            notation: Notation system to use

        Returns:
            Line object with detected chords
        """
        lines = self._detector.detect_chords(line_text, notation)
        if lines:
            line = lines[0]
            # Update line number to match provided value
            line.line_number = line_number
            return line
        else:
            # Return empty line
            return Line(content=line_text, line_number=line_number, type="text", chords=[])

    def validate_chord(self, chord_text: str, notation: str = "american") -> bool:
        """Validate if a string is a valid chord.

        Args:
            chord_text: Chord string to validate
            notation: Notation system to use

        Returns:
            True if valid chord, False otherwise
        """
        # Convert to american notation for validation if needed
        if notation == "european":
            chord_text = self._converter.european_to_american(chord_text)

        return self._helper.is_valid_chord(chord_text)

    def get_chord_notes(self, chord_text: str, notation: str = "american") -> List[str]:
        """Get the note names that make up a chord.

        Args:
            chord_text: Chord string (e.g., "C", "Dm7", "G7")
            notation: Notation system

        Returns:
            List of note names (e.g., ['C', 'E', 'G'])
        """
        # Convert to american notation for processing
        if notation == "european":
            chord_text = self._converter.european_to_american(chord_text)

        notes = self._helper.get_notes(chord_text)
        return notes if notes else []

    def convert_to_american(self, text: str) -> str:
        """Convert text from European to American notation.

        Args:
            text: Text in European notation

        Returns:
            Text in American notation
        """
        return self._converter.european_to_american(text)

    def convert_to_european(self, text: str) -> str:
        """Convert text from American to European notation.

        Args:
            text: Text in American notation

        Returns:
            Text in European notation
        """
        return self._converter.american_to_european(text)

    def identify_chord_from_notes(self, notes: List[str]) -> List[str]:
        """Identify possible chord names from a set of notes.

        Args:
            notes: List of note names (e.g., ['C', 'E', 'G'])

        Returns:
            List of possible chord names (e.g., ['C', 'Cmaj'])
        """
        chords = self._helper.identify_chord(notes)
        return chords if chords else []

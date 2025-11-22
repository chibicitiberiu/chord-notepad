"""ViewModel for the chord text editor."""

import logging
from typing import List, Optional, Tuple
from utils.observable import Observable
from services.chord_detection_service import ChordDetectionService
from chord.line_model import Line
from chord.chord_model import ChordInfo

logger = logging.getLogger(__name__)


class TextEditorViewModel(Observable):
    """ViewModel for the chord text editor.

    Manages chord detection, highlighting, and cursor interaction logic.
    """

    def __init__(self, chord_detection_service: ChordDetectionService):
        """Initialize the ViewModel.

        Args:
            chord_detection_service: Service for chord detection
        """
        super().__init__()

        self._chord_service = chord_detection_service

        # Observable state
        self._detected_lines: List[Line] = []
        self._current_notation: str = "american"
        self._current_playing_chord: Optional[ChordInfo] = None

    @property
    def detected_lines(self) -> List[Line]:
        """Get the detected chord lines."""
        return self._detected_lines

    @property
    def current_notation(self) -> str:
        """Get the current notation system."""
        return self._current_notation

    @property
    def current_playing_chord(self) -> Optional[ChordInfo]:
        """Get the currently playing chord (if any)."""
        return self._current_playing_chord

    def on_text_changed(self, text: str) -> None:
        """Handle text content changes and detect chords.

        Args:
            text: The current text content
        """
        logger.debug("Detecting chords in text")
        detected_lines = self.detect_chords(text)
        self.set_and_notify("detected_lines", detected_lines)

    def detect_chords(self, text: str) -> List[Line]:
        """Detect chords in the given text.

        Args:
            text: Text to analyze

        Returns:
            List of Line objects with detected chords
        """
        try:
            lines = self._chord_service.detect_chords_in_text(text, self._current_notation)
            logger.debug(f"Detected {len(lines)} lines with chords")
            return lines
        except Exception as e:
            logger.error(f"Error detecting chords: {e}", exc_info=True)
            return []

    def convert_notation(self, text: str, to_notation: str) -> str:
        """Convert text to a different notation system.

        Args:
            text: Text to convert
            to_notation: Target notation ("american" or "european")

        Returns:
            Converted text
        """
        if to_notation not in ("american", "european"):
            logger.warning(f"Invalid notation: {to_notation}")
            return text

        try:
            if to_notation == "european":
                converted = self._chord_service.convert_to_european(text)
            else:
                converted = self._chord_service.convert_to_american(text)

            self.set_and_notify("current_notation", to_notation)
            return converted

        except Exception as e:
            logger.error(f"Error converting notation: {e}", exc_info=True)
            return text

    def set_notation(self, notation: str) -> None:
        """Set the current notation system.

        Args:
            notation: "american" or "european"
        """
        if notation in ("american", "european"):
            self.set_and_notify("current_notation", notation)

    def get_chord_at_position(self, line_number: int, column: int) -> Optional[ChordInfo]:
        """Get the chord at a specific cursor position.

        Args:
            line_number: Line number (1-indexed)
            column: Column position (0-indexed)

        Returns:
            ChordInfo if a chord exists at that position, None otherwise
        """
        # Line numbers in our model are 1-indexed
        if line_number < 1 or line_number > len(self._detected_lines):
            return None

        line = self._detected_lines[line_number - 1]

        # Check if this is a chord line
        if line.type != "chord":
            return None

        # Find chord at column position
        for chord in line.chords:
            chord_start = chord.line_offset
            chord_end = chord_start + len(chord.chord)

            if chord_start <= column < chord_end:
                return chord

        return None

    def set_playing_chord(self, chord: Optional[ChordInfo]) -> None:
        """Set the currently playing chord for highlighting.

        Args:
            chord: Chord being played, or None to clear
        """
        self.set_and_notify("current_playing_chord", chord)

    def get_chord_ranges(self, line_number: int) -> List[Tuple[int, int, bool]]:
        """Get chord ranges for a specific line for highlighting.

        Args:
            line_number: Line number (1-indexed)

        Returns:
            List of (start, end, is_valid) tuples for each chord in the line
        """
        if line_number < 1 or line_number > len(self._detected_lines):
            return []

        line = self._detected_lines[line_number - 1]

        if line.type != "chord":
            return []

        ranges = []
        for chord in line.chords:
            start = chord.line_offset
            end = start + len(chord.chord)
            is_valid = chord.is_valid
            ranges.append((start, end, is_valid))

        return ranges

    def get_all_chords(self) -> List[ChordInfo]:
        """Get all chords from all detected lines.

        Returns:
            List of all ChordInfo objects
        """
        all_chords = []
        for line in self._detected_lines:
            all_chords.extend(line.chords)
        return all_chords

    def validate_chord(self, chord_text: str) -> bool:
        """Validate if a string is a valid chord.

        Args:
            chord_text: Chord string to validate

        Returns:
            True if valid, False otherwise
        """
        return self._chord_service.validate_chord(chord_text, self._current_notation)

    def get_chord_notes(self, chord_text: str) -> List[str]:
        """Get the notes that make up a chord.

        Args:
            chord_text: Chord string

        Returns:
            List of note names
        """
        return self._chord_service.get_chord_notes(chord_text, self._current_notation)

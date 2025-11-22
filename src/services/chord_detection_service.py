"""Chord detection service wrapping chord detection logic."""

import logging
from typing import List, Union

from chord.detector import ChordDetector
from chord.helper import ChordHelper
from chord.converter import NotationConverter
from chord.line_model import Line
from chord.chord_model import ChordInfo
from models.notation import Notation


class ChordDetectionService:
    """Manages chord detection operations.

    Provides a high-level interface for chord detection, validation, and conversion.
    """

    def __init__(self):
        self._helper = ChordHelper()
        self._converter = NotationConverter()
        self._logger = logging.getLogger(__name__)

    def detect_chords_in_text(self, text: str, notation: Union[Notation, str] = "american") -> List[Line]:
        """Detect chords in a block of text.

        Args:
            text: Text content to analyze
            notation: Notation system (Notation enum or "american"/"european" string)

        Returns:
            List of Line objects with detected chords
        """
        # Convert Notation enum to string if needed
        notation_str = notation.value if isinstance(notation, Notation) else notation
        self._logger.debug(f"Detecting chords in text using {notation_str} notation")

        # Create detector with the specified notation
        detector = ChordDetector(notation=notation_str)

        # Get chord detections
        chord_infos = detector.detect_chords_in_text(text)
        self._logger.debug(f"Detected {len(chord_infos)} chords")

        # Convert to Line objects
        lines = self._convert_chord_infos_to_lines(text, chord_infos)
        self._logger.debug(f"Created {len(lines)} Line objects")

        return lines

    def detect_chords_in_line(self, line_text: str, line_number: int, notation: Union[Notation, str] = "american") -> Line:
        """Detect chords in a single line.

        Args:
            line_text: Line content to analyze
            line_number: Line number (1-indexed)
            notation: Notation system (Notation enum or string)

        Returns:
            Line object with detected chords
        """
        # Convert Notation enum to string if needed
        notation_str = notation.value if isinstance(notation, Notation) else notation

        # Create detector with the specified notation
        detector = ChordDetector(notation=notation_str)

        # Get chord detections for this line
        chord_infos = detector.detect_chords_in_text(line_text)

        # Filter to chords on line 1 (since we're only analyzing one line)
        line_chords = [c for c in chord_infos if c.line == 1]

        if line_chords:
            # Create chord line
            line = Line(content=line_text, line_number=line_number)
            line.set_as_chord_line(line_chords)
            return line
        else:
            # Return empty text line
            return Line(content=line_text, line_number=line_number)

    def _convert_chord_infos_to_lines(self, text: str, chord_infos: List[ChordInfo]) -> List[Line]:
        """Convert ChordInfo objects to Line objects.

        Args:
            text: Original text
            chord_infos: List of detected chords

        Returns:
            List of Line objects
        """
        lines = []
        text_lines = text.split('\n')

        # Group chords by line number
        chords_by_line = {}
        for chord_info in chord_infos:
            line_num = chord_info.line
            if line_num not in chords_by_line:
                chords_by_line[line_num] = []
            chords_by_line[line_num].append(chord_info)

        # Create Line objects for each text line
        for line_num, content in enumerate(text_lines, start=1):
            line = Line(content=content, line_number=line_num)

            if line_num in chords_by_line:
                # This is a chord line
                line.set_as_chord_line(chords_by_line[line_num])
            else:
                # This is a text line
                line.set_as_text_line()

            lines.append(line)

        return lines

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

    def identify_chord_from_notes(self, notes: List[str], bass_note: str = None) -> List[str]:
        """Identify possible chord names from a set of notes.

        Args:
            notes: List of note names (e.g., ['C', 'E', 'G'])
            bass_note: Optional bass note for slash chords

        Returns:
            List of possible chord names (e.g., ['C', 'Cmaj', 'C/G'])
        """
        chords = self._helper.identify_chord(notes, bass_note)
        return chords if chords else []

    def chord_to_midi(self, chord_name: str, base_octave: int = 4) -> List[int]:
        """Convert a chord name to MIDI note numbers.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            base_octave: Base octave for the chord root

        Returns:
            List of MIDI note numbers
        """
        midi_notes = self._helper.chord_to_midi(chord_name, base_octave)
        return midi_notes if midi_notes else []

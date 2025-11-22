"""
Chord model for storing chord information
"""


class ChordInfo:
    """Represents a detected chord with its metadata"""

    def __init__(self, chord, line_offset, is_valid=True, notes=None):
        """
        Initialize a chord

        Args:
            chord: The chord string (e.g., "C", "Am", "Do", "rem")
            line_offset: Position within the line where the chord appears
            is_valid: Whether the chord is valid according to ChordHelper
            notes: List of note names (e.g., ['C', 'E', 'G']) if valid, None otherwise
        """
        self.chord = chord
        self.line_offset = line_offset
        self.is_valid = is_valid
        self.notes = notes if notes else []

    def __repr__(self):
        return f"ChordInfo(chord='{self.chord}', offset={self.line_offset}, valid={self.is_valid})"

    def __len__(self):
        """Return length of chord string for convenience"""
        return len(self.chord)

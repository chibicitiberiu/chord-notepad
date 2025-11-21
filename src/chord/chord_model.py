"""
Chord model for storing chord information
"""


class ChordInfo:
    """Represents a detected chord with its metadata"""

    def __init__(self, chord, line_offset, is_valid=True, pychord_obj=None):
        """
        Initialize a chord

        Args:
            chord: The chord string (e.g., "C", "Am", "Do", "rem")
            line_offset: Position within the line where the chord appears
            is_valid: Whether the chord is valid according to PyChord
            pychord_obj: PyChord Chord object if valid, None otherwise
        """
        self.chord = chord
        self.line_offset = line_offset
        self.is_valid = is_valid
        self.pychord_obj = pychord_obj

    def __repr__(self):
        return f"ChordInfo(chord='{self.chord}', offset={self.line_offset}, valid={self.is_valid})"

    def __len__(self):
        """Return length of chord string for convenience"""
        return len(self.chord)

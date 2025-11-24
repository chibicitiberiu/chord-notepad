"""
Chord model for storing chord information
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChordInfo:
    """Represents a detected chord with its metadata.

    This is a dataclass that stores comprehensive information about a chord,
    including its position, validity, notes, and musical properties.
    """

    # Core properties
    chord: str
    """The chord string (e.g., "C", "Am", "Do", "rem", "I", "V7", "C/G", "vi/I")"""

    start: int
    """Character position where chord starts in the full text"""

    end: int
    """Character position where chord ends in the full text"""

    is_valid: bool = True
    """Whether the chord is valid"""

    is_relative: bool = False
    """Whether this is a relative chord (roman numeral) that depends on the current key"""

    duration: Optional[float] = None
    """Duration of the chord in beats"""

    def __repr__(self) -> str:
        """String representation of the chord."""
        return f"ChordInfo(chord='{self.chord}', start={self.start}, end={self.end}, valid={self.is_valid})"

    def __len__(self) -> int:
        """Return length of chord string for convenience."""
        return len(self.chord)

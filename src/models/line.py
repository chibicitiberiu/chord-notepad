"""
Line model for storing text lines with metadata
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Union
from models.chord import ChordInfo
from models.directive import Directive


class LineType(IntEnum):
    """Enum for line types."""
    TEXT = 0
    CHORD = 1


@dataclass
class Line:
    """Represents a line of text with metadata and chord information.

    This dataclass stores information about a line in the text editor,
    including its content, line number, type classification, and detected chords.
    """

    content: str
    """The text content of the line"""

    line_number: int
    """Line number (1-indexed)"""

    type: Optional[LineType] = None
    """Line type: LineType.CHORD for chord lines, LineType.TEXT for text lines"""

    items: List[Union[ChordInfo, Directive]] = field(default_factory=list)
    """List of ChordInfo or Directive objects for chord/directive lines"""

    def __post_init__(self) -> None:
        """Validate line data after initialization."""
        if self.line_number < 1:
            raise ValueError(f"Line number must be >= 1, got {self.line_number}")

        # Ensure items list is empty for text lines
        if self.type == LineType.TEXT and self.items:
            self.items = []

    def is_chord_line(self) -> bool:
        """Check if this is a chord line.

        Returns:
            True if line type is LineType.CHORD, False otherwise
        """
        return self.type == LineType.CHORD

    def is_text_line(self) -> bool:
        """Check if this is a text/lyric line.

        Returns:
            True if line type is LineType.TEXT, False otherwise
        """
        return self.type == LineType.TEXT

    def set_as_chord_line(self, chords: List[ChordInfo]) -> None:
        """Mark this line as a chord line with detected chords.

        Args:
            chords: List of ChordInfo objects detected in this line
        """
        self.type = LineType.CHORD
        self.items = chords

    def set_as_text_line(self) -> None:
        """Mark this line as a text/lyric line."""
        self.type = LineType.TEXT
        self.items = []

    @property
    def chords(self) -> List[ChordInfo]:
        """Get only the chord items from this line.

        Returns:
            List of ChordInfo objects (filtering out directives)
        """
        return [item for item in self.items if isinstance(item, ChordInfo)]

    @property
    def directives(self) -> List[Directive]:
        """Get only the directive items from this line.

        Returns:
            List of Directive objects (filtering out chords)
        """
        return [item for item in self.items if isinstance(item, Directive)]

    def get_valid_chords(self) -> List[ChordInfo]:
        """Get only the valid chords from this line.

        Returns:
            List of valid ChordInfo objects
        """
        return [chord for chord in self.chords if chord.is_valid]

    def get_invalid_chords(self) -> List[ChordInfo]:
        """Get only the invalid chords from this line.

        Returns:
            List of invalid ChordInfo objects
        """
        return [chord for chord in self.chords if not chord.is_valid]

    def has_chords(self) -> bool:
        """Check if this line has any chords.

        Returns:
            True if line has chords, False otherwise
        """
        return len(self.chords) > 0

    def chord_count(self) -> int:
        """Get the total number of chords in this line.

        Returns:
            Number of chords
        """
        return len(self.chords)

    def __repr__(self) -> str:
        """String representation of the line."""
        content_preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"Line({self.line_number}, type={self.type}, content='{content_preview}')"

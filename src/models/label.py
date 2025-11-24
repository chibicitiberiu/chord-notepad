"""
Label model for marking positions in a song
"""

from dataclasses import dataclass


@dataclass
class Label:
    """Represents a label marker in the song.

    Labels mark specific positions in the song, typically used with loop directives.
    """

    name: str
    """Name/identifier of the label"""

    line_number: int
    """Line number where the label appears (1-indexed)"""

    offset: int
    """Character offset within the line where the label appears"""

    def __repr__(self) -> str:
        """String representation of the label."""
        return f"Label(name='{self.name}', line={self.line_number}, offset={self.offset})"

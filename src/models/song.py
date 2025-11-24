"""
Song model representing an entire song file
"""

from dataclasses import dataclass, field
from typing import List, Dict
from models.line import Line
from models.label import Label


@dataclass
class Song:
    """Represents an entire song made up of lines.

    A song contains all the lines of text/chords/directives and a dictionary
    of labels for navigation and loop markers.
    """

    lines: List[Line] = field(default_factory=list)
    """List of lines in the song"""

    labels: Dict[str, Label] = field(default_factory=dict)
    """Dictionary of labels, keyed by label name"""

    def add_line(self, line: Line) -> None:
        """Add a line to the song.

        Args:
            line: Line object to add
        """
        self.lines.append(line)

    def add_label(self, label: Label) -> None:
        """Add a label to the song.

        Args:
            label: Label object to add
        """
        self.labels[label.name] = label

    def get_label(self, name: str) -> Label | None:
        """Get a label by name.

        Args:
            name: Label name to look up

        Returns:
            Label object if found, None otherwise
        """
        return self.labels.get(name)

    def line_count(self) -> int:
        """Get the total number of lines in the song.

        Returns:
            Number of lines
        """
        return len(self.lines)

    def __repr__(self) -> str:
        """String representation of the song."""
        return f"Song(lines={len(self.lines)}, labels={len(self.labels)})"

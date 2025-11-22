"""Notation system enumeration."""

from enum import Enum


class Notation(str, Enum):
    """Chord notation system.

    Inherits from str to allow easy serialization and comparison with strings.
    """
    AMERICAN = "american"
    EUROPEAN = "european"

    def __str__(self) -> str:
        """Return the string value."""
        return self.value

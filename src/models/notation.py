"""Notation system enumeration."""

from enum import Enum
from typing import Tuple


class Notation(str, Enum):
    """Chord notation system.

    Inherits from str to allow easy serialization and comparison with strings.
    """
    AMERICAN = "american"
    EUROPEAN = "european"

    def __str__(self) -> str:
        """Return the string value."""
        return self.value


#: The key names each notation offers, index-aligned (C <-> Do, Db <-> Reb...).
#: The config stores keys in American spelling; a view shows them in its
#: notation (:func:`spell_key`).
AMERICAN_KEYS = (
    "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#",
    "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
)
EUROPEAN_KEYS = (
    "Do", "Do#", "Reb", "Re", "Re#", "Mib", "Mi", "Fa", "Fa#",
    "Solb", "Sol", "Sol#", "Lab", "La", "La#", "Sib", "Si",
)


def key_names(notation: str) -> Tuple[str, ...]:
    """The keys ``notation`` offers, in order (raises ValueError for an unknown notation)."""
    return EUROPEAN_KEYS if Notation(notation) is Notation.EUROPEAN else AMERICAN_KEYS


def american_key(key: str) -> str:
    """``key`` in American spelling ("Sol" -> "G"); "" and unknown keys stay as they are."""
    if key in EUROPEAN_KEYS:
        return AMERICAN_KEYS[EUROPEAN_KEYS.index(key)]
    return key


def spell_key(key: str, notation: str) -> str:
    """``key`` (either spelling) spelled in ``notation`` ("G" -> "Sol" for
    European); "" and unknown keys stay as they are."""
    key = american_key(key)
    if Notation(notation) is Notation.EUROPEAN and key in AMERICAN_KEYS:
        return EUROPEAN_KEYS[AMERICAN_KEYS.index(key)]
    return key

"""
ChordNotes model - represents resolved chord notes
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ChordNotes:
    """Result of chord note computation.

    Attributes:
        notes: List of note names in the chord (e.g., ['C', 'E', 'G'])
        bass_note: The bass note (may differ from root for slash chords)
        root: The root note of the chord
    """
    notes: List[str]
    bass_note: str
    root: str

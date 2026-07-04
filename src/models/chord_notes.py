"""
ChordNotes model - represents resolved chord notes
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChordNotes:
    """Result of chord note computation.

    Attributes:
        notes: List of note names in the chord (e.g., ['C', 'E', 'G'])
        bass_note: The bass note (may differ from root for slash chords)
        root: The root note of the chord
        intervals: Semitones of each note above the root, register-preserving
            and positionally aligned with ``notes`` (root is 0, a 9th is 14,
            an 11th is 17, a 13th is 21). This carries the chord's intended
            register - which octave an extension belongs in - through to the
            voicer, instead of it being re-guessed from note ordering. Optional
            for backward compatibility; when absent the picker reconstructs it
            from ``notes``.
    """
    notes: List[str]
    bass_note: str
    root: str
    intervals: Optional[List[int]] = None

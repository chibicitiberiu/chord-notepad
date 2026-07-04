"""
Interface for note pickers (Piano, Guitar, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes


class INotePicker(ABC):
    """Interface for chord-to-MIDI converters with voice leading"""

    @abstractmethod
    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """
        Convert chord to MIDI notes

        Args:
            chord_notes: ChordNotes object with notes, bass_note, and root

        Returns:
            List of MIDI note numbers
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state for new playback session"""
        pass

    @property
    @abstractmethod
    def state(self):
        """Get current state (implementation-specific)"""
        pass

    @state.setter
    @abstractmethod
    def state(self, value) -> None:
        """Set current state (implementation-specific)"""
        pass

    def voice_sequence(self, sequence: List['ChordNotes']) -> List[List[int]]:
        """Voice an entire song in order.

        Deterministic: the same sequence always yields the same voicings,
        regardless of prior picker state. The default implementation resets and
        voices greedily chord-by-chord; pickers that can do better (e.g. by
        optimizing the whole sequence with lookahead) should override this.

        Args:
            sequence: The chords to voice, in playback order.

        Returns:
            One MIDI-note list per chord, positionally aligned with ``sequence``.
        """
        self.reset()
        return [self.chord_to_midi(cn) for cn in sequence]

    @property
    def voice_labels(self) -> Optional[List[str]]:
        """Ordered voice names (top voice first), or ``None``.

        Populated by pickers that voice a fixed ensemble of monophonic voices
        (e.g. an SATB voicer): such pickers guarantee that ``voice_sequence``
        emits exactly one note per voice per chord, ordered LOW to HIGH
        (bottom voice first), with duplicates allowed for unisons. ``None``
        for free-voiced pickers (piano, guitar), which is the default.
        """
        return None

"""
Interface for note pickers (Piano, Guitar, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

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

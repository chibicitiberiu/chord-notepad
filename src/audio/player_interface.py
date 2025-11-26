"""Interface for audio player implementations."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Callable, Optional


class IPlayer(ABC):
    """Interface for audio player."""

    @abstractmethod
    def play_notes_immediate(self, midi_notes: List[int]) -> None:
        """Play notes immediately (for click-to-play).

        Args:
            midi_notes: List of MIDI note numbers to play
        """
        pass

    @abstractmethod
    def start_playback(self) -> None:
        """Start playback."""
        pass

    @abstractmethod
    def pause_playback(self) -> None:
        """Pause playback."""
        pass

    @abstractmethod
    def resume_playback(self) -> None:
        """Resume playback."""
        pass

    @abstractmethod
    def stop_playback(self) -> None:
        """Stop playback."""
        pass

    @abstractmethod
    def set_bpm(self, bpm: int) -> None:
        """Set the playback tempo.

        Args:
            bpm: Beats per minute
        """
        pass

    @abstractmethod
    def set_playback_finished_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when playback finishes.

        Args:
            callback: Function to call when playback ends
        """
        pass

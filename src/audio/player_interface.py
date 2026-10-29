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
    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Set the playback speed multiplier applied on top of the BPM.

        Args:
            multiplier: Speed multiplier (e.g. 1.0 = normal, 0.5 = half speed)
        """
        pass

    @abstractmethod
    def set_playback_finished_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when playback finishes.

        Args:
            callback: Function to call when playback ends
        """
        pass

    def suspend_audio(self) -> bool:
        """Release the audio output device while keeping the loaded state.

        For hosts whose app can be backgrounded (Android). Desktop never
        calls it. Refuses while a song is actively playing.

        Returns:
            True if the output was released; False if nothing was released.
        """
        return False

    def resume_audio(self) -> bool:
        """Reopen the audio output released by :meth:`suspend_audio`.

        Returns:
            True if the output is open (or never was released); False if it
            could not be reopened (the player stays suspended).
        """
        return True

    @property
    def audio_suspended(self) -> bool:
        """True while the audio output is released by :meth:`suspend_audio`."""
        return False

"""Audio playback service wrapping NotePlayer."""

import logging
from typing import Optional, List, Callable

from audio.player import NotePlayer
from audio.chord_picker import ChordNotePicker
from chord.chord_model import ChordInfo
from services.config_service import ConfigService


class AudioService:
    """High-level audio playback orchestration service.

    Provides business-level API for audio playback, abstracting FluidSynth/NotePlayer details.
    """

    def __init__(self, config_service: ConfigService):
        self._config = config_service
        self._player: Optional[NotePlayer] = None
        self._note_picker = ChordNotePicker()
        self._logger = logging.getLogger(__name__)
        self._initialized = False

    def initialize_player(self, soundfont_path: Optional[str] = None) -> bool:
        """Initialize the audio player.

        Args:
            soundfont_path: Optional path to soundfont file (.sf2)

        Returns:
            True if initialized successfully, False otherwise
        """
        if self._initialized:
            self._logger.debug("Audio player already initialized")
            return True

        try:
            # Get config values
            bpm = self._config.get("bpm", 120)
            sf_path = soundfont_path or self._config.get("soundfont_path")

            # Create player
            self._logger.info("Initializing audio player")
            self._player = NotePlayer(soundfont_path=sf_path, bpm=bpm)
            self._initialized = True
            self._logger.info("Audio player initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize audio player: {e}", exc_info=True)
            self._player = None
            self._initialized = False
            return False

    def play_chord_immediate(self, chord_info: ChordInfo) -> None:
        """Play a chord immediately (click-to-play).

        Args:
            chord_info: Chord information with notes
        """
        if not self._ensure_initialized():
            return

        try:
            # Get MIDI notes from chord
            midi_notes = self._note_picker.chord_to_midi(
                notes=chord_info.notes,
                add_bass=True,
                chord_octave=self._config.get("default_octave", 4),
                bass_octave=self._config.get("bass_octave", 3)
            )

            if midi_notes:
                self._logger.debug(f"Playing chord immediately: {chord_info.chord}")
                self._player.play_notes_immediate(midi_notes)
            else:
                self._logger.warning(f"Could not convert chord to MIDI notes: {chord_info.chord}")

        except Exception as e:
            self._logger.error(f"Error playing chord: {e}", exc_info=True)

    def start_sequential_playback(
        self,
        get_next_callback: Callable,
        on_finished_callback: Optional[Callable] = None
    ) -> None:
        """Start sequential chord playback.

        Args:
            get_next_callback: Callback that returns (midi_notes, duration_beats) or None
            on_finished_callback: Optional callback when playback finishes
        """
        if not self._ensure_initialized():
            return

        try:
            self._logger.info("Starting sequential playback")
            self._player.set_next_note_callback(get_next_callback)

            if on_finished_callback:
                self._player.set_playback_finished_callback(on_finished_callback)

            self._player.start_playback()

        except Exception as e:
            self._logger.error(f"Error starting playback: {e}", exc_info=True)

    def pause_playback(self) -> None:
        """Pause ongoing playback."""
        if self._player:
            self._logger.debug("Pausing playback")
            self._player.pause_playback()

    def resume_playback(self) -> None:
        """Resume paused playback."""
        if self._player:
            self._logger.debug("Resuming playback")
            self._player.resume_playback()

    def stop_playback(self) -> None:
        """Stop ongoing playback."""
        if self._player:
            self._logger.debug("Stopping playback")
            self._player.stop_playback()

    def set_bpm(self, bpm: int) -> None:
        """Change playback speed.

        Args:
            bpm: Beats per minute (60-240)
        """
        if self._player:
            self._logger.debug(f"Setting BPM to {bpm}")
            self._player.set_bpm(bpm)
            self._config.set("bpm", bpm)

    def set_instrument(self, program: int) -> None:
        """Change MIDI instrument.

        Args:
            program: MIDI program number (0-127)
                     0 = Acoustic Grand Piano
                     24-31 = Guitars
                     40-47 = Strings
                     56-63 = Brass
        """
        if self._player:
            self._logger.debug(f"Setting instrument to program {program}")
            self._player.set_instrument(program)

    def cleanup(self) -> None:
        """Cleanup audio resources."""
        if self._player:
            self._logger.info("Cleaning up audio player")
            self._player.cleanup()
            self._player = None
            self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Ensure player is initialized, initialize if needed.

        Returns:
            True if initialized, False if initialization failed
        """
        if not self._initialized:
            return self.initialize_player()
        return True

    @property
    def is_initialized(self) -> bool:
        """Check if audio player is initialized."""
        return self._initialized

    @property
    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._player.is_playing if self._player else False

    @property
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._player.is_paused if self._player else False

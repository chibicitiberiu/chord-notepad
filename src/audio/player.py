"""
Audio playback using FluidSynth
"""

import logging
import os
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Dict
import fluidsynth
from audio.player_interface import IPlayer

logger = logging.getLogger(__name__)


class NotePlayer(IPlayer):
    """Audio player for MIDI notes using FluidSynth"""

    def __init__(self, soundfont_path: Optional[str] = None, bpm: int = 120, time_signature: Tuple[int, int] = (4, 4)) -> None:
        """
        Initialize the note player

        Args:
            soundfont_path: Path to soundfont file (.sf2)
            bpm: Beats per minute (default 120)
            time_signature: Tuple of (beats_per_measure, beat_unit) (default 4/4)
        """
        self.fs = None
        self.sfid = None
        self.channel = 0
        self.instrument = 0  # Acoustic Grand Piano by default

        # Timing information
        self.bpm = bpm
        self.time_signature = time_signature

        # Playback thread and state
        self.playback_thread = None
        self.is_playing = False
        self.is_paused = False
        self.stop_event = None
        self.pause_event = None
        self._state_lock = threading.Lock()  # Protects is_playing and is_paused

        # Callback to get next note (should return (midi_notes, duration_beats) or None)
        self.get_next_note_callback = None

        # Callback when playback finishes
        self.on_playback_finished_callback = None

        # Find soundfont
        if soundfont_path is None:
            soundfont_path = self._find_soundfont()

        if soundfont_path and os.path.exists(soundfont_path):
            self._initialize_fluidsynth(soundfont_path)
        else:
            raise FileNotFoundError(f"Soundfont not found at: {soundfont_path}")

    def _find_soundfont(self) -> Optional[str]:
        """Find the bundled soundfont"""
        import sys

        # Check if running from PyInstaller bundle
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running from PyInstaller bundle
            base_dir = Path(sys._MEIPASS)
        else:
            # Running from source
            base_dir = Path(__file__).parent.parent.parent

        sf_path = base_dir / 'resources' / 'soundfont' / 'GeneralUser-GS.sf2'

        if sf_path.exists():
            return str(sf_path)

        return None

    def _initialize_fluidsynth(self, soundfont_path: str) -> None:
        """Initialize FluidSynth with the soundfont"""
        try:
            # Create FluidSynth instance
            logger.debug("Creating FluidSynth instance...")
            self.fs = fluidsynth.Synth()
            logger.debug("FluidSynth instance created")

            # Set gain (volume) - 0.0 to 10.0, default is 0.2
            logger.debug("Setting gain...")
            self.fs.setting('synth.gain', 0.5)
            logger.debug("Gain set")

            # Start audio output
            # Try different drivers in order of preference
            drivers = ['alsa', 'pulseaudio', 'oss']
            started = False

            for driver in drivers:
                try:
                    result = self.fs.start(driver=driver)
                    if result == 0:  # Success
                        logger.info(f"FluidSynth started with driver: {driver}")
                        started = True
                        break
                except Exception as e:
                    logger.debug(f"Failed to start with {driver}: {e}")
                    continue

            if not started:
                raise Exception("Could not start FluidSynth with any audio driver")

            # Load soundfont
            self.sfid = self.fs.sfload(soundfont_path)
            logger.info(f"Loaded soundfont: {soundfont_path}, ID: {self.sfid}")

            # Select instrument (program)
            self.fs.program_select(self.channel, self.sfid, 0, self.instrument)

        except Exception as e:
            logger.error(f"Failed to initialize FluidSynth: {e}", exc_info=True)
            self.fs = None

    def get_available_instruments(self) -> List[Tuple[int, str]]:
        """
        Get list of available instruments from the loaded soundfont

        Returns:
            List of tuples (program_number, instrument_name)
        """
        instruments = []
        if self.fs and self.sfid is not None:
            # Bank 0 contains melodic instruments (GM standard: 0-127)
            bank = 0
            for program in range(128):
                try:
                    name = self.fs.sfpreset_name(self.sfid, bank, program)
                    if name:
                        instruments.append((program, name))
                except Exception:
                    # Preset doesn't exist, skip
                    pass
        return instruments

    def get_current_instrument(self) -> int:
        """
        Get the current instrument program number

        Returns:
            Current MIDI program number (0-127)
        """
        return self.instrument

    def set_instrument(self, program: int) -> None:
        """
        Change the instrument

        Args:
            program: MIDI program number (0-127)
                     0 = Acoustic Grand Piano
                     24-31 = Guitars
                     40-47 = Strings
                     56-63 = Brass
                     4-7 = Electric Pianos
        """
        if self.fs and self.sfid is not None:
            self.instrument = program
            self.fs.program_select(self.channel, self.sfid, 0, program)

    def play_notes_immediate(self, midi_notes: List[int]) -> None:
        """
        Play notes immediately (for manual clicks)

        Args:
            midi_notes: List of MIDI note numbers
        """
        if not self.fs:
            logger.warning("FluidSynth not initialized, cannot play notes")
            return

        # Stop any currently playing notes first
        self.stop_all_notes()

        # Play all notes
        velocity = 100
        for midi_note in midi_notes:
            self.fs.noteon(self.channel, midi_note, velocity)

    def stop_all_notes(self) -> None:
        """Stop all currently playing notes"""
        if self.fs:
            self.fs.all_notes_off(self.channel)

    def set_bpm(self, bpm: int) -> None:
        """Update BPM setting"""
        self.bpm = bpm

    def set_time_signature(self, beats_per_measure: int, beat_unit: int) -> None:
        """Update time signature"""
        self.time_signature = (beats_per_measure, beat_unit)

    def _beats_to_seconds(self, beats: float) -> float:
        """
        Convert beats to seconds based on current BPM

        Args:
            beats: Number of beats

        Returns:
            Duration in seconds
        """
        # 60 seconds per minute / BPM = seconds per beat
        seconds_per_beat = 60.0 / self.bpm
        return beats * seconds_per_beat

    def set_next_note_callback(self, callback: Callable[[], Optional[Tuple[List[int], float]]]) -> None:
        """
        Set callback to get next note for playback

        Args:
            callback: Function that returns (midi_notes, duration_beats) or None
                     Should handle read locking internally
        """
        self.get_next_note_callback = callback

    def set_playback_finished_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback to be called when playback finishes

        Args:
            callback: Function to call when playback finishes naturally
        """
        self.on_playback_finished_callback = callback

    def start_playback(self) -> None:
        """Start playback in a separate thread"""
        with self._state_lock:
            if self.is_playing:
                logger.debug("Playback already in progress")
                return

            if not self.get_next_note_callback:
                logger.warning("No callback set for getting next note")
                return

            logger.debug("Starting playback thread")
            self.is_playing = True
            self.is_paused = False

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Not paused initially

        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def pause_playback(self) -> None:
        """Pause playback"""
        with self._state_lock:
            if not self.is_playing or self.is_paused:
                return

            logger.debug("Pausing playback")
            self.is_paused = True

        self.pause_event.clear()
        self.stop_all_notes()

    def resume_playback(self) -> None:
        """Resume playback"""
        with self._state_lock:
            if not self.is_playing or not self.is_paused:
                return

            logger.debug("Resuming playback")
            self.is_paused = False

        self.pause_event.set()

    def stop_playback(self) -> None:
        """Stop playback and wait for thread to finish"""
        with self._state_lock:
            if not self.is_playing:
                return

            logger.debug("Stopping playback")
            self.is_playing = False
            self.is_paused = False

        if self.stop_event:
            self.stop_event.set()
        if self.pause_event:
            self.pause_event.set()  # Unblock if paused

        # Wait for thread to finish
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)

        self.stop_all_notes()
        logger.debug("Playback stopped")

    def _playback_loop(self) -> None:
        """Main playback loop running in separate thread"""
        import time

        logger.debug("Playback loop started")

        while True:
            with self._state_lock:
                if not self.is_playing or self.stop_event.is_set():
                    break

            # Check if paused
            if not self.pause_event.wait(timeout=0.1):
                continue  # Still paused

            with self._state_lock:
                if not self.is_playing:
                    break

            # Get next note from callback (with read lock)
            logger.debug("Calling get_next_note_callback")
            try:
                result = self.get_next_note_callback()
            except Exception as e:
                logger.error(f"Exception in get_next_note_callback: {e}", exc_info=True)
                break

            if result is None:
                logger.debug("No more notes, stopping playback")
                with self._state_lock:
                    self.is_playing = False
                break

            midi_notes, duration_beats = result
            logger.debug(f"Got note: {midi_notes}, duration: {duration_beats} beats")

            # Play notes
            if self.fs and midi_notes:
                velocity = 100
                for midi_note in midi_notes:
                    self.fs.noteon(self.channel, midi_note, velocity)
                logger.debug(f"Notes pressed")

            # Sleep for duration
            duration_seconds = self._beats_to_seconds(duration_beats)
            logger.debug(f"Sleeping for {duration_seconds}s")

            # Sleep in small chunks to be responsive to stop/pause
            sleep_chunks = int(duration_seconds / 0.1) + 1
            for _ in range(sleep_chunks):
                with self._state_lock:
                    should_stop = not self.is_playing or self.stop_event.is_set()
                if should_stop:
                    break
                time.sleep(min(0.1, duration_seconds))
                duration_seconds -= 0.1
                if duration_seconds <= 0:
                    break

            # Release notes
            self.stop_all_notes()
            logger.debug(f"Notes released")

        logger.debug("Playback loop ended")

        # Call finished callback if playback ended naturally (not via stop)
        logger.debug(f"Checking callback: stop_event={self.stop_event.is_set()}, callback={self.on_playback_finished_callback is not None}")
        if not self.stop_event.is_set() and self.on_playback_finished_callback:
            logger.debug("Calling playback finished callback")
            try:
                self.on_playback_finished_callback()
                logger.debug("Playback finished callback completed")
            except Exception as e:
                logger.error(f"Exception in playback finished callback: {e}", exc_info=True)
        else:
            logger.debug("Skipping callback (stop_event set or no callback)")

    def cleanup(self) -> None:
        """Clean up FluidSynth resources"""
        # Stop playback thread if running
        self.stop_playback()

        if self.fs:
            self.stop_all_notes()
            self.fs.delete()
            self.fs = None

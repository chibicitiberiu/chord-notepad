"""
Audio playback using FluidSynth
"""

import logging
import os
from pathlib import Path
import fluidsynth

logger = logging.getLogger(__name__)

# MIDI note mapping (C4 = Middle C = MIDI 60)
NOTE_TO_MIDI_BASE = {
    'C': 0, 'C#': 1, 'Db': 1,
    'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6,
    'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10,
    'B': 11
}


def note_to_midi(note_str, default_octave=4):
    """
    Convert note string to MIDI number

    Args:
        note_str: Note like "C4", "D#5", "Bb3", or just "C", "D#"
        default_octave: Octave to use if not specified (default 4 = middle C)

    Returns:
        MIDI note number (0-127)
    """
    # Extract note name and octave
    import re
    match = re.match(r'([A-Ga-g][#b]?)(\d+)?', note_str)
    if not match:
        return None

    note_name = match.group(1)
    octave_str = match.group(2)

    # Use specified octave or default
    octave = int(octave_str) if octave_str else default_octave

    # Get base note value
    if note_name not in NOTE_TO_MIDI_BASE:
        return None

    # Adjust octave for F, G, A, B notes to avoid muddy low range
    # If we're in octave 3 or below, move F, G, A, B up one octave
    note_base = note_name.rstrip('#b')
    if octave <= 3 and note_base in ['F', 'G', 'A', 'B']:
        octave += 1

    # Calculate MIDI number: (octave + 1) * 12 + note_offset
    # C4 = 60, so octave 4 starts at MIDI 48
    midi_number = (octave + 1) * 12 + NOTE_TO_MIDI_BASE[note_name]

    return midi_number if 0 <= midi_number <= 127 else None


class NotePlayer:
    """Audio player for MIDI notes using FluidSynth"""

    def __init__(self, soundfont_path=None, bpm=120, time_signature=(4, 4)):
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

        # Playback thread
        self.playback_thread = None
        self.is_playing = False
        self.is_paused = False
        self.stop_event = None
        self.pause_event = None

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

    def _find_soundfont(self):
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

    def _initialize_fluidsynth(self, soundfont_path):
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

    def set_instrument(self, program):
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

    def play_notes_immediate(self, midi_notes):
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

    def stop_all_notes(self):
        """Stop all currently playing notes"""
        if self.fs:
            self.fs.all_notes_off(self.channel)

    def set_bpm(self, bpm):
        """Update BPM setting"""
        self.bpm = bpm

    def set_time_signature(self, beats_per_measure, beat_unit):
        """Update time signature"""
        self.time_signature = (beats_per_measure, beat_unit)

    def _beats_to_seconds(self, beats):
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

    def set_next_note_callback(self, callback):
        """
        Set callback to get next note for playback

        Args:
            callback: Function that returns (midi_notes, duration_beats) or None
                     Should handle read locking internally
        """
        self.get_next_note_callback = callback

    def set_playback_finished_callback(self, callback):
        """
        Set callback to be called when playback finishes

        Args:
            callback: Function to call when playback finishes naturally
        """
        self.on_playback_finished_callback = callback

    def start_playback(self):
        """Start playback in a separate thread"""
        if self.is_playing:
            logger.debug("Playback already in progress")
            return

        if not self.get_next_note_callback:
            logger.warning("No callback set for getting next note")
            return

        logger.debug("Starting playback thread")
        self.is_playing = True
        self.is_paused = False

        import threading
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Not paused initially

        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def pause_playback(self):
        """Pause playback"""
        if not self.is_playing or self.is_paused:
            return

        logger.debug("Pausing playback")
        self.is_paused = True
        self.pause_event.clear()
        self.stop_all_notes()

    def resume_playback(self):
        """Resume playback"""
        if not self.is_playing or not self.is_paused:
            return

        logger.debug("Resuming playback")
        self.is_paused = False
        self.pause_event.set()

    def stop_playback(self):
        """Stop playback and wait for thread to finish"""
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

    def _playback_loop(self):
        """Main playback loop running in separate thread"""
        import time

        logger.debug("Playback loop started")

        while self.is_playing and not self.stop_event.is_set():
            # Check if paused
            if not self.pause_event.wait(timeout=0.1):
                continue  # Still paused

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
                if not self.is_playing or self.stop_event.is_set():
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
        if not self.stop_event.is_set() and self.on_playback_finished_callback:
            logger.debug("Calling playback finished callback")
            try:
                self.on_playback_finished_callback()
            except Exception as e:
                logger.error(f"Exception in playback finished callback: {e}", exc_info=True)

    def cleanup(self):
        """Clean up FluidSynth resources"""
        # Stop playback thread if running
        self.stop_playback()

        if self.fs:
            self.stop_all_notes()
            self.fs.delete()
            self.fs = None

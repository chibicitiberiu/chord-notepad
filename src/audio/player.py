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
        self._bpm_multiplier = 1.0

        # Song-time / wall-time anchors for live-multiplier-aware scheduling.
        # target_wall = _wall_anchor + (event.timestamp - _song_anchor) / multiplier
        self._song_anchor: float = 0.0
        self._wall_anchor: Optional[float] = None

        # Playback thread and state
        self.playback_thread = None
        self.is_playing = False
        self.is_paused = False
        self.stop_event = None
        self.pause_event = None
        self._state_lock = threading.Lock()  # Protects is_playing and is_paused

        # Event buffer for producer-consumer architecture
        self.event_buffer = None

        # Callback when playback finishes
        self.on_playback_finished_callback = None

        # Callback for playback events (chord start/end)
        self.on_event_callback = None
        self.application = None

        # Playback start time for absolute timestamp tracking
        self._playback_start_time = None

        # Timer for immediate play note-off
        self._immediate_note_timer = None
        self._immediate_notes = []

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
            # Try different drivers in order of preference based on platform
            import sys
            if sys.platform == 'win32':
                drivers = ['dsound', 'wasapi', 'waveout']
            elif sys.platform == 'darwin':
                drivers = ['coreaudio']
            else:  # Linux and others
                drivers = ['pulseaudio', 'alsa', 'oss']
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

    def play_notes_immediate(self, midi_notes: List[int], duration: float = 2.0) -> None:
        """
        Play notes immediately (for manual clicks) and schedule NOTE_OFF after duration

        Args:
            midi_notes: List of MIDI note numbers
            duration: Duration in seconds before notes are released (default 2.0)
        """
        if not self.fs:
            logger.warning("FluidSynth not initialized, cannot play notes")
            return

        # Cancel any pending timer
        if self._immediate_note_timer:
            self._immediate_note_timer.cancel()

        # Stop any currently playing immediate notes
        if self._immediate_notes:
            for midi_note in self._immediate_notes:
                self.fs.noteoff(self.channel, midi_note)

        # Play all notes
        velocity = 100
        for midi_note in midi_notes:
            self.fs.noteon(self.channel, midi_note, velocity)

        # Store notes for later release
        self._immediate_notes = midi_notes.copy()

        # Schedule NOTE_OFF after duration
        self._immediate_note_timer = threading.Timer(duration, self._release_immediate_notes)
        self._immediate_note_timer.daemon = True
        self._immediate_note_timer.start()

    def _release_immediate_notes(self) -> None:
        """Release notes that were played via play_notes_immediate (called by timer)."""
        if self.fs and self._immediate_notes:
            for midi_note in self._immediate_notes:
                self.fs.noteoff(self.channel, midi_note)
            logger.debug(f"Released immediate notes: {self._immediate_notes}")
            self._immediate_notes = []

    def stop_all_notes(self) -> None:
        """Stop all currently playing notes"""
        if self.fs:
            self.fs.all_notes_off(self.channel)
        # Also cancel immediate note timer
        if self._immediate_note_timer:
            self._immediate_note_timer.cancel()
            self._immediate_note_timer = None
        self._immediate_notes = []

    def set_bpm(self, bpm: int) -> None:
        """Update BPM setting"""
        self.bpm = bpm

    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Update playback speed multiplier.

        Takes effect immediately on the next scheduled event; the playback loop
        recomputes wait times against the live multiplier value.
        """
        self._bpm_multiplier = max(0.001, float(multiplier))

    def set_metronome_enabled(self, enabled: bool) -> None:
        """Mute/unmute the drum channel that carries the click track.

        The event producer always schedules METRONOME_TICK events; this just
        rides the channel-volume CC so toggling is immediate regardless of
        what's already buffered.
        """
        if self.fs is None:
            return
        self._ensure_drum_channel()
        try:
            self.fs.cc(self.METRONOME_DRUM_CHANNEL, 7, 100 if enabled else 0)
        except Exception as e:
            logger.warning(f"Could not set metronome channel volume: {e}")

    def set_time_signature(self, beats_per_measure: int, beat_unit: int) -> None:
        """Update time signature"""
        self.time_signature = (beats_per_measure, beat_unit)

    # GM percussion on channel 9
    METRONOME_DRUM_CHANNEL = 9
    METRONOME_DRUM_BANK = 128
    METRONOME_DOWNBEAT_NOTE = 76  # High Wood Block
    METRONOME_OFFBEAT_NOTE = 77   # Low Wood Block
    METRONOME_DOWNBEAT_VELOCITY = 100
    METRONOME_OFFBEAT_VELOCITY = 80

    def _ensure_drum_channel(self) -> None:
        if getattr(self, "_drum_configured", False) or self.fs is None or self.sfid is None:
            return
        try:
            self.fs.program_select(
                self.METRONOME_DRUM_CHANNEL, self.sfid, self.METRONOME_DRUM_BANK, 0
            )
            # Start muted; the service raises CC 7 when the user toggles the
            # metronome on.
            self.fs.cc(self.METRONOME_DRUM_CHANNEL, 7, 0)
            self._drum_configured = True
        except Exception as e:
            logger.warning(f"Could not select drum bank on channel 9: {e}")

    def play_metronome_tick(self, is_downbeat: bool) -> None:
        """Sound a short metronome click on the drum channel."""
        if self.fs is None:
            return
        self._ensure_drum_channel()
        note = self.METRONOME_DOWNBEAT_NOTE if is_downbeat else self.METRONOME_OFFBEAT_NOTE
        velocity = self.METRONOME_DOWNBEAT_VELOCITY if is_downbeat else self.METRONOME_OFFBEAT_VELOCITY
        try:
            self.fs.noteon(self.METRONOME_DRUM_CHANNEL, note, velocity)
            # Schedule a quick noteoff so the click stays short.
            threading.Timer(0.04, lambda: self._safe_noteoff(note)).start()
        except Exception as e:
            logger.debug(f"Metronome tick failed: {e}")

    def _safe_noteoff(self, note: int) -> None:
        try:
            if self.fs is not None:
                self.fs.noteoff(self.METRONOME_DRUM_CHANNEL, note)
        except Exception:
            pass

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

    def set_event_buffer(self, event_buffer) -> None:
        """
        Set event buffer for playback

        Args:
            event_buffer: EventBuffer instance containing pre-computed MIDI events
        """
        self.event_buffer = event_buffer

    def set_playback_finished_callback(self, callback: Callable[[], None]) -> None:
        """
        Set callback to be called when playback finishes

        Args:
            callback: Function to call when playback finishes naturally
        """
        self.on_playback_finished_callback = callback

    def set_event_callback(self, callback: Optional[Callable], application) -> None:
        """
        Set callback to be called for playback events (chord start/end)

        Args:
            callback: Function to call for playback events
            application: Application instance for queueing UI callbacks
        """
        self.on_event_callback = callback
        self.application = application

    def start_playback(self) -> None:
        """Start playback in a separate thread"""
        with self._state_lock:
            if self.is_playing:
                logger.debug("Playback already in progress")
                return

            if not self.event_buffer:
                logger.warning("No event buffer set for playback")
                return

            logger.debug("Starting playback thread")
            self.is_playing = True
            self.is_paused = False

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Not paused initially
        self._playback_start_time = None  # Will be set on first event
        self._song_anchor = 0.0
        self._wall_anchor = None

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
        """Main playback loop running in separate thread - consumes events from buffer."""
        import time
        from models.playback_event_internal import MidiEventType

        logger.debug("Playback loop started (buffer-based)")

        natural_end = False  # Track if playback ended naturally

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

            # Get next event from buffer (with timeout)
            logger.debug("Fetching next event from buffer")
            try:
                event = self.event_buffer.pop_event(timeout=0.1)
            except Exception as e:
                logger.error(f"Exception getting event from buffer: {e}", exc_info=True)
                break

            if event is None:
                # Timeout - check if we should continue waiting
                continue

            logger.debug(f"Got event: {event}")

            # Handle END_OF_SONG event
            if event.event_type == MidiEventType.END_OF_SONG:
                logger.debug("Reached END_OF_SONG event")
                with self._state_lock:
                    self.is_playing = False
                natural_end = True
                break

            # Initialize anchors on first event
            if self._playback_start_time is None:
                self._playback_start_time = time.time()
                self._song_anchor = event.timestamp
                self._wall_anchor = self._playback_start_time
                logger.debug(f"Playback start time initialized: {self._playback_start_time}")

            def _target_wall_time() -> float:
                # Live read of multiplier — changes take effect on the next chunk.
                mult = self._bpm_multiplier or 1.0
                return self._wall_anchor + (event.timestamp - self._song_anchor) / mult

            current_time = time.time()
            wait_time = _target_wall_time() - current_time

            # Sleep until target time (if in the future)
            if wait_time > 0:
                logger.debug(f"Waiting {wait_time:.3f}s until event at t={event.timestamp:.3f}s")
                # Sleep in small chunks to be responsive to stop/pause/multiplier
                CHUNK = 0.05
                while True:
                    with self._state_lock:
                        should_stop = not self.is_playing or self.stop_event.is_set()
                    if should_stop:
                        break
                    if not self.pause_event.is_set():
                        # Paused - shift wall anchor by the pause duration so the
                        # song-time -> wall-time mapping stays consistent.
                        pause_start = time.time()
                        self.pause_event.wait()
                        pause_duration = time.time() - pause_start
                        self._wall_anchor += pause_duration
                        logger.debug(f"Paused for {pause_duration:.3f}s, adjusted anchor")
                        continue
                    remaining = _target_wall_time() - time.time()
                    if remaining <= 0:
                        break
                    time.sleep(min(CHUNK, remaining))
            else:
                if wait_time < -0.1:
                    logger.warning(f"Event is {-wait_time:.3f}s late (target={event.timestamp:.3f}s)")

            # Advance anchors so subsequent events schedule from here under the
            # current multiplier.
            self._song_anchor = event.timestamp
            self._wall_anchor = time.time()

            # Check if we should stop before playing
            with self._state_lock:
                if not self.is_playing or self.stop_event.is_set():
                    break

            # Handle NOTE_ON event
            if event.event_type == MidiEventType.NOTE_ON:
                if self.fs and event.midi_notes:
                    # Play notes (don't stop existing notes - allows overlapping/arpeggio)
                    for midi_note in event.midi_notes:
                        self.fs.noteon(self.channel, midi_note, event.velocity)
                    logger.debug(f"Played notes: {event.midi_notes}")

                # Fire event callback if provided and metadata indicates it should be called
                if self.on_event_callback and self.application and event.metadata.get('has_callback'):
                    try:
                        from models.playback_event import PlaybackEventArgs, PlaybackEventType
                        event_args = PlaybackEventArgs(
                            event_type=PlaybackEventType.CHORD_START,
                            chord_info=event.metadata.get('chord_info'),
                            chord_index=event.metadata.get('chord_index'),
                            bpm=event.metadata.get('bpm'),
                            time_signature_beats=event.metadata.get('time_signature_beats'),
                            time_signature_unit=event.metadata.get('time_signature_unit'),
                            key=event.metadata.get('key'),
                            current_line=event.metadata.get('line_index'),
                            current_bar=event.metadata.get('bar'),
                            total_bars=event.metadata.get('total_bars')
                        )
                        # Queue callback to UI thread
                        self.application.queue_ui_callback(lambda: self.on_event_callback(event_args))
                    except Exception as e:
                        logger.error(f"Error in playback event callback: {e}", exc_info=True)

            # Handle NOTE_OFF event
            elif event.event_type == MidiEventType.NOTE_OFF:
                if self.fs and event.midi_notes:
                    for midi_note in event.midi_notes:
                        self.fs.noteoff(self.channel, midi_note)
                    logger.debug(f"Released notes: {event.midi_notes}")

            # Handle METRONOME_TICK event — short percussive blip on drum channel
            elif event.event_type == MidiEventType.METRONOME_TICK:
                self.play_metronome_tick(bool(event.metadata.get('is_downbeat', False)))

            # Handle REST event (NC - No Chord)
            elif event.event_type == MidiEventType.REST:
                # REST plays no notes, but fires callback for UI highlighting
                logger.debug(f"REST event at t={event.timestamp:.3f}s (duration={event.metadata.get('duration_seconds', 0):.3f}s)")

                # Fire event callback if provided
                if self.on_event_callback and self.application and event.metadata.get('has_callback'):
                    try:
                        from models.playback_event import PlaybackEventArgs, PlaybackEventType
                        event_args = PlaybackEventArgs(
                            event_type=PlaybackEventType.CHORD_START,
                            chord_info=event.metadata.get('chord_info'),
                            chord_index=event.metadata.get('chord_index'),
                            bpm=event.metadata.get('bpm'),
                            time_signature_beats=event.metadata.get('time_signature_beats'),
                            time_signature_unit=event.metadata.get('time_signature_unit'),
                            key=event.metadata.get('key'),
                            current_line=event.metadata.get('line_index'),
                            current_bar=event.metadata.get('bar'),
                            total_bars=event.metadata.get('total_bars')
                        )
                        # Queue callback to UI thread
                        self.application.queue_ui_callback(lambda: self.on_event_callback(event_args))
                    except Exception as e:
                        logger.error(f"Error in REST event callback: {e}", exc_info=True)

        # Stop all notes when exiting
        self.stop_all_notes()
        logger.debug("Playback loop ended")

        # Call finished callback if playback ended naturally (not via stop)
        logger.debug(f"Checking callback: natural_end={natural_end}, callback={self.on_playback_finished_callback is not None}")
        if natural_end and self.on_playback_finished_callback:
            logger.debug("Calling playback finished callback")
            try:
                self.on_playback_finished_callback()
                logger.debug("Playback finished callback completed")
            except Exception as e:
                logger.error(f"Exception in playback finished callback: {e}", exc_info=True)
        else:
            logger.debug("Skipping callback (stopped manually or no callback)")

    def cleanup(self) -> None:
        """Clean up FluidSynth resources"""
        # Stop playback thread if running
        self.stop_playback()

        if self.fs:
            self.stop_all_notes()
            self.fs.delete()
            self.fs = None

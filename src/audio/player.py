"""
Audio playback using FluidSynth.

Song notes are scheduled on FluidSynth's sequencer, which runs on the synth's
sample clock (see :mod:`audio.sequencer` and :mod:`audio.song_scheduler`), so
note timing doesn't depend on when a Python thread gets to run. A light
"PlaybackClock" thread only feeds the sequencer a couple of seconds ahead and
posts the chord pings for the UI when their time is reached. Nothing calls
back into Python from FluidSynth's audio thread.
"""

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from audio.audio_options import AudioOptions
from audio.fluidsynth_import import fluidsynth
from audio.player_interface import IPlayer
from audio.sequencer import TICKS_PER_SECOND, SynthSequencer
from audio.song_scheduler import CLICK_TICKS, ClickSound, SongScheduler
from exceptions import AudioInitializationError
from models.playback_event_internal import MidiEvent

logger = logging.getLogger(__name__)


class NotePlayer(IPlayer):
    """Audio player for MIDI notes using FluidSynth"""

    _audio_suspended = False
    _driver_candidates: List[str] = []

    def __init__(
        self,
        soundfont_path: Optional[str] = None,
        bpm: int = 120,
        time_signature: Tuple[int, int] = (4, 4),
        options: Optional[AudioOptions] = None,
    ) -> None:
        """
        Initialize the note player

        Args:
            soundfont_path: Path to soundfont file (.sf2)
            bpm: Beats per minute (default 120)
            time_signature: Tuple of (beats_per_measure, beat_unit) (default 4/4)
            options: Synth settings and preferred audio driver from the host
                (default: FluidSynth's defaults and the platform driver list)
        """
        self.fs = None
        #: The audio driver that actually started.
        self.driver_name: Optional[str] = None
        #: The driver candidates tried at init, to retry on resume_audio().
        self._driver_candidates: List[str] = []
        self._audio_suspended = False
        self.sfid = None
        self.channel = 0
        self.instrument = 0  # Acoustic Grand Piano by default

        # Sequencer on the synth's sample clock, and the client ids that tag
        # song events and click-to-hear note-offs (so each can be removed
        # without touching the other).
        self._sequencer: Optional[SynthSequencer] = None
        self._song_source = -1
        self._click_source = -1

        # Timing information
        self.bpm = bpm
        self.time_signature = time_signature
        self._bpm_multiplier = 1.0

        # Playback state. The lock guards is_playing/is_paused and the
        # scheduler; the condition wakes the clock thread early.
        self.playback_thread: Optional[threading.Thread] = None
        self.is_playing = False
        self.is_paused = False
        self._state_lock = threading.Lock()
        self._wake = threading.Condition(self._state_lock)
        self._scheduler: Optional[SongScheduler] = None

        # Event buffer for producer-consumer architecture
        self.event_buffer = None

        # Callback when playback finishes
        self.on_playback_finished_callback = None

        # Callback for playback events (chord start/end)
        self.on_event_callback = None
        self.application = None

        # Notes sounding from play_notes_immediate
        self._immediate_notes: List[int] = []

        # Find soundfont
        if soundfont_path is None:
            soundfont_path = self._find_soundfont()

        if soundfont_path and os.path.exists(soundfont_path):
            self._initialize_fluidsynth(soundfont_path, options)
        elif soundfont_path:
            raise FileNotFoundError(f"Soundfont not found: {soundfont_path}")
        else:
            raise FileNotFoundError("No soundfont found. Choose one in Settings.")

    def _find_soundfont(self) -> Optional[str]:
        """Find the bundled soundfont"""
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

    def _initialize_fluidsynth(self, soundfont_path: str, options: Optional[AudioOptions] = None) -> None:
        """Initialize FluidSynth with the soundfont.

        Args:
            soundfont_path: The .sf2 file to load.
            options: Synth settings and the preferred audio driver.

        Raises:
            AudioInitializationError: If no audio driver starts or the
                soundfont can't be loaded. The caller decides how to tell the
                user; a player with no synth would just play silence.
        """
        options = options or AudioOptions()
        try:
            synth_kwargs = options.synth_settings()
            if options.sample_rate:
                synth_kwargs["samplerate"] = float(options.sample_rate)
            logger.debug("Creating FluidSynth instance...")
            self.fs = fluidsynth.Synth(**synth_kwargs)

            # Set gain (volume) - 0.0 to 10.0, default is 0.2
            self.fs.setting('synth.gain', 0.5)

            # Before any driver renders: registering adds a sample timer to
            # the synth, which the audio thread walks.
            self._create_sequencer()

            # Try the preferred driver, then the platform's usual ones
            drivers = options.driver_candidates(sys.platform)
            self._driver_candidates = list(drivers)
            self.driver_name = None
            for driver in drivers:
                if self._start_audio_driver(driver):
                    self.driver_name = driver
                    break

            if self.driver_name is None:
                raise AudioInitializationError(
                    f"No audio output could be started (tried {', '.join(drivers)})."
                )
            logger.info(f"FluidSynth started with audio driver: {self.driver_name}")

            # Load soundfont (FluidSynth returns -1 instead of raising)
            self.sfid = self.fs.sfload(soundfont_path)
            if self.sfid is None or self.sfid < 0:
                self.sfid = None
                raise AudioInitializationError(f"Could not load the soundfont: {soundfont_path}")
            logger.info(f"Loaded soundfont: {soundfont_path}, ID: {self.sfid}")

            # Select instrument (program)
            self.fs.program_select(self.channel, self.sfid, 0, self.instrument)

        except Exception as e:
            logger.error(f"Failed to initialize FluidSynth: {e}", exc_info=True)
            self._release_synth()  # release the audio device we may hold
            if isinstance(e, AudioInitializationError):
                raise
            raise AudioInitializationError(f"FluidSynth failed to start: {e}") from e

    @property
    def audio_suspended(self) -> bool:
        """True while the audio driver is released by :meth:`suspend_audio`."""
        return self._audio_suspended

    def suspend_audio(self) -> bool:
        """Release the audio driver (the device) but keep the synth.

        The SoundFont, program and sequencer stay loaded. The sequencer runs
        on the synth's sample clock, so its time freezes while no driver
        renders; a paused song's scheduler resumes from ``sequencer.now()``,
        so playback continues from where it was after :meth:`resume_audio`.

        Returns:
            True if suspended (or already); False when a song is playing
            or there is no synth.
        """
        if self._audio_suspended:
            return True
        if self.fs is None:
            return False
        if self.is_playing and not self.is_paused:
            logger.info("Not suspending the audio output while a song plays")
            return False
        self.stop_all_notes()
        fs = self.fs
        try:
            if fs.audio_driver:
                fluidsynth.delete_fluid_audio_driver(fs.audio_driver)
        except Exception:
            logger.debug("Could not free the audio driver", exc_info=True)
        fs.audio_driver = None
        self._audio_suspended = True
        logger.info("Audio output released (suspended)")
        return True

    def resume_audio(self) -> bool:
        """Reopen the audio driver released by :meth:`suspend_audio`.

        Tries the driver that ran before, then the other candidates.

        Returns:
            True if the output is running; False if no driver started (the
            player stays suspended).
        """
        if not self._audio_suspended:
            return True
        if self.fs is None:
            return False
        candidates = list(self._driver_candidates)
        if self.driver_name in candidates:
            candidates.remove(self.driver_name)
        if self.driver_name:
            candidates.insert(0, self.driver_name)
        for driver in candidates:
            if self._start_audio_driver(driver):
                self.driver_name = driver
                self._audio_suspended = False
                logger.info(f"Audio output reopened with driver: {driver}")
                return True
        logger.warning("The audio output could not be reopened")
        return False

    def _create_sequencer(self) -> None:
        """Create the sample-clocked sequencer and its two source clients."""
        self._sequencer = SynthSequencer(self.fs)
        self._song_source = self._sequencer.new_source("chordnotepad-song")
        self._click_source = self._sequencer.new_source("chordnotepad-click")

    def _release_synth(self) -> None:
        """Free the audio driver, the sequencer and the synth, in that order.

        The driver goes first so nothing renders while the sequencer (whose
        sample timer the synth calls) is freed.
        """
        fs = self.fs
        if fs is None:
            return
        try:
            if fs.audio_driver:
                fluidsynth.delete_fluid_audio_driver(fs.audio_driver)
        except Exception:
            logger.debug("Could not free the audio driver", exc_info=True)
        fs.audio_driver = None
        sequencer = getattr(self, "_sequencer", None)
        if sequencer is not None:
            try:
                sequencer.delete()
            except Exception:
                logger.debug("Could not free the sequencer", exc_info=True)
            self._sequencer = None
        try:
            fs.delete()
        except Exception:
            logger.debug("FluidSynth cleanup failed", exc_info=True)
        self.fs = None

    def _start_audio_driver(self, driver: str) -> bool:
        """Try to start one FluidSynth audio driver.

        pyfluidsynth's ``Synth.start()`` returns OK even when FluidSynth could
        not create the driver (``new_fluid_audio_driver`` returned NULL), so
        the handle it stores is what tells success from failure.

        Args:
            driver: FluidSynth audio driver name, e.g. ``"pulseaudio"``.

        Returns:
            True if the driver is running.
        """
        try:
            result = self.fs.start(driver=driver)
        except Exception as e:
            logger.info(f"Audio driver {driver!r} failed to start: {e}")
            result = -1
        if result == 0 and self.fs.audio_driver:
            return True
        logger.info(f"Audio driver {driver!r} could not be started")
        self._discard_failed_start()
        return False

    def _discard_failed_start(self) -> None:
        """Free the MIDI input driver a failed ``start()`` still created.

        The next attempt would overwrite (and leak) it.
        """
        fs = self.fs
        if getattr(fs, "midi_driver", None):
            try:
                fluidsynth.delete_fluid_midi_driver(fs.midi_driver)
            except Exception:
                logger.debug("Could not free the MIDI driver after a failed start", exc_info=True)
            fs.midi_driver = None
        fs.audio_driver = None

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

        The note-offs go to the sequencer, so no timer thread is started per
        click.

        Args:
            midi_notes: List of MIDI note numbers
            duration: Duration in seconds before notes are released (default 2.0)
        """
        if not self.fs:
            logger.warning("FluidSynth not initialized, cannot play notes")
            return

        # Drop the pending release of the previous click, and stop its notes
        self._cancel_immediate_release()
        for midi_note in self._immediate_notes:
            self.fs.noteoff(self.channel, midi_note)

        velocity = 100
        for midi_note in midi_notes:
            self.fs.noteon(self.channel, midi_note, velocity)
        self._immediate_notes = list(midi_notes)

        if self._sequencer is not None:
            release = self._sequencer.now() + int(round(duration * TICKS_PER_SECOND))
            for midi_note in midi_notes:
                self._sequencer.note_off(release, self.channel, midi_note, self._click_source)

    def _cancel_immediate_release(self) -> None:
        if self._sequencer is not None:
            self._sequencer.remove(self._click_source)

    def stop_all_notes(self) -> None:
        """Stop all currently playing notes"""
        if self.fs:
            self.fs.all_notes_off(self.channel)
        self._cancel_immediate_release()
        self._immediate_notes = []

    def set_bpm(self, bpm: int) -> None:
        """Update BPM setting"""
        self.bpm = bpm

    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Update playback speed multiplier.

        During playback the rest of the song is rescheduled from the current
        position at the new speed, so the change is heard at once.
        """
        multiplier = max(0.001, float(multiplier))
        with self._wake:
            self._bpm_multiplier = multiplier
            if self._scheduler is not None and self._sequencer is not None:
                self._scheduler.set_multiplier(multiplier, self._sequencer.now())
                self._wake.notify_all()

    def set_metronome_enabled(self, enabled: bool) -> None:
        """Mute/unmute the drum channel that carries the click track.

        The event producer always schedules METRONOME_TICK events; this just
        rides the channel-volume CC so toggling is immediate regardless of
        what's already scheduled.
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

    @property
    def click_sound(self) -> ClickSound:
        """The metronome click the scheduler plays."""
        return ClickSound(
            channel=self.METRONOME_DRUM_CHANNEL,
            downbeat_note=self.METRONOME_DOWNBEAT_NOTE,
            offbeat_note=self.METRONOME_OFFBEAT_NOTE,
            downbeat_velocity=self.METRONOME_DOWNBEAT_VELOCITY,
            offbeat_velocity=self.METRONOME_OFFBEAT_VELOCITY,
        )

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
        """Sound a short metronome click on the drum channel now.

        Song playback schedules its clicks on the sequencer instead.
        """
        if self.fs is None:
            return
        self._ensure_drum_channel()
        note = self.METRONOME_DOWNBEAT_NOTE if is_downbeat else self.METRONOME_OFFBEAT_NOTE
        velocity = self.METRONOME_DOWNBEAT_VELOCITY if is_downbeat else self.METRONOME_OFFBEAT_VELOCITY
        try:
            self.fs.noteon(self.METRONOME_DRUM_CHANNEL, note, velocity)
            if self._sequencer is not None:
                # Untagged source: pause/stop/clicks never remove it.
                self._sequencer.note_off(self._sequencer.now() + CLICK_TICKS,
                                         self.METRONOME_DRUM_CHANNEL, note, -1)
        except Exception as e:
            logger.debug(f"Metronome tick failed: {e}")

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
            event_buffer: EventBuffer holding the whole compiled song; it is
                drained when playback starts.
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

    def _drain_event_buffer(self) -> List[MidiEvent]:
        events: List[MidiEvent] = []
        while True:
            event = self.event_buffer.pop_event(timeout=0)
            if event is None:
                return events
            events.append(event)

    def start_playback(self) -> None:
        """Schedule the buffered song and start the clock thread."""
        with self._wake:
            if self.is_playing:
                logger.debug("Playback already in progress")
                return

            if not self.event_buffer:
                logger.warning("No event buffer set for playback")
                return

            if self._sequencer is None:
                logger.warning("FluidSynth not initialized, cannot play the song")
                return

            self._ensure_drum_channel()
            scheduler = SongScheduler(
                self._drain_event_buffer(),
                self._sequencer,
                source=self._song_source,
                channel=self.channel,
                click=self.click_sound,
                multiplier=self._bpm_multiplier,
            )
            scheduler.start(self._sequencer.now())
            self._scheduler = scheduler
            self.is_playing = True
            self.is_paused = False

            logger.debug("Starting playback clock thread")
            self.playback_thread = threading.Thread(
                target=self._clock_loop, args=(scheduler,), daemon=True, name="PlaybackClock"
            )
            self.playback_thread.start()

    def pause_playback(self) -> None:
        """Pause playback"""
        with self._wake:
            if not self.is_playing or self.is_paused:
                return

            logger.debug("Pausing playback")
            self.is_paused = True
            pings: List[MidiEvent] = []
            if self._scheduler is not None:
                pings = self._scheduler.pause(self._sequencer.now())
            self._wake.notify_all()

        self._post_pings(pings)
        self.stop_all_notes()

    def resume_playback(self) -> None:
        """Resume playback"""
        with self._wake:
            if not self.is_playing or not self.is_paused:
                return

            logger.debug("Resuming playback")
            self.is_paused = False
            if self._scheduler is not None:
                self._scheduler.resume(self._sequencer.now())
            self._wake.notify_all()

    def stop_playback(self) -> None:
        """Stop playback and wait for the clock thread to finish"""
        with self._wake:
            if not self.is_playing:
                return

            logger.debug("Stopping playback")
            self.is_playing = False
            self.is_paused = False
            scheduler, self._scheduler = self._scheduler, None
            if scheduler is not None:
                scheduler.stop(self._sequencer.now())
            self._wake.notify_all()

        thread = self.playback_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

        self.stop_all_notes()
        logger.debug("Playback stopped")

    def _clock_loop(self, scheduler: SongScheduler) -> None:
        """Feed the sequencer ahead of time and post pings as they come due.

        Runs on the PlaybackClock thread until the song ends or is stopped
        (another song's scheduler replacing this one also ends it).
        """
        logger.debug("Playback clock started")
        natural_end = False

        while True:
            with self._wake:
                if self._scheduler is not scheduler or not self.is_playing:
                    break
                result = scheduler.pump(self._sequencer.now())
                if result.finished:
                    self.is_playing = False
                    self.is_paused = False
                    self._scheduler = None
                    natural_end = True

            self._post_pings(result.pings)
            if natural_end:
                break

            with self._wake:
                if self._scheduler is not scheduler:
                    break
                self._wake.wait(timeout=result.wait_s)

        logger.debug("Playback clock ended")
        if not natural_end:
            return

        self.stop_all_notes()
        if self.on_playback_finished_callback:
            try:
                self.on_playback_finished_callback()
            except Exception as e:
                logger.error(f"Exception in playback finished callback: {e}", exc_info=True)

    def _post_pings(self, events: List[MidiEvent]) -> None:
        """Queue a CHORD_START ping per event on the UI/session thread."""
        if not events or not self.on_event_callback or not self.application:
            return
        from models.playback_event import PlaybackEventArgs, PlaybackEventType

        callback = self.on_event_callback
        for event in events:
            try:
                meta = event.metadata
                event_args = PlaybackEventArgs(
                    event_type=PlaybackEventType.CHORD_START,
                    chord_info=meta.get('chord_info'),
                    chord_index=meta.get('chord_index'),
                    bpm=meta.get('bpm'),
                    time_signature_beats=meta.get('time_signature_beats'),
                    time_signature_unit=meta.get('time_signature_unit'),
                    key=meta.get('key'),
                    current_line=meta.get('line_index'),
                    current_bar=meta.get('bar'),
                    song_bar=meta.get('song_bar'),
                    total_bars=meta.get('total_bars')
                )
                self.application.queue_ui_callback(lambda args=event_args: callback(args))
            except Exception as e:
                logger.error(f"Error in playback event callback: {e}", exc_info=True)

    def cleanup(self) -> None:
        """Clean up FluidSynth resources"""
        self.stop_playback()

        if self.fs:
            self.stop_all_notes()
            self._release_synth()

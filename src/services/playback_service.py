"""Audio playback service wrapping NotePlayer."""

import logging
import threading
from typing import Optional, List, Callable, Tuple

from audio.player_interface import IPlayer
from audio.player import NotePlayer
from audio.note_picker_interface import INotePicker
from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from audio.event_buffer import EventBuffer
from services.song_renderer import SongRenderer
from services.event_compiler import compile_events
from models.chord_notes import ChordNotes
from models.chord import ChordInfo
from models.playback_state import PlaybackState
from models.playback_event import PlaybackEventArgs
from models.line import Line
from models.rendered_song import RenderedSong
from services.config_service import ConfigService
from exceptions import RenderAborted


class PlaybackService:
    """High-level audio playback orchestration service.

    Provides business-level API for audio playback, abstracting FluidSynth/NotePlayer details.
    """

    def __init__(self, config_service: ConfigService, player: Optional[IPlayer] = None, application=None):
        self._config = config_service
        self._player: Optional[IPlayer] = player
        self._note_picker = self._create_note_picker(self._config.get("voicing", "piano"))
        self._logger = logging.getLogger(__name__)
        self._initialized = player is not None
        self._playback_state = PlaybackState()
        self._application = application  # For UI callbacks

        # Pre-render pipeline components
        self._event_buffer: Optional[EventBuffer] = None
        self._render_thread: Optional[threading.Thread] = None
        self._render_cancel: Optional[threading.Event] = None

        self._metronome_enabled: bool = False

    def _create_note_picker(self, voicing: str) -> INotePicker:
        """Create appropriate note picker based on voicing string.

        Args:
            voicing: Voicing string like 'piano', 'guitar:standard', 'guitar:drop_d',
                'ensemble:<name>', or 'voicing:<name>' (a named entry in the
                config's ``voicings`` registry).

        Returns:
            INotePicker instance
        """
        if voicing.startswith("voicing:"):
            return self._create_registry_picker(voicing.split(":", 1)[1])
        elif voicing.startswith("guitar:"):
            return self._create_guitar_picker(voicing.split(":", 1)[1])
        elif voicing.startswith("ensemble:"):
            return self._create_ensemble_picker(voicing.split(":", 1)[1])
        else:
            # Default to piano voicing
            return ChordNotePicker()

    def _create_registry_picker(self, name: str) -> INotePicker:
        """Create the note picker for a named entry in the ``voicings`` registry.

        Each registry entry is ``{"model": "fretboard" | "ensemble" | "piano",
        ...model-specific parameters}``. Falls back to piano voicing (with a
        warning) if ``name`` is unknown, the model is unrecognized, or the
        parameters fail validation.

        Args:
            name: Voicing name as registered in config ``voicings``.

        Returns:
            An INotePicker instance for the resolved model, or a
            ``ChordNotePicker`` fallback.
        """
        from exceptions import ConfigurationError

        voicings = self._config.get("voicings", {})
        params = voicings.get(name)
        if params is None:
            self._logger.warning(f"Unknown voicing '{name}'; falling back to piano")
            return ChordNotePicker()

        params = dict(params)
        model = params.pop("model", None)

        try:
            if model == "fretboard":
                from models.fretboard_spec import FretboardSpec

                spec = FretboardSpec.from_dict(name, params)
                return GuitarChordPicker(spec)
            elif model == "ensemble":
                from models.ensemble_spec import EnsembleSpec
                # Imported lazily (rather than at module level) because this
                # module is owned by a concurrent task and may not exist on
                # disk yet when this branch is first exercised.
                from audio.ensemble_voicer import EnsembleVoicer

                spec = EnsembleSpec.from_dict(name, params)
                return EnsembleVoicer(spec)
            elif model == "piano":
                from models.piano_spec import PianoSpec

                spec = PianoSpec.from_dict(name, params)
                return ChordNotePicker(spec)
            else:
                self._logger.warning(
                    f"Unknown model {model!r} for voicing '{name}'; falling back to piano"
                )
                return ChordNotePicker()
        except ConfigurationError as e:
            self._logger.warning(f"Invalid voicing '{name}': {e}; falling back to piano")
            return ChordNotePicker()

    def _create_guitar_picker(self, tuning_name: str) -> INotePicker:
        """Create a ``GuitarChordPicker`` for a built-in fretboard tuning.

        Custom guitar tunings now live in the ``voicings`` registry (see
        :meth:`_create_registry_picker`); this only resolves the built-in
        presets in :data:`models.fretboard_spec.BUILTIN_FRETBOARDS`.

        Args:
            tuning_name: Built-in fretboard slug, e.g. ``'standard'``.

        Returns:
            A ``GuitarChordPicker`` for the resolved spec, falling back to
            the standard tuning (with a warning) if unknown.
        """
        from models.fretboard_spec import BUILTIN_FRETBOARDS

        if tuning_name in BUILTIN_FRETBOARDS:
            spec = BUILTIN_FRETBOARDS[tuning_name]
        else:
            self._logger.warning(
                f"Unknown guitar tuning '{tuning_name}'; falling back to standard"
            )
            spec = BUILTIN_FRETBOARDS["standard"]

        return GuitarChordPicker(spec)

    def _create_ensemble_picker(self, name: str) -> INotePicker:
        """Create an ``EnsembleVoicer`` for a built-in ensemble.

        Custom ensembles now live in the ``voicings`` registry (see
        :meth:`_create_registry_picker`); this only resolves the built-in
        presets in :data:`models.ensemble_spec.BUILTIN_ENSEMBLES`.

        Args:
            name: Built-in ensemble slug, e.g. ``'satb'``.

        Returns:
            An ``EnsembleVoicer`` for the resolved spec, or a
            ``ChordNotePicker`` fallback (with a warning) if ``name`` is
            unknown.
        """
        from models.ensemble_spec import BUILTIN_ENSEMBLES

        if name not in BUILTIN_ENSEMBLES:
            self._logger.warning(f"Unknown ensemble '{name}'; falling back to piano")
            return ChordNotePicker()

        spec = BUILTIN_ENSEMBLES[name]

        # Imported lazily (rather than at module level) because this module
        # is owned by a concurrent task and may not exist on disk yet when
        # this branch is first exercised; only needed once a spec resolves.
        from audio.ensemble_voicer import EnsembleVoicer

        return EnsembleVoicer(spec)

    def set_voicing(self, voicing: str) -> None:
        """Change the voicing style.

        Args:
            voicing: Voicing string like 'piano', 'guitar:standard', etc.
        """
        self._logger.debug(f"Setting voicing to {voicing}")
        self._note_picker = self._create_note_picker(voicing)
        self._config.set("voicing", voicing)

    def active_fretboard_spec(self):
        """Return the active picker's :class:`FretboardSpec`, or ``None``.

        Only fretboard-model voicings (``GuitarChordPicker``) carry a spec; for
        piano/ensemble voicings this returns ``None``. Exposed as a seam for the
        chord-sheet strip's capo advisor, which needs the tuning a capo raises.
        """
        if isinstance(self._note_picker, GuitarChordPicker):
            return self._note_picker.spec
        return None

    def get_available_instruments(self) -> List[Tuple[int, str]]:
        """Get list of available instruments from the soundfont.

        Returns:
            List of tuples (program_number, instrument_name)
        """
        if self._player:
            return self._player.get_available_instruments()
        return []

    def set_instrument(self, program: int) -> None:
        """Change the MIDI instrument.

        Args:
            program: MIDI program number (0-127)
        """
        if self._player:
            self._player.set_instrument(program)

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
            time_sig_beats = self._config.get("time_signature_beats", 4)
            time_sig_unit = self._config.get("time_signature_unit", 4)

            # Initialize playback state with config values
            self._playback_state = PlaybackState(
                bpm=bpm,
                initial_bpm=bpm,
                time_signature_beats=time_sig_beats,
                time_signature_unit=time_sig_unit
            )

            # Create player
            self._logger.info("Initializing audio player")
            self._player = NotePlayer(
                soundfont_path=sf_path,
                bpm=bpm,
                time_signature=(time_sig_beats, time_sig_unit)
            )

            # Set instrument from config
            instrument = self._config.get("instrument", 0)
            self._player.set_instrument(instrument)

            # Apply saved speed multiplier
            multiplier = float(self._config.get("bpm_multiplier", 1.0))
            self._player.set_bpm_multiplier(multiplier)

            self._initialized = True
            self._logger.info("Audio player initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize audio player: {e}", exc_info=True)
            self._player = None
            self._initialized = False
            return False

    def play_chord_immediate(self, chord_info: ChordInfo, current_key: Optional[str] = None) -> None:
        """Play a chord immediately (click-to-play) with dynamic note resolution.

        Args:
            chord_info: Chord information
            current_key: Current key signature for resolving roman numerals
        """
        if not self._ensure_initialized():
            return

        try:
            # Resolve chord notes dynamically
            chord_notes = self._resolve_chord_notes(chord_info, current_key)
            if not chord_notes:
                self._logger.warning(f"Could not resolve chord: {chord_info.chord}")
                return

            # Convert to MIDI
            midi_notes = self._notes_to_midi(chord_notes)
            if midi_notes:
                self._logger.debug(f"Playing chord immediately: {chord_info.chord} -> {chord_notes.notes} (bass: {chord_notes.bass_note})")
                self._player.play_notes_immediate(midi_notes)
            else:
                self._logger.warning(f"Could not convert chord to MIDI notes: {chord_info.chord}")

        except Exception as e:
            self._logger.error(f"Error playing chord: {e}", exc_info=True)

    def play_notes_immediate(self, midi_notes: List[int]) -> None:
        """Play MIDI notes immediately.

        Args:
            midi_notes: List of MIDI note numbers to play
        """
        if not self._ensure_initialized():
            return

        try:
            if midi_notes:
                self._logger.debug(f"Playing MIDI notes immediately: {midi_notes}")
                self._player.play_notes_immediate(midi_notes)
            else:
                self._logger.warning("No MIDI notes provided to play")

        except Exception as e:
            self._logger.error(f"Error playing notes: {e}", exc_info=True)

    def play_note(self, note_name: str, octave: int, duration: float = 1.0) -> None:
        """Play a single note by name and octave.

        Args:
            note_name: Note name (e.g., 'C', 'D#', 'Bb')
            octave: Octave number
            duration: Duration in seconds (currently not used, for API compatibility)
        """
        if not self._ensure_initialized():
            return

        try:
            # Convert note name and octave to MIDI note number
            # MIDI formula: (octave + 1) * 12 + note_offset
            NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

            if note_name not in NOTE_NAMES:
                self._logger.warning(f"Invalid note name: {note_name}")
                return

            note_offset = NOTE_NAMES.index(note_name)
            midi_note = (octave + 1) * 12 + note_offset

            self._logger.debug(f"Playing note: {note_name}{octave} (MIDI {midi_note})")
            self._player.play_notes_immediate([midi_note])

        except Exception as e:
            self._logger.error(f"Error playing note {note_name}{octave}: {e}", exc_info=True)

    def play_chord_from_midi(self, midi_notes: List[int], duration: float = 2.0) -> None:
        """Play a chord from MIDI note numbers.

        Args:
            midi_notes: List of MIDI note numbers to play as a chord
            duration: Duration in seconds (currently not used, for API compatibility)
        """
        # Delegate to play_notes_immediate
        self.play_notes_immediate(midi_notes)

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
        # Cancel any in-flight render so the render thread bails promptly.
        if self._render_cancel is not None:
            self._render_cancel.set()

        # Wait for the render thread to finish (it either bails on the cancel
        # flag or completes its quick buffer-fill + player-start wiring).
        if self._render_thread is not None:
            self._logger.debug("Joining render thread")
            self._render_thread.join(timeout=2.0)
            self._render_thread = None
        self._render_cancel = None

        # Close the event buffer (if the render thread got as far as creating it)
        # to wake the player if it's blocked waiting for events.
        if self._event_buffer is not None:
            self._logger.debug("Closing event buffer")
            self._event_buffer.close()
            self._event_buffer = None

        # Finally stop player
        if self._player:
            self._logger.debug("Stopping playback")
            self._player.stop_playback()

    def stop_all_notes(self) -> None:
        """Stop all currently playing notes (even if not in playback mode).

        This is useful for clearing stuck notes or stopping immediate chord playback.
        """
        if self._player:
            self._logger.debug("Stopping all notes")
            self._player.stop_all_notes()

    def set_bpm(self, bpm: int) -> None:
        """Change playback speed.

        Args:
            bpm: Beats per minute (20-400)
        """
        if self._player:
            self._logger.debug(f"Setting BPM to {bpm}")
            self._player.set_bpm(bpm)
            self._config.set("bpm", bpm)

        # Update playback state
        self._playback_state.set_bpm(bpm)

    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Set the playback speed multiplier (live during playback).

        Args:
            multiplier: Speed multiplier (0.125 - 4.0)
        """
        if self._player:
            self._logger.debug(f"Setting BPM multiplier to {multiplier}")
            self._player.set_bpm_multiplier(multiplier)
            self._config.set("bpm_multiplier", multiplier)

    def set_metronome_enabled(self, enabled: bool) -> None:
        """Arm or disarm the click track.

        Tick events are always pre-rendered into the event stream; the player
        mutes/unmutes the drum channel via CC 7, so toggling is immediate
        even mid-playback.
        """
        self._metronome_enabled = bool(enabled)
        if self._player is not None:
            self._player.set_metronome_enabled(self._metronome_enabled)

    @property
    def is_metronome_enabled(self) -> bool:
        return self._metronome_enabled

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

    def reset_playback_state(self) -> None:
        """Reset playback state for new playback session.

        Resets line position, chord index, and loop stack while preserving
        BPM, time signature, and key settings. Also resets chord picker state
        for consistent voice leading.
        """
        self._logger.debug("Resetting playback state")
        bpm = self._playback_state.bpm
        initial_bpm = self._playback_state.initial_bpm
        time_sig_beats = self._playback_state.time_signature_beats
        time_sig_unit = self._playback_state.time_signature_unit
        key = self._playback_state.key

        self._playback_state = PlaybackState(
            bpm=bpm,
            initial_bpm=initial_bpm,
            time_signature_beats=time_sig_beats,
            time_signature_unit=time_sig_unit,
            key=key
        )

        # Reset chord picker state for consistent voice leading
        self._note_picker.reset()

    def set_time_signature_from_state(self, beats: int, unit: int) -> None:
        """Update time signature in both playback state and player.

        Args:
            beats: Number of beats per measure
            unit: Beat unit (4 = quarter note, etc.)
        """
        self._logger.debug(f"Setting time signature to {beats}/{unit}")
        self._playback_state.set_time_signature(beats, unit)

        # Update player if initialized
        if self._player:
            # NotePlayer doesn't have a set_time_signature method yet
            # This would need to be implemented in NotePlayer if needed
            pass

    def set_key(self, key: str) -> None:
        """Update the current key signature in playback state.

        Args:
            key: Key signature (e.g., 'C', 'Am', 'G')
        """
        self._logger.debug(f"Setting key to {key}")
        self._playback_state.set_key(key)

    def get_playback_state(self) -> PlaybackState:
        """Get the current playback state.

        Returns:
            The current PlaybackState object
        """
        return self._playback_state

    def get_time_signature(self) -> Tuple[int, int]:
        """Get the current time signature from playback state.

        Returns:
            Tuple of (beats_per_measure, beat_unit), e.g., (4, 4) for 4/4 time
        """
        return (self._playback_state.time_signature_beats,
                self._playback_state.time_signature_unit)

    def start_song_playback(
        self,
        lines: List[Line],
        initial_key: Optional[str],
        on_finished_callback: Optional[Callable[[], None]] = None,
        on_event_callback: Optional[Callable[[PlaybackEventArgs], None]] = None,
        start_line_index: int = 0,
        start_item_index: int = 0
    ) -> bool:
        """Start playback of a song with lines containing chords and directives.

        Args:
            lines: List of Line objects with chords and directives
            initial_key: Initial key signature (from UI)
            on_finished_callback: Optional callback when playback finishes
            on_event_callback: Optional callback for playback events (chord start/end)
            start_line_index: Line index to start playback from (default: 0)
            start_item_index: Item index within the line to start from (default: 0)

        Returns:
            True if playback started, False otherwise
        """
        if not self._ensure_initialized():
            return False

        # Stop any existing playback before starting new one
        self.stop_playback()

        # Reset chord picker state for consistent voice leading at start of playback
        self._note_picker.reset()

        # Count total chords
        total_chords = sum(len(line.chords) for line in lines)
        if total_chords == 0:
            self._logger.info("No chords found for playback")
            return False

        self._logger.info(f"Starting song playback with {total_chords} chords (pre-render)")

        # Get initial playback parameters
        initial_bpm = self._playback_state.bpm
        initial_time_sig = self.get_time_signature()

        has_callback = on_event_callback is not None
        cancel_event = threading.Event()
        self._render_cancel = cancel_event

        def _render_and_play() -> None:
            """Render the whole song, compile events, then wire and start the
            player. Runs off the calling thread so rendering never blocks the UI.
            """
            try:
                rendered = SongRenderer(logger=self._logger).render(
                    lines=lines,
                    initial_key=initial_key,
                    initial_bpm=initial_bpm,
                    initial_time_sig=initial_time_sig,
                    note_picker=self._note_picker,
                    start_line_index=start_line_index,
                    start_item_index=start_item_index,
                    cancel_event=cancel_event,
                )
                if rendered is None or cancel_event.is_set():
                    self._logger.debug("Render cancelled before playback start")
                    return

                events = compile_events(rendered, has_callback=has_callback)
                if cancel_event.is_set():
                    return

                # Buffer holds the whole song at once (no backpressure needed).
                buffer = EventBuffer(capacity=len(events) + 1)
                for event in events:
                    buffer.push_event(event)

                self._event_buffer = buffer
                self._player.set_event_buffer(buffer)
                self._player.set_event_callback(on_event_callback, self._application)
                if on_finished_callback:
                    self._player.set_playback_finished_callback(on_finished_callback)

                if cancel_event.is_set():
                    return
                self._player.start_playback()
                self._logger.info("Render complete, playback started")
            except Exception as e:
                self._logger.error(f"Error rendering song for playback: {e}", exc_info=True)

        self._render_thread = threading.Thread(
            target=_render_and_play, daemon=True, name="RenderThread"
        )
        self._render_thread.start()
        return True

    def fretboard_spec_for(self, voicing: str):
        """Resolve a voicing string to its :class:`FretboardSpec`, or ``None``.

        Pure lookup -- unlike :meth:`set_voicing` it does not change the active
        picker. Handles built-in ``guitar:<tuning>`` slugs and ``voicing:<name>``
        registry entries whose model is ``fretboard``; returns ``None`` for
        piano/ensemble voicings or an unresolvable name. Used by the Suggest
        Capo tool, which scores capo positions on a chosen fretboard voicing
        that need not be the active one.
        """
        from models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec

        if voicing.startswith("guitar:"):
            key = voicing.split(":", 1)[1]
            return BUILTIN_FRETBOARDS.get(key, BUILTIN_FRETBOARDS["standard"])
        if voicing.startswith("voicing:"):
            name = voicing.split(":", 1)[1]
            params = self._config.get("voicings", {}).get(name)
            if isinstance(params, dict) and params.get("model") == "fretboard":
                params = {k: v for k, v in params.items() if k != "model"}
                try:
                    return FretboardSpec.from_dict(name, params)
                except Exception as e:  # pragma: no cover - defensive
                    self._logger.warning(f"Invalid fretboard voicing '{name}': {e}")
                    return None
        return None

    def render_song(
        self,
        lines: List[Line],
        initial_key: Optional[str],
        should_abort: Optional[Callable[[], bool]] = None,
        private_picker: bool = False,
        note_picker: Optional[INotePicker] = None,
    ) -> Optional[RenderedSong]:
        """Synchronously render a whole song for export or the chord-sheet strip.

        Unlike :meth:`start_song_playback`, this does not touch the audio
        player: it never calls ``_ensure_initialized`` and never starts
        playback. It always renders from the very start of the song (no
        cancellation, no mid-song resume).

        Args:
            lines: List of Line objects with chords and directives
            initial_key: Initial key signature (from UI)
            should_abort: Optional cooperative-abort predicate threaded into the
                voicing search. ``None`` (default, used by MIDI export) never
                aborts. The chord-sheet strip passes a generation-guard here so a
                superseded render bails promptly (raising
                :class:`~exceptions.RenderAborted`, which this method re-raises).
            private_picker: When ``True``, render with a *freshly created* note
                picker for the current voicing instead of the shared
                ``self._note_picker``. Pickers carry mutable voice-leading state
                and per-instance caches, so the strip -- which can render on a
                background thread concurrently with a playback render -- must not
                share the playback picker. Playback and export keep the shared
                picker (default ``False``) so their goldens are unchanged.
            note_picker: Explicit picker to render with, overriding both the
                shared picker and ``private_picker``. Used by the Suggest Capo
                tool to render (and thus resolve the chords of) a *chosen*
                fretboard voicing that need not be the active one.

        Returns:
            The fully rendered song, or None if there are no chords to render
            or rendering fails.

        Raises:
            RenderAborted: If ``should_abort`` fires during the voicing search.
        """
        total_chords = sum(len(line.chords) for line in lines)
        if total_chords == 0:
            self._logger.info("No chords found to render")
            return None

        if note_picker is None:
            if private_picker:
                note_picker = self._create_note_picker(self._config.get("voicing", "piano"))
            else:
                note_picker = self._note_picker

        try:
            return SongRenderer(logger=self._logger).render(
                lines=lines,
                initial_key=initial_key,
                initial_bpm=self._playback_state.bpm,
                initial_time_sig=self.get_time_signature(),
                note_picker=note_picker,
                start_line_index=0,
                start_item_index=0,
                should_abort=should_abort,
            )
        except RenderAborted:
            # Control flow, not an error: let the strip's job runner drop the
            # abandoned render. Never reached on the export path (should_abort
            # is None there).
            raise
        except Exception as e:
            self._logger.error(f"Error rendering song for export: {e}", exc_info=True)
            return None

    def _resolve_chord_notes(self, chord: ChordInfo, current_key: Optional[str]) -> Optional[ChordNotes]:
        """Resolve a chord to its ``ChordNotes``, stamped with the current key.

        ``current_key`` is always passed through, not just for roman-numeral
        chords: absolute chords still resolve against their own notes
        regardless of key, but ``ChordNotes.key`` records the key in effect
        so key-aware voicing rules (e.g. leading-tone handling, or a future
        ensemble voicer) can see it regardless of how the chord was spelled.
        This mirrors ``SongRenderer._resolve_chord_notes``, which is
        likewise unconditional.

        Args:
            chord: ChordInfo object
            current_key: Current key signature in effect

        Returns:
            ChordNotes object with notes, bass_note, and root, or None if resolution fails
        """
        from chord.helper import ChordHelper

        helper = ChordHelper()
        chord_notes_result = helper.compute_chord_notes(
            chord.chord,
            key=current_key,
            is_relative=chord.is_relative
        )

        return chord_notes_result

    def _notes_to_midi(self, chord_notes: ChordNotes) -> Optional[List[int]]:
        """Convert ChordNotes to MIDI note numbers.

        Args:
            chord_notes: ChordNotes object with notes, bass_note, and root

        Returns:
            List of MIDI note numbers or None
        """
        # Use the injected note picker
        return self._note_picker.chord_to_midi(chord_notes)

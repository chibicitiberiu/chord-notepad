"""ViewModel for the main application window."""

import logging
from typing import Optional, List, Callable
from utils.observable import Observable
from services.config_service import ConfigService
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.documents import DocumentRef, DocumentStore
from models.line import Line
from models.chord import ChordInfo
from models.directive import DirectiveType
from models.notation import Notation
from models.playback_event import PlaybackEventArgs, PlaybackEventType

logger = logging.getLogger(__name__)

_NO_CHORDS_TO_EXPORT = "There are no chords to export."


def _describe_error(exc: BaseException) -> str:
    """A one-line reason for an error dialog.

    Our own exceptions and OS errors already carry a readable message; for
    anything else (a missing module, a bug) prefix the type so it isn't bare.
    """
    from exceptions import ChordNotepadError

    text = str(exc).strip()
    if isinstance(exc, (ChordNotepadError, OSError)) and text:
        return text
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


class MainWindowViewModel(Observable):
    """ViewModel for the main application window.

    This class encapsulates all presentation logic for the main window,
    coordinating between services and providing an API for the view.
    """

    def __init__(
        self,
        config_service: ConfigService,
        audio_service: PlaybackService,
        documents: DocumentStore,
        song_parser_service: SongParserService,
        application
    ):
        """Initialize the ViewModel with required services.

        Args:
            config_service: Configuration service
            audio_service: Audio playback service
            documents: Where documents are read and written (and the
                recent list kept)
            song_parser_service: Chord detection service
            application: Application instance for cross-thread communication
        """
        super().__init__()

        # Services
        self._config = config_service
        self._audio = audio_service
        self._documents = documents
        self._chord = song_parser_service
        self._application = application

        # Observable state properties (private storage with _ prefix)
        self._current_document: Optional[DocumentRef] = None
        self._is_modified: bool = False
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._bpm: int = self._config.get("bpm", 120)
        self._bpm_multiplier: float = float(self._config.get("bpm_multiplier", 1.0))
        self._metronome_enabled: bool = False  # Always starts off per session
        # Convert string notation to enum
        notation_str = self._config.get("notation", "american")
        self._notation: Notation = Notation(notation_str)
        self._font_size: int = self._config.get("font_size", 11)
        self._font_family: str = self._config.get("font_family", "TkFixedFont")
        self._current_text: str = ""
        self._key: Optional[str] = self._config.get("key", None)
        self._time_signature_beats: int = self._config.get("time_signature_beats", 4)
        self._time_signature_unit: int = self._config.get("time_signature_unit", 4)

        # Playback state
        self._current_chord_index: int = 0
        self._playback_lines: List[Line] = []
        self._current_playing_chord: Optional[ChordInfo] = None
        self._current_playback_event: Optional[PlaybackEventArgs] = None
        # Goes up with every start and stop; see start_playback.
        self._playback_generation: int = 0

        # Why the last open/save/export failed, for the view's error dialog.
        self._last_error: Optional[str] = None

    # Properties (read-only access to state)

    @property
    def last_error(self) -> Optional[str]:
        """Reason the last open/save/export failed, or None if it succeeded."""
        return self._last_error

    @property
    def documents(self) -> DocumentStore:
        """The store documents are read from and written to.

        The session keeps the recent list in it (the viewmodel doesn't).
        """
        return self._documents

    @property
    def current_document(self) -> Optional[DocumentRef]:
        """The open document, or None for an unsaved new one."""
        return self._current_document

    @property
    def is_modified(self) -> bool:
        """Check if the current document has unsaved changes."""
        return self._is_modified

    @property
    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._is_paused

    @property
    def bpm(self) -> int:
        """Get the current BPM (beats per minute)."""
        return self._bpm

    @property
    def bpm_multiplier(self) -> float:
        """Get the BPM speed multiplier applied on top of BPM/directives."""
        return self._bpm_multiplier

    @property
    def metronome_enabled(self) -> bool:
        """Whether the metronome click track is on."""
        return self._metronome_enabled

    @property
    def notation(self) -> Notation:
        """Get the current notation system."""
        return self._notation

    @property
    def font_size(self) -> int:
        """Get the current font size."""
        return self._font_size

    @property
    def font_family(self) -> str:
        """Get the current font family."""
        return self._font_family

    @property
    def current_text(self) -> str:
        """Get the current document text."""
        return self._current_text

    @property
    def current_playing_chord(self) -> Optional[ChordInfo]:
        """Get the currently playing chord during playback."""
        return self._current_playing_chord

    @property
    def current_playback_event(self) -> Optional[PlaybackEventArgs]:
        """Get the current playback event data."""
        return self._current_playback_event

    @property
    def key(self) -> Optional[str]:
        """Get the current key signature."""
        return self._key

    @property
    def time_signature_beats(self) -> int:
        """Get the current time signature beats (numerator)."""
        return self._time_signature_beats

    @property
    def time_signature_unit(self) -> int:
        """Get the current time signature unit (denominator)."""
        return self._time_signature_unit

    # Commands (actions triggered by UI)

    def new_file(self) -> bool:
        """Create a new file.

        Returns:
            True if successful or user confirmed, False if cancelled
        """
        # Check for unsaved changes
        if self._is_modified:
            # View should show confirmation dialog
            # For now, we'll assume the view handles this
            pass

        logger.info("Creating new file")
        self.set_and_notify("current_text", "")
        self.set_and_notify("is_modified", False)
        self.set_and_notify("current_document", None)

        return True

    def open_file(self, ref: DocumentRef) -> bool:
        """Open a document.

        Args:
            ref: The document to open

        Returns:
            True if successful, False otherwise (see :attr:`last_error`)
        """
        self._last_error = None
        try:
            logger.info(f"Opening file: {ref.location}")
            content = self._documents.read_text(ref)

            self.set_and_notify("current_text", content)
            self.set_and_notify("is_modified", False)
            self.set_and_notify("current_document", ref)

            # Extract and apply initial settings from first directives in the file
            self._apply_initial_settings_from_content(content)

            return True

        except Exception as e:
            logger.error(f"Failed to open file: {e}", exc_info=True)
            self._last_error = _describe_error(e)
            return False

    def restore_document(self, text: str, ref: Optional[DocumentRef], modified: bool) -> None:
        """Take back a draft: its text, its document (not read) and its modified flag.

        For a process that was killed with unsaved work (Android). Unlike
        :meth:`open_file`, the document isn't read and its directives don't
        change the toolbar (the toolbar values were kept in the config).

        Args:
            text: The draft's text.
            ref: The document the draft belongs to, or None for a new one.
            modified: Whether the draft has unsaved changes.
        """
        logger.info("Restoring a draft%s", f" of {ref.location}" if ref is not None else "")
        self.set_and_notify("current_text", text)
        self.set_and_notify("is_modified", bool(modified))
        self.set_and_notify("current_document", ref)

    def document_renamed(self, ref: DocumentRef) -> None:
        """The open document was renamed: keep working on it under ``ref``.

        Nothing is read or written and the modified flag stays as it is.
        """
        logger.info(f"Document renamed: {ref.location}")
        self.set_and_notify("current_document", ref)

    def save_file(self) -> bool:
        """Save the current file.

        Returns:
            True if successful, False otherwise. When there is no current
            file, returns False with :attr:`last_error` None (the view should
            ask for a name); on a real failure :attr:`last_error` is set.
        """
        if self._current_document is None:
            # Need to show save-as dialog
            self._last_error = None
            return False

        return self.save_file_as(self._current_document)

    def save_file_as(self, ref: DocumentRef) -> bool:
        """Save the current text to a specific document.

        Args:
            ref: The document to save to

        Returns:
            True if successful, False otherwise (see :attr:`last_error`)
        """
        self._last_error = None
        try:
            logger.info(f"Saving file: {ref.location}")
            self._documents.write_text(ref, self._current_text)

            self.set_and_notify("is_modified", False)
            self.set_and_notify("current_document", ref)

            return True

        except Exception as e:
            logger.error(f"Failed to save file: {e}", exc_info=True)
            self._last_error = _describe_error(e)
            return False

    def export_midi_file(self, ref: DocumentRef) -> bool:
        """Export the current document as a standard MIDI file, synchronously.

        :meth:`midi_export_job` and :meth:`finish_midi_export` in one go, on
        the calling thread. The session runs the job on its background worker
        instead.

        Args:
            ref: The document to write the MIDI file to

        Returns:
            True if successful, False otherwise (see :attr:`last_error`)
        """
        job = self.midi_export_job()
        try:
            data = job()
        except Exception as e:
            return self.finish_midi_export(ref, None, e)
        return self.finish_midi_export(ref, data, None)

    def midi_export_job(self) -> Callable[[], bytes]:
        """Snapshot the song for a MIDI export; the job renders it.

        Everything the export depends on (text, notation, key, tempo, time
        signature, instrument, title, a note picker of its own) is captured
        now, so the returned job can run on any thread while the document
        keeps changing. It parses the text, renders the whole song (voicing +
        timing) and returns a format-1 SMF.

        Returns:
            A job returning the MIDI file's bytes. It raises if there are no
            chords (``ChordNotepadError``) or rendering fails.
        """
        from exceptions import ChordNotepadError

        text, notation, key = self._current_text, self._notation, self._key
        program = self._config.get("instrument", 0)
        title = self._current_document.stem if self._current_document is not None else "Untitled"
        playback = self._audio.get_playback_state()
        bpm = playback.bpm
        time_signature = (playback.time_signature_beats, playback.time_signature_unit)
        # Its own picker: the shared one may be voicing a playback render on
        # the render thread meanwhile.
        picker = self._audio.create_note_picker()

        def render() -> bytes:
            # Imported lazily to keep the (potentially heavier) MIDI writer
            # dependencies out of application startup.
            from services.midi_file_writer import render_midi_bytes

            lines = self._chord.detect_chords_in_text(text, notation)
            if not any(line.chords for line in lines):
                logger.warning("No chords found to export as MIDI")
                raise ChordNotepadError(_NO_CHORDS_TO_EXPORT)
            rendered = self._audio.render_song(
                lines, key, note_picker=picker, raise_errors=True,
                initial_bpm=bpm, initial_time_sig=time_signature)
            if rendered is None:
                logger.warning("No chords found to export as MIDI")
                raise ChordNotepadError(_NO_CHORDS_TO_EXPORT)
            return render_midi_bytes(rendered, program=program, title=title)

        return render

    def finish_midi_export(self, ref: DocumentRef, data: Optional[bytes],
                           error: Optional[BaseException]) -> bool:
        """Write what a :meth:`midi_export_job` produced (or record why it failed).

        Args:
            ref: The document to write the MIDI file to.
            data: The job's bytes, or None if it raised.
            error: What the job raised, or None.

        Returns:
            True if the file was written, False otherwise (see :attr:`last_error`)
        """
        self._last_error = None
        try:
            if error is not None:
                raise error
            logger.info(f"Exporting MIDI file: {ref.location}")
            self._documents.write_bytes(ref, data)
            return True
        except Exception as e:
            logger.error(f"Failed to export MIDI file: {e}", exc_info=True)
            self._last_error = _describe_error(e)
            return False

    def on_text_changed(self, text: str) -> None:
        """Handle text content changes.

        Args:
            text: The new text content
        """
        if text != self._current_text:
            self._current_text = text
            if not self._is_modified:
                self.set_and_notify("is_modified", True)

    def toggle_playback(self) -> None:
        """Toggle playback on/off."""
        if self._is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self, from_char_offset: int = 0) -> bool:
        """Start sequential chord playback with directive support.

        Args:
            from_char_offset: Character offset to start playback from (0 = beginning)

        Returns:
            True if playback started, False if there was nothing to play

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        if self._is_playing:
            logger.warning("Playback already active")
            return False

        # Parse text into lines with chords and directives
        self._playback_lines = self._chord.detect_chords_in_text(
            self._current_text,
            self._notation
        )

        # Find starting line and item index if starting from a specific position
        start_line_index = 0
        start_item_index = 0

        if from_char_offset > 0:
            logger.info(f"Starting playback from character offset {from_char_offset}")
            # Find the first chord where chord.end > cursor_position
            found = False
            for line_idx, line in enumerate(self._playback_lines):
                for item_idx, item in enumerate(line.items):
                    # Check if this is a chord
                    from models.chord import ChordInfo
                    if isinstance(item, ChordInfo) and item.is_valid:
                        # Found the first chord after cursor
                        if item.end > from_char_offset:
                            start_line_index = line_idx
                            start_item_index = item_idx
                            found = True
                            logger.info(f"Starting from line {line_idx}, item {item_idx} (chord: {item.chord})")
                            break
                if found:
                    break

            if not found:
                logger.warning("No chords found after cursor position")
                return False

        # Everything this run reports is tagged with its generation. Stopping
        # (or starting another run) moves the generation on, so a ping, an
        # end or an error the old run posted before it stopped is dropped
        # instead of landing in the new run. Checked on the UI thread, where
        # the generation changes.
        self._playback_generation += 1
        generation = self._playback_generation

        def is_current() -> bool:
            if generation == self._playback_generation:
                return True
            logger.debug("Dropping a callback from an earlier playback run")
            return False

        # Wrap finished callback to run on UI thread
        def on_finished_wrapper():
            logger.debug("Playback finished - queueing UI callback")
            self._application.queue_ui_callback(
                lambda: self._on_playback_finished() if is_current() else None)

        # Event callback: the player already marshals this onto the UI thread
        # via Application.queue_ui_callback (it fires from the playback thread),
        # so invoke the handler directly here to avoid double-marshalling.
        def on_event_wrapper(event_args: PlaybackEventArgs):
            logger.debug(f"Playback event: {event_args.event_type}")
            if is_current():
                self._on_playback_event(event_args)

        # Render failures happen on the render thread: hand them to the UI thread.
        def on_error_wrapper(message: str):
            self._application.queue_ui_callback(
                lambda: self.notify("playback_error", message) if is_current() else None)

        # Start playback (AudioService handles all directive processing and chord resolution)
        success = self._audio.start_song_playback(
            lines=self._playback_lines,
            initial_key=self._key,
            on_finished_callback=on_finished_wrapper,
            on_event_callback=on_event_wrapper,
            start_line_index=start_line_index,
            start_item_index=start_item_index,
            on_error_callback=on_error_wrapper,
        )

        if success:
            self.set_and_notify("is_playing", True)
            self.set_and_notify("is_paused", False)

        return success

    def pause_playback(self) -> None:
        """Pause ongoing playback."""
        if not self._is_playing or self._is_paused:
            return

        logger.debug("Pausing playback")
        self._audio.pause_playback()
        self.set_and_notify("is_paused", True)

    def resume_playback(self) -> None:
        """Resume paused playback."""
        if not self._is_playing or not self._is_paused:
            return

        logger.debug("Resuming playback")
        self._audio.resume_playback()
        self.set_and_notify("is_paused", False)

    def stop_playback(self) -> None:
        """Stop ongoing playback and all notes."""
        if not self._is_playing:
            # Even if not playing, stop all notes to clear any stuck notes
            logger.debug("Stopping all notes (not playing)")
            self._audio.stop_all_notes()
            return

        logger.debug("Stopping playback")
        self._playback_generation += 1  # what the stopped run still posts is stale
        self._audio.stop_playback()
        self._current_chord_index = 0
        self.set_and_notify("is_playing", False)
        self.set_and_notify("is_paused", False)

    def _on_playback_event(self, event_args: PlaybackEventArgs) -> None:
        """Internal callback for playback events.

        Args:
            event_args: Playback event data
        """
        logger.debug(f"Processing playback event on UI thread: {event_args.event_type}")
        # Use set_and_notify which will set _current_playback_event and notify observers
        self.set_and_notify("current_playback_event", event_args)

    def _on_playback_finished(self) -> None:
        """Internal callback when playback finishes."""
        logger.info("Playback finished callback executing on UI thread")
        self._current_chord_index = 0
        self.set_and_notify("is_playing", False)
        self.set_and_notify("is_paused", False)
        self.set_and_notify("current_playback_event", None)
        logger.info("Playback state reset complete")

    def on_chord_clicked(self, chord_info: ChordInfo) -> None:
        """Handle chord click event (play chord immediately with current key).

        Args:
            chord_info: Information about the clicked chord

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        logger.debug(f"Playing chord on click: {chord_info.chord} (key={self._key})")
        self._audio.play_chord_immediate(chord_info, self._key)

    def set_bpm(self, bpm: int) -> None:
        """Set playback tempo.

        Args:
            bpm: Beats per minute (20-400)
        """
        if not (20 <= bpm <= 400):
            logger.warning(f"Invalid BPM value: {bpm}")
            return

        logger.debug(f"Setting BPM to {bpm}")
        self._audio.set_bpm(bpm)
        self._config.set("bpm", bpm)
        self.set_and_notify("bpm", bpm)

    def toggle_metronome(self) -> None:
        """Arm or disarm the metronome.

        The actual click track is scheduled by the playback engine; this
        viewmodel just owns the on/off state and forwards it to the audio
        service.
        """
        new_state = not self._metronome_enabled
        self._audio.set_metronome_enabled(new_state)
        # `set_and_notify` updates the backing field and only fires observers
        # when the value actually changed — let it own both writes.
        self.set_and_notify("metronome_enabled", new_state)

    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Set the playback speed multiplier (applied on top of BPM/directives).

        Args:
            multiplier: Speed multiplier (0.125 - 4.0)
        """
        if not (0.125 <= multiplier <= 4.0):
            logger.warning(f"Invalid BPM multiplier: {multiplier}")
            return

        logger.debug(f"Setting BPM multiplier to {multiplier}")
        self._audio.set_bpm_multiplier(multiplier)
        self._config.set("bpm_multiplier", multiplier)
        self.set_and_notify("bpm_multiplier", multiplier)

    def set_key(self, key: Optional[str]) -> None:
        """Set the key signature.

        Args:
            key: Key signature (e.g., 'C', 'Am', 'G') or None
        """
        logger.debug(f"Setting key to {key}")
        self._audio.set_key(key) if key else None
        self._config.set("key", key)
        self.set_and_notify("key", key)

    def set_time_signature(self, beats: int, unit: int) -> None:
        """Set the time signature.

        Args:
            beats: Number of beats per measure
            unit: Beat unit (4 = quarter note, etc.)
        """
        if beats < 1 or beats > 16:
            logger.warning(f"Invalid time signature beats: {beats}")
            return
        if unit not in [1, 2, 4, 8, 16]:
            logger.warning(f"Invalid time signature unit: {unit}")
            return

        logger.debug(f"Setting time signature to {beats}/{unit}")
        self._audio.set_time_signature_from_state(beats, unit)
        self._config.set("time_signature_beats", beats)
        self._config.set("time_signature_unit", unit)
        self.set_and_notify("time_signature_beats", beats)
        self.set_and_notify("time_signature_unit", unit)

    def get_voicing(self) -> str:
        """Get the current voicing style.

        Returns:
            Voicing string like 'piano', 'guitar:standard', etc.
        """
        return self._config.get("voicing", "piano")

    def set_voicing(self, voicing: str) -> None:
        """Set the voicing style.

        Args:
            voicing: Voicing string like 'piano', 'guitar:standard', etc.
        """
        logger.debug(f"Setting voicing to {voicing}")
        self._audio.set_voicing(voicing)
        # Notify unconditionally (not set_and_notify, which skips equal
        # values): re-selecting or editing the active voicing in place keeps
        # the same selection string, but the note picker was still rebuilt,
        # so observers (e.g. the chord sheet) must re-render regardless.
        self.notify("voicing", voicing)

    def get_voicings(self) -> dict:
        """Get the raw voicings registry.

        Returns:
            Dictionary mapping voicing name to its parameter dict, each of
            the form ``{"model": "fretboard" | "ensemble" | "piano", ...}``.
        """
        return self._config.get("voicings", {})

    def get_instrument(self) -> int:
        """Get the current MIDI instrument program number.

        Returns:
            MIDI program number (0-127)
        """
        return self._config.get("instrument", 0)

    def set_instrument(self, program: int) -> None:
        """Set the MIDI instrument.

        Args:
            program: MIDI program number (0-127)
        """
        logger.debug(f"Setting instrument to program {program}")
        self._config.set("instrument", program)
        self._audio.set_instrument(program)

    def get_available_instruments(self) -> List[tuple]:
        """Get list of available instruments from the soundfont.

        Returns:
            List of tuples (program_number, instrument_name)
        """
        return self._audio.get_available_instruments()

    def toggle_notation(self) -> None:
        """Toggle between American and European notation."""
        new_notation = Notation.EUROPEAN if self._notation == Notation.AMERICAN else Notation.AMERICAN
        self.set_notation(new_notation)

    def set_notation(self, notation: Notation) -> None:
        """Set the notation system preference.

        Note: This only changes the notation preference for new chord detection.
        It does NOT convert existing text. Use convert_text_to_american() or
        convert_text_to_european() methods for explicit conversion.

        Args:
            notation: Notation enum value
        """
        if notation != self._notation:
            logger.info(f"Changing notation preference to {notation.value}")
            self._config.set("notation", notation.value)
            self.set_and_notify("notation", notation)

    def convert_text_to_american(self, lines: Optional[List[Line]] = None) -> None:
        """Convert the current text from European to American notation.

        Also switches the editor's notation preference to American so the
        new chords get highlighted, clickable, and parsed correctly.

        Args:
            lines: Optional pre-parsed document model. If provided, the
                detector is not re-run for the substitution step.
        """
        logger.info("Converting text to American notation")
        converted_text = self._chord.convert_to_american(self._current_text, lines)
        self.set_and_notify("current_text", converted_text)
        # Flip the toolbar / editor notation so detection re-runs with the
        # target notation against the freshly-substituted text.
        self.set_notation(Notation.AMERICAN)
        if not self._is_modified:
            self.set_and_notify("is_modified", True)

    def convert_text_to_european(self, lines: Optional[List[Line]] = None) -> None:
        """Convert the current text from American to European notation.

        Also switches the editor's notation preference to European so the
        new chords get highlighted, clickable, and parsed correctly.

        Args:
            lines: Optional pre-parsed document model. If provided, the
                detector is not re-run for the substitution step.
        """
        logger.info("Converting text to European notation")
        converted_text = self._chord.convert_to_european(self._current_text, lines)
        self.set_and_notify("current_text", converted_text)
        self.set_notation(Notation.EUROPEAN)
        if not self._is_modified:
            self.set_and_notify("is_modified", True)

    def transpose(self, semitones: int, region: Optional[tuple] = None) -> None:
        """Transpose chords by ``semitones`` and replace the document text.

        Mirrors the ``convert_text_to_*`` command pattern: call the pure
        service, then ``set_and_notify("current_text", ...)`` so the editor
        replaces its content (the view groups this into one undo step).

        When the whole document is transposed (``region is None``) the toolbar
        key, if set, is shifted too so roman numerals keep sounding the same.

        Args:
            semitones: Number of semitones to shift (positive = up).
            region: Optional ``(start, end)`` character range to limit the
                transpose to a text selection; ``None`` = whole document.
        """
        if semitones == 0:
            return

        from services.transpose_service import transpose_text, transpose_key

        logger.info(f"Transposing by {semitones} semitones (region={region})")
        new_text = transpose_text(self._current_text, semitones, self._notation, region)
        self.set_and_notify("current_text", new_text)

        # Whole-document transpose also shifts the toolbar key so relative
        # (roman-numeral) chords resolve to the same pitches as before.
        if region is None and self._key:
            new_key = transpose_key(self._key, semitones, self._notation)
            self.set_key(new_key)

        if not self._is_modified:
            self.set_and_notify("is_modified", True)

    # -- Suggest Capo (Tools) ------------------------------------------------

    def capo_voicing_options(self) -> List[tuple]:
        """List ``(display_name, voicing_string)`` for every fretboard voicing.

        Covers the built-in fretboard tunings and any ``fretboard``-model entry
        in the voicings registry. The Suggest Capo dialog shows the display
        names; the voicing string resolves back to a :class:`FretboardSpec`.
        """
        from models.fretboard_spec import BUILTIN_FRETBOARDS

        options: List[tuple] = []
        for key in ("standard", "drop_d", "dadgad", "open_g", "ukulele"):
            options.append((BUILTIN_FRETBOARDS[key].label, f"guitar:{key}"))
        for name, params in self.get_voicings().items():
            if isinstance(params, dict) and params.get("model") == "fretboard":
                options.append((name, f"voicing:{name}"))
        return options

    def default_capo_voicing(self) -> str:
        """The voicing string to preselect in the Suggest Capo dialog.

        The active voicing when it is a fretboard voicing (the common case),
        otherwise built-in standard guitar -- a capo is a fretboard concept, and
        the active voicing may be piano or an ensemble.
        """
        active = self.get_voicing()
        if self._audio.fretboard_spec_for(active) is not None:
            return active
        return "guitar:standard"

    def suggest_capo_for(self, voicing: str, region: Optional[tuple] = None) -> Optional[int]:
        """Best capo fret for ``voicing`` over ``region`` (whole song if ``None``).

        Runs :meth:`capo_job` on the calling thread. Returns the suggested
        fret, or ``None`` when the voicing is not a fretboard voicing, there
        are no chords in range, or no capo beats capo 0 meaningfully.
        """
        job = self.capo_job(voicing, region)
        return job() if job is not None else None

    def capo_job(self, voicing: str, region: Optional[tuple] = None
                 ) -> Optional[Callable[[], Optional[int]]]:
        """Snapshot the song for Suggest Capo on ``voicing``; the job scores it.

        The job renders the document (as it is now) with a picker on the
        chosen voicing's spec, so chords resolve with the same key/loop
        context as everywhere else, keeps the chords whose source span
        overlaps ``region``, and scores capo positions with
        :func:`services.capo_advisor.suggest_capo`. It only uses what was
        captured here, so it can run on any thread.

        Returns:
            None when ``voicing`` is not a fretboard voicing; otherwise a job
            returning the suggested fret, or None when there are no chords in
            range or no capo beats capo 0 meaningfully. Rendering errors are
            raised by the job.
        """
        spec = self._audio.fretboard_spec_for(voicing)
        if spec is None:
            return None

        text, notation, key = self._current_text, self._notation, self._key
        playback = self._audio.get_playback_state()
        bpm = playback.bpm
        time_signature = (playback.time_signature_beats, playback.time_signature_unit)

        def score() -> Optional[int]:
            from audio.guitar_chord_picker import GuitarChordPicker
            from services.capo_advisor import suggest_capo

            lines = self._chord.detect_chords_in_text(text, notation)
            rendered = self._audio.render_song(
                lines, key, note_picker=GuitarChordPicker(spec), raise_errors=True,
                initial_bpm=bpm, initial_time_sig=time_signature)
            if rendered is None:
                return None

            chords = rendered.chords
            if region is not None:
                start, end = region
                chords = [rc for rc in chords
                          if rc.chord_info.start < end and rc.chord_info.end > start]
            sequence = [rc.chord_notes for rc in chords if rc.chord_notes is not None]
            if not sequence:
                return None
            return suggest_capo(spec, sequence)

        return score

    def insert_capo(self, capo: int, region: Optional[tuple] = None) -> None:
        """Insert a ``{capo: N}`` directive and replace the document text.

        Mirrors :meth:`transpose`: it calls the pure
        :func:`services.capo_insert.insert_capo_directive` and
        ``set_and_notify("current_text", ...)`` so the editor swaps its content
        (the view groups this into one undo step). The directive lands at the
        start of the line containing the selection (or the top of the document
        when ``region`` is ``None``).
        """
        from services.capo_insert import insert_capo_directive

        selection_start = region[0] if region is not None else None
        new_text, _offset = insert_capo_directive(
            self._current_text, capo, selection_start)
        self.set_and_notify("current_text", new_text)
        if not self._is_modified:
            self.set_and_notify("is_modified", True)

    def set_font_size(self, size: int) -> None:
        """Set editor font size.

        Args:
            size: Font size (6-72)
        """
        if not (6 <= size <= 72):
            logger.warning(f"Invalid font size: {size}")
            return

        logger.debug(f"Setting font size to {size}")
        self._config.set("font_size", size)
        self.set_and_notify("font_size", size)

    def set_font_family(self, family: str) -> None:
        """Set editor font family.

        Args:
            family: Font family name
        """
        logger.debug(f"Setting font family to {family}")
        self._config.set("font_family", family)
        self.set_and_notify("font_family", family)

    def reload_font_settings(self) -> None:
        """Re-apply the font family and size stored in the config.

        For the Settings dialog, which writes the config directly.
        """
        self.set_font_family(self._config.get("font_family", self._font_family))
        self.set_font_size(self._config.get("font_size", self._font_size))

    def increase_font_size(self) -> None:
        """Increase font size by 1."""
        self.set_font_size(min(self._font_size + 1, 72))

    def decrease_font_size(self) -> None:
        """Decrease font size by 1."""
        self.set_font_size(max(self._font_size - 1, 6))

    def reset_font_size(self) -> None:
        """Reset font size to default."""
        default_size = 11
        self.set_font_size(default_size)

    def on_mouse_wheel_zoom(self, delta: int) -> None:
        """Handle mouse wheel zoom (Ctrl+MouseWheel).

        Args:
            delta: Mouse wheel delta (positive = up, negative = down)
        """
        if delta > 0:
            self.increase_font_size()
        else:
            self.decrease_font_size()

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes.

        Returns:
            True if there are unsaved changes, False otherwise
        """
        return self._is_modified

    def set_window_geometry(self, geometry: str) -> None:
        """Save window geometry to configuration.

        Args:
            geometry: Window geometry string (e.g., "900x600+100+100")
        """
        self._config.set("window_geometry", geometry)

    def get_window_geometry(self) -> str:
        """Get saved window geometry.

        Returns:
            Window geometry string
        """
        return self._config.get("window_geometry", "900x600")

    def get_show_quick_start_on_startup(self) -> bool:
        """Get whether to show quick start dialog on startup.

        Returns:
            True if quick start should be shown on startup
        """
        return self._config.get("show_quick_start_on_startup", True)

    def set_show_quick_start_on_startup(self, show: bool) -> None:
        """Set whether to show quick start dialog on startup.

        Args:
            show: True to show quick start on startup, False to disable
        """
        self._config.set("show_quick_start_on_startup", show)

    def _apply_initial_settings_from_content(self, content: str) -> None:
        """Parse content and apply initial settings from first directives.

        This is called when loading a file to set toolbar values based on
        the first occurrence of each directive type in the document.

        Args:
            content: The text content of the file
        """
        try:
            # Parse the content to extract lines with directives
            lines = self._chord.detect_chords_in_text(content, self._notation)

            # Extract initial settings from first directives
            settings = self._extract_initial_settings_from_lines(lines)

            # Apply settings to toolbar (UI state)
            if 'bpm' in settings:
                logger.info(f"Setting initial BPM from directive: {settings['bpm']}")
                self.set_bpm(settings['bpm'])

            if 'key' in settings:
                logger.info(f"Setting initial key from directive: {settings['key']}")
                self.set_key(settings['key'])

            if 'time_signature' in settings:
                beats, unit = settings['time_signature']
                logger.info(f"Setting initial time signature from directive: {beats}/{unit}")
                self.set_time_signature(beats, unit)

        except Exception as e:
            logger.warning(f"Failed to extract initial settings from content: {e}")
            # Not critical - just continue with default settings

    def _extract_initial_settings_from_lines(self, lines: List[Line]) -> dict:
        """Extract initial playback settings from first directives in document.

        Scans through lines sequentially and finds the first occurrence of each
        directive type (BPM, KEY, TIME_SIGNATURE). Returns these as initial settings.

        Args:
            lines: Parsed lines from the document

        Returns:
            Dict with 'bpm', 'key', and/or 'time_signature' if found
        """
        settings = {}
        found = {'bpm': False, 'key': False, 'time': False}

        for line in lines:
            for directive in line.directives:
                if directive.type == DirectiveType.BPM and not found['bpm']:
                    settings['bpm'] = directive.bpm
                    found['bpm'] = True

                elif directive.type == DirectiveType.KEY and not found['key']:
                    settings['key'] = directive.key
                    found['key'] = True

                elif directive.type == DirectiveType.TIME_SIGNATURE and not found['time']:
                    settings['time_signature'] = (directive.beats, directive.unit)
                    found['time'] = True

            # Early exit if we found all directive types
            if all(found.values()):
                break

        return settings

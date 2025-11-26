"""ViewModel for the main application window."""

import logging
from pathlib import Path
from typing import Optional, List, Callable
from utils.observable import Observable
from services.config_service import ConfigService
from services.playback_service import PlaybackService
from services.file_service import FileService
from services.song_parser_service import SongParserService
from models.line import Line
from models.chord import ChordInfo
from models.directive import DirectiveType
from models.notation import Notation
from models.playback_event import PlaybackEventArgs, PlaybackEventType

logger = logging.getLogger(__name__)


class MainWindowViewModel(Observable):
    """ViewModel for the main application window.

    This class encapsulates all presentation logic for the main window,
    coordinating between services and providing an API for the view.
    """

    def __init__(
        self,
        config_service: ConfigService,
        audio_service: PlaybackService,
        file_service: FileService,
        song_parser_service: SongParserService,
        application
    ):
        """Initialize the ViewModel with required services.

        Args:
            config_service: Configuration service
            audio_service: Audio playback service
            file_service: File I/O service
            song_parser_service: Chord detection service
            application: Application instance for cross-thread communication
        """
        super().__init__()

        # Services
        self._config = config_service
        self._audio = audio_service
        self._file = file_service
        self._chord = song_parser_service
        self._application = application

        # Observable state properties (private storage with _ prefix)
        self._current_file: Optional[Path] = None
        self._is_modified: bool = False
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._bpm: int = self._config.get("bpm", 120)
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

    # Properties (read-only access to state)

    @property
    def current_file(self) -> Optional[Path]:
        """Get the currently opened file path."""
        return self._current_file

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
        self._current_file = None
        self.set_and_notify("current_text", "")
        self.set_and_notify("is_modified", False)
        self.set_and_notify("current_file", None)

        return True

    def open_file(self, path: Path) -> bool:
        """Open a file.

        Args:
            path: Path to the file to open

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Opening file: {path}")
            content = self._file.open_file(path)

            self._current_file = path
            self.set_and_notify("current_text", content)
            self.set_and_notify("is_modified", False)
            self.set_and_notify("current_file", path)

            # Extract and apply initial settings from first directives in the file
            self._apply_initial_settings_from_content(content)

            # Add to recent files
            self._file.add_recent_file(path)

            return True

        except Exception as e:
            logger.error(f"Failed to open file: {e}", exc_info=True)
            return False

    def save_file(self) -> bool:
        """Save the current file.

        Returns:
            True if successful, False otherwise
        """
        if self._current_file is None:
            # Need to show save-as dialog
            return False

        return self.save_file_as(self._current_file)

    def save_file_as(self, path: Path) -> bool:
        """Save the current file to a specific path.

        Args:
            path: Path to save the file to

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Saving file: {path}")
            self._file.save_file(path, self._current_text)

            self._current_file = path
            self.set_and_notify("is_modified", False)
            self.set_and_notify("current_file", path)

            # Add to recent files
            self._file.add_recent_file(path)

            return True

        except Exception as e:
            logger.error(f"Failed to save file: {e}", exc_info=True)
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
            True if playback started, False otherwise
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

        # Wrap finished callback to run on UI thread
        def on_finished_wrapper():
            logger.debug("Playback finished - queueing UI callback")
            self._application.queue_ui_callback(self._on_playback_finished)

        # Wrap event callback to run on UI thread
        def on_event_wrapper(event_args: PlaybackEventArgs):
            logger.debug(f"Playback event - queueing UI callback: {event_args.event_type}")
            self._application.queue_ui_callback(lambda: self._on_playback_event(event_args))

        # Start playback (AudioService handles all directive processing and chord resolution)
        success = self._audio.start_song_playback(
            lines=self._playback_lines,
            initial_key=self._key,
            on_finished_callback=on_finished_wrapper,
            on_event_callback=on_event_wrapper,
            start_line_index=start_line_index,
            start_item_index=start_item_index
        )

        if success:
            self.set_and_notify("is_playing", True)
            self.set_and_notify("is_paused", False)

        return success

    def start_playback_from_cursor(self, cursor_position: str) -> bool:
        """Start playback from a specific cursor position.

        Args:
            cursor_position: Tkinter cursor position (e.g., "9.2" = line 9, char 2)

        Returns:
            True if playback started, False otherwise
        """
        # Convert cursor position to character offset
        # cursor_position format: "line.column" (1-indexed)
        try:
            line_num, col_num = cursor_position.split('.')
            line_num = int(line_num)
            col_num = int(col_num)
        except (ValueError, AttributeError):
            logger.error(f"Invalid cursor position: {cursor_position}")
            return False

        # Calculate character offset
        # Count characters in all lines before the cursor line, plus column offset
        lines = self._current_text.split('\n')
        char_offset = 0
        for i in range(line_num - 1):  # line_num is 1-indexed
            if i < len(lines):
                char_offset += len(lines[i]) + 1  # +1 for newline

        char_offset += col_num

        logger.info(f"Cursor position {cursor_position} = character offset {char_offset}")
        return self.start_playback(from_char_offset=char_offset)

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
        """
        logger.debug(f"Playing chord on click: {chord_info.chord} (key={self._key})")
        self._audio.play_chord_immediate(chord_info, self._key)

    def set_bpm(self, bpm: int) -> None:
        """Set playback tempo.

        Args:
            bpm: Beats per minute (60-240)
        """
        if not (60 <= bpm <= 240):
            logger.warning(f"Invalid BPM value: {bpm}")
            return

        logger.debug(f"Setting BPM to {bpm}")
        self._audio.set_bpm(bpm)
        self._config.set("bpm", bpm)
        self.set_and_notify("bpm", bpm)

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

    def get_custom_tunings(self) -> dict:
        """Get custom guitar tunings.

        Returns:
            Dictionary of custom tuning names to tuning lists
        """
        return self._config.get("custom_tunings", {})

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

    def convert_text_to_american(self) -> None:
        """Convert the current text from European to American notation.

        This is an explicit conversion action, typically called from the Tools menu.
        """
        logger.info("Converting text to American notation")
        converted_text = self._chord.convert_to_american(self._current_text)
        self.set_and_notify("current_text", converted_text)
        if not self._is_modified:
            self.set_and_notify("is_modified", True)

    def convert_text_to_european(self) -> None:
        """Convert the current text from American to European notation.

        This is an explicit conversion action, typically called from the Tools menu.
        """
        logger.info("Converting text to European notation")
        converted_text = self._chord.convert_to_european(self._current_text)
        self.set_and_notify("current_text", converted_text)
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

    def increase_font_size(self) -> None:
        """Increase font size by 1."""
        self.set_font_size(min(self._font_size + 1, 72))

    def decrease_font_size(self) -> None:
        """Decrease font size by 1."""
        self.set_font_size(max(self._font_size - 1, 6))

    def get_recent_files(self) -> List[Path]:
        """Get list of recently opened files.

        Returns:
            List of file paths
        """
        return self._file.get_recent_files()

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

    def get_window_title(self) -> str:
        """Get the window title based on current state.

        Returns:
            Window title string
        """
        if self._current_file:
            filename = self._current_file.name
            modified_marker = "*" if self._is_modified else ""
            return f"{filename}{modified_marker} - Chord Notepad"
        else:
            modified_marker = "*" if self._is_modified else ""
            return f"Untitled{modified_marker} - Chord Notepad"

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

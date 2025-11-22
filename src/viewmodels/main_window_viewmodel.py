"""ViewModel for the main application window."""

import logging
from pathlib import Path
from typing import Optional, List, Callable
from utils.observable import Observable
from services.config_service import ConfigService
from services.audio_service import AudioService
from services.file_service import FileService
from services.chord_detection_service import ChordDetectionService
from chord.line_model import Line
from chord.chord_model import ChordInfo
from models.notation import Notation

logger = logging.getLogger(__name__)


class MainWindowViewModel(Observable):
    """ViewModel for the main application window.

    This class encapsulates all presentation logic for the main window,
    coordinating between services and providing an API for the view.
    """

    def __init__(
        self,
        config_service: ConfigService,
        audio_service: AudioService,
        file_service: FileService,
        chord_detection_service: ChordDetectionService,
        application
    ):
        """Initialize the ViewModel with required services.

        Args:
            config_service: Configuration service
            audio_service: Audio playback service
            file_service: File I/O service
            chord_detection_service: Chord detection service
            application: Application instance for cross-thread communication
        """
        super().__init__()

        # Services
        self._config = config_service
        self._audio = audio_service
        self._file = file_service
        self._chord = chord_detection_service
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

        # Playback state
        self._current_chord_index: int = 0
        self._playback_lines: List[Line] = []
        self._current_playing_chord: Optional[ChordInfo] = None

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

    def start_playback(self) -> bool:
        """Start sequential chord playback.

        Returns:
            True if playback started, False otherwise
        """
        if self._is_playing:
            logger.warning("Playback already active")
            return False

        # Detect chords in current text
        self._playback_lines = self._chord.detect_chords_in_text(
            self._current_text,
            self._notation
        )

        # Extract all chords
        all_chords: List[ChordInfo] = []
        for line in self._playback_lines:
            all_chords.extend(line.chords)

        if not all_chords:
            logger.info("No chords found for playback")
            return False

        logger.info(f"Starting playback of {len(all_chords)} chords")
        self._current_chord_index = 0

        # Set up playback callback
        def get_next_chord():
            if self._current_chord_index >= len(all_chords):
                return None

            chord = all_chords[self._current_chord_index]
            self._current_chord_index += 1

            # Convert to MIDI notes
            from audio.chord_picker import ChordNotePicker
            picker = ChordNotePicker(
                chord_octave=self._config.get("default_octave", 4),
                bass_octave=self._config.get("bass_octave", 3),
                add_bass=True
            )
            midi_notes = picker.chord_to_midi(chord.notes)

            # Return (midi_notes, duration_in_beats)
            # Play each chord for one full bar (beats per measure from time signature)
            time_signature = self._audio.get_time_signature()
            beats_per_measure = time_signature[0]
            return (midi_notes, float(beats_per_measure))

        # Start audio playback (wrap callback to run on UI thread)
        def on_finished_wrapper():
            logger.debug("Playback finished - queueing UI callback")
            self._application.queue_ui_callback(self._on_playback_finished)

        self._audio.start_sequential_playback(
            get_next_callback=get_next_chord,
            on_finished_callback=on_finished_wrapper
        )

        self.set_and_notify("is_playing", True)
        self.set_and_notify("is_paused", False)

        return True

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
        """Stop ongoing playback."""
        if not self._is_playing:
            return

        logger.debug("Stopping playback")
        self._audio.stop_playback()
        self._current_chord_index = 0
        self.set_and_notify("is_playing", False)
        self.set_and_notify("is_paused", False)

    def _on_playback_finished(self) -> None:
        """Internal callback when playback finishes."""
        logger.info("Playback finished callback executing on UI thread")
        self._current_chord_index = 0
        self.set_and_notify("is_playing", False)
        self.set_and_notify("is_paused", False)
        logger.info("Playback state reset complete")

    def on_chord_clicked(self, chord_info: ChordInfo) -> None:
        """Handle chord click event (play chord immediately).

        Args:
            chord_info: Information about the clicked chord
        """
        logger.debug(f"Playing chord on click: {chord_info.chord}")
        self._audio.play_chord_immediate(chord_info)

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

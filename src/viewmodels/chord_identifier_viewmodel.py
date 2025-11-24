"""ViewModel for the chord identifier window."""

import logging
from typing import List, Tuple, Set
from utils.observable import Observable
from services.song_parser_service import SongParserService

logger = logging.getLogger(__name__)


class ChordIdentifierViewModel(Observable):
    """ViewModel for the chord identifier window.

    Manages note selection, chord identification, and playback for the
    chord identifier UI.
    """

    def __init__(self, song_parser_service: SongParserService, audio_service=None):
        """Initialize the ViewModel.

        Args:
            song_parser_service: Service for chord detection and identification
            audio_service: Optional audio service for playing notes and chords
        """
        super().__init__()

        self._chord_service = song_parser_service
        self._audio_service = audio_service

        # Observable state
        self._selected_notes: Set[Tuple[str, int]] = set()  # (note_name, octave) = []
        self._identified_chords: List[str] = []
        self._notation: str = "american"

    @property
    def selected_notes(self) -> Set[Tuple[str, int]]:
        """Get the currently selected notes."""
        return self._selected_notes

    @property
    def identified_chords(self) -> List[str]:
        """Get the identified chord names."""
        return self._identified_chords

    @property
    def notation(self) -> str:
        """Get the current notation system."""
        return self._notation

    def toggle_note(self, note_name: str, octave: int) -> None:
        """Toggle a note selection on/off.

        Args:
            note_name: Note name (e.g., "C", "D#", "Bb")
            octave: Octave number
        """
        note_tuple = (note_name, octave)

        if note_tuple in self._selected_notes:
            self._selected_notes.remove(note_tuple)
            logger.debug(f"Deselected note: {note_name}{octave}")
        else:
            self._selected_notes.add(note_tuple)
            logger.debug(f"Selected note: {note_name}{octave}")

        self.notify("selected_notes", self._selected_notes.copy())

        # Re-identify chords with new selection
        self._identify_chords()

    def set_notes(self, notes: List[Tuple[str, int]]) -> None:
        """Set the selected notes.

        Args:
            notes: List of (note_name, octave) tuples
        """
        self._selected_notes = set(notes)
        self.notify("selected_notes", self._selected_notes.copy())
        self._identify_chords()

    def clear_selection(self) -> None:
        """Clear all selected notes."""
        logger.debug("Clearing note selection")
        self._selected_notes.clear()
        self._identified_chords.clear()
        self.notify("selected_notes", self._selected_notes.copy())
        self.notify("identified_chords", self._identified_chords.copy())

    def _identify_chords(self) -> None:
        """Identify possible chords from selected notes with advanced logic.

        This includes:
        - Trying all inversions/rotations
        - Special handling for symmetric chords (diminished 7th)
        - Bass note detection for slash chords
        """
        if not self._selected_notes:
            self._identified_chords = ["Select notes to identify chords..."]
            self.notify("identified_chords", self._identified_chords.copy())
            return

        # Extract just the note names (ignore octaves for chord identification)
        note_names = sorted(set(note for note, _ in self._selected_notes))

        # Get the actual lowest note for bass/slash chord detection
        bass_note = self._get_bass_note_from_selection()

        try:
            all_chords = set()

            # Try the notes in their original order
            chord_names = self._chord_service.identify_chord_from_notes(note_names, bass_note)
            all_chords.update(chord_names)

            # Check if this is a symmetric chord (diminished 7th)
            # For these chords, manually add all possible root interpretations
            if self._is_diminished_seventh(note_names):
                # All notes can be the root of a dim7 chord
                for note in note_names:
                    if bass_note and bass_note != note:
                        all_chords.add(f"{note}dim7/{bass_note}")
                    all_chords.add(f"{note}dim7")

            # For better coverage, try all inversions/rotations for non-symmetric chords
            if not self._is_diminished_seventh(note_names):
                for i in range(1, len(note_names)):
                    rotated = note_names[i:] + note_names[:i]
                    chord_names = self._chord_service.identify_chord_from_notes(rotated, bass_note)
                    all_chords.update(chord_names)

            if all_chords:
                # Sort chords: prioritize simpler chords, then alphabetically
                chord_list = sorted(all_chords, key=lambda c: (len(c), c))
                logger.info(f"Identified {len(chord_list)} possible chords from notes: {note_names}")
                self._identified_chords = chord_list
            else:
                logger.info(f"No chords identified from notes: {note_names}")
                self._identified_chords = [
                    f"Notes: {', '.join(note_names)}",
                    "",
                    "No standard chord found.",
                    "Try adding or removing notes."
                ]

        except Exception as e:
            logger.error(f"Error identifying chords: {e}", exc_info=True)
            self._identified_chords = [
                f"Notes: {', '.join(note_names)}",
                "",
                f"Error: {str(e)}",
                "Make sure you've selected valid notes."
            ]

        # Notify observers directly (don't use set_and_notify since _identified_chords already has underscore)
        self.notify("identified_chords", self._identified_chords.copy())

    def _get_bass_note_from_selection(self) -> Optional[str]:
        """Get the lowest selected note (actual bass note).

        Returns:
            The note name of the lowest selected note, or None if no selection
        """
        if not self._selected_notes:
            return None

        # Find the note with the lowest MIDI number
        # MIDI formula: (octave + 1) * 12 + note_offset
        NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        lowest = None
        lowest_midi = float('inf')

        for note_name, octave in self._selected_notes:
            note_offset = NOTE_NAMES.index(note_name) if note_name in NOTE_NAMES else 0
            midi = (octave + 1) * 12 + note_offset
            if midi < lowest_midi:
                lowest_midi = midi
                lowest = note_name

        return lowest

    def _is_diminished_seventh(self, note_names: List[str]) -> bool:
        """Check if the notes form a diminished seventh chord.

        Diminished 7th chords are symmetric - any note can be the root.

        Args:
            note_names: List of note names

        Returns:
            True if the notes form a diminished 7th chord
        """
        if len(note_names) != 4:
            return False

        # Check if any interpretation is a diminished 7th chord
        for note in note_names:
            chord_name = f"{note}dim7"
            chord_notes = self._chord_service.get_chord_notes(chord_name)
            if chord_notes and set(chord_notes) == set(note_names):
                return True

        return False

    def identify_chords_from_notes(self) -> List[str]:
        """Manually trigger chord identification.

        Returns:
            List of identified chord names
        """
        self._identify_chords()
        return self._identified_chords

    def set_notation(self, notation: str) -> None:
        """Set the notation system.

        Args:
            notation: "american" or "european"
        """
        if notation in ("american", "european"):
            self.set_and_notify("notation", notation)

    def get_note_list(self) -> List[str]:
        """Get selected notes as a formatted list.

        Returns:
            List of note strings (e.g., ["C4", "E4", "G4"])
        """
        return [f"{note}{octave}" for note, octave in sorted(self._selected_notes)]

    def parse_note_string(self, note_string: str) -> List[Tuple[str, int]]:
        """Parse a space or comma-separated list of notes.

        Args:
            note_string: String like "C4, E4, G4" or "C E G" or "C, E, G"

        Returns:
            List of (note_name, octave) tuples
        """
        import re

        # Split by spaces, commas, or other punctuation
        parts = re.split(r'[,\s;/|]+', note_string.strip())

        notes = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Match note name and optional octave
            match = re.match(r'([A-Ga-g][#b]?)(\d+)?', part)
            if match:
                note_name = match.group(1)
                octave_str = match.group(2)
                octave = int(octave_str) if octave_str else 4  # Default to octave 4

                # Normalize note name (capitalize and convert flats to sharps)
                note_name = self.normalize_note_name(note_name)

                # Validate it's a real note
                NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                if note_name in NOTE_NAMES:
                    notes.append((note_name, octave))

        return notes

    def set_notes_from_string(self, note_string: str) -> None:
        """Set selected notes from a comma-separated string.

        Args:
            note_string: String like "C4, E4, G4"
        """
        try:
            notes = self.parse_note_string(note_string)
            self.set_notes(notes)
            logger.debug(f"Set notes from string: {note_string} -> {notes}")
        except Exception as e:
            logger.error(f"Error parsing note string '{note_string}': {e}", exc_info=True)

    def get_selected_note_names(self) -> List[str]:
        """Get just the note names (without octaves) from selection.

        Returns:
            Sorted list of unique note names
        """
        return sorted(set(note for note, _ in self._selected_notes))

    def is_note_selected(self, note_name: str, octave: int) -> bool:
        """Check if a specific note is selected.

        Args:
            note_name: Note name
            octave: Octave number

        Returns:
            True if selected, False otherwise
        """
        return (note_name, octave) in self._selected_notes

    def get_chord_midi_notes(self, chord_name: str, base_octave: int = 3) -> List[int]:
        """Get MIDI notes for a chord name.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            base_octave: Base octave for the chord

        Returns:
            List of MIDI note numbers, or empty list if chord not recognized
        """
        try:
            midi_notes = self._chord_service.chord_to_midi(chord_name, base_octave)
            return midi_notes if midi_notes else []
        except Exception as e:
            logger.error(f"Error converting chord to MIDI: {e}", exc_info=True)
            return []

    def normalize_note_name(self, note_name: str) -> str:
        """Normalize a note name (convert flats to sharps, capitalize).

        Args:
            note_name: Note name like "c#", "Db", "C"

        Returns:
            Normalized note name (e.g., "C#")
        """
        if not note_name or len(note_name) < 1:
            return note_name

        # Capitalize first letter
        normalized = note_name[0].upper() + note_name[1:]

        # Convert flats to sharps for consistency
        if 'b' in normalized:
            flat_to_sharp = {
                'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'
            }
            normalized = flat_to_sharp.get(normalized, normalized)

        return normalized

    def play_note(self, note_name: str, octave: int, duration: float = 1.0) -> None:
        """Play a single note.

        Args:
            note_name: Note name (e.g., "C", "D#")
            octave: Octave number
            duration: Duration in seconds
        """
        if self._audio_service is None:
            logger.warning("Cannot play note: AudioService not available")
            return

        try:
            self._audio_service.play_note(note_name, octave, duration)
            logger.debug(f"Playing note: {note_name}{octave}")
        except Exception as e:
            logger.error(f"Error playing note {note_name}{octave}: {e}", exc_info=True)

    def play_chord(self, chord_name: str, duration: float = 2.0) -> None:
        """Play a chord by name.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            duration: Duration in seconds
        """
        if self._audio_service is None:
            logger.warning("Cannot play chord: AudioService not available")
            return

        try:
            # Get MIDI notes for the chord
            midi_notes = self.get_chord_midi_notes(chord_name)
            if not midi_notes:
                logger.warning(f"Cannot play chord: No MIDI notes for '{chord_name}'")
                return

            # Play the chord
            self._audio_service.play_chord_from_midi(midi_notes, duration)
            logger.debug(f"Playing chord: {chord_name}")
        except Exception as e:
            logger.error(f"Error playing chord {chord_name}: {e}", exc_info=True)

    def play_selected_notes(self, duration: float = 2.0) -> None:
        """Play all currently selected notes as a chord.

        Args:
            duration: Duration in seconds
        """
        if self._audio_service is None:
            logger.warning("Cannot play selected notes: AudioService not available")
            return

        if not self._selected_notes:
            logger.warning("No notes selected to play")
            return

        try:
            # Convert selected notes to MIDI
            NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            midi_notes = []
            for note_name, octave in self._selected_notes:
                note_offset = NOTE_NAMES.index(note_name) if note_name in NOTE_NAMES else 0
                midi = (octave + 1) * 12 + note_offset
                midi_notes.append(midi)

            # Play as chord
            self._audio_service.play_chord_from_midi(midi_notes, duration)
            logger.debug(f"Playing selected notes: {self._selected_notes}")
        except Exception as e:
            logger.error(f"Error playing selected notes: {e}", exc_info=True)

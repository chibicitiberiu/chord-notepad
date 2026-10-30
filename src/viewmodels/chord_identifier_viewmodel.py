"""ViewModel for the chord identifier window (desktop dialog and Android screen).

The note helpers at module level (:func:`note_to_midi`, :func:`bass_note`,
:func:`parse_notes`) are plain functions both UIs share; the desktop piano
widget calls them too.
"""

import itertools
import logging
import re
from typing import Dict, Iterable, List, Tuple, Set, Optional

from music21 import chord as m21_chord
from utils.observable import Observable
from services.song_parser_service import SongParserService
from exceptions import ChordDetectionError

logger = logging.getLogger(__name__)

#: The note names the identifier works with (sharps only), in pitch order.
NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')

#: What the results list shows before any note is selected.
SELECT_NOTES_PROMPT = "Select notes to identify chords..."

_FLAT_TO_SHARP = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
_SHARP_TO_FLAT = {sharp: flat for flat, sharp in _FLAT_TO_SHARP.items()}

#: How a chord's root is usually spelled, for notes that read as a chord
#: either way (F# rather than Gb, Eb minor rather than D# minor).
_USUAL_ROOTS = frozenset(('C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'))

#: Spelling preferences: what the typed notes used.
FLATS = "flats"
SHARPS = "sharps"
_NOTE_TOKEN = re.compile(r'([A-Ga-g][#b]?)(\d+)?')


def note_to_midi(note_name: str, octave: int) -> int:
    """The MIDI number of a note (C4 = 60); an unknown name counts as C."""
    offset = NOTE_NAMES.index(note_name) if note_name in NOTE_NAMES else 0
    return (octave + 1) * 12 + offset


def bass_note(notes: Iterable[Tuple[str, int]]) -> Optional[str]:
    """The name of the lowest of ``(name, octave)`` notes, or None for none."""
    lowest = None
    lowest_midi = float('inf')
    for note_name, octave in notes:
        midi = note_to_midi(note_name, octave)
        if midi < lowest_midi:
            lowest_midi = midi
            lowest = note_name
    return lowest


def normalize_note_name(note_name: str) -> str:
    """Capitalize a note name and spell flats as sharps (``db`` -> ``C#``)."""
    if not note_name:
        return note_name
    normalized = note_name[0].upper() + note_name[1:]
    if 'b' in normalized:
        normalized = _FLAT_TO_SHARP.get(normalized, normalized)
    return normalized


def spelling_preference(note_string: str) -> Optional[str]:
    """Whether typed notes lean on flats or sharps (:data:`FLATS`,
    :data:`SHARPS`), or None when they use neither or as many of each."""
    flats = sharps = 0
    for part in re.split(r'[,\s;/|]+', note_string.strip()):
        match = _NOTE_TOKEN.match(part)
        if match and len(match.group(1)) == 2:
            if match.group(1)[1] == 'b':
                flats += 1
            else:
                sharps += 1
    if flats == sharps:
        return None
    return FLATS if flats > sharps else SHARPS


def _music21_name(name: str) -> str:
    return name.replace('b', '-') if len(name) == 2 else name


def _app_name(name: str) -> str:
    """A music21 note or chord name in the app's spelling (``B-`` -> ``Bb``)."""
    return name.replace('-', 'b')


def spell_for_identification(names: Iterable[str], bass: Optional[str] = None,
                             preference: Optional[str] = None) -> Dict[str, str]:
    """Spell sharp-named keys so the chord they make stacks in thirds.

    music21 finds a chord's root from how its notes are spelled: A# D F is
    not stacked in thirds, so it reads as some kind of D, while Bb D F reads
    as Bb major. Each black key is tried as a sharp and as a flat, and the
    spellings music21 calls a plain chord (not an "enharmonic equivalent")
    win. Among those, the typed ``preference`` comes first, then a usual
    root spelling (Eb minor over D# minor), a root in the bass, fewer
    accidentals, and sharps.

    Args:
        names: Note names spelled with sharps (:data:`NOTE_NAMES`).
        bass: The lowest note's name, also with a sharp.
        preference: :data:`FLATS`, :data:`SHARPS` or None.

    Returns:
        Each name mapped to its spelling. When no spelling reads as a plain
        chord, the preferred accidental is used throughout (sharps by default).
    """
    names = sorted(set(names), key=NOTE_NAMES.index)
    black = [n for n in names if n in _SHARP_TO_FLAT]
    best_key = None
    best: Optional[Dict[str, str]] = None
    if 2 <= len(names) <= 7:
        for flats in itertools.product((False, True), repeat=len(black)):
            flat = {n for n, f in zip(black, flats) if f}
            spelled = {n: _SHARP_TO_FLAT[n] if n in flat else n for n in names}
            try:
                c = m21_chord.Chord([_music21_name(spelled[n]) for n in names])
                if c.commonName.startswith('enharmonic'):
                    continue
                root = _app_name(c.root().name)
            except Exception:  # music21 can't read it: not a chord
                continue
            sharps = len(black) - len(flat)
            key = (
                sharps if preference == FLATS else len(flat) if preference == SHARPS else 0,
                root not in _USUAL_ROOTS,
                bass is not None and root != spelled.get(bass),
                len(flat),
            )
            if best_key is None or key < best_key:
                best_key, best = key, spelled
    if best is not None:
        return best
    if preference == FLATS:
        return {n: _SHARP_TO_FLAT.get(n, n) for n in names}
    return {n: n for n in names}


def parse_notes(note_string: str) -> Tuple[List[Tuple[str, int]], List[str]]:
    """Parse typed notes ("C4, E4, G4", "C E G"; octave 4 when left out).

    Forgiving like the desktop field: a token that starts with a note name
    counts as that note (``Cm`` reads as ``C``), anything else is skipped.

    Returns:
        ``(notes, not_understood)``: the ``(name, octave)`` notes in typed
        order, and the tokens that weren't exactly a note (skipped or only
        partly read).
    """
    notes: List[Tuple[str, int]] = []
    not_understood: List[str] = []
    for part in re.split(r'[,\s;/|]+', note_string.strip()):
        part = part.strip()
        if not part:
            continue
        match = _NOTE_TOKEN.match(part)
        name = normalize_note_name(match.group(1)) if match else ''
        if match and name in NOTE_NAMES:
            octave = int(match.group(2)) if match.group(2) else 4
            notes.append((name, octave))
            if match.end() != len(part):
                not_understood.append(part)
        else:
            not_understood.append(part)
    return notes, not_understood


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
        # The same result split in two: the chord names alone, and the
        # explanation shown instead of (or for lack of) chords.
        self._candidates: List[str] = []
        self._info_lines: List[str] = [SELECT_NOTES_PROMPT]
        self._notation: str = "american"
        # How the last typed notes were spelled (FLATS/SHARPS), so the answer
        # is spelled the same way; None after a key tap.
        self._spelling: Optional[str] = None

    @property
    def selected_notes(self) -> Set[Tuple[str, int]]:
        """Get the currently selected notes."""
        return self._selected_notes

    @property
    def identified_chords(self) -> List[str]:
        """Get the identified chord names."""
        return self._identified_chords

    @property
    def candidates(self) -> List[str]:
        """The identified chord names only (no explanation lines)."""
        return list(self._candidates)

    @property
    def info_lines(self) -> List[str]:
        """What to say instead of chords (a prompt, "no chord found", an error);
        empty when there are candidates."""
        return list(self._info_lines)

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
        self._spelling = None

        if note_tuple in self._selected_notes:
            self._selected_notes.remove(note_tuple)
            logger.debug(f"Deselected note: {note_name}{octave}")
        else:
            self._selected_notes.add(note_tuple)
            logger.debug(f"Selected note: {note_name}{octave}")

        self.notify("selected_notes", self._selected_notes.copy())

        # Re-identify chords with new selection
        self._identify_chords()

    def set_notes(self, notes: List[Tuple[str, int]], spelling: Optional[str] = None) -> None:
        """Set the selected notes.

        Args:
            notes: List of (note_name, octave) tuples
            spelling: How the notes were typed (:func:`spelling_preference`),
                so the chords are named with the same accidentals; None
                for piano keys.
        """
        self._spelling = spelling
        self._selected_notes = set(notes)
        self.notify("selected_notes", self._selected_notes.copy())
        self._identify_chords()

    def clear_selection(self) -> None:
        """Clear all selected notes."""
        logger.debug("Clearing note selection")
        self._selected_notes.clear()
        self._spelling = None
        self._identified_chords.clear()
        self._candidates = []
        self._info_lines = [SELECT_NOTES_PROMPT]
        self.notify("selected_notes", self._selected_notes.copy())
        self.notify("identified_chords", self._identified_chords.copy())

    def _identify_chords(self) -> None:
        """Identify possible chords from selected notes with advanced logic.

        This includes:
        - Trying all inversions/rotations
        - Special handling for symmetric chords (diminished 7th)
        - Bass note detection for slash chords
        """
        self._candidates = []
        if not self._selected_notes:
            self._identified_chords = [SELECT_NOTES_PROMPT]
            self._info_lines = list(self._identified_chords)
            self.notify("identified_chords", self._identified_chords.copy())
            return

        # The selection is piano keys, spelled with sharps. Respell them so
        # the chord they make stacks in thirds (A# D F is Bb D F): music21
        # finds the root from the spelling. Octaves don't matter here.
        keys = sorted(set(note for note, _ in self._selected_notes), key=NOTE_NAMES.index)
        lowest = self._get_bass_note_from_selection()
        spelled = spell_for_identification(keys, lowest, self._spelling)
        note_names = [spelled[n] for n in keys]
        bass_note = spelled.get(lowest) if lowest else None

        try:
            all_chords = set()

            # music21 spells flats with '-': hand it its own spelling, so a
            # root and a bass compare equal (B- vs B-, not B- vs Bb).
            m21_notes = [_music21_name(n) for n in note_names]
            m21_bass = _music21_name(bass_note) if bass_note else None

            # Try the notes in their original order
            chord_names = self._chord_service.identify_chord_from_notes(m21_notes, m21_bass)
            all_chords.update(chord_names)

            # Check if this is a symmetric chord (diminished 7th)
            # For these chords, manually add all possible root interpretations
            if self._is_diminished_seventh(keys):
                # All notes can be the root of a dim7 chord
                for note in note_names:
                    if bass_note and bass_note != note:
                        all_chords.add(f"{note}dim7/{bass_note}")
                    all_chords.add(f"{note}dim7")

            # For better coverage, try all inversions/rotations for non-symmetric chords
            if not self._is_diminished_seventh(keys):
                for i in range(1, len(m21_notes)):
                    rotated = m21_notes[i:] + m21_notes[:i]
                    chord_names = self._chord_service.identify_chord_from_notes(rotated, m21_bass)
                    all_chords.update(chord_names)

            all_chords = {_app_name(name) for name in all_chords}
            if all_chords:
                # Sort chords: prioritize simpler chords, then alphabetically
                chord_list = sorted(all_chords, key=lambda c: (len(c), c))
                logger.info(f"Identified {len(chord_list)} possible chords from notes: {note_names}")
                self._identified_chords = chord_list
                self._candidates = list(chord_list)
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

        self._info_lines = [] if self._candidates else list(self._identified_chords)
        # Notify observers directly (don't use set_and_notify since _identified_chords already has underscore)
        self.notify("identified_chords", self._identified_chords.copy())

    def _get_bass_note_from_selection(self) -> Optional[str]:
        """Get the lowest selected note (actual bass note).

        Returns:
            The note name of the lowest selected note, or None if no selection
        """
        return bass_note(self._selected_notes)

    def _is_diminished_seventh(self, note_names: List[str]) -> bool:
        """Check if the notes form a diminished seventh chord.

        Diminished 7th chords are symmetric - any note can be the root.

        Args:
            note_names: List of note names

        Returns:
            True if the notes form a diminished 7th chord
        """
        if len(set(note_names)) != 4:
            return False
        steps = sorted(NOTE_NAMES.index(_FLAT_TO_SHARP.get(n, n)) for n in set(note_names))
        return all(b - a == 3 for a, b in zip(steps, steps[1:]))

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
        return parse_notes(note_string)[0]

    def set_notes_from_string(self, note_string: str) -> None:
        """Set selected notes from a comma-separated string.

        Args:
            note_string: String like "C4, E4, G4"
        """
        try:
            notes = self.parse_note_string(note_string)
            self.set_notes(notes, spelling_preference(note_string))
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
        return normalize_note_name(note_name)

    def play_note(self, note_name: str, octave: int, duration: float = 1.0) -> None:
        """Play a single note.

        Args:
            note_name: Note name (e.g., "C", "D#")
            octave: Octave number
            duration: Duration in seconds

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play note: AudioService not available")
            return

        self._audio_service.play_note(note_name, octave, duration)
        logger.debug(f"Playing note: {note_name}{octave}")

    def play_chord(self, chord_name: str, duration: float = 2.0) -> None:
        """Play a chord by name.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            duration: Duration in seconds

        Raises:
            ChordDetectionError: If the chord's notes can't be worked out.
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play chord: AudioService not available")
            return

        # Get MIDI notes for the chord
        midi_notes = self.get_chord_midi_notes(chord_name)
        if not midi_notes:
            logger.warning(f"Cannot play chord: No MIDI notes for '{chord_name}'")
            raise ChordDetectionError(f"Could not work out the notes of {chord_name}.")

        # Play the chord
        self._audio_service.play_chord_from_midi(midi_notes, duration)
        logger.debug(f"Playing chord: {chord_name}")

    def play_selected_notes(self, duration: float = 2.0) -> None:
        """Play all currently selected notes as a chord.

        Args:
            duration: Duration in seconds

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play selected notes: AudioService not available")
            return

        if not self._selected_notes:
            logger.warning("No notes selected to play")
            return

        midi_notes = [note_to_midi(name, octave) for name, octave in self._selected_notes]

        # Play as chord
        self._audio_service.play_chord_from_midi(midi_notes, duration)
        logger.debug(f"Playing selected notes: {self._selected_notes}")

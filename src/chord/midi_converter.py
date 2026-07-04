"""
Convert chord names to MIDI note numbers
"""

from typing import List, Optional


# Base letter to semitone offset within the octave.
_BASE_LETTER_SEMITONE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def parse_note_to_semitone(note_name: str) -> Optional[int]:
    """Convert a note name to a semitone class (0-11) modulo octave.

    Accepts any number of sharps ('#') or flats ('b', also '-' for music21 style)
    after the base letter. Handles enharmonic spellings like 'E#', 'B#', 'Cb',
    'Fb', and double accidentals ('C##', 'Dbb', etc.).

    Returns None if the input is empty or contains an unrecognised character.
    """
    if not note_name:
        return None
    base = note_name[0].upper()
    if base not in _BASE_LETTER_SEMITONE:
        return None
    offset = 0
    for ch in note_name[1:]:
        if ch == '#':
            offset += 1
        elif ch == 'b' or ch == '-':
            offset -= 1
        else:
            return None
    return (_BASE_LETTER_SEMITONE[base] + offset) % 12


def intervals_from_note_names(note_names: List[str]) -> List[int]:
    """Reconstruct register-preserving intervals (semitones above the root).

    The first name is treated as the root (interval 0). Each subsequent note is
    placed in the lowest octave that keeps the stack strictly ascending, so
    extensions land where tertian stacking puts them (a 9th at +14, an 11th at
    +17, a 13th at +21) rather than folding down into a 2nd/4th/6th.

    This is the fallback for when a backend can't supply real intervals; the
    normal paths use pychord/music21/the table's own register instead.
    """
    if not note_names:
        return []
    root_class = parse_note_to_semitone(note_names[0])
    if root_class is None:
        return []

    # Keep the reconstructed voicing within two octaves of the root. Real
    # chords top out at the 13th (+21), so this never touches them; it only
    # stops a non-tertian pile-up (e.g. a chromatic cluster) from stacking
    # every note into its own octave and exploding the span.
    MAX_INTERVAL = 24

    intervals: List[int] = []
    for name in note_names:
        note_class = parse_note_to_semitone(name)
        if note_class is None:
            continue
        interval = (note_class - root_class) % 12
        while intervals and interval <= intervals[-1] and interval + 12 <= MAX_INTERVAL:
            interval += 12
        intervals.append(interval)
    return intervals


class ChordToMidiConverter:
    """
    Converts chord names to MIDI note numbers

    Handles both standard chords and exotic notations
    """

    def __init__(self) -> None:
        """Initialize converter"""
        pass

    def chord_to_midi(self, chord_notes: List[str], base_octave: int = 4) -> Optional[List[int]]:
        """
        Convert list of note names to MIDI note numbers

        Args:
            chord_notes: List of note names (e.g., ['C', 'E', 'G'])
            base_octave: Starting octave (default 4, middle C = C4 = MIDI 60)

        Returns:
            list: MIDI note numbers or None if invalid
        """
        if not chord_notes:
            return None

        midi_notes = []
        current_octave = base_octave
        prev_note_class = None

        for note_name in chord_notes:
            # Get the pitch class (0-11)
            note_class = parse_note_to_semitone(note_name)

            if note_class is None:
                return None

            # If this note is lower than the previous note in pitch class,
            # move to the next octave
            if prev_note_class is not None and note_class < prev_note_class:
                current_octave += 1

            # Calculate MIDI note number
            midi_note = note_class + (current_octave + 1) * 12

            # Validate MIDI range (0-127)
            if 0 <= midi_note <= 127:
                midi_notes.append(midi_note)

            prev_note_class = note_class

        return midi_notes

    def note_to_midi(self, note_name: str, octave: int) -> Optional[int]:
        """
        Convert a single note name and octave to MIDI number

        Args:
            note_name: Note name (e.g., 'C', 'C#', 'Eb')
            octave: Octave number (C4 = middle C)

        Returns:
            int: MIDI note number or None if invalid
        """
        note_class = self.NOTE_MAP.get(note_name)
        if note_class is None:
            return None

        return note_class + (octave + 1) * 12

"""
Convert chord names to MIDI note numbers
"""


class ChordToMidiConverter:
    """
    Converts chord names to MIDI note numbers

    Handles both standard chords and exotic notations
    """

    # Note name to semitone mapping
    NOTE_MAP = {
        'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4, 'E-': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7,
        'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'B-': 11
    }

    def __init__(self):
        """Initialize converter"""
        pass

    def chord_to_midi(self, chord_notes, base_octave=4):
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
            note_class = self.NOTE_MAP.get(note_name)

            if note_class is None:
                return None

            # If this note is lower than the previous note in pitch class,
            # move to the next octave
            if prev_note_class is not None and note_class < prev_note_class:
                current_octave += 1

            # Calculate MIDI note number
            midi_note = note_class + (current_octave + 1) * 12
            midi_notes.append(midi_note)

            prev_note_class = note_class

        return midi_notes

    def note_to_midi(self, note_name, octave):
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

"""
Chord note picker - converts chords to MIDI notes
"""

from typing import List, Union
from audio.player import note_to_midi


class ChordNotePicker:
    """Picks MIDI notes for chords"""

    def __init__(self, chord_octave: int = 3, bass_octave: int = 2, add_bass: bool = True) -> None:
        """
        Initialize chord note picker

        Args:
            chord_octave: Default octave for chord notes (default 3)
            bass_octave: Default octave for bass note (default 2)
            add_bass: Whether to add a bass note (root doubled) (default True)
        """
        self.chord_octave = chord_octave
        self.bass_octave = bass_octave
        self.add_bass = add_bass

    def chord_to_midi(self, chord_obj: Union[List[str], object], bass_note: str = None) -> List[int]:
        """
        Convert a PyChord Chord object or note list to MIDI note numbers

        Args:
            chord_obj: PyChord Chord object or list of note names
            bass_note: Optional bass note to use instead of the root (for slash chords)

        Returns:
            List of MIDI note numbers
        """
        # Get notes from chord - handle both PyChord object and list
        if isinstance(chord_obj, list):
            notes = chord_obj
        else:
            # Assume it's a PyChord object
            notes = chord_obj.components()

        # Convert to MIDI notes
        midi_notes: List[int] = []
        for note in notes:
            midi_num = note_to_midi(note, default_octave=self.chord_octave)
            if midi_num is not None:
                midi_notes.append(midi_num)

        # Add bass note (use provided bass_note or root doubled in lower octave)
        if self.add_bass and notes:
            bass_note_to_use = bass_note if bass_note else notes[0]
            bass_midi = note_to_midi(bass_note_to_use, default_octave=self.bass_octave)
            if bass_midi is not None:
                midi_notes.insert(0, bass_midi)

        return midi_notes

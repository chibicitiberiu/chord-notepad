"""
Chord note picker - converts chords to MIDI notes
"""

from audio.player import note_to_midi


class ChordNotePicker:
    """Picks MIDI notes for chords"""

    def __init__(self, chord_octave=3, bass_octave=2, add_bass=True):
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

    def chord_to_midi(self, chord_obj):
        """
        Convert a PyChord Chord object or note list to MIDI note numbers

        Args:
            chord_obj: PyChord Chord object or list of note names

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
        midi_notes = []
        for note in notes:
            midi_num = note_to_midi(note, default_octave=self.chord_octave)
            if midi_num is not None:
                midi_notes.append(midi_num)

        # Add bass note (root doubled in lower octave)
        if self.add_bass and notes:
            bass_note = note_to_midi(notes[0], default_octave=self.bass_octave)
            if bass_note is not None:
                midi_notes.insert(0, bass_note)

        return midi_notes

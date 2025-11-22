"""
Unified chord handling that wraps pychord, music21, and adds custom support
"""

import re
from pychord import Chord as PyChord
from music21 import chord as m21_chord, pitch
from chord.midi_converter import ChordToMidiConverter


class ChordHelper:
    """
    Unified chord helper that combines pychord, music21, and custom chord handling

    Provides:
    - Chord validation (is this a real chord?)
    - Chord parsing (what notes are in this chord?)
    - Chord identification (what chord is this set of notes?)
    - MIDI conversion (convert chord name to MIDI notes)
    """

    # Comprehensive interval patterns for all chord types
    QUALITY_INTERVALS = {
        # Triads
        '': [0, 4, 7],                  # Major
        'm': [0, 3, 7],                 # Minor
        'dim': [0, 3, 6],               # Diminished
        'aug': [0, 4, 8],               # Augmented
        'sus2': [0, 2, 7],              # Suspended 2nd
        'sus4': [0, 5, 7],              # Suspended 4th
        '5': [0, 7],                    # Power chord

        # Seventh chords
        '7': [0, 4, 7, 10],             # Dominant 7th
        'maj7': [0, 4, 7, 11],          # Major 7th
        'm7': [0, 3, 7, 10],            # Minor 7th
        'dim7': [0, 3, 6, 9],           # Diminished 7th
        'm7b5': [0, 3, 6, 10],          # Half-diminished
        'mM7': [0, 3, 7, 11],           # Minor-major 7th
        'augmaj7': [0, 4, 8, 11],       # Augmented major 7th
        'aug7': [0, 4, 8, 10],          # Augmented 7th
        '7sus4': [0, 5, 7, 10],         # Dominant 7 sus4

        # Sixth chords
        '6': [0, 4, 7, 9],              # Major 6th
        'm6': [0, 3, 7, 9],             # Minor 6th

        # Ninth chords
        '9': [0, 4, 7, 10, 14],         # Dominant 9th
        'maj9': [0, 4, 7, 11, 14],      # Major 9th
        'm9': [0, 3, 7, 10, 14],        # Minor 9th
        '7b9': [0, 4, 7, 10, 13],       # Dominant 7th flat 9
        '7#9': [0, 4, 7, 10, 15],       # Dominant 7th sharp 9
        'mM9': [0, 3, 7, 11, 14],       # Minor-major 9th

        # Eleventh and thirteenth chords
        '11': [0, 4, 7, 10, 14, 17],    # Dominant 11th
        'm11': [0, 3, 7, 10, 14, 17],   # Minor 11th
        'maj11': [0, 4, 7, 11, 14, 17], # Major 11th
        '13': [0, 4, 7, 10, 14, 21],    # Dominant 13th

        # Add chords
        'add9': [0, 4, 7, 14],          # Add 9
        'madd9': [0, 3, 7, 14],         # Minor add 9
        'add11': [0, 4, 7, 17],         # Add 11

        # Exotic/altered chords
        'aug7b9': [0, 4, 8, 10, 13],    # Augmented 7th flat 9
        'maj7#5(9)': [0, 4, 8, 11, 14], # Major 7 #5 add 9
        'm7b5(b9)': [0, 3, 6, 10, 13],  # Half-diminished flat 9
        'dim7#9': [0, 3, 6, 9, 15],     # Diminished 7th sharp 9
        'dim(maj9)': [0, 3, 6, 11, 14], # Diminished with maj7 and 9
        'dimm9': [0, 3, 6, 10, 14],     # Diminished minor 9th
    }

    def __init__(self):
        """Initialize chord helper"""
        self.midi_converter = ChordToMidiConverter()

    def is_valid_chord(self, chord_name):
        """
        Check if a chord name is valid

        Args:
            chord_name: Chord string (e.g., "Cmaj7", "Am/G", "Cdim(maj9)")

        Returns:
            bool: True if chord is valid/recognized
        """
        # Try pychord first
        try:
            PyChord(chord_name)
            return True
        except:
            pass

        # Try our custom patterns
        root = self.extract_root(chord_name)
        if not root:
            return False

        quality = chord_name[len(root):]

        # Handle slash chords
        if '/' in quality:
            quality = quality.split('/')[0]

        # Check if we have this quality
        return quality in self.QUALITY_INTERVALS

    def get_notes(self, chord_name):
        """
        Get the notes in a chord

        Args:
            chord_name: Chord string (e.g., "Cmaj7", "Am/G")

        Returns:
            list: Note names (e.g., ['C', 'E', 'G', 'B']) or None if invalid
        """
        # Try pychord first
        try:
            chord_obj = PyChord(chord_name)
            return chord_obj.components()
        except:
            pass

        # Try our custom implementation
        return self._build_chord_notes(chord_name)

    def chord_to_midi(self, chord_name, base_octave=4):
        """
        Convert chord name to MIDI note numbers

        Args:
            chord_name: Chord string (e.g., "Cmaj7")
            base_octave: Starting octave (default 4)

        Returns:
            list: MIDI note numbers or None if invalid
        """
        notes = self.get_notes(chord_name)
        if not notes:
            return None

        return self.midi_converter.chord_to_midi(notes, base_octave)

    def identify_chord(self, notes, actual_bass_note=None):
        """
        Identify what chord(s) a set of notes represents

        Args:
            notes: List of note names (e.g., ['C', 'E', 'G'])
            actual_bass_note: Optional bass note for slash chord detection

        Returns:
            set: Set of possible chord names
        """
        if not notes:
            return set()

        chord_names = set()

        try:
            # Use music21 for identification
            c = m21_chord.Chord(notes)
            common_name = c.commonName

            # Get root and convert to shorthand
            root = c.root().name
            shorthand = self._music21_type_to_shorthand(common_name)

            if shorthand is not None:
                # Add basic chord
                chord_names.add(f"{root}{shorthand}")

                # Add slash chord if bass differs from root
                bass_note = actual_bass_note if actual_bass_note else c.bass().name
                if bass_note != root:
                    chord_names.add(f"{root}{shorthand}/{bass_note}")
        except:
            pass

        return chord_names

    def extract_root(self, chord_name):
        """Extract root note from chord name"""
        match = re.match(r'^([A-G][#b]?)', chord_name)
        if match:
            return match.group(1)
        return None

    def _build_chord_notes(self, chord_name):
        """Build chord notes from our interval patterns"""
        root = self.extract_root(chord_name)
        if not root:
            return None

        quality = chord_name[len(root):]

        # Handle slash chords
        if '/' in quality:
            quality = quality.split('/')[0]

        # Get intervals
        intervals = self.QUALITY_INTERVALS.get(quality)
        if not intervals:
            return None

        # Build notes from intervals
        try:
            root_pitch = pitch.Pitch(root)
            notes = [root]

            for interval in intervals[1:]:
                new_pitch = root_pitch.transpose(interval)
                notes.append(new_pitch.name)

            return notes
        except:
            return None

    def _music21_type_to_shorthand(self, chord_type):
        """Convert music21 chord type to shorthand notation"""
        type_map = {
            # Triads
            'major triad': '',
            'minor triad': 'm',
            'diminished triad': 'dim',
            'augmented triad': 'aug',
            'suspended-second triad': 'sus2',
            'suspended-fourth triad': 'sus4',
            'quartal trichord': 'sus',
            'whole-tone trichord': 'sus2',

            # Seventh chords
            'dominant seventh chord': '7',
            'incomplete dominant-seventh chord': '7',
            'major seventh chord': 'maj7',
            'incomplete major-seventh chord': 'maj7',
            'minor seventh chord': 'm7',
            'incomplete minor-seventh chord': 'm7',
            'diminished seventh chord': 'dim7',
            'half-diminished seventh chord': 'm7b5',
            'augmented seventh chord': 'aug7',
            'major-minor seventh chord': '7',
            'minor-major seventh chord': 'mM7',
            'minor-augmented tetrachord': 'mM7',
            'augmented major tetrachord': 'augmaj7',

            # Sixth chords
            'major sixth': '6',
            'minor sixth': 'm6',
            'major-sixth chord': '6',
            'minor-sixth chord': 'm6',

            # Ninth chords
            'dominant ninth': '9',
            'dominant-ninth': '9',
            'major ninth': 'maj9',
            'major-ninth chord': 'maj9',
            'minor ninth': 'm9',
            'minor-ninth chord': 'm9',

            # Eleventh and thirteenth
            'dominant-eleventh': '11',
            'minor-eleventh chord': 'm11',
            'major-eleventh chord': 'maj11',
            'dominant-thirteenth': '13',
            'dominant-13th': '13',
            'augmented-eleventh': '13',

            # Add chords
            'major-second major tetrachord': 'add9',
            'perfect-fourth major tetrachord': 'add11',
            'major-sixth major tetrachord': 'add13',

            # Altered chords
            'flat-ninth pentachord': '7b9',
            'neapolitan pentachord': '7#9',
            'sharp-ninth pentachord': '7#9',

            # Power chord
            'perfect-fifth open-fifth chord': '5',

            # Augmented sixth chords
            'Italian augmented sixth chord': 'It+6',
            'French augmented sixth chord': 'Fr+6',
            'German augmented sixth chord': 'Ger+6',
            'german augmented sixth chord in third inversion': 'Ger+6',

            # Enharmonic equivalents
            'enharmonic equivalent to diminished triad': 'dim',
            'enharmonic equivalent to major triad': '',
            'enharmonic equivalent to minor triad': 'm',
            'enharmonic equivalent to half-diminished seventh chord': 'm7b5',
            'enharmonic equivalent to major seventh chord': 'maj7',
            'enharmonic equivalent to minor seventh chord': 'm7',
            'enharmonic to dominant seventh chord': '7',
            'enharmonic equivalent to dominant-ninth': '9',
            'enharmonic equivalent to major-ninth chord': 'maj9',
            'enharmonic equivalent to minor-ninth chord': 'm9',

            # Incomplete chords
            'incomplete half-diminished seventh chord': 'm7b5',

            # Extended/altered chords
            'augmented-diminished ninth chord': 'aug7b9',
            'diminished-augmented ninth chord': 'dim7#9',
            'diminished-major ninth chord': 'dim(maj9)',
            'diminished minor-ninth chord': 'dimm9',
            'major-augmented ninth chord': 'maj7#5(9)',
            'minor-major ninth chord': 'mM9',
            'minor-diminished ninth chord': 'm7b5(b9)',

            # Add chords with minor
            'major-second minor tetrachord': 'madd9',
        }

        return type_map.get(chord_type.lower())

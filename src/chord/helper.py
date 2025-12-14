"""
Unified chord handling that wraps pychord, music21, and adds custom support
"""

import re
from typing import List, Optional, Set
from pychord import Chord as PyChord
from music21 import chord as m21_chord, pitch
from chord.midi_converter import ChordToMidiConverter
from models.chord_notes import ChordNotes


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
        # Note: Following jazz theory and pychord conventions
        '11': [0, 7, 10, 14, 17],       # Dominant 11th (omits 3rd - clashes with 11th)
        'm11': [0, 3, 7, 10, 14, 17],   # Minor 11th (b3 doesn't clash)
        'maj11': [0, 4, 7, 11, 14, 17], # Major 11th
        '13': [0, 4, 7, 10, 14, 21],    # Dominant 13th (omits 11th - practical voicing)

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

    def __init__(self) -> None:
        """Initialize chord helper"""
        self.midi_converter = ChordToMidiConverter()

    def is_valid_chord(self, chord_name: str) -> bool:
        """
        Check if a chord name is valid

        Args:
            chord_name: Chord string (e.g., "Cmaj7", "Am/G", "Cdim(maj9)")

        Returns:
            bool: True if chord is valid/recognized
        """
        # Use compute_chord_notes to validate - it applies all normalizations
        # and tries multiple backends (pychord, music21, custom)
        result = self.compute_chord_notes(chord_name)
        return result is not None

    def get_notes(self, chord_name: str) -> Optional[List[str]]:
        """
        Get the notes in a chord

        Args:
            chord_name: Chord string (e.g., "Cmaj7", "Am/G")

        Returns:
            list: Note names (e.g., ['C', 'E', 'G', 'B']) or None if invalid
        """
        # Try pychord first (fast and lightweight)
        try:
            chord_obj = PyChord(chord_name)
            return chord_obj.components()
        except:
            pass

        # Try music21 as fallback (supports omit notation and more)
        try:
            import music21
            chord_obj = music21.harmony.ChordSymbol(chord_name)
            # Convert pitch objects to note names
            return [p.name.replace('-', 'b') for p in chord_obj.pitches]
        except:
            pass

        # Try our custom implementation
        return self._build_chord_notes(chord_name)

    def chord_to_midi(self, chord_name: str, base_octave: int = 4) -> Optional[List[int]]:
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

    def identify_chord(self, notes: List[str], actual_bass_note: Optional[str] = None) -> Set[str]:
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

    def extract_root(self, chord_name: str) -> Optional[str]:
        """Extract root note from chord name"""
        match = re.match(r'^([A-G][#b]?)', chord_name)
        if match:
            return match.group(1)
        return None

    def _build_chord_notes(self, chord_name: str) -> Optional[List[str]]:
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

    def _music21_type_to_shorthand(self, chord_type: str) -> Optional[str]:
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

    def compute_chord_notes(self, chord_name: str, key: Optional[str] = None, is_relative: bool = False) -> Optional[ChordNotes]:
        """
        Compute chord notes with support for roman numerals and slash chords.

        Args:
            chord_name: Chord string (e.g., "Cmaj7", "Am/G", "I", "V7", "c", "d")
            key: Key signature (required if is_relative=True)
            is_relative: True if chord_name is a roman numeral

        Returns:
            ChordNotes object with notes, bass_note, and root, or None if invalid
        """
        # Handle roman numeral chords
        if is_relative:
            if not key:
                return None
            # Convert roman numeral to absolute chord name
            chord_name = self._resolve_roman_numeral(chord_name, key)
            if not chord_name:
                return None
        else:
            # Convert European notation to American first (Do → C, Re → D, etc.)
            from chord.converter import NotationConverter
            chord_name = NotationConverter.european_to_american(chord_name)
            # Normalize unicode and alternative symbols
            chord_name = self._normalize_unicode_symbols(chord_name)
            # Normalize enharmonic equivalents (Cb → B, E# → F, etc.)
            chord_name = self._normalize_enharmonics(chord_name)
            # Normalize alternative chord quality notations (Δ, -, M, min, etc.)
            chord_name = self._normalize_alternative_qualities(chord_name)
            # Normalize lowercase notation (c = Cm, d = Dm) for absolute chords
            chord_name = self._normalize_lowercase_chord(chord_name)
            # Convert symbols to text (° → dim, ø → m7b5, + → aug)
            chord_name = self._convert_symbols_to_text(chord_name)
            # Normalize parentheses notation (Cmaj7(9) → Cmaj9)
            chord_name = self._normalize_parentheses(chord_name)
            # Handle omit notation (C(no3) → simplified form)
            chord_name = self._normalize_omit_notation(chord_name)

        # Parse slash chord
        slash_bass = None
        if '/' in chord_name:
            parts = chord_name.split('/')
            chord_name = parts[0]
            slash_bass = parts[1]

        # Get chord notes
        notes = self.get_notes(chord_name)
        if not notes:
            return None

        # Extract root
        root = self.extract_root(chord_name)
        if not root:
            return None

        # Determine bass note
        bass_note = slash_bass if slash_bass else root

        return ChordNotes(
            notes=notes,
            bass_note=bass_note,
            root=root
        )

    def _resolve_roman_numeral(self, roman: str, key: str) -> Optional[str]:
        """
        Convert roman numeral chord to absolute chord name.

        Args:
            roman: Roman numeral chord (e.g., "I", "iv", "V7", "vi/IV", "♭III", "viio", "#ivo")
            key: Key signature (e.g., "C", "Am", "G")

        Returns:
            Absolute chord name (e.g., "C", "Fm", "G7") or None if invalid
        """
        # Handle slash chords in roman numerals
        slash_bass_roman = None
        if '/' in roman:
            parts = roman.split('/')
            roman = parts[0]
            slash_bass_roman = parts[1]

        # Normalize unicode symbols first
        roman = self._normalize_unicode_symbols(roman)

        # Extract roman numeral with optional accidental and diminished symbol
        # Pattern: [optional flat/sharp][roman numeral][optional diminished o][rest of quality]
        match = re.match(r'^([#b])?([IViv]+)(o|°)?(.*)', roman)
        if not match:
            return None

        accidental = match.group(1)  # '#' or 'b' or None
        roman_base = match.group(2)   # 'I', 'ii', 'V', etc.
        diminished_symbol = match.group(3)  # 'o' or '°' or None
        quality = match.group(4)      # '7', 'maj7', etc.

        # Determine if major or minor based on case
        is_major = roman_base.isupper()

        # Map roman numerals to scale degrees (0-indexed)
        roman_to_degree = {
            'I': 0, 'II': 1, 'III': 2, 'IV': 3, 'V': 4, 'VI': 5, 'VII': 6,
            'i': 0, 'ii': 1, 'iii': 2, 'iv': 3, 'v': 4, 'vi': 5, 'vii': 6,
        }

        degree = roman_to_degree.get(roman_base.upper())
        if degree is None:
            return None

        # Get key root
        key_root = self.extract_root(key)
        if not key_root:
            return None

        # Calculate absolute note for this degree
        # Major scale intervals: W-W-H-W-W-W-H (2-2-1-2-2-2-1 semitones)
        major_scale_intervals = [0, 2, 4, 5, 7, 9, 11]
        interval = major_scale_intervals[degree]

        # Apply accidental if present
        if accidental == 'b':
            interval -= 1  # Flat: lower by 1 semitone
        elif accidental == '#':
            interval += 1  # Sharp: raise by 1 semitone

        try:
            key_pitch = pitch.Pitch(key_root)
            root_pitch = key_pitch.transpose(interval)
            # music21 uses "-" for flats, convert to "b" for consistency
            root = root_pitch.name.replace('-', 'b')
        except:
            return None

        # Build quality
        # If lowercase roman numeral, it's minor (unless quality overrides)
        if not is_major and not quality and not diminished_symbol:
            quality = 'm'

        # Handle diminished symbol
        if diminished_symbol:
            # If there's a quality already (like '7'), prepend 'dim'
            # Otherwise, just use 'dim'
            quality = 'dim' + quality

        # Build final chord name
        chord_name = root + quality

        # Handle slash bass if present
        if slash_bass_roman:
            bass_chord = self._resolve_roman_numeral(slash_bass_roman, key)
            if bass_chord:
                bass_root = self.extract_root(bass_chord)
                if bass_root:
                    chord_name = chord_name + '/' + bass_root

        return chord_name

    def _normalize_lowercase_chord(self, chord_name: str) -> str:
        """Normalize lowercase chord notation to standard format.

        In American notation, lowercase root notes indicate minor chords:
        - 'c' -> 'Cm' (C minor)
        - 'd7' -> 'Dm7' (D minor 7)
        - 'c#m7' -> 'C#m7' (already has 'm', keep as is)

        Args:
            chord_name: Original chord string

        Returns:
            Normalized chord string with uppercase root
        """
        if not chord_name or not chord_name[0].islower():
            return chord_name

        # Check for sharp/flat after root
        if len(chord_name) > 1 and chord_name[1] in ['#', 'b']:
            root = chord_name[:2].upper()
            suffix = chord_name[2:]
        else:
            root = chord_name[0].upper()
            suffix = chord_name[1:]

        # Add 'm' for minor if no quality is specified
        # Check if suffix already starts with quality indicator
        if not suffix or (suffix and suffix[0] not in ['m', 'M'] and not suffix.startswith('maj') and not suffix.startswith('min')):
            return root + 'm' + suffix
        else:
            return root + suffix

    def _convert_symbols_to_text(self, chord_name: str) -> str:
        """Convert chord symbols to text equivalents.

        Converts musical symbols to their text representations:
        - ° (degree sign) → dim (diminished)
        - ø (slashed o) → m7b5 (half-diminished)
        - + (plus) → aug (augmented)

        Args:
            chord_name: Chord with symbols (e.g., "A°7", "Bø7", "C+")

        Returns:
            Chord with text (e.g., "Adim7", "Bm7b5", "Caug")
        """
        # Handle ° (diminished)
        if '°' in chord_name:
            chord_name = chord_name.replace('°', 'dim')

        # Handle ø (half-diminished)
        if 'ø' in chord_name:
            # ø means half-diminished, which is m7b5
            # Bø7 → Bm7b5, Bø → Bm7b5
            chord_name = chord_name.replace('ø7', 'm7b5')
            chord_name = chord_name.replace('ø', 'm7b5')

        # Handle + (augmented)
        if '+' in chord_name:
            chord_name = chord_name.replace('+', 'aug')

        return chord_name

    def _normalize_parentheses(self, chord_name: str) -> str:
        """Normalize parentheses notation to standard format.

        Converts parentheses extensions based on whether base chord has 7th:
        - Cmaj7(9) → Cmaj9 (has 7th, so full 9 chord)
        - C7(b9) → C7b9 (has 7th, so full altered chord)
        - C(9) → Cadd9 (no 7th, so just add the 9)
        - Dm7(11) → Dm11 (has 7th, so full 11 chord)

        Args:
            chord_name: Chord with parentheses (e.g., "Cmaj7(9)", "C(9)")

        Returns:
            Chord without parentheses (e.g., "Cmaj9", "Cadd9")
        """
        if '(' not in chord_name:
            return chord_name

        # Skip omit notation - these are handled by _normalize_omit_notation()
        # Don't process C(no3), C(omit3), C(add9), etc.
        if re.search(r'\((?:no|omit|add)\d+', chord_name):
            return chord_name

        # Match root, quality, and parentheses extension
        # Quality can be empty for cases like C(9)
        match = re.match(r'^([A-Ga-g][#b]?)(.*?)\(([^)]+)\)(.*)$', chord_name)
        if not match:
            return chord_name

        root = match.group(1)
        base_quality = match.group(2) or ''  # Can be empty
        extension = match.group(3)
        suffix = match.group(4)  # Anything after the parentheses

        # Check if base quality contains a 7th
        # Need to be careful: dim7, ø7, m7b5, mM7, aug7, etc.
        has_seventh = ('7' in base_quality or
                      base_quality.startswith('maj7') or
                      base_quality.startswith('m7') or
                      base_quality == 'M7')

        if has_seventh:
            # Base has 7th: convert to full extended chord
            # Remove the base 7 and add the extension directly
            # E.g., maj7(9) → maj9, m7(11) → m11, 7(b9) → 7b9

            # Special case: if base is just "7"
            if base_quality == '7':
                # For simple extensions (9, 11, 13), replace the 7
                # C7(9) → C9, C7(11) → C11, C7(13) → C13
                # For alterations (b9, #9, b5, etc.), keep the 7
                # C7(b9) → C7b9, C7(#5) → C7#5
                if extension in ['9', '11', '13']:
                    result = root + extension + suffix
                else:
                    result = root + '7' + extension + suffix
            elif base_quality.startswith('maj7'):
                # maj7(9) → maj9, maj7(#11) → maj#11
                rest = base_quality[4:]  # Everything after "maj7"
                result = root + 'maj' + extension + rest + suffix
            elif base_quality.startswith('m7b5'):
                # Half-diminished: m7b5(9) → m9b5
                rest = base_quality[2:]  # Everything after "m7"
                result = root + 'm' + extension + rest + suffix
            elif base_quality.startswith('m7'):
                # m7(9) → m9, m7(11) → m11
                rest = base_quality[2:]  # Everything after "m7"
                result = root + 'm' + extension + rest + suffix
            elif base_quality.startswith('mM7'):
                # Minor-major 7th: mM7(9) → mM9
                result = root + 'mM' + extension + suffix
            elif base_quality.startswith('dim7'):
                # Diminished 7th: dim7(9) → dim9 (though rare)
                result = root + 'dim' + extension + suffix
            elif base_quality.startswith('aug7'):
                # Augmented 7th: aug7(9) → aug9 (though rare)
                result = root + 'aug' + extension + suffix
            else:
                # Generic fallback: keep the quality and add extension with 7
                # This handles edge cases we haven't covered
                result = root + base_quality + extension + suffix
        else:
            # Base has no 7th: add the extension
            # E.g., C(9) → Cadd9, Dm(11) → Dmadd11
            result = root + base_quality + 'add' + extension + suffix

        return result

    def _normalize_unicode_symbols(self, chord_name: str) -> str:
        """Normalize unicode musical symbols to ASCII equivalents.

        Converts:
        - ♭ (unicode flat) → b
        - ♯ (unicode sharp) → #
        - ♮ (unicode natural) → (remove)
        - Δ (delta/triangle for major) → maj

        Args:
            chord_name: Chord with unicode symbols

        Returns:
            Chord with ASCII symbols
        """
        # Unicode to ASCII mapping
        replacements = {
            '♭': 'b',
            '♯': '#',
            '♮': '',  # Natural sign - just remove it
            'Δ': 'maj',  # Triangle for major 7th
        }

        for unicode_char, ascii_char in replacements.items():
            chord_name = chord_name.replace(unicode_char, ascii_char)

        return chord_name

    def _normalize_enharmonics(self, chord_name: str) -> str:
        """Normalize enharmonic equivalents to standard forms.

        Converts unusual enharmonics to their common equivalents:
        - Cb → B
        - E# → F
        - Fb → E
        - B# → C

        Args:
            chord_name: Chord with possible enharmonic root

        Returns:
            Chord with normalized root
        """
        # Extract root note (first 1-2 characters)
        root_match = re.match(r'^([A-Ga-g][#b]?)', chord_name)
        if not root_match:
            return chord_name

        root = root_match.group(1)
        suffix = chord_name[len(root):]

        # Map enharmonic equivalents to standard forms
        enharmonic_map = {
            'Cb': 'B',
            'Fb': 'E',
            'E#': 'F',
            'B#': 'C',
            # Lowercase versions
            'cb': 'b',
            'fb': 'e',
            'e#': 'f',
            'b#': 'c',
        }

        if root in enharmonic_map:
            return enharmonic_map[root] + suffix

        return chord_name

    def _normalize_alternative_qualities(self, chord_name: str) -> str:
        """Normalize alternative chord quality notations to standard forms.

        Converts:
        - C- → Cm (minus for minor)
        - Cmin → Cm
        - Cmi → Cm
        - CM7 → Cmaj7 (M for major 7th, but not standalone M)
        - Cdom7 → C7 (dominant)
        - Calt → C7alt (altered dominant)

        Args:
            chord_name: Chord with alternative quality notation

        Returns:
            Chord with standard quality notation
        """
        # Extract root to avoid replacing within root (like C# → C#, not C#m)
        root_match = re.match(r'^([A-Ga-g][#b]?)', chord_name)
        if not root_match:
            return chord_name

        root = root_match.group(1)
        quality = chord_name[len(root):]

        # Handle slash chords - only process quality before the slash
        slash_parts = quality.split('/', 1)
        quality_part = slash_parts[0]
        slash_part = '/' + slash_parts[1] if len(slash_parts) > 1 else ''

        # Apply replacements to quality part only
        # Order matters! Do specific patterns before general ones

        # Handle "alt" chord (altered dominant)
        # Note: Will be further processed to expand '7alt' to specific alterations
        if quality_part == 'alt':
            quality_part = '7alt'

        # Expand 7alt to specific alterations that pychord understands
        # Note: 7alt can include b5/#5, b9/#9, #11, b13
        # We use 7b9b13 as a practical simplification (altered 9th and 13th)
        # This gives a usable altered dominant sound without requiring all alterations
        if '7alt' in quality_part:
            quality_part = quality_part.replace('7alt', '7b9b13')

        # Handle dominant seventh variants
        quality_part = quality_part.replace('dom7', '7')
        quality_part = quality_part.replace('dom', '7')

        # Handle major 7th with M notation (but not standalone M for major triad)
        # CM7, CΔ7 → Cmaj7 (already handled Δ → maj in unicode normalization)
        if quality_part.startswith('M7'):
            quality_part = 'maj7' + quality_part[2:]
        elif quality_part == 'M':
            # Standalone M means major triad, just remove it
            quality_part = ''

        # Handle minor variations
        # Do these carefully to avoid replacing 'm' in 'maj', 'dim', etc.
        if quality_part.startswith('min'):
            quality_part = 'm' + quality_part[3:]
        elif quality_part.startswith('mi') and (len(quality_part) == 2 or quality_part[2] in ['7', '9', '1', 'M', '(', 'b', '#']):
            # 'mi' followed by extension or end → minor
            quality_part = 'm' + quality_part[2:]
        elif quality_part.startswith('-'):
            # Minus sign for minor
            quality_part = 'm' + quality_part[1:]

        return root + quality_part + slash_part

    def _normalize_omit_notation(self, chord_name: str) -> str:
        """Normalize omit/no/add notation in parentheses.

        Converts:
        - C(no3) → C5 (power chord)
        - C(omit3) → C5
        - C7(no3) → C7omit3 (for music21)
        - C11(no3) → C11omit3
        - Multiple: C11(no3,5) → C11omit3omit5
        - C(add9) → Cadd9
        - C(add11) → Cadd11

        Args:
            chord_name: Chord with omit/add notation in parentheses

        Returns:
            Normalized chord (music21 compatible format)
        """
        # Handle (add...) notation: C(add9) → Cadd9
        chord_name = re.sub(r'\(add(\d+[#b]?)\)', r'add\1', chord_name)

        # Special case: just (no3) or (omit3) with no other quality → power chord
        if re.match(r'^[A-Ga-g][#b]?\((?:no|omit)3\)$', chord_name):
            root = re.match(r'^([A-Ga-g][#b]?)', chord_name).group(1)
            return root + '5'

        # Normalize parentheses omit notation to music21 format
        # C7(no3) → C7omit3, C11(no3,5) → C11omit3omit5

        # Handle (no...) notation -> convert to omit
        chord_name = re.sub(r'\(no(\d+)\)', r'omit\1', chord_name)
        # Handle (omit...) notation
        chord_name = re.sub(r'\(omit(\d+)\)', r'omit\1', chord_name)
        # Handle comma-separated: (no3,5) or (omit3,5)
        chord_name = re.sub(r'\((?:no|omit)(\d+),(\d+)\)', r'omit\1omit\2', chord_name)
        # Handle multiple (no3)(no5) style
        chord_name = re.sub(r'\)\(no', r'omit', chord_name)
        chord_name = re.sub(r'\)\(omit', r'omit', chord_name)
        # Clean up any remaining parentheses
        chord_name = chord_name.replace('(', '').replace(')', '')

        return chord_name

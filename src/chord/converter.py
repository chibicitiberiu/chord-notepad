"""
Notation converter between American and European chord notation
"""


class NotationConverter:
    """Convert between American (C, D, E...) and European (Do, Re, Mi...) notation"""

    # Mapping tables (uppercase = major, lowercase = minor)
    AMERICAN_TO_EUROPEAN = {
        'C': 'Do',
        'D': 'Re',
        'E': 'Mi',
        'F': 'Fa',
        'G': 'Sol',
        'A': 'La',
        'B': 'Si',
        'c': 'do',
        'd': 're',
        'e': 'mi',
        'f': 'fa',
        'g': 'sol',
        'a': 'la',
        'b': 'si'
    }

    EUROPEAN_TO_AMERICAN = {v: k for k, v in AMERICAN_TO_EUROPEAN.items()}

    @classmethod
    def american_to_european(cls, chord_str):
        """
        Convert American notation chord to European

        Args:
            chord_str: Chord in American notation (e.g., "Cmaj7", "Am/G")

        Returns:
            Chord in European notation (e.g., "Domaj7", "Lam/Sol")
        """
        result = chord_str

        # Handle slash chords (e.g., C/E -> Do/Mi)
        if '/' in result:
            parts = result.split('/', 1)
            root_part = cls._convert_root_american_to_european(parts[0])
            bass_part = cls._convert_root_american_to_european(parts[1])
            return f"{root_part}/{bass_part}"
        else:
            return cls._convert_root_american_to_european(result)

    @classmethod
    def european_to_american(cls, chord_str):
        """
        Convert European notation chord to American

        Args:
            chord_str: Chord in European notation (e.g., "Domaj7", "Lam/Sol")

        Returns:
            Chord in American notation (e.g., "Cmaj7", "Am/G")
        """
        result = chord_str

        # Handle slash chords
        if '/' in result:
            parts = result.split('/', 1)
            root_part = cls._convert_root_european_to_american(parts[0])
            bass_part = cls._convert_root_european_to_american(parts[1])
            return f"{root_part}/{bass_part}"
        else:
            return cls._convert_root_european_to_american(result)

    @classmethod
    def _convert_root_american_to_european(cls, chord_part):
        """Convert root note from American to European"""
        # Extract root note (first 1-2 chars, handling sharps/flats)
        if len(chord_part) >= 2 and chord_part[1] in ['#', 'b']:
            root = chord_part[:2]
            suffix = chord_part[2:]
        else:
            root = chord_part[0]
            suffix = chord_part[1:]

        # Convert root
        root_letter = root[0].upper()
        if root_letter in cls.AMERICAN_TO_EUROPEAN:
            european_root = cls.AMERICAN_TO_EUROPEAN[root_letter]
            if len(root) > 1:  # Has sharp/flat
                european_root += root[1]
            return european_root + suffix

        return chord_part  # Return unchanged if not found

    @classmethod
    def _convert_root_european_to_american(cls, chord_part):
        """Convert root note from European to American"""
        # Try to match European roots (Do, Re, Mi, etc.)
        # Check lowercase first (longer matches), then uppercase
        for european, american in sorted(cls.EUROPEAN_TO_AMERICAN.items(), key=lambda x: len(x[0]), reverse=True):
            if chord_part.startswith(european):
                # Check for sharp/flat after European root
                suffix_start = len(european)
                if suffix_start < len(chord_part) and chord_part[suffix_start] in ['#', 'b']:
                    suffix_start += 1
                    american_root = american + chord_part[len(european)]
                else:
                    american_root = american

                suffix = chord_part[suffix_start:]

                # Handle capitalization convention (lowercase = minor)
                if european[0].islower():
                    # Lowercase European notation means minor
                    # do -> Cm, re -> Dm (unless suffix already specifies quality)
                    if not suffix or (suffix[0] not in ['m', 'M'] and not suffix.startswith('maj') and not suffix.startswith('min')):
                        # Add 'm' for minor if no quality is specified
                        suffix = 'm' + suffix
                    # Convert lowercase american to uppercase
                    american_root = american_root.upper()

                # Normalize European "M" (major) to "maj" for PyChord compatibility
                # DoM -> Cmaj, but Do -> C (major is implied)
                if suffix == 'M':
                    suffix = 'maj'
                elif suffix.startswith('M') and len(suffix) > 1:
                    # Handle cases like "M7" -> "maj7"
                    suffix = 'maj' + suffix[1:]

                return american_root + suffix

        return chord_part  # Return unchanged if not found

    @classmethod
    def format_for_display(cls, chord_str, notation='american'):
        """
        Format chord for display based on notation preference

        Args:
            chord_str: Chord string (assumed to be in American notation)
            notation: 'american' or 'european'

        Returns:
            Formatted chord string
        """
        if notation == 'european':
            return cls.american_to_european(chord_str)
        return chord_str

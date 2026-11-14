"""
Notation converter between American and European chord notation
"""

import unicodedata
from typing import Literal, Optional, Tuple


def lowercase_minor(suffix: str) -> str:
    """The quality of a chord written with a lowercase root, which is always
    minor (as in roman numerals): ``c`` is Cm, ``c7`` Cm7, ``cmaj7`` and
    ``cM7`` C minor-major 7. A quality that already says minor (``m``,
    ``min``, ``mi``, ``mM7``, ``-``) is kept as it is."""
    if suffix.startswith('-') or (suffix.startswith('m') and not suffix.startswith('maj')):
        return suffix
    return 'm' + suffix


def split_bass(chord: str) -> Tuple[str, Optional[str]]:
    """``chord`` split at its slash bass: ``("C", "E")`` for ``C/E``,
    ``("C6/9", "E")`` for ``C6/9/E``, and no bass for ``C6/9``, whose slash
    belongs to the quality (6 and 9 added)."""
    i = chord.rfind('/')
    if i < 0 or chord[i - 1:i] == '6' and chord[i + 1:] == '9':
        return chord, None
    return chord[:i], chord[i + 1:]


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

    @staticmethod
    def _normalize_to_ascii(text: str) -> str:
        """
        Normalize unicode string to ASCII, removing all accents.

        Examples:
            Dó -> Do
            Ré -> Re
            Fá -> Fa
            Lá -> La

        Args:
            text: Unicode string potentially containing accents

        Returns:
            ASCII string with accents removed
        """
        # NFD normalization separates characters from their accents
        nfd = unicodedata.normalize('NFD', text)
        # Filter out combining characters (accents)
        ascii_text = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
        return ascii_text

    @classmethod
    def chord_american_to_european(cls, chord_str: str) -> str:
        """
        Convert a single American-notation chord to European.

        For converting an entire text, see
        :py:meth:`services.song_parser_service.SongParserService.convert_to_european`,
        which uses the chord detector to skip lyrics and non-chord text.

        Args:
            chord_str: Chord in American notation (e.g., "Cmaj7", "Am/G")

        Returns:
            Chord in European notation (e.g., "Domaj7", "Lam/Sol")
        """
        result = chord_str

        # Handle slash chords (e.g., C/E -> Do/Mi)
        body, bass = split_bass(result)
        if bass is not None:
            root_part = cls._convert_root_american_to_european(body)
            bass_part = cls._convert_root_american_to_european(bass)
            return f"{root_part}/{bass_part}"
        else:
            return cls._convert_root_american_to_european(result)

    @classmethod
    def chord_european_to_american(cls, chord_str: str, as_written: bool = False) -> str:
        """
        Convert a single European-notation chord to American.

        For converting an entire text, see
        :py:meth:`services.song_parser_service.SongParserService.convert_to_american`,
        which uses the chord detector to skip lyrics and non-chord text.

        Args:
            chord_str: Chord in European notation (e.g., "Domaj7", "Lam/Sol")
            as_written: Keep the writer's spelling, for rewriting a song: a
                lowercase root stays lowercase (``do7`` -> ``c7``, minor in
                both) and ``M`` stays ``M`` (``DoM7`` -> ``CM7``), so
                converting back gives the same text. Otherwise the result is
                normalized for reading (``do7`` -> ``Cm7``, ``DoM7`` -> ``Cmaj7``).

        Returns:
            Chord in American notation (e.g., "Cmaj7", "Am/G")
        """
        result = chord_str

        # Handle slash chords
        body, bass = split_bass(result)
        if bass is not None:
            root_part = cls._convert_root_european_to_american(body, as_written)
            # A bass is a note, never a minor chord: si is B.
            bass_part = cls._convert_root_european_to_american(bass, True)
            if not as_written:
                bass_part = bass_part[:1].upper() + bass_part[1:]
            return f"{root_part}/{bass_part}"
        else:
            return cls._convert_root_european_to_american(result, as_written)

    @classmethod
    def _convert_root_american_to_european(cls, chord_part: str) -> str:
        """Convert root note from American to European"""
        if not chord_part:
            return chord_part

        # Extract root note (first 1-2 chars, handling sharps/flats)
        if len(chord_part) >= 2 and chord_part[1] in ['#', 'b']:
            root = chord_part[:2]
            suffix = chord_part[2:]
        else:
            root = chord_part[0]
            suffix = chord_part[1:]

        # Convert root, keeping its case: a lowercase root is a minor chord
        # (c -> do), which converts back to Cm.
        root_letter = root[0]
        if root_letter in cls.AMERICAN_TO_EUROPEAN:
            european_root = cls.AMERICAN_TO_EUROPEAN[root_letter]
            if len(root) > 1:  # Has sharp/flat
                european_root += root[1]
            return european_root + suffix

        return chord_part  # Return unchanged if not found

    @classmethod
    def _convert_root_european_to_american(cls, chord_part: str, as_written: bool = False) -> str:
        """Convert root note from European to American"""
        # Normalize accents first (Dó -> Do, Ré -> Re, etc.)
        chord_part = cls._normalize_to_ascii(chord_part)

        # Try to match European roots (Do, Re, Mi, etc.)
        # Check lowercase first (longer matches), then uppercase
        for european, american in sorted(cls.EUROPEAN_TO_AMERICAN.items(), key=lambda x: len(x[0]), reverse=True):
            if chord_part.startswith(european):
                # Check for sharp/flat after European root
                suffix_start = len(european)
                if suffix_start < len(chord_part) and chord_part[suffix_start] in ['#', 'b', '♯', '♭']:
                    suffix_start += 1
                    american_root = american + chord_part[len(european)]
                else:
                    american_root = american

                suffix = chord_part[suffix_start:]
                if as_written:
                    return american_root + suffix

                # Handle capitalization convention (lowercase = minor)
                if european and european[0].islower():
                    # Lowercase European notation means minor
                    # do -> Cm, re -> Dm (unless suffix already specifies quality)
                    suffix = lowercase_minor(suffix)
                    # Uppercase the letter only: sib is Bbm, not BBm
                    american_root = american_root[0].upper() + american_root[1:]

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
    def format_for_display(cls, chord_str: str, notation: Literal['american', 'european'] = 'american') -> str:
        """
        Format chord for display based on notation preference

        Args:
            chord_str: Chord string (assumed to be in American notation)
            notation: 'american' or 'european'

        Returns:
            Formatted chord string
        """
        if notation == 'european':
            return cls.chord_american_to_european(chord_str)
        return chord_str

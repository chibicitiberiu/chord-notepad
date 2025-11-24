"""Helper utilities for key signatures and notation."""

from models.notation import Notation


def get_key_options(notation: Notation) -> list:
    """Get key options based on notation (root notes only).

    For roman numeral chords, only the root note is needed since
    major/minor is indicated by uppercase/lowercase roman numerals.

    Args:
        notation: Notation enum (AMERICAN or EUROPEAN)

    Returns:
        List of key options for the given notation (major keys only)
    """
    if notation == Notation.EUROPEAN:
        # European notation (Do, Re, Mi, etc.) - root notes only
        return [
            "Do", "Do#", "Reb", "Re", "Re#", "Mib", "Mi", "Fa", "Fa#",
            "Solb", "Sol", "Sol#", "Lab", "La", "La#", "Sib", "Si"
        ]
    else:
        # American notation (C, D, E, etc.) - root notes only
        return [
            "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#",
            "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"
        ]

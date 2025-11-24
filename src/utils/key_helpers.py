"""Helper utilities for key signatures and notation."""

from models.notation import Notation


def get_key_options(notation: Notation) -> list:
    """Get key options based on notation.

    Args:
        notation: Notation enum (AMERICAN or EUROPEAN)

    Returns:
        List of key options for the given notation
    """
    if notation == Notation.EUROPEAN:
        # European notation (Do, Re, Mi, etc.)
        return [
            "Do", "Do#", "Reb", "Re", "Re#", "Mib", "Mi", "Fa", "Fa#",
            "Solb", "Sol", "Sol#", "Lab", "La", "La#", "Sib", "Si",
            "Lam", "La#m", "Sibm", "Sim", "Dom", "Do#m", "Rem", "Re#m",
            "Mibm", "Mim", "Fam", "Fa#m", "Solm", "Sol#m"
        ]
    else:
        # American notation (C, D, E, etc.)
        return [
            "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#",
            "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
            "Am", "A#m", "Bbm", "Bm", "Cm", "C#m", "Dm", "D#m",
            "Ebm", "Em", "Fm", "F#m", "Gm", "G#m"
        ]

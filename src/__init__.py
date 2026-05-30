"""
Chord Notepad - A simple text editor with chord detection and playback
"""

from pathlib import Path


def _read_version() -> str:
    try:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0"


__version__ = _read_version()

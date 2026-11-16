"""The name an untitled song goes by: its first lyric line.

A song that was never saved and never renamed is "Untitled" in the title,
but File › Backups lists it, and Save and Export MIDI suggest a file name
for it, by the first line that is lyrics ("Twinkle, twinkle, little star").

A lyric line is one the editor's chord detection calls a text line
(``SongParserService.detect_chords_in_text``, the same call the highlighter's
lines come from) that still has a letter or a digit once its directives
(``{bpm: 90}``) and its comment (``// ...``) are taken out. A leading ``.``
(the plain-text marker) isn't part of the name. Chord lines, directive and
comment lines, blank lines and lines of punctuation only (``---``,
``| | |``) are skipped.

The name is made safe for a file name on Windows, macOS and Linux: the
characters ``\\ / : * ? " < > |`` and control characters become spaces,
runs of spaces become one, and leading dots and trailing punctuation
(``, ; : . -`` and the like, which Windows also refuses at the end) go. A
long line is cut at a word boundary to at most :data:`MAX_LENGTH`
characters. Pure: no state, no I/O.
"""

import re
from typing import Optional

from chordnotepad.chord.detector import ChordDetector
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session.formatting import UNTITLED, UNTITLED_FILE_NAME
from chordnotepad.session.highlighting import find_comments

#: A name is cut (at a word boundary) to at most this many characters.
MAX_LENGTH = 48
#: A word boundary is only used to cut if it leaves at least this much.
_MIN_CUT = 24

# Not allowed in a Windows file name (the strictest of the three), and "/"
# everywhere; control characters too.
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
_SPACES = re.compile(r"\s+")
# Dropped from the end: Windows refuses a trailing dot or space, and a
# trailing comma or dash reads badly in a file name.
_TRAILING = " ,;:.…-–—_"
# Names Windows reserves for devices, with or without an extension.
_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"}
                      | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)})


def _clean(line: str) -> str:
    """``line`` as a file-name-safe name, possibly empty."""
    name = _SPACES.sub(" ", _UNSAFE.sub(" ", line)).strip()
    name = name.lstrip(". ").rstrip(_TRAILING)
    if len(name) > MAX_LENGTH:
        cut = name[:MAX_LENGTH + 1]
        space = cut.rfind(" ")
        name = cut[:space] if space >= _MIN_CUT else name[:MAX_LENGTH]
        name = name.rstrip(_TRAILING)
    if not any(c.isalnum() for c in name):
        return ""
    if name.split(".")[0].strip().upper() in _RESERVED:
        return ""
    return name


def _lyric(line_text: str, parser: SongParserService, notation: str) -> str:
    """The name ``line_text`` gives (cleaned), or "" if it isn't a lyric line."""
    if not line_text.strip():
        return ""
    line = parser.detect_chords_in_text(line_text, notation)[0]
    if not line.is_text_line():
        return ""
    # Take out the directives and the comment, keeping the rest in order.
    cuts = [(d.start, d.end) for d in line.directives] + find_comments(line_text)
    kept, at = [], 0
    for start, end in sorted(cuts):
        if start > at:
            kept.append(line_text[at:start])
        at = max(at, end)
    kept.append(line_text[at:])
    text = " ".join(kept)
    if ChordDetector.is_text_line(line_text):
        text = text.lstrip()[1:]          # the plain-text marker
    return _clean(text)


def lyric_name(text: str, notation: str = "american") -> Optional[str]:
    """The first lyric line of ``text``, cleaned to name a file; None
    without one.

    Args:
        text: The song.
        notation: ``american`` or ``european``, as the editor detects chords
            (a European chord line is a lyric line to American detection).
    """
    parser = SongParserService()
    for line_text in str(text).split("\n"):
        name = _lyric(line_text, parser, notation)
        if name:
            return name
    return None


def song_name(text: str, notation: str = "american") -> str:
    """An untitled song's name: its first lyric line, or ``Untitled``."""
    return lyric_name(text, notation) or UNTITLED


def song_file_name(text: str, notation: str = "american") -> str:
    """The name Save suggests for an untitled song that wasn't renamed:
    ``Twinkle, twinkle, little star.txt`` (``Untitled.txt`` without lyrics)."""
    name = lyric_name(text, notation)
    return f"{name}.txt" if name else UNTITLED_FILE_NAME

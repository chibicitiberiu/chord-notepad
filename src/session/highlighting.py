"""Highlight spans and chord hit-testing, computed from detected lines.

This used to live in the Tk editor (``ChordTextEditor._update_highlighting``,
``_find_comments`` and its pixel hit-test). It is pure now, so every view
paints the same ranges: the Tk editor maps spans to text tags, the Android
editor to an ``AnnotatedString``.

Offsets are Unicode code points into the text the lines were detected in.
"""

import re
from typing import List, Optional, Sequence, Tuple

from models.chord import ChordInfo
from models.line import Line
from session.state import Span, SpanKind

_COMMENT = re.compile(r"//[^\n]*")


def find_comments(text: str) -> List[Tuple[int, int]]:
    """Find the comment ranges: from ``//`` to the end of its line.

    Args:
        text: The whole text.

    Returns:
        ``(start, end)`` for each comment, in text order.
    """
    return [(match.start(), match.end()) for match in _COMMENT.finditer(text)]


def compute_spans(lines: Sequence[Line], text: str) -> Tuple[Span, ...]:
    """The ranges a view highlights for the detected ``lines`` of ``text``.

    Comments come first, then the chords of chord lines (valid or not), then
    the directives of every line (valid or not), each in text order. Ranges of
    different kinds may overlap (a ``//`` inside a directive, say); the view
    decides which wins.

    Args:
        lines: What chord detection returned for ``text``.
        text: The text the lines were detected in (comments are found here).

    Returns:
        The spans.
    """
    spans = [Span(start, end, SpanKind.COMMENT) for start, end in find_comments(text)]
    for line in lines:
        if line.is_chord_line():
            for chord in line.chords:
                kind = SpanKind.CHORD if chord.is_valid else SpanKind.CHORD_INVALID
                spans.append(Span(chord.start, chord.end, kind))
    for line in lines:
        for directive in line.directives:
            kind = SpanKind.DIRECTIVE if directive.is_valid else SpanKind.DIRECTIVE_INVALID
            spans.append(Span(directive.start, directive.end, kind))
    return tuple(spans)


def chord_at(lines: Sequence[Line], offset: int) -> Optional[ChordInfo]:
    """The chord (valid or not) on a chord line covering ``offset``.

    Args:
        lines: Detected lines.
        offset: A code-point offset into the text they were detected in.

    Returns:
        The first chord with ``start <= offset < end``, or None.
    """
    for line in lines:
        if not line.is_chord_line():
            continue
        for chord in line.chords:
            if chord.start <= offset < chord.end:
                return chord
    return None

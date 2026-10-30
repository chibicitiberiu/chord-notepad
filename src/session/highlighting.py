"""Highlight spans and chord hit-testing, computed from detected lines.

This used to live in the Tk editor (``ChordTextEditor._update_highlighting``,
``_find_comments`` and its pixel hit-test). It is pure now, so every view
paints the same ranges: the Tk editor maps spans to text tags, the Android
editor to an ``AnnotatedString``.

Offsets are Unicode code points into the text the lines were detected in.
"""

import re
from typing import Iterable, List, Optional, Sequence, Tuple

from models.chord import ChordInfo
from models.directive import (
    DIRECTIVE_KEYWORDS, DIRECTIVE_SYNTAX, UNKNOWN_DIRECTIVE_SYNTAX, Directive, directive_syntax)
from models.line import Line
from session.events import DirectiveHint
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
            if directive.is_valid and directive.redundant:
                spans.append(Span(directive.start, directive.end, SpanKind.DIRECTIVE_REDUNDANT,
                                  directive.message or ""))
            elif directive.is_valid:
                spans.append(Span(directive.start, directive.end, SpanKind.DIRECTIVE))
            else:
                spans.append(Span(directive.start, directive.end, SpanKind.DIRECTIVE_INVALID,
                                  directive.message or ""))
    return tuple(spans)


def directive_hint(text: str, offset: int, notation: str = "american",
                   directives: Optional[Iterable[Directive]] = None) -> Optional[DirectiveHint]:
    """The directive at ``offset`` with its syntax hint, or None.

    ``text`` is detected afresh in ``notation``, so the answer matches the
    text as it is now even while the editor's chord detection is still
    debounced (and a redundant directive's reason, which depends on the
    chords around it, is right).

    A parsed directive counts when ``start <= offset <= end`` (so right after
    its ``}`` too). Otherwise a directive being typed counts: a ``{`` earlier
    on the same line with no ``}`` after it, outside a comment or a
    plain-text line; its keyword is what follows the brace (up to ``:``),
    and the hint lists every directive that keyword could still become.

    Args:
        text: The text.
        offset: A code-point offset into it.
        notation: ``american`` or ``european``.
        directives: The directives of ``text`` when the caller already has
            them (the session's last detection, or a quick
            ``parse_directives``), so nothing is detected again; None
            detects ``text`` here.
    """
    if directives is None:
        from services.song_parser_service import SongParserService

        lines = SongParserService().detect_chords_in_text(text, notation)
        directives = (d for line in lines for d in line.directives)
    for directive in directives:
        if directive.start <= offset <= directive.end:
            redundant = directive.is_valid and directive.redundant
            return DirectiveHint(offset, directive.start, directive.end,
                                 directive.keyword or "", directive.syntax,
                                 directive.message or "", redundant)
    line_start = text.rfind("\n", 0, offset) + 1
    before = text[line_start:offset]
    brace = before.rfind("{")
    if brace < 0 or "}" in before[brace:] or "//" in before[:brace]:
        return None
    if before.lstrip().startswith("."):
        return None
    typed = before[brace + 1:]
    keyword, colon, _value = typed.partition(":")
    keyword = keyword.strip().lower()
    if colon or not keyword:
        syntax = directive_syntax(keyword) if keyword else UNKNOWN_DIRECTIVE_SYNTAX
    else:
        matches = [k for k in DIRECTIVE_KEYWORDS if k.startswith(keyword)]
        syntax = ("\n".join(DIRECTIVE_SYNTAX[k] for k in matches) if matches
                  else UNKNOWN_DIRECTIVE_SYNTAX)
    return DirectiveHint(offset, line_start + brace, offset, keyword, syntax, "")


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


def _playable(lines: Sequence[Line]) -> List[Tuple[int, ChordInfo]]:
    """The valid chords of chord lines as ``(line_number, chord)``, in text order."""
    return [(line.line_number, chord) for line in lines if line.is_chord_line()
            for chord in line.chords if chord.is_valid]


def first_chord(lines: Sequence[Line]) -> Optional[ChordInfo]:
    """The first valid chord (where playback from the top starts), or None."""
    chords = _playable(lines)
    return chords[0][1] if chords else None


def nearest_chord(lines: Sequence[Line], text: str, offset: int) -> Optional[ChordInfo]:
    """The valid chord a tap at ``offset`` means (the playhead's snap rule).

    1. A valid chord covering ``offset`` (``start <= offset < end``).
    2. Else the nearest valid chord on the same line, by distance in code
       points to its span; on a tie the later one (the chord being heading
       to).
    3. Else the nearest line with valid chords (a lyric line's chords are on
       the line above it, so on a tie the line above wins), and on it the
       chord nearest the tap's column (a tie: the later one).

    Args:
        lines: The detected lines of ``text``.
        text: The text (for line starts and columns).
        offset: A code-point offset; clamped to the text.

    Returns:
        The chord, or None if the text has no valid chord.
    """
    chords = _playable(lines)
    if not chords:
        return None
    offset = max(0, min(int(offset), len(text)))
    for _number, chord in chords:
        if chord.start <= offset < chord.end:
            return chord
    line_number = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    column = offset - line_start

    def distance(chord: ChordInfo, at: int) -> int:
        return chord.start - at if at < chord.start else max(0, at - (chord.end - 1))

    same_line = [c for n, c in chords if n == line_number]
    if same_line:
        # min() keeps the first of equals; reversed, that is the later chord.
        return min(reversed(same_line), key=lambda c: distance(c, offset))
    numbers = sorted({n for n, _c in chords})
    # On a tie the smaller line number (the line above) comes first.
    target = min(numbers, key=lambda n: (abs(n - line_number), n))
    target_start = sum(len(part) + 1 for part in text.split("\n")[:target - 1])
    on_target = [c for n, c in chords if n == target]
    return min(reversed(on_target),
               key=lambda c: distance(c, target_start + column))

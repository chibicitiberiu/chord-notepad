"""The text editor's operations on the song text: find and replace, line
operations, comments and indentation, going to a line.

Pure functions over a string, in code-point offsets (the session's). The
session applies the edits they return (``AppSession.duplicate_lines`` and
the rest) as one undo step each, with the selection they say; the Qt
desktop's find bar uses the lookups directly. Android could use the same
commands later.

An edit is a :class:`TextOp`: replace ``[start, end)`` of the old text with
``replacement``, then select ``anchor``..``cursor`` (offsets into the new
text; ``anchor == cursor`` is a plain caret). A function returns None when
there is nothing to do (moving the first line up, a selection with no
matches, ...).

Selections come as ``(anchor, cursor)``: where the selection started and
where its moving end (the caret) is. The edits keep that direction.

The lines a selection "touches" are the lines from the one holding its
start to the one holding its end, except that a selection of several lines
ending at the very start of a line doesn't take that line in (selecting two
whole lines with Shift+Down ends there).

Comments are ``//`` to the end of the line (``highlighting.find_comments``,
the parser's ``COMMENT_PATTERN``); a commented line is one whose first
non-blank characters are ``//``.
"""

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

#: What a comment starts with, and what Toggle comment puts in front of a line.
COMMENT = "//"
COMMENT_PREFIX = "// "
#: One indentation step (the Tab key inserts it too).
INDENT = "\t"
#: The most spaces Shift+Tab takes off a line indented with spaces.
OUTDENT_SPACES = 4
#: The longest selection whose other occurrences are highlighted.
OCCURRENCE_MAX = 64

Span = Tuple[int, int]


@dataclass(frozen=True)
class TextOp:
    """Replace ``[start, end)`` with ``replacement``, then select
    ``anchor``..``cursor`` (offsets into the new text)."""

    start: int
    end: int
    replacement: str
    anchor: int
    cursor: int

    def apply(self, text: str) -> str:
        """``text`` with the edit made (for tests and callers that need the result)."""
        return text[:self.start] + self.replacement + text[self.end:]


# -- find and replace ------------------------------------------------------------------


def _pattern(query: str, match_case: bool, whole_word: bool) -> "re.Pattern[str]":
    body = re.escape(query)
    if whole_word:
        # Not glued to a letter, digit or underscore on either side; works for
        # queries that start or end with punctuation too ("{bpm", "F#").
        body = r"(?<!\w)" + body + r"(?!\w)"
    return re.compile(body, 0 if match_case else re.IGNORECASE)


def find_all(text: str, query: str, match_case: bool = False,
             whole_word: bool = False) -> List[Span]:
    """Every match of ``query`` in ``text``, in order, not overlapping.

    Case-insensitive unless ``match_case`` (lengths never change, so the
    offsets are the text's). With ``whole_word`` a match must not have a
    word character right before or after it. An empty query matches nothing.
    """
    if not query:
        return []
    return [m.span() for m in _pattern(query, match_case, whole_word).finditer(text)]


def is_match(text: str, span: Span, query: str, match_case: bool = False,
             whole_word: bool = False) -> bool:
    """Whether ``span`` is one of :func:`find_all`'s matches."""
    return tuple(span) in set(find_all(text, query, match_case, whole_word))


def next_match(matches: Sequence[Span], position: int,
               backward: bool = False) -> Optional[Tuple[int, bool]]:
    """The match to go to from ``position``: its index, and whether the
    search wrapped around the end (or the start, going back).

    Forward: the first match starting at or after ``position``. Backward:
    the last one ending at or before it. None when there are no matches.
    """
    if not matches:
        return None
    if backward:
        for i in range(len(matches) - 1, -1, -1):
            if matches[i][1] <= position:
                return i, False
        return len(matches) - 1, True
    for i, (start, _) in enumerate(matches):
        if start >= position:
            return i, False
    return 0, True


def replace_match(text: str, span: Span, query: str, replacement: str,
                  match_case: bool = False, whole_word: bool = False) -> Optional[TextOp]:
    """Replace the match at ``span``, the caret after the replacement; None
    when ``span`` isn't a match of ``query`` (the text changed meanwhile)."""
    if not is_match(text, span, query, match_case, whole_word):
        return None
    start, end = span
    caret = start + len(replacement)
    return TextOp(start, end, replacement, caret, caret)


def replace_all(text: str, query: str, replacement: str, match_case: bool = False,
                whole_word: bool = False, cursor: int = 0) -> Tuple[Optional[TextOp], int]:
    """Every match replaced, as one edit, and how many there were.

    The edit spans the first match to the last; the caret stays where it
    was in the text around the matches (after the replacement when it was
    inside one). ``(None, 0)`` without matches.
    """
    matches = find_all(text, query, match_case, whole_word)
    if not matches:
        return None, 0
    first, last = matches[0][0], matches[-1][1]
    parts = []
    at = first
    for start, end in matches:
        parts.append(text[at:start])
        parts.append(replacement)
        at = end
    shift = 0
    new_cursor = None
    for start, end in matches:
        if cursor <= start:
            break
        if cursor <= end:               # inside the match, or at its end: after its replacement
            new_cursor = start + shift + len(replacement)
            break
        shift += len(replacement) - (end - start)
    if new_cursor is None:
        new_cursor = cursor + shift
    return TextOp(first, last, "".join(parts), new_cursor, new_cursor), len(matches)


def occurrences(text: str, selection: Span) -> List[Span]:
    """The selected text's occurrences (itself included), for the subtle
    highlight of a selected word: exact case, not inside a longer word.

    Only for a selection on one line without spaces around it, at most
    :data:`OCCURRENCE_MAX` long, that is a whole word itself (``Am`` but
    not the ``Am`` of ``Am7``); otherwise none.
    """
    start, end = sorted(selection)
    word = text[start:end]
    if (not word or len(word) > OCCURRENCE_MAX or "\n" in word
            or word != word.strip() or any(c.isspace() for c in word)):
        return []
    spans = find_all(text, word, match_case=True, whole_word=True)
    return spans if (start, end) in spans else []


# -- lines -------------------------------------------------------------------------------


def line_start(text: str, offset: int) -> int:
    """Where the line holding ``offset`` starts."""
    return text.rfind("\n", 0, offset) + 1


def line_end(text: str, offset: int) -> int:
    """Where the line holding ``offset`` ends (its newline, or the text's end)."""
    end = text.find("\n", offset)
    return len(text) if end < 0 else end


def touched_lines(text: str, anchor: int, cursor: int) -> Span:
    """``(first, last_end)``: the start of the first line the selection
    touches and the end of the last one (before its newline)."""
    lo, hi = min(anchor, cursor), max(anchor, cursor)
    if hi > lo and text[hi - 1] == "\n":
        hi -= 1             # ends at a line's start: that line isn't in it
    return line_start(text, lo), line_end(text, hi)


def line_count(text: str) -> int:
    """How many lines the text has (an empty text has one)."""
    return text.count("\n") + 1


def line_offset(text: str, line: int) -> int:
    """Where line ``line`` (1-based) starts, clamped to the first and last line."""
    line = max(1, min(int(line), line_count(text)))
    at = 0
    for _ in range(line - 1):
        at = text.index("\n", at) + 1
    return at


def select_lines(text: str, anchor: int, cursor: int) -> Span:
    """Select Line (Ctrl+L): ``(anchor, cursor)`` of the lines the selection
    touches, whole, newline included; when it is whole lines already, one
    more line below. The caret goes at the end."""
    lo, hi = min(anchor, cursor), max(anchor, cursor)
    whole = (hi > lo and line_start(text, lo) == lo
             and (hi == len(text) or text[hi - 1] == "\n"))
    if whole:
        if hi == len(text):
            return lo, hi
        end = line_end(text, hi)
        return lo, min(len(text), end + 1)
    first, last_end = touched_lines(text, lo, hi)
    return first, min(len(text), last_end + 1)


def _column_kept(text: str, start: int, column: int) -> int:
    """The offset ``column`` characters into the line starting at ``start``
    (its end, if it is shorter)."""
    return min(start + column, line_end(text, start))


def duplicate(text: str, anchor: int, cursor: int) -> TextOp:
    """Duplicate Line or Selection (Ctrl+D).

    With a selection, its text goes in again right after it and the copy is
    selected (the direction kept). Without, the caret's line is repeated
    below it and the caret moves down with it, on the same column.
    """
    if anchor != cursor:
        lo, hi = min(anchor, cursor), max(anchor, cursor)
        copy = text[lo:hi]
        new_lo, new_hi = hi, hi + len(copy)
        if cursor >= anchor:
            return TextOp(hi, hi, copy, new_lo, new_hi)
        return TextOp(hi, hi, copy, new_hi, new_lo)
    start, end = line_start(text, cursor), line_end(text, cursor)
    line = text[start:end]
    caret = cursor + len(line) + 1
    return TextOp(end, end, "\n" + line, caret, caret)


def move_lines(text: str, anchor: int, cursor: int, offset: int) -> Optional[TextOp]:
    """Move the lines the selection touches up (``offset`` -1) or down (+1)
    past their neighbour, the selection with them; None at the edge."""
    if offset not in (-1, 1):
        raise ValueError(f"move_lines offset must be -1 or 1, not {offset}")
    first, last_end = touched_lines(text, anchor, cursor)
    block = text[first:last_end]
    if first == len(text) and first > 0:
        return None         # the empty line after the final newline isn't a line to move
    if offset < 0:
        if first == 0:
            return None
        above = line_start(text, first - 1)
        neighbour = text[above:first - 1]
        shift = -(len(neighbour) + 1)
        return TextOp(above, last_end, block + "\n" + neighbour, anchor + shift, cursor + shift)
    if last_end >= len(text):
        return None
    below_end = line_end(text, last_end + 1)
    if below_end == len(text) == last_end + 1:
        return None         # only the final newline below: the text keeps ending with it
    neighbour = text[last_end + 1:below_end]
    shift = len(neighbour) + 1
    return TextOp(first, below_end, neighbour + "\n" + block, anchor + shift, cursor + shift)


def delete_lines(text: str, anchor: int, cursor: int) -> TextOp:
    """Delete Line (Ctrl+Shift+K): the lines the selection touches, with
    their newline; the caret on the line that takes their place, on the
    caret's column."""
    first, last_end = touched_lines(text, anchor, cursor)
    column = cursor - line_start(text, cursor)
    if last_end < len(text):
        start, end = first, last_end + 1
    elif first > 0:
        start, end = first - 1, last_end      # the last line: the newline before it goes
    else:
        start, end = first, last_end
    new = text[:start] + text[end:]
    # The caret's line is now the one after the deleted lines (the one
    # before them, when they were the last).
    caret = _column_kept(new, line_start(new, min(start, len(new))), column)
    return TextOp(start, end, "", caret, caret)


# -- per-line edits: comments and indentation ------------------------------------------

#: One line's change: at ``column``, ``removed`` characters become ``inserted``.
_LineChange = Tuple[int, int, str]


def _edit_lines(text: str, anchor: int, cursor: int,
                change: Callable[[List[str]], List[Optional[_LineChange]]]) -> Optional[TextOp]:
    """Apply ``change`` (one optional change per touched line) as one edit.

    The selection follows the text: its start stays before what goes in at
    its own position (so whole selected lines stay whole), its end and a
    plain caret move after it.
    """
    first, last_end = touched_lines(text, anchor, cursor)
    lines = text[first:last_end].split("\n")
    changes = change(lines)
    if not any(c is not None and (c[1] or c[2]) for c in changes):
        return None
    out = []
    # (old offset of the change, removed, inserted length), in text order.
    marks = []
    at = first
    for line, c in zip(lines, changes):
        if c is None:
            out.append(line)
        else:
            column, removed, inserted = c
            out.append(line[:column] + inserted + line[column + removed:])
            marks.append((at + column, removed, len(inserted)))
        at += len(line) + 1

    def mapped(pos: int, after: bool) -> int:
        shift = 0
        for where, removed, inserted in marks:
            if pos < where or (pos == where and not after and removed == 0):
                break
            if pos < where + removed:
                return where + shift + (inserted if after else 0)
            shift += inserted - removed
        return pos + shift

    lo_after = anchor == cursor
    if cursor >= anchor:
        new_anchor, new_cursor = mapped(anchor, lo_after), mapped(cursor, True)
    else:
        new_anchor, new_cursor = mapped(anchor, True), mapped(cursor, False)
    return TextOp(first, last_end, "\n".join(out), new_anchor, new_cursor)


def _leading(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def toggle_comment(text: str, anchor: int, cursor: int) -> Optional[TextOp]:
    """Toggle Comment (Ctrl+/) on the lines the selection touches.

    When every non-blank line among them is a comment, the ``//`` (and one
    space after it) comes off each. Otherwise ``// `` goes in front of each
    non-blank line, all at the same column (the smallest indentation among
    them), so lines aligned with each other stay aligned. Blank lines are
    left alone, unless they are all there is (a comment can then be typed).
    """
    def change(lines: List[str]) -> List[Optional[_LineChange]]:
        filled = [line for line in lines if line.strip()]
        if not filled:
            return [(len(line), 0, COMMENT_PREFIX) for line in lines]
        if all(line.lstrip(" \t").startswith(COMMENT) for line in filled):
            result: List[Optional[_LineChange]] = []
            for line in lines:
                if not line.strip():
                    result.append(None)
                    continue
                column = _leading(line)
                removed = len(COMMENT)
                if line[column + removed:column + removed + 1] == " ":
                    removed += 1
                result.append((column, removed, ""))
            return result
        column = min(_leading(line) for line in filled)
        return [(column, 0, COMMENT_PREFIX) if line.strip() else None for line in lines]

    return _edit_lines(text, anchor, cursor, change)


def indent_lines(text: str, anchor: int, cursor: int, outdent: bool = False) -> Optional[TextOp]:
    """Indent (Tab) or unindent (Shift+Tab) the lines the selection touches.

    Indenting puts a tab in front of every line that isn't empty. Unindenting
    takes one leading tab off a line that starts with one, and the same
    number of spaces (up to :data:`OUTDENT_SPACES`, but no more than the
    least-indented of them has) off the lines that start with spaces, so
    chords and the lyrics under them keep their alignment. None when
    nothing changes.
    """
    def change(lines: List[str]) -> List[Optional[_LineChange]]:
        if not outdent:
            return [(0, 0, INDENT) if line else None for line in lines]
        spaced = [len(line) - len(line.lstrip(" ")) for line in lines
                  if line.startswith(" ") and line.strip()]
        spaces = min([OUTDENT_SPACES] + spaced)
        result: List[Optional[_LineChange]] = []
        for line in lines:
            if line.startswith("\t"):
                result.append((0, 1, ""))
            elif line.startswith(" ") and line.strip():
                result.append((0, spaces, ""))
            elif line.startswith(" "):        # only spaces: as many as it has, up to the step
                result.append((0, min(len(line), spaces), ""))
            else:
                result.append(None)
        return result

    return _edit_lines(text, anchor, cursor, change)


def spans_lines(text: str, anchor: int, cursor: int) -> bool:
    """Whether the selection reaches over more than one line (Tab then
    indents instead of typing a tab)."""
    lo, hi = min(anchor, cursor), max(anchor, cursor)
    return "\n" in text[lo:hi]

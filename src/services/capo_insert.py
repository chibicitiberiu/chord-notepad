"""Headless capo-directive insertion.

Inserts a ``{capo: N}`` directive into song text on its own line. Like
``{key: ...}`` and ``{bpm: ...}``, ``{capo: ...}`` is a forward-scoping song
directive: it takes effect from the line it sits on and applies to everything
after it. This module only performs the text edit; it does not decide *which*
capo value to use (that is the advisor's job) and it does not touch Tk or the
filesystem.

Placement policy
----------------
The directive is inserted as a whole new line, ``{capo: N}\\n``, at the
*beginning* of the physical line that contains ``selection_start`` (the caller's
selection/cursor char offset). It never splits an existing line mid-way: the
offset is snapped back to the start of its line before the text is inserted, so
the directive always lands at column 0. When ``selection_start`` is ``None`` the
directive is inserted at the very top of the document (offset 0).

All existing characters are preserved verbatim; the only change is the inserted
line. The returned offset is the char position of the inserted ``{`` (equal to
the start-of-line offset), which lets a caller reposition the cursor or select
the freshly inserted directive for undo.

Value policy
------------
``N`` is emitted as-is, including ``0`` and negative numbers. ``{capo: 0}`` is a
legitimate, deliberate "no capo" marker, so it is *not* special-cased away here.
Whether a particular value is worth inserting is a decision for the caller.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _line_start_offset(text: str, offset: int) -> int:
    """Return the char offset of the start of the line containing ``offset``.

    ``offset`` is clamped into ``[0, len(text)]`` first. The result is the index
    just after the previous newline, or 0 if there is no preceding newline.
    """
    offset = max(0, min(offset, len(text)))
    newline = text.rfind('\n', 0, offset)
    return newline + 1 if newline != -1 else 0


def insert_capo_directive(
    text: str,
    capo: int,
    selection_start: Optional[int] = None,
) -> Tuple[str, int]:
    """Insert a ``{capo: N}`` directive on its own line into ``text``.

    The directive is placed at the beginning of the line containing
    ``selection_start`` (snapped to that line's start so it never lands
    mid-line). When ``selection_start`` is ``None`` it is inserted at the top of
    the document.

    Args:
        text: Full document text.
        capo: Capo fret number to write. Emitted verbatim; ``0`` and negatives
            are inserted as-is (the caller decides whether that is desired).
        selection_start: Char offset of the selection/cursor. ``None`` inserts
            at offset 0. Values outside ``[0, len(text)]`` are clamped.

    Returns:
        A ``(new_text, directive_char_offset)`` tuple. ``directive_char_offset``
        is the position of the inserted ``{``, i.e. the start-of-line offset
        where the new directive begins.
    """
    if selection_start is None:
        insert_at = 0
    else:
        insert_at = _line_start_offset(text, selection_start)

    directive = f"{{capo: {capo}}}\n"
    new_text = text[:insert_at] + directive + text[insert_at:]
    return new_text, insert_at

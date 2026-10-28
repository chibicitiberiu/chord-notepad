"""The session's state DTOs: what a view needs to draw itself.

States are frozen dataclasses holding only ``str``/``int``/``float``/``bool``/
``None``, tuples of those and ``str`` enums, so the bridge can serialize them
and no live object (a ``ChordInfo``, a ``Line``) leaks to a view. The session
keeps the latest value of each state type, replays them to a new listener,
and coalesces repeated changes (see :mod:`session.emitter`).

Only the states the session already publishes are defined here; the rest of
the design's list (``docs/architecture/session.md``) arrives with the steps
that publish them.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class SpanKind(str, Enum):
    """What a highlighted range of the text is."""

    CHORD = "chord"
    CHORD_INVALID = "chord_invalid"
    DIRECTIVE = "directive"
    DIRECTIVE_INVALID = "directive_invalid"
    COMMENT = "comment"


@dataclass(frozen=True)
class Span:
    """A highlighted range ``[start, end)`` of the text, in code points."""

    start: int
    end: int
    kind: SpanKind


@dataclass(frozen=True)
class HighlightState:
    """The highlight spans for one version of the text.

    Attributes:
        text_revision: The session's revision of the text the spans were
            computed for. It goes up on every change to the session's copy.
        client_token: The token the view passed with the ``set_text`` that
            produced that text (0 for edits the session made). A view whose
            text has moved on since can tell the spans are stale and wait for
            the next state.
        spans: Comments, then chords, then directives, each in text order.
    """

    text_revision: int
    client_token: int
    spans: Tuple[Span, ...]

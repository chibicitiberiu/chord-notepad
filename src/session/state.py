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
from typing import Optional, Tuple


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


class PlaybackStatus(str, Enum):
    """Whether a song is playing."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass(frozen=True)
class PlaybackState:
    """Song playback: the transport status and the chord that is sounding.

    Attributes:
        status: Idle, playing or paused.
        playing_span: The chord sounding now (kind ``CHORD``), in code points
            of the text playback started from; None when idle or before the
            first chord.
        chord_index: Index of that chord in the played song's unrolled chord
            list (loop passes have distinct indices), or None.
        bar: The current bar, 1-based (0 when idle).
        total_bars: Bars in the played song (0 when idle).
        bpm: The effective tempo of the chord sounding now (directives
            applied), or None before the first chord and when idle.
            Interim: the design shows it as ``ToolbarState.bpm_display``,
            which arrives in step 9.
    """

    status: PlaybackStatus
    playing_span: Optional[Span] = None
    chord_index: Optional[int] = None
    bar: int = 0
    total_bars: int = 0
    bpm: Optional[int] = None


@dataclass(frozen=True)
class StatusState:
    """The status line under the editor."""

    text: str


@dataclass(frozen=True)
class EditorState:
    """How the editor behaves.

    Attributes:
        read_only: True while a song plays or is paused (the editor is locked
            so the playing-chord offsets stay valid).

    The design's font and notation fields arrive with the steps that move
    them into the session (9 and 10).
    """

    read_only: bool


@dataclass(frozen=True)
class MenuItem:
    """One choice in a menu or list a view shows.

    Attributes:
        label: What the user sees.
        value: What the view sends back when it is chosen.
    """

    label: str
    value: str

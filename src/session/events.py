"""The session's one-off events: things that happened, delivered in order.

Unlike states, events are never coalesced and never replayed to a new
listener (see :mod:`session.emitter`). Like states they are frozen and carry
only plain values, so the bridge can serialize them.

Only the events the session already emits are defined here; the rest of the
design's list (``docs/architecture/session.md``) arrives with the steps that
emit them.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from session.state import MenuItem


@dataclass(frozen=True)
class UserError:
    """Something the user asked for failed in an expected way; tell them why.

    Attributes:
        title: A short title (the dialog's title on desktop).
        message: The full, user-facing explanation.
    """

    title: str
    message: str


@dataclass(frozen=True)
class AudioUnavailable:
    """Audio couldn't be started for something the user did.

    The session already applied the reporting policy: failures of Play are
    emitted every time, failures of click-to-hear actions only the first time
    in a session (later ones are only logged).

    Attributes:
        message: The full, user-facing explanation.
        from_click: True if a click-to-hear action (a chord tap) failed,
            False for Play.
    """

    message: str
    from_click: bool


class UndoPolicy(str, Enum):
    """How a view folds a :class:`TextEdited` into its undo history."""

    GROUP = "group"
    """One undo step on its own (transpose, capo)."""
    PLAIN = "plain"
    """Like any edit (convert notation, inserts)."""
    RESET = "reset"
    """The history starts over (a document was opened)."""


@dataclass(frozen=True)
class TextEdited:
    """The session changed the text; the view applies the same splice.

    Replace ``[start, end)`` of the view's text with ``replacement`` (offsets
    in code points), fold it into the undo history by ``undo`` and put the
    cursor at ``cursor``. The view must not report the result back as a user
    edit: the session's copy already has it.

    Attributes:
        text_revision: The session's text revision after the edit.
        start: Start of the replaced range.
        end: End of the replaced range (== start for an insert).
        replacement: The new text for the range.
        undo: How the edit goes into the undo history.
        cursor: Where the cursor goes afterwards.
    """

    text_revision: int
    start: int
    end: int
    replacement: str
    undo: UndoPolicy
    cursor: int


@dataclass(frozen=True)
class InsertDirectiveRequest:
    """Ask for the fields of a directive to insert.

    Answer with ``respond(request_id, fields)``, a ``{field: value}`` mapping
    (see :mod:`session.directives`), or None to cancel. The view can check
    the fields with :func:`session.directives.check_directive` while the user
    types; the session checks them again before inserting.

    Attributes:
        request_id: Pass back to ``respond``.
        kind: ``bpm``, ``time``, ``key``, ``label`` or ``loop``.
        existing_labels: The song's labels, sorted (a new label must differ;
            a loop jumps back to one of them, see
            :func:`session.directives.loop_label_choices`).
        notation: ``american`` or ``european`` (the key options).
    """

    request_id: int
    kind: str
    existing_labels: Tuple[str, ...]
    notation: str


@dataclass(frozen=True)
class CapoChoiceRequest:
    """Ask which fretboard voicing a capo suggestion should optimize for.

    Answer with ``respond(request_id, value)``, the chosen option's value, or
    None to cancel.

    Attributes:
        request_id: Pass back to ``respond``.
        options: The fretboard voicings.
        default: The value to preselect.
    """

    request_id: int
    options: Tuple[MenuItem, ...]
    default: str

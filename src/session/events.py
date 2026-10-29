"""The session's one-off events: things that happened, delivered in order.

Unlike states, events are never coalesced and never replayed to a new
listener (see :mod:`session.emitter`). Like states they are frozen and carry
only plain values, so the bridge can serialize them.

Only the events the session already emits are defined here; the rest of the
design's list (``docs/architecture/session.md``) arrives with the steps that
emit them.

Requests (``...Request``) carry a ``request_id``: the view answers each with
``AppSession.respond(request_id, value)``, where None always means cancel.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from session.state import MenuItem, Span


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


@dataclass(frozen=True)
class UnexpectedError:
    """Something failed that nothing handled: a bug, not the user's doing.

    Emitted on hosts whose error handler reports through the session
    (Android: ``session.bridge.ErrorEvents``); the desktop shows its own
    dialog instead (``utils.error_reporting``).

    Attributes:
        message: A one-line description (exception type and text).
        context: What was running (``"bridge"`` for a command the bridge
            couldn't decode or doesn't know, a command name, a callback);
            None if unknown.
    """

    message: str
    context: Optional[str] = None


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
class DirectiveCheck:
    """The live check of a directive's fields (reply to ``check_directive``).

    Attributes:
        kind: The directive kind that was checked.
        request_id: The id of the Insert request the check is for.
        fields: The fields that were checked, echoed so a view can tell
            a late reply from one for what is typed now.
        errors: ``{field: message}`` for a problem about one field.
        form_error: A problem about no particular field, else "".
    """

    kind: str
    request_id: int
    fields: Any
    errors: Any
    form_error: str


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


class DiscardChoice(str, Enum):
    """The answers to :class:`ConfirmDiscardRequest`."""

    SAVE = "save"
    """Save the changes first (asks for a name if the document has none)."""
    DISCARD = "discard"
    """Go on without saving."""
    CANCEL = "cancel"
    """Stop what was being done (None means the same)."""


@dataclass(frozen=True)
class ConfirmDiscardRequest:
    """The document has unsaved changes: save them before going on?

    Asked before New, Open and closing the app. Answer with
    ``respond(request_id, choice)``, a :class:`DiscardChoice` value
    (``"save"``, ``"discard"`` or ``"cancel"``); None cancels too.

    Attributes:
        request_id: Pass back to ``respond``.
    """

    request_id: int


class PickMode(str, Enum):
    """What a :class:`PickDocumentRequest` picks a document for."""

    OPEN = "open"
    """An existing song to open."""
    SAVE = "save"
    """Where to save the song (Save As)."""
    EXPORT_MIDI = "export_midi"
    """Where to write a MIDI export."""


@dataclass(frozen=True)
class PickDocumentRequest:
    """Ask the user to pick a document (the platform's file picker).

    Answer with ``respond(request_id, ref)``, a :class:`DocumentRef` from the
    platform's store (desktop: ``FileSystemDocumentStore.ref_for_path``), or
    None if the user cancelled.

    Attributes:
        request_id: Pass back to ``respond``.
        mode: Open, save or export.
        suggested_name: The name to pre-fill when saving or exporting
            (``"song.txt"``, ``"song.mid"``); empty when opening.
    """

    request_id: int
    mode: PickMode
    suggested_name: str


@dataclass(frozen=True)
class CloseApproved:
    """The app may close now (nothing unsaved, or the user chose).

    Emitted by ``request_close``. The view tears itself down; the session
    doesn't stop anything itself.
    """


@dataclass(frozen=True)
class VoicingEditorSchema:
    """The voicings editor's form schemas (``request_voicing_editor_schema``).

    Static for a given ``version`` and platform; a view keeps it.

    Attributes:
        version: ``settings_forms.voicing_form.SCHEMA_VERSION``.
        schema: ``voicing_form.editor_schema()`` as JSON: ``models``,
            ``tree_groups``, ``texts``, ``help`` and ``forms`` (model ->
            sections -> fields).
    """

    version: int
    schema: Any


@dataclass(frozen=True)
class QuickStartBlock:
    """One block of a Quick Start page.

    Attributes:
        kind: ``text``, ``snippet`` or ``image``.
        text: The paragraph, or the snippet's song text ("" for an image).
        notation: A snippet's notation, else None.
        spans: A snippet's highlight spans (as the editor paints them).
        image: An image's resource path (``resources/...``), else None.
    """

    kind: str
    text: str
    notation: Optional[str]
    spans: Tuple[Span, ...]
    image: Optional[str]


@dataclass(frozen=True)
class QuickStartPage:
    """A Quick Start page: a title and its blocks."""

    title: str
    blocks: Tuple[QuickStartBlock, ...]


@dataclass(frozen=True)
class QuickStartContent:
    """The Quick Start tour for this platform (``request_quick_start``).

    Attributes:
        pages: The pages, in order.
        show_on_startup: Whether Quick Start opens at startup; "Don't show
            this again" sends ``set_show_quick_start_on_startup(false)``.
    """

    pages: Tuple[QuickStartPage, ...]
    show_on_startup: bool


@dataclass(frozen=True)
class RenameFailed:
    """``rename_document`` couldn't rename the document.

    Attributes:
        name: The name the user typed (without the extension), so the view
            can keep it in the field or pass it to ``save_as(name)``.
        reason: Why, worded for the user (an invalid name, a name already
            in use, storage that can't rename).
        can_save_as: True when the name itself is fine and Save As under it
            is the way out (the storage refused); False when the name has
            to change.
    """

    name: str
    reason: str
    can_save_as: bool

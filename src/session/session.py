"""AppSession: the Tk-free application layer the views drive.

The session composes the existing viewmodels and is their observer; views send
it primitive-typed commands and get back one stream of frozen DTOs (see
``docs/architecture/session.md``). It is being built up step by step: so far
it owns the text mirror, debounced chord detection, the highlight spans, the
chord-sheet feed, playback (transport, playing chord, status line, editor
lock, audio-failure reporting), the programmatic edits (transpose, capo,
convert notation, inserts), which it sends to the views as ``TextEdited``,
the toolbar, the menus, settings, and the document flows (new, open, save,
save as, export MIDI, close; the recent list and the window title). Renders
the user waits for (MIDI export, Suggest Capo) run on a background worker.
The Tk window talks to nothing else (``tests/test_main_window_guard.py``).

Every public command and every callback the session schedules runs inside
:meth:`Emitter.batch`, so output is delivered at the outermost exit and never
in the middle of a command. All of it runs on the session thread.
"""

import contextlib
import dataclasses
import functools
import logging
import os
from typing import (
    TYPE_CHECKING, Any, Callable, Dict, Generator, Iterator, Optional, Sequence, Tuple, TypeVar,
)

from constants import CHORD_DETECTION_DEBOUNCE_MS, MAX_FONT_SIZE, MIN_FONT_SIZE
from exceptions import (
    AudioInitializationError, ChordNotepadError, ConfigurationError, FileOperationError,
    RenameNotSupported,
)
from models.notation import Notation
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from session import directives, errors, formatting, quick_start, song_defaults, toolbar
from session.platform import ANDROID, DESKTOP, TRACKS_PLAYHEAD, check_platform, pick
from session.audio_policy import AudioFailurePolicy
from session.emitter import Emitter, Listener
from session.documents import DocumentRef
from session.events import (
    AudioUnavailable, CapoChoiceRequest, CloseApproved, ConfirmDiscardRequest, DiscardChoice,
    InsertDirectiveRequest, PickDocumentRequest, PickMode, QuickStartBlock, QuickStartContent,
    DirectiveCheck, DirectiveHint, QuickStartPage, RenameFailed, TextEdited, UndoPolicy,
    UnexpectedError,
    UserError, VoicingEditorSchema,
)
from session.flows import Flow, FlowRunner
from session.highlighting import (
    chord_at, compute_spans, directive_hint, first_chord, nearest_chord)
from session.host import Cancellable, Host
from session.settings import TIME_SIGNATURE_UNITS, MAX_RECENT_LIMIT, SettingsValues
from session.settings_edit import SettingsEdit
from session.workers import BackgroundWorker, Job, Outcome
from session.state import (
    ChordSheetState, ChordSheetView, DocumentState, EditorState, HighlightState,
    IdentifierNote, IdentifierState, InstrumentMenuState, MenuItem, PlayAction, PlaybackState,
    INACTIVE_VOICING_EDITOR, PlaybackStatus, RecentDocumentsState, SettingsState,
    SongDefaultsState, Span, SpanKind, StatusState, ToolbarState, VoicingMenuState,
)

if TYPE_CHECKING:
    # Type-only: the chord-sheet viewmodel still imports PIL (see the core
    # import guard), so the session must not import it at run time.
    from session.bootstrap import CoreServices
    from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel
    from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
    from viewmodels.main_window_viewmodel import MainWindowViewModel
    from viewmodels.settings_viewmodel import SettingsChanges, SettingsViewModel
    from viewmodels.text_editor_viewmodel import TextEditorViewModel

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

Selection = Optional[Sequence[int]]

# A step of a document flow that reports whether it went through (the
# unsaved-changes question, a save): ``ok = yield from self._save_flow()``.
SubFlow = Generator[Any, Any, bool]

# The viewmodel properties the toolbar shows (besides the notation).
_TOOLBAR_INPUTS = ("bpm", "bpm_multiplier", "metronome_enabled", "key",
                   "time_signature_beats", "time_signature_unit")

# The chord-sheet viewmodel properties ChordSheetState mirrors (besides the
# rendered song, which bumps its revision).
_CHORD_SHEET_INPUTS = ("visible", "active_view", "available_views", "zoom", "current_index")

_PLAY_ACTIONS = {
    PlaybackStatus.IDLE: PlayAction.PLAY,
    PlaybackStatus.PLAYING: PlayAction.PAUSE,
    PlaybackStatus.PAUSED: PlayAction.RESUME,
}


def _common_prefix(a: str, b: str) -> int:
    """The length of the longest common prefix of ``a`` and ``b``."""
    n = min(len(a), len(b))
    i, step = 0, 256
    while i + step <= n and a[i:i + step] == b[i:i + step]:
        i += step
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _shift_offset(old: str, new: str, offset: int) -> int:
    """Where ``offset`` into ``old`` lands in ``new`` (one edited range assumed).

    The edit is the span between the common prefix and suffix. An offset at
    or after its end moves by the length difference; one inside it goes to
    the edit's start; one before it stays.
    """
    prefix = _common_prefix(old, new)
    limit = min(len(old), len(new)) - prefix
    suffix = _common_prefix(old[::-1][:limit], new[::-1][:limit]) if limit > 0 else 0
    old_end = len(old) - suffix
    if offset >= old_end:
        return offset + len(new) - len(old)
    return min(offset, prefix)


def _command(method: F) -> F:
    """Run a public method as a session command (thread check, batched output)."""

    @functools.wraps(method)
    def wrapper(self: "AppSession", *args: Any, **kwargs: Any) -> Any:
        self._require_session_thread(method.__name__)
        with self._emitter.batch():
            return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class AppSession:
    """The application layer shared by the Tk and the mobile UIs."""

    def __init__(self, host: Host, *,
                 main_window_viewmodel: "MainWindowViewModel",
                 text_editor_viewmodel: "TextEditorViewModel",
                 chord_sheet_viewmodel: Optional["ChordSheetViewModel"] = None,
                 detection_delay_s: float = CHORD_DETECTION_DEBOUNCE_MS / 1000,
                 audio_failure_policy: Optional[AudioFailurePolicy] = None,
                 worker: Optional[BackgroundWorker] = None,
                 services: Optional["CoreServices"] = None,
                 platform: str = DESKTOP) -> None:
        """Create the session. Nothing is delivered or scheduled until used.

        Args:
            host: Runs the session's callbacks and timers on the session thread.
            main_window_viewmodel: Keeps the document text, its modified flag,
                the open document and the notation preference (until those
                move here), does the document I/O through its store (which
                the session's recent list uses too), and runs playback.
            text_editor_viewmodel: The chord-detection component; only the
                session drives it.
            chord_sheet_viewmodel: The chord-sheet strip, fed the parsed song
                once the session is started and moved along by playback;
                None without a strip.
            detection_delay_s: How long typing must pause before the text is
                re-detected.
            audio_failure_policy: Decides which audio failures are reported;
                a new one (nothing reported yet) by default.
            worker: Runs the renders the user waits for (MIDI export,
                Suggest Capo) off the session thread; a new one on ``host``
                by default. Shut down with the session.
            services: The core services the viewmodels were built over
                (``session.bootstrap.create_session`` passes them). The
                dialog-scoped models (:meth:`settings_model`,
                :meth:`chord_identifier_model`), the settings commands and
                :meth:`save_config` need them; tests that don't use those
                leave them out.
            platform: ``desktop`` or ``android`` (``session.platform``):
                picks the variant of the texts that name gestures or menus,
                whether the playhead follows playback and taps
                (``TRACKS_PLAYHEAD``) and the player's short status texts.

        Raises:
            ValueError: For an unknown platform.
        """
        self._platform = check_platform(platform)
        self._android = self._platform == ANDROID
        self._host = host
        self._emitter = Emitter()
        self._main = main_window_viewmodel
        self._detector = text_editor_viewmodel
        self._chord_sheet = chord_sheet_viewmodel
        self._services = services
        self._started = False
        self._detection_delay_s = detection_delay_s

        # The session's copy of the editor text, and its revision.
        self._text = self._main.current_text
        # The text the detected lines were found in (their offsets point
        # into it; the session's copy may have moved on since).
        self._detected_text = ""
        self._revision = 0
        self._client_token = 0
        self._detect_timer: Optional[Cancellable] = None
        self._spans: Tuple[Span, ...] = ()

        # The viewmodel replaces the whole text for open and new (and for the
        # transpose, convert and capo commands the session runs through it).
        # The undo policy of the resulting edit is the running command's.
        self._edit_undo = UndoPolicy.PLAIN
        self._on_replaced = self._entry(self._on_text_replaced)
        self._main.observe("current_text", self._on_replaced)

        # Dialog-driven commands (insert directive, suggest capo, the
        # document flows).
        self._flows = FlowRunner(self._emitter.emit)

        # Renders the user waits for run here; the outcome comes back as a
        # posted callback. A newer Suggest Capo supersedes an older one.
        self._worker = worker if worker is not None else BackgroundWorker(host)
        self._capo_job: Optional[Job] = None

        # Documents: the viewmodel reads and writes them through its store;
        # the session keeps the recent list there (the flows are its only
        # writer) and publishes the title.
        self._documents = self._main.documents
        self._on_document = self._entry(self._publish_document)
        self._main.observe("current_document", self._on_document)
        self._main.observe("is_modified", self._on_document)

        # Detection follows the notation preference.
        self._detector.set_notation(self._main.notation.value)
        self._on_notation = self._entry(self._on_notation_changed)
        self._main.observe("notation", self._on_notation)

        # The toolbar mirrors the viewmodel's tempo, key, time signature and
        # metronome, whoever changed them (a command, New/Open going back to
        # the defaults, a whole-song transpose), with the song's own
        # directives on top (see _publish_toolbar).
        self._on_toolbar_input = self._entry(self._on_toolbar_value)
        for name in _TOOLBAR_INPUTS:
            self._main.observe(name, self._on_toolbar_input)

        # The chord sheet re-renders when the parsed song, the key (roman
        # numerals) or the voicing (fingerings, view gating) changes.
        self._on_song_input = self._entry(self._feed_chord_sheet)
        if self._chord_sheet is not None:
            self._detector.observe("detected_lines", self._on_song_input)
            self._main.observe("key", self._on_song_input)
            self._main.observe("voicing", self._on_song_input)

        # The editor font and the Voicing menu follow the viewmodel (the
        # Settings dialog changes them too, through apply_settings).
        self._on_editor_input = self._entry(self._publish_editor)
        self._main.observe("font_family", self._on_editor_input)
        self._main.observe("font_size", self._on_editor_input)
        self._on_voicing = self._entry(self._publish_voicing_menu)
        self._main.observe("voicing", self._on_voicing)
        # A voicing change while a song is paused: it was rendered with the
        # old one, so Play re-renders from the paused chord.
        self._voicing_stale = False
        self._voicing_locked = False
        self._on_voicing_stale = self._entry(self._on_voicing_changed)
        self._main.observe("voicing", self._on_voicing_stale)

        # The strip's own state (visibility, view, zoom, playhead) and a
        # revision that goes up with every song it rendered. What the op
        # buffer is packed from is kept as one tuple, replaced (never
        # mutated) on the session thread, so other threads can read it.
        self._sheet_revision = 0
        self._sheet_snapshot: Optional[Tuple[Any, str, float, Any]] = None
        # Whether the strip has had a playback ping since it was last cleared.
        self._sheet_pinged = False
        self._on_sheet_change = self._entry(self._publish_chord_sheet)
        self._on_sheet_song = self._entry(self._on_chord_sheet_song)
        if self._chord_sheet is not None:
            for name in _CHORD_SHEET_INPUTS:
                self._chord_sheet.observe(name, self._on_sheet_change)
            self._chord_sheet.observe("rendered_song", self._on_sheet_song)

        # The playhead: the start of the chord Play starts from (None: the
        # top). Kept on a chord across edits; on Android it also follows
        # playback and taps (TRACKS_PLAYHEAD).
        self._tracks_playhead = pick(TRACKS_PLAYHEAD, self._platform)
        self._playhead: Optional[int] = None
        # Android's status line holds the playhead's position while idle; it
        # is refreshed only while the status still shows a position.
        self._position_status = False
        # Bars of chords seen in playback pings, by chord start, for the
        # idle position when the strip hasn't rendered (same text revision).
        self._ping_bars: Dict[int, Tuple[int, int]] = {}
        self._ping_bars_revision = -1
        self._playing_chord: Optional[str] = None
        # The name an untitled document takes when it is first saved.
        self._pending_name: Optional[str] = None

        # Playback: the viewmodel runs it, the session turns its transport
        # flags and progress pings into states.
        self._audio_policy = audio_failure_policy or AudioFailurePolicy()
        self._playback = PlaybackState(self._playback_status())
        # The tempo of the chord sounding (directives applied); None when
        # idle and before the first chord.
        self._effective_bpm: Optional[int] = None
        self._on_transport = self._entry(self._on_transport_changed)
        self._on_progress = self._entry(self._on_playback_event)
        self._on_render_error = self._entry(self._on_playback_error)
        self._main.observe("is_playing", self._on_transport)
        self._main.observe("is_paused", self._on_transport)
        self._main.observe("current_playback_event", self._on_progress)
        self._main.observe("playback_error", self._on_render_error)

        # The chord identifier (Android's screen; the desktop dialog keeps a
        # model of its own): created on first use, since it needs services.
        self._identifier_model: Optional["ChordIdentifierViewModel"] = None
        self._identifier_error: Optional[str] = None
        # A Settings screen's working copy (Android), while one is open.
        self._settings_edit: Optional[SettingsEdit] = None

        with self._emitter.batch():
            self._emitter.set_state(HighlightState(0, 0, ()))
            self._emitter.set_state(self._playback)
            self._emitter.set_state(StatusState(formatting.READY))
            self._publish_editor()
            self._publish_toolbar()
            self._publish_voicing_menu()
            self._publish_instrument_menu()
            self._publish_chord_sheet()
            self._publish_document()
            self._publish_recent()
            self._publish_song_defaults()
            if services is not None:
                # The screens that need the services (Android's identifier
                # and Settings).
                self._emitter.set_state(IdentifierState(
                    (), "", None, (), formatting.IDENTIFIER_PROMPT))
                self._publish_settings()
                self._emitter.set_state(INACTIVE_VOICING_EDITOR)
        if services is not None:
            # Several viewmodels write the config (the toolbar, the font,
            # Quick Start's preference), none notifies: re-read it at the
            # end of every command (an unchanged value is dropped).
            self._emitter.set_before_flush(self._publish_settings)

    # -- lifecycle ------------------------------------------------------------

    @_command
    def subscribe(self, listener: Listener) -> Cancellable:
        """Add a listener for the session's output.

        The listener first gets the current value of every state, then
        everything published after; it is only ever called on the session
        thread, between commands.

        Returns:
            A handle whose ``cancel()`` removes the listener.
        """
        return self._emitter.subscribe(listener)

    @_command
    def start(self) -> None:
        """Detect the current text, publish the result and seed the chord sheet.

        Call once the host can run timers (on desktop: after
        ``TkHost.attach``); the chord sheet is fed only from here on, because
        feeding it arms its debounce timer.
        """
        self._detect_now()
        # Started after detecting, so the strip is seeded exactly once.
        self._started = True
        self._feed_chord_sheet()

    def shutdown(self) -> None:
        """Cancel pending work and stop observing; drops every listener."""
        self._started = False
        self._cancel_detection()
        self._flows.cancel()
        # Outcomes still on their way are dropped (an export not written yet
        # is lost; the app is closing).
        self._worker.shutdown()
        self._main.unobserve("current_text", self._on_replaced)
        self._main.unobserve("current_document", self._on_document)
        self._main.unobserve("is_modified", self._on_document)
        self._main.unobserve("notation", self._on_notation)
        for name in _TOOLBAR_INPUTS:
            self._main.unobserve(name, self._on_toolbar_input)
        self._main.unobserve("font_family", self._on_editor_input)
        self._main.unobserve("font_size", self._on_editor_input)
        self._main.unobserve("voicing", self._on_voicing)
        self._main.unobserve("voicing", self._on_voicing_stale)
        if self._chord_sheet is not None:
            for name in _CHORD_SHEET_INPUTS:
                self._chord_sheet.unobserve(name, self._on_sheet_change)
            self._chord_sheet.unobserve("rendered_song", self._on_sheet_song)
        self._detector.unobserve("detected_lines", self._on_song_input)
        self._main.unobserve("key", self._on_song_input)
        self._main.unobserve("voicing", self._on_song_input)
        self._main.unobserve("is_playing", self._on_transport)
        self._main.unobserve("is_paused", self._on_transport)
        self._main.unobserve("current_playback_event", self._on_progress)
        self._main.unobserve("playback_error", self._on_render_error)
        # The session is the viewmodels' only observer; drop whatever is
        # left (the Tk chord-sheet panel observes the strip for repaints).
        self._main.clear_observers()
        if self._chord_sheet is not None:
            self._chord_sheet.clear_observers()
        self._emitter.close()

    # -- editing ----------------------------------------------------------------

    @_command
    def set_text(self, text: str, client_token: int = 0) -> None:
        """The user changed the text; re-detect once typing pauses.

        Args:
            text: The editor's whole text.
            client_token: An opaque number the view picks (e.g. its own edit
                counter); it comes back in the :class:`HighlightState` for this
                text.
        """
        if text == self._text:
            if client_token != self._client_token:
                self._client_token = client_token
                if self._detect_timer is None:
                    # The spans are current; re-send them under the new token.
                    self._emitter.set_state(
                        HighlightState(self._revision, client_token, self._spans))
            return
        self._replace_mirror(text, client_token)
        self._arm_detection()

    @_command
    def insert_text(self, at: int, text: str) -> None:
        """Insert ``text`` at offset ``at`` and re-detect immediately.

        For inserts that don't come from typing (the chord identifier). The
        views get it as a plain :class:`TextEdited` with the cursor after the
        inserted text. Refused (logged, nothing changes) while a song plays
        or is paused, like every programmatic edit.

        Raises:
            ValueError: If ``at`` is outside the text.
        """
        if not 0 <= at <= len(self._text):
            raise ValueError(f"insert offset {at} outside the text (length {len(self._text)})")
        if not self._edits_allowed("insert"):
            return
        self._splice(at, at, text)

    @_command
    def insert_chord(self, at: int, chord: str) -> None:
        """Insert ``chord`` and a space at offset ``at`` (the chord identifier).

        Like :meth:`insert_text`, and says "Inserted chord: X" in the status
        line when it went in (refused while a song plays or is paused).

        Raises:
            ValueError: If ``at`` is outside the text.
        """
        if not 0 <= at <= len(self._text):
            raise ValueError(f"insert offset {at} outside the text (length {len(self._text)})")
        if not self._edits_allowed("insert chord"):
            return
        self._splice(at, at, chord + " ")
        self._set_status(formatting.inserted_chord_status(chord))

    @_command
    def transpose(self, semitones: int, selection: Selection = None) -> None:
        """Transpose the chords (and key directives) by ``semitones``.

        One undo step in the views. A whole-song transpose also shifts the
        toolbar key, so roman numerals keep sounding the same.

        Args:
            semitones: Positive is up; 0 does nothing.
            selection: ``(start, end)`` to transpose only the chords that
                overlap it; None (or an empty range) for the whole song.

        Raises:
            ValueError: If the selection is outside the text.
        """
        if semitones == 0 or not self._edits_allowed("transpose"):
            return
        region = self._region(selection)
        with self._undo_policy(UndoPolicy.GROUP):
            self._main.transpose(semitones, region)
        self._set_status(formatting.transposed_status(semitones, region is not None))

    @_command
    def convert_notation(self, target: str) -> None:
        """Rewrite the chords in ``target`` notation and switch detection to it.

        When the text has no chords in the other notation nothing changes
        (text, notation, modified flag) and the status says so.

        Args:
            target: ``american`` or ``european``.

        Raises:
            ValueError: For any other notation.
        """
        notation = Notation(target)
        if not self._edits_allowed("convert"):
            return
        source = Notation.EUROPEAN if notation is Notation.AMERICAN else Notation.AMERICAN
        # The detector's lines can be reused when they are of the current
        # text in the source notation; otherwise the converter parses.
        lines = None
        if self._detect_timer is None and self._detector.current_notation == source.value:
            lines = self._detector.detected_lines or None
        if notation is Notation.AMERICAN:
            converted = self._main.convert_text_to_american(lines)
        else:
            converted = self._main.convert_text_to_european(lines)
        if converted:
            self._set_status(formatting.converted_status(notation.value))
        else:
            # Nothing in the source notation (e.g. Android's Convert on a
            # solfège song with the AB switch on): say so, change nothing.
            self._set_status(formatting.nothing_to_convert_status(source.value))

    @_command
    def request_insert_directive(self, kind: str, at: int) -> None:
        """Ask the view for a directive's fields, then insert it at ``at``.

        Emits :class:`InsertDirectiveRequest`; ``respond`` with the fields
        inserts the directive (and a space) as a plain edit, or emits a
        :class:`UserError` if they don't validate. Refused at answer time
        while a song plays.

        Args:
            kind: ``bpm``, ``time``, ``key``, ``label``, ``loop`` or ``capo``.
            at: Where to insert (the cursor), in code points.

        Raises:
            ValueError: For an unknown kind, or ``at`` outside the text.
        """
        kind = directives.DirectiveKind(kind).value
        if not 0 <= at <= len(self._text):
            raise ValueError(f"insert offset {at} outside the text (length {len(self._text)})")
        self._flows.start(self._insert_directive_flow(kind, at))

    @_command
    def write_song_defaults(self) -> None:
        """Write the starting values the song doesn't set into its top.

        Inserts the missing ``{bpm}``, ``{time}`` and ``{key}`` directives
        (:class:`SongDefaultsState`'s values; no key directive without a key)
        as one line at the top, one undo step, highlighted at once. Refused
        while a song plays or is paused.
        """
        if not self._edits_allowed("write song defaults"):
            return
        state = self._song_defaults()
        missing = song_defaults.missing_directives(state)
        if not missing:
            self._set_status(formatting.NOTHING_TO_WRITE_STATUS)
            return
        text = " ".join(missing)
        self._splice(0, 0, text + "\n", UndoPolicy.GROUP)
        self._set_status(formatting.inserted_status(text))

    @_command
    def request_suggest_capo(self, selection: Selection = None) -> None:
        """Ask which voicing to optimize for, then insert the best ``{capo: N}``.

        Emits :class:`CapoChoiceRequest`; ``respond`` with a voicing scores
        the selection (or the whole song) on the background worker ("Finding
        a capo..." meanwhile), then inserts the directive at the start of the
        selection's line (the top without one) as one undo step, or says in
        the status line that no capo helps. Refused at answer time, and when
        the result arrives, while a song plays. If the text changed while it
        was being scored the result is dropped (the status says so) rather
        than inserted into a song it wasn't computed for; the user can ask
        again.

        Args:
            selection: ``(start, end)`` to score only the chords that overlap
                it; None (or an empty range) for the whole song.

        Raises:
            ValueError: If the selection is outside the text.
        """
        self._flows.start(self._suggest_capo_flow(self._region(selection)))

    @_command
    def respond(self, request_id: int, value: object) -> None:
        """Answer a request the session emitted.

        Args:
            request_id: The request's ``request_id``.
            value: The answer (see each request type); None cancels.
                Answers to a request that is no longer pending are ignored.
        """
        self._flows.respond(request_id, value)

    @_command
    def restore_draft(self, text: str, document: Optional[DocumentRef], modified: bool) -> None:
        """Put back the editor a killed process had (Android draft restore).

        The text replaces the session's as a ``reset`` edit (a fresh undo
        history), ``document`` becomes the open document without being
        read (its saved content may differ from the draft) and the modified
        flag is set as given. A pending request is dropped. Refused while a
        song plays, like every programmatic edit.

        Args:
            text: The draft text.
            document: The document it belongs to, or None for a new one.
            modified: Whether the draft has unsaved changes.

        Raises:
            TypeError: If ``document`` isn't a DocumentRef or None.
        """
        document = self._as_ref(document)
        if not self._edits_allowed("restore draft"):
            return
        self._flows.cancel()
        self._pending_name = None
        revision = self._revision
        with self._undo_policy(UndoPolicy.RESET):
            self._main.restore_document(str(text), document, bool(modified))
        if self._revision == revision:
            # Same text as the session's: still a new undo history in the views.
            self._splice(0, len(self._text), self._text, UndoPolicy.RESET)

    @_command
    def report_unexpected(self, message: str, context: Optional[str] = None) -> None:
        """Emit an :class:`UnexpectedError` (for hosts whose error handler
        reports through the session, and for the bridge's own failures)."""
        self._emitter.emit(UnexpectedError(str(message), context))

    @_command
    def save_config(self) -> None:
        """Write the settings to disk now (Android: when the app leaves the
        screen, as the process may be killed afterwards).

        Raises:
            RuntimeError: If the session was built without services.
            ConfigurationError: If the config can't be written.
        """
        self._require_services("saving the config").config.save_config()

    @_command
    def suspend_audio(self) -> None:
        """Release the audio output (Android: the app left the screen).

        Does nothing while a song is playing or rendering. The next play,
        tap or audition reopens the output lazily.
        """
        released = self._require_services("suspending the audio").playback.suspend_audio()
        logger.info("Audio output suspended" if released else "Audio output left open")

    @_command
    def resume_audio(self) -> None:
        """Reopen the audio output released by :meth:`suspend_audio`.

        A failure isn't reported here; the next play reports it.
        """
        reopened = self._require_services("resuming the audio").playback.resume_audio()
        if not reopened:
            logger.warning("The audio output could not be reopened")

    # -- documents ----------------------------------------------------------------
    #
    # Each command is a flow (see session.flows): the unsaved-changes question
    # is a ConfirmDiscardRequest, file pickers are PickDocumentRequests the
    # view answers with a DocumentRef. Send the editor's text with set_text
    # first, so the modified flag and what gets saved are current. Starting
    # one while another flow waits for an answer closes that one.

    @_command
    def new_document(self) -> None:
        """Start a new, empty document.

        Asks about unsaved changes first. The text is cleared with a plain
        edit (Undo brings the old text back, as it always has).
        """
        self._flows.start(self._new_flow())

    @_command
    def open_document(self, ref: Optional[DocumentRef] = None) -> None:
        """Open a document: ``ref``, or one the user picks.

        Asks about unsaved changes first, then (without ``ref``) emits a
        :class:`PickDocumentRequest` in ``open`` mode. The opened text
        replaces the editor's with a ``reset`` edit (the undo history starts
        over) and its first tempo, key and time-signature directives set the
        toolbar. A failure is a :class:`UserError`.

        Raises:
            TypeError: If ``ref`` isn't a DocumentRef.
        """
        self._flows.start(self._open_flow(self._as_ref(ref)))

    @_command
    def open_recent(self, ref: DocumentRef) -> None:
        """Open an entry of :class:`RecentDocumentsState` (like :meth:`open_document`).

        Raises:
            TypeError: If ``ref`` isn't a DocumentRef.
        """
        ref = self._as_ref(ref)
        if ref is None:
            raise TypeError("open_recent needs a DocumentRef")
        self._flows.start(self._open_flow(ref))

    @_command
    def save(self) -> None:
        """Save the document; one that was never saved asks for a name first."""
        self._flows.start(self._as_flow(self._save_flow()))

    @_command
    def save_as(self, name: Optional[str] = None) -> None:
        """Save the document under a name the user picks (it becomes the open document).

        Args:
            name: The name to suggest instead of the document's, as typed
                (without the extension; the document's, or ``.txt``, is
                added): Android's way out of a :class:`RenameFailed`.

        Raises:
            ValueError: If ``name`` isn't a valid document name.
        """
        suggested = None
        if name is not None:
            problem = self._name_problem(name)
            if problem is not None:
                raise ValueError(problem)
            suggested = self._with_extension(name)
        self._flows.start(self._as_flow(self._save_as_flow(suggested)))

    @_command
    def rename_document(self, name: str) -> None:
        """Rename the open document to ``name`` (the title's Rename dialog).

        ``name`` is typed without the extension; the document's own is kept
        (``.txt`` for an untitled one), and a name that already ends with it
        isn't doubled. The document is renamed where it is
        (``DocumentStore.rename``); it stays open under the new ref, the
        recent list and :class:`DocumentState` follow and the status says
        "Renamed to X". An untitled document only takes the name: Save
        suggests it, and the title shows it. A name that isn't valid, or a
        storage that refuses (a name in use, no rename support), emits
        :class:`RenameFailed`; nothing changes then.
        """
        name = str(name)
        problem = self._name_problem(name)
        if problem is not None:
            self._emitter.emit(RenameFailed(name, problem, False))
            return
        display_name = self._with_extension(name)
        current = self._main.current_document
        if current is None:
            self._pending_name = display_name
            self._publish_document()
            self._set_status(formatting.renamed_status(display_name))
            return
        if display_name == current.display_name:
            return
        try:
            renamed = self._documents.rename(current, display_name)
        except RenameNotSupported as e:
            logger.info("Rename refused by the storage: %s", e)
            self._emitter.emit(RenameFailed(name, str(e), True))
            return
        except FileOperationError as e:
            logger.warning("Rename failed: %s", e)
            self._emitter.emit(RenameFailed(name, str(e), True))
            return
        self._main.document_renamed(renamed)
        self._remember(renamed)
        self._set_status(formatting.renamed_status(renamed.display_name))

    @_command
    def export_midi(self) -> None:
        """Render the song and write it as a MIDI file the user picks.

        Suggests ``<document name>.mid``. The song as it is when the user
        picks the file is rendered on the background worker ("Exporting
        MIDI: ..." meanwhile) and written when the render arrives. Exports
        don't join the recent list and don't change the open document. A
        failure (no chords, a render or write error) is a :class:`UserError`.
        """
        self._flows.start(self._export_flow())

    @_command
    def request_close(self) -> None:
        """The user wants to quit: asks about unsaved changes, then emits
        :class:`CloseApproved` unless they cancelled (or a save failed)."""
        self._flows.start(self._close_flow())

    # -- playback ---------------------------------------------------------------

    @_command
    def play_pause(self, from_offset: Optional[int] = None) -> None:
        """The Play/Pause button: start, pause or resume.

        Args:
            from_offset: When idle, start at the first chord ending after this
                code-point offset (the cursor) instead of at the playhead
                (``PlaybackState.playhead_offset``), or at the top without
                one. Ignored while playing or paused.
        """
        status = self._playback_status()
        if status is PlaybackStatus.PLAYING:
            logger.info("Pausing playback")
            self._main.pause_playback()
            self._set_paused_status()
        elif status is PlaybackStatus.PAUSED and self._voicing_stale:
            # The paused song was rendered with the old voicing: start again
            # from the chord it stopped on, rendered with the new one.
            span = self._playback.playing_span
            from_offset = span.start if span is not None else self._playhead
            logger.info("Resuming playback re-rendered (the voicing changed while paused)")
            self._main.stop_playback()
            self._start_playback(from_offset)
        elif status is PlaybackStatus.PAUSED:
            logger.info("Resuming playback")
            self._main.resume_playback()
            if self._android and self._playing_chord is not None:
                self._set_status(formatting.position_status(
                    self._playback.bar, self._playback.total_bars,
                    formatting.playing_activity(self._playing_chord)))
            else:
                self._set_status(formatting.RESUMED)
        else:
            if from_offset is None and self._playhead is not None:
                from_offset = self._playhead
            self._start_playback(from_offset)

    @_command
    def stop(self) -> None:
        """Stop playback (also silences notes still ringing when idle).

        The playhead stays where it is (on the chord that was sounding when
        it follows playback).
        """
        self._main.stop_playback()
        if self._android:
            self._set_idle_status()
        else:
            self._set_status(formatting.STOPPED)

    @_command
    def rewind(self) -> None:
        """The player's ⏮: stop if a song plays or is paused, and put the
        playhead on the first chord (no playhead without chords)."""
        if self._playback_status() is not PlaybackStatus.IDLE:
            logger.info("Rewinding: stopping playback")
            self._main.stop_playback()
        chord = first_chord(self._detector.detected_lines)
        self._move_playhead(chord.start if chord is not None else None)
        self._set_idle_status()

    @_command
    def set_playhead(self, offset: int) -> None:
        """Put the playhead on the chord a tap at ``offset`` means.

        The chord covering ``offset``, else the nearest one on its line,
        else on the nearest line with chords (``highlighting.nearest_chord``).
        Silent. While paused, the paused song is dropped (stopped), so Play
        starts at the new playhead; while playing, playback jumps there
        (it restarts from that chord). Nothing happens without chords.

        Args:
            offset: A code-point offset into the text (clamped to it).
        """
        chord = nearest_chord(self._detector.detected_lines, self._text, offset)
        if chord is None:
            return
        self._seek(chord.start)

    @_command
    def pause(self) -> None:
        """Pause if a song is playing; otherwise do nothing.

        For interruptions rather than the Play/Pause button (Android: audio
        focus lost, headphones unplugged, the app left the screen), which
        must never start or resume playback.
        """
        if self._playback_status() is PlaybackStatus.PLAYING:
            logger.info("Pausing playback (interrupted)")
            self._main.pause_playback()
            self._set_paused_status()

    @_command
    def tap_chord_at(self, offset: int) -> None:
        """Play the chord under ``offset`` once, if there is a valid one.

        Works while a song plays too. If audio can't start, the first tap in
        a session emits :class:`AudioUnavailable`; later ones only log.

        Where the playhead follows taps (Android) the tapped chord also
        becomes the playhead, like :meth:`set_playhead`: idle or paused it
        moves there (a paused song is dropped) and the chord sounds; while a
        song plays, playback jumps there instead of sounding the chord over
        it.
        """
        chord = chord_at(self._detector.detected_lines, offset)
        if chord is None or not chord.is_valid:
            return
        if self._tracks_playhead:
            if self._playback_status() is PlaybackStatus.PLAYING:
                self._seek(chord.start)
                return
            self._seek(chord.start)
        try:
            self._main.on_chord_clicked(chord)
        except AudioInitializationError as e:
            self._set_status(formatting.AUDIO_UNAVAILABLE_STATUS)
            self._report_audio_failure(str(e), from_click=True)
            return
        if self._android:
            self._set_idle_status()
        else:
            self._set_status(formatting.tapped_chord_status(chord.chord))

    @_command
    def report_audio_failure(self, reason: str, from_click: bool = True) -> None:
        """Report audio that failed to start for something played outside the session.

        For the click-to-hear sources whose audio a dialog-scoped viewmodel
        plays (the chord identifier). The failure goes through the session's
        reporting policy like a chord tap: emits :class:`AudioUnavailable` the
        first time in a session, later ones are only logged.

        Args:
            reason: Why, usually the ``AudioInitializationError`` text.
            from_click: True for click-to-hear actions.
        """
        self._report_audio_failure(reason, from_click)

    # -- chord identifier ---------------------------------------------------------
    #
    # The identifier's notes and candidates are an IdentifierState. Inserting
    # a candidate is insert_chord. Audio that can't start is reported by the
    # click-to-hear policy, like a chord tap.

    @_command
    def identifier_toggle_note(self, note: str, octave: int) -> None:
        """Select or deselect a piano key; a key that became selected sounds.

        Args:
            note: A note name (``C``, ``C#``, ``Db``...).
            octave: Its octave (C4 is middle C).

        Raises:
            ValueError: For something that isn't a note, or a note outside MIDI.
        """
        octave = int(octave)
        name = self._identifier_note(note, octave)
        model = self._identifier()
        selecting = (name, octave) not in model.selected_notes
        model.toggle_note(name, octave)
        self._identifier_error = None
        self._publish_identifier()
        if selecting:
            self._play_identifier_note(name, octave)

    @_command
    def identifier_set_notes_text(self, text: str) -> None:
        """The typed-notes field changed: select the notes it names.

        Parsed forgivingly (``"C E G"``, ``"C4, E4, G4"``; octave 4 when left
        out); what isn't a note is skipped and named in
        ``IdentifierState.typed_text_error``. Nothing sounds.
        """
        from viewmodels.chord_identifier_viewmodel import parse_notes, spelling_preference

        notes, not_understood = parse_notes(str(text))
        self._identifier().set_notes(notes, spelling_preference(str(text)))
        self._identifier_error = (formatting.identifier_not_notes(not_understood)
                                  if not_understood else None)
        self._publish_identifier()

    @_command
    def identifier_clear(self) -> None:
        """Deselect every note (the Clear button; also a fresh identifier)."""
        if self._identifier_model is not None:
            self._identifier_model.clear_selection()
        self._identifier_error = None
        self._publish_identifier()

    @_command
    def play_note(self, note: str, octave: int) -> None:
        """Sound one note without selecting it (right-click, long-press).

        Raises:
            ValueError: For something that isn't a note, or a note outside MIDI.
        """
        octave = int(octave)
        name = self._identifier_note(note, octave)
        self._play_identifier_note(name, octave)

    @_command
    def play_identified_chord(self, chord: str) -> None:
        """Sound a chord by name (a candidate the user tapped).

        A chord whose notes can't be worked out is a :class:`UserError`.
        """
        try:
            self._identifier().play_chord(str(chord), duration=2.0)
        except AudioInitializationError as e:
            self._report_audio_failure(str(e), from_click=True)
        except ChordNotepadError as e:
            self._emitter.emit(UserError(formatting.IDENTIFIER_TITLE, str(e)))

    # -- toolbar ----------------------------------------------------------------

    @_command
    def set_notation(self, notation: str) -> None:
        """Detect chords in ``notation`` from now on (the text is not rewritten).

        The toolbar key is respelled in the new notation and the key list
        swapped; the text is re-detected at once.

        Args:
            notation: ``american`` or ``european``.

        Raises:
            ValueError: For any other notation.
        """
        self._main.set_notation(Notation(notation))

    @_command
    def set_bpm(self, bpm: float) -> None:
        """Set the current document's tempo (not the default in Settings).

        Ignored while a song plays or is paused, and when the song sets its
        starting tempo with a directive (``ToolbarState.bpm_set_by``). The
        value is clamped to 20-400 and snapped like the toolbar's tempo
        control (``toolbar.BPM_SCALE``). New and Open go back to the default.
        """
        if self._playback_status() is not PlaybackStatus.IDLE:
            logger.info("Ignoring a tempo change while a song is playing")
            return
        if self._setting_directives().tempo is not None:
            logger.info("Ignoring a tempo change: the song sets its tempo")
            return
        self._main.set_bpm(toolbar.normalize_bpm(bpm))

    @_command
    def set_multiplier_pct(self, pct: float) -> None:
        """Set the speed multiplier, in percent (100 = as written).

        Applies during playback too. The value is clamped to 12.5-400
        (``toolbar.MULTIPLIER_SCALE``) and otherwise played as given.
        """
        self._main.set_bpm_multiplier(toolbar.MULTIPLIER_SCALE.normalize(pct) / 100.0)

    @_command
    def set_bpm_text(self, text: str) -> None:
        """Set the base tempo from typed text; bad input is ignored.

        Parsed like the desktop scrubber (``toolbar.parse_bpm``), then
        behaves like :meth:`set_bpm`.
        """
        try:
            bpm = toolbar.parse_bpm(text)
        except (ValueError, TypeError, OverflowError):
            logger.info("Ignoring an unreadable tempo: %r", text)
            return
        self.set_bpm(bpm)

    @_command
    def set_multiplier_text(self, text: str) -> None:
        """Set the speed multiplier from typed text ("150", "150%", "1.5x");
        bad input is ignored. Otherwise like :meth:`set_multiplier_pct`."""
        try:
            pct = toolbar.parse_multiplier_pct(text)
        except (ValueError, TypeError, OverflowError):
            logger.info("Ignoring an unreadable speed: %r", text)
            return
        self.set_multiplier_pct(pct)

    @_command
    def reset_bpm(self) -> None:
        """Reset the tempo to its default (the scrubber's middle-click);
        ignored while a song plays or is paused, like :meth:`set_bpm`."""
        self.set_bpm(toolbar.BPM_SCALE.default)

    @_command
    def reset_multiplier(self) -> None:
        """Reset the speed multiplier to its default (100%)."""
        self.set_multiplier_pct(toolbar.MULTIPLIER_SCALE.default)

    @_command
    def set_key(self, key: Optional[str]) -> None:
        """Set the current document's key, which roman numerals resolve in
        (None or empty: no key). Not the default in Settings; ignored when
        the song sets its starting key (``ToolbarState.key_set_by``)."""
        if self._setting_directives().key is not None:
            logger.info("Ignoring a key change: the song sets its key")
            return
        self._main.set_key(key or None)

    @_command
    def set_time_signature(self, beats: int, unit: int) -> None:
        """Set the current document's time signature (not the default in
        Settings); invalid values are logged and ignored, and so is any
        change when the song sets its time signature
        (``ToolbarState.time_set_by``).

        Args:
            beats: Beats per bar, 1-16.
            unit: The beat unit: 1, 2, 4, 8 or 16.
        """
        if self._setting_directives().time is not None:
            logger.info("Ignoring a time-signature change: the song sets it")
            return
        self._main.set_time_signature(int(beats), int(unit))

    @_command
    def toggle_metronome(self) -> None:
        """Turn the click track on or off."""
        self._main.toggle_metronome()

    # -- playback menu, fonts, settings -------------------------------------------

    @_command
    def set_voicing(self, voicing: str) -> None:
        """Voice chords with ``voicing`` (a value from :class:`VoicingMenuState`).

        Choosing the voicing in use again re-applies it (the chord sheet
        re-renders).

        Raises:
            ValueError: If it isn't one of the menu's values.
        """
        values = {item.value for group in self._voicing_groups() for item in group}
        if voicing not in values:
            raise ValueError(f"unknown voicing {voicing!r}")
        if self._playback_status() is PlaybackStatus.PLAYING:
            # The song is pre-rendered with the voicing it started with.
            logger.info("Not changing the voicing while a song plays")
            self._set_status(formatting.VOICING_LOCKED_REASON)
            return
        self._main.set_voicing(voicing)

    @_command
    def set_instrument(self, program: int) -> None:
        """Play with General MIDI ``program`` (0-127).

        Raises:
            ValueError: For a program outside 0-127.
        """
        program = int(program)
        if not 0 <= program <= 127:
            raise ValueError(f"MIDI program {program} outside 0-127")
        self._main.set_instrument(program)
        self._publish_instrument_menu()

    @_command
    def set_font(self, family: str, size: int) -> None:
        """Set the editor font (a size outside 6-72 is logged and ignored)."""
        self._main.set_font_family(family)
        self._main.set_font_size(int(size))

    @_command
    def step_font_size(self, delta: int) -> None:
        """Grow (positive) or shrink the editor font, within 6-72 points."""
        size = self._main.font_size + int(delta)
        self._main.set_font_size(max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size)))

    @_command
    def reset_font_size(self) -> None:
        """Put the editor font back to its default size."""
        self._main.reset_font_size()

    @_command
    def apply_settings(self, changes: "SettingsChanges | SettingsValues") -> None:
        """Bring the running app in line with new settings.

        Desktop: the Settings dialog writes the config itself
        (``SettingsViewModel.commit``) and hands over what changed. Bridge
        views send a whole :class:`SettingsValues` instead (start from
        :meth:`settings_values`); the session checks it and commits it
        through a ``SettingsViewModel``, so the config writes are the same.

        Then a new font is applied, the Voicing menu is rebuilt from the
        edited registry, and the voicing in use is re-applied when it was
        renamed or removed (the new value) or may have been edited in place
        (a user voicing). ``general_changed`` and ``audio_changed`` are
        ignored, as they always were: those settings are defaults for the
        next start (the dialog says so where it matters).

        Args:
            changes: What :meth:`SettingsViewModel.commit` reported, or the
                new values.

        Raises:
            ValueError: If a :class:`SettingsValues` is out of range
                (nothing is written then).
        """
        if isinstance(changes, SettingsValues):
            changes = self._commit_settings(changes)
        self._apply_changes(changes)

    def _apply_changes(self, changes: "SettingsChanges") -> None:
        """Bring the app in line with committed settings (see :meth:`apply_settings`)."""
        if changes.font_changed:
            self._main.reload_font_settings()
        if changes.voicings_changed:
            self._publish_voicing_menu()
        if changes.new_active_voicing is not None:
            self._main.set_voicing(changes.new_active_voicing)
        elif changes.voicings_changed and self._main.get_voicing().startswith("voicing:"):
            # Possibly edited in place: rebuild the picker from the new values.
            self._main.set_voicing(self._main.get_voicing())

    # -- the Settings screen (bridge views) ---------------------------------------
    #
    # Android's Settings screen edits a working copy the session keeps, like
    # the desktop dialog's SettingsViewModel: begin_settings_edit opens it,
    # the voicing commands edit it (VoicingEditorState shows it), and
    # save_settings validates every voicing, commits and applies, or
    # cancel_settings_edit drops it. SettingsState carries the plain values.

    @_command
    def begin_settings_edit(self) -> None:
        """Open a settings working copy (dropping one already open).

        Raises:
            RuntimeError: If the session was built without services.
        """
        self._settings_edit = SettingsEdit(self.settings_model())
        self._publish_voicing_editor()

    @_command
    def cancel_settings_edit(self) -> None:
        """Drop the working copy; nothing is written."""
        self._settings_edit = None
        self._emitter.set_state(INACTIVE_VOICING_EDITOR)

    @_command
    def save_settings(self, values: Optional[SettingsValues] = None) -> None:
        """Save the working copy: the voicings, plus ``values`` if given.

        Like the desktop dialog's Save: if a voicing is invalid, a
        :class:`UserError` names the first one, it is selected, and the edit
        stays open. Otherwise everything is committed (one config write) and
        applied like :meth:`apply_settings`, and the edit ends
        (``VoicingEditorState.active`` goes False). A config that can't be
        written is a :class:`UserError` and the edit stays open.

        Args:
            values: The General/Playback settings; None keeps them as the
                config has them now.

        Raises:
            RuntimeError: If no settings edit is open.
            ValueError: If ``values`` are out of range (nothing is written).
        """
        edit = self._require_settings_edit()
        if values is None:
            values = SettingsValues.read(self._require_services("settings").config.config)
        values.check()
        for name, value in values.as_dict().items():
            setattr(edit.model, name, value)
        problem = edit.first_invalid()
        if problem is not None:
            name, message = problem
            edit.select(name)
            edit.bump()
            self._emitter.emit(UserError(formatting.INVALID_VOICING_TITLE, f"{name}: {message}"))
            self._publish_voicing_editor()
            return
        try:
            changes = edit.model.commit()
        except ConfigurationError as e:
            logger.error(f"Could not save settings: {e}")
            self._emitter.emit(UserError(formatting.SETTINGS_TITLE,
                                         formatting.settings_save_failed(str(e))))
            return
        self._settings_edit = None
        self._emitter.set_state(INACTIVE_VOICING_EDITOR)
        self._apply_changes(changes)

    @_command
    def check_directive(self, kind: str, fields: Any, request_id: int) -> None:
        """Check an Insert dialog's fields as the user types (:class:`DirectiveCheck`).

        Uses the same check as the final insert, with the pending request's
        labels and notation.
        """
        request = self.pending_request
        if (request is None or request.request_id != request_id
                or not isinstance(request, InsertDirectiveRequest) or request.kind != kind):
            return
        values = {str(k): str(v) for k, v in fields.items()} if isinstance(fields, dict) else {}
        problem = directives.check_directive(
            kind, values, existing_labels=request.existing_labels, notation=request.notation)
        errors = {problem.field: problem.message} if problem and problem.field else {}
        form_error = problem.message if problem and not problem.field else ""
        self._emitter.emit(DirectiveCheck(kind, request_id, values, errors, form_error))

    def directive_hint_at(self, offset: int) -> DirectiveHint:
        """The directive at ``offset`` (or being typed there) with its syntax
        hint and, when invalid, the reason; ``syntax`` is "" when there is no
        directive there. For a tooltip while typing."""
        hint = directive_hint(self._text, offset)
        return hint or DirectiveHint(offset, offset, offset, "", "", "")

    @_command
    def request_directive_hint(self, offset: int) -> None:
        """Emit :meth:`directive_hint_at` for ``offset`` (a bridge view's way
        to ask; the reply is a :class:`DirectiveHint` event)."""
        self._emitter.emit(self.directive_hint_at(offset))

    @_command
    def request_voicing_editor_schema(self) -> None:
        """Emit the voicings editor's form schemas (:class:`VoicingEditorSchema`)."""
        from settings_forms.voicing_form import SCHEMA_VERSION, editor_schema

        self._emitter.emit(VoicingEditorSchema(SCHEMA_VERSION, editor_schema(self._platform)))

    @_command
    def select_voicing(self, name: str) -> None:
        """Show voicing ``name`` in the form.

        Raises:
            RuntimeError: If no settings edit is open.
            ValueError: If there is no such voicing.
        """
        self._edit_voicings(lambda edit: edit.select(name))

    @_command
    def add_voicing(self) -> None:
        """Add a voicing (a guitar fretboard, named "New voicing", "New voicing 2"...)
        and select it."""
        self._edit_voicings(lambda edit: edit.add())

    @_command
    def remove_voicing(self, name: str) -> None:
        """Remove a voicing from the working copy (the view asks first)."""
        self._edit_voicings(lambda edit: edit.remove(name))

    @_command
    def rename_voicing(self, old: str, new: str) -> None:
        """Rename a voicing; an empty or taken name is a :class:`UserError`
        and nothing changes (the state's ``revision`` still goes up)."""
        def rename(edit: SettingsEdit) -> None:
            try:
                edit.rename(old, new)
            except ValueError as e:
                from settings_forms.voicing_texts import EDITOR_TEXTS

                self._emitter.emit(UserError(EDITOR_TEXTS["rename_error_title"], str(e)))

        self._edit_voicings(rename)

    @_command
    def set_voicing_values(self, values: Any) -> None:
        """The form changed: ``values`` are the changed fields (or all of them).

        Merged into the form's values and parsed forgivingly into the
        voicing; the state comes back with the field and form errors.

        Raises:
            RuntimeError: If no settings edit is open or nothing is selected.
            TypeError: If ``values`` isn't an object.
        """
        self._edit_voicings(lambda edit: edit.set_values(values))

    @_command
    def set_voicing_model(self, model: str) -> None:
        """Switch the selected voicing to ``model`` with its defaults (the view
        confirms first when ``dirty``)."""
        self._edit_voicings(lambda edit: edit.set_model(model))

    @_command
    def add_voicing_record(self, field_id: str = "voices") -> None:
        """Add a row to a records field of the form (an ensemble voice)."""
        self._edit_voicings(lambda edit: edit.add_record(field_id))

    @_command
    def remove_voicing_record(self, index: int, field_id: str = "voices") -> None:
        """Remove row ``index`` of a records field of the form."""
        self._edit_voicings(lambda edit: edit.remove_record(int(index), field_id))

    @_command
    def load_voicing_preset(self, group: str, label: str) -> None:
        """Replace the selected voicing's parameters with a "Load config" entry
        (a ``VoicingEditorState.presets`` item; the view confirms first)."""
        self._edit_voicings(lambda edit: edit.load_preset(group, label))

    # -- Quick Start ----------------------------------------------------------------

    @_command
    def request_quick_start(self) -> None:
        """Emit the Quick Start tour for this platform (:class:`QuickStartContent`).

        Raises:
            RuntimeError: If the session was built without services.
        """
        parser = self._require_services("Quick Start").song_parser
        pages = []
        for page in quick_start.pages(self._platform):
            blocks = []
            for block in page["blocks"]:
                kind = block[0]
                if kind == "snippet":
                    text, notation = block[1], block[2]
                    lines = parser.detect_chords_in_text(text, notation)
                    blocks.append(QuickStartBlock("snippet", text, notation,
                                                  compute_spans(lines, text), None))
                elif kind == "image":
                    blocks.append(QuickStartBlock("image", "", None, (), block[1]))
                else:
                    blocks.append(QuickStartBlock("text", block[1], None, (), None))
            pages.append(QuickStartPage(page["title"], tuple(blocks)))
        self._emitter.emit(QuickStartContent(tuple(pages), self.show_quick_start_on_startup))

    # -- chord sheet ------------------------------------------------------------

    @_command
    def set_chord_sheet_visible(self, visible: bool) -> None:
        """Show or hide the chord sheet (it renders only while shown)."""
        if self._chord_sheet is not None:
            self._chord_sheet.set_visible(bool(visible))

    @_command
    def set_chord_sheet_height(self, px: int) -> None:
        """Remember the chord sheet's height, in pixels (desktop)."""
        if self._chord_sheet is not None:
            self._chord_sheet.set_height(int(px))
            self._publish_chord_sheet()

    @_command
    def set_chord_sheet_view(self, view_id: str) -> None:
        """Show the chord sheet as ``view_id``; an unavailable view is ignored."""
        if self._chord_sheet is not None:
            self._chord_sheet.set_active_view(view_id)

    @_command
    def chord_sheet_zoom(self, step: int) -> None:
        """Zoom the active chord-sheet view in (positive) or out (negative)
        by ``|step|`` steps at once (a pinch sends one command); ignored for
        views that don't zoom. ``step`` 0 does nothing."""
        if self._chord_sheet is None or step == 0:
            return
        self._chord_sheet.zoom_steps(int(step))

    @_command
    def audition(self, index: int) -> None:
        """Play chord ``index`` of the chord sheet's song once (click-to-hear).

        If audio can't start, the first click-to-hear failure in a session
        emits :class:`AudioUnavailable`; later ones only log.
        """
        if self._chord_sheet is None:
            return
        try:
            self._chord_sheet.audition(int(index))
        except AudioInitializationError as e:
            self._report_audio_failure(str(e), from_click=True)

    # -- desktop window preferences --------------------------------------------

    @property
    def window_geometry(self) -> str:
        """The saved main-window geometry (Tk ``WxH+X+Y``)."""
        return self._main.get_window_geometry()

    @_command
    def set_window_geometry(self, geometry: str) -> None:
        """Remember the main window's geometry for the next start."""
        self._main.set_window_geometry(str(geometry))

    @property
    def show_quick_start_on_startup(self) -> bool:
        """Whether Quick Start opens when the app starts."""
        return bool(self._main.get_show_quick_start_on_startup())

    @_command
    def set_show_quick_start_on_startup(self, show: bool) -> None:
        """Open Quick Start at startup (or not) from now on."""
        self._main.set_show_quick_start_on_startup(bool(show))

    # -- dialog-scoped models ---------------------------------------------------
    #
    # The Settings dialog and the chord identifier keep a viewmodel of their
    # own for as long as they are open (desktop). The session hands them out
    # so the window needn't reach the services; what they change comes back
    # through commands (apply_settings, insert_chord, report_audio_failure).

    def settings_model(self) -> "SettingsViewModel":
        """A new working copy of the settings for a Settings dialog.

        Commit it with ``SettingsViewModel.commit()`` and hand the changes to
        :meth:`apply_settings`.

        Raises:
            RuntimeError: If the session was built without services.
        """
        from viewmodels.settings_viewmodel import SettingsViewModel

        return SettingsViewModel(self._require_services("the Settings dialog").config)

    def chord_identifier_model(self) -> "ChordIdentifierViewModel":
        """A new model for a chord identifier window.

        Raises:
            RuntimeError: If the session was built without services.
        """
        from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel

        services = self._require_services("the chord identifier")
        return ChordIdentifierViewModel(
            song_parser_service=services.song_parser, audio_service=services.playback)

    def settings_values(self) -> SettingsValues:
        """The current settings as plain values (for :meth:`apply_settings`).

        Raises:
            RuntimeError: If the session was built without services.
        """
        return SettingsValues.read(self._require_services("settings").config.config)

    def chord_sheet_buffer(self, height: float) -> Optional[bytes]:
        """The active chord-sheet view packed as draw ops, for Android.

        Safe to call from any thread, and meant to be called off the
        session thread: it packs (10-40 ms on the emulator) the song the
        strip rendered last, in the view and zoom it shows, from a snapshot
        the session thread replaces whenever ``ChordSheetState`` changes.
        Refetch when ``song_revision``, ``active_view``, ``zoom`` or the
        height changes. Format: docs/ANDROID.md, "Chord sheet op buffer".

        Args:
            height: The strip's content height in dp (marker lane excluded).

        Returns:
            The buffer, or None without a chord sheet or a rendered song.
        """
        snapshot = self._sheet_snapshot
        if snapshot is None or snapshot[0] is None:
            return None
        from chord_sheet.pack import pack_view

        song, view_id, zoom, renderers = snapshot
        return pack_view(song, view_id, zoom, float(height), renderers=renderers)

    @property
    def has_chord_sheet(self) -> bool:
        """Whether there is a chord sheet (a ``ChordSheetState`` is published)."""
        return self._chord_sheet is not None

    @property
    def chord_sheet_model(self) -> Optional["ChordSheetViewModel"]:
        """The chord-sheet strip, for the Tk panel's painting only.

        Interim (desktop): the panel replays the strip's renderers over its
        rendered song, which are live objects, so it reads them here and
        observes the strip for repaints. Its commands go through the session.
        Android paints from draw ops sent over the bridge instead.
        """
        return self._chord_sheet

    @property
    def audio_failure_policy(self) -> AudioFailurePolicy:
        """The policy the session reports audio failures by."""
        return self._audio_policy

    # -- queries ----------------------------------------------------------------

    def document_ref(self, document_id: str) -> DocumentRef:
        """The :class:`DocumentRef` for a document the view's picker chose.

        Args:
            document_id: The store's id for it (desktop: the file's path).
        """
        return self._documents.ref_for(document_id)

    @property
    def pending_request(self) -> Optional[object]:
        """The request waiting for an answer, or None (the bridge decodes
        ``respond``'s value by its type)."""
        return self._flows.pending_request

    @property
    def text(self) -> str:
        """The session's copy of the editor text."""
        return self._text

    @property
    def text_revision(self) -> int:
        """The revision of :attr:`text`; it goes up on every change."""
        return self._revision

    def chord_at(self, offset: int) -> Optional[Span]:
        """The chord under ``offset``, from the latest detection.

        Returns:
            A ``CHORD`` or ``CHORD_INVALID`` span, or None.
        """
        chord = chord_at(self._detector.detected_lines, offset)
        if chord is None:
            return None
        kind = SpanKind.CHORD if chord.is_valid else SpanKind.CHORD_INVALID
        return Span(chord.start, chord.end, kind)

    # -- internals --------------------------------------------------------------

    def _require_services(self, what: str) -> "CoreServices":
        if self._services is None:
            raise RuntimeError(f"the session was built without services, which {what} needs")
        return self._services

    def _require_settings_edit(self) -> SettingsEdit:
        if self._settings_edit is None:
            raise RuntimeError("no settings edit is open (begin_settings_edit first)")
        return self._settings_edit

    def _edit_voicings(self, change: Callable[[SettingsEdit], Any]) -> None:
        """Run one voicings-editor command and publish the editor."""
        edit = self._require_settings_edit()
        try:
            change(edit)
        finally:
            edit.bump()
            self._publish_voicing_editor()

    def _publish_voicing_editor(self) -> None:
        if self._settings_edit is not None:
            self._emitter.set_state(self._settings_edit.state())

    def _publish_settings(self) -> None:
        if self._services is None:
            return
        self._emitter.set_state(SettingsState(
            values=SettingsValues.read(self._services.config.config),
            american_keys=toolbar.key_options("american"),
            european_keys=toolbar.key_options("european"),
            font_size_min=MIN_FONT_SIZE,
            font_size_max=MAX_FONT_SIZE,
            bpm_min=int(toolbar.BPM_SCALE.min_value),
            bpm_max=int(toolbar.BPM_SCALE.max_value),
            max_recent_files_max=MAX_RECENT_LIMIT,
            time_signature_units=TIME_SIGNATURE_UNITS,
        ))

    def _identifier(self) -> "ChordIdentifierViewModel":
        if self._identifier_model is None:
            self._identifier_model = self.chord_identifier_model()
        return self._identifier_model

    @staticmethod
    def _identifier_note(note: str, octave: int) -> str:
        """``note`` spelled as the identifier spells it, checked."""
        from viewmodels.chord_identifier_viewmodel import (
            NOTE_NAMES, normalize_note_name, note_to_midi,
        )

        name = normalize_note_name(str(note).strip())
        if name not in NOTE_NAMES:
            raise ValueError(f"not a note name: {note!r}")
        if not 0 <= note_to_midi(name, int(octave)) <= 127:
            raise ValueError(f"{name}{octave} is outside the MIDI range")
        return name

    def _play_identifier_note(self, name: str, octave: int) -> None:
        try:
            self._identifier().play_note(name, octave, duration=1.0)
        except AudioInitializationError as e:
            self._report_audio_failure(str(e), from_click=True)

    def _publish_identifier(self) -> None:
        from viewmodels.chord_identifier_viewmodel import note_to_midi

        model = self._identifier()
        notes = sorted(
            (IdentifierNote(name, octave, note_to_midi(name, octave))
             for name, octave in model.selected_notes),
            key=lambda n: n.midi)
        names = []
        for note in sorted(notes, key=lambda n: n.midi % 12):
            if note.name not in names:
                names.append(note.name)
        info = model.info_lines
        self._emitter.set_state(IdentifierState(
            notes=tuple(notes),
            notes_text=" ".join(names),
            typed_text_error=self._identifier_error,
            candidates=tuple(model.candidates),
            message="\n".join(info) if info else None,
        ))

    def _commit_settings(self, values: SettingsValues) -> "SettingsChanges":
        """Write ``values`` to the config like the Settings dialog does."""
        from viewmodels.settings_viewmodel import SettingsViewModel

        values.check()
        model = SettingsViewModel(self._require_services("applying settings").config)
        for name, value in values.as_dict().items():
            setattr(model, name, value)
        return model.commit()

    def _require_session_thread(self, name: str) -> None:
        if not self._host.is_session_thread():
            raise RuntimeError(f"AppSession.{name} must be called on the session thread")

    def _entry(self, fn: Callable[..., None]) -> Callable[..., None]:
        """Wrap a callback the session doesn't call itself (timer, observer)
        so its output is batched like a command's."""

        @functools.wraps(fn)
        def run(*args: Any) -> None:
            with self._emitter.batch():
                fn(*args)

        return run

    def _replace_mirror(self, text: str, client_token: int) -> None:
        """Take a new text: bump the revision and keep the viewmodel in step.

        The playhead moves with the text around it (re-snapped to a chord at
        the next detection).
        """
        if self._playhead is not None:
            moved = _shift_offset(self._text, text, self._playhead)
            if moved != self._playhead:
                self._playhead = moved
                self._publish_playback(self._playback)
        self._text = text
        self._revision += 1
        self._client_token = client_token
        # The main viewmodel still holds the document text (playback, save,
        # export read it) and raises the modified flag.
        self._main.on_text_changed(text)

    def _arm_detection(self) -> None:
        self._cancel_detection()
        self._detect_timer = self._host.call_later(
            self._detection_delay_s, self._entry(self._on_detection_due))

    def _cancel_detection(self) -> None:
        timer, self._detect_timer = self._detect_timer, None
        if timer is not None:
            timer.cancel()

    def _on_detection_due(self) -> None:
        self._detect_timer = None
        self._detect_now()

    def _detect_now(self, publish_toolbar: bool = True) -> None:
        """Detect the text now. The toolbar follows (the song's directives
        set its values) unless the caller publishes it itself, later."""
        self._cancel_detection()
        self._detector.on_text_changed(self._text)
        self._detected_text = self._text
        self._publish_highlight()
        self._publish_song_defaults()
        if publish_toolbar:
            self._publish_toolbar()
        self._snap_playhead()

    def _publish_highlight(self) -> None:
        self._spans = compute_spans(self._detector.detected_lines, self._text)
        self._emitter.set_state(HighlightState(self._revision, self._client_token, self._spans))

    # -- editing internals ------------------------------------------------------

    def _edits_allowed(self, what: str) -> bool:
        """Programmatic edits wait for playback to stop (the editor is locked)."""
        if self._playback_status() is PlaybackStatus.IDLE:
            return True
        logger.info("Ignoring %s while a song is playing", what)
        return False

    def _region(self, selection: Selection) -> Optional[Tuple[int, int]]:
        """A command's selection as ``(start, end)``, or None for none/empty.

        Raises:
            ValueError: If it is outside the text or reversed.
        """
        if selection is None:
            return None
        start, end = (int(x) for x in selection)
        if not 0 <= start <= end <= len(self._text):
            raise ValueError(f"selection {start}-{end} outside the text (length {len(self._text)})")
        return (start, end) if start < end else None

    @contextlib.contextmanager
    def _undo_policy(self, policy: UndoPolicy) -> Iterator[None]:
        """Give the edits the viewmodel makes meanwhile ``policy``."""
        previous, self._edit_undo = self._edit_undo, policy
        try:
            yield
        finally:
            self._edit_undo = previous

    def _splice(self, start: int, end: int, replacement: str,
                undo: UndoPolicy = UndoPolicy.PLAIN) -> None:
        """Make an edit: update the copies, tell the views, re-detect at once.

        A ``reset`` edit is delivered even if it changes nothing (a document
        with the same text was opened): the views still start a new undo
        history.
        """
        if undo is UndoPolicy.RESET:
            # Another document (or a restored draft): its playhead starts over.
            self._playhead = None
        if start != end or replacement or undo is UndoPolicy.RESET:
            old = self._text
            self._replace_mirror(old[:start] + replacement + old[end:], 0)
            self._emitter.emit(TextEdited(self._revision, start, end, replacement, undo,
                                          start + len(replacement)))
        self._detect_now()

    def _on_text_replaced(self, text: str) -> None:
        """The viewmodel replaced the document text (open, new, or a command)."""
        if text != self._text:
            self._splice(0, len(self._text), text, self._edit_undo)
        else:
            self._detect_now()

    def _labels(self) -> Tuple[str, ...]:
        """The labels in the current text (parsed afresh if detection is pending)."""
        lines = (self._detector.detected_lines if self._detect_timer is None
                 else self._detector.detect_chords(self._text))
        return directives.existing_labels(lines)

    def _insert_directive_flow(self, kind: str, at: int) -> Flow:
        """Ask for a directive's fields, check them and insert the directive."""
        notation = self._main.notation.value
        fields = yield InsertDirectiveRequest(0, kind, self._labels(), notation)
        if fields is None:
            return
        try:
            # Checked against the labels now: the text may have changed.
            text = directives.build_directive(
                kind, fields, existing_labels=self._labels(), notation=notation)
        except directives.InvalidDirective as e:
            self._emitter.emit(UserError(e.problem.title, e.problem.message))
            return
        if not self._edits_allowed("insert directive"):
            return
        # The text may have changed while the user was answering.
        at = min(at, len(self._text))
        self._splice(at, at, text + " ")
        self._set_status(formatting.inserted_status(text))

    def _suggest_capo_flow(self, region: Optional[Tuple[int, int]]) -> Flow:
        """Ask for a voicing, score capo positions on it and insert the best."""
        options = tuple(MenuItem(label, value)
                        for label, value in self._main.capo_voicing_options())
        values = [o.value for o in options]
        default = self._main.default_capo_voicing()
        if default not in values:
            default = values[0] if values else ""
        voicing = yield CapoChoiceRequest(0, options, default,
                                          formatting.capo_scope_text(region is not None))
        label = next((o.label for o in options if o.value == voicing), None)
        if voicing is None or label is None:
            return
        if not self._edits_allowed("suggest capo"):
            return
        if region is not None and region[1] > len(self._text):
            region = None  # the text changed under the selection
        job = self._main.capo_job(voicing, region)
        if job is None:
            self._set_status(formatting.no_capo_status(region is not None, label))
            return
        if self._capo_job is not None:
            self._capo_job.cancel()  # superseded: its result would be stale anyway
        self._set_status(formatting.finding_capo_status(region is not None, label))
        self._capo_job = self._worker.submit(job, self._entry(functools.partial(
            self._on_capo_scored, self._revision, region, label)))

    def _on_capo_scored(self, revision: int, region: Optional[Tuple[int, int]], label: str,
                        outcome: Outcome) -> None:
        """The worker scored the capo positions for the text at ``revision``."""
        self._capo_job = None
        if not outcome.ok:
            self._set_status(formatting.READY)
            error = outcome.error
            errors.report_from_any_thread((type(error), error, error.__traceback__),
                                          "Suggest Capo")
            return
        if not self._edits_allowed("suggest capo"):
            return
        if self._revision != revision:
            logger.info("The text changed while finding a capo; dropping the result")
            self._set_status(formatting.CAPO_STALE_STATUS)
            return
        capo = outcome.value
        if not capo:
            self._set_status(formatting.no_capo_status(region is not None, label))
            return
        with self._undo_policy(UndoPolicy.GROUP):
            self._main.insert_capo(capo, region)
        self._set_status(formatting.capo_suggested_status(capo, region is not None, label))

    # -- document internals -----------------------------------------------------

    @staticmethod
    def _name_problem(name: str) -> Optional[str]:
        """Why ``name`` can't name a document, or None if it can."""
        stripped = name.strip()
        if not stripped:
            return formatting.NAME_EMPTY
        if "/" in name or "\\" in name:
            return formatting.NAME_HAS_SEPARATOR
        if any(ord(c) < 32 or ord(c) == 127 for c in name):
            return formatting.NAME_CONTROL
        if stripped in (".", ".."):
            return formatting.NAME_RESERVED
        if len(name.encode("utf-8")) > formatting.MAX_NAME_BYTES:
            return formatting.NAME_TOO_LONG
        return None

    def _with_extension(self, name: str) -> str:
        """``name`` (stripped) with the open document's extension (``.txt``
        for a new one), unless it already ends with it."""
        name = name.strip()
        current = self._main.current_document
        source = current.display_name if current is not None else formatting.UNTITLED_FILE_NAME
        extension = os.path.splitext(source)[1]
        if extension and not name.lower().endswith(extension.lower()):
            name += extension
        return name

    @staticmethod
    def _as_ref(value: object) -> Optional[DocumentRef]:
        """A document a view handed over (a command argument or an answer)."""
        if value is None or isinstance(value, DocumentRef):
            return value
        raise TypeError(f"expected a DocumentRef or None, not {value!r}")

    @staticmethod
    def _as_flow(step: SubFlow) -> Flow:
        """Run a step that reports success as a flow of its own."""
        yield from step

    def _confirm_discard(self) -> SubFlow:
        """With unsaved changes, ask whether to save them; True to go on."""
        if not self._main.is_modified:
            return True
        answer = yield ConfirmDiscardRequest(0)
        if answer == DiscardChoice.SAVE:
            # A failed or cancelled save stops what was being done, so the
            # changes aren't lost.
            return (yield from self._save_flow())
        if answer == DiscardChoice.DISCARD:
            return True
        if answer not in (None, DiscardChoice.CANCEL):
            logger.warning("Unknown answer %r to the unsaved-changes question; cancelling",
                           answer)
        return False

    def _save_flow(self) -> SubFlow:
        """Save to the open document, or ask for a name if there is none."""
        ref = self._main.current_document
        if ref is None:
            return (yield from self._save_as_flow())
        return self._write_document(ref)

    def _save_as_flow(self, suggested: Optional[str] = None) -> SubFlow:
        """Ask where to save (suggesting ``suggested``), then save there."""
        current = self._main.current_document
        # A name with its extension: the Flatpak's portal dialog only grants
        # access to the exact name chosen, so ".txt" can't be added later.
        if suggested is None:
            suggested = (current.display_name if current is not None
                         else self._pending_name or formatting.UNTITLED_FILE_NAME)
        ref = self._as_ref((yield PickDocumentRequest(0, PickMode.SAVE, suggested)))
        if ref is None:
            return False
        return self._write_document(ref)

    def _write_document(self, ref: DocumentRef) -> bool:
        """Write the text to ``ref``; it becomes the open, unmodified document."""
        if not self._main.save_file_as(ref):
            self._file_error(formatting.SAVE_FAILED, ref)
            return False
        self._pending_name = None
        self._remember(ref)
        self._set_status(formatting.saved_status(ref.location))
        return True

    def _new_flow(self) -> Flow:
        if not (yield from self._confirm_discard()):
            return
        self._pending_name = None
        with self._undo_policy(UndoPolicy.PLAIN):
            self._main.new_file()
        self._publish_document()
        self._set_status(formatting.NEW_DOCUMENT_STATUS)

    def _open_flow(self, ref: Optional[DocumentRef]) -> Flow:
        if not (yield from self._confirm_discard()):
            return
        if ref is None:
            ref = self._as_ref((yield PickDocumentRequest(0, PickMode.OPEN, "")))
            if ref is None:
                return
        # The text arrives through the viewmodel (_on_text_replaced) as one
        # reset edit, highlighted at once; the directives then set the toolbar.
        revision = self._revision
        with self._undo_policy(UndoPolicy.RESET):
            opened = self._main.open_file(ref)
        if not opened:
            self._file_error(formatting.OPEN_FAILED, ref)
            return
        if self._revision == revision:
            # Same text as before: still a new undo history in the views.
            self._splice(0, len(self._text), self._text, UndoPolicy.RESET)
        self._pending_name = None
        self._remember(ref)
        self._set_status(formatting.opened_status(ref.location))

    def _export_flow(self) -> Flow:
        current = self._main.current_document
        suggested = formatting.midi_export_name(current.stem if current is not None else None)
        ref = self._as_ref((yield PickDocumentRequest(0, PickMode.EXPORT_MIDI, suggested)))
        if ref is None:
            return
        # Rendered off the session thread from a snapshot of the song now.
        job = self._main.midi_export_job()
        self._set_status(formatting.exporting_midi_status(ref.location))
        self._worker.submit(job, self._entry(functools.partial(self._on_midi_rendered, ref)))

    def _on_midi_rendered(self, ref: DocumentRef, outcome: Outcome) -> None:
        """The worker rendered (or failed to render) a MIDI export: write it."""
        # Not remembered as recent: exports aren't documents to reopen here.
        if self._main.finish_midi_export(ref, outcome.value, outcome.error):
            self._set_status(formatting.exported_midi_status(ref.location))
        else:
            self._set_status(formatting.READY)
            self._file_error(formatting.EXPORT_FAILED, ref)

    def _close_flow(self) -> Flow:
        if not (yield from self._confirm_discard()):
            return
        self._emitter.emit(CloseApproved())

    def _remember(self, ref: DocumentRef) -> None:
        """Put ``ref`` at the front of the recent list (the one place that does)."""
        self._documents.add_recent(ref)
        self._publish_recent()

    def _file_error(self, action: str, ref: DocumentRef) -> None:
        self._emitter.emit(UserError(
            formatting.FILE_ERROR_TITLE,
            formatting.file_error_message(action, ref.location, self._main.last_error)))

    def _publish_document(self, _changed: Any = None) -> None:
        ref = self._main.current_document
        modified = self._main.is_modified
        name = ref.display_name if ref is not None else self._pending_name
        self._emitter.set_state(DocumentState(
            display_name=name or formatting.UNTITLED,
            location=ref.location if ref is not None else None,
            is_modified=modified,
            title=formatting.window_title(name, modified),
            document_id=ref.id if ref is not None else None,
        ))

    def _publish_recent(self) -> None:
        """Publish the recent list (reading it prunes documents that are gone)."""
        self._emitter.set_state(RecentDocumentsState(tuple(self._documents.recent())))

    def _feed_chord_sheet(self, _changed: Any = None) -> None:
        """Send the parsed song and key to the chord sheet (it debounces)."""
        if self._chord_sheet is None or not self._started:
            return
        self._chord_sheet.set_song(self._detector.detected_lines, self._main.key)

    def _on_notation_changed(self, notation: Notation) -> None:
        """Detect in the new notation and respell the key in it.

        Also reached from convert, whose ``TextEdited`` is already queued, so
        the views get the edit first and then its highlight.
        """
        self._detector.set_notation(notation.value)
        self._detect_now(publish_toolbar=False)
        self._publish_editor()
        key = self._main.key
        if key:
            converted = toolbar.convert_key(key, notation.value)
            if converted != key:
                self._main.set_key(converted)
        self._publish_toolbar()

    def _publish_editor(self, _changed: Any = None) -> None:
        self._emitter.set_state(EditorState(
            font_family=self._main.font_family,
            font_size=self._main.font_size,
            read_only=self._playback.status is not PlaybackStatus.IDLE,
            notation=self._main.notation.value,
        ))

    def _voicing_groups(self) -> Tuple[Tuple[MenuItem, ...], ...]:
        return formatting.voicing_menu_groups(self._main.get_voicings())

    def _publish_voicing_menu(self, _changed: Any = None) -> None:
        locked = self._voicing_locked = self._playback_status() is PlaybackStatus.PLAYING
        self._emitter.set_state(VoicingMenuState(
            selected=self._main.get_voicing(), groups=self._voicing_groups(),
            locked_reason=formatting.VOICING_LOCKED_REASON if locked else None))

    def _on_voicing_changed(self, _changed: Any = None) -> None:
        if self._playback_status() is PlaybackStatus.PAUSED:
            self._voicing_stale = True

    def _publish_instrument_menu(self) -> None:
        current = self._main.get_instrument()
        self._emitter.set_state(InstrumentMenuState(
            current=current,
            families=formatting.instrument_families(
                self._main.get_available_instruments(), current),
        ))

    def _on_chord_sheet_song(self, _song: Any) -> None:
        self._sheet_revision += 1
        self._publish_chord_sheet()
        # The new song may know the playhead's bar.
        if self._position_status and self._playback.status is PlaybackStatus.IDLE:
            self._set_idle_status()

    def _cursor_index(self) -> Optional[int]:
        """The strip's index of the playhead's chord (its first occurrence)."""
        found = self._strip_chord(self._playhead)
        return found[0] if found is not None else None

    def _strip_chord(self, start: Optional[int]) -> Optional[Tuple[int, int, int]]:
        """``(index, bar, total_bars)`` of the first strip chord starting at ``start``."""
        sheet = self._chord_sheet
        song = sheet.rendered_song if sheet is not None else None
        if start is None or song is None:
            return None
        for index, rendered in enumerate(song.chords):
            source = rendered.chord_info
            if source is not None and source.start == start and not rendered.skipped:
                return index, rendered.song_bar or rendered.bar, song.total_bars
        return None

    def _publish_chord_sheet(self, _changed: Any = None) -> None:
        sheet = self._chord_sheet
        if sheet is None:
            return
        available = set(sheet.available_views)
        self._sheet_snapshot = (sheet.rendered_song, sheet.active_view,
                                sheet.zoom, tuple(sheet.renderers))
        self._emitter.set_state(ChordSheetState(
            visible=sheet.visible,
            height=sheet.height,
            active_view=sheet.active_view,
            views=tuple(ChordSheetView(r.id, r.label, r.id in available)
                        for r in sheet.renderers),
            disabled_reason=sheet.fretted_views_unavailable_reason,
            zoom=sheet.zoom,
            zoom_supported=sheet.zoom_supported,
            current_index=sheet.current_index,
            song_revision=self._sheet_revision,
            cursor_index=self._cursor_index(),
        ))

    def _on_toolbar_value(self, _changed: Any = None) -> None:
        """A toolbar value changed: the toolbar and the song's defaults follow."""
        self._publish_toolbar()
        self._publish_song_defaults()

    def _song_defaults(self) -> SongDefaultsState:
        locked = self._playback_status() is not PlaybackStatus.IDLE
        return song_defaults.song_defaults(
            self._detector.detected_lines, self._main.bpm,
            (self._main.time_signature_beats, self._main.time_signature_unit),
            self._main.key,
            formatting.SONG_DEFAULTS_LOCKED_REASON if locked else None)

    def _publish_song_defaults(self) -> None:
        self._emitter.set_state(self._song_defaults())

    def _setting_directives(self) -> song_defaults.SettingDirectives:
        """The directives with which the song sets its starting values."""
        return song_defaults.setting_directives(self._detector.detected_lines)

    def _directive_text(self, directive: Any) -> Optional[str]:
        """``directive`` as written in the song, or None."""
        if directive is None:
            return None
        return self._detected_text[directive.start:directive.end]

    def _publish_toolbar(self, _changed: Any = None) -> None:
        status = self._playback.status
        idle = status is PlaybackStatus.IDLE
        notation = self._main.notation.value
        # What the song starts with: its directives over the document's values.
        start = self._song_defaults()
        setting = self._setting_directives()
        bpm = int(start.tempo.value)
        beats, unit = (int(v) for v in start.time.value.split("/"))
        self._emitter.set_state(ToolbarState(
            notation=notation,
            bpm=bpm,
            bpm_display=(self._effective_bpm
                         if not idle and self._effective_bpm is not None else bpm),
            bpm_editable=idle and setting.tempo is None,
            multiplier_pct=round(self._main.bpm_multiplier * 100.0, 6),
            key=toolbar.shown_key(start.key.value or None, notation),
            key_options=toolbar.key_options(notation),
            beats=beats,
            unit=unit,
            metronome=self._main.metronome_enabled,
            play_action=_PLAY_ACTIONS[status],
            bpm_set_by=self._directive_text(setting.tempo),
            time_set_by=self._directive_text(setting.time),
            key_set_by=self._directive_text(setting.key),
        ))

    # -- playback internals -----------------------------------------------------

    def _playback_status(self) -> PlaybackStatus:
        if not self._main.is_playing:
            return PlaybackStatus.IDLE
        return PlaybackStatus.PAUSED if self._main.is_paused else PlaybackStatus.PLAYING

    def _set_status(self, text: str) -> None:
        self._position_status = False
        self._emitter.set_state(StatusState(text))

    def _set_idle_status(self) -> None:
        """The status while nothing plays: Android shows the playhead's bar
        (``Bar 6/24``) when it is known, else (and on desktop) "Ready"."""
        if not self._android:
            self._set_status(formatting.READY)
            return
        bar, total = self._playhead_bar()
        self._set_status(formatting.position_status(bar, total))
        self._position_status = True

    def _set_paused_status(self) -> None:
        if self._android:
            self._set_status(formatting.position_status(
                self._playback.bar, self._playback.total_bars, formatting.PAUSED_ACTIVITY))
        else:
            self._set_status(formatting.PAUSED)

    def _playhead_bar(self) -> Tuple[int, int]:
        """``(bar, total_bars)`` of the playhead's chord, ``(0, 0)`` if unknown.

        From the strip's song when it has rendered this text, else from the
        pings of the last run over the same text.
        """
        found = self._strip_chord(self._playhead)
        if found is not None:
            return found[1], found[2]
        if self._playhead is not None and self._ping_bars_revision == self._revision:
            return self._ping_bars.get(self._playhead, (0, 0))
        return 0, 0

    def _publish_playback(self, playback: PlaybackState) -> None:
        playback = dataclasses.replace(playback, playhead_offset=self._playhead)
        self._playback = playback
        if playback.status is PlaybackStatus.IDLE:
            self._effective_bpm = None
            self._playing_chord = None
        self._emitter.set_state(playback)
        self._publish_editor()
        self._publish_toolbar()

    def _move_playhead(self, start: Optional[int]) -> None:
        """Put the playhead at ``start`` (a chord's start, or None)."""
        if start == self._playhead:
            return
        self._playhead = start
        self._publish_playback(self._playback)
        self._publish_chord_sheet()

    def _seek(self, start: int) -> None:
        """Move the playhead to the chord at ``start`` (set_playhead, a tap).

        Paused: the paused song is dropped, so Play starts here. Playing:
        playback restarts here.
        """
        status = self._playback_status()
        if status is not PlaybackStatus.IDLE:
            logger.info("Moving the playhead %s", "while playing: restarting there"
                        if status is PlaybackStatus.PLAYING else "while paused: stopping")
            self._main.stop_playback()
        self._move_playhead(start)
        if status is PlaybackStatus.PLAYING:
            self._start_playback(start)
        else:
            self._set_idle_status()

    def _snap_playhead(self) -> None:
        """Keep the playhead on a chord of the text just detected.

        A playhead the edits left off a chord snaps to the nearest one;
        where the playhead follows playback (Android) a song with chords
        always has one (the first chord by default). Not while a song plays:
        playback moves it then.
        """
        if self._playback.status is not PlaybackStatus.IDLE:
            return
        lines = self._detector.detected_lines
        if self._playhead is not None:
            chord = nearest_chord(lines, self._text, self._playhead)
        elif self._tracks_playhead:
            chord = first_chord(lines)
        else:
            return
        before = self._playhead
        self._move_playhead(chord.start if chord is not None else None)
        if self._playhead != before and self._position_status:
            self._set_idle_status()

    def _start_playback(self, from_offset: Optional[int]) -> None:
        from_cursor = from_offset is not None
        logger.info("Playing from %s", "the cursor" if from_cursor else "the start")
        self._playing_chord = None
        try:
            started = self._main.start_playback(from_char_offset=from_offset or 0)
        except AudioInitializationError as e:
            self._set_status(formatting.AUDIO_UNAVAILABLE_STATUS)
            self._report_audio_failure(str(e), from_click=False)
            return
        if started and self._android:
            self._set_status(formatting.STARTING)
        elif started:
            # Counted from the latest detection, as the status always has.
            count = sum(1 for c in self._detector.get_all_chords() if c.is_valid)
            self._set_status(formatting.playback_started_status(count, from_cursor))
        else:
            self._set_status(formatting.nothing_to_play_status(from_cursor))

    def _report_audio_failure(self, reason: str, from_click: bool) -> None:
        if not self._audio_policy.should_report(from_click):
            logger.warning(f"Audio unavailable (already reported): {reason}")
            return
        message = formatting.audio_unavailable_message(reason, from_click, self._platform)
        self._emitter.emit(AudioUnavailable(message, from_click))

    def _on_transport_changed(self, _value: Any = None) -> None:
        """The viewmodel started, paused, resumed or stopped playback."""
        status = self._playback_status()
        if status is self._playback.status:
            return
        if status is PlaybackStatus.IDLE:
            # A stop (unlike the song ending) posts no "finished" ping, so the
            # chord sheet's playhead would stay on the last chord.
            self._clear_playhead()
            self._voicing_stale = False
            self._publish_playback(PlaybackState(PlaybackStatus.IDLE))
            # The song defaults' tempo and "Write into song" wait for a stop.
            self._publish_song_defaults()
            self._set_idle_status()
        else:
            self._publish_playback(dataclasses.replace(self._playback, status=status))
            self._publish_song_defaults()
        # The voicing menu is locked only while a song plays.
        if self._voicing_locked != (status is PlaybackStatus.PLAYING):
            self._publish_voicing_menu()

    def _clear_playhead(self) -> None:
        """Take the chord sheet's playhead off the last chord (once).

        Also when the strip shows none (its song rendered after the last ping
        or not at all): it remembers the ping for its next song until told.
        """
        if self._chord_sheet is not None and (
                self._sheet_pinged or self._chord_sheet.current_index is not None):
            self._sheet_pinged = False
            self._chord_sheet.on_playback_chord(None)

    def _on_playback_event(self, event: Optional[PlaybackEventArgs]) -> None:
        """A progress ping from the player, or None when a song finished."""
        if event is None:
            # The song finished.
            self._clear_playhead()
            if self._tracks_playhead:
                chord = first_chord(self._detector.detected_lines)
                self._move_playhead(chord.start if chord is not None else None)
            self._set_idle_status()
            return
        if self._playback.status is PlaybackStatus.IDLE:
            # Posted by the player before a Stop reached it.
            logger.debug("Dropping a playback event that arrived after stopping")
            return
        is_chord_start = event.event_type == PlaybackEventType.CHORD_START
        if is_chord_start and self._chord_sheet is not None:
            # chord_index keeps the strip's playhead right on loop passes.
            self._chord_sheet.on_playback_chord(event.chord_info, event.chord_index)
            self._sheet_pinged = True
        if event.bpm is not None:
            self._effective_bpm = int(event.bpm)
        chord = event.chord_info
        if not (is_chord_start and chord is not None):
            self._publish_toolbar()
            return
        # Android counts bars from the top of the song even when playback
        # started later (the desktop's status restarts at bar 1 there).
        bar = event.current_bar
        if self._android and event.song_bar:
            bar = event.song_bar
            if self._ping_bars_revision != self._revision:
                self._ping_bars = {}
                self._ping_bars_revision = self._revision
            self._ping_bars.setdefault(chord.start, (event.song_bar, event.total_bars))
        self._playing_chord = chord.chord
        if self._tracks_playhead and self._playhead != chord.start:
            self._playhead = chord.start
            self._publish_chord_sheet()
        self._publish_playback(dataclasses.replace(
            self._playback,
            playing_span=Span(chord.start, chord.end, SpanKind.CHORD),
            chord_index=event.chord_index,
            bar=bar,
            total_bars=event.total_bars,
        ))
        if self._android:
            self._set_status(formatting.with_tempo_clamp(formatting.position_status(
                bar, event.total_bars, formatting.playing_activity(chord.chord)),
                event.tempo_clamp, formatting.POSITION_SEPARATOR))
        else:
            self._set_status(formatting.with_tempo_clamp(formatting.playing_chord_status(
                event.current_bar, event.total_bars, event.bpm,
                event.time_signature_beats, event.time_signature_unit, event.key, chord.chord),
                event.tempo_clamp, " | "))

    def _on_playback_error(self, message: str) -> None:
        """Rendering the song failed on the render thread (posted here)."""
        self._set_status(formatting.PLAYBACK_FAILED)
        self._emitter.emit(UserError(formatting.PLAYBACK_ERROR_TITLE,
                                     formatting.playback_error_message(message)))

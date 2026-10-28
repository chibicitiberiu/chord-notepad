"""AppSession: the Tk-free application layer the views drive.

The session composes the existing viewmodels and is their observer; views send
it primitive-typed commands and get back one stream of frozen DTOs (see
``docs/architecture/session.md``). It is being built up step by step: so far
it owns the text mirror, debounced chord detection, the highlight spans, the
chord-sheet feed, playback (transport, playing chord, status line, editor
lock, audio-failure reporting), the programmatic edits (transpose, capo,
convert notation, inserts), which it sends to the views as ``TextEdited``,
the toolbar, the menus, settings, and the document flows (new, open, save,
save as, export MIDI, close; the recent list and the window title).

Every public command and every callback the session schedules runs inside
:meth:`Emitter.batch`, so output is delivered at the outermost exit and never
in the middle of a command. All of it runs on the session thread.
"""

import contextlib
import dataclasses
import functools
import logging
from typing import (
    TYPE_CHECKING, Any, Callable, Generator, Iterator, Optional, Sequence, Tuple, TypeVar,
)

from constants import CHORD_DETECTION_DEBOUNCE_MS, MAX_FONT_SIZE, MIN_FONT_SIZE
from exceptions import AudioInitializationError
from models.notation import Notation
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from session import directives, formatting, toolbar
from session.audio_policy import AudioFailurePolicy
from session.emitter import Emitter, Listener
from session.documents import DocumentRef
from session.events import (
    AudioUnavailable, CapoChoiceRequest, CloseApproved, ConfirmDiscardRequest, DiscardChoice,
    InsertDirectiveRequest, PickDocumentRequest, PickMode, TextEdited, UndoPolicy, UserError,
)
from session.flows import Flow, FlowRunner
from session.highlighting import chord_at, compute_spans
from session.host import Cancellable, Host
from session.state import (
    ChordSheetState, ChordSheetView, DocumentState, EditorState, HighlightState,
    InstrumentMenuState, MenuItem, PlayAction, PlaybackState, PlaybackStatus,
    RecentDocumentsState, Span, SpanKind, StatusState, ToolbarState, VoicingMenuState,
)

if TYPE_CHECKING:
    # Type-only: the chord-sheet viewmodel still imports PIL (see the core
    # import guard), so the session must not import it at run time.
    from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
    from viewmodels.main_window_viewmodel import MainWindowViewModel
    from viewmodels.settings_viewmodel import SettingsChanges
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
                 audio_failure_policy: Optional[AudioFailurePolicy] = None) -> None:
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
        """
        self._host = host
        self._emitter = Emitter()
        self._main = main_window_viewmodel
        self._detector = text_editor_viewmodel
        self._chord_sheet = chord_sheet_viewmodel
        self._started = False
        self._detection_delay_s = detection_delay_s

        # The session's copy of the editor text, and its revision.
        self._text = self._main.current_text
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
        # metronome, whoever changed them (a command, an opened file's
        # directives, a whole-song transpose).
        self._on_toolbar_input = self._entry(self._publish_toolbar)
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

        # The strip's own state (visibility, view, zoom, playhead) and a
        # revision that goes up with every song it rendered.
        self._sheet_revision = 0
        self._on_sheet_change = self._entry(self._publish_chord_sheet)
        self._on_sheet_song = self._entry(self._on_chord_sheet_song)
        if self._chord_sheet is not None:
            for name in _CHORD_SHEET_INPUTS:
                self._chord_sheet.observe(name, self._on_sheet_change)
            self._chord_sheet.observe("rendered_song", self._on_sheet_song)

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
        self._main.unobserve("current_text", self._on_replaced)
        self._main.unobserve("current_document", self._on_document)
        self._main.unobserve("is_modified", self._on_document)
        self._main.unobserve("notation", self._on_notation)
        for name in _TOOLBAR_INPUTS:
            self._main.unobserve(name, self._on_toolbar_input)
        self._main.unobserve("font_family", self._on_editor_input)
        self._main.unobserve("font_size", self._on_editor_input)
        self._main.unobserve("voicing", self._on_voicing)
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
            self._main.convert_text_to_american(lines)
        else:
            self._main.convert_text_to_european(lines)
        self._set_status(formatting.converted_status(notation.value))

    @_command
    def request_insert_directive(self, kind: str, at: int) -> None:
        """Ask the view for a directive's fields, then insert it at ``at``.

        Emits :class:`InsertDirectiveRequest`; ``respond`` with the fields
        inserts the directive (and a space) as a plain edit, or emits a
        :class:`UserError` if they don't validate. Refused at answer time
        while a song plays.

        Args:
            kind: ``bpm``, ``time``, ``key``, ``label`` or ``loop``.
            at: Where to insert (the cursor), in code points.

        Raises:
            ValueError: For an unknown kind, or ``at`` outside the text.
        """
        kind = directives.DirectiveKind(kind).value
        if not 0 <= at <= len(self._text):
            raise ValueError(f"insert offset {at} outside the text (length {len(self._text)})")
        self._flows.start(self._insert_directive_flow(kind, at))

    @_command
    def request_suggest_capo(self, selection: Selection = None) -> None:
        """Ask which voicing to optimize for, then insert the best ``{capo: N}``.

        Emits :class:`CapoChoiceRequest`; ``respond`` with a voicing scores
        the selection (or the whole song) and inserts the directive at the
        start of the selection's line (the top without one) as one undo step,
        or says in the status line that no capo helps. Refused at answer time
        while a song plays.

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
    def save_as(self) -> None:
        """Save the document under a name the user picks (it becomes the open document)."""
        self._flows.start(self._as_flow(self._save_as_flow()))

    @_command
    def export_midi(self) -> None:
        """Render the song and write it as a MIDI file the user picks.

        Suggests ``<document name>.mid``. Exports don't join the recent list
        and don't change the open document. A failure (no chords, a render or
        write error) is a :class:`UserError`.
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
                code-point offset (the cursor) instead of at the top. Ignored
                while playing or paused.
        """
        status = self._playback_status()
        if status is PlaybackStatus.PLAYING:
            logger.info("Pausing playback")
            self._main.pause_playback()
            self._set_status(formatting.PAUSED)
        elif status is PlaybackStatus.PAUSED:
            logger.info("Resuming playback")
            self._main.resume_playback()
            self._set_status(formatting.RESUMED)
        else:
            self._start_playback(from_offset)

    @_command
    def stop(self) -> None:
        """Stop playback (also silences notes still ringing when idle)."""
        self._main.stop_playback()
        self._set_status(formatting.STOPPED)

    @_command
    def tap_chord_at(self, offset: int) -> None:
        """Play the chord under ``offset`` once, if there is a valid one.

        Works while a song plays too. If audio can't start, the first tap in
        a session emits :class:`AudioUnavailable`; later ones only log.
        """
        chord = chord_at(self._detector.detected_lines, offset)
        if chord is None or not chord.is_valid:
            return
        try:
            self._main.on_chord_clicked(chord)
        except AudioInitializationError as e:
            self._set_status(formatting.AUDIO_UNAVAILABLE_STATUS)
            self._report_audio_failure(str(e), from_click=True)
            return
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
        """Set the base tempo; ignored while a song plays or is paused.

        The value is clamped to 20-400 and snapped like the toolbar's tempo
        control (``toolbar.BPM_SCALE``).
        """
        if self._playback_status() is not PlaybackStatus.IDLE:
            logger.info("Ignoring a tempo change while a song is playing")
            return
        self._main.set_bpm(toolbar.normalize_bpm(bpm))

    @_command
    def set_multiplier_pct(self, pct: float) -> None:
        """Set the speed multiplier, in percent (100 = as written).

        Applies during playback too. The value is clamped to 12.5-400 and
        snapped like the toolbar's control (``toolbar.MULTIPLIER_SCALE``).
        """
        self._main.set_bpm_multiplier(toolbar.MULTIPLIER_SCALE.normalize(pct) / 100.0)

    @_command
    def set_key(self, key: Optional[str]) -> None:
        """Set the key roman numerals resolve in (None or empty: no key)."""
        self._main.set_key(key or None)

    @_command
    def set_time_signature(self, beats: int, unit: int) -> None:
        """Set the time signature; invalid values are logged and ignored.

        Args:
            beats: Beats per bar, 1-16.
            unit: The beat unit: 1, 2, 4, 8 or 16.
        """
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
    def apply_settings(self, changes: "SettingsChanges") -> None:
        """Bring the running app in line with settings the Settings dialog saved.

        The dialog writes the config itself (``SettingsViewModel.commit``) and
        hands over what changed: a new font is applied, the Voicing menu is
        rebuilt from the edited registry, and the voicing in use is
        re-applied when it was renamed or removed (the new value) or may have
        been edited in place (a user voicing). ``general_changed`` and
        ``audio_changed`` are ignored, as they always were: those settings
        are defaults for the next start (the dialog says so where it
        matters).

        Args:
            changes: What :meth:`SettingsViewModel.commit` reported.
        """
        if changes.font_changed:
            self._main.reload_font_settings()
        if changes.voicings_changed:
            self._publish_voicing_menu()
        if changes.new_active_voicing is not None:
            self._main.set_voicing(changes.new_active_voicing)
        elif changes.voicings_changed and self._main.get_voicing().startswith("voicing:"):
            # Possibly edited in place: rebuild the picker from the new values.
            self._main.set_voicing(self._main.get_voicing())

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
        one step; ignored for views that don't zoom."""
        if self._chord_sheet is None or step == 0:
            return
        if step > 0:
            self._chord_sheet.zoom_in()
        else:
            self._chord_sheet.zoom_out()

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

    @_command
    def show_status(self, text: str) -> None:
        """Show ``text`` in the status line.

        Transitional: the Tk view still words the chord identifier's
        "Inserted chord: X". Goes away with step 13.
        """
        self._set_status(text)

    @property
    def audio_failure_policy(self) -> AudioFailurePolicy:
        """The policy the session reports audio failures by."""
        return self._audio_policy

    # -- queries ----------------------------------------------------------------

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
        """Take a new text: bump the revision and keep the viewmodel in step."""
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

    def _detect_now(self) -> None:
        self._cancel_detection()
        self._detector.on_text_changed(self._text)
        self._publish_highlight()

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
        voicing = yield CapoChoiceRequest(0, options, default)
        label = next((o.label for o in options if o.value == voicing), None)
        if voicing is None or label is None:
            return
        if not self._edits_allowed("suggest capo"):
            return
        if region is not None and region[1] > len(self._text):
            region = None  # the text changed under the selection
        capo = self._main.suggest_capo_for(voicing, region)
        if not capo:
            self._set_status(formatting.no_capo_status(region is not None, label))
            return
        with self._undo_policy(UndoPolicy.GROUP):
            self._main.insert_capo(capo, region)
        self._set_status(formatting.capo_suggested_status(capo, region is not None, label))

    # -- document internals -----------------------------------------------------

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

    def _save_as_flow(self) -> SubFlow:
        """Ask where to save, then save there."""
        current = self._main.current_document
        # A name with its extension: the Flatpak's portal dialog only grants
        # access to the exact name chosen, so ".txt" can't be added later.
        suggested = current.display_name if current is not None else formatting.UNTITLED_FILE_NAME
        ref = self._as_ref((yield PickDocumentRequest(0, PickMode.SAVE, suggested)))
        if ref is None:
            return False
        return self._write_document(ref)

    def _write_document(self, ref: DocumentRef) -> bool:
        """Write the text to ``ref``; it becomes the open, unmodified document."""
        if not self._main.save_file_as(ref):
            self._file_error(formatting.SAVE_FAILED, ref)
            return False
        self._remember(ref)
        self._set_status(formatting.saved_status(ref.location))
        return True

    def _new_flow(self) -> Flow:
        if not (yield from self._confirm_discard()):
            return
        with self._undo_policy(UndoPolicy.PLAIN):
            self._main.new_file()
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
        self._remember(ref)
        self._set_status(formatting.opened_status(ref.location))

    def _export_flow(self) -> Flow:
        current = self._main.current_document
        suggested = formatting.midi_export_name(current.stem if current is not None else None)
        ref = self._as_ref((yield PickDocumentRequest(0, PickMode.EXPORT_MIDI, suggested)))
        if ref is None:
            return
        # Not remembered as recent: exports aren't documents to reopen here.
        if self._main.export_midi_file(ref):
            self._set_status(formatting.exported_midi_status(ref.location))
        else:
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
        name = ref.display_name if ref is not None else None
        self._emitter.set_state(DocumentState(
            display_name=name or formatting.UNTITLED,
            location=ref.location if ref is not None else None,
            is_modified=modified,
            title=formatting.window_title(name, modified),
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
        self._detect_now()
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
        self._emitter.set_state(VoicingMenuState(
            selected=self._main.get_voicing(), groups=self._voicing_groups()))

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

    def _publish_chord_sheet(self, _changed: Any = None) -> None:
        sheet = self._chord_sheet
        if sheet is None:
            return
        available = set(sheet.available_views)
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
        ))

    def _publish_toolbar(self, _changed: Any = None) -> None:
        status = self._playback.status
        idle = status is PlaybackStatus.IDLE
        bpm = self._main.bpm
        notation = self._main.notation.value
        self._emitter.set_state(ToolbarState(
            notation=notation,
            bpm=bpm,
            bpm_display=(self._effective_bpm
                         if not idle and self._effective_bpm is not None else bpm),
            bpm_editable=idle,
            multiplier_pct=round(self._main.bpm_multiplier * 100.0, 6),
            key=toolbar.shown_key(self._main.key, notation),
            key_options=toolbar.key_options(notation),
            beats=self._main.time_signature_beats,
            unit=self._main.time_signature_unit,
            metronome=self._main.metronome_enabled,
            play_action=_PLAY_ACTIONS[status],
        ))

    # -- playback internals -----------------------------------------------------

    def _playback_status(self) -> PlaybackStatus:
        if not self._main.is_playing:
            return PlaybackStatus.IDLE
        return PlaybackStatus.PAUSED if self._main.is_paused else PlaybackStatus.PLAYING

    def _set_status(self, text: str) -> None:
        self._emitter.set_state(StatusState(text))

    def _publish_playback(self, playback: PlaybackState) -> None:
        self._playback = playback
        if playback.status is PlaybackStatus.IDLE:
            self._effective_bpm = None
        self._emitter.set_state(playback)
        self._publish_editor()
        self._publish_toolbar()

    def _start_playback(self, from_offset: Optional[int]) -> None:
        from_cursor = from_offset is not None
        logger.info("Playing from %s", "the cursor" if from_cursor else "the start")
        try:
            started = self._main.start_playback(from_char_offset=from_offset or 0)
        except AudioInitializationError as e:
            self._set_status(formatting.AUDIO_UNAVAILABLE_STATUS)
            self._report_audio_failure(str(e), from_click=False)
            return
        if started:
            # Counted from the latest detection, as the status always has.
            count = sum(1 for c in self._detector.get_all_chords() if c.is_valid)
            self._set_status(formatting.playback_started_status(count, from_cursor))
        else:
            self._set_status(formatting.nothing_to_play_status(from_cursor))

    def _report_audio_failure(self, reason: str, from_click: bool) -> None:
        if not self._audio_policy.should_report(from_click):
            logger.warning(f"Audio unavailable (already reported): {reason}")
            return
        message = formatting.audio_unavailable_message(reason, from_click)
        self._emitter.emit(AudioUnavailable(message, from_click))

    def _on_transport_changed(self, _value: Any = None) -> None:
        """The viewmodel started, paused, resumed or stopped playback."""
        status = self._playback_status()
        if status is self._playback.status:
            return
        if status is PlaybackStatus.IDLE:
            self._publish_playback(PlaybackState(PlaybackStatus.IDLE))
            self._set_status(formatting.READY)
        else:
            self._publish_playback(dataclasses.replace(self._playback, status=status))

    def _on_playback_event(self, event: Optional[PlaybackEventArgs]) -> None:
        """A progress ping from the player, or None when a song finished."""
        if event is None:
            if self._chord_sheet is not None:
                self._chord_sheet.on_playback_chord(None)
            self._set_status(formatting.READY)
            return
        if self._playback.status is PlaybackStatus.IDLE:
            # Posted by the player before a Stop reached it.
            logger.debug("Dropping a playback event that arrived after stopping")
            return
        is_chord_start = event.event_type == PlaybackEventType.CHORD_START
        if is_chord_start and self._chord_sheet is not None:
            # chord_index keeps the strip's playhead right on loop passes.
            self._chord_sheet.on_playback_chord(event.chord_info, event.chord_index)
        if event.bpm is not None:
            self._effective_bpm = int(event.bpm)
        chord = event.chord_info
        if not (is_chord_start and chord is not None):
            self._publish_toolbar()
            return
        self._publish_playback(dataclasses.replace(
            self._playback,
            playing_span=Span(chord.start, chord.end, SpanKind.CHORD),
            chord_index=event.chord_index,
            bar=event.current_bar,
            total_bars=event.total_bars,
        ))
        self._set_status(formatting.playing_chord_status(
            event.current_bar, event.total_bars, event.bpm,
            event.time_signature_beats, event.time_signature_unit, event.key, chord.chord))

    def _on_playback_error(self, message: str) -> None:
        """Rendering the song failed on the render thread (posted here)."""
        self._set_status(formatting.PLAYBACK_FAILED)
        self._emitter.emit(UserError(formatting.PLAYBACK_ERROR_TITLE,
                                     formatting.playback_error_message(message)))

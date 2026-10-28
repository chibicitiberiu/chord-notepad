"""AppSession: the Tk-free application layer the views drive.

The session composes the existing viewmodels and is their observer; views send
it primitive-typed commands and get back one stream of frozen DTOs (see
``docs/architecture/session.md``). It is being built up step by step: so far
it owns the text mirror, debounced chord detection, the highlight spans, the
chord-sheet feed and playback (transport, playing chord, status line,
editor lock, audio-failure reporting).

Every public command and every callback the session schedules runs inside
:meth:`Emitter.batch`, so output is delivered at the outermost exit and never
in the middle of a command. All of it runs on the session thread.
"""

import dataclasses
import functools
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, TypeVar

from constants import CHORD_DETECTION_DEBOUNCE_MS
from exceptions import AudioInitializationError
from models.notation import Notation
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from session import formatting
from session.audio_policy import AudioFailurePolicy
from session.emitter import Emitter, Listener
from session.events import AudioUnavailable, UserError
from session.highlighting import chord_at, compute_spans
from session.host import Cancellable, Host
from session.state import (
    EditorState, HighlightState, PlaybackState, PlaybackStatus, Span, SpanKind, StatusState,
)

if TYPE_CHECKING:
    # Type-only: the chord-sheet viewmodel still imports PIL (see the core
    # import guard), so the session must not import it at run time.
    from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
    from viewmodels.main_window_viewmodel import MainWindowViewModel
    from viewmodels.text_editor_viewmodel import TextEditorViewModel

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


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
            main_window_viewmodel: Keeps the document text, its modified flag
                and the notation preference (until those move here), and
                runs playback.
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

        # Detection follows the notation preference.
        self._detector.set_notation(self._main.notation.value)
        self._on_notation = self._entry(self._on_notation_changed)
        self._main.observe("notation", self._on_notation)

        # The chord sheet re-renders when the parsed song, the key (roman
        # numerals) or the voicing (fingerings, view gating) changes.
        self._on_song_input = self._entry(self._feed_chord_sheet)
        if self._chord_sheet is not None:
            self._detector.observe("detected_lines", self._on_song_input)
            self._main.observe("key", self._on_song_input)
            self._main.observe("voicing", self._on_song_input)

        # Playback: the viewmodel runs it, the session turns its transport
        # flags and progress pings into states.
        self._audio_policy = audio_failure_policy or AudioFailurePolicy()
        self._playback = PlaybackState(self._playback_status())
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
            self._emitter.set_state(EditorState(read_only=False))

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
        self._main.unobserve("notation", self._on_notation)
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
    def set_text_now(self, text: str) -> None:
        """Like :meth:`set_text`, but re-detect immediately.

        Transitional: the Tk view still applies programmatic edits (open,
        transpose, convert, capo) itself and reports the result here. It goes
        away once those edits move into the session (steps 8 and 11).
        """
        if text != self._text:
            self._replace_mirror(text, 0)
        self._detect_now()

    @_command
    def insert_text(self, at: int, text: str) -> None:
        """Insert ``text`` at offset ``at`` and re-detect immediately.

        For inserts that don't come from typing (the chord identifier).

        Raises:
            ValueError: If ``at`` is outside the text.
        """
        if not 0 <= at <= len(self._text):
            raise ValueError(f"insert offset {at} outside the text (length {len(self._text)})")
        if text:
            self._replace_mirror(self._text[:at] + text + self._text[at:], 0)
        self._detect_now()

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
            self._report_audio_failure(e, from_click=True)
            return
        self._set_status(formatting.tapped_chord_status(chord.chord))

    @_command
    def show_status(self, text: str) -> None:
        """Show ``text`` in the status line.

        Transitional: the Tk view still words the outcome of the flows it
        runs itself (open, save, transpose, insert...). Goes away as those
        flows move into the session (steps 8-11).
        """
        self._set_status(text)

    @property
    def audio_failure_policy(self) -> AudioFailurePolicy:
        """The policy the session reports audio failures by.

        Shared with the Tk presenter for the click sources that don't go
        through the session yet (chord-sheet audition, chord identifier).
        """
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

    def _feed_chord_sheet(self, _changed: Any = None) -> None:
        """Send the parsed song and key to the chord sheet (it debounces)."""
        if self._chord_sheet is None or not self._started:
            return
        self._chord_sheet.set_song(self._detector.detected_lines, self._main.key)

    def _on_notation_changed(self, notation: Notation) -> None:
        self._detector.set_notation(notation.value)
        self._detect_now()

    # -- playback internals -----------------------------------------------------

    def _playback_status(self) -> PlaybackStatus:
        if not self._main.is_playing:
            return PlaybackStatus.IDLE
        return PlaybackStatus.PAUSED if self._main.is_paused else PlaybackStatus.PLAYING

    def _set_status(self, text: str) -> None:
        self._emitter.set_state(StatusState(text))

    def _publish_playback(self, playback: PlaybackState) -> None:
        self._playback = playback
        self._emitter.set_state(playback)
        self._emitter.set_state(EditorState(read_only=playback.status is not PlaybackStatus.IDLE))

    def _start_playback(self, from_offset: Optional[int]) -> None:
        from_cursor = from_offset is not None
        logger.info("Playing from %s", "the cursor" if from_cursor else "the start")
        try:
            started = self._main.start_playback(from_char_offset=from_offset or 0)
        except AudioInitializationError as e:
            self._set_status(formatting.AUDIO_UNAVAILABLE_STATUS)
            self._report_audio_failure(e, from_click=False)
            return
        if started:
            # Counted from the latest detection, as the status always has.
            count = sum(1 for c in self._detector.get_all_chords() if c.is_valid)
            self._set_status(formatting.playback_started_status(count, from_cursor))
        else:
            self._set_status(formatting.nothing_to_play_status(from_cursor))

    def _report_audio_failure(self, error: BaseException, from_click: bool) -> None:
        if not self._audio_policy.should_report(from_click):
            logger.warning(f"Audio unavailable (already reported): {error}")
            return
        message = formatting.audio_unavailable_message(str(error), from_click)
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
        bpm = int(event.bpm) if event.bpm is not None else self._playback.bpm
        chord = event.chord_info
        if not (is_chord_start and chord is not None):
            self._publish_playback(dataclasses.replace(self._playback, bpm=bpm))
            return
        self._publish_playback(dataclasses.replace(
            self._playback,
            playing_span=Span(chord.start, chord.end, SpanKind.CHORD),
            chord_index=event.chord_index,
            bar=event.current_bar,
            total_bars=event.total_bars,
            bpm=bpm,
        ))
        self._set_status(formatting.playing_chord_status(
            event.current_bar, event.total_bars, event.bpm,
            event.time_signature_beats, event.time_signature_unit, event.key, chord.chord))

    def _on_playback_error(self, message: str) -> None:
        """Rendering the song failed on the render thread (posted here)."""
        self._set_status(formatting.PLAYBACK_FAILED)
        self._emitter.emit(UserError(formatting.PLAYBACK_ERROR_TITLE,
                                     formatting.playback_error_message(message)))

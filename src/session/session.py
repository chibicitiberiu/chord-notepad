"""AppSession: the Tk-free application layer the views drive.

The session composes the existing viewmodels and is their observer; views send
it primitive-typed commands and get back one stream of frozen DTOs (see
``docs/architecture/session.md``). It is being built up step by step: so far
it owns the text mirror, debounced chord detection and the highlight spans.

Every public command and every callback the session schedules runs inside
:meth:`Emitter.batch`, so output is delivered at the outermost exit and never
in the middle of a command. All of it runs on the session thread.
"""

import functools
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, TypeVar

from constants import CHORD_DETECTION_DEBOUNCE_MS
from models.chord import ChordInfo
from models.notation import Notation
from session.emitter import Emitter, Listener
from session.highlighting import chord_at, compute_spans
from session.host import Cancellable, Host
from session.state import HighlightState, Span, SpanKind

if TYPE_CHECKING:
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
                 detection_delay_s: float = CHORD_DETECTION_DEBOUNCE_MS / 1000) -> None:
        """Create the session. Nothing is delivered or scheduled until used.

        Args:
            host: Runs the session's callbacks and timers on the session thread.
            main_window_viewmodel: Keeps the document text, its modified flag
                and the notation preference (until those move here).
            text_editor_viewmodel: The chord-detection component; only the
                session drives it.
            detection_delay_s: How long typing must pause before the text is
                re-detected.
        """
        self._host = host
        self._emitter = Emitter()
        self._main = main_window_viewmodel
        self._detector = text_editor_viewmodel
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

        with self._emitter.batch():
            self._emitter.set_state(HighlightState(0, 0, ()))

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
        """Detect the current text and publish the result.

        Call once the host can run timers (on desktop: after
        ``TkHost.attach``).
        """
        self._detect_now()

    def shutdown(self) -> None:
        """Cancel pending work and stop observing; drops every listener."""
        self._cancel_detection()
        self._main.unobserve("notation", self._on_notation)
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

    def detected_chord_at(self, offset: int) -> Optional[ChordInfo]:
        """The detected chord object under ``offset``.

        Transitional, for the Tk click-to-play that still calls the viewmodel
        itself; ``tap_chord_at`` replaces it in step 7.
        """
        return chord_at(self._detector.detected_lines, offset)

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

    def _on_notation_changed(self, notation: Notation) -> None:
        self._detector.set_notation(notation.value)
        self._detect_now()

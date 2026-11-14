"""What the Edit workspace's status bar shows (plan step D4; F4 adds the rest).

:class:`StatusBarModel` is the Qt side of the Tk front end's
``DirectiveHints`` status line (``chordnotepad_tk/directive_hints.py``). The
precedence itself is the core's :class:`~chordnotepad.session.status_line.StatusLine`,
shared with Tk:

* while a song plays or is paused (``PlaybackState.status``), playback's
  status wins;
* otherwise the hint of the directive at the caret covers the session's
  status (``StatusState.text``), also for one still being typed (``{b``);
* a new status from the session shows over the hint until the caret moves.

The caret's hint is looked up :data:`HINT_DELAY_MS` after the caret rests
(QML calls :meth:`StatusBarModel.schedule` on a key, a click, a caret move
and focus) and after each ``HighlightState`` (a directive's "has no effect"
reason needs the new detection), through the session's
``directive_hint_at`` (a direct call).

QML reads :attr:`statusText` when :attr:`showHint` is false, else
:attr:`hintMessage` (red, or muted when :attr:`hintRedundant`) and
:attr:`hintSyntax` (monospace, the lines joined with " · ").
:attr:`text` is all of it as one line, as Tk shows it.

F4 owns the rest of the bar (Ln/Col, the notation, "Read-only while
playing"): add it here, next to the precedence.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from chordnotepad.session import formatting
from chordnotepad.session.status_line import StatusLine

logger = logging.getLogger(__name__)

#: How long the caret rests before its hint is looked up (Tk's HINT_DELAY_MS).
HINT_DELAY_MS = 150


@dataclass(frozen=True)
class HintLine:
    """A directive hint as the status bar shows it.

    Attributes:
        message: Why the directive is invalid or has no effect, or "".
        syntax: Its syntax on one line (" · " between the examples).
        redundant: The directive is valid but has no effect (shown muted).
    """

    message: str
    syntax: str
    redundant: bool = False

    @property
    def text(self) -> str:
        """The hint on one line, the reason first (Tk's status-bar text)."""
        return formatting.directive_hint_status(self.message, self.syntax)


def hint_line(hint: Any) -> Optional[HintLine]:
    """The status bar's line for a ``DirectiveHint``; None when there is no
    directive at the offset (its ``syntax`` is "")."""
    if not hint.syntax:
        return None
    return HintLine(hint.message, formatting.directive_hint_status("", hint.syntax),
                    bool(hint.redundant))


class StatusBarModel(QObject):
    """The status bar's message: the session's status or the caret's hint.

    Args:
        store: The window's SessionStore (states and the direct call).
        editor: The EditorBridge (the caret, offsets, whether the session has
            the text shown).
        delay_ms: The caret's rest before its hint is looked up.
    """

    #: Something the bar shows changed.
    changed = Signal()

    def __init__(self, store: Any, editor: Any, delay_ms: int = HINT_DELAY_MS,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self.line = StatusLine(lambda _shown: self.changed.emit())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self.refresh)
        store.stateChanged.connect(self._on_state)
        # The session replayed its states into the store when it was made.
        self._take_status()
        self._take_playback()

    # -- for QML ----------------------------------------------------------------------

    def _get_status_text(self) -> str:
        return self.line.status

    #: The session's status (StatusState.text), or playback's.
    statusText = Property(str, _get_status_text, notify=changed)

    def _get_show_hint(self) -> bool:
        return self.line.showing_hint

    #: Whether the hint shows instead of the status.
    showHint = Property(bool, _get_show_hint, notify=changed)

    def _hint(self) -> HintLine:
        return self.line.hint or HintLine("", "")

    def _get_hint_message(self) -> str:
        return self._hint().message

    #: The hint's reason ("" for a valid directive).
    hintMessage = Property(str, _get_hint_message, notify=changed)

    def _get_hint_syntax(self) -> str:
        return self._hint().syntax

    #: The hint's syntax, on one line.
    hintSyntax = Property(str, _get_hint_syntax, notify=changed)

    def _get_hint_redundant(self) -> bool:
        return self._hint().redundant

    #: The hinted directive has no effect (its reason is muted, not an error).
    hintRedundant = Property(bool, _get_hint_redundant, notify=changed)

    def _get_playing(self) -> bool:
        return self.line.playing

    #: A song is playing or paused.
    playing = Property(bool, _get_playing, notify=changed)

    def _get_text(self) -> str:
        return self._hint().text if self.line.showing_hint else self.line.status

    #: Everything the message shows, on one line.
    text = Property(str, _get_text, notify=changed)

    @Slot()
    def schedule(self) -> None:
        """Look the caret's hint up once it has rested (debounced)."""
        self._timer.start()

    @Slot()
    def refresh(self) -> None:
        """Look the caret's hint up now and show it."""
        self._timer.stop()
        if self.line.playing or self._store.closed:
            return
        cursor = self._editor.cursor_position()
        if cursor is None:
            return
        if not self._editor.in_step:
            self.schedule()     # a set_text is still queued: its offsets would be off
            return
        hint = self._store.direct("directive_hint_at", self._editor.to_code_point(cursor))
        self.line.set_hint(hint_line(hint), cursor)

    # -- from the session -------------------------------------------------------------

    def _on_state(self, type_name: str) -> None:
        if type_name == "StatusState":
            self._take_status()
        elif type_name == "PlaybackState":
            self._take_playback()
        elif type_name == "HighlightState":
            self.schedule()

    def _take_status(self) -> None:
        # The session drops a state equal to the last one, so every
        # StatusState delivered is a new status (as Tk's set_status).
        text = self._store.state("StatusState").value("text")
        if text is not None:
            self.line.set_status(str(text), self._editor.cursor_position())

    def _take_playback(self) -> None:
        status = self._store.state("PlaybackState").value("status")
        playing = status is not None and status != "idle"
        if playing != self.line.playing:
            self.line.set_playing(playing)
            if not playing:
                self.schedule()     # the hint comes back after

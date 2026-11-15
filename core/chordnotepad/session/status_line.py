"""What a desktop status bar shows: the session's status, a directive hint
over it while the caret is in a directive, and playback's status while a
song plays. Plain logic, shown by the Qt window's status bar
(``chordnotepad_desktop/status_bar.py``); the Tk window's (removed in 0.6.0)
showed the same.

The precedence (checklist §8):

* While a song plays or is paused, playback's status wins.
* Otherwise the directive hint covers the session's status while the caret
  is in a directive (or one being typed).
* A new status from the session shows at once, over the hint, until the
  caret moves again.

A hint is whatever the front end shows for one: Tk a line of text
(``formatting.directive_hint_status``), Qt the reason and the syntax apart,
to colour them. Anything false (``""``, None) is no hint.
"""

from typing import Any, Callable, Optional


class StatusLine:
    """The status bar's text and the hint over it (see the module docstring).

    ``quiet_at`` is where the caret was when the last status came in: a hint
    for that same place is ignored, so the status stays until the caret
    moves. Positions are the front end's own (any unit, as long as it is the
    same for :meth:`set_status` and :meth:`set_hint`).
    """

    def __init__(self, show: Callable[[Any], None]) -> None:
        """Args:
            show: Called with :attr:`text` whenever what shows changes.
        """
        self._show = show
        self.status = ""
        self.hint: Any = ""
        self.playing = False
        self.quiet_at: Optional[int] = None

    @property
    def showing_hint(self) -> bool:
        """Whether the hint shows (else the status does)."""
        return not self.playing and bool(self.hint)

    @property
    def text(self) -> Any:
        """What the status bar should show now: the hint or the status."""
        return self.hint if self.showing_hint else self.status

    def set_status(self, text: str, cursor: Optional[int] = None) -> None:
        """The session's status changed; it shows until the caret moves.

        Args:
            text: The new status.
            cursor: Where the caret is now.
        """
        self.status = text
        self.hint = ""
        self.quiet_at = cursor
        self._show(self.text)

    def set_playing(self, playing: bool) -> None:
        """Whether a song is playing or paused (its status wins then)."""
        if playing != self.playing:
            self.playing = playing
            self._show(self.text)

    def set_hint(self, hint: Any, cursor: int) -> None:
        """The hint for the caret at ``cursor`` (false outside a directive).

        Ignored while the caret hasn't moved since the last status came in.
        """
        if cursor == self.quiet_at:
            return
        self.quiet_at = None
        if hint != self.hint:
            self.hint = hint
            self._show(self.text)

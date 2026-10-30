"""The directive hints of the desktop editor: chrome only, the text is untouched.

* While the text cursor is inside a directive (or one being typed), the
  status bar shows its syntax, with the reason first when the directive is
  invalid or has no effect. When the cursor leaves, the status bar shows what
  it showed before; while a song plays (or is paused), playback's status wins.
* Hovering a red (invalid) or faded (redundant) directive shows a tooltip
  with the reason and the syntax.

The session answers "which directive is here?" (``directive_hint_at``,
which detects nothing); this module only decides what to show and when.
"""

import tkinter as tk
from typing import TYPE_CHECKING, Callable, Optional, Tuple

from constants import TAG_DIRECTIVE_INVALID, TAG_DIRECTIVE_REDUNDANT
from session import formatting
from ui.base.tooltip import RegionToolTip

if TYPE_CHECKING:
    from session.session import AppSession
    from ui.text_editor import ChordTextEditor

#: How long the cursor rests before its hint is looked up.
HINT_DELAY_MS = 150

#: The editor tags that get a hover tooltip.
_EXPLAINED_TAGS = (TAG_DIRECTIVE_INVALID, TAG_DIRECTIVE_REDUNDANT)


class StatusLine:
    """What the status bar shows: the session's status, a directive hint over
    it while the cursor is in a directive, and playback's status while a song
    plays. Plain logic (no Tk), so it can be tested on its own.

    A new status from the session shows at once, over the hint, until the
    cursor moves again (``quiet_at`` is where the cursor was then).
    """

    def __init__(self, show: Callable[[str], None]) -> None:
        """Args:
            show: Puts a text in the status bar.
        """
        self._show = show
        self.status = ""
        self.hint = ""
        self.playing = False
        self.quiet_at: Optional[int] = None

    @property
    def text(self) -> str:
        """What the status bar should show now."""
        if self.playing or not self.hint:
            return self.status
        return self.hint

    def set_status(self, text: str, cursor: Optional[int] = None) -> None:
        """The session's status changed; it shows until the cursor moves.

        Args:
            text: The new status.
            cursor: Where the text cursor is now.
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

    def set_hint(self, hint: str, cursor: int) -> None:
        """The hint for the cursor at ``cursor`` ("" outside a directive).

        Ignored while the cursor hasn't moved since the last status came in.
        """
        if cursor == self.quiet_at:
            return
        self.quiet_at = None
        if hint != self.hint:
            self.hint = hint
            self._show(self.text)


class DirectiveHints:
    """Wires the status-bar hint and the hover tooltip to a Tk editor.

    The cursor hook is debounced (:data:`HINT_DELAY_MS`) and asks the session
    once per rest; hovering looks only at the editor's own tags until the
    tooltip is about to show.
    """

    def __init__(self, editor: "ChordTextEditor", statusbar: tk.Widget,
                 session: "AppSession", delay_ms: int = HINT_DELAY_MS) -> None:
        """Args:
            editor: The song editor.
            statusbar: The status bar label (its ``text`` is set).
            session: Answers ``directive_hint_at``.
            delay_ms: The cursor's rest before its hint is looked up.
        """
        self._editor = editor
        self._statusbar = statusbar
        self._session = session
        self._delay_ms = delay_ms
        self._after_id: Optional[str] = None
        self.status = StatusLine(lambda text: statusbar.config(text=text))
        for sequence in ('<KeyRelease>', '<ButtonRelease-1>', '<FocusIn>'):
            editor.bind(sequence, lambda _e: self.schedule(), add='+')
        self.tooltip = RegionToolTip(editor, self.region_at, self.tooltip_text,
                                     position_for=self.tooltip_position)

    # -- the status bar ------------------------------------------------------

    def set_status(self, text: str) -> None:
        """Show the session's status (over the hint, until the cursor moves)."""
        self.status.set_status(text, self._cursor())

    def set_playing(self, playing: bool) -> None:
        """Playback started (or paused) or stopped; the hint comes back after."""
        self.status.set_playing(playing)
        if not playing:
            self.schedule()

    def schedule(self) -> None:
        """Look the cursor's hint up once it has rested (debounced)."""
        if self._after_id is not None:
            self._editor.after_cancel(self._after_id)
        self._after_id = self._editor.after(self._delay_ms, self.refresh)

    def refresh(self) -> None:
        """Look the cursor's hint up now and show it."""
        self._after_id = None
        if self.status.playing:
            return
        cursor = self._cursor()
        if cursor is None:
            return
        hint = self._session.directive_hint_at(cursor)
        self.status.set_hint(formatting.directive_hint_status(hint.message, hint.syntax), cursor)

    def _cursor(self) -> Optional[int]:
        try:
            return self._editor.offset_of(tk.INSERT)
        except tk.TclError:
            return None

    # -- the hover tooltip ---------------------------------------------------

    def region_at(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """The red or faded directive under the pointer, as ``(start, end)``
        code-point offsets, or None. Uses only the editor's tags."""
        index = self._editor.index(f"@{x},{y}")
        box = self._editor.bbox(index)
        if box is None or not (box[0] <= x < box[0] + box[2]):
            return None  # past the end of the line, or hidden
        for tag in _EXPLAINED_TAGS:
            if tag in self._editor.tag_names(index):
                span = self._editor.tag_prevrange(tag, f"{index}+1c")
                if span:
                    return self._editor.offset_of(span[0]), self._editor.offset_of(span[1])
        return None

    def tooltip_position(self, region: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Just under the directive's first character, so the tip doesn't
        cover the directive (screen coordinates); None when it's hidden."""
        box = self._editor.bbox(f"1.0 + {region[0]} chars")
        if box is None:
            return None
        x, y, _width, height = box
        return self._editor.winfo_rootx() + x, self._editor.winfo_rooty() + y + height + 4

    def tooltip_text(self, region: Tuple[int, int]) -> Optional[str]:
        """The reason and the syntax of the directive at ``region``."""
        hint = self._session.directive_hint_at(region[0])
        if not hint.message:
            return None
        return formatting.directive_hint_tooltip(hint.message, hint.syntax)

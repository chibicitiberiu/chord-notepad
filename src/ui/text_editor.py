"""
Custom text editor widget that paints the session's chord highlighting
"""

import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional
from session.events import TextEdited, UndoPolicy
from session.state import HighlightState, Span, SpanKind
from utils.text_normalization import normalize_song_text
from constants import (
    TAG_CHORD_VALID, TAG_CHORD_INVALID, TAG_CHORD_PLAYING,
    TAG_DIRECTIVE_VALID, TAG_DIRECTIVE_INVALID, TAG_COMMENT,
    COLOR_CHORD_VALID, COLOR_CHORD_INVALID, COLOR_CHORD_PLAYING_BG,
    COLOR_DIRECTIVE_VALID, COLOR_DIRECTIVE_INVALID, COLOR_COMMENT,
)

if TYPE_CHECKING:
    from session.session import AppSession

# The text tag each kind of highlight span is painted with.
_SPAN_TAGS: Dict[SpanKind, str] = {
    SpanKind.CHORD: TAG_CHORD_VALID,
    SpanKind.CHORD_INVALID: TAG_CHORD_INVALID,
    SpanKind.DIRECTIVE: TAG_DIRECTIVE_VALID,
    SpanKind.DIRECTIVE_INVALID: TAG_DIRECTIVE_INVALID,
    SpanKind.COMMENT: TAG_COMMENT,
}

#: The keys that redo, on every platform: Tk's own <<Redo>> is Ctrl+Shift+Z on
#: Linux and macOS and Ctrl+Y on Windows (the Lock forms keep Caps Lock working).
REDO_SEQUENCES = ('<Control-Key-y>', '<Control-Lock-Key-Y>',
                  '<Control-Key-Z>', '<Control-Lock-Key-z>')
#: What the Edit menu shows for Redo.
REDO_ACCELERATOR = "Ctrl+Y"


class ChordTextEditor(tk.Text):
    """Text editor widget that shows chord highlighting.

    A thin view: chord detection, highlight spans and chord hit-testing live
    in the session. The window sends the text to the session when it changes,
    hands the resulting :class:`HighlightState` to :meth:`apply_highlight` and
    the session's own edits to :meth:`apply_edit`.
    """

    def __init__(self, parent: Any, session: Optional["AppSession"] = None, **kwargs: Any) -> None:
        """Initialize the text editor.

        Args:
            parent: Parent widget
            session: Answers "is there a chord here?" for the hand cursor.
                None for a display-only editor (no hand cursor).
            **kwargs: Additional keyword arguments passed to tk.Text
        """
        # Enable undo by default
        kwargs.setdefault('undo', True)
        kwargs.setdefault('maxundo', -1)
        kwargs.setdefault('wrap', tk.WORD)
        kwargs.setdefault('insertbackground', 'black')

        super().__init__(parent, **kwargs)

        self._session = session

        # The highlighting currently painted
        self.highlight: Optional[HighlightState] = None

        # Configure tags for chord highlighting
        self.tag_config(TAG_CHORD_VALID, foreground=COLOR_CHORD_VALID, underline=True)
        self.tag_config(TAG_CHORD_INVALID, foreground=COLOR_CHORD_INVALID, underline=True)
        self.tag_config(TAG_CHORD_PLAYING, background=COLOR_CHORD_PLAYING_BG, foreground='black', underline=True)

        # Configure tags for directive highlighting
        self.tag_config(TAG_DIRECTIVE_VALID, foreground=COLOR_DIRECTIVE_VALID, underline=False)
        self.tag_config(TAG_DIRECTIVE_INVALID, foreground=COLOR_DIRECTIVE_INVALID, underline=True, underlinefg=COLOR_DIRECTIVE_INVALID)

        # Configure tag for comments
        self.tag_config(TAG_COMMENT, foreground=COLOR_COMMENT)

        # Bind numpad Enter to work like regular Enter
        self.bind('<KP_Enter>', lambda e: self.insert(tk.INSERT, '\n'))

        # Bind mouse motion to change cursor over chords
        self.bind('<Motion>', self._on_mouse_motion)

        # Fix paste to replace selection
        self.bind('<<Paste>>', self._on_paste)

        # Ctrl+Y and Ctrl+Shift+Z both redo, whatever the platform. Tk's X11
        # bindings also make Ctrl+Y paste (emacs "yank"): not here.
        for virtual in self.event_info():
            if virtual != '<<Redo>>':
                taken = [seq for seq in REDO_SEQUENCES if seq in self.event_info(virtual)]
                if taken:
                    self.event_delete(virtual, *taken)
        self.event_add('<<Redo>>', *REDO_SEQUENCES)

    def get_text(self) -> str:
        """The whole text, without Tk's trailing newline."""
        return self.get('1.0', 'end-1c')

    def apply_highlight(self, state: HighlightState) -> None:
        """Paint the session's highlight spans.

        Args:
            state: The latest highlighting from the session
        """
        self.highlight = state
        self.paint_spans(state.spans)

    def apply_edit(self, edit: TextEdited) -> None:
        """Apply an edit the session made (transpose, insert, open...).

        The undo policy decides how it goes into the undo history: ``group``
        is one undo step of its own, ``plain`` is like any edit, ``reset``
        clears the history. The edit is applied even while the editor is
        locked for playback (the session decides what may change), and it is
        not reported back to the session as typing.

        Args:
            edit: The splice, in code-point offsets
        """
        locked = str(self.cget('state')) == tk.DISABLED
        if locked:
            self.config(state=tk.NORMAL)
        try:
            start = f"1.0 + {edit.start} chars"
            if edit.undo is UndoPolicy.GROUP:
                autoseparators = self.cget('autoseparators')
                self.edit_separator()
                self.config(autoseparators=False)
                try:
                    self._splice(start, f"1.0 + {edit.end} chars", edit.replacement)
                finally:
                    self.config(autoseparators=autoseparators)
                    self.edit_separator()
            else:
                self._splice(start, f"1.0 + {edit.end} chars", edit.replacement)
                if edit.undo is UndoPolicy.RESET:
                    self.edit_reset()
            self.mark_set(tk.INSERT, f"1.0 + {edit.cursor} chars")
        finally:
            if locked:
                self.config(state=tk.DISABLED)
        # The session already has this text. <<Modified>> is delivered later
        # through the event queue and only sends the text when the flag is
        # set, so clearing it here keeps the edit from coming back as typing.
        self.edit_modified(False)

    def _splice(self, start: str, end: str, replacement: str) -> None:
        if self.compare(start, '<', end):
            self.delete(start, end)
        if replacement:
            self.insert(start, replacement)

    def paint_spans(self, spans: Iterable[Span]) -> None:
        """Replace the chord, directive and comment highlighting with ``spans``.

        The playing-chord highlight is left alone.

        Args:
            spans: Ranges to highlight, as code-point offsets
        """
        for tag in _SPAN_TAGS.values():
            self.tag_remove(tag, '1.0', tk.END)
        for span in spans:
            self.tag_add(_SPAN_TAGS[span.kind],
                         f"1.0 + {span.start} chars", f"1.0 + {span.end} chars")

    def offset_of(self, index: str) -> int:
        """The code-point offset of a Tk text index (e.g. ``insert``, ``3.4``).

        Args:
            index: Any Tk text index

        Returns:
            Characters from the start of the text to ``index``
        """
        return int(self.tk.call(self._w, 'count', '-chars', '1.0', index))

    def offset_at(self, x: int, y: int) -> int:
        """The code-point offset of the character at pixel ``(x, y)``.

        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
        """
        return self.offset_of(f"@{x},{y}")

    def _on_mouse_motion(self, event: Any) -> None:
        """Handle mouse motion - change cursor when over chords"""
        if self._session is None:
            return
        hit = self._session.chord_at(self.offset_at(event.x, event.y))
        over_chord = hit is not None and hit.kind is SpanKind.CHORD
        self.config(cursor='hand2' if over_chord else 'xterm')

    def _on_paste(self, event: Any) -> Optional[str]:
        """Handle paste - replace selection if any, normalizing the text"""
        # Get clipboard content, normalized: Tk inserts CR characters from
        # CRLF clipboards verbatim (they render as junk glyphs at line ends
        # and pollute the document), and text copied from websites often
        # carries non-breaking / zero-width spaces that break chord
        # detection. Always suppress the default paste: falling back to it
        # would insert the raw, unnormalized text.
        try:
            clipboard_text = normalize_song_text(self.clipboard_get())
        except tk.TclError:
            # Clipboard empty or unavailable - paste nothing rather than let
            # the default binding insert unnormalized text.
            return 'break'

        try:
            # Replace the selection if there is one
            if self.tag_ranges(tk.SEL):
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)

            # Insert at current cursor position. Like any edit, this fires
            # <<Modified>>, which sends the text to the session and re-arms
            # chord detection.
            self.insert(tk.INSERT, clipboard_text)
        except tk.TclError:
            pass
        return 'break'

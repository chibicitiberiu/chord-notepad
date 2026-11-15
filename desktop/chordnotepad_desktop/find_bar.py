"""The find bar under the text (Kate and Firefox's): the Python side.

``FindBar.qml`` is the bar; :class:`FindModel` decides what it shows and
does, over the core's :mod:`chordnotepad.session.text_ops` (the matching,
next match with wrap-around, go to line) and the session's commands (the
replacements):

* **Find:** :meth:`FindModel.setQuery` searches as the query is typed, from
  where the search started (the caret or the selection when the bar
  opened), and selects the match; Enter and F3 go to the next match, Shift
  with them to the previous one, wrapping around the text with a short
  notice. :attr:`countText` is "3 of 7" (the selection is the third match),
  "7 matches" or "No matches". Match case and whole word are toggles.
  While the bar is open every match is tinted in the text (the editor's
  ``find`` tint) and the selected one shows in the stronger find colour
  (:attr:`currentSelected`; QML swaps the selection colour).
* **Replace:** :meth:`replaceCurrent` replaces the selected match
  (``replace_match``) and selects the next one; when the selection isn't a
  match it goes to the next match first, as other editors do.
  :meth:`replaceAll` is ``replace_all``: one undo step, the status says how
  many. While a song plays the session refuses both and the status bar says
  why (its ``EditRefused``), as for any edit.
* **F3 with the bar closed** finds the last query again (:meth:`findAgain`).
* **Go to line** (the bar's other row): :meth:`goToLine`.

Positions to and from QML are Qt (UTF-16) positions; the session's
commands get code points (the editor's :class:`OffsetMapper`).
"""

import logging
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from chordnotepad.session import text_ops
from chordnotepad_desktop.offsets import OffsetMapper

logger = logging.getLogger(__name__)

#: How long the wrap-around notice shows.
NOTICE_MS = 2000
WRAPPED_DOWN = "Continued from the top"
WRAPPED_UP = "Continued from the bottom"
NO_MATCHES = "No matches"


def count_text(query: str, count: int, current: int) -> str:
    """What the bar says about the matches: "" for no query, "No matches",
    "3 of 7" when the selection is the third, else "7 matches"."""
    if not query:
        return ""
    if count == 0:
        return NO_MATCHES
    if current > 0:
        return f"{current} of {count}"
    return f"{count} match" + ("" if count == 1 else "es")


class FindModel(QObject):
    """The find bar's state and actions (see the module docstring).

    Args:
        store: The window's SessionStore (the replace commands).
        editor: The :class:`~chordnotepad_desktop.editor_bridge.EditorBridge`
            (the text, the selection, the tints).
    """

    changed = Signal()

    def __init__(self, store: Any, editor: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self._active = False
        self._query = ""
        self._match_case = False
        self._whole_word = False
        self._matches: List[Tuple[int, int]] = []     # code points, in the editor's text
        self._current = 0                             # 1-based; 0: the selection isn't one
        self._origin = 0                              # code point the typed search starts from
        self._notice = ""
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(NOTICE_MS)
        self._notice_timer.timeout.connect(self._clear_notice)
        editor.textChanged.connect(self._text_changed)

    # -- properties --------------------------------------------------------------------

    def _get_active(self) -> bool:
        return self._active

    #: The bar is open (the matches are tinted).
    active = Property(bool, _get_active, notify=changed)

    def _get_query(self) -> str:
        return self._query

    query = Property(str, _get_query, notify=changed)

    def _get_match_case(self) -> bool:
        return self._match_case

    def _set_match_case(self, on: bool) -> None:
        if bool(on) != self._match_case:
            self._match_case = bool(on)
            self._options_changed()

    matchCase = Property(bool, _get_match_case, _set_match_case, notify=changed)

    def _get_whole_word(self) -> bool:
        return self._whole_word

    def _set_whole_word(self, on: bool) -> None:
        if bool(on) != self._whole_word:
            self._whole_word = bool(on)
            self._options_changed()

    wholeWord = Property(bool, _get_whole_word, _set_whole_word, notify=changed)

    def _get_count(self) -> int:
        return len(self._matches)

    count = Property(int, _get_count, notify=changed)

    def _get_current(self) -> int:
        return self._current

    #: Which match the selection is (1-based), or 0.
    current = Property(int, _get_current, notify=changed)

    def _get_count_text(self) -> str:
        return count_text(self._query, len(self._matches), self._current)

    countText = Property(str, _get_count_text, notify=changed)

    def _get_no_match(self) -> bool:
        return bool(self._query) and not self._matches

    #: A query that matches nothing (the bar says so in red).
    noMatch = Property(bool, _get_no_match, notify=changed)

    def _get_current_selected(self) -> bool:
        return self._active and self._current > 0

    #: The selection is a match and the bar is open: it shows in the find colour.
    currentSelected = Property(bool, _get_current_selected, notify=changed)

    def _get_notice(self) -> str:
        return self._notice

    #: "Continued from the top" for a moment after a search wrapped around.
    notice = Property(str, _get_notice, notify=changed)

    def _get_line_count(self) -> int:
        return text_ops.line_count(self._editor.text)

    #: The text's lines, for Go to line's "of N".
    lineCount = Property(int, _get_line_count, notify=changed)

    # -- the editor's text and selection, in code points -------------------------------------

    def _text(self) -> str:
        return self._editor.text

    def _selection(self) -> Tuple[int, int, int]:
        """(start, end, caret) of the selection, in code points."""
        start, end, caret = self._editor.selection_range()
        mapper = OffsetMapper(self._text())
        return mapper.to_code_point(start), mapper.to_code_point(end), mapper.to_code_point(caret)

    def _select(self, span: Tuple[int, int]) -> None:
        mapper = OffsetMapper(self._text())
        self._editor.select_range(mapper.to_utf16(span[0]), mapper.to_utf16(span[1]))

    def _search(self) -> None:
        self._matches = text_ops.find_all(self._text(), self._query, self._match_case,
                                          self._whole_word)
        self._paint()

    def _paint(self) -> None:
        if not self._active:
            self._editor.set_find_spans([])
            return
        mapper = OffsetMapper(self._text())
        self._editor.set_find_spans([mapper.range_to_utf16(s, e) for s, e in self._matches])

    def _update_current(self) -> None:
        start, end, _ = self._selection()
        try:
            current = self._matches.index((start, end)) + 1 if start < end else 0
        except ValueError:
            current = 0
        if current != self._current:
            self._current = current
            self.changed.emit()

    # -- QML: opening and closing ---------------------------------------------------------

    @Slot(result=str)
    def begin(self) -> str:
        """The bar opens (Ctrl+F, Ctrl+H): the search starts from the
        selection (or the caret). Returns the selection's text to put in the
        find field when it is one line ("" otherwise)."""
        start, end, caret = self._selection()
        self._origin = start if start < end else caret
        self._active = True
        selected = self._text()[start:end]
        prefill = selected if selected and "\n" not in selected else ""
        self._search()
        self._update_current()
        self.changed.emit()
        return prefill

    @Slot()
    def end(self) -> None:
        """The bar closed: no tints; the query stays for F3."""
        if self._active:
            self._active = False
            self._paint()
            self.changed.emit()

    @Slot()
    def selectionMoved(self) -> None:  # noqa: N802 (Qt)
        """The editor's selection or caret moved: which match it is now."""
        if self._query:
            self._update_current()

    # -- QML: finding ---------------------------------------------------------------------

    @Slot(str)
    def setQuery(self, query: str) -> None:  # noqa: N802 (Qt)
        """The find field changed: search as it is typed, from where the
        search started; without a match the caret goes back there."""
        if query == self._query:
            return
        self._query = query
        self._search()
        if query:
            found = text_ops.next_match(self._matches, self._origin)
            if found is None:
                self._editor.move_caret(OffsetMapper(self._text()).to_utf16(self._origin))
            else:
                self._go(found)
        self._update_current()
        self.changed.emit()

    @Slot()
    def findNext(self) -> None:  # noqa: N802 (Qt)
        """Enter, F3, the ▼ button: the next match after the selection."""
        self._find(backward=False)

    @Slot()
    def findPrevious(self) -> None:  # noqa: N802 (Qt)
        """Shift+Enter, Shift+F3, the ▲ button: the match before the selection."""
        self._find(backward=True)

    @Slot(bool, result=bool)
    def findAgain(self, backward: bool) -> bool:  # noqa: N802 (Qt)
        """F3 / Shift+F3: the last query again, the bar open or not. False
        when there is no query yet (QML opens the bar then)."""
        if not self._query:
            return False
        self._search()
        self._find(backward)
        return True

    def _find(self, backward: bool) -> None:
        if not self._matches:
            self.changed.emit()
            return
        start, end, caret = self._selection()
        position = (start if start < end else caret) if backward else (end if start < end else caret)
        found = text_ops.next_match(self._matches, position, backward)
        if found is not None:
            self._go(found, backward)
            self._origin = self._matches[found[0]][0]
        self._update_current()
        self.changed.emit()

    def _go(self, found: Tuple[int, bool], backward: bool = False) -> None:
        index, wrapped = found
        self._select(self._matches[index])
        if wrapped:
            self._notice = WRAPPED_UP if backward else WRAPPED_DOWN
            self._notice_timer.start()

    def _clear_notice(self) -> None:
        if self._notice:
            self._notice = ""
            self.changed.emit()

    def _options_changed(self) -> None:
        """Match case or whole word toggled: search again from the selection's start."""
        self._search()
        if self._query and self._matches:
            start, _, caret = self._selection()
            found = text_ops.next_match(self._matches, min(start, caret))
            if found is not None:
                self._go(found)
        self._update_current()
        self.changed.emit()

    def _text_changed(self) -> None:
        if self._query and (self._active or self._matches):
            self._search()
            self._update_current()
            self.changed.emit()
        else:
            self.changed.emit()     # lineCount

    # -- QML: replacing -------------------------------------------------------------------

    @Slot(str)
    def replaceCurrent(self, replacement: str) -> None:  # noqa: N802 (Qt)
        """Replace: the selected match, then select the next one. When the
        selection isn't a match, go to the next match first."""
        self._search()
        self._update_current()
        if self._current == 0:
            self.findNext()
            return
        span = self._matches[self._current - 1]
        self._store.submit("replace_match", {
            "span": list(span), "query": self._query, "replacement": replacement,
            "match_case": self._match_case, "whole_word": self._whole_word})
        self._store.after_commands(self._after_replace)

    def _after_replace(self) -> None:
        # The session's edit is in (the caret after the replacement), or it
        # was refused (playing): either way, on to the next match.
        self._search()
        if self._matches:
            _, end, caret = self._selection()
            found = text_ops.next_match(self._matches, max(end, caret))
            if found is not None:
                self._go(found)
        self._update_current()
        self.changed.emit()

    @Slot(str)
    def replaceAll(self, replacement: str) -> None:  # noqa: N802 (Qt)
        """Replace all: one undo step; the status says how many."""
        if not self._query:
            return
        _, _, caret = self._selection()
        self._store.submit("replace_all", {
            "query": self._query, "replacement": replacement, "match_case": self._match_case,
            "whole_word": self._whole_word, "cursor": caret})

    # -- QML: go to line ------------------------------------------------------------------

    @Slot(str, result=bool)
    def goToLine(self, text: str) -> bool:  # noqa: N802 (Qt)
        """Go to line ``text`` (a number; clamped to the first and last line):
        the caret at its start. False when ``text`` isn't a number."""
        try:
            line = int(str(text).strip())
        except ValueError:
            return False
        offset = text_ops.line_offset(self._text(), line)
        self._editor.move_caret(OffsetMapper(self._text()).to_utf16(offset))
        return True

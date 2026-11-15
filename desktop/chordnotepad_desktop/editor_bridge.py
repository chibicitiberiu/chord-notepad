"""The editor's Python side: the song text between the QML TextArea and the session.

:class:`EditorBridge` is handed to the main window (``required property var
editor``) and attached to its TextArea's document by ``EditorPane.qml``. It
does what the Tk editor (``chordnotepad_tk/text_editor.py`` and the main
window's glue) does, through the bridge commands Android uses:

* **User edits** (typing, paste, undo, IME commits) go to the session as
  ``set_text`` with an increasing ``client_token``, on every change of the
  document's text. A change of formatting only (the highlighter, an IME
  pre-edit) isn't one: the text is compared, not trusted from the signal.
* **The session's edits** (``TextEdited``: transpose, inserts, open) are
  applied to the document with a ``QTextCursor`` per their undo policy and
  are not sent back. ``group`` is one undo step on its own (an edit block:
  Qt never merges a block with its neighbours), ``plain`` is like any edit
  (a replacement is still one step), ``reset`` clears the history. They
  apply while the editor is read-only too: ``readOnly`` only stops the
  user's input. The cursor goes where the edit says; an edit with an
  ``anchor`` (plan step B4, on main) selects from it to the cursor.
* **Highlighting:** ``HighlightState`` spans are painted by
  :class:`SpanHighlighter`, a ``QSyntaxHighlighter``. A state is painted
  only when it was computed for the text the editor shows (its
  ``client_token`` and, for the session's own edits, its ``text_revision``;
  the Android ``TextIdentity`` rule). Until then the painted spans move with
  each edit the way Tk's tags do (:func:`shift_spans`).
* **Playback:** the sounding chord gets the playing format on top of the
  rest, repainted only when ``(span, chord_index, bar)`` changes, and
  ``playingMoved`` tells QML to scroll to it. ``playheadPos`` places the
  playhead marker.
* **Paste normalisation** on every path QML routes here (Ctrl+V, Shift+Insert,
  the context menu, middle-click PRIMARY, drag and drop): the core's
  ``normalize_song_text``, as Tk's ``_on_paste``.

Offsets: the session counts code points, Qt UTF-16 units
(:class:`~chordnotepad_desktop.offsets.OffsetMapper`). Every position QML
passes in or gets back is a Qt (UTF-16) position.

Qt Quick pitfall 8: the ``QQuickTextDocument`` wrapper is kept in
``self._quick_document``; without a Python reference it is collected and the
``QTextDocument`` behind it goes with it.
"""

import logging
from bisect import bisect_left
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import Q_ARG, Property, QMetaObject, QObject, Qt, Signal, Slot
from PySide6.QtGui import (
    QClipboard, QColor, QCursor, QGuiApplication, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
    QTextDocument,
)
from PySide6.QtQuick import QQuickItem, QQuickTextDocument

from chordnotepad.constants import DEFAULT_FONT_SIZE
from chordnotepad.session import snippets
from chordnotepad.utils.text_normalization import normalize_song_text
from chordnotepad_desktop import editor_font, popups
from chordnotepad_desktop.find_bar import FindModel
from chordnotepad_desktop.offsets import OffsetMapper, utf16_length
from chordnotepad_desktop.text_mouse import TextMouse

logger = logging.getLogger(__name__)

#: How strongly a redundant directive's colour shows over the background
#: (Tk's ``DIRECTIVE_REDUNDANT_STRENGTH``, ``chordnotepad_tk/theme.py``).
REDUNDANT_STRENGTH = 0.45
#: One zoom step of the mouse wheel, in angle-delta units (one notch).
WHEEL_NOTCH = 120

#: The highlight kinds, as HighlightState names them.
CHORD = "chord"
COMMENT = "comment"


@dataclass(frozen=True)
class TextChange:
    """``[start, old_end)`` of the old text became ``[start, new_end)`` (UTF-16)."""

    start: int
    old_end: int
    new_end: int

    @property
    def delta(self) -> int:
        return self.new_end - self.old_end


#: A painted span: ``(start, end, kind)`` in UTF-16 positions of the document.
PaintedSpan = Tuple[int, int, str]


def diff_texts(old: str, new: str) -> Optional[TextChange]:
    """The smallest change that turns ``old`` into ``new``, in UTF-16 units;
    None when they are equal (the common prefix and suffix are kept)."""
    if old == new:
        return None
    limit = min(len(old), len(new))
    prefix = 0
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < limit - prefix and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]:
        suffix += 1
    start = utf16_length(old[:prefix])
    return TextChange(start, start + utf16_length(old[prefix:len(old) - suffix]),
                      start + utf16_length(new[prefix:len(new) - suffix]))


def shift_spans(spans: Sequence[PaintedSpan], change: TextChange) -> List[PaintedSpan]:
    """``spans`` moved along with ``change``, the way Tk text tags move.

    Text after the change shifts; text typed at a span's edge stays outside
    it; text typed inside a span joins it; a span whose text was all
    removed disappears. It keeps the old highlighting about right until the
    session's next HighlightState replaces it (half a second after typing
    stops). The Android app's ``shiftedBy``.
    """
    def start_of(x: int) -> int:
        if x < change.start:
            return x
        if x >= change.old_end:
            return x + change.delta
        return change.new_end        # its first characters were replaced

    def end_of(x: int) -> int:
        if x <= change.start:
            return x
        if x >= change.old_end:
            return x + change.delta
        return change.start          # its last characters were replaced

    moved = []
    for start, end, kind in spans:
        new_start, new_end = start_of(start), end_of(end)
        if new_end > new_start:
            moved.append((new_start, new_end, kind))
    return moved


def blend(fg: QColor, bg: QColor, strength: float) -> QColor:
    """``fg`` laid over ``bg`` at ``strength`` (0-1)."""
    return QColor.fromRgbF(fg.redF() * strength + bg.redF() * (1 - strength),
                           fg.greenF() * strength + bg.greenF() * (1 - strength),
                           fg.blueF() * strength + bg.blueF() * (1 - strength))


def char_formats(palette: Dict[str, Any]) -> Dict[str, QTextCharFormat]:
    """The format of each highlight kind (and ``"playing"``) for ``palette``.

    ``palette`` holds Theme's editor colours (``EditorPane.palette()``):
    chord, chordInvalid, directive, directiveInvalid, comment, playing,
    editorText, editorBg. The look is Tk's (checklist §5): chords blue and
    underlined, invalid chords grey and underlined, directives purple,
    invalid ones red and underlined, redundant ones faded 45% into the
    background, comments grey; the playing chord on a yellow background
    with the editor's text colour, underlined, over everything.
    """
    colour = {name: QColor(value) for name, value in palette.items()}

    def fmt(fg: QColor, underline: bool = False, background: Optional[QColor] = None):
        f = QTextCharFormat()
        f.setForeground(fg)
        if underline:
            f.setFontUnderline(True)
            f.setUnderlineColor(fg)
        if background is not None:
            f.setBackground(background)
        return f

    return {
        "chord": fmt(colour["chord"], underline=True),
        "chord_invalid": fmt(colour["chordInvalid"], underline=True),
        "directive": fmt(colour["directive"]),
        "directive_invalid": fmt(colour["directiveInvalid"], underline=True),
        "directive_redundant": fmt(blend(colour["directive"], colour["editorBg"], REDUNDANT_STRENGTH)),
        "comment": fmt(colour["comment"]),
        "playing": fmt(colour["editorText"], underline=True, background=colour["playing"]),
    }


def tint_colours(palette: Dict[str, Any]) -> Dict[str, QColor]:
    """The tints' backgrounds for ``palette``: ``findMatch`` for the find
    bar's matches, ``occurrence`` for a selected word's other occurrences
    (missing ones are left out, so nothing is tinted)."""
    names = {"find": "findMatch", "occurrence": "occurrence"}
    return {kind: QColor(palette[name]) for kind, name in names.items() if name in palette}


class SpanHighlighter(QSyntaxHighlighter):
    """Paints the bridge's spans, comments over the rest, the playing chord on top."""

    def __init__(self, document: QTextDocument, bridge: "EditorBridge") -> None:
        super().__init__(document)
        self._bridge = bridge
        self.formats: Dict[str, QTextCharFormat] = {}
        #: The background of each tint kind ("find", "occurrence").
        self.tints: Dict[str, QColor] = {}

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt)
        block = self.currentBlock()
        first = block.position()
        last = first + block.length() - 1         # without the line's separator
        later = []
        for start, end, kind in self._bridge.spans_between(first, last):
            if kind == COMMENT:
                later.append((start, end, kind))   # comments win on overlap
            else:
                self._paint(first, last, start, end, kind)
        for start, end, kind in later:
            self._paint(first, last, start, end, kind)
        # The find bar's matches and a selected word's occurrences: a
        # background over whatever the text has (occurrences first, find wins).
        for start, end, kind in self._bridge.tints_between(first, last):
            self._tint(first, last, start, end, kind)
        playing = self._bridge.playing_range
        if playing is not None:
            self._paint(first, last, playing[0], playing[1], "playing")

    def _tint(self, first: int, last: int, start: int, end: int, kind: str) -> None:
        colour = self.tints.get(kind)
        if colour is None:
            return
        for pos in range(max(start, first), min(end, last)):
            fmt = self.format(pos - first)
            fmt.setBackground(colour)
            self.setFormat(pos - first, 1, fmt)

    def _paint(self, first: int, last: int, start: int, end: int, kind: str) -> None:
        start, end = max(start, first), min(end, last)
        fmt = self.formats.get(kind)
        if end > start and fmt is not None:
            self.setFormat(start - first, end - start, fmt)


class EditorBridge(QObject):
    """The song text between the QML editor and the session (see the module docstring).

    Args:
        store: The window's :class:`~chordnotepad_desktop.session_store.SessionStore`.
    """

    #: The editor's look changed: fontFamily, fontSize, zoomPercent.
    fontChanged = Signal()
    #: readOnly or wordWrap changed.
    modeChanged = Signal()
    #: The playing chord moved (playingStart / playingEnd).
    playingChanged = Signal()
    #: A chord started sounding at this position: scroll to it.
    playingMoved = Signal(int)
    #: The playhead moved (playheadPos).
    playheadChanged = Signal()
    #: Scroll the text to the playhead's chord (a click in the chord sheet or
    #: on the seek bar): its position.
    revealRequested = Signal(int)
    #: The session put the cursor here (after one of its edits).
    cursorMoved = Signal(int)
    #: Another document's text came in (open, New, a restored draft: a
    #: ``reset`` edit). The view goes back to the top, as Tk's does: the
    #: session puts the cursor after the text, and Tk moves its insert mark
    #: there without scrolling, so a song opens at its first line. Qt's
    #: caret is visible (and the view follows it), so it goes to the start.
    documentReset = Signal()
    #: The text changed: typed, pasted or the session's edit. (TextArea's
    #: textChanged also fires when only the highlighting changed.)
    textChanged = Signal()

    def __init__(self, store: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._area: Optional[QQuickItem] = None
        self._quick_document: Optional[QQuickTextDocument] = None   # pitfall 8
        self._document: Optional[QTextDocument] = None
        self._highlighter: Optional[SpanHighlighter] = None
        self._palette: Dict[str, Any] = {}
        # Edits that arrived before QML attached the document.
        self._early_edits: List[dict] = []

        # The text the painted spans are laid out for (the document's text),
        # and what the session has, as far as the editor knows.
        self._painted_text = ""
        self._synced_text = ""
        self._spans: List[PaintedSpan] = []
        self._span_starts: List[int] = []
        self._longest_span = 0
        self._applying = False      # inside a session edit: don't send it back
        self._repainting = False    # inside our own rehighlight: no text change
        # The text's identity in the session's terms: (client_token, revision).
        self._token = 0
        self._identity: Tuple[int, Optional[int]] = (0, None)
        self._pending_texts = 0     # set_text commands the session hasn't run yet
        self._latest_highlight: Optional[dict] = None
        self._applied_highlight: Optional[dict] = None

        self._font_family = editor_font.editor_monospace()
        self._font_size = DEFAULT_FONT_SIZE
        self._asked_size: Optional[int] = None     # a zoom the session hasn't applied yet
        self._read_only = False
        self._word_wrap = False
        self._playing: Optional[Tuple[int, int]] = None   # UTF-16, for the highlighter
        self._playing_progress: Any = None
        self._playhead = -1
        self._drag_cursor = False          # setDragCursor's override is on
        # Tints (UTF-16 spans): the find bar's matches, a selected word's occurrences.
        self._tint_spans: Dict[str, List[Tuple[int, int]]] = {"find": [], "occurrence": []}
        self._tints: List[PaintedSpan] = []
        self._tint_starts: List[int] = []
        self._longest_tint = 0
        self._finder = FindModel(store, self, parent=self)

        store.event.connect(self._on_event)
        store.stateChanged.connect(self._on_state)
        # The session replayed its states into the store when it was made.
        for name in ("EditorState", "HighlightState", "PlaybackState"):
            self._on_state(name)

    # -- attaching (QML) --------------------------------------------------------------

    @Slot(QQuickItem, QQuickTextDocument, "QVariantMap")
    def attach(self, area: QQuickItem, document: QQuickTextDocument, palette: dict) -> None:
        """Take over ``area``'s document (EditorPane's Component.onCompleted)."""
        self._area = area
        area.destroyed.connect(self._area_gone)
        # Presses reach the text at once, and a drag held past the edge scrolls (pitfall 29).
        self._mouse_filter = TextMouse(area)
        area.installEventFilter(self._mouse_filter)
        self._quick_document = document
        self._document = document.textDocument()
        self._painted_text = self._synced_text = self._document.toPlainText()
        # Connected before the highlighter: the spans must have moved when it
        # re-formats the changed block (slots run in connection order).
        self._document.contentsChange.connect(self._on_contents_change)
        self._highlighter = SpanHighlighter(self._document, self)
        self.setPalette(palette)
        edits, self._early_edits = self._early_edits, []
        for edit in edits:
            self._apply_edit(edit)

    def _area_gone(self) -> None:
        # The window went first (shutdown): a late timer must not reach it.
        self._area = None

    @Slot(QQuickItem, result=bool)
    def modalPopupOpen(self, overlay: QQuickItem) -> bool:
        """Whether the window whose ``Overlay.overlay`` this is shows a modal
        dialog: the editor must not take the keys from it
        (EditorPane.focusEditor)."""
        return popups.modal_popup_open(overlay)

    @Slot("QVariantMap")
    def setPalette(self, palette: dict) -> None:  # noqa: N802 (Qt)
        """New editor colours (the theme switched)."""
        self._palette = {k: v.name(QColor.NameFormat.HexArgb) if isinstance(v, QColor) else str(v)
                         for k, v in palette.items()}
        if self._highlighter is not None:
            self._highlighter.formats = char_formats(self._palette)
            self._highlighter.tints = tint_colours(self._palette)
            self._rehighlight()

    @property
    def document(self) -> Optional[QTextDocument]:
        """The editor's document (None before QML attached it)."""
        return self._document

    # -- properties for QML -----------------------------------------------------------

    def _get_font_family(self) -> str:
        return self._font_family

    #: The family to draw the text in (editor_font.resolve_family).
    fontFamily = Property(str, _get_font_family, notify=fontChanged)

    def _get_font_size(self) -> int:
        return self._font_size

    #: The text size in points (EditorState.font_size).
    fontSize = Property(int, _get_font_size, notify=fontChanged)

    def _get_zoom_percent(self) -> int:
        return editor_font.zoom_percent(self._font_size)

    #: What the zoom chip shows (resolution 3).
    zoomPercent = Property(int, _get_zoom_percent, notify=fontChanged)

    def _get_read_only(self) -> bool:
        return self._read_only

    #: Read-only while a song plays or is paused (EditorState.read_only).
    readOnly = Property(bool, _get_read_only, notify=modeChanged)

    def _get_word_wrap(self) -> bool:
        return self._word_wrap

    #: Whether long lines wrap (EditorState.word_wrap).
    wordWrap = Property(bool, _get_word_wrap, notify=modeChanged)

    def _get_playing_start(self) -> int:
        return self._playing[0] if self._playing else -1

    #: Where the sounding chord starts, or -1.
    playingStart = Property(int, _get_playing_start, notify=playingChanged)

    def _get_playing_end(self) -> int:
        return self._playing[1] if self._playing else -1

    playingEnd = Property(int, _get_playing_end, notify=playingChanged)

    def _get_playhead(self) -> int:
        return self._playhead

    #: Where ▶ starts (PlaybackState.playhead_offset), or -1 for none.
    playheadPos = Property(int, _get_playhead, notify=playheadChanged)

    # -- for the highlighter ----------------------------------------------------------

    @property
    def playing_range(self) -> Optional[Tuple[int, int]]:
        return self._playing

    def spans_between(self, first: int, last: int) -> List[PaintedSpan]:
        """The painted spans that touch ``[first, last]``, in text order."""
        lo = bisect_left(self._span_starts, first - self._longest_span)
        hi = bisect_left(self._span_starts, last + 1)
        return [s for s in self._spans[lo:hi] if s[1] > first and s[0] < last]

    def tints_between(self, first: int, last: int) -> List[PaintedSpan]:
        """The tints that touch ``[first, last]``: occurrences, then find matches."""
        lo = bisect_left(self._tint_starts, first - self._longest_tint)
        hi = bisect_left(self._tint_starts, last + 1)
        found = [t for t in self._tints[lo:hi] if t[1] > first and t[0] < last]
        return sorted(found, key=lambda t: t[2] != "occurrence")

    @property
    def tints(self) -> Dict[str, List[Tuple[int, int]]]:
        """The tinted spans by kind (UTF-16 positions)."""
        return {kind: list(spans) for kind, spans in self._tint_spans.items()}

    def _set_tints(self, kind: str, spans: List[Tuple[int, int]]) -> None:
        old = self._tint_spans[kind]
        spans = sorted(spans)
        if spans == old:
            return
        self._tint_spans[kind] = spans
        self._index_tints()
        # Repaint the lines the tints were on and are on now.
        self._rehighlight_at([s for s, _ in old] + [s for s, _ in spans])

    def _index_tints(self) -> None:
        self._tints = sorted((s, e, k) for k, ks in self._tint_spans.items() for s, e in ks)
        self._tint_starts = [t[0] for t in self._tints]
        self._longest_tint = max((e - s for s, e, _ in self._tints), default=0)

    def _shift_tints(self, change: TextChange) -> None:
        """The tints moved with an edit, until their owner works them out again."""
        if not self._tints:
            return
        for kind, spans in self._tint_spans.items():
            self._tint_spans[kind] = [(s, e) for s, e, _ in shift_spans([(s, e, kind) for s, e in spans],
                                                                       change)]
        self._index_tints()

    def set_find_spans(self, spans: List[Tuple[int, int]]) -> None:
        """Tint the find bar's matches (UTF-16 spans; [] for none)."""
        self._set_tints("find", spans)

    @property
    def spans(self) -> List[PaintedSpan]:
        """The spans painted now (UTF-16 positions)."""
        return list(self._spans)

    def _set_spans(self, spans: List[PaintedSpan]) -> None:
        self._spans = sorted(spans)
        self._span_starts = [s[0] for s in self._spans]
        self._longest_span = max((e - s for s, e, _ in self._spans), default=0)

    def _rehighlight(self) -> None:
        if self._highlighter is None:
            return
        self._repainting = True
        try:
            self._highlighter.rehighlight()
        finally:
            self._repainting = False

    def _rehighlight_at(self, positions) -> None:
        if self._highlighter is None or self._document is None:
            return
        self._repainting = True
        try:
            seen = set()
            for pos in positions:
                block = self._document.findBlock(pos)
                if block.isValid() and block.blockNumber() not in seen:
                    seen.add(block.blockNumber())
                    self._highlighter.rehighlightBlock(block)
        finally:
            self._repainting = False

    # -- the document changed -----------------------------------------------------------

    def _on_contents_change(self, position: int, removed: int, added: int) -> None:
        if self._repainting or self._document is None:
            return
        text = self._document.toPlainText()
        if text == self._painted_text:
            return              # formats only (the highlighter, an IME pre-edit)
        old = self._painted_text
        change = TextChange(position, position + removed, position + added)
        # Qt's numbers count the document's last paragraph mark in some
        # changes (setPlainText, removing everything): then work it out.
        if not (0 <= position and change.old_end <= utf16_length(old)
                and utf16_length(text) - utf16_length(old) == added - removed):
            change = diff_texts(old, text)
        self._set_spans(shift_spans(self._spans, change))
        self._shift_tints(change)
        self._painted_text = text
        if not self._applying:
            self._send_text(text)
        self.textChanged.emit()

    def _send_text(self, text: str) -> None:
        """Hand the user's text to the session under a new token."""
        self._token += 1
        self._identity = (self._token, None)
        self._synced_text = text
        self._pending_texts += 1
        self._store.submit("set_text", {"text": text, "client_token": self._token})
        # Runs once the session has run every command queued so far.
        self._store.after_commands(self._text_delivered)

    def _text_delivered(self) -> None:
        self._pending_texts -= 1

    # -- the session's outputs ----------------------------------------------------------

    def _on_event(self, type_name: str, data: Any) -> None:
        if type_name == "TextEdited":
            if self._document is None:
                self._early_edits.append(dict(data))
            else:
                self._apply_edit(dict(data))

    def _on_state(self, type_name: str) -> None:
        if type_name == "EditorState":
            self._take_editor_state(self._read_state(type_name))
        elif type_name == "HighlightState":
            state = self._read_state(type_name)
            if state.get("spans") is not None:
                self._latest_highlight = state
                self._repaint_highlight()
        elif type_name == "PlaybackState":
            self._take_playback(self._read_state(type_name))

    def _read_state(self, type_name: str) -> dict:
        mapping = self._store.state(type_name)
        return {key: mapping.value(key) for key in mapping.keys()}

    def _take_editor_state(self, state: dict) -> None:
        if state.get("font_size") is None:
            return              # not published yet
        family = editor_font.resolve_family(state.get("font_family"))
        size = int(state["font_size"])
        self._asked_size = None
        if (family, size) != (self._font_family, self._font_size):
            self._font_family, self._font_size = family, size
            self.fontChanged.emit()
        read_only, wrap = bool(state.get("read_only")), bool(state.get("word_wrap"))
        if (read_only, wrap) != (self._read_only, self._word_wrap):
            self._read_only, self._word_wrap = read_only, wrap
            self.modeChanged.emit()

    def _apply_edit(self, edit: dict) -> None:
        """Apply one of the session's edits per its undo policy, without echoing it."""
        document = self._document
        before = self._painted_text
        mapper = OffsetMapper(before)
        start, end = mapper.to_utf16(edit["start"]), mapper.to_utf16(edit["end"])
        replacement = edit["replacement"]
        policy = edit["undo"]
        # The user typed something the session hasn't run yet: the edit was
        # made on the session's older text. The editor's text wins: send it
        # again after the edit, so the session ends up with what is shown.
        unsent = self._pending_texts > 0
        self._applying = True
        try:
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            # An edit block is one undo step that Qt never merges with the
            # typing around it ("group"). A replacement is one step anyway
            # (insertText over a selection); a plain insert may join the typing.
            grouped = policy == "group"
            if grouped:
                cursor.beginEditBlock()
            if replacement:
                cursor.insertText(replacement)
            elif start != end:
                cursor.removeSelectedText()
            if grouped:
                cursor.endEditBlock()
        finally:
            self._applying = False
        after = document.toPlainText()
        self._painted_text = after
        if policy == "reset":
            document.clearUndoRedoStacks()
        if unsent:
            self._send_text(after)
        else:
            self._synced_text = after
            self._identity = (0, edit["text_revision"])
        mapper = OffsetMapper(after)
        anchor = edit.get("anchor")
        if policy == "reset":
            # Another document: the caret at its start, nothing selected (the
            # session's cursor is after the text, where Tk's unseen insert
            # mark goes; here the caret would take the view to the end).
            self._move_cursor(0)
        elif anchor is not None and self._area is not None:
            # The edit selects what it inserted (B4's insert_snippet: the
            # value), from ``anchor`` to the cursor, so typing replaces it.
            QMetaObject.invokeMethod(self._area, "select",
                                     Q_ARG(int, mapper.to_utf16(anchor)),
                                     Q_ARG(int, mapper.to_utf16(edit["cursor"])))
            self.cursorMoved.emit(mapper.to_utf16(edit["cursor"]))
        else:
            self._move_cursor(mapper.to_utf16(edit["cursor"]))
        if policy == "reset":
            self.documentReset.emit()
        self._repaint_highlight()
        self._repaint_playing()

    def _move_cursor(self, position: int) -> None:
        if self._area is not None:
            self._area.setProperty("cursorPosition", position)
        self.cursorMoved.emit(position)

    def _accepts(self, state: dict) -> bool:
        """Whether ``state``'s spans were computed for the text shown."""
        token, revision = self._identity
        return state["client_token"] == token and (revision is None
                                                   or state["text_revision"] == revision)

    @property
    def highlight_current(self) -> bool:
        """Whether the painted spans are the session's for the text shown
        (none typed or edited since)."""
        state = self._applied_highlight
        return (state is not None and self._accepts(state)
                and self._painted_text == self._synced_text)

    def _repaint_highlight(self) -> None:
        state = self._latest_highlight
        if state is None or state is self._applied_highlight or self._document is None:
            return
        if not self._accepts(state):
            return              # spans for another text: wait for the next state
        if self._painted_text != self._synced_text:
            return
        mapper = OffsetMapper(self._painted_text)
        painted = []
        for span in state["spans"] or ():
            start, end = mapper.range_to_utf16(span["start"], span["end"])
            if end > start:
                painted.append((start, end, span["kind"]))
        self._set_spans(painted)
        self._applied_highlight = state
        self._rehighlight()

    def _take_playback(self, state: dict) -> None:
        span = state.get("playing_span")
        progress = (None if span is None else (span["start"], span["end"]),
                    state.get("chord_index"), state.get("bar"))
        if progress != self._playing_progress:
            self._playing_progress = progress
            self._repaint_playing(scroll=True)
        offset = state.get("playhead_offset")
        playhead = -1 if offset is None else OffsetMapper(self._painted_text).to_utf16(offset)
        if playhead != self._playhead:
            self._playhead = playhead
            self.playheadChanged.emit()

    def _repaint_playing(self, scroll: bool = False) -> None:
        cps = self._playing_progress[0] if self._playing_progress else None
        old = self._playing
        new = None if cps is None else OffsetMapper(self._painted_text).range_to_utf16(*cps)
        if new == old:
            return
        self._playing = new
        self._rehighlight_at([r[0] for r in (old, new) if r is not None])
        self.playingChanged.emit()
        if scroll and new is not None:
            self.playingMoved.emit(new[0])

    # -- for the hints and the pickers (status_bar.py, value_picker.py) -------------------

    @property
    def in_step(self) -> bool:
        """Whether the session has the text shown: no ``set_text`` still
        queued, so its offsets and the editor's agree (lookups wait for that)."""
        return (self._document is not None and self._pending_texts == 0
                and self._painted_text == self._synced_text)

    @property
    def text(self) -> str:
        """The text shown (as the painted spans and the offsets know it)."""
        return self._painted_text

    def cursor_position(self) -> Optional[int]:
        """The caret's Qt position; None before QML attached the editor."""
        if self._area is None:
            return None
        return int(self._area.property("cursorPosition"))

    def to_code_point(self, position: int) -> int:
        """The session's offset for Qt position ``position``."""
        return OffsetMapper(self._painted_text).to_code_point(position)

    def to_utf16(self, offset: int) -> int:
        """The Qt position of the session's offset ``offset``."""
        return OffsetMapper(self._painted_text).to_utf16(offset)

    def char_offset(self, position: int) -> Optional[int]:
        """The session's offset of the character at Qt position ``position``
        (one the pointer is over), or None past the text or on a line's end:
        nothing hovers past the end of a line."""
        if position < 0:
            return None
        offset = self.to_code_point(position)
        text = self._painted_text
        if offset >= len(text) or text[offset] == "\n":
            return None
        return offset

    @Slot(int, result="QVariantMap")
    def hintAt(self, position: int) -> dict:  # noqa: N802 (Qt)
        """The hover card for the character at Qt position ``position``:
        the directive's ``start``/``end`` (Qt positions), its ``message``
        (why it is invalid or has no effect, or ""), ``redundant`` and
        ``syntax`` (one line per directive a half-typed keyword could become).
        Empty when the character isn't inside a directive, past a line's end,
        or while the session hasn't got the text shown yet."""
        offset = self.char_offset(position)
        if offset is None or self._store.closed or not self.in_step:
            return {}
        hint = self._store.direct("directive_hint_at", offset)
        if not hint.syntax or not hint.start <= offset < hint.end:
            return {}       # a directive being typed ends at the offset: not hovered
        mapper = OffsetMapper(self._painted_text)
        return {"start": mapper.to_utf16(hint.start), "end": mapper.to_utf16(hint.end),
                "keyword": hint.keyword, "message": hint.message, "syntax": hint.syntax,
                "redundant": bool(hint.redundant)}

    # -- for QML: the user's actions ---------------------------------------------------

    @Slot(int, result=int)
    def codePointAt(self, position: int) -> int:  # noqa: N802 (Qt)
        """The session's offset for Qt position ``position``."""
        return self.to_code_point(position)

    @Slot(int, result=bool)
    def isChordAt(self, position: int) -> bool:  # noqa: N802 (Qt)
        """Whether the character at ``position`` is part of a valid chord, as
        painted (the last detection, moved with the typing since)."""
        if position < 0:
            return False
        return any(kind == CHORD and start <= position < end
                   for start, end, kind in self.spans_between(position, position + 1))

    @Slot(int)
    def tapAt(self, position: int) -> None:  # noqa: N802 (Qt)
        """A click on the character at ``position``: the session sounds the
        chord there, if any, and moves the playhead (or seeks while playing).
        With Shift held the chord sounds rolled, one note at a time (the
        modifiers of the click, read here: the editor's TapHandler passes
        only the position)."""
        if position >= 0:
            args = {"offset": self.codePointAt(position)}
            if QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                args["rolled"] = True
            self._store.submit("tap_chord_at", args)

    @Slot()
    def revealPlayhead(self) -> None:  # noqa: N802 (Qt)
        """Scroll the text to the playhead's chord once the session has run the
        commands submitted so far (the click's audition or seek moves it)."""
        self._store.after_commands(self._reveal_playhead)

    def _reveal_playhead(self) -> None:
        if self._playhead >= 0:
            self.revealRequested.emit(self._playhead)

    @Slot()
    def paste(self) -> None:
        """Paste the clipboard over the selection, normalised (Ctrl+V,
        Shift+Insert, the context menu)."""
        if self._area is None:
            return
        start = int(self._area.property("selectionStart"))
        end = int(self._area.property("selectionEnd"))
        self._insert_user_text(start, end, QGuiApplication.clipboard().text())

    @Slot(int)
    def pasteSelectionAt(self, position: int) -> None:  # noqa: N802 (Qt)
        """Paste the X11/Wayland PRIMARY selection at ``position`` (middle click), normalised."""
        text = self._selection_text()
        if text is not None:
            self._insert_user_text(position, position, text)

    @staticmethod
    def _selection_text() -> Optional[str]:
        """The PRIMARY selection's text; None where there is no such thing."""
        clipboard = QGuiApplication.clipboard()
        if not clipboard.supportsSelection():
            return None
        return clipboard.text(QClipboard.Mode.Selection)

    @Slot(int, str)
    def dropText(self, position: int, text: str) -> None:  # noqa: N802 (Qt)
        """Text dragged onto the editor, at ``position``, normalised."""
        self._insert_user_text(position, position, text)

    # -- keys the TextArea doesn't handle as other editors do (EditorPane's Keys) -------

    @Slot()
    def typeNewline(self) -> None:  # noqa: N802 (Qt)
        """A new line over the selection, for Ctrl+Enter and Shift+Enter (Qt
        does nothing for the first and puts a line separator, not a new
        paragraph, for the second): what Enter does, one undo step like it."""
        if self._area is None or self._document is None or self._read_only:
            return
        cursor = QTextCursor(self._document)
        cursor.setPosition(int(self._area.property("selectionStart")))
        cursor.setPosition(int(self._area.property("selectionEnd")), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertBlock()
        self._area.setProperty("cursorPosition", cursor.position())

    @Slot(int, result=int)
    def homePosition(self, position: int) -> int:  # noqa: N802 (Qt)
        """Where Home goes from Qt position ``position``: on a line's first
        row, its first non-blank character, or the line's start when the
        caret is already there (so Home toggles between the two); on the
        later rows of a wrapped line, the row's start."""
        if self._document is None:
            return position
        block = self._document.findBlock(position)
        if not block.isValid():
            return position
        start = block.position()
        layout = block.layout()
        if layout is not None and layout.lineCount() > 0:
            row = layout.lineForTextPosition(position - start)
            if row.isValid() and row.lineNumber() > 0:
                return start + row.textStart()
        text = block.text()
        indent = len(text) - len(text.lstrip(" \t"))
        first = start + indent if indent < len(text) else start
        return start if position == first else first

    # -- the selection, for the find bar (find_bar.py) ---------------------------------------

    def _get_finder(self) -> QObject:
        return self._finder

    #: The find bar's FindModel (find_bar.py).
    finder = Property(QObject, _get_finder, constant=True)

    def selection_range(self) -> Tuple[int, int, int]:
        """``(selectionStart, selectionEnd, cursorPosition)`` (Qt positions);
        zeros before QML attached the editor."""
        if self._area is None:
            return 0, 0, 0
        return (int(self._area.property("selectionStart")), int(self._area.property("selectionEnd")),
                int(self._area.property("cursorPosition")))

    def select_range(self, anchor: int, cursor: int) -> None:
        """Select ``anchor``..``cursor`` (Qt positions), the caret at ``cursor``;
        the view follows the caret."""
        if self._area is not None:
            QMetaObject.invokeMethod(self._area, "select", Q_ARG(int, anchor), Q_ARG(int, cursor))

    def move_caret(self, position: int) -> None:
        """Put the caret at Qt position ``position``, nothing selected."""
        if self._area is not None:
            self._area.setProperty("cursorPosition", position)

    @Slot()
    def selectionMoved(self) -> None:  # noqa: N802 (Qt)
        """The TextArea's selection or caret moved (EditorPane)."""
        self._finder.selectionMoved()

    # -- drag and drop from the sidebars (the palette tiles, the identifier's chords) ---

    @Slot(int, result=int)
    def dropPosition(self, position: int) -> int:  # noqa: N802 (Qt)
        """Where a tile or chord dropped at Qt position ``position`` goes in
        (the drop caret): out of the middle of a word or directive, as
        ``insert_snippet`` with ``snap`` puts it (``snippets.drop_offset``)."""
        if position < 0:
            return position
        mapper = OffsetMapper(self._painted_text)
        return mapper.to_utf16(snippets.drop_offset(self._painted_text, mapper.to_code_point(position)))

    @Slot(int, str, result=bool)
    def dropSnippet(self, position: int, text: str) -> bool:  # noqa: N802 (Qt)
        """Drop ``text`` (a tile's snippet, or a chord) at Qt position
        ``position``: ``insert_snippet`` with ``snap``, one undo step, spaced
        off its neighbours, a directive's value selected. False (nothing
        sent) while a song plays or is paused, or for no text."""
        if self._read_only or not text or position < 0:
            return False
        self._store.submit("insert_snippet", {"offset": self.to_code_point(position), "text": text,
                                              "snap": True})
        return True

    @Slot(bool)
    def setDragCursor(self, allowed: bool) -> None:  # noqa: N802 (Qt)
        """The pointer during a drag from a sidebar: the closed hand where it
        can drop, the no-drop sign elsewhere (the whole window's, so the
        items under it don't change it)."""
        cursor = QCursor(Qt.CursorShape.ClosedHandCursor if allowed else Qt.CursorShape.ForbiddenCursor)
        if self._drag_cursor:
            QGuiApplication.changeOverrideCursor(cursor)
        else:
            QGuiApplication.setOverrideCursor(cursor)
            self._drag_cursor = True

    @Slot()
    def clearDragCursor(self) -> None:  # noqa: N802 (Qt)
        """The drag is over: the pointer is the items' own again."""
        if self._drag_cursor:
            QGuiApplication.restoreOverrideCursor()
            self._drag_cursor = False

    def _insert_user_text(self, start: int, end: int, raw: Optional[str]) -> None:
        """Replace ``[start, end)`` with ``raw`` normalised, as the user's
        edit: one undo step, cursor after it, sent to the session."""
        if self._document is None or self._read_only:
            return
        text = normalize_song_text(raw or "")
        if not text:
            return              # an empty clipboard pastes nothing
        length = utf16_length(self._painted_text)
        start, end = max(0, min(start, length)), max(0, min(end, length))
        cursor = QTextCursor(self._document)
        cursor.setPosition(min(start, end))
        cursor.setPosition(max(start, end), QTextCursor.MoveMode.KeepAnchor)
        cursor.beginEditBlock()
        cursor.insertText(text)
        cursor.endEditBlock()
        if self._area is not None:
            self._area.setProperty("cursorPosition", cursor.position())

    # -- zoom (resolution 3) ----------------------------------------------------------

    @Slot()
    def zoomIn(self) -> None:  # noqa: N802 (Qt)
        self._zoom(1)

    @Slot()
    def zoomOut(self) -> None:  # noqa: N802 (Qt)
        self._zoom(-1)

    @Slot()
    def zoomReset(self) -> None:  # noqa: N802 (Qt)
        self._store.submit("reset_font_size")

    def _zoom(self, steps: int) -> None:
        # From the size asked for last, if the session hasn't answered yet
        # (a fast wheel): steps between rungs differ (14 to 15 is 1 pt, 15
        # to 17 is 2), so stepping from a stale size would leave the ladder.
        base = self._asked_size if self._asked_size is not None else self._font_size
        target = editor_font.zoomed_size(base, steps)
        if target != base:
            self._asked_size = target
            self._store.submit("step_font_size", {"delta": target - base})

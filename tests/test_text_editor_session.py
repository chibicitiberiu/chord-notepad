"""The Tk editor as a view over the session.

The real ChordTextEditor and AppSession, wired the way MainWindow wires them:
``<<Modified>>`` runs ``MainWindow.on_text_modified`` (text -> session), and
the session's HighlightState is painted with ``apply_highlight``. The session
runs on a ManualHost, so the debounce is driven by the test.
"""

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

tk = pytest.importorskip("tkinter")

from constants import (
    TAG_CHORD_INVALID, TAG_CHORD_VALID, TAG_COMMENT, TAG_DIRECTIVE_INVALID,
    TAG_DIRECTIVE_VALID,
)
from services.song_parser_service import SongParserService
from session.host import HostDispatch
from session.session import AppSession
from session.state import HighlightState, Span, SpanKind
from session.testing import InMemoryDocumentStore, ManualHost
from ui.main_window import MainWindow
from ui.text_editor import ChordTextEditor
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY")) or os.name == "nt"


class _Config:
    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass


@pytest.fixture
def wired():
    """An editor and a session, wired like MainWindow does it."""
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    host = ManualHost()
    parser = SongParserService()
    main_vm = MainWindowViewModel(_Config(), MagicMock(), InMemoryDocumentStore(),
                                  parser, HostDispatch(host))
    session = AppSession(host, main_window_viewmodel=main_vm,
                         text_editor_viewmodel=TextEditorViewModel(parser))
    editor = ChordTextEditor(root, session=session)
    editor.pack()
    window = SimpleNamespace(text_editor=editor, session=session, viewmodel=Mock(),
                             update_statusbar=Mock())
    editor.bind("<<Modified>>", lambda e: MainWindow.on_text_modified(window))
    session.subscribe(lambda item: MainWindow._on_session_output(window, item))
    session.start()
    # Mapped, so synthesized events (paste, motion) are delivered.
    root.deiconify()
    editor.wait_visibility()
    root.update()
    yield SimpleNamespace(root=root, host=host, session=session, editor=editor,
                          window=window, main_vm=main_vm)
    session.shutdown()
    root.destroy()


def _ranges(editor, tag):
    r = editor.tag_ranges(tag)
    return [(editor.offset_of(str(a)), editor.offset_of(str(b)))
            for a, b in zip(r[0::2], r[1::2])]


def test_paint_spans_maps_each_kind_to_its_tag(wired):
    editor = wired.editor
    editor.insert("1.0", "x" * 40)
    editor.paint_spans([
        Span(0, 2, SpanKind.CHORD), Span(3, 5, SpanKind.CHORD_INVALID),
        Span(6, 8, SpanKind.DIRECTIVE), Span(9, 11, SpanKind.DIRECTIVE_INVALID),
        Span(12, 14, SpanKind.COMMENT),
    ])
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 2)]
    assert _ranges(editor, TAG_CHORD_INVALID) == [(3, 5)]
    assert _ranges(editor, TAG_DIRECTIVE_VALID) == [(6, 8)]
    assert _ranges(editor, TAG_DIRECTIVE_INVALID) == [(9, 11)]
    assert _ranges(editor, TAG_COMMENT) == [(12, 14)]

    editor.paint_spans([Span(20, 21, SpanKind.CHORD)])
    assert _ranges(editor, TAG_CHORD_VALID) == [(20, 21)]
    assert _ranges(editor, TAG_COMMENT) == []


def test_typing_reaches_the_session_and_is_highlighted_after_the_debounce(wired):
    editor = wired.editor
    editor.insert("insert", "C G // hi\nla la")
    wired.root.update()  # delivers <<Modified>>

    assert wired.session.text == "C G // hi\nla la"
    assert wired.main_vm.is_modified is True
    assert _ranges(editor, TAG_CHORD_VALID) == []

    wired.host.advance(0.5)
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 1), (2, 3)]
    assert _ranges(editor, TAG_COMMENT) == [(4, 9)]
    assert editor.highlight.text_revision == wired.session.text_revision


def test_offsets_count_code_points(wired):
    editor = wired.editor
    editor.insert("1.0", "\U0001F3B8 x\nC G")
    wired.root.update()
    wired.host.advance(0.5)
    assert _ranges(editor, TAG_CHORD_VALID) == [(4, 5), (6, 7)]
    assert editor.get("1.0 + 4 chars") == "C"
    assert editor.offset_of("2.2") == 6


def _set_clipboard(widget, text):
    widget.clipboard_clear()
    widget.clipboard_append(text)
    for _ in range(50):
        widget.update()
        try:
            if widget.clipboard_get() == text:
                return
        except tk.TclError:
            pass
        time.sleep(0.01)
    pytest.skip("clipboard not available in this environment")


def test_paste_rearms_detection(wired):
    editor = wired.editor
    _set_clipboard(editor, "Am  F\r\nwords\r\n")
    editor.focus_force()
    editor.event_generate("<<Paste>>")
    wired.root.update()

    assert wired.session.text == "Am  F\nwords\n"
    assert wired.host.pending_timers == 1
    wired.host.advance(0.5)
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 2), (4, 5)]


def test_programmatic_replace_is_highlighted_at_once(wired):
    # MainWindow._on_current_text_changed: open/transpose/convert results.
    MainWindow._on_current_text_changed(wired.window, "G D\nla")
    assert _ranges(wired.editor, TAG_CHORD_VALID) == [(0, 1), (2, 3)]
    wired.root.update()  # the edit's own <<Modified>> must not re-arm anything
    assert wired.host.pending_timers == 0


def test_identifier_insert_is_highlighted_at_once(wired):
    editor = wired.editor
    editor.insert("1.0", "C ")
    wired.root.update()
    editor.mark_set("insert", "end-1c")
    MainWindow._on_insert_chord_from_identifier(wired.window, "Am")
    assert wired.session.text == "C Am "
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 1), (2, 4)]
    wired.root.update()
    assert wired.host.pending_timers == 0


def _pixel_of(editor, offset):
    x, y, w, h = editor.bbox(f"1.0 + {offset} chars")
    return x + w // 2, y + h // 2


def test_hand_cursor_only_over_valid_chords(wired):
    editor = wired.editor
    MainWindow._on_current_text_changed(wired.window, "C  Cmaj13#11b9\nCome")
    wired.root.update()

    x, y = _pixel_of(editor, 0)
    editor.event_generate("<Motion>", x=x, y=y)
    assert str(editor.cget("cursor")) == "hand2"

    x, y = _pixel_of(editor, 5)  # inside the invalid chord
    editor.event_generate("<Motion>", x=x, y=y)
    assert str(editor.cget("cursor")) == "xterm"

    x, y = _pixel_of(editor, 16)  # the lyric line
    editor.event_generate("<Motion>", x=x, y=y)
    assert str(editor.cget("cursor")) == "xterm"


def test_click_plays_the_chord_under_the_pointer(wired):
    editor = wired.editor
    MainWindow._on_current_text_changed(wired.window, "C  G\nla")
    wired.root.update()

    x, y = _pixel_of(editor, 3)
    MainWindow.on_chord_click(wired.window, SimpleNamespace(x=x, y=y))
    played = wired.window.viewmodel.on_chord_clicked.call_args.args[0]
    assert (played.chord, played.start, played.end) == ("G", 3, 4)

    wired.window.viewmodel.on_chord_clicked.reset_mock()
    x, y = _pixel_of(editor, 6)
    MainWindow.on_chord_click(wired.window, SimpleNamespace(x=x, y=y))
    wired.window.viewmodel.on_chord_clicked.assert_not_called()


def test_highlight_state_from_the_session_is_painted(wired):
    MainWindow._on_session_output(
        wired.window, HighlightState(9, 0, (Span(0, 1, SpanKind.COMMENT),)))
    assert wired.editor.highlight.text_revision == 9

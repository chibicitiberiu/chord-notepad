"""The Tk editor as a view over the session.

The real ChordTextEditor and AppSession, wired the way MainWindow wires them:
``<<Modified>>`` runs ``MainWindow.on_text_modified`` (text -> session), and
the session's HighlightState is painted with ``apply_highlight``. The session
runs on a ManualHost, so the debounce is driven by the test.
"""

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

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
    audio = MagicMock()
    main_vm = MainWindowViewModel(_Config(), audio, InMemoryDocumentStore(),
                                  parser, HostDispatch(host))
    session = AppSession(host, main_window_viewmodel=main_vm,
                         text_editor_viewmodel=TextEditorViewModel(parser))
    editor = ChordTextEditor(root, session=session)
    editor.pack()
    # Only the editor is real; the other widgets the session's states map
    # to are stand-ins.
    window = SimpleNamespace(text_editor=editor, session=session, statusbar=Mock(),
                             _apply_playback=Mock(), _apply_toolbar=Mock(),
                             _apply_editor=Mock(), rebuild_voicing_menu=Mock(),
                             build_instrument_menu=Mock(), _apply_chord_sheet=Mock())
    editor.bind("<<Modified>>", lambda e: MainWindow.on_text_modified(window))
    session.subscribe(lambda item: MainWindow._on_session_output(window, item))
    session.start()
    # Mapped, so synthesized events (paste, motion) are delivered.
    root.deiconify()
    editor.wait_visibility()
    root.update()
    yield SimpleNamespace(root=root, host=host, session=session, editor=editor,
                          window=window, main_vm=main_vm, audio=audio)
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


def _replace(wired, text):
    """Replace the text through the viewmodel, like Open and New do."""
    wired.main_vm.set_and_notify("current_text", text)


def test_programmatic_replace_is_highlighted_at_once(wired):
    _replace(wired, "G D\nla")
    assert wired.editor.get_text() == "G D\nla"
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
    _replace(wired, "C  Cmaj13#11b9\nCome")
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
    _replace(wired, "C  G\nla")
    wired.root.update()

    x, y = _pixel_of(editor, 3)
    MainWindow.on_chord_click(wired.window, SimpleNamespace(x=x, y=y))
    played = wired.audio.play_chord_immediate.call_args.args[0]
    assert (played.chord, played.start, played.end) == ("G", 3, 4)
    wired.window.statusbar.config.assert_called_with(text="Playing: G")

    wired.audio.play_chord_immediate.reset_mock()
    x, y = _pixel_of(editor, 6)
    MainWindow.on_chord_click(wired.window, SimpleNamespace(x=x, y=y))
    wired.audio.play_chord_immediate.assert_not_called()


def test_highlight_state_from_the_session_is_painted(wired):
    MainWindow._on_session_output(
        wired.window, HighlightState(9, 0, (Span(0, 1, SpanKind.COMMENT),)))
    assert wired.editor.highlight.text_revision == 9


# -- playback: the view only maps states and forwards commands -------------------


def _playback_window(wired):
    """A window whose playback widgets are stand-ins around the real editor."""
    return SimpleNamespace(
        text_editor=wired.editor, _shown_progress=None, session=Mock())


def test_playing_state_highlights_and_scrolls_to_the_chord(wired):
    from constants import TAG_CHORD_PLAYING
    from session.state import PlaybackState, PlaybackStatus

    editor = wired.editor
    editor.insert("1.0", "\n" * 200 + "C  G")
    window = _playback_window(wired)
    span = Span(203, 204, SpanKind.CHORD)
    MainWindow._apply_playback(window, PlaybackState(PlaybackStatus.PLAYING, span, 1, 1, 1))

    assert _ranges(editor, TAG_CHORD_PLAYING) == [(203, 204)]
    assert editor.bbox("1.0 + 203 chars") is not None  # scrolled into view

    # Pausing keeps the chord highlighted and doesn't scroll back to it.
    editor.see("1.0")
    MainWindow._apply_playback(window, PlaybackState(PlaybackStatus.PAUSED, span, 1, 1, 1))
    assert _ranges(editor, TAG_CHORD_PLAYING) == [(203, 204)]
    assert editor.bbox("1.0 + 203 chars") is None

    MainWindow._apply_playback(window, PlaybackState(PlaybackStatus.IDLE))
    assert _ranges(editor, TAG_CHORD_PLAYING) == []


def test_editor_state_locks_the_editor(wired):
    from session.state import EditorState

    wired.window._apply_editor = lambda state: MainWindow._apply_editor(wired.window, state)
    wired.window.apply_font = lambda: None
    MainWindow._on_session_output(wired.window, EditorState("TkFixedFont", 11, True, "american"))
    assert str(wired.editor.cget("state")) == "disabled"
    MainWindow._on_session_output(wired.window, EditorState("TkFixedFont", 11, False, "american"))
    assert str(wired.editor.cget("state")) == "normal"


def test_shift_play_sends_the_cursor_offset_in_code_points(wired):
    editor = wired.editor
    editor.insert("1.0", "\U0001F3B8 C\nG")
    editor.mark_set("insert", "2.0")
    window = _playback_window(wired)

    MainWindow.on_play_pause_click(window, SimpleNamespace(state=0x1))
    window.session.play_pause.assert_called_with(4)
    window.session.set_text.assert_called_with("\U0001F3B8 C\nG")

    MainWindow.on_play_pause_click(window, SimpleNamespace(state=0))
    window.session.play_pause.assert_called_with(None)


# -- programmatic edits: undo policy, no echo, request presenters ----------------


def _type(wired, text):
    """Type ``text`` into an empty editor and let it reach the session."""
    wired.editor.insert("1.0", text)
    wired.root.update()
    wired.host.advance(0.5)
    wired.editor.edit_reset()


def _count_set_text(wired):
    calls = []
    real = wired.session.set_text

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    wired.session.set_text = spy
    return calls


def test_transpose_is_one_undo_step_and_is_not_echoed(wired):
    editor = wired.editor
    _type(wired, "C G\nla la")
    calls = _count_set_text(wired)
    revision = wired.session.text_revision

    wired.session.transpose(2, None)
    assert editor.get_text() == "D A\nla la"
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 1), (2, 3)]
    assert editor.index("insert") == "2.5"  # cursor after the replacement

    wired.root.update()  # the edit's own <<Modified>>
    assert calls == []
    assert wired.session.text_revision == revision + 1
    assert wired.host.pending_timers == 0

    editor.edit_undo()  # one step restores the original
    assert editor.get_text() == "C G\nla la"
    wired.root.update()  # undo is a user edit: it reaches the session
    assert wired.session.text == "C G\nla la"


def test_inserted_text_is_a_plain_edit_with_the_cursor_after_it(wired):
    editor = wired.editor
    _type(wired, "C G")
    wired.session.insert_text(1, " Am")
    assert editor.get_text() == "C Am G"
    assert editor.offset_of("insert") == 4
    assert _ranges(editor, TAG_CHORD_VALID) == [(0, 1), (2, 4), (5, 6)]
    editor.edit_undo()
    assert editor.get_text() == "C G"


def test_a_reset_edit_clears_the_undo_history(wired):
    from session.events import TextEdited, UndoPolicy

    editor = wired.editor
    _type(wired, "C G")
    editor.insert("end", " Am")
    editor.apply_edit(TextEdited(9, 0, 6, "G D", UndoPolicy.RESET, 0))
    assert editor.get_text() == "G D"
    assert editor.index("insert") == "1.0"
    with pytest.raises(tk.TclError):
        editor.edit_undo()


def test_an_edit_applies_while_the_editor_is_locked(wired):
    from session.events import TextEdited, UndoPolicy

    editor = wired.editor
    editor.config(state=tk.DISABLED)
    editor.apply_edit(TextEdited(1, 0, 0, "C G", UndoPolicy.PLAIN, 3))
    assert editor.get_text() == "C G"
    assert str(editor.cget("state")) == "disabled"


def _presenting_window(wired):
    """The wired window, plus the bits the request presenters use."""
    window = wired.window
    window.after_idle = Mock()
    window.wait_window = Mock()
    window._present_directive_request = Mock()
    window._present_capo_request = Mock()
    return window


def test_insert_directive_round_trip(wired):
    from session.events import InsertDirectiveRequest

    editor = wired.editor
    _type(wired, "C G\n{label: verse}\nAm")
    editor.mark_set("insert", "3.0")
    window = _presenting_window(wired)

    MainWindow._request_directive(window, "loop")
    # Presented once delivery is over, not from inside it.
    present, request = window.after_idle.call_args.args
    assert present is window._present_directive_request
    assert isinstance(request, InsertDirectiveRequest)
    assert request.existing_labels == ("verse",)

    dialog = SimpleNamespace(result={"label": "verse", "count": "2"})
    with patch("ui.main_window.dialog_for_request", return_value=dialog) as make:
        MainWindow._present_directive_request(window, request)
    make.assert_called_once_with(window, request)
    assert editor.get_text() == "C G\n{label: verse}\n{loop: verse 2} Am"
    assert _ranges(editor, TAG_DIRECTIVE_VALID) == [(4, 18), (19, 34)]
    wired.window.statusbar.config.assert_called_with(text="Inserted: {loop: verse 2}")


def test_cancelled_directive_dialog_answers_none(wired):
    _type(wired, "C G")
    window = _presenting_window(wired)
    MainWindow._request_directive(window, "bpm")
    _, request = window.after_idle.call_args.args
    with patch("ui.main_window.dialog_for_request",
               return_value=SimpleNamespace(result=None)):
        MainWindow._present_directive_request(window, request)
    assert wired.editor.get_text() == "C G"
    assert wired.session.text == "C G"


def test_insert_capo_round_trip(wired):
    _type(wired, "C G")
    wired.editor.mark_set("insert", "1.0")
    window = _presenting_window(wired)
    window.open_suggest_capo_dialog = Mock()
    window._request_directive = lambda kind: MainWindow._request_directive(window, kind)
    MainWindow.insert_capo(window)
    _, request = window.after_idle.call_args.args
    assert request.kind == "capo"
    with patch("ui.main_window.dialog_for_request",
               return_value=SimpleNamespace(result={"capo": "3"}, suggest=False)):
        MainWindow._present_directive_request(window, request)
    assert wired.editor.get_text() == "{capo: 3} C G"
    window.open_suggest_capo_dialog.assert_not_called()


def test_insert_capo_suggest_hands_over_to_suggest_capo(wired):
    _type(wired, "C G")
    window = _presenting_window(wired)
    window.open_suggest_capo_dialog = Mock()
    window._request_directive = lambda kind: MainWindow._request_directive(window, kind)
    MainWindow.insert_capo(window)
    _, request = window.after_idle.call_args.args
    with patch("ui.main_window.dialog_for_request",
               return_value=SimpleNamespace(result=None, suggest=True)):
        MainWindow._present_directive_request(window, request)
    assert wired.session.text == "C G"
    window.open_suggest_capo_dialog.assert_called_once_with()


def test_the_insert_capo_dialog(wired):
    from session.events import InsertDirectiveRequest
    from ui.dialogs.insert_directives import InsertCapoDialog, dialog_for_request

    request = InsertDirectiveRequest(1, "capo", (), "american")
    dialog = dialog_for_request(wired.root, request)
    try:
        assert isinstance(dialog, InsertCapoDialog)
        dialog.fret_var.set("4")
        assert dialog.get_values() == {"capo": "4"}
        dialog._on_suggest()
        assert dialog.result is None and dialog.suggest
    finally:
        if dialog.winfo_exists():
            dialog.destroy()


def test_tools_insert_menu_offers_capo():
    import inspect
    source = inspect.getsource(MainWindow.create_menu)
    assert '.add_command("Capo...", self.insert_capo)' in source


def test_capo_dialog_answers_with_the_chosen_voicing(wired):
    from session.events import CapoChoiceRequest
    from session.state import MenuItem

    window = SimpleNamespace(wait_window=Mock(), session=Mock())
    request = CapoChoiceRequest(5, (MenuItem("Standard", "guitar:standard"),
                                    MenuItem("Drop D", "guitar:drop_d")), "guitar:drop_d",
                                "Applies to the whole song.")
    dialog = SimpleNamespace(result="Standard")
    with patch("ui.main_window.CapoDialog", return_value=dialog) as make:
        MainWindow._present_capo_request(window, request)
    make.assert_called_once_with(window, ["Standard", "Drop D"], "Drop D",
                                 scope="Applies to the whole song.")
    window.session.respond.assert_called_once_with(5, "guitar:standard")

    dialog.result = None
    with patch("ui.main_window.CapoDialog", return_value=dialog):
        MainWindow._present_capo_request(window, request)
    window.session.respond.assert_called_with(5, None)


def test_identifier_insert_is_refused_while_playing(wired):
    editor = wired.editor
    _type(wired, "C ")
    wired.main_vm._is_playing = True  # what the session checks
    editor.mark_set("insert", "end-1c")
    MainWindow._on_insert_chord_from_identifier(wired.window, "Am")
    assert editor.get_text() == "C "
    assert wired.session.text == "C "
    assert not any("Inserted chord" in str(c) for c in wired.window.statusbar.config.call_args_list)

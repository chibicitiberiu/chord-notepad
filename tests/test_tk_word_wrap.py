"""Desktop: View > Word Wrap and the editor's horizontal scrollbar.

The window is built without its ``__init__`` (just the editor and the
menus) over a stand-in session: the menu sends ``set_word_wrap`` and the
editor follows ``EditorState.word_wrap``, with a horizontal scrollbar
while wrap is off.
"""

import os
import tkinter as tk
from unittest.mock import Mock

import pytest

from session.state import EditorState


@pytest.fixture
def window():
    if not (os.environ.get("DISPLAY") or os.name == "nt"):
        pytest.skip("No display available for tkinter tests")
    from ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    try:
        tk.Tk.__init__(window)
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    window.session = Mock()
    window._editor_state = None
    window.create_text_editor()
    window.create_menu()
    window.update()
    yield window
    window.destroy()


def _view_entry(window, label):
    menubar = window.nametowidget(window["menu"])
    for i in range(menubar.index("end") + 1):
        if menubar.type(i) == "cascade" and menubar.entrycget(i, "label") == "View":
            view = window.nametowidget(menubar.entrycget(i, "menu"))
            for j in range(view.index("end") + 1):
                if view.type(j) != "separator" and view.entrycget(j, "label") == label:
                    return view, j
    raise AssertionError(f"no View > {label}")


def _state(word_wrap):
    return EditorState(font_family="TkFixedFont", font_size=11, read_only=False,
                       notation="american", word_wrap=word_wrap)


def test_off_until_the_session_says_otherwise(window):
    assert window.text_editor.cget("wrap") == "none"
    assert window._hscrollbar.winfo_manager() == "pack"
    view, index = _view_entry(window, "Word Wrap")
    assert view.type(index) == "checkbutton"
    assert window._word_wrap_var.get() is False


def test_the_menu_sends_set_word_wrap(window):
    view, index = _view_entry(window, "Word Wrap")
    view.invoke(index)
    window.session.set_word_wrap.assert_called_once_with(True)


def test_the_editor_follows_editor_state(window):
    window._apply_editor(_state(True))
    window.update()
    assert window.text_editor.cget("wrap") == "word"
    assert window._hscrollbar.winfo_manager() == ""
    assert window._word_wrap_var.get() is True

    window._apply_editor(_state(False))
    window.update()
    assert window.text_editor.cget("wrap") == "none"
    assert window._hscrollbar.winfo_manager() == "pack"
    assert window._word_wrap_var.get() is False
    # Packed once, under the text (not beside it).
    window._apply_editor(_state(False))
    assert window._hscrollbar.pack_info()["side"] == "bottom"


def test_a_long_line_scrolls_sideways_with_wrap_off(window):
    window.geometry("300x200")
    window.text_editor.insert("1.0", "C       G       Am      F       " * 6 + "\nhello")
    window.update()
    first, last = window.text_editor.xview()
    assert first == 0.0 and last < 1.0
    window._apply_editor(_state(True))
    window.update()
    assert window.text_editor.xview() == (0.0, 1.0)

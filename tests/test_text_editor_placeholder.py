"""The desktop editor's placeholder: grey "Type or paste a song here" while the
song is empty, drawn over the text and never part of it."""

import os
import tkinter as tk

import pytest

from session.events import TextEdited, UndoPolicy
from ui.text_editor import ChordTextEditor

PLACEHOLDER = "Type or paste a song here"


def _root():
    if not (os.environ.get("DISPLAY") or os.name == "nt"):
        pytest.skip("No display available for tkinter tests")
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")


@pytest.fixture
def editor():
    root = _root()
    widget = ChordTextEditor(root, placeholder=PLACEHOLDER, padx=6, pady=4)
    widget.pack()
    root.update()
    yield widget
    root.destroy()


def _shown(widget: ChordTextEditor) -> bool:
    widget.update()
    return bool(widget._placeholder.winfo_ismapped())


def test_shown_while_empty_and_not_part_of_the_text(editor):
    assert _shown(editor)
    assert editor._placeholder.cget("text") == PLACEHOLDER
    assert editor.get_text() == ""


def test_typing_hides_it_and_clearing_brings_it_back(editor):
    editor.insert("1.0", "C G")
    assert not _shown(editor)
    editor.edit_modified(False)  # as the window does after sending the text
    editor.delete("1.0", "end")
    assert _shown(editor)


def test_undo_back_to_empty_shows_it(editor):
    editor.insert("1.0", "Am")
    editor.edit_separator()
    assert not _shown(editor)
    editor.edit_modified(False)
    editor.edit_undo()
    assert _shown(editor)


def test_session_edits_hide_and_show_it(editor):
    editor.apply_edit(TextEdited(text_revision=1, start=0, end=0, replacement="C\nla", cursor=0,
                                 undo=UndoPolicy.RESET))
    assert not _shown(editor)
    editor.apply_edit(TextEdited(text_revision=2, start=0, end=4, replacement="", cursor=0,
                                 undo=UndoPolicy.RESET))
    assert _shown(editor)


def test_follows_the_editor_font_and_padding(editor):
    editor.configure(font=("Courier", 17), padx=10)
    label = editor._placeholder
    assert label.cget("font") == editor.cget("font")
    editor.update()
    # Where the first character goes: border, highlight ring, then padding.
    inset = int(editor.cget("borderwidth")) + int(editor.cget("highlightthickness"))
    assert label.winfo_x() == inset + 10
    assert label.winfo_y() == inset + 4


def test_faded_editor_colour_on_the_editor_background(editor):
    label = editor._placeholder
    assert label.cget("background") == editor.cget("background")
    assert editor.winfo_rgb(label.cget("foreground")) != editor.winfo_rgb(editor.cget("foreground"))


def test_click_puts_the_cursor_in_the_text(editor):
    editor._placeholder.event_generate("<Button-1>", x=2, y=2)
    editor.update()
    assert editor.index(tk.INSERT) == "1.0"


def test_no_placeholder_by_default():
    root = _root()
    try:
        widget = ChordTextEditor(root)
        widget.pack()
        root.update()
        assert widget._placeholder is None
        assert not [w for w in widget.winfo_children() if isinstance(w, tk.Label)]
        widget.configure(font=("Courier", 12))  # no placeholder to restyle
    finally:
        root.destroy()

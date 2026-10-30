"""Desktop Redo: the keys the Edit menu shows are the keys that redo (todo #7).

Tk's own <<Redo>> is Ctrl+Shift+Z on Linux and Ctrl+Y on Windows, while the
menu said Ctrl+Y everywhere. The editor now binds both on every platform.
"""

import os
import tkinter as tk

import pytest

from ui.text_editor import ChordTextEditor, REDO_ACCELERATOR


def _root():
    if not (os.environ.get("DISPLAY") or os.name == "nt"):
        pytest.skip("No display available for tkinter tests")
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")


def test_ctrl_y_and_ctrl_shift_z_both_redo():
    root = _root()
    try:
        ChordTextEditor(root)
        redo = root.event_info("<<Redo>>")
        assert "<Control-Key-y>" in redo
        assert "<Control-Key-Z>" in redo
        # Neither key does anything else in the editor (Tk's X11 bindings
        # made Ctrl+Y paste, emacs-style).
        for other in root.event_info():
            if other != "<<Redo>>":
                keys = root.event_info(other)
                assert "<Control-Key-y>" not in keys, other
                assert "<Control-Key-Z>" not in keys, other
    finally:
        root.destroy()


def test_the_menu_shows_a_bound_key():
    assert REDO_ACCELERATOR == "Ctrl+Y"
    source = open(os.path.join(os.path.dirname(__file__), "..", "src", "ui",
                               "main_window.py"), encoding="utf-8").read()
    assert 'accelerator="Ctrl+Y"' not in source
    assert "accelerator=REDO_ACCELERATOR" in source


def test_ctrl_y_redoes_in_the_editor():
    root = _root()
    try:
        editor = ChordTextEditor(root)
        editor.pack()
        editor.insert("1.0", "C G")
        editor.edit_separator()
        editor.edit_undo()
        assert editor.get_text() == ""
        editor.focus_set()
        root.update()
        editor.event_generate("<Control-Key-y>", keysym="y", when="now")
        root.update()
        assert editor.get_text() == "C G"
        editor.edit_undo()
        editor.event_generate("<Control-Key-Z>", keysym="Z", when="now")
        root.update()
        assert editor.get_text() == "C G"
    finally:
        root.destroy()

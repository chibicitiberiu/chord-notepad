"""The Linux .desktop file must match the window the app actually creates."""

from pathlib import Path

import pytest

from constants import WM_CLASS

DESKTOP_FILE = (Path(__file__).parent.parent / "packaging" / "linux"
                / "io.github.chibicitiberiu.ChordNotepad.desktop")


def _desktop_value(key):
    for line in DESKTOP_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def test_startup_wm_class_matches_constant():
    assert _desktop_value("StartupWMClass") == WM_CLASS


def test_tk_keeps_the_window_class_as_spelled():
    """Tk title-cases className; the constant must already be in that form."""
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk(className=WM_CLASS)
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    try:
        root.withdraw()
        assert root.winfo_class() == WM_CLASS
    finally:
        root.destroy()

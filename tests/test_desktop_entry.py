"""The Linux .desktop file must match the window the app actually creates."""

from pathlib import Path


from chordnotepad.constants import WM_CLASS

DESKTOP_FILE = (Path(__file__).parent.parent / "packaging" / "linux"
                / "io.github.chibicitiberiu.ChordNotepad.desktop")


def _desktop_value(key):
    for line in DESKTOP_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def test_startup_wm_class_matches_constant():
    assert _desktop_value("StartupWMClass") == WM_CLASS


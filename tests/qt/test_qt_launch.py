"""The Qt front end starts: the main window loads, ``--ui qt --smoke`` exits 0."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402

from chordnotepad_desktop import main as qt_main  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_the_main_window_loads(qapp):
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    try:
        assert qt_main.load_main_window(engine)
        window = engine.rootObjects()[0]
        assert isinstance(window, QQuickWindow)
        assert window.title() == "Chord Notepad"
        assert warnings == []
    finally:
        for window in engine.rootObjects():
            window.close()
        engine.deleteLater()


def throwaway_env(tmp_path):
    """Offscreen, no audio, and every XDG folder in tmp_path (the brief's isolation)."""
    env = dict(os.environ)
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        folder = tmp_path / name.lower()
        folder.mkdir(mode=0o700)
        env[name] = str(folder)
    env.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               PULSE_SERVER="unix:/nonexistent", PIPEWIRE_REMOTE="/nonexistent",
               PYTHONPATH=os.pathsep.join([str(REPO / "core"), str(REPO / "desktop")]))
    return env


def test_ui_qt_smoke_starts_and_quits_cleanly(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_tk.main", "--ui", "qt", "--smoke"],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "QML" not in result.stderr


def test_the_qt_module_runs_through_the_shared_entry_point(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_desktop.main", "--smoke"],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr

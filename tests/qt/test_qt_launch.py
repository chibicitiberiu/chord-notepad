"""The app starts: the main window loads, ``python -m chordnotepad_desktop --smoke`` exits 0."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtQuick import QQuickWindow  # noqa: E402

from chordnotepad_desktop import main as qt_main  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def test_the_main_window_loads(main_window):
    assert isinstance(main_window.window, QQuickWindow)
    assert main_window.window.title() == "Untitled - Chord Notepad"
    assert main_window.window.property("altWatcher") is main_window.alt


def test_the_qml_ships_inside_the_package():
    assert qt_main.MAIN_QML.is_file()
    assert qt_main.QML_DIR == Path(qt_main.__file__).resolve().parent / "qml"


def test_the_front_end_options_leave_qts_own_alone():
    options, rest = qt_main.parse_args(["--smoke", "-platform", "offscreen"])
    assert options.smoke and rest == ["-platform", "offscreen"]
    assert not qt_main.parse_args([])[0].smoke


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


def test_smoke_starts_and_quits_cleanly(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_desktop", "--smoke"],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    # The console log (stdout): started and shut down, nothing from Qt above INFO.
    assert "Application initialization complete" in result.stdout
    assert "Application shutdown complete" in result.stdout
    assert not re.search(r"\[(WARNING|ERROR|CRITICAL)\] qt\.", result.stdout), result.stdout
    # The log file has it too (logging was set up in the throwaway folders).
    log = tmp_path / "xdg_data_home" / "chord-notepad" / "logs" / "chord-notepad.log"
    assert "Application shutdown complete" in log.read_text(encoding="utf-8")


def test_ui_qt_is_still_accepted(tmp_path):
    """Older scripts and a relaunch of an old command line may pass ``--ui qt``."""
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_desktop", "--ui", "qt", "--smoke"],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_ui_tk_says_the_tk_window_is_gone(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_desktop", "--ui", "tk"],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 2
    assert "the Tk window was removed in 0.6.0" in result.stderr
    assert "Application initialization complete" not in result.stdout


#: Starts the app, opens Settings, closes it, then closes the main window;
#: exit code 7 if the app is still running 10 s later.
_SETTINGS_THEN_CLOSE = """
import os, sys
from PySide6.QtCore import QMetaObject, QObject, QTimer, Q_ARG
import chordnotepad_desktop.application as application
from chordnotepad_desktop import launcher

orig_start = application.QtApplication.start

def start(self, app):
    main = orig_start(self, app)
    win = main.window
    hub = win.findChild(QObject, "appDialogs")
    settings = win.findChild(QObject, "settingsWindow")
    QTimer.singleShot(300, lambda: QMetaObject.invokeMethod(hub, "openSettings", Q_ARG("QVariant", "general")))
    QTimer.singleShot(900, lambda: settings.close())
    QTimer.singleShot(1500, lambda: print("settings shown after close:", settings.isVisible(), flush=True))
    QTimer.singleShot(1600, lambda: win.close())
    QTimer.singleShot(10000, lambda: (print("STILL RUNNING", flush=True), os._exit(7)))
    return main

application.QtApplication.start = start
launcher.main([])
"""


def test_the_app_ends_when_its_window_closes_after_settings_was_open(tmp_path):
    # Qt counts a window that was shown and then only hidden as still open:
    # the Settings window, hidden on close, kept the app running (no window,
    # no shutdown, the config not saved) after the main window closed (H1).
    env = throwaway_env(tmp_path)
    env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/nonexistent"
    config = tmp_path / "xdg_config_home" / "chord-notepad"
    config.mkdir(parents=True)
    (config / "settings.json").write_text('{"show_quick_start_on_startup": false}', encoding="utf-8")
    result = subprocess.run([sys.executable, "-c", _SETTINGS_THEN_CLOSE],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert "settings shown after close: False" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Application shutdown complete" in result.stdout

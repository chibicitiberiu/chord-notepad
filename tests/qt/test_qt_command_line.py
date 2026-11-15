"""A song named on the command line opens at start (main.song_path, application.py).

``chord-notepad song.txt`` (``python -m chordnotepad_desktop song.txt``): the
first argument that isn't an option, after Qt has taken its own, opens once
the session runs, as File › Open would. A file that can't be read gets
Open's error message and the app starts anyway.
"""

import subprocess
import sys

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from chordnotepad_desktop import main as qt_main  # noqa: E402
from tests.qt.conftest import QtAppHarness, write_config  # noqa: E402
from tests.qt.test_qt_launch import throwaway_env  # noqa: E402


def test_the_song_is_the_first_argument_that_isnt_an_option():
    assert qt_main.song_path([]) is None
    assert qt_main.song_path(["song.txt"]) == "song.txt"
    assert qt_main.song_path(["--unknown", "a.txt", "b.txt"]) == "a.txt"
    assert qt_main.song_path(["-x", "--", "-dash.txt"]) == "-dash.txt"
    assert qt_main.song_path(["--", "--"]) == "--"


def started(qapp, qtbot, tmp_path, path):
    write_config(tmp_path, show_quick_start_on_startup=False)
    harness = QtAppHarness(qapp, tmp_path)
    harness.app._open_path = str(path)
    harness.start()
    qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
    return harness


def test_a_named_song_opens_and_joins_the_recent_list(qapp, qtbot, tmp_path):
    song = tmp_path / "Hymn.txt"
    song.write_text("G D\nAmazing grace\n", encoding="utf-8")
    harness = started(qapp, qtbot, tmp_path, song)
    try:
        editor = harness.app.editor
        qtbot.waitUntil(lambda: editor.text == "G D\nAmazing grace\n", timeout=2000)
        doc = harness.store.state("DocumentState")
        assert doc.value("document_id") == str(song) and doc.value("is_modified") is False
        assert list(harness.app.chrome.files.recentLabels) == ["Hymn.txt"]
    finally:
        harness.shutdown()
        qtbot.wait(1)
    assert harness.app.warnings == [] and harness.unexpected == []


def test_a_missing_song_gets_opens_error_and_the_app_starts(qapp, qtbot, tmp_path):
    shown = []
    write_config(tmp_path, show_quick_start_on_startup=False)
    harness = QtAppHarness(qapp, tmp_path)
    harness.app._open_path = str(tmp_path / "missing.txt")
    try:
        harness.start()
        harness.app.presenter.shown.connect(lambda title, message: shown.append(message))
        qtbot.waitUntil(lambda: shown != [], timeout=3000)
        assert shown[0].startswith("Failed to open file")
        assert harness.window.isVisible()
        assert harness.app.editor.text == ""
    finally:
        harness.shutdown()
        qtbot.wait(1)


def test_from_the_command_line_with_qts_own_options_around_it(tmp_path):
    song = tmp_path / "Hymn.txt"
    song.write_text("G D\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "chordnotepad_desktop", "--smoke", "-platform", "offscreen",
         "--unknown-flag", str(song), str(tmp_path / "second.txt")],
        cwd=tmp_path, env=throwaway_env(tmp_path), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Opening {song} from the command line" in result.stdout
    assert f"Opening file: {song}" in result.stdout
    assert "second.txt" not in result.stdout

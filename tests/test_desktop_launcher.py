"""The desktop entry point (chordnotepad_desktop.launcher, ``python -m chordnotepad_desktop``).

These tests need neither a display nor PySide6: the Qt window is replaced
by a stand-in.
"""

import ast
import sys
import types
from pathlib import Path

import pytest

from chordnotepad_desktop import launcher as entry

PACKAGE = Path(entry.__file__).resolve().parent


def test_without_ui_the_command_line_is_left_alone():
    assert entry.parse_ui(["-platform", "offscreen", "--smoke"]) == (
        None, ["-platform", "offscreen", "--smoke"])


@pytest.mark.parametrize("argv", [["--ui", "qt"], ["--ui=qt"]])
def test_ui_qt_is_taken_off_the_command_line(argv):
    assert entry.parse_ui(argv + ["-platform", "offscreen", "--smoke"]) == (
        "qt", ["-platform", "offscreen", "--smoke"])


def test_an_unknown_front_end_is_refused(capsys):
    with pytest.raises(SystemExit) as exc:
        entry.parse_ui(["--ui", "gtk"])
    assert exc.value.code == 2
    assert "invalid choice: 'gtk'" in capsys.readouterr().err


@pytest.fixture
def fake_window(monkeypatch):
    """The Qt window's ``run``, recording its calls and returning 7."""
    calls = []
    fake = types.ModuleType("chordnotepad_desktop.main")
    fake.run = lambda paths, argv, build_info=None: calls.append((paths, argv, build_info)) or 7
    monkeypatch.setitem(sys.modules, "chordnotepad_desktop.main", fake)
    monkeypatch.setattr(entry.importlib.util, "find_spec", lambda name: object())
    return calls


@pytest.mark.parametrize("argv", [["--smoke"], ["--ui", "qt", "--smoke"]])
def test_main_starts_the_qt_window_with_the_resolved_paths(fake_window, argv):
    with pytest.raises(SystemExit) as exc:
        entry.main(argv)
    assert exc.value.code == 7
    assert fake_window == [(entry.APP_PATHS, ["--smoke"], entry.read_build_info())]


def test_ui_tk_says_the_tk_window_is_gone(fake_window, capsys):
    with pytest.raises(SystemExit) as exc:
        entry.main(["--ui", "tk"])
    assert exc.value.code == 2
    assert fake_window == []
    assert capsys.readouterr().err.strip() == entry.TK_REMOVED
    assert "removed in 0.6.0" in entry.TK_REMOVED


def test_the_window_gets_the_build_info_ci_writes():
    from chordnotepad_desktop import build_info

    info = entry.read_build_info()
    assert set(info) == {"VERSION", "BUILD_TYPE", "BUILD_NUMBER", "COMMIT_SHORT", "BUILD_DATE"}
    assert info["VERSION"] == build_info.VERSION and info["COMMIT_SHORT"] == build_info.COMMIT_SHORT


def test_without_pyside6_it_says_so(monkeypatch, capsys):
    monkeypatch.setattr(entry.importlib.util, "find_spec", lambda name: None)
    assert entry.run_qt([]) == 2
    assert "PySide6 is missing" in capsys.readouterr().err


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def test_the_package_imports_nothing_on_its_own():
    """``python -m chordnotepad_desktop`` imports ``__init__`` before the launcher's set-up runs."""
    assert list(_imports(PACKAGE / "__init__.py")) == []


def test_the_launcher_imports_no_qt_or_audio_before_its_set_up():
    """The DLL folder and the std streams come first: the top level imports only these."""
    tree = ast.parse((PACKAGE / "launcher.py").read_text(encoding="utf-8"))
    top = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            top.add(node.module)
    assert top == {"argparse", "importlib.util", "os", "sys", "chordnotepad_desktop.desktop_paths",
                   "chordnotepad.utils.std_streams"}


def test_main_module_only_calls_the_launcher():
    assert list(_imports(PACKAGE / "__main__.py")) == ["chordnotepad_desktop.launcher"]

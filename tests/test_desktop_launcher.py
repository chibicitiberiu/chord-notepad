"""The desktop entry point's ``--ui tk|qt`` choice (chordnotepad_tk.main).

Tk stays the default until the switch (plan H4). These tests need neither a
display nor PySide6: the front ends are replaced by stand-ins.
"""

import sys
import types

import pytest

from chordnotepad_tk import main as entry


def test_tk_is_the_default():
    assert entry.parse_ui([]) == ("tk", [])


@pytest.mark.parametrize("argv", [["--ui", "qt"], ["--ui=qt"]])
def test_ui_qt_is_taken_off_the_command_line(argv):
    assert entry.parse_ui(argv + ["-platform", "offscreen", "--smoke"]) == (
        "qt", ["-platform", "offscreen", "--smoke"])


def test_an_unknown_front_end_is_refused(capsys):
    with pytest.raises(SystemExit) as exc:
        entry.parse_ui(["--ui", "gtk"])
    assert exc.value.code == 2
    assert "invalid choice: 'gtk'" in capsys.readouterr().err


def test_ui_qt_starts_the_qt_front_end_with_the_resolved_paths(monkeypatch):
    calls = []
    fake = types.ModuleType("chordnotepad_desktop.main")
    fake.run = lambda paths, argv: calls.append((paths, argv)) or 7
    monkeypatch.setitem(sys.modules, "chordnotepad_desktop.main", fake)
    monkeypatch.setattr(entry.importlib.util, "find_spec", lambda name: object())
    with pytest.raises(SystemExit) as exc:
        entry.main(["--ui", "qt", "--smoke"])
    assert exc.value.code == 7
    assert calls == [(entry.APP_PATHS, ["--smoke"])]


def test_ui_qt_without_pyside6_says_so(monkeypatch, capsys):
    monkeypatch.setattr(entry.importlib.util, "find_spec", lambda name: None)
    assert entry.run_qt([]) == 2
    assert "--ui qt needs PySide6" in capsys.readouterr().err


def test_the_default_starts_the_tk_application(monkeypatch):
    from chordnotepad_tk import application

    calls = []
    monkeypatch.setattr(application.Application, "main",
                        classmethod(lambda cls, paths: calls.append(paths) or 0))
    with pytest.raises(SystemExit) as exc:
        entry.main([])
    assert exc.value.code == 0
    assert calls == [entry.APP_PATHS]


def test_the_qt_package_imports_nothing_on_its_own():
    """The entry point checks for PySide6 before importing the Qt package."""
    import ast
    from pathlib import Path

    init = Path(entry.__file__).resolve().parents[1] / "chordnotepad_desktop" / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]


def test_the_qt_package_never_imports_the_tk_one():
    """Tk is deleted after the switch. Only main.py's ``__main__`` block may use its entry point."""
    import ast
    from pathlib import Path

    package = Path(entry.__file__).resolve().parents[1] / "chordnotepad_desktop"
    found = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        body = [node for node in tree.body if not (
            isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and getattr(node.test.left, "id", None) == "__name__")]
        for top in body:
            for node in ast.walk(top):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                found += [f"{path.name}:{node.lineno} {n}" for n in names
                          if n.split(".")[0] == "chordnotepad_tk"]
    assert found == []

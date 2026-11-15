"""The Qt window is a thin view over the session.

``chordnotepad_desktop`` talks to the session (commands, subscribed states and
events, through ``SessionStore``) plus pure view concerns, so the wiring exists
once, in ``chordnotepad.session``, for the desktop and the Android UI alike
(``docs/architecture/session.md``). tests/qt/test_qt_session_store.py keeps the
calls on the session to the allow-list; these checks keep the imports
honest. They replace the Tk main window's guard (test_main_window_guard.py).

Services (app data, logging and the like) are plumbing the window may use;
only ``application.py`` builds the session. The documented viewmodel
exceptions:

* ``chord_sheet.py`` paints from the strip's rendered song, which it reads
  through ``AppSession.chord_sheet_model`` (a ``ChordSheetViewModel``).
* ``identifier.py`` takes the identifier's note spelling and lowest key from
  its viewmodel module (plain functions and constants).
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "desktop" / "chordnotepad_desktop"

#: Who may import which core layer.
ALLOWED = {
    ("chordnotepad", "viewmodels"): {"chord_sheet.py", "identifier.py"},
}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module
            # from chordnotepad import services
            yield from (f"{node.module}.{a.name}" for a in node.names)


def test_only_the_documented_modules_import_viewmodels():
    found = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        for module in _imports(path):
            layer = tuple(module.split(".")[:2])
            if layer in ALLOWED and path.name not in ALLOWED[layer]:
                found.setdefault(path.name, set()).add(module)
    assert found == {}


def test_only_the_application_builds_the_session():
    users = {path.name for path in sorted(PACKAGE.rglob("*.py"))
             if any(m.startswith("chordnotepad.session.session") or m == "chordnotepad.session.bootstrap"
                    for m in _imports(path))}
    assert users == {"application.py"}


def test_the_exceptions_still_exist():
    """A stale entry here would hide a new import in its place."""
    for files in ALLOWED.values():
        for name in files:
            assert (PACKAGE / name).is_file(), name

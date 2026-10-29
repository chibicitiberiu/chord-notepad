"""The Tk main window is a thin view over the session.

``ui/main_window.py`` talks to the session only (commands, subscribed states
and events) plus pure view concerns, so the wiring exists once, in
``src/session/``, for the Tk and the Android UI alike
(``docs/architecture/session.md``). These checks keep it that way.

The one documented exception lives elsewhere: the chord-sheet panel
(``ui/chord_sheet/panel.py``) still paints from the strip's rendered song,
which it reads through ``AppSession.chord_sheet_model``.
"""

import ast
import re
from pathlib import Path

MAIN_WINDOW = Path(__file__).parent.parent / "src" / "ui" / "main_window.py"


def _source() -> str:
    return MAIN_WINDOW.read_text(encoding="utf-8")


def _imported_modules():
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_main_window_never_mentions_a_viewmodel():
    hits = [(n, line.strip()) for n, line in enumerate(_source().splitlines(), 1)
            if re.search("viewmodel", line, re.IGNORECASE)]
    assert hits == [], f"main_window.py refers to viewmodels: {hits}"


def test_main_window_imports_no_viewmodels_services_or_application():
    forbidden = [m for m in _imported_modules()
                 if m.split(".")[0] in ("viewmodels", "services", "application")]
    assert forbidden == []


def test_main_window_reaches_nothing_through_the_application():
    assert not re.search(r"\.application\b|\bapplication\.", _source()), \
        "main_window.py should get everything from the session, host and resources"

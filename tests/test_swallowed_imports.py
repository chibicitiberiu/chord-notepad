"""Imports of our own modules whose failure the code swallows must resolve.

A few imports sit in ``try`` blocks that fall back quietly: the build info
behind the About box and the window title (``chordnotepad_tk.application``,
``chordnotepad_tk.main_window``), the voicing models behind
``PlaybackService`` and the Android host's chord-sheet check. After a module
moves, a stale name there doesn't fail anything: the desktop shows
"dev-local", Android runs without the chord sheet. These tests make such a
name fail here instead.
"""

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ROOTS = {
    "chordnotepad": REPO / "core" / "chordnotepad",
    "chordnotepad_tk": REPO / "desktop" / "chordnotepad_tk",
    "chordnotepad_desktop": REPO / "desktop" / "chordnotepad_desktop",
    "chordnotepad_android": REPO / "android" / "app" / "src" / "main" / "python" / "chordnotepad_android",
}


def _guarded_imports():
    """(file, line, module, names) for each own-package import inside a try block."""
    found = []
    for folder in ROOTS.values():
        for path in sorted(folder.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Try):
                    continue
                for stmt in node.body:
                    for imp in ast.walk(stmt):
                        if isinstance(imp, ast.ImportFrom) and imp.level == 0 and imp.module:
                            found.append((path, imp.lineno, imp.module, [a.name for a in imp.names]))
                        elif isinstance(imp, ast.Import):
                            found += [(path, imp.lineno, a.name, []) for a in imp.names]
    own = [entry for entry in found if entry[2].split(".")[0] in ROOTS]
    return sorted(set((p.relative_to(REPO).as_posix(), n, m, tuple(names)) for p, n, m, names in own))


GUARDED = _guarded_imports()


def test_the_scan_finds_the_known_guarded_imports():
    modules = {module for _, _, module, _ in GUARDED}
    assert {"chordnotepad_desktop.build_info", "chordnotepad_tk.main_window",
            "chordnotepad.viewmodels.chord_sheet_viewmodel",
            "chordnotepad.models.fretboard_spec"} <= modules


@pytest.mark.parametrize("where, line, module, names", GUARDED,
                         ids=[f"{w}:{n}" for w, n, _, _ in GUARDED])
def test_guarded_import_resolves(where, line, module, names):
    mod = importlib.import_module(module)
    for name in names:
        assert hasattr(mod, name) or importlib.util.find_spec(f"{module}.{name}"), (
            f"{where}:{line}: {module} has no {name}")


def test_build_info_imports_under_its_package_name():
    from chordnotepad_desktop import build_info

    assert build_info.__name__ == "chordnotepad_desktop.build_info"
    assert build_info.BASE_VERSION == (REPO / "VERSION").read_text(encoding="utf-8").strip()


def test_the_window_title_and_about_box_get_the_build_info():
    """main_window reads build_info at import; "dev-local" means the import failed."""
    from chordnotepad_desktop import build_info
    from chordnotepad_tk import main_window

    assert main_window.VERSION == build_info.VERSION != "dev-local"
    assert main_window.BUILD_NUMBER == build_info.BUILD_NUMBER


def test_android_host_finds_the_chord_sheet():
    from chordnotepad_android import host

    assert host._chord_sheet_available() is True

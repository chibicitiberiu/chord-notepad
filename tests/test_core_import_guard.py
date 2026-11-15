"""The shared core must import without desktop-only libraries.

The Android build (Chaquopy) has no PySide6, tkinter, Pillow or jeepney
(the last three were the Tk window's, removed in 0.6.0). Every module of the
``chordnotepad`` package (``core/chordnotepad``) is imported in a fresh
interpreter with those libraries blocked, so a stray top-level import fails
here rather than on a phone. There is no exclusion list: desktop-only code
lives in the desktop app's package (``desktop/chordnotepad_desktop``).

The second half checks that the old top-level names (``session``, ``ui``,
``constants``...) can't be imported any more, so no second copy of a core
module can load next to the ``chordnotepad`` one.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
CORE = REPO / "core"
PACKAGE = CORE / "chordnotepad"
GRADLE = REPO / "android" / "app" / "build.gradle.kts"
ANDROID_PYTHON = REPO / "android" / "app" / "src" / "main" / "python"

BLOCKED = ("tkinter", "_tkinter", "PIL", "jeepney", "PySide6", "shiboken6")

#: The top-level names the code had before it moved into packages (A3),
#: and the folder that held them (a leftover src/ would import as a
#: namespace package).
OLD_ROOTS = (
    "app_paths", "application", "audio", "build_info", "chord", "chord_sheet", "constants",
    "exceptions", "main", "models", "services", "session", "settings_forms", "ui", "utils",
    "viewmodels", "src",
)

_PROBE = r"""
import importlib, json, sys
blocked = set(json.loads(sys.argv[1]))

class _Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in blocked:
            raise ModuleNotFoundError(f"No module named {name!r} (blocked)", name=name)
        return None

sys.meta_path.insert(0, _Block())
sys.path.insert(0, sys.argv[2])
failures = {}
for mod in json.loads(sys.argv[3]):
    try:
        importlib.import_module(mod)
    except Exception as exc:
        failures[mod] = f"{type(exc).__name__}: {exc}"
leaked = sorted(m for m in sys.modules if m.split(".")[0] in blocked)
print(json.dumps({"failures": failures, "leaked": leaked}))
"""


def _core_modules():
    mods = []
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = path.relative_to(CORE).with_suffix("").parts
        if "__pycache__" in parts:
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mods.append(".".join(parts))
    return mods


def _probe(modules):
    out = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, json.dumps(BLOCKED), str(CORE), json.dumps(modules)],
        capture_output=True, text=True, timeout=300,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_walk_finds_the_whole_core():
    mods = _core_modules()
    assert mods[0] == "chordnotepad"
    assert {"chordnotepad.session.host", "chordnotepad.session.errors",
            "chordnotepad.chord_sheet.clef_assets", "chordnotepad.app_paths"} <= set(mods)
    assert len(mods) > 100


def test_core_imports_without_desktop_libraries():
    result = _probe(_core_modules())
    assert not result["failures"], "Core modules import desktop-only libraries:\n" + "\n".join(
        f"  {m}: {e}" for m, e in sorted(result["failures"].items()))
    assert result["leaked"] == []


def test_the_desktop_package_is_not_inside_the_core():
    assert not (PACKAGE / "ui").exists()
    for name in ("main", "application", "build_info", "launcher"):
        assert not (PACKAGE / f"{name}.py").exists()
        assert (REPO / "desktop" / "chordnotepad_desktop" / f"{name}.py").is_file()


@pytest.mark.parametrize("name", OLD_ROOTS)
def test_old_top_level_names_are_gone(name):
    # pytest.ini puts core/, desktop/ and the Android glue on sys.path, so
    # this also checks no folder there has a module by an old name.
    assert importlib.util.find_spec(name) is None, (
        f"'{name}' is importable as a top-level module: a second copy of the core next to "
        f"chordnotepad.{name}, or a stray src/ on sys.path")


def test_old_top_level_names_are_gone_in_a_clean_interpreter():
    """What the Android build, the bundles and make run see: core/ and desktop/ only."""
    script = ("import importlib.util, json, sys; sys.path[:0] = sys.argv[1:3]; "
              "print(json.dumps([n for n in json.loads(sys.argv[3]) "
              "if importlib.util.find_spec(n) is not None]))")
    out = subprocess.run(
        [sys.executable, "-I", "-c", script, str(CORE), str(REPO / "desktop"),
         json.dumps(OLD_ROOTS)],
        capture_output=True, text=True, timeout=60, cwd=REPO)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == []


def test_android_ships_exactly_the_core_package():
    # Chaquopy's sourceSets: the chordnotepad package from core/ plus the glue
    # in the default src/main/python. include() filters every srcDir of the
    # set, so a glue package missing from it silently drops out of the APK.
    gradle = GRADLE.read_text(encoding="utf-8")
    block = re.search(r'srcDir\("\.\./\.\./core"\)\s*include\((.*?)\)\s*exclude\((.*?)\)', gradle, re.S)
    assert block, 'no srcDir("../../core") include(...) exclude(...) in build.gradle.kts'
    glue = {p.name for p in ANDROID_PYTHON.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert glue == {"chordnotepad_android"}
    assert set(re.findall(r'"([^"]+)"', block.group(1))) == {"chordnotepad/**"} | {f"{g}/**" for g in glue}
    assert set(re.findall(r'"([^"]+)"', block.group(2))) == {"**/__pycache__/**"}
    assert not re.search(r'srcDir\("\.\./\.\./(src|desktop)', gradle)

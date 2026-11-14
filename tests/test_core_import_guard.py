"""The shared core must import without desktop-only libraries.

The Android build (Chaquopy) has no tkinter, Pillow or jeepney. Every module
outside ``src/ui/`` and the desktop-only list below is imported in a fresh
interpreter with those libraries blocked, so a stray top-level import fails
here rather than on a phone. Desktop-only code goes under ``src/ui/``; the
list only holds the entry points next to it.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SRC = REPO / "src"
GRADLE = REPO / "android" / "app" / "build.gradle.kts"

BLOCKED = ("tkinter", "_tkinter", "PIL", "jeepney")

# Desktop-only modules outside src/ui/: they never ship on Android.
DESKTOP_ONLY = {
    "main",
    "application",
    "build_info",
}

# Core modules that still reach a blocked library. The Android port removes
# these one by one; the test fails when one starts
# importing cleanly, so the entry gets deleted instead of going stale.
KNOWN_LEAKS: set = set()

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
print(json.dumps(failures))
"""


def _core_modules():
    mods = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).with_suffix("")
        parts = rel.parts
        if parts[0] == "ui" or "__pycache__" in parts:
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts:
                continue
        name = ".".join(parts)
        if name not in DESKTOP_ONLY:
            mods.append(name)
    return mods


def _probe(modules):
    out = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(BLOCKED), str(SRC), json.dumps(modules)],
        capture_output=True, text=True, timeout=300,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_core_imports_without_desktop_libraries():
    failures = _probe(_core_modules())
    unexpected = {m: e for m, e in failures.items() if m not in KNOWN_LEAKS}
    assert not unexpected, "Core modules import desktop-only libraries:\n" + "\n".join(
        f"  {m}: {e}" for m, e in sorted(unexpected.items()))


def test_known_leaks_list_is_current():
    fixed = KNOWN_LEAKS - set(_probe(sorted(KNOWN_LEAKS)))
    assert not fixed, f"These modules import cleanly now; remove them from KNOWN_LEAKS: {sorted(fixed)}"


def test_session_package_is_core_and_imports_without_desktop_libraries():
    # The session layer is what the Android UI talks to: it must never be
    # excused as desktop-only or as a known leak.
    session = [m for m in _core_modules() if m == "session" or m.startswith("session.")]
    assert "session.host" in session and "session.errors" in session
    assert not set(session) & (DESKTOP_ONLY | KNOWN_LEAKS)
    assert _probe(session) == {}


def test_android_excludes_exactly_ui_and_the_desktop_only_modules():
    # Chaquopy's sourceSets exclude list ships everything else in src/.
    gradle = GRADLE.read_text(encoding="utf-8")
    block = re.search(r'srcDir\("\.\./\.\./src"\)\s*exclude\((.*?)\)', gradle, re.S)
    assert block, "no exclude(...) after srcDir(\"../../src\") in build.gradle.kts"
    excluded = set(re.findall(r'"([^"]+)"', block.group(1)))
    expected = {"__init__.py", "**/__pycache__/**", "ui/**"}
    expected |= {name.replace(".", "/") + ".py" for name in DESKTOP_ONLY}
    assert excluded == expected

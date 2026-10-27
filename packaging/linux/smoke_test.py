"""Import every app module inside an installed Flatpak or snap.

Packages are built in an environment that has more Python modules than the
one the app runs in, so a missing dependency only shows up at run time, often
as a lazy import behind a menu item. Run it inside the installed package:

    flatpak run --command=python3 io.github.chibicitiberiu.ChordNotepad - < smoke_test.py
    snap run --shell chord-notepad -c '$SNAP/bin/python3 - $SNAP/share/chord-notepad' < smoke_test.py

The optional argument is the app folder (default: the Flatpak location).
"""

import importlib
import pkgutil
import sys
from pathlib import Path

APP = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/share/chord-notepad")
sys.path.insert(0, str(APP / "src"))

failures = []
names = [m.name for m in pkgutil.iter_modules([str(APP / "src")])]
for package in [n for n in names if (APP / "src" / n).is_dir()]:
    module = importlib.import_module(package)
    names += [m.name for m in pkgutil.walk_packages(module.__path__, package + ".")]

for name in sorted(set(names)):
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001 - report every failure, not just the first
        failures.append(f"{name}: {type(exc).__name__}: {exc}")

# Lazily imported third-party code the module walk doesn't reach.
for name in ["mido", "music21.harmony", "jeepney.io.blocking", "fluidsynth", "PIL.ImageTk"]:
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: {type(exc).__name__}: {exc}")

for path in ["resources/soundfont/GeneralUser-GS.sf2", "help/build/html/index.html",
             "resources/icons/play.png", "resources/icon-32.png"]:
    if not (APP / path).exists():
        failures.append(f"missing file: {path}")

print(f"Checked {len(set(names))} app modules")
if failures:
    print("FAILED:\n  " + "\n  ".join(failures))
    sys.exit(1)
print("Smoke test passed")

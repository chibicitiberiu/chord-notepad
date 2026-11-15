"""Import every app module inside an installed Flatpak or snap.

Packages are built in an environment that has more Python modules than the
one the app runs in, so a missing dependency only shows up at run time, often
as a lazy import behind a menu item. Run it inside the installed package:

    flatpak run --command=python3 io.github.chibicitiberiu.ChordNotepad - < smoke_test.py
    snap run --shell chord-notepad -c '$SNAP/bin/python3 - $SNAP/share/chord-notepad' < smoke_test.py

The optional argument is the app folder (default: the Flatpak location).
"""

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path

APP = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/share/chord-notepad")
# The core and both front ends (Tk, and Qt for --ui qt), as the launcher puts
# them on PYTHONPATH. Importing the Qt one also loads PySide6's libraries,
# which shows a library the package lacks (no display needed).
PACKAGES = {"chordnotepad": APP / "core", "chordnotepad_tk": APP / "desktop",
            "chordnotepad_desktop": APP / "desktop"}
sys.path[:0] = [str(folder) for folder in PACKAGES.values()]

failures = []
names = []
for package, folder in PACKAGES.items():
    if not (folder / package / "__init__.py").is_file():
        failures.append(f"missing package: {folder / package}")
        continue
    # Walk the folder, not the imported package: importing it may be the
    # very thing that fails, and that has to be reported, not crash the test.
    # Not __main__: importing it starts the app.
    names += [package] + [m.name for m in pkgutil.walk_packages([str(folder / package)], package + ".")
                          if not m.name.endswith(".__main__")]
for old in ["session", "ui", "utils", "constants"]:
    if importlib.util.find_spec(old) is not None:
        failures.append(f"an old top-level module is importable: {old}")

for name in sorted(set(names)):
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001 - report every failure, not just the first
        failures.append(f"{name}: {type(exc).__name__}: {exc}")

# Lazily imported third-party code the module walk doesn't reach.
for name in ["mido", "music21.harmony", "jeepney.io.blocking", "PIL.ImageTk"]:
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{name}: {type(exc).__name__}: {exc}")

for path in ["resources/soundfont/GeneralUser-GS.sf2", "help/build/html/index.html",
             "resources/icons/play.png", "resources/icon-32.png",
             "resources/fonts/Inter-Regular.ttf", "resources/fonts/NotoSansMono-Regular.ttf",
             "resources/qt-icons/mdi/play.svg", "desktop/chordnotepad_desktop/qml/app/Main.qml"]:
    if not (APP / path).exists():
        failures.append(f"missing file: {path}")

# The app finds its files where the package put them (chordnotepad_desktop.desktop_paths).
try:
    from chordnotepad_desktop.desktop_paths import resolve_desktop_paths

    paths = resolve_desktop_paths()
    if paths.root is None or paths.root.resolve() != APP.resolve():
        failures.append(f"app files resolved to {paths.root}, not {APP}")
    elif paths.read_version() == "0.0":
        failures.append("VERSION not found next to the app")
except Exception as exc:  # noqa: BLE001
    failures.append(f"resolving the app files: {type(exc).__name__}: {exc}")

print(f"Checked {len(set(names))} app modules")
if failures:
    print("FAILED:\n  " + "\n  ".join(failures))
    sys.exit(1)
print("Smoke test passed")

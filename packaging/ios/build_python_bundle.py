#!/usr/bin/env python3
"""Build the Python half of the iOS app: the core and its packages.

    python3.14 -I packaging/ios/build_python_bundle.py OUT_DIR [--cache-dir DIR]

Writes, all precompiled (``compile_pyc.py``):

- ``OUT_DIR/app``: the core (``core/chordnotepad``) and the Swift kit's glue
  (``chordnotepad_ios``);
- ``OUT_DIR/app_packages``: the packages pinned in ``android/requirements.txt``,
  the same pure-Python wheels the APK installs, installed with
  ``pip --no-deps --target``. chardet stays out, as on the desktop (BACKLOG.md,
  iOS licensing), and music21 is the data-trimmed wheel
  ``android/tools/strip_music21.py`` builds.

The wheels come from an offline wheelhouse that
``android/tools/build_wheelhouse.py`` fills and hash-checks (it downloads only
the pins it doesn't have). ios/tools/install_python.sh copies both folders
into the app at build time, next to the standard library from
Python.xcframework.

Run it with Python 3.14, the app's interpreter version (the .pyc files are
version-specific).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "android" / "requirements.txt"
WHEELHOUSE_TOOL = ROOT / "android" / "tools" / "build_wheelhouse.py"
STRIP_TOOL = ROOT / "android" / "tools" / "strip_music21.py"
COMPILE_TOOL = Path(__file__).resolve().parent / "compile_pyc.py"
CORE = ROOT / "core" / "chordnotepad"
GLUE = ROOT / "ios" / "ChordNotepadKit" / "Sources" / "ChordNotepadKit" / "Python" / "chordnotepad_ios"

#: Pinned in android/requirements.txt but not shipped on iOS.
LEFT_OUT = {"chardet"}
#: Installed from the trimmed wheel instead of the upstream one.
TRIMMED = "music21"
TRIMMED_SUFFIX = "+cnstrip1"

PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)")


def pins(requirements: Path) -> list:
    """``(name, version)`` for every pin, in file order."""
    found = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line.strip())
        if match:
            found.append((match.group(1), match.group(2)))
    return found


def run(*args) -> None:
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True)


def copy_package(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "ios" / "build" / "wheel-cache",
                        help="where the wheelhouse and the trimmed music21 wheel are kept")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        print(f"build_python_bundle.py needs Python 3.14 (the app's), not {sys.version.split()[0]}",
              file=sys.stderr)
        return 1

    wheelhouse = args.cache_dir / "wheelhouse"
    trimmed_dir = args.cache_dir / "trimmed"
    run(sys.executable, "-I", WHEELHOUSE_TOOL, "fetch", "--requirements", REQUIREMENTS,
        "--wheelhouse", wheelhouse)
    pinned = pins(REQUIREMENTS)
    versions = dict(pinned)
    run(sys.executable, "-I", STRIP_TOOL, "--wheel",
        wheelhouse / f"{TRIMMED}-{versions[TRIMMED]}-py3-none-any.whl", "--out-dir", trimmed_dir)

    out = args.out_dir
    app, packages = out / "app", out / "app_packages"
    for folder in (app, packages):
        if folder.exists():
            shutil.rmtree(folder)
    app.mkdir(parents=True)

    copy_package(CORE, app / "chordnotepad")
    copy_package(GLUE, app / "chordnotepad_ios")

    wanted = [f"{name}=={version}" for name, version in pinned if name not in LEFT_OUT | {TRIMMED}]
    wanted.append(f"{TRIMMED}=={versions[TRIMMED]}{TRIMMED_SUFFIX}")
    run(sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--no-index",
        "--no-compile", "--only-binary", ":all:", "--find-links", wheelhouse, "--find-links", trimmed_dir,
        "--target", packages, *wanted)
    # Console scripts pip writes for the host; nothing on iOS runs them.
    shutil.rmtree(packages / "bin", ignore_errors=True)
    binaries = sorted(str(p.relative_to(packages)) for p in packages.rglob("*") if p.suffix in (".so", ".dylib"))
    if binaries:
        print(f"Binary modules in app_packages (iOS needs each as a framework): {binaries}", file=sys.stderr)
        return 1

    run(sys.executable, "-I", COMPILE_TOOL, app, packages)
    print(f"Wrote {app} and {packages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

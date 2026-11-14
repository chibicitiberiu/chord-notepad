#!/usr/bin/env python3
"""Generate the app's pinned Python dependency lists for the Linux packages.

Writes python3-deps.json (the Flatpak module) and
packaging/linux/requirements.txt (installed with --no-deps by the snap).

flatpak-pip-generator resolves the whole dependency tree, which drags in numpy
and matplotlib through music21 even though the parts of music21 we use never
import them. This pins exactly the packages below, at the versions in
Pipfile.lock, and installs them with --no-deps.

Pure-Python packages use their universal wheel (no build backend needed in the
SDK); anything without one is built from its sdist, except the packages in
ARCH_WHEELS, which come as one manylinux wheel per CPU (flatpak-builder
fetches only the current architecture's, by ``only-arches``).

Usage: packaging/flatpak/gen_python_deps.py   (needs network)
"""

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LOCK = HERE.parent.parent / "Pipfile.lock"

# Everything the app imports at runtime, plus their runtime deps. Deliberately
# left out: numpy, matplotlib, joblib, jsonpickle (music21 extras we never hit)
# and numpy for pyfluidsynth (only its get_samples/raw_audio helpers use it),
# and chardet (see PYINSTALLER_EXCLUDES in packaging/licenses/licence_inventory.py).
PACKAGES = [
    "pychord",
    "music21",
    "more-itertools",
    "requests",
    "certifi",
    "charset-normalizer",
    "idna",
    "urllib3",
    "webcolors",
    "pyfluidsynth",
    "mido",
    "packaging",
    "pillow",
    "jeepney",
    # The Qt window (--ui qt); packaging/qt_bundle.py trims the installed wheel.
    "pyside6-essentials",
    "shiboken6",
]

# Binary wheels by Flatpak architecture: Qt can't be built from an sdist in
# the SDK (PySide6 has none on PyPI anyway).
ARCH_WHEELS = {"pyside6-essentials", "shiboken6"}
FLATPAK_ARCHES = {"x86_64": "x86_64", "aarch64": "aarch64"}  # Flatpak arch -> wheel platform tag suffix

# Needed only to build the packages above from source (Pillow's sdist), so it
# goes into its own module whose files are all cleaned up afterwards. Not in
# Pipfile.lock, hence pinned here.
BUILD_ONLY = {
    "pybind11": "3.1.0",
}


def pypi_files(name: str, version: str) -> list:
    """The PyPI file entries of name==version."""
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url) as response:
        return json.load(response)["urls"]


def pick_arch_wheels(name: str, version: str, files: list) -> dict:
    """Flatpak arch -> the manylinux wheel of name==version for it."""
    picked = {}
    for arch, tag in FLATPAK_ARCHES.items():
        wheels = [f for f in files if f["filename"].endswith(".whl")
                  and re.search(rf"-manylinux_\d+_\d+_{tag}\.whl$", f["filename"])]
        if len(wheels) != 1:
            sys.exit(f"{name}=={version}: expected one manylinux {tag} wheel, found {[f['filename'] for f in wheels]}")
        picked[arch] = wheels[0]
    return picked


def pick_file(name: str, version: str, files: Optional[list] = None) -> dict:
    """Return the PyPI file entry to use for name==version."""
    files = pypi_files(name, version) if files is None else files
    universal = [f for f in files if f["filename"].endswith("-none-any.whl")]
    sdists = [f for f in files if f["packagetype"] == "sdist"]
    chosen = (universal or sdists or [None])[0]
    if chosen is None:
        sys.exit(f"{name}=={version}: no universal wheel or sdist on PyPI")
    return chosen


def make_module(name: str, packages: dict) -> dict:
    """Build a flatpak-builder module installing {package: version} offline.

    --ignore-installed matters: the SDK ships some packages (e.g. packaging)
    that the runtime doesn't, and without it pip would skip them at build time.
    """
    sources = []
    for package, version in packages.items():
        if package in ARCH_WHEELS:
            for arch, entry in pick_arch_wheels(package, version, pypi_files(package, version)).items():
                sources.append({
                    "type": "file",
                    "url": entry["url"],
                    "sha256": entry["digests"]["sha256"],
                    "only-arches": [arch],
                })
                print(f"{package}=={version} ({arch}): {entry['filename']}")
            continue
        entry = pick_file(package, version)
        sources.append({
            "type": "file",
            "url": entry["url"],
            "sha256": entry["digests"]["sha256"],
        })
        print(f"{package}=={version}: {entry['filename']}")
    return {
        "name": name,
        "buildsystem": "simple",
        "build-commands": [
            "pip3 install --verbose --exists-action=i --no-index --no-deps --ignore-installed"
            " --no-build-isolation --find-links=\"file://${PWD}\""
            " --prefix=${FLATPAK_DEST} " + " ".join(packages)
        ],
        "sources": sources,
    }


def main() -> None:
    """Write python3-deps.json next to this script."""
    locked = json.loads(LOCK.read_text())["default"]
    pinned = {name: locked[name]["version"].lstrip("=") for name in PACKAGES}
    build_only = make_module("python3-build-deps", BUILD_ONLY)
    build_only["cleanup"] = ["*"]
    runtime = make_module("python3-deps", pinned)
    runtime["modules"] = [build_only]
    out = HERE / "python3-deps.json"
    out.write_text(json.dumps(runtime, indent=4) + "\n")
    print(f"Wrote {out}")

    requirements = HERE.parent / "linux" / "requirements.txt"
    lines = ["# Generated by packaging/flatpak/gen_python_deps.py; install with --no-deps."]
    lines += [f"{name}=={version}" for name, version in pinned.items()]
    requirements.write_text("\n".join(lines) + "\n")
    print(f"Wrote {requirements}")


if __name__ == "__main__":
    main()

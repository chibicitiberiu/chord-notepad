"""android/requirements.txt must list the dependencies of the packages it pins.

Chaquopy installs the Android packages with --no-deps from an offline
wheelhouse, so a missing indirect dependency only shows up on the phone (mido
needs ``packaging`` at import: MIDI export failed with it absent).
"""

import re
from importlib import metadata
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REQUIREMENTS = Path(__file__).resolve().parent.parent / "android" / "requirements.txt"

# music21's declared dependencies are left out on purpose (see the file's comments).
CHECKED = ["pychord", "mido", "pyfluidsynth", "requests"]

# Declared but never needed here: pyfluidsynth only uses numpy for its optional
# sample helpers (the core doesn't call them).
LEFT_OUT = {"pyfluidsynth": {"numpy"}}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pinned() -> set[str]:
    pins = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", line)
        if m:
            pins.add(_norm(m.group(1)))
    return pins


@pytest.mark.parametrize("package", CHECKED)
def test_dependencies_of_pinned_packages_are_pinned(package):
    try:
        requires = metadata.requires(package) or []
    except metadata.PackageNotFoundError:
        pytest.skip(f"{package} is not installed")
    pins = _pinned()
    assert _norm(package) in pins
    missing = []
    for text in requires:
        req = Requirement(text)
        if req.marker is not None and not req.marker.evaluate({"extra": ""}):
            continue  # an extra, or another Python version
        name = _norm(req.name)
        if name not in pins and name not in LEFT_OUT.get(package, ()):
            missing.append(name)
    assert not missing, f"{package} needs {missing}: add them to android/requirements.txt"

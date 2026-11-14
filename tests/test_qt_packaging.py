"""The Qt window in the packages (the packaging tracer, C5 of the Qt migration).

PySide6 goes into every desktop build next to Tk: the licence entries, the
Flatpak's per-architecture wheels, the parts of the wheel each build keeps
(packaging/qt_bundle.py), the PyInstaller spec, the Flatpak and snap
manifests, and the CI steps that start ``--ui qt --smoke`` from each package.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packaging" / "flatpak"))

import gen_python_deps  # noqa: E402

LOCK = json.loads((REPO / "Pipfile.lock").read_text(encoding="utf-8"))


def test_pyside6_is_a_runtime_package():
    """Every build ships it now, so it is locked with the app's packages, not the dev tools."""
    assert {"pyside6-essentials", "shiboken6"} <= set(LOCK["default"])
    assert not {"pyside6-essentials", "shiboken6"} & set(LOCK["develop"])
    assert LOCK["default"]["pyside6-essentials"]["version"].startswith("==6.12.")


def test_the_flatpak_takes_one_locked_wheel_per_architecture():
    module = json.loads((REPO / "packaging/flatpak/python3-deps.json").read_text(encoding="utf-8"))
    for package in sorted(gen_python_deps.ARCH_WHEELS):
        version = LOCK["default"][package]["version"].lstrip("=")
        prefix = package.replace("-", "_") + f"-{version}-"
        wheels = [s for s in module["sources"] if s["url"].rsplit("/", 1)[1].startswith(prefix)]
        assert sorted(a for s in wheels for a in s["only-arches"]) == ["aarch64", "x86_64"], package
        for source in wheels:
            name = source["url"].rsplit("/", 1)[1]
            assert "manylinux" in name and name.endswith(f"_{source['only-arches'][0]}.whl"), name
            assert f"sha256:{source['sha256']}" in LOCK["default"][package]["hashes"], name
    assert "pyside6-essentials shiboken6" in module["build-commands"][0]

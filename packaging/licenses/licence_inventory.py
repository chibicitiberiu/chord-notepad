"""The desktop builds' licence inventory, for the build tooling.

resources/licenses/components.json lists what each desktop build bundles.
This module is what chord-notepad.spec, the licence tools next to it and the
tests use to read it, and to check a PyInstaller build against it:

* :data:`PYINSTALLER_EXCLUDES`: modules the PyInstaller builds leave out.
* :func:`fluidsynth_dlls`: the DLLs of the FluidSynth Windows package to bundle
  (exactly the ones the inventory lists).
* :func:`classify`: maps every file PyInstaller collected to a component, or
  reports it as uncovered.
* :func:`system_packages`: on Linux, the distribution packages that own the
  shared libraries PyInstaller copied from the system, with their licence files.

No PyInstaller import: the spec passes plain ``(dest, src, typecode)`` tuples.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

REPO = Path(__file__).resolve().parents[2]
LICENSES = REPO / "resources" / "licenses"
COMPONENTS = LICENSES / "components.json"

BUILDS = ("windows", "macos", "linux", "flatpak", "snap")

# The user guide's Sphinx output: its _static folder holds Sphinx's, the
# theme's and their fonts' files (each with its own component) next to the
# few the repository's help/_static adds. The rest of the guide lies under
# the repository too, so without this a new third-party file there would
# quietly count as the app's.
GUIDE_STATIC = "help/build/html/_static/"


def guide_own_static(repo: Path = REPO) -> set:
    """The guide's _static files that come from help/_static (the app's own), lower-cased."""
    base = Path(repo) / "help" / "_static"
    return {p.relative_to(base).as_posix().lower() for p in base.rglob("*") if p.is_file()} if base.is_dir() else set()

# Imported by music21 (optionally) or present only because the build venv
# also holds the dev tools. The app never imports them: the Flatpak and the
# snap ship without them (packaging/flatpak/gen_python_deps.py), and
# tests/test_licences.py imports every app module with them blocked.
# Leaving them out keeps numpy's OpenBLAS and GCC Fortran runtime,
# matplotlib's fonts and the GPL readline library out of the bundles.
PYINSTALLER_EXCLUDES = (
    "numpy",
    "matplotlib",
    "mpl_toolkits",
    "pylab",
    "contourpy",
    "kiwisolver",
    "cycler",
    "fontTools",
    "pyparsing",
    "dateutil",
    "six",
    "joblib",
    "jsonpickle",
    "jinja2",
    "markupsafe",
    "yaml",
    "setuptools",
    "pkg_resources",
    "_distutils_hack",
    # CPython's readline module links GNU readline (GPL-3.0) on Linux; only
    # the interactive interpreter uses it.
    "readline",
    # chardet 7's relicensing (LGPL to 0BSD) is disputed. Only music21's
    # fileTools imports it, lazily, for files music21 reads itself, which the
    # app never does; requests falls back to charset-normalizer.
    "chardet",
)


def normalize(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def load_components(path: Path = COMPONENTS) -> list:
    """The component dicts of components.json."""
    return json.loads(Path(path).read_text(encoding="utf-8"))["components"]


def components_for(build: str, components: Optional[list] = None) -> list:
    """The components a build bundles."""
    if build not in BUILDS:
        raise ValueError(f"unknown build {build!r}")
    return [c for c in (components or load_components()) if build in c.get("builds", [])]


def build_for_platform(platform: str = sys.platform) -> str:
    """The PyInstaller build id for a ``sys.platform`` value."""
    if platform == "win32":
        return "windows"
    if platform == "darwin":
        return "macos"
    return "linux"


def match(path: str, patterns: Iterable[str]) -> bool:
    """Whether a bundle path matches one of the glob patterns.

    ``*`` crosses ``/``, and case is ignored (Windows file names).
    """
    path = path.replace("\\", "/").lower()
    return any(fnmatch.fnmatchcase(path, p.lower()) for p in patterns)


def _key(path: str) -> str:
    """A path in the form used to compare paths (resolved, case-folded on Windows)."""
    return os.path.normcase(os.path.realpath(path))


def fluidsynth_dlls(bin_dir: str, components: Optional[list] = None) -> list:
    """``(source, 'fluidsynth')`` binaries for the FluidSynth Windows package.

    Only the DLLs the inventory names under ``fluidsynth/`` go in: the package
    also has libinstpatch and libgobject, which libfluidsynth-3.dll doesn't
    load. A listed DLL that is missing is an error, so is a pattern that
    matches nothing.
    """
    names = sorted(os.listdir(bin_dir))
    picked, missing = [], []
    for c in components_for("windows", components):
        for pattern in c.get("files", []):
            if not pattern.startswith("fluidsynth/"):
                continue
            hits = [n for n in names if fnmatch.fnmatch(n.lower(), pattern[len("fluidsynth/"):].lower())]
            if not hits:
                missing.append(pattern)
            picked += [(os.path.join(bin_dir, n), "fluidsynth") for n in hits]
    if missing:
        raise SystemExit(f"FluidSynth package in {bin_dir} lacks {missing}")
    return sorted(set(picked))


@dataclass
class SystemPackage:
    """A distribution package that owns bundled system libraries."""

    name: str
    version: str
    source_name: str
    source_version: str
    license: str
    licence_files: list
    files: list = field(default_factory=list)


@dataclass
class Report:
    """What :func:`classify` found."""

    covered: dict = field(default_factory=dict)    # component id -> [dest]
    system: dict = field(default_factory=dict)     # package name -> SystemPackage
    uncovered: list = field(default_factory=list)  # (dest, src, typecode, why)


def distribution_files() -> dict:
    """Resolved path of every installed distribution file -> normalized distribution name."""
    from importlib import metadata

    owners = {}
    for dist in metadata.distributions():
        name = normalize(dist.metadata["Name"] or "")
        for f in dist.files or []:
            try:
                owners[_key(dist.locate_file(f))] = name
            except (OSError, ValueError):
                continue
    return owners


def _under(path: str, roots: Iterable[str]) -> bool:
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots if r)


def classify(
    entries: Iterable[tuple],
    build: str,
    *,
    components: Optional[list] = None,
    owners: Optional[dict] = None,
    stdlib_roots: Optional[list] = None,
    pyinstaller_root: Optional[str] = None,
    repo: Path = REPO,
    resolve_system: Optional[Callable[[str], Optional[SystemPackage]]] = None,
    own_static: Optional[set] = None,
) -> Report:
    """Map each ``(dest, src, typecode)`` PyInstaller entry to a component.

    In order: a component's ``files`` pattern (binaries and data), the
    installed distribution that owns ``src`` (by its ``pypi`` name), this
    repository (the app), PyInstaller itself, the Python standard library
    (not for binaries: those need their own entry), and on Linux the system
    package owning a shared library (``resolve_system``). A file in the user
    guide's ``_static`` folder that no pattern covers and that isn't one of
    ``own_static`` (default: :func:`guide_own_static`) is uncovered, not the app's.
    """
    comps = components_for(build, components)
    by_pypi = {normalize(c["pypi"]): c["id"] for c in comps if c.get("pypi")}
    owners = distribution_files() if owners is None else owners
    if stdlib_roots is None:
        stdlib_roots = sorted({_key(p) for p in (sys.base_prefix, sys.base_exec_prefix)})
    if pyinstaller_root is None:
        try:
            import PyInstaller  # type: ignore[import-not-found]
            pyinstaller_root = os.path.dirname(_key(PyInstaller.__file__))
        except ImportError:
            pyinstaller_root = ""
    repo_root = _key(str(repo))
    if own_static is None:
        own_static = guide_own_static(repo)
    app_id = "chord-notepad"
    report = Report()

    def add(cid: str, dest: str) -> None:
        report.covered.setdefault(cid, []).append(dest)

    for dest, src, typecode in entries:
        dest = dest.replace("\\", "/")
        if typecode in ("SYMLINK", "OPTION", "DEPENDENCY"):
            continue
        hit = next((c["id"] for c in comps if typecode != "PYMODULE" and match(dest, c.get("files", []))), None)
        if hit:
            add(hit, dest)
            continue
        if dest.lower().startswith(GUIDE_STATIC) and dest[len(GUIDE_STATIC):].lower() not in own_static:
            report.uncovered.append((dest, src, typecode, "user guide asset (Sphinx or its theme) with no entry"))
            continue
        real = _key(src) if src and src != "-" else ""
        dist = owners.get(real)
        if dist:
            if dist in by_pypi:
                add(by_pypi[dist], dest)
            elif dist in ("pyinstaller", "pyinstaller-hooks-contrib") and "pyinstaller" in {c["id"] for c in comps}:
                # Run-time hooks (Apache-2.0 in both projects).
                add("pyinstaller", dest)
            else:
                report.uncovered.append((dest, src, typecode, f"distribution {dist} has no entry"))
            continue
        if real and _under(real, [repo_root]):
            add(app_id, dest)
            continue
        if real and pyinstaller_root and _under(real, [pyinstaller_root]):
            add("pyinstaller", dest)
            continue
        if typecode != "BINARY":
            top = dest.split(".")[0].split("/")[0]
            if (real and _under(real, stdlib_roots)) or (not real and top in sys.stdlib_module_names):
                add("cpython", dest)
                continue
        if typecode == "BINARY" and real and resolve_system:
            pkg = resolve_system(real)
            if pkg:
                report.system.setdefault(pkg.name, pkg).files.append(dest)
                continue
        report.uncovered.append((dest, src, typecode, "no component covers it"))
    return report


# --- System packages (the Linux PyInstaller build) -------------------------

def _run(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(args, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def dep5_licence_names(text: str) -> list:
    """The short licence names of a Debian (DEP-5) copyright file, in order, without repeats."""
    seen = []
    for line in text.splitlines():
        if line.startswith("License:"):
            value = line[len("License:"):].strip()
            if value and value not in seen:
                seen.append(value)
    return seen


def _dep5_licenses(text: str) -> str:
    """The short licence names of a Debian (DEP-5) copyright file, as one string."""
    return " / ".join(dep5_licence_names(text)) or "See the copyright file"


def resolve_dpkg(path: str) -> Optional[SystemPackage]:
    """The Debian/Ubuntu package that owns ``path`` (via dpkg), with its copyright file."""
    candidates = [path]
    # usrmerge: dpkg records /lib/x86_64-linux-gnu/..., the loader reports /usr/lib/...
    if path.startswith("/usr/lib/"):
        candidates.append(path[len("/usr"):])
    owner = None
    for candidate in candidates:
        out = _run("dpkg-query", "-S", candidate)
        if out:
            owner = out.splitlines()[0].split(":")[0].strip()
            break
    if not owner:
        return None
    fields = _run("dpkg-query", "-W", "-f=${Package}\t${Version}\t${source:Package}\t${source:Version}", owner)
    if not fields:
        return None
    name, version, src_name, src_version = (fields.split("\t") + ["", "", "", ""])[:4]
    base = owner.split(":")[0]
    copyright_file = Path("/usr/share/doc") / base / "copyright"
    texts, licence = [], "Unknown"
    if copyright_file.is_file():
        try:
            licence = _dep5_licenses(copyright_file.read_text(encoding="utf-8", errors="replace"))
            texts = [str(copyright_file)]
        except OSError as exc:  # unreadable: list the package anyway, the build goes on
            print(f"warning: can't read {copyright_file}: {exc}", file=sys.stderr)
    return SystemPackage(base, version, src_name or base, src_version or version, licence, texts)


def resolve_rpm(path: str) -> Optional[SystemPackage]:
    """The RPM package (Fedora and the like) that owns ``path``, with its licence files."""
    out = _run("rpm", "-qf", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{SOURCERPM}\t%{LICENSE}\n", path)
    if not out or "not owned" in out:
        return None
    name, version, srpm, licence = (out.splitlines()[0].split("\t") + ["", "", "", ""])[:4]
    files = _run("rpm", "-qL", name) or ""
    texts = [f for f in files.splitlines() if os.path.isfile(f)]
    src = re.sub(r"-[^-]+-[^-]+\.src\.rpm$", "", srpm) or name
    return SystemPackage(name, version, src, version, licence or "Unknown", texts)


def system_resolver() -> Optional[Callable[[str], Optional[SystemPackage]]]:
    """dpkg or rpm, whichever this system has (None elsewhere)."""
    if shutil.which("dpkg-query"):
        return resolve_dpkg
    if shutil.which("rpm"):
        return resolve_rpm
    return None


def os_release() -> str:
    """PRETTY_NAME from /etc/os-release, or ''."""
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def write_system_notices(packages: dict, out_dir: Path) -> list:
    """Write system.json and one text per package under ``out_dir``.

    Returns PyInstaller data entries ``(source, bundle dir)`` for them, so the
    app finds them at resources/licenses/system.json and system/<name>.txt.
    """
    out_dir = Path(out_dir)
    texts_dir = out_dir / "system"
    if texts_dir.exists():
        shutil.rmtree(texts_dir)
    texts_dir.mkdir(parents=True)
    items = []
    for name in sorted(packages):
        pkg = packages[name]
        parts = []
        for f in pkg.licence_files:
            try:
                parts.append(Path(f).read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                continue
        (texts_dir / f"{name}.txt").write_text("\n\n----------------------------------------\n\n".join(parts) + "\n",
                                               encoding="utf-8")
        items.append({
            "name": pkg.name, "version": pkg.version,
            "sourcePackage": pkg.source_name, "sourceVersion": pkg.source_version,
            "license": pkg.license, "files": sorted(pkg.files), "text": f"system/{name}.txt",
        })
    (out_dir / "system.json").write_text(json.dumps({
        "distribution": os_release(),
        "packageFormat": "deb" if shutil.which("dpkg-query") else "rpm",
        "packages": items,
    }, indent=2) + "\n", encoding="utf-8")
    return [(str(out_dir / "system.json"), "resources/licenses"),
            *[(str(p), "resources/licenses/system") for p in sorted(texts_dir.iterdir())]]


def format_uncovered(report: Report) -> str:
    """A readable list of what no component covers."""
    return "\n".join(f"  {typecode:9} {dest}  ({why}; from {src})"
                     for dest, src, typecode, why in sorted(report.uncovered))

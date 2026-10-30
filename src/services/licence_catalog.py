"""The open source licences of everything this build of the app is made of.

The data lives in ``resources/licenses``:

* ``components.json``: the hand-checked inventory of every desktop build
  (see packaging/licenses/ for the tools that keep it right), each component
  tagged with the builds that bundle it.
* ``texts/*.txt``: the licence texts the components point at.
* ``SOURCE-OFFER.txt``: where to get the corresponding source.
* ``system.json`` + ``system/*.txt``: written by the Linux PyInstaller build
  for the distribution packages whose libraries it copied in.

In the snap, the Ubuntu packages staged into it are listed from their own
copyright files (``$SNAP/usr/share/doc/<package>/copyright``).

The window that shows all this (``ui.dialogs.licences_dialog``) only lays
out what :func:`load_catalog` returns.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

#: Builds that have their own component lists (components.json "builds").
BUILDS = ("windows", "macos", "linux", "flatpak", "snap")

#: Group key -> heading, in the order the list shows them.
GROUPS: Dict[str, str] = {
    "app": "Chord Notepad",
    "runtime": "Runtime",
    "native": "Audio libraries",
    "python": "Python packages",
    "data": "Sounds, fonts and icons",
    "guide": "User guide",
    "system": "System libraries",
}

TEXT_SEPARATOR = "\n\n" + "-" * 40 + "\n\n"


@dataclass(frozen=True)
class LicenceEntry:
    """One component in the licences list.

    Attributes:
        id: Unique and stable.
        name: Display name.
        version: Version shipped, when known.
        group: A :data:`GROUPS` key.
        license: Short licence name (an SPDX expression where there is one).
        copyright: Copyright holders, when the text doesn't name them.
        url: Project home page.
        source_url: Where its source is, when the licence asks for it.
        text_paths: Licence text files to show, in order.
        note: What the component does here, and anything unusual.
    """

    id: str
    name: str
    version: Optional[str]
    group: str
    license: str
    copyright: Optional[str] = None
    url: Optional[str] = None
    source_url: Optional[str] = None
    text_paths: tuple = ()
    note: Optional[str] = None


@dataclass
class LicenceCatalog:
    """The entries of one build, and the source offer that goes with them."""

    build: Optional[str]
    entries: List[LicenceEntry] = field(default_factory=list)
    source_offer: str = ""

    def groups(self) -> List[tuple]:
        """``(group key, heading, entries)`` for each non-empty group, in display order."""
        return [(key, heading, [e for e in self.entries if e.group == key])
                for key, heading in GROUPS.items()
                if any(e.group == key for e in self.entries)]

    def get(self, entry_id: str) -> Optional[LicenceEntry]:
        """The entry with this id, or None."""
        return next((e for e in self.entries if e.id == entry_id), None)

    @staticmethod
    def text_of(entry: LicenceEntry) -> str:
        """The licence text(s) of an entry, one after the other.

        A missing file is reported in the text rather than raised: the window
        should still open.
        """
        parts = []
        for path in entry.text_paths:
            try:
                parts.append(Path(path).read_text(encoding="utf-8", errors="replace").strip())
            except OSError as exc:
                logger.warning("Licence text missing: %s (%s)", path, exc)
                parts.append(f"[Licence text not found: {Path(path).name}]")
        return TEXT_SEPARATOR.join(parts) if parts else f"Licence: {entry.license}"


def detect_build(env: Mapping[str, str] = os.environ, platform_name: str = sys.platform,
                 frozen: Optional[bool] = None, flatpak_info: str = "/.flatpak-info") -> Optional[str]:
    """Which desktop build this is, or None when running from source."""
    if env.get("FLATPAK_ID") or os.path.exists(flatpak_info):
        return "flatpak"
    if env.get("SNAP") and env.get("SNAP_NAME"):
        return "snap"
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return None
    if platform_name == "win32":
        return "windows"
    if platform_name == "darwin":
        return "macos"
    return "linux"


def _python_version() -> str:
    return platform.python_version()


def _tcl_version() -> Optional[str]:
    import tkinter
    return str(tkinter.Tcl().eval("info patchlevel"))


def _openssl_version() -> Optional[str]:
    import ssl
    match = re.match(r"OpenSSL (\S+)", ssl.OPENSSL_VERSION)
    return match.group(1) if match else None


#: ``versionFrom`` keys: the version is whatever this build actually runs.
RUNTIME_VERSIONS: Dict[str, Callable[[], Optional[str]]] = {
    "python": _python_version,
    "tcl": _tcl_version,
    "openssl": _openssl_version,
}


def _runtime_version(key: str) -> Optional[str]:
    getter = RUNTIME_VERSIONS.get(key)
    if getter is None:
        logger.warning("Unknown versionFrom %r in components.json", key)
        return None
    try:
        return getter()
    except Exception as exc:  # noqa: BLE001 - a version is nice to have, never fatal
        logger.debug("No %s version: %s", key, exc)
        return None


def parse_components(data: dict, texts_dir: Path, build: Optional[str]) -> List[LicenceEntry]:
    """The entries of components.json for ``build`` (every component when None)."""
    entries = []
    for c in data["components"]:
        if build is not None and build not in c.get("builds", []):
            continue
        if c["group"] not in GROUPS:
            raise ValueError(f"{c['id']}: unknown group {c['group']!r}")
        version = c.get("version")
        if version is None and c.get("versionFrom"):
            version = _runtime_version(c["versionFrom"])
        entries.append(LicenceEntry(
            id=c["id"], name=c["name"], version=version, group=c["group"],
            license=c["license"], copyright=c.get("copyright"), url=c.get("url"),
            source_url=c.get("sourceUrl"),
            text_paths=tuple(str(texts_dir / f"{t}.txt") for t in c.get("texts", [])),
            note=c.get("note"),
        ))
    return entries


def parse_system_packages(data: dict, base_dir: Path) -> List[LicenceEntry]:
    """Entries for system.json (the distribution packages of the Linux binary)."""
    distro = data.get("distribution") or "the build system"
    entries = []
    for pkg in data.get("packages", []):
        files = ", ".join(pkg.get("files", []))
        entries.append(LicenceEntry(
            id=f"system:{pkg['name']}", name=pkg["name"], version=pkg.get("version"),
            group="system", license=pkg.get("license") or "See the text",
            text_paths=(str(base_dir / pkg["text"]),) if pkg.get("text") else (),
            note=f"Package of {distro}" + (f" that provides {files}." if files else "."),
        ))
    return entries


#: One ``primed-stage-packages`` item: ``package[:arch]=version``.
_SNAP_PACKAGE = re.compile(r"([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9]+)?=(\S+)")


def primed_stage_packages(manifest_text: str) -> List[tuple]:
    """``(package, version)`` pairs of the Ubuntu packages primed into a snap.

    Reads only the top-level ``primed-stage-packages`` list of snapcraft's
    manifest.yaml (written with SNAPCRAFT_BUILD_INFO=1). The same file also
    lists each part's ``build-packages``, ``stage-packages`` and
    ``installed-packages`` (the latter is the whole build container), and the
    top-level ``build-packages``: none of those are what the snap ships.
    No YAML library (the app doesn't bundle one): snapcraft writes this list
    in block style, one ``- name=version`` per line, and a flow-style list
    (``[]``) is understood too.
    """
    pairs = set()
    inside = False
    for line in manifest_text.splitlines():
        if not inside:
            # A top-level key starts at column 0; the parts' keys are indented.
            match = re.match(r"primed-stage-packages:(.*)$", line)
            if not match:
                continue
            rest = match.group(1).split(" #")[0].strip()
            if rest.startswith("["):
                items = rest.strip("[]").split(",")
                pairs.update(m.groups() for m in (_SNAP_PACKAGE.fullmatch(i.strip().strip("'\"")) for i in items)
                             if m)
                break
            inside = True
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "-" or stripped.startswith("- "):
            item = stripped[1:].split(" #")[0].strip().strip("'\"")
            found = _SNAP_PACKAGE.fullmatch(item)
            if found:
                pairs.add(found.groups())
            continue
        break  # the next key: the list is over
    return sorted(pairs)


def _snap_versions(manifest: Path) -> Dict[str, str]:
    """Package -> version from the snap's build manifest (snap/manifest.yaml), if it has one."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return {}
    return dict(primed_stage_packages(text))


def snap_packages(snap_root: Path) -> List[LicenceEntry]:
    """Entries for the Ubuntu packages staged into the snap, from their copyright files."""
    doc = snap_root / "usr" / "share" / "doc"
    versions = _snap_versions(snap_root / "snap" / "manifest.yaml")
    entries = []
    for copyright_file in sorted(doc.glob("*/copyright")):
        name = copyright_file.parent.name
        try:
            head = copyright_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        licences = []
        for line in head.splitlines():
            if line.startswith("License:"):
                value = line[len("License:"):].strip()
                if value and value not in licences:
                    licences.append(value)
        entries.append(LicenceEntry(
            id=f"system:{name}", name=name, version=versions.get(name), group="system",
            license=" / ".join(licences) or "See the text",
            text_paths=(str(copyright_file),),
            note="Ubuntu package included in the snap.",
        ))
    return entries


def load_catalog(licenses_dir: Path, build: Optional[str] = None,
                 snap_root: Optional[Path] = None) -> LicenceCatalog:
    """Read the licence data for ``build`` (see :func:`detect_build`).

    Args:
        licenses_dir: The ``resources/licenses`` directory.
        build: The build to list; None lists every component (running from source).
        snap_root: Where the snap is mounted (``$SNAP``), for its Ubuntu packages.

    Raises:
        OSError, ValueError: components.json is missing or malformed.
    """
    licenses_dir = Path(licenses_dir)
    data = json.loads((licenses_dir / "components.json").read_text(encoding="utf-8"))
    entries = parse_components(data, licenses_dir / "texts", build)
    system_json = licenses_dir / "system.json"
    if system_json.is_file():
        try:
            entries += parse_system_packages(json.loads(system_json.read_text(encoding="utf-8")), licenses_dir)
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Ignoring unreadable %s: %s", system_json, exc)
    if build == "snap" and snap_root is not None:
        entries += snap_packages(Path(snap_root))
    ids = [e.id for e in entries]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate licence ids: {duplicates}")
    order = list(GROUPS)
    entries.sort(key=lambda e: (order.index(e.group), e.id != "chord-notepad", e.name.lower()))
    try:
        offer = (licenses_dir / "SOURCE-OFFER.txt").read_text(encoding="utf-8").strip()
    except OSError:
        offer = ""
    return LicenceCatalog(build=build, entries=entries, source_offer=offer)


def load_for_this_app(base_path: Path) -> LicenceCatalog:
    """The catalog of the running app (its build detected from the environment)."""
    build = detect_build()
    snap = os.environ.get("SNAP")
    return load_catalog(Path(base_path) / "resources" / "licenses", build,
                        snap_root=Path(snap) if snap else None)

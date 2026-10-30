#!/usr/bin/env python3
"""Write the third-party source bundle attached to each desktop release.

The source offer (resources/licenses/SOURCE-OFFER.txt) for the LGPL, GPL and
MPL components of the desktop builds: every ``sources`` entry of
resources/licenses/components.json, downloaded and checked against its
SHA-256 (``extract`` entries contribute only the listed members), plus a
README saying which archive belongs to which component and build.

The Linux binary and the snap take their system libraries from Ubuntu. For
those, the README and ubuntu-sources.txt list the exact source packages, with
the Launchpad URLs of their files (``--fetch-ubuntu`` downloads them into the
bundle too). The inputs are what the builds recorded:

* ``--system-json``: resources/licenses/system.json of the Linux binary,
  written by chord-notepad.spec (build/chord-notepad/licenses-system/).
* ``--snap-manifest``: snap/manifest.yaml from inside the snap (snapcraft
  writes it when SNAPCRAFT_BUILD_INFO=1).

The tar is reproducible for the same inputs (sorted, fixed owner and mtime);
the archives inside are stored as downloaded, not recompressed.

Usage:
    python3 packaging/licenses/make_source_bundle.py --out X-third-party-sources.tar
        [--cache DIR] [--system-json F] [--snap-manifest F] [--fetch-ubuntu]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from licence_inventory import COMPONENTS, LICENSES, REPO, load_components  # noqa: E402
from licence_sources import DEFAULT_CACHE, fetch  # noqa: E402

LAUNCHPAD = "https://api.launchpad.net/1.0/ubuntu/+archive/primary"
COPYLEFT = re.compile(r"\b(L?GPL|AGPL|MPL)-")


def _launchpad(params: dict) -> dict:
    url = LAUNCHPAD + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "chord-notepad-licence-tools"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def ubuntu_source_files(source: str, version: str) -> list:
    """Launchpad URLs of a source package's files (.dsc, .orig, .debian), [] if unknown."""
    try:
        found = _launchpad({"ws.op": "getPublishedSources", "source_name": source,
                            "version": version, "exact_match": "true", "ws.size": "1"})
        if not found.get("entries"):
            return []
        link = found["entries"][0]["self_link"] + "?ws.op=sourceFileUrls"
        request = urllib.request.Request(link, headers={"User-Agent": "chord-notepad-licence-tools"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return sorted(json.load(response))
    except (OSError, ValueError, KeyError) as exc:
        print(f"warning: Launchpad lookup of {source} {version} failed: {exc}", file=sys.stderr)
        return []


def ubuntu_source_of(binary: str, version: str) -> tuple:
    """(source package, source version) of an Ubuntu binary package, or the binary's own."""
    try:
        found = _launchpad({"ws.op": "getPublishedBinaries", "binary_name": binary,
                            "version": version, "exact_match": "true", "ws.size": "1"})
        if found.get("entries"):
            entry = found["entries"][0]
            return entry["source_package_name"], entry["source_package_version"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"warning: Launchpad lookup of {binary} {version} failed: {exc}", file=sys.stderr)
    return binary, version


def snap_packages(manifest: Path) -> list:
    """(binary package, version) pairs from a snap's manifest.yaml."""
    pairs = set()
    for match in re.finditer(r"^\s*-\s*([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9]+)?=(\S+)\s*$",
                             manifest.read_text(encoding="utf-8"), re.M):
        pairs.add((match.group(1), match.group(2)))
    return sorted(pairs)


def ubuntu_packages(system_jsons: list, snap_manifests: list) -> list:
    """Every Ubuntu source package the builds used: dicts with build, binaries, source, version."""
    found = {}
    for path in system_jsons:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("packageFormat") != "deb":
            print(f"note: {path} is not from a Debian-based build, skipped", file=sys.stderr)
            continue
        for pkg in data["packages"]:
            key = (pkg["sourcePackage"], pkg["sourceVersion"])
            item = found.setdefault(key, {"source": key[0], "version": key[1], "builds": set(), "binaries": set()})
            item["builds"].add("linux")
            item["binaries"].add(f"{pkg['name']} {pkg['version']}")
    for path in snap_manifests:
        for binary, version in snap_packages(Path(path)):
            key = ubuntu_source_of(binary, version)
            item = found.setdefault(key, {"source": key[0], "version": key[1], "builds": set(), "binaries": set()})
            item["builds"].add("snap")
            item["binaries"].add(f"{binary} {version}")
    return [found[k] for k in sorted(found)]


class Bundle:
    """A reproducible tar being written."""

    def __init__(self, path: Path, prefix: str):
        self._tar = tarfile.open(path, "w", format=tarfile.PAX_FORMAT)
        self._prefix = prefix
        self._names = set()

    def add(self, name: str, data: bytes) -> None:
        """Add a file (once: a second add of the same name is ignored)."""
        if name in self._names:
            return
        self._names.add(name)
        info = tarfile.TarInfo(f"{self._prefix}/{name}")
        info.size, info.mtime, info.mode = len(data), 0, 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        self._tar.addfile(info, io.BytesIO(data))

    def close(self) -> None:
        """Finish the tar."""
        self._tar.close()


def main() -> int:
    """Download, verify and pack; print a summary."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--prefix", help="top-level directory (default: ChordNotepad-<VERSION>-third-party-sources)")
    ap.add_argument("--system-json", action="append", default=[], type=Path)
    ap.add_argument("--snap-manifest", action="append", default=[], type=Path)
    ap.add_argument("--fetch-ubuntu", action="store_true", help="download the Ubuntu source packages too")
    args = ap.parse_args()
    version = (REPO / "VERSION").read_text().strip()
    prefix = args.prefix or f"ChordNotepad-{version}-third-party-sources"

    components = load_components()
    files = {}  # bundle name -> bytes
    readme = [
        f"Chord Notepad {version}: source code of third-party components",
        "=" * 60,
        "",
        (LICENSES / "SOURCE-OFFER.txt").read_text(encoding="utf-8").strip(),
        "",
        "Contents, by component (licence; builds that include it):",
        "",
    ]
    for c in components:
        if not c.get("sources") and not c.get("sourceNote"):
            continue
        readme.append(f"* {c['name']} {c.get('version', '')}".rstrip()
                      + f" ({c['license']}; {', '.join(c['builds'])})")
        for source in c.get("sources", []):
            path = fetch(source, args.cache)
            if source.get("extract"):
                with zipfile.ZipFile(path) as z:
                    for member in source["extract"]:
                        name = f"{Path(source['file']).stem}/{member}"
                        files[name] = z.read(member)
                        readme.append(f"    {name}")
            else:
                files[source["file"]] = path.read_bytes()
                readme.append(f"    {source['file']}")
            readme.append(f"      from {source['urls'][0]}")
            readme.append(f"      sha256 {source['sha256']}")
            if source.get("role"):
                readme.append(f"      {source['role']}")
        if c.get("sourceNote"):
            readme.append(f"    {c['sourceNote']}")
        readme.append("")

    ubuntu = ubuntu_packages(args.system_json, args.snap_manifest)
    if ubuntu:
        readme += ["Ubuntu source packages (Linux binary and snap): see ubuntu-sources.txt", ""]
        lines = ["# Ubuntu source packages of the libraries in the Linux binary and the snap.",
                 "# source version  (builds)  binary packages", "#   file URLs on Launchpad", ""]
        for item in ubuntu:
            urls = ubuntu_source_files(item["source"], item["version"])
            lines.append(f"{item['source']} {item['version']}  ({', '.join(sorted(item['builds']))})  "
                         + ", ".join(sorted(item["binaries"])))
            lines += [f"  {u}" for u in urls] or [
                f"  https://launchpad.net/ubuntu/+source/{item['source']}/{item['version']}"]
            if args.fetch_ubuntu:
                for url in urls:
                    request = urllib.request.Request(url, headers={"User-Agent": "chord-notepad-licence-tools"})
                    with urllib.request.urlopen(request, timeout=300) as response:
                        files[f"ubuntu/{url.rsplit('/', 1)[1]}"] = response.read()
        files["ubuntu-sources.txt"] = ("\n".join(lines) + "\n").encode()
    elif args.system_json or args.snap_manifest:
        readme += ["(No Ubuntu packages were recorded.)", ""]

    # Chord Notepad's own licence files (its full source is the separate
    # ChordNotepad-<version>-source.tar.gz).
    for own in ("LICENSE", "ADDITIONAL-TERMS.txt", "ARTWORK-TERMS.txt", "help/LICENSE"):
        files[f"chord-notepad/{own}"] = (REPO / own).read_bytes()
    files["components.json"] = COMPONENTS.read_bytes()
    files["README.txt"] = ("\n".join(readme) + "\n").encode()
    bundle = Bundle(args.out, prefix)
    for name in sorted(files):
        bundle.add(name, files[name])
    bundle.close()
    copyleft = [c["id"] for c in components if COPYLEFT.search(c["license"]) and not c.get("sources")
                and not c.get("sourceNote") and c["id"] != "chord-notepad"]
    if copyleft:
        print(f"warning: copyleft components without sources: {copyleft}", file=sys.stderr)
    print(f"{args.out}: {len(files)} files, {args.out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build the offline wheelhouse that Chaquopy's pip installs from.

Every Python package in the APK is pinned, with the sha256 of its pure-Python
(``py3-none-any``) wheel, in ``android/requirements.txt``. The Gradle build
runs pip with ``--no-index --find-links <wheelhouse>``, so nothing is fetched
from PyPI or chaquo.com during a build; this script is the only step that
touches the network, and only for files the wheelhouse doesn't have yet.

Commands:
    fetch (default)  Make sure the wheelhouse holds every pinned wheel. Files
                     already there are hash-checked offline; missing ones are
                     downloaded with ``pip download --require-hashes``
                     (pure-Python wheels only: --platform any --abi none).
    check            Offline only: exit 1 if any pinned wheel is missing or
                     doesn't match its hash.
    lock             Refresh the hashes in requirements.txt from PyPI for the
                     versions written there (after you edit a version).

To bump a package: edit its version in android/requirements.txt, run
``build_wheelhouse.py lock``, then ``build_wheelhouse.py``, and build.

The wheelhouse defaults to $CHORD_NOTEPAD_ANDROID_CACHE/wheelhouse.

Usage:
    python3 build_wheelhouse.py [fetch|check|lock] [--wheelhouse DIR] [--requirements FILE]
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REQUIREMENTS = HERE.parent / "requirements.txt"
PYTHON_VERSION = "3.14"  # Chaquopy's target Python (app/build.gradle.kts)

_REQ = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)(.*)$")
_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements(path: Path) -> list[tuple[str, str, set[str]]]:
    """Return (name, version, sha256 set) for each pinned requirement."""
    logical, buf = [], ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        if buf.strip():
            logical.append(buf.strip())
        buf = ""
    reqs = []
    for line in logical:
        m = _REQ.match(line)
        if not m:
            raise SystemExit(f"{path}: not a 'name==version --hash=...' pin: {line}")
        hashes = set(_HASH.findall(m.group(3)))
        if not hashes:
            raise SystemExit(f"{path}: {m.group(1)} has no --hash (run '{Path(__file__).name} lock')")
        reqs.append((m.group(1), m.group(2), hashes))
    return reqs


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _wheel_project(filename: str) -> str:
    return _normalize(filename.split("-", 1)[0])


def check(wheelhouse: Path, reqs) -> list[str]:
    """Return the names of requirements without a matching file in the wheelhouse."""
    by_project: dict[str, list[Path]] = {}
    if wheelhouse.is_dir():
        for f in sorted(wheelhouse.iterdir()):
            if f.suffix == ".whl":
                by_project.setdefault(_wheel_project(f.name), []).append(f)
    missing = []
    for name, version, hashes in reqs:
        files = by_project.get(_normalize(name), [])
        if not any(_sha256(f) in hashes for f in files):
            missing.append(f"{name}=={version}")
    return missing


def fetch(wheelhouse: Path, requirements: Path, reqs) -> None:
    missing = check(wheelhouse, reqs)
    if not missing:
        print(f"wheelhouse complete: {len(reqs)} pinned wheels in {wheelhouse}")
        return
    print(f"downloading into {wheelhouse}: {', '.join(missing)}")
    wheelhouse.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "download",
            "--require-hashes", "--no-deps",
            "--only-binary=:all:", "--platform", "any", "--abi", "none",
            "--implementation", "py", "--python-version", PYTHON_VERSION,
            "--dest", str(wheelhouse),
            "--requirement", str(requirements),
        ],
        check=True,
    )
    still = check(wheelhouse, reqs)
    if still:
        raise SystemExit(f"still missing after download: {', '.join(still)}")
    print(f"wheelhouse complete: {len(reqs)} pinned wheels in {wheelhouse}")


def lock(requirements: Path, reqs) -> None:
    """Rewrite every pin's --hash with its py3-none-any wheel's sha256 from PyPI."""
    text = requirements.read_text(encoding="utf-8")
    for name, version, _ in reqs:
        url = f"https://pypi.org/pypi/{_normalize(name)}/{version}/json"
        with urllib.request.urlopen(url, timeout=60) as resp:
            info = json.load(resp)
        wheels = [u for u in info["urls"] if u["filename"].endswith("-py3-none-any.whl")]
        if len(wheels) != 1:
            raise SystemExit(f"{name}=={version}: expected one py3-none-any wheel on PyPI, found {len(wheels)}")
        digest = wheels[0]["digests"]["sha256"]
        pattern = re.compile(
            rf"^({re.escape(name)}=={re.escape(version)}\s*\\\s*\n\s*--hash=sha256:)[0-9a-f]{{64}}",
            re.MULTILINE,
        )
        text, n = pattern.subn(rf"\g<1>{digest}", text)
        if n != 1:
            raise SystemExit(f"{name}=={version}: expected the 'name==version \\' / '--hash=' layout")
        print(f"{name}=={version}  {wheels[0]['filename']}  {digest}")
    requirements.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", nargs="?", default="fetch", choices=("fetch", "check", "lock"))
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument(
        "--wheelhouse",
        type=Path,
        default=Path(os.environ.get("CHORD_NOTEPAD_ANDROID_CACHE", ".")) / "wheelhouse",
    )
    args = parser.parse_args()
    reqs = parse_requirements(args.requirements)
    if args.command == "lock":
        lock(args.requirements, reqs)
    elif args.command == "check":
        missing = check(args.wheelhouse, reqs)
        if missing:
            print(f"missing or wrong hash in {args.wheelhouse}: {', '.join(missing)}", file=sys.stderr)
            return 1
        print(f"wheelhouse complete: {len(reqs)} pinned wheels in {args.wheelhouse}")
    else:
        fetch(args.wheelhouse, args.requirements, reqs)
    return 0


if __name__ == "__main__":
    sys.exit(main())

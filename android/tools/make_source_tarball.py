#!/usr/bin/env python3
"""Write the complete source of a commit, submodules included, as one .tar.gz.

The Android release's source offer (AGPL-3.0 section 6 for the app, LGPL for
FluidSynth, libsndfile and its codecs): the app, its build scripts and every
checked-out submodule (android/native/*), at the commits the build used.
Built with ``git archive`` per repository, so it holds exactly the tracked
files (no build outputs, no .git) and is reproducible: entries are sorted,
owners are root/0, mtimes are the superproject commit's time, and the gzip
header carries no name or timestamp.

Submodules that aren't checked out (FluidSynth's test/manual data, which the
build doesn't use) are skipped and listed on stderr.

Usage: python3 make_source_tarball.py --out ChordNotepad-0.4.1-source.tar.gz
           [--prefix ChordNotepad-0.4.1] [--repo .]
"""

import argparse
import gzip
import io
import subprocess
import sys
import tarfile
from pathlib import Path


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def checked_out_submodules(repo: Path) -> list:
    """Paths (relative to ``repo``) of every initialized submodule, recursively."""
    out = git(repo, "submodule", "foreach", "--recursive", "--quiet", "echo $displaypath")
    return sorted(p for p in out.decode().splitlines() if p)


def uninitialized_submodules(repo: Path) -> list:
    out = git(repo, "submodule", "status", "--recursive").decode()
    return [line.split()[1] for line in out.splitlines() if line.startswith("-")]


def build(repo: Path, out: Path, prefix: str) -> int:
    mtime = int(git(repo, "log", "-1", "--format=%ct", "HEAD").decode().strip())
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    members = {}
    for sub in [""] + checked_out_submodules(repo):
        sub_repo = repo / sub if sub else repo
        sub_prefix = f"{prefix}/{sub}/" if sub else f"{prefix}/"
        data = git(sub_repo, "archive", "--format=tar", f"--prefix={sub_prefix}", "HEAD")
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for info in tar.getmembers():
                payload = tar.extractfile(info).read() if info.isfile() else None
                # A submodule shows up in its parent's archive as an empty
                # directory; the submodule's own archive replaces it.
                members[info.name.rstrip("/")] = (info, payload)
    buf = io.BytesIO()
    # Like git archive, the commit id goes in the global header
    # (`git get-tar-commit-id < x.tar` reads it).
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": commit}) as tar:
        for name in sorted(members):
            info, payload = members[name]
            info.name = name
            info.mtime = mtime
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.pax_headers = {}
            tar.addfile(info, io.BytesIO(payload) if payload is not None else None)
    with open(out, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
        gz.write(buf.getvalue())
    return len(members)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--prefix", help="top-level directory (default: ChordNotepad-<VERSION>)")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo = args.repo.resolve()
    prefix = args.prefix or f"ChordNotepad-{(repo / 'VERSION').read_text().strip()}"
    for path in uninitialized_submodules(repo):
        print(f"not checked out, left out: {path}", file=sys.stderr)
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no").decode().strip()
    if dirty:
        print("note: uncommitted changes are not included (the tarball is HEAD)", file=sys.stderr)
    count = build(repo, args.out, prefix)
    print(f"{args.out}: {count} entries, {args.out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

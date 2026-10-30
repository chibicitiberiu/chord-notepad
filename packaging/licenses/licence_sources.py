"""Download pinned archives (source code, licence texts) into a cache.

Each entry is ``{"file", "urls", "sha256"}``: the first URL that answers with
the right SHA-256 wins, and a cached file is reused once its hash checks out.
Downloaded archives are only ever read as data (tar/zip members), never run.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

# Under build/ (git-ignored) unless CHORD_NOTEPAD_SOURCE_CACHE says otherwise.
DEFAULT_CACHE = Path(os.environ.get("CHORD_NOTEPAD_SOURCE_CACHE",
                                    Path(__file__).resolve().parents[2] / "build" / "licence-sources"))


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(entry: dict, cache: Path = DEFAULT_CACHE) -> Path:
    """The cached file for ``entry``, downloading it first if needed."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / entry["file"]
    if target.is_file() and sha256_of(target) == entry["sha256"]:
        return target
    errors = []
    for url in entry["urls"]:
        partial = target.with_suffix(target.suffix + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "chord-notepad-licence-tools"})
            with urllib.request.urlopen(request, timeout=120) as response, open(partial, "wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
        except OSError as exc:
            errors.append(f"{url}: {exc}")
            continue
        got = sha256_of(partial)
        if got != entry["sha256"]:
            errors.append(f"{url}: sha256 {got}, expected {entry['sha256']}")
            partial.unlink()
            continue
        partial.replace(target)
        print(f"downloaded {entry['file']} from {url}", file=sys.stderr)
        return target
    raise SystemExit(f"could not fetch {entry['file']}:\n  " + "\n  ".join(errors))

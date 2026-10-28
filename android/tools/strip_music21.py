#!/usr/bin/env python3
"""Build a data-trimmed music21 wheel for the Android APK.

Chord Notepad uses music21 only for chord symbols and pitches, but the upstream
wheel ships ~60 MB of corpus scores, Scala scale files, test audio and example
documents. This script downloads the pinned upstream wheel (hash-checked),
keeps every ``.py`` file (``corpus/*.py`` and ``test/*.py`` are imported at
startup, so they must stay), drops every other data file, and repacks it as
``music21-<version>+cnstrip<N>-py3-none-any.whl``.

The output is byte-for-byte deterministic: entries are sorted, timestamps are
fixed and permissions normalized, so two runs produce the same file.

Usage:
    python3 strip_music21.py --out-dir DIR [--cache-dir DIR] [--wheel PATH]

Prints the path of the trimmed wheel on stdout.
"""

import argparse
import base64
import hashlib
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "10.3.0"
WHEEL_NAME = f"music21-{VERSION}-py3-none-any.whl"
WHEEL_URL = (
    "https://files.pythonhosted.org/packages/fa/32/"
    "3790478438b1fdd0b9b5154e2ac6f91dce105743a26bf0bd20c04b1922ec/" + WHEEL_NAME
)
WHEEL_SHA256 = "f7b12100142537ef96a1f3ea567ca59df9b5a0c7323b988e9b05c56c52547ee1"

# Bump when the trimming rules change, so pip sees a new version.
STRIP_REVISION = 1
LOCAL_VERSION = f"{VERSION}+cnstrip{STRIP_REVISION}"

# Non-.py files that are kept. Everything else outside dist-info is data.
KEEP_SUFFIXES = (".py", "py.typed")
KEEP_DIST_INFO = ("METADATA", "WHEEL", "licenses/LICENSE", "top_level.txt")

# 1980-01-01, the earliest date a zip can store.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_wheel(cache_dir: Path) -> Path:
    """Return the upstream wheel from the cache, downloading it if needed."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / WHEEL_NAME
    if not target.exists() or _sha256(target) != WHEEL_SHA256:
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(WHEEL_URL, timeout=120) as resp, open(tmp, "wb") as out:
            while block := resp.read(1 << 20):
                out.write(block)
        tmp.replace(target)
    actual = _sha256(target)
    if actual != WHEEL_SHA256:
        raise SystemExit(f"music21 wheel hash mismatch: {actual} != {WHEEL_SHA256}")
    return target


def _keep(name: str, old_info: str) -> bool:
    if name.startswith(old_info + "/"):
        return name[len(old_info) + 1:] in KEEP_DIST_INFO
    return name.endswith(KEEP_SUFFIXES)


def _record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + digest.decode("ascii")


def strip(src: Path, out_dir: Path) -> Path:
    """Write the trimmed wheel into out_dir and return its path."""
    old_info = f"music21-{VERSION}.dist-info"
    new_info = f"music21-{LOCAL_VERSION}.dist-info"
    files = {}
    with zipfile.ZipFile(src) as zin:
        for info in zin.infolist():
            if info.is_dir() or not _keep(info.filename, old_info):
                continue
            data = zin.read(info)
            name = info.filename
            if name.startswith(old_info + "/"):
                name = new_info + name[len(old_info):]
                if name.endswith("/METADATA"):
                    data = data.replace(
                        f"\nVersion: {VERSION}\n".encode(),
                        f"\nVersion: {LOCAL_VERSION}\n".encode(),
                        1,
                    )
            files[name] = data

    record_name = f"{new_info}/RECORD"
    lines = [f"{name},{_record_hash(data)},{len(data)}" for name, data in sorted(files.items())]
    lines.append(f"{record_name},,")
    files[record_name] = ("\n".join(lines) + "\n").encode()

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"music21-{LOCAL_VERSION}-py3-none-any.whl"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            zout.writestr(info, files[name])
    data = buf.getvalue()
    if not out.exists() or out.read_bytes() != data:
        tmp = out.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("CHORD_NOTEPAD_ANDROID_CACHE", ".")) / "wheels",
    )
    parser.add_argument("--wheel", type=Path, help="use this upstream wheel instead of downloading")
    args = parser.parse_args()

    src = args.wheel or fetch_wheel(args.cache_dir)
    if _sha256(src) != WHEEL_SHA256:
        raise SystemExit(f"{src} is not the pinned music21 {VERSION} wheel")
    out = strip(src, args.out_dir)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

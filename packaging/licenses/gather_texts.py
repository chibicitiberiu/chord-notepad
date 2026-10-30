#!/usr/bin/env python3
"""Copy the licence texts the desktop builds bundle into resources/licenses/texts.

Each text is the upstream file, verbatim. Sources: this repository, the
Android app's already-gathered texts (the same CPython runtime libraries and
data), the installed Python distributions (run it in the pipenv venv, whose
versions are Pipfile.lock's), and pinned source archives (downloaded into the
cache, see licence_sources.py). The result is committed, so this only needs
to run when a component or its version changes; ``--check`` verifies the
committed files.

Usage:
    pipenv run python packaging/licenses/gather_texts.py [--check]

Two texts have no upstream file and are not regenerated (see ONE_OFF).
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import tarfile
import zipfile
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from licence_inventory import LICENSES, REPO, load_components  # noqa: E402
from licence_sources import DEFAULT_CACHE, fetch  # noqa: E402

OUT = LICENSES / "texts"
ANDROID = REPO / "android/app/src/main/assets/licenses/texts"
FEDORA = Path("/usr/share/licenses")

# Archives read only for their licence files (no source obligation).
TEXT_ARCHIVES = {
    "tcl9.0.3-src.tar.gz": {
        "urls": ["https://prdownloads.sourceforge.net/tcl/tcl9.0.3-src.tar.gz"],
        "sha256": "2537ba0c86112c8c953f7c09d33f134dd45c0fb3a71f2d7f7691fd301d2c33a6"},
    "tk9.0.3-src.tar.gz": {
        "urls": ["https://prdownloads.sourceforge.net/tcl/tk9.0.3-src.tar.gz"],
        "sha256": "bf344efadb618babb7933f69275620f72454d1c8220130da93e3f7feb0efbf9b"},
}

# Licence texts downloaded as they are.
TEXT_DOWNLOADS = {
    # The official plain-text legal code of CC BY-SA 4.0.
    "cc-by-sa-4.0-legalcode.txt": {
        "urls": ["https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"],
        "sha256": "28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5"},
}

# dest name -> ("file", path) | ("dist", distribution, member regex)
#            | ("archive", file name, member) | ("download", TEXT_DOWNLOADS key)
SOURCES = {
    "AGPL-3.0.txt": ("file", REPO / "LICENSE"),
    "ADDITIONAL-TERMS.txt": ("file", REPO / "ADDITIONAL-TERMS.txt"),
    "ARTWORK-TERMS.txt": ("file", REPO / "ARTWORK-TERMS.txt"),
    "help-LICENSE.txt": ("file", REPO / "help/LICENSE"),
    "CC-BY-SA-4.0.txt": ("download", "cc-by-sa-4.0-legalcode.txt"),
    "GeneralUser-GS.txt": ("file", REPO / "resources/soundfont/GeneralUser-GS.LICENSE.txt"),
    "phosphor-MIT.txt": ("file", REPO / "resources/icons/LICENSE"),
    "Bravura-OFL.txt": ("file", ANDROID / "Bravura-OFL.txt"),
    "PSF-Python.txt": ("file", ANDROID / "PSF-Python.txt"),
    "openssl-Apache-2.0.txt": ("file", ANDROID / "openssl-Apache-2.0.txt"),
    "libffi-MIT.txt": ("file", ANDROID / "libffi-MIT.txt"),
    "sqlite-public-domain.txt": ("file", ANDROID / "sqlite-public-domain.txt"),
    "zlib.txt": ("file", ANDROID / "zlib.txt"),
    "bzip2-BSD.txt": ("file", ANDROID / "bzip2-BSD.txt"),
    "xz-0BSD.txt": ("file", ANDROID / "xz-0BSD.txt"),
    "expat-MIT.txt": ("file", ANDROID / "expat-MIT.txt"),
    "mpdecimal-BSD.txt": ("file", ANDROID / "mpdecimal-BSD.txt"),
    "zstd-BSD.txt": ("file", ANDROID / "zstd-BSD.txt"),
    "GCC-exception-3.1.txt": ("file", FEDORA / "libgcc/COPYING.RUNTIME"),
    "pyinstaller-COPYING.txt": ("dist", "pyinstaller", r"licenses/COPYING\.txt$"),
    "Tcl-license.txt": ("archive", "tcl9.0.3-src.tar.gz", "tcl9.0.3/license.terms"),
    "Tk-license.txt": ("archive", "tk9.0.3-src.tar.gz", "tk9.0.3/license.terms"),
    "LGPL-2.1.txt": ("archive", "fluidsynth-2.3.4.tar.gz", "fluidsynth-2.3.4/LICENSE"),
    "LGPL-2.0.txt": ("archive", "glib-2.26.1.tar.bz2", "glib-2.26.1/COPYING"),
    "GPL-3.0.txt": ("archive", "gettext-0.18.1.1.tar.gz", "gettext-0.18.1.1/COPYING"),
    "flac-BSD.txt": ("archive", "flac-1.3.2.tar.xz", "flac-1.3.2/COPYING.Xiph"),
    "vorbis-BSD.txt": ("archive", "libvorbis-1.3.5.tar.xz", "libvorbis-1.3.5/COPYING"),
    "ogg-BSD.txt": ("archive", "libogg-1.3.2.tar.xz", "libogg-1.3.2/COPYING"),
    "gcem-Apache-2.0.txt": ("archive", "gcem-012ae73c6d0a2cb09ffe86475f5c6fba3926e200.tar.gz",
                            "gcem-012ae73c6d0a2cb09ffe86475f5c6fba3926e200/LICENSE"),
    "pychord-MIT.txt": ("dist", "pychord", r"licenses/LICENSE$"),
    "music21-BSD.txt": ("dist", "music21", r"licenses/LICENSE$"),
    "chardet-0BSD.txt": ("dist", "chardet", r"licenses/LICENSE$"),
    "more-itertools-MIT.txt": ("dist", "more-itertools", r"licenses/LICENSE$"),
    "requests-Apache-2.0.txt": ("dist", "requests", r"licenses/LICENSE$"),
    "requests-NOTICE.txt": ("dist", "requests", r"licenses/NOTICE$"),
    "certifi-MPL-2.0.txt": ("dist", "certifi", r"licenses/LICENSE$"),
    "charset-normalizer-MIT.txt": ("dist", "charset-normalizer", r"licenses/LICENSE$"),
    "idna-BSD.txt": ("dist", "idna", r"licenses/LICENSE\.md$"),
    "urllib3-MIT.txt": ("dist", "urllib3", r"licenses/LICENSE\.txt$"),
    "webcolors-BSD.txt": ("dist", "webcolors", r"licenses/LICENSE$"),
    "pyfluidsynth-LGPL-2.1.txt": ("dist", "pyfluidsynth", r"licenses/LICENSE$"),
    "mido-MIT.txt": ("dist", "mido", r"\.dist-info/LICENSE$"),
    "packaging-Apache-2.0.txt": ("dist", "packaging", r"licenses/LICENSE\.APACHE$"),
    "packaging-BSD.txt": ("dist", "packaging", r"licenses/LICENSE\.BSD$"),
    "pillow.txt": ("dist", "pillow", r"licenses/LICENSE$"),
    "jeepney-MIT.txt": ("dist", "jeepney", r"licenses/LICENSE$"),
}

# Kept as committed (no upstream file to copy):
#   msvc-runtime.txt  written by hand (what Microsoft's terms allow).
#   winpthreads.txt   <- https://raw.githubusercontent.com/mirror/mingw-w64/v5.0.4/mingw-w64-libraries/winpthreads/COPYING
ONE_OFF = ["msvc-runtime.txt", "winpthreads.txt"]


def archive_entries() -> dict:
    """File name -> download entry, for every archive a text may come from."""
    entries = {name: {"file": name, **e} for name, e in TEXT_ARCHIVES.items()}
    for component in load_components():
        for source in component.get("sources", []):
            entries.setdefault(source["file"], source)
    return entries


def read(spec: tuple, cache: Path) -> str:
    """The text a SOURCES spec names, with CRLF line ends made LF."""
    kind = spec[0]
    if kind == "file":
        data = Path(spec[1]).read_bytes()
    elif kind == "dist":
        dist = metadata.distribution(spec[1])
        names = [str(f) for f in dist.files or [] if re.search(spec[2], str(f))]
        if len(names) != 1:
            raise SystemExit(f"{spec[1]}: {spec[2]!r} matched {names}")
        data = Path(dist.locate_file(names[0])).read_bytes()
    elif kind == "download":
        data = fetch({"file": spec[1], **TEXT_DOWNLOADS[spec[1]]}, cache).read_bytes()
    elif kind == "archive":
        path = fetch(archive_entries()[spec[1]], cache)
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                data = z.read(spec[2])
        else:
            with tarfile.open(path) as tar:
                member = tar.extractfile(spec[2])
                if member is None:
                    raise SystemExit(f"{spec[1]}: no {spec[2]}")
                data = member.read()
    else:
        raise SystemExit(f"bad source {spec}")
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="strict", newline=None).read()


def main() -> int:
    """Write (or with --check, compare) every text; report extras and gaps."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="compare, don't write")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    bad = 0
    for dest, spec in SOURCES.items():
        text = read(spec, args.cache)
        target = OUT / dest
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                print(f"differs: {target.relative_to(REPO)}")
                bad += 1
        else:
            target.write_text(text, encoding="utf-8")
    for name in ONE_OFF:
        if not (OUT / name).exists():
            print(f"missing: {name}")
            bad += 1
    known = set(SOURCES) | set(ONE_OFF)
    for extra in sorted(p.name for p in OUT.iterdir() if p.name not in known):
        print(f"not in the table: {extra}")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

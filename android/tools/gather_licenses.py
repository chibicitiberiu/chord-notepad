#!/usr/bin/env python3
"""Copies the licence texts the Android app bundles into assets/licenses/texts.

Each text is the upstream file, verbatim, except where SOURCES says otherwise.
Sources: the pinned wheels in the offline wheelhouse, the native submodules,
this repository, the pinned @mdi/svg tarball (tools/mdi_icons.py), (for components with no source tree here) a distribution's
licence directory, and the Android SDK's own license agreement. The texts only
the play flavour needs (Play Billing and the Play services libraries it pulls
in) go to src/play/assets/licenses/texts instead. The result is committed, so this only needs to run when a
component or its version changes; ``--check`` verifies the committed files.

Usage:
    python3 android/tools/gather_licenses.py [--check] [--wheelhouse DIR]

The wheelhouse defaults to $CHORD_NOTEPAD_ANDROID_CACHE/wheelhouse.
Three texts have no local source and are not regenerated (see ONE_OFF).
"""
import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "android/app/src/main/assets/licenses/texts"
PLAY_OUT = REPO / "android/app/src/play/assets/licenses/texts"
NATIVE = REPO / "android/native"
FEDORA = Path("/usr/share/licenses")

# dest name -> ("file", path) | ("wheel", package, member regex) | ("python",)
#            | ("until", path, marker line prefix: text before it)
#            | ("mdi", member): a file of the @mdi/svg tarball in the cache
SOURCES = {
    "AGPL-3.0.txt": ("file", REPO / "LICENSE"),
    "GeneralUser-GS.txt": ("file", REPO / "resources/soundfont/GeneralUser-GS.LICENSE.txt"),
    "Apache-2.0.txt": ("file", NATIVE / "oboe/LICENSE"),
    "Apache-2.0-LLVM-exception.txt": ("until", FEDORA / "llvm-libs/LICENSE.TXT", "Software from third parties"),
    "LGPL-2.1.txt": ("file", NATIVE / "fluidsynth/LICENSE"),
    "libsndfile-LGPL-2.1.txt": ("file", NATIVE / "libsndfile/COPYING"),
    "ogg-BSD.txt": ("file", NATIVE / "ogg/COPYING"),
    "vorbis-BSD.txt": ("file", NATIVE / "vorbis/COPYING"),
    "opus-BSD.txt": ("file", NATIVE / "opus/COPYING"),
    "flac-BSD.txt": ("file", NATIVE / "flac/COPYING.Xiph"),
    "signalsmith-dsp-MIT.txt": ("file", NATIVE / "signalsmith-dsp/LICENSE.txt"),
    "signalsmith-linear-MIT.txt": ("file", NATIVE / "signalsmith-linear/LICENSE.txt"),
    "signalsmith-hilbert-0BSD.txt": ("file", NATIVE / "signalsmith-hilbert/LICENSE.txt"),
    "PSF-Python.txt": ("python",),
    "openssl-Apache-2.0.txt": ("file", FEDORA / "openssl-libs/LICENSE.txt"),
    "libffi-MIT.txt": ("file", FEDORA / "libffi/LICENSE"),
    "bzip2-BSD.txt": ("file", FEDORA / "bzip2/LICENSE"),
    "xz-0BSD.txt": ("file", FEDORA / "xz/COPYING.0BSD"),
    "zlib.txt": ("file", FEDORA / "zlib-ng/LICENSE.md"),
    "expat-MIT.txt": ("file", FEDORA / "expat/COPYING"),
    "zstd-BSD.txt": ("file", FEDORA / "libzstd/LICENSE"),
    "mpdecimal-BSD.txt": ("file", FEDORA / "mpdecimal/COPYRIGHT.txt"),
    "pychord-MIT.txt": ("wheel", "pychord", r"licenses/LICENSE$"),
    "mido-MIT.txt": ("wheel", "mido", r"\.dist-info/LICENSE$"),
    "packaging-Apache-2.0.txt": ("wheel", "packaging", r"licenses/LICENSE\.APACHE$"),
    "packaging-BSD.txt": ("wheel", "packaging", r"licenses/LICENSE\.BSD$"),
    "pyfluidsynth-LGPL-2.1.txt": ("wheel", "pyfluidsynth", r"licenses/LICENSE$"),
    "music21-BSD.txt": ("wheel", "music21", r"licenses/LICENSE$"),
    "chardet-LGPL-2.1.txt": ("wheel", "chardet", r"licenses/LICENSE$"),
    "webcolors-BSD.txt": ("wheel", "webcolors", r"licenses/LICENSE$"),
    "more-itertools-MIT.txt": ("wheel", "more_itertools", r"licenses/LICENSE$"),
    "requests-Apache-2.0.txt": ("wheel", "requests", r"licenses/LICENSE$"),
    "requests-NOTICE.txt": ("wheel", "requests", r"licenses/NOTICE$"),
    "urllib3-MIT.txt": ("wheel", "urllib3", r"licenses/LICENSE.txt$"),
    "idna-BSD.txt": ("wheel", "idna", r"licenses/LICENSE.md$"),
    "certifi-MPL-2.0.txt": ("wheel", "certifi", r"licenses/LICENSE$"),
    "charset-normalizer-MIT.txt": ("wheel", "charset_normalizer", r"licenses/LICENSE$"),
    "mdi-Pictogrammers-Free-License.txt": ("mdi", "package/LICENSE"),
}

# Play flavour only. AboutLibraries names the Play libraries' POM licence
# ("Android Software Development Kit License") ASDKL; the text is the SDK
# License Agreement that sdkmanager stores with each installed package.
PLAY_SOURCES = {
    "ASDKL.txt": ("sdk-license", "android-sdk-license"),
}

# Downloaded once, kept as committed (no local source):
#   Chaquopy-MIT.txt <- https://raw.githubusercontent.com/chaquo/chaquopy/master/LICENSE.txt
#   Bravura-OFL.txt  <- https://raw.githubusercontent.com/steinbergmedia/bravura/master/LICENSE.txt
#   sqlite-public-domain.txt is written by hand (SQLite's blessing; sqlite.org/copyright.html).
ONE_OFF = ["Chaquopy-MIT.txt", "Bravura-OFL.txt", "sqlite-public-domain.txt"]


def read(spec, wheelhouse: Path) -> str:
    kind = spec[0]
    if kind == "file":
        return Path(spec[1]).read_text(encoding="utf-8")
    if kind == "until":
        text = Path(spec[1]).read_text(encoding="utf-8")
        return text[: text.index(spec[2])].rstrip() + "\n"
    if kind == "python":
        import builtins
        builtins.license._Printer__setup()  # type: ignore[attr-defined]
        return "\n".join(builtins.license._Printer__lines) + "\n"  # type: ignore[attr-defined]
    if kind == "wheel":
        wheels = sorted(wheelhouse.glob(f"{spec[1]}-*.whl"))
        if not wheels:
            raise SystemExit(f"no wheel for {spec[1]} in {wheelhouse}")
        with zipfile.ZipFile(wheels[-1]) as z:
            names = [n for n in z.namelist() if re.search(spec[2], n)]
            if len(names) != 1:
                raise SystemExit(f"{spec[1]}: {spec[2]!r} matched {names}")
            return z.read(names[0]).decode("utf-8")
    if kind == "mdi":
        import tarfile
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mdi_icons
        with tarfile.open(mdi_icons.tarball()) as tar:
            member = tar.extractfile(spec[1])
            if member is None:
                raise SystemExit(f"@mdi/svg: no {spec[1]}")
            # Its LICENSE has CRLF line ends; kept as LF like the other texts.
            return member.read().decode("utf-8").replace("\r\n", "\n")
    if kind == "sdk-license":
        import xml.etree.ElementTree as ET
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if not sdk:
            raise SystemExit("set ANDROID_HOME (source android/local.env) for the SDK license text")
        for package in sorted(Path(sdk, "platforms").glob("*/package.xml")):
            for element in ET.parse(package).iter():
                if element.tag.endswith("license") and element.get("id") == spec[1] and element.text:
                    return element.text.strip() + "\n"
        raise SystemExit(f"no {spec[1]} in {sdk}/platforms/*/package.xml")
    raise SystemExit(f"bad source {spec}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="compare, don't write")
    ap.add_argument("--wheelhouse", default=os.path.join(
        os.environ.get("CHORD_NOTEPAD_ANDROID_CACHE", ""), "wheelhouse"))
    args = ap.parse_args()
    bad = 0
    for out, sources, one_off in ((OUT, SOURCES, ONE_OFF), (PLAY_OUT, PLAY_SOURCES, [])):
        out.mkdir(parents=True, exist_ok=True)
        for dest, spec in sources.items():
            text = read(spec, Path(args.wheelhouse))
            target = out / dest
            if args.check:
                if not target.exists() or target.read_text(encoding="utf-8") != text:
                    print(f"differs: {target.relative_to(REPO)}")
                    bad += 1
            else:
                target.write_text(text, encoding="utf-8")
        for name in one_off:
            if not (out / name).exists():
                print(f"missing: {name}")
                bad += 1
        known = set(sources) | set(one_off)
        for extra in sorted(p.name for p in out.iterdir() if p.name not in known):
            print(f"not in the table: {out.relative_to(REPO)}/{extra}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

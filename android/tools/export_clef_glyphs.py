#!/usr/bin/env python3
"""Export the chord sheet's base clef and glyph PNGs for the Android app.

The staff view's image ops carry keys like ``clef_treble:96`` or
``glyph_accidental_sharp:40:3a5a8a`` (see ``docs/ANDROID.md``, "Chord sheet op
buffer"). Kotlin draws them from the seven base PNGs embedded in
``core/chordnotepad/chord_sheet/clef_assets.py``: the part before the first
``:`` names the file, the height scales it and the optional colour tints the
black ink.

Writes ``<asset>.png`` for each base asset plus ``glyphs.json``
(``{"version": 1, "assets": {name: {"width": w, "height": h}}}``) into
``--out-dir``. Needs no Pillow: the PNG bytes are written as embedded.
Output is byte-for-byte deterministic. The Gradle task ``exportClefGlyphs``
runs this into generated assets under ``chord_sheet/``.

Usage: python3 -I export_clef_glyphs.py --out-dir DIR [--core REPO/core]
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_CORE = Path(__file__).resolve().parents[2] / "core"


def main(argv=None) -> int:
    """Write the base PNGs and their size index into ``--out-dir``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--core", type=Path, default=DEFAULT_CORE,
                        help="the folder holding the shared core's chordnotepad package")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(args.core.resolve()))
    from chordnotepad.chord_sheet.clef_assets import base_glyph_pngs, base_size

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for asset, png in base_glyph_pngs().items():
        (out / f"{asset}.png").write_bytes(png)
        width, height = base_size(asset)
        index[asset] = {"width": width, "height": height}
    (out / "glyphs.json").write_text(
        json.dumps({"version": 1, "assets": index}, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(index)} glyphs to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

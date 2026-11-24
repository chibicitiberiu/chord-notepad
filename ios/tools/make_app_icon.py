#!/usr/bin/env python3
"""Render the iOS app icon from resources/chord-notepad-icon.svg.

Writes ios/ChordNotepad/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png:
one 1024 px image, from which Xcode 14 and later make every size. iOS
rounds the corners itself, and App Store icons may have no transparency, so
the notepad sits on the cream background of the Android launcher icon
(android/tools/make_launcher_icons.py). The PNG is committed, so builds don't
need Inkscape; rerun this after changing the SVG:

    python3 ios/tools/make_app_icon.py

Inkscape renders the SVG (ImageMagick paints its linked gradient black);
Pillow composes and flattens it.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "resources" / "chord-notepad-icon.svg"
OUT = ROOT / "ios" / "ChordNotepad" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-1024.png"

SIZE = 1024
#: The notepad's share of the icon's width (iOS masks about 10% off each corner).
CONTENT = 0.74
BACKGROUND = (253, 240, 235)  # the Android launcher icon's cream


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        rendered = Path(tmp) / "icon.png"
        subprocess.run(["inkscape", str(SVG), "--export-type=png", f"--export-filename={rendered}",
                        "-w", str(SIZE), "-h", str(SIZE)], check=True, capture_output=True)
        icon = Image.open(rendered).convert("RGBA")
        icon.load()
    icon = icon.crop(icon.getbbox())
    scale = SIZE * CONTENT / max(icon.size)
    icon = icon.resize((round(icon.width * scale), round(icon.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), BACKGROUND + (255,))
    canvas.alpha_composite(icon, ((SIZE - icon.width) // 2, (SIZE - icon.height) // 2))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(OUT, optimize=True)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

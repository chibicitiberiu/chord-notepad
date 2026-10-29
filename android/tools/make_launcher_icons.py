#!/usr/bin/env python3
"""Render the Android launcher icons from resources/chord-notepad-icon.svg.

Writes the adaptive icon layers (foreground, monochrome) and legacy icons for
every density into android/app/src/main/res/mipmap-*/. The PNGs are committed,
so builds don't need Inkscape; rerun this after changing the SVG:

    python3 android/tools/make_launcher_icons.py

Inkscape renders the SVG (its linked gradients render correctly there, unlike
ImageMagick's built-in renderer); Pillow scales and composes the layers.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "resources" / "chord-notepad-icon.svg"
RES = ROOT / "android" / "app" / "src" / "main" / "res"

# Adaptive icons are 108 dp with a 72 dp visible area; launchers mask it to a
# circle or squircle. The notepad (a square object) must fit the 66 dp safe
# circle, so it takes 54% of the canvas.
CONTENT = 0.54
BACKGROUND = (253, 240, 235, 255)          # cream, also in values/ic_launcher_background.xml
NOTE_INK = (80, 58, 85)                    # the plum of the note and rings
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def render_source(px: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "icon.png"
        subprocess.run(["inkscape", str(SVG), "--export-type=png", f"--export-filename={out}",
                        "-w", str(px), "-h", str(px)], check=True, capture_output=True)
        img = Image.open(out).convert("RGBA")
        img.load()
    return img.crop(img.getbbox())


def place(icon: Image.Image, size: int, fraction: float, bg=(0, 0, 0, 0)) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg)
    target = round(size * fraction)
    w, h = icon.size
    scale = target / max(w, h)
    scaled = icon.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    canvas.alpha_composite(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def monochrome(icon: Image.Image) -> Image.Image:
    """The note and rings only (themed icons tint this single layer)."""
    out = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    src, dst = icon.load(), out.load()
    for y in range(icon.height):
        for x in range(icon.width):
            r, g, b, a = src[x, y]
            if a > 0 and abs(r - NOTE_INK[0]) + abs(g - NOTE_INK[1]) + abs(b - NOTE_INK[2]) < 60:
                dst[x, y] = (255, 255, 255, a)
    return out


def main() -> int:
    icon = render_source(1024)
    mono = monochrome(icon)
    for name, factor in DENSITIES.items():
        folder = RES / f"mipmap-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        fg = round(108 * factor)
        place(icon, fg, CONTENT).save(folder / "ic_launcher_foreground.png", optimize=True)
        place(mono, fg, CONTENT).save(folder / "ic_launcher_monochrome.png", optimize=True)
        # Legacy (API 24-25): 48 dp; the square one is the notepad as drawn,
        # the round one sits on the cream circle.
        legacy = round(48 * factor)
        place(icon, legacy, 0.92).save(folder / "ic_launcher.png", optimize=True)
        round_icon = place(icon, legacy, 0.62)
        disc = Image.new("RGBA", (legacy, legacy), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((0, 0, legacy - 1, legacy - 1), fill=BACKGROUND)
        disc.alpha_composite(round_icon)
        disc.save(folder / "ic_launcher_round.png", optimize=True)
    print(f"wrote launcher icons for {', '.join(DENSITIES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Render the Google Play listing graphics into packaging/store/play/graphics/:

- icon-512.png: the 512 px store icon, a full opaque square on the launcher's
  cream, saved as 32-bit PNG (Play's spec). Play rounds the corners and adds
  the drop shadow itself.
- feature-graphic.png: the 1024x500 banner. The icon, name and tagline on the
  left, the top of the first phone screenshot on the right.

Uses the same Inkscape rendering as make_launcher_icons.py, and the phone
screenshot from packaging/store/play/screenshots/phone/, so regenerate those
first if the app's look changed:

    python3 android/tools/make_play_graphics.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from make_launcher_icons import BACKGROUND, NOTE_INK, ROOT, place, render_source

OUT = ROOT / "packaging" / "store" / "play" / "graphics"
SHOT = ROOT / "packaging" / "store" / "play" / "screenshots" / "phone" / "01-play-fret-cards.png"
FONTS = Path("/usr/share/fonts/rsms-inter-fonts")
TAGLINE = ("Write chords above your lyrics", "and hear them played.")

# Play masks the icon with a 30% corner radius. The notepad has a defining
# shape, so it sits on Material's square keyline (about 79% of the icon)
# instead of filling the square, which keeps the rings clear of the corners.
ICON_CONTENT = 0.78


def store_icon(source: Image.Image) -> Image.Image:
    return place(source, 512, ICON_CONTENT, BACKGROUND)


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def feature_graphic(source: Image.Image) -> Image.Image:
    w, h = 1024, 500
    canvas = Image.new("RGBA", (w, h), BACKGROUND)

    # The phone screenshot, framed in plum, running off the bottom edge.
    shot = Image.open(SHOT).convert("RGB")
    shot_w = 330
    shot = shot.resize((shot_w, round(shot.height * shot_w / shot.width)), Image.LANCZOS)
    border = 10
    frame = Image.new("RGBA", (shot_w + 2 * border, shot.height + 2 * border), NOTE_INK + (255,))
    frame = rounded(frame, 36)
    frame.alpha_composite(rounded(shot, 28), (border, border))
    canvas.alpha_composite(frame, (w - frame.width - 70, 48))

    icon = place(source, 150, 1.0)
    canvas.alpha_composite(icon, (70, 110))

    draw = ImageDraw.Draw(canvas)
    title = ImageFont.truetype(str(FONTS / "InterDisplay-SemiBold.ttf"), 62)
    body = ImageFont.truetype(str(FONTS / "Inter-Regular.ttf"), 30)
    draw.text((70, 290), "Chord Notepad", font=title, fill=NOTE_INK)
    for i, line in enumerate(TAGLINE):
        draw.text((72, 375 + i * 40), line, font=body, fill=NOTE_INK + (215,))
    return canvas.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = render_source(2048)
    store_icon(source).save(OUT / "icon-512.png", optimize=True)
    feature_graphic(source).save(OUT / "feature-graphic.png", optimize=True)
    print(f"Wrote {OUT / 'icon-512.png'} and {OUT / 'feature-graphic.png'}")


if __name__ == "__main__":
    main()

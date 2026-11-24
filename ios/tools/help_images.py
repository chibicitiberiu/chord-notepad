#!/usr/bin/env python3
"""The iOS edition's screenshots (help/images/ios) from a CI run's artifacts.

The guide's iOS images come from what `.github/workflows/ios.yml` uploads: the
preview catalog (`ios-catalog`, drawn from ios/Fixtures) and the simulator's
screenshots of the running app (`ios-screenshots`). The shot list,
`ios/tools/help_shots.json`, says for each image of the guide which PNG it
comes from, the part of it to keep (in points) and the numbered callouts, as
Android's `android/tools/help_shots.json` does for the emulator. The look
of the callouts and the 256-colour PNGs are Android's (help_screenshots.py).

    gh run download <run> -n ios-catalog -D /tmp/run/catalog
    gh run download <run> -n ios-screenshots -D /tmp/run/screenshots
    python3 ios/tools/help_images.py --catalog /tmp/run/catalog --screenshots /tmp/run/screenshots
    python3 ios/tools/help_images.py ... --only player-labeled,drawer
    python3 ios/tools/help_images.py --list

Writes help/images/ios/<name>.png (and <name>.dark.png for a shot with
"dark"); a run that gives the same bytes leaves a file alone. It never
writes anywhere else (the desktop, Android and shared images are made by
their own tools). Needs Pillow; libimagequant for the palette step if
Pillow has it.
"""

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "ios/tools/help_shots.json"
OUT = ROOT / "help/images/ios"
# The app's primary colour and its text, and the halo round a callout (Android's).
PRIMARY = {"light": (63, 81, 181), "dark": (182, 195, 255)}
ON_PRIMARY = {"light": (255, 255, 255), "dark": (27, 42, 107)}
HALO = {"light": (255, 255, 255), "dark": (17, 19, 24)}
FONT_CANDIDATES = [
    "/usr/share/fonts/google-roboto/Roboto-Bold.ttf",
    "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
# Pixels per point of each source: the catalog renders the iPhone at @3x and
# the iPad at @2x, as the simulators' screenshots are.
SCALES = {"iphone": 3, "ipad": 2}


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def source(shot: dict, theme: str, catalog: Path, screenshots: Path) -> tuple[Path, int]:
    """The PNG a shot comes from in ``theme``, and its pixels per point."""
    if "catalog" in shot:
        name = shot["catalog"]
        device = name.split("-")[-1] if not name.endswith("landscape") else name.split("-")[-2]
        text = shot.get("text", "default")
        return catalog / f"{name}-{theme}-{text}.png", SCALES[device]
    name = shot["shot"]
    if theme != "light":
        raise SystemExit(f"{shot['name']}: the simulator's screenshots are light only")
    return screenshots / f"{name}.png", SCALES[name.split("-")[0]]


def draw_callouts(img: Image.Image, callouts: list, crop: tuple, scale: float, theme: str) -> None:
    """Numbered circles with leader lines to their anchors (Android's look)."""
    draw = ImageDraw.Draw(img)
    radius = 14
    font = load_font(18)
    primary, on_primary, halo = PRIMARY[theme], ON_PRIMARY[theme], HALO[theme]
    width, height = img.size
    for c in callouts:
        ax = (c["at"][0] - crop[0]) * scale
        ay = (c["at"][1] - crop[1]) * scale
        dx, dy = c.get("offset", (0, 0))
        cx = min(max(ax + dx, radius + 2), width - radius - 3)
        cy = min(max(ay + dy, radius + 2), height - radius - 3)
        dist = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
        if dist > radius + 2:
            ex = cx + (ax - cx) * radius / dist
            ey = cy + (ay - cy) * radius / dist
            draw.line([(ex, ey), (ax, ay)], fill=halo, width=5)
            draw.line([(ex, ey), (ax, ay)], fill=primary, width=2)
            draw.ellipse([ax - 4.5, ay - 4.5, ax + 4.5, ay + 4.5], fill=halo)
            draw.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=primary)
        draw.ellipse([cx - radius - 2, cy - radius - 2, cx + radius + 2, cy + radius + 2], fill=halo)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=primary)
        draw.text((cx, cy + 0.5), str(c["n"]), fill=on_primary, font=font, anchor="mm")


def panel_box(img: Image.Image, at: list, ppp: int, tolerance: int = 6) -> tuple:
    """The rectangle (points) of the panel (a dialog's card, a sheet) around
    ``at``: the rows and then the columns where most pixels have the panel's
    colour, contiguous with that point."""
    px = img.load()
    x0, y0 = round(at[0] * ppp), round(at[1] * ppp)
    colour = px[x0, y0]

    def same(p):
        return all(abs(a - b) <= tolerance for a, b in zip(p, colour))

    # The dimmed screen round a panel has none of its exact colour; a row or a
    # column through the panel has some, whatever text or controls it holds.
    xs = range(0, img.width, 2)

    def row_in(y):
        return sum(same(px[x, y]) for x in xs) > 0.05 * len(xs)

    top = y0
    while top > 0 and row_in(top - 1):
        top -= 1
    bottom = y0
    while bottom < img.height - 1 and row_in(bottom + 1):
        bottom += 1
    ys = range(top, bottom + 1, 2)

    def column_in(x):
        return sum(same(px[x, y]) for y in ys) > 0.05 * len(ys)

    left = x0
    while left > 0 and column_in(left - 1):
        left -= 1
    right = x0
    while right < img.width - 1 and column_in(right + 1):
        right += 1
    return (left / ppp, top / ppp, (right - left + 1) / ppp, (bottom - top + 1) / ppp)


def crop_of(shot: dict, img: Image.Image, ppp: int) -> tuple:
    """The part of the source to keep, in points: ``crop`` [x, y, w, h], or
    ``panel`` (the card or sheet around a point) with ``pad``, ``full_width``
    and ``to_bottom``; else the whole image."""
    full = (0, 0, img.width / ppp, img.height / ppp)
    if "panel" in shot:
        x, y, w, h = panel_box(img, shot["panel"], ppp)
        pad = shot.get("pad", 4)
        x, y, w, h = x - pad, y - pad, w + 2 * pad, h + 2 * pad
        if shot.get("full_width"):
            x, w = 0, full[2]
        if shot.get("to_bottom"):
            h = full[3] - y
        x, y = max(0, x), max(0, y)
        return (x, y, min(w, full[2] - x), min(h, full[3] - y))
    return tuple(shot.get("crop", full))


def render(shot: dict, theme: str, catalog: Path, screenshots: Path) -> Image.Image:
    """The shot cut, scaled and labelled."""
    path, ppp = source(shot, theme, catalog, screenshots)
    if not path.exists():
        raise SystemExit(f"{shot['name']}: no {path}")
    img = Image.open(path).convert("RGB")
    if "rotate" in shot:
        # The simulator's screenshot of an app on its side is the upright
        # screen's pixels: turned counterclockwise by this many degrees.
        img = img.rotate(shot["rotate"], expand=True)
    crop = crop_of(shot, img, ppp)  # x, y, width, height in points
    box = tuple(round(v * ppp) for v in (crop[0], crop[1], crop[0] + crop[2], crop[1] + crop[3]))
    img = img.crop(box)
    # Output pixels per point: Android's phone shots are 720 px for its 412 dp
    # (1.75); the iPhone's 402 pt get the same 720 px.
    scale = shot.get("scale", 720 / 402)
    size = (round(crop[2] * scale), round(crop[3] * scale))
    img = img.resize(size, Image.Resampling.LANCZOS)
    pad = round(shot.get("pad_top", 0) * scale)
    if pad:
        # Room for callouts over the app bar (Android's sit in its status bar).
        padded = Image.new("RGB", (img.width, img.height + pad), img.getpixel((2, 2)))
        padded.paste(img, (0, pad))
        img = padded
    draw_callouts(img, shot.get("callouts", []), (crop[0], crop[1] - pad / scale), scale, theme)
    return img


def save_png(img: Image.Image, path: Path) -> bool:
    """Write ``img`` as a 256-colour PNG; False when the file already had these bytes."""
    if path.parent.resolve() != OUT.resolve():
        raise SystemExit(f"refusing to write outside {OUT}: {path}")
    if features.check("libimagequant"):
        out = img.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT, dither=Image.Dither.FLOYDSTEINBERG)
    else:
        out = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    buffer = io.BytesIO()
    out.save(buffer, "PNG", optimize=True)
    data = buffer.getvalue()
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--catalog", type=Path, help="the ios-catalog artifact's folder")
    parser.add_argument("--screenshots", type=Path, help="the ios-screenshots artifact's folder")
    parser.add_argument("--only", help="comma-separated image names")
    parser.add_argument("--list", action="store_true", help="list the shots and their sources")
    args = parser.parse_args(argv)
    shots = json.loads(SHOTS.read_text())["shots"]
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {s["name"] for s in shots}
        if unknown:
            raise SystemExit(f"unknown shots: {', '.join(sorted(unknown))}")
        shots = [s for s in shots if s["name"] in wanted]
    if args.list:
        for s in shots:
            print(f"{s['name']:28} {s.get('catalog') or s.get('shot'):45} {s.get('what', '')}")
        return 0
    if not args.catalog or not args.screenshots:
        parser.error("--catalog and --screenshots are needed")
    OUT.mkdir(parents=True, exist_ok=True)
    for shot in shots:
        for theme in ["light"] + (["dark"] if shot.get("dark") else []):
            img = render(shot, theme, args.catalog, args.screenshots)
            name = shot["name"] + (".dark" if theme == "dark" else "") + ".png"
            changed = save_png(img, OUT / name)
            print(f"{name:34} {img.width}x{img.height} {'written' if changed else 'unchanged'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

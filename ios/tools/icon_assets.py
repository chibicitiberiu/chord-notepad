#!/usr/bin/env python3
"""Copy Chord Notepad's own icons into the iOS asset catalog.

The app's chrome draws SF Symbols (docs/IOS.md, "The main screen", the iOS
look); a capo, transposing and a time signature have no symbol, so those are
Chord Notepad's own drawings, Android's vector drawables
(android/res/drawable/ic_*.xml) turned into 24 x 24 SVG image sets rendered
as templates, tinted like a symbol:

    python3 -I ios/tools/icon_assets.py

Writes ios/ChordNotepad/Assets.xcassets/Icons/<name>.imageset; their strokes
and group transforms are kept. Standard library only.
"""

import json
import pathlib
import sys
import xml.etree.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parents[2]
DRAWABLES = REPO / "android/app/src/main/res/drawable"
OUT = REPO / "ios/ChordNotepad/Assets.xcassets/Icons"
ANDROID = "{http://schemas.android.com/apk/res/android}"

# The Edit ribbon's Transpose and Capo, the Insert sheet's and Playback settings' time signature.
ICONS = ["ic_transpose", "ic_capo", "ic_time_signature"]


def svg_element(node: ET.Element) -> str:
    """A path or a group of the drawable as SVG: filled paths, stroked ones
    (such as ic_time_signature's) and groups with their scale and
    translation (ic_transpose)."""
    if node.tag == "path":
        d = " ".join(node.get(ANDROID + "pathData").split())
        if node.get(ANDROID + "strokeColor") and not node.get(ANDROID + "fillColor"):
            width = node.get(ANDROID + "strokeWidth", "1")
            cap = node.get(ANDROID + "strokeLineCap", "butt")
            join = node.get(ANDROID + "strokeLineJoin", "miter")
            return (f'<path d="{d}" fill="none" stroke="#000000" stroke-width="{width}" '
                    f'stroke-linecap="{cap}" stroke-linejoin="{join}"/>')
        return f'<path d="{d}"/>'
    if node.tag == "group":
        # Android applies a group's scale, then its translation.
        tx = node.get(ANDROID + "translateX", "0")
        ty = node.get(ANDROID + "translateY", "0")
        sx = node.get(ANDROID + "scaleX", "1")
        sy = node.get(ANDROID + "scaleY", "1")
        inner = "".join(svg_element(child) for child in node)
        return f'<g transform="translate({tx} {ty}) scale({sx} {sy})">{inner}</g>'
    return ""


def svg(drawable: pathlib.Path) -> str:
    root = ET.parse(drawable).getroot()
    width = root.get(ANDROID + "viewportWidth")
    height = root.get(ANDROID + "viewportHeight")
    body = "".join(svg_element(child) for child in root)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">{body}</svg>\n')


def write_set(name: str, svg_text: str) -> None:
    folder = OUT / f"{name}.imageset"
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.svg").write_text(svg_text)
    contents = {
        "images": [{"filename": f"{name}.svg", "idiom": "universal"}],
        "info": {"author": "xcode", "version": 1},
        "properties": {"preserves-vector-representation": True, "template-rendering-intent": "template"},
    }
    (folder / "Contents.json").write_text(json.dumps(contents, indent=2) + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "Contents.json").write_text(json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    for name in ICONS:
        write_set(name, svg(DRAWABLES / f"{name}.xml"))
    print(f"{len(ICONS)} icons in {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

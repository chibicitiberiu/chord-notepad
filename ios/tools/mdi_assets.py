#!/usr/bin/env python3
"""Copy Android's Material Design Icons into the iOS asset catalog.

The main screen's app bar, player and menu draw the same icons as Android
(docs/IOS.md, "The main screen"). Each one is Android's generated vector
drawable (android/res/drawable/mdi_*.xml, from android/tools/mdi_icons.py)
turned into a 24 x 24 SVG image set rendered as a template, so SwiftUI tints
it like Android's MdiIcon:

    python3 -I ios/tools/mdi_assets.py

Writes ios/ChordNotepad/Assets.xcassets/Icons/<name>.imageset. Chord
Notepad's own drawables (ic_*) come along the same way: their strokes and
group transforms are kept. The Settings, About and licence screens' icons
are Kotlin ImageVectors on Android, not drawables (ui/settings/SettingsIcons.kt,
ui/icons/AppIcons.kt): their path strings are read from the Kotlin source
into settings_<name> and app_<name> image sets. Standard library only.
"""

import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

REPO = pathlib.Path(__file__).resolve().parents[2]
DRAWABLES = REPO / "android/app/src/main/res/drawable"
KOTLIN_UI = REPO / "android/app/src/main/kotlin/com/tibich/chordnotepad/ui"

# Kotlin ImageVectors: (source file, image set prefix, icon names; None: every icon in the file).
KOTLIN_ICONS = [
    (KOTLIN_UI / "settings/SettingsIcons.kt", "settings", None),
    (KOTLIN_UI / "icons/AppIcons.kt", "app", ["ArrowBack", "ArrowDropDown", "ChevronRight"]),
]
OUT = REPO / "ios/ChordNotepad/Assets.xcassets/Icons"
ANDROID = "{http://schemas.android.com/apk/res/android}"

ICONS = [
    # The app bar.
    "mdi_menu", "mdi_pencil", "mdi_play_circle", "mdi_content_save",
    # The player.
    "mdi_music", "mdi_guitar_acoustic", "mdi_skip_previous", "mdi_play", "mdi_pause", "mdi_metronome",
    "mdi_speedometer", "mdi_dock_bottom", "mdi_music_clef_treble", "mdi_chevron_down",
    # The menu.
    "mdi_file_plus", "mdi_folder_open", "mdi_file_music", "mdi_content_save_edit", "mdi_export",
    "mdi_waveform", "mdi_file_pdf_box", "mdi_cog", "mdi_music_box_multiple", "mdi_book_open_variant",
    "mdi_school", "mdi_information",
    # The Edit ribbon's tools and the player's and the ribbon's sheets.
    "mdi_plus", "ic_transpose", "ic_capo", "mdi_piano", "ic_time_signature", "mdi_label", "mdi_repeat",
    "mdi_radiobox_marked", "mdi_radiobox_blank", "mdi_circle", "mdi_circle_outline", "mdi_chevron_right",
    "mdi_arrow_left",
]


def svg_element(node: ET.Element) -> str:
    """A path or a group of the drawable as SVG: filled paths, stroked ones
    (Chord Notepad's own icons, such as ic_time_signature) and groups with
    their scale and translation (ic_transpose)."""
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


def kotlin_icons(source: pathlib.Path, names) -> dict:
    """``{name: path data}`` of the single-path ``icon("Name", "path" + ...)``
    calls in a Kotlin file (the path's string literals joined)."""
    text = source.read_text(encoding="utf-8")
    found = {}
    for match in re.finditer(r'icon\(\s*"(\w+)",\s*((?:"[^"]*"\s*\+?\s*)+),?\s*\)', text):
        found[match.group(1)] = "".join(re.findall(r'"([^"]*)"', match.group(2)))
    if names is None:
        return found
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit(f"{source}: no icon {missing}")
    return {n: found[n] for n in names}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


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
    count = len(ICONS)
    for source, prefix, names in KOTLIN_ICONS:
        for name, path in kotlin_icons(source, names).items():
            write_set(f"{prefix}_{snake(name)}",
                      '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
                      f'<path d="{path}"/></svg>\n')
            count += 1
    print(f"{count} icons in {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

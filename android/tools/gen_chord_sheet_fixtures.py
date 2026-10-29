#!/usr/bin/env python3
"""Generate the chord sheet op-buffer fixtures for the Kotlin decoder tests.

Packs ``examples/02_american_complete.txt`` (guitar voicing) with
``chord_sheet.pack.pack_view`` for every view at zoom 1 and a couple of other
zooms, plus a small multi-key song whose staff gutter has several variants,
and writes ``<name>.bin`` with a ``<name>.json`` summary of what
``chord_sheet.pack.unpack`` decodes (header values, counts, opcode histograms,
first/last ops, coordinate sums, gutter runs). The Kotlin tests
(``ChordSheetBufferTest``) decode the ``.bin`` and compare.

Usage (from the repo root): python3 -I android/tools/gen_chord_sheet_fixtures.py
Output: android/app/src/test/resources/chord_sheet/
"""

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "android/app/src/test/resources/chord_sheet"

MULTI_KEY_SONG = """{bpm: 100} {time: 4/4} {key: C}
{label: verse}
C Am F G*2
{key: G}
G D/F# Em C
{bpm: 140}
{key: Eb}
Eb Bb Cm7 Ab
{time: 3/4}
{key: C}
{label: outro}
C G7 C*3
"""

# (fixture name, song, view, zoom, height)
CASES = [
    ("american_keyboard", "american", "keyboard", 1.0, 130.0),
    ("american_staff", "american", "staff", 1.0, 130.0),
    ("american_fret", "american", "fret", 1.0, 130.0),
    ("american_tab", "american", "tab", 1.0, 130.0),
    ("american_staff_z1728", "american", "staff", 1.728, 180.0),
    ("multikey_tab_z0833", "multikey", "tab", 0.833, 110.0),
    ("multikey_staff", "multikey", "staff", 1.0, 130.0),
]


def _render(text):
    from audio.guitar_chord_picker import GuitarChordPicker
    from services.song_parser_service import SongParserService
    from services.song_renderer import SongRenderer

    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
        note_picker=GuitarChordPicker("standard"),
    )


def _op_dict(op):
    from chord_sheet.ops import ImageOp, LineOp, OvalOp, PolygonOp, RectOp, TextOp

    kind = type(op)
    if kind in (RectOp, OvalOp):
        d = {"op": "rect" if kind is RectOp else "oval", "x": op.x, "y": op.y,
             "w": op.w, "h": op.h, "fill": op.fill, "outline": op.outline,
             "width": op.width}
    elif kind is LineOp:
        d = {"op": "line", "fill": op.fill, "width": op.width,
             "points": [list(p) for p in op.points]}
    elif kind is PolygonOp:
        d = {"op": "polygon", "fill": op.fill, "smooth": op.smooth,
             "points": [list(p) for p in op.points]}
    elif kind is TextOp:
        d = {"op": "text", "x": op.x, "y": op.y, "text": op.s, "anchor": op.anchor,
             "bold": op.bold, "size": float(op.size), "fill": op.fill}
    elif kind is ImageOp:
        d = {"op": "image", "x": op.x, "y": op.y, "key": op.key, "anchor": op.anchor}
    else:
        raise TypeError(kind)
    d["tags"] = list(op.tags)
    return d


def _coord_sum(ops):
    """Sum of every coordinate/size field, the same walk the Kotlin test does."""
    total = 0.0
    for op in ops:
        d = _op_dict(op)
        for key in ("x", "y", "w", "h", "width", "size"):
            if key in d:
                total += d[key]
        for p in d.get("points", ()):
            total += p[0] + p[1]
    return total


def _list_summary(ops):
    hist = {}
    for op in ops:
        name = _op_dict(op)["op"]
        hist[name] = hist.get(name, 0) + 1
    return {
        "count": len(ops),
        "histogram": hist,
        "first": _op_dict(ops[0]) if ops else None,
        "last": _op_dict(ops[-1]) if ops else None,
        "coord_sum": _coord_sum(ops),
        "tag_count": sum(len(op.tags) for op in ops),
    }


def main() -> int:
    """Write every fixture pair into OUT."""
    sys.path.insert(0, str(REPO / "src"))
    from chord_sheet.pack import pack_view, unpack

    songs = {
        "american": _render((REPO / "examples/02_american_complete.txt").read_text()),
        "multikey": _render(MULTI_KEY_SONG),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, song_key, view, zoom, height in CASES:
        data = pack_view(songs[song_key], view, zoom, height)
        v = unpack(data)
        summary = {
            "view_id": v.view_id, "zoom": v.zoom, "height": v.height,
            "content_width": v.content_width, "content_height": v.content_height,
            "gutter_width": v.gutter_width, "lane_height": v.lane_height,
            "background": v.background, "highlight": v.highlight,
            "byte_length": len(data),
            "string_count": int.from_bytes(data[40:44], "little"),
            "slot_count": len(v.slots),
            "first_slot": [v.slots[0].chord_index, v.slots[0].x, v.slots[0].width],
            "last_slot": [v.slots[-1].chord_index, v.slots[-1].x, v.slots[-1].width],
            "slot_x_sum": sum(s.x for s in v.slots),
            "content": _list_summary(v.content),
            "lane": _list_summary(v.lane),
            "gutter_variants": [_list_summary(g) for g in v.gutter_variants],
            "gutter_runs": [[None if math.isinf(r.start_x) else r.start_x, r.variant]
                            for r in v.gutter_runs],
        }
        (OUT / f"{name}.bin").write_bytes(data)
        (OUT / f"{name}.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
        print(f"{name}: {len(data)} bytes, {summary['content']['count']} content ops")
    return 0


if __name__ == "__main__":
    sys.exit(main())

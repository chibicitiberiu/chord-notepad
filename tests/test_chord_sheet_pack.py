"""Tests for the chord-sheet op buffer (``chord_sheet.pack``).

The buffer is what Android draws the chord sheet from, so the tests pin three
things: every view round-trips (pack -> unpack gives back the ops, at float32
precision), the byte layout matches ``docs/ANDROID.md`` ("Chord sheet op
buffer"), and the frozen-gutter variants reproduce what ``paint_gutter`` paints
at any scroll position.
"""

import dataclasses
import hashlib
import math
import struct

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from chord_sheet import pack
from chord_sheet.ops import DrawOps, TextOp
from chord_sheet.registry import default_renderers
from chord_sheet.renderer_interface import SheetContext, SlotBox
from chord_sheet.staff_card import StaffCardRenderer
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer

VIEWS = ("keyboard", "staff", "fret", "tab")
HEIGHT = 130.0

SONG_TEXT = """{bpm: 100} {time: 4/4} {key: C}
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


def _render(text: str):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines, initial_key="C", initial_bpm=100, initial_time_sig=(4, 4),
        note_picker=GuitarChordPicker("standard"),
    )


@pytest.fixture(scope="module")
def song():
    return _render(SONG_TEXT)


def _renderer(view_id):
    return next(r for r in default_renderers() if r.id == view_id)


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _quantized(value):
    """``value`` with every float rounded to float32, as the buffer stores it."""
    if isinstance(value, float):
        return _f32(value)
    if isinstance(value, tuple):
        return tuple(_quantized(v) for v in value)
    if isinstance(value, list):
        return [_quantized(v) for v in value]
    if dataclasses.is_dataclass(value):
        return type(value)(**{f.name: _quantized(getattr(value, f.name))
                              for f in dataclasses.fields(value)})
    return value


# -- Round trip -----------------------------------------------------------------

@pytest.mark.parametrize("view_id", VIEWS)
def test_every_view_round_trips(song, view_id):
    view = pack.collect_view(song, _renderer(view_id), 1.0, HEIGHT)
    assert view.content and view.slots
    assert pack.unpack(pack.serialize(view)) == _quantized(view)


@pytest.mark.parametrize("view_id", VIEWS)
@pytest.mark.parametrize("zoom", [0.5, 1.44, 2.5])
def test_round_trips_at_other_zooms_and_heights(song, view_id, zoom):
    view = pack.collect_view(song, _renderer(view_id), zoom, 211.0)
    assert pack.unpack(pack.serialize(view)) == _quantized(view)


def test_pack_view_is_serialize_of_collect_view(song):
    for view_id in VIEWS:
        assert pack.pack_view(song, view_id, 1.0, HEIGHT) == pack.serialize(
            pack.collect_view(song, _renderer(view_id), 1.0, HEIGHT))


def test_pack_view_uses_the_given_renderers(song):
    staff = StaffCardRenderer()
    data = pack.pack_view(song, "staff", 1.0, HEIGHT, renderers=[staff])
    assert pack.unpack(data).view_id == "staff"
    with pytest.raises(ValueError):
        pack.pack_view(song, "keyboard", 1.0, HEIGHT, renderers=[staff])


def test_unknown_view_is_rejected(song):
    with pytest.raises(ValueError):
        pack.pack_view(song, "bogus", 1.0, HEIGHT)


def test_slots_and_sizes_match_the_layout(song):
    renderer = _renderer("tab")
    layout = renderer.layout(SheetContext(song=song, zoom=1.0), HEIGHT)
    view = pack.unpack(pack.pack_view(song, "tab", 1.0, HEIGHT))
    assert view.slots == _quantized(tuple(layout.slots))
    assert len(view.slots) == len(song.chords)
    assert view.content_width == _f32(layout.width)
    assert view.content_height == _f32(layout.height)


def test_marker_lane_is_packed(song):
    view = pack.unpack(pack.pack_view(song, "keyboard", 1.0, HEIGHT))
    labels = " ".join(op.s for op in view.lane if isinstance(op, TextOp))
    assert "verse" in labels and "outro" in labels
    assert view.lane_height == 20.0


def test_empty_song_packs(song):
    empty = dataclasses.replace(song, chords=[], markers=[])
    for view_id in VIEWS:
        view = pack.unpack(pack.pack_view(empty, view_id, 1.0, HEIGHT))
        assert view.slots == ()


# -- Frozen gutter ----------------------------------------------------------------

def test_staff_gutter_has_one_variant_per_key_signature(song):
    view = pack.collect_view(song, _renderer("staff"), 1.0, HEIGHT)
    # C, G, Eb, then C again: three distinct signatures, four runs.
    assert len(view.gutter_variants) == 3
    assert [run.variant for run in view.gutter_runs] == [0, 1, 2, 0]
    assert view.gutter_runs[0].start_x == -math.inf


@pytest.mark.parametrize("zoom", [1.0, 1.728])
def test_gutter_variants_match_paint_gutter_at_any_scroll(song, zoom):
    renderer = _renderer("staff")
    view = pack.collect_view(song, renderer, zoom, HEIGHT)
    ctx = SheetContext(song=song, zoom=zoom)
    probes = [-10.0, 0.0, view.content_width + 50.0]
    for slot in view.slots:
        probes += [slot.x - 0.5, slot.x, slot.x + 0.5, slot.x + slot.width / 2]
    for scroll_x in probes:
        expected = DrawOps()
        renderer.paint_gutter(expected, ctx, HEIGHT, scroll_x)
        variant = view.gutter_variant_at(scroll_x)
        assert view.gutter_variants[variant] == expected.ops, scroll_x


def test_keyboard_gutter_is_static(song):
    view = pack.collect_view(song, _renderer("keyboard"), 1.0, HEIGHT)
    assert view.gutter_width > 0
    assert len(view.gutter_variants) == 1
    assert view.gutter_runs == [pack.GutterRun(-math.inf, 0)]


@pytest.mark.parametrize("view_id", ["fret", "tab"])
def test_views_without_a_gutter_pack_none(song, view_id):
    view = pack.collect_view(song, _renderer(view_id), 1.0, HEIGHT)
    assert view.gutter_width == 0.0
    assert view.gutter_variants == [] and view.gutter_runs == []
    assert view.gutter_variant_at(100.0) is None


# -- Byte layout ------------------------------------------------------------------

def _every_op_kind() -> pack.ViewOps:
    ops = DrawOps()
    ops.rect(1.5, 2.0, 30.0, 40.25, fill="#fbfbf8", outline=None, width=1.0, tags=("a",))
    ops.oval(3.0, 4.0, 5.0, 6.0, fill=None, outline="#22323a", width=1.5)
    ops.line([(0.0, 1.0), (2.0, 3.0), (4.0, 5.0)], fill="#b9c2c7", width=0.75,
             tags=("a", "slot:0"))
    ops.polygon([(0.0, 0.0), (8.0, 0.0), (4.0, 6.0)], fill="#3a5a8a", smooth=True)
    ops.text(10.0, 20.0, "C♯ maj7 · é", anchor="center", size=12,
             fill="#22323a", bold=True, tags=("slot:0",))
    ops.image(7.0, 8.0, "glyph_accidental_sharp:40:3a5a8a", anchor="nw")
    gutter = DrawOps()
    gutter.rect(0.0, 0.0, 40.0, 130.0, fill="#fbfbf8", tags=("gutter",))
    return pack.ViewOps(
        view_id="staff", zoom=1.2, height=130.0, content_width=500.0,
        content_height=130.0, gutter_width=40.0, lane_height=20.0,
        background="#fbfbf8", highlight="#ffe58a",
        slots=(SlotBox(0, 10.0, 50.0), SlotBox(1, 60.0, 8.5)),
        content=ops.ops, lane=[], gutter_variants=[gutter.ops, []],
        gutter_runs=[pack.GutterRun(-math.inf, 0), pack.GutterRun(10.0, 1)],
    )


def test_header_layout_matches_the_spec():
    data = pack.serialize(_every_op_kind())
    magic, version, header_size = struct.unpack_from("<4sHH", data, 0)
    assert (magic, version, header_size) == (b"CNSB", 1, 48)
    view_id, background, highlight, flags = struct.unpack_from("<HHHH", data, 8)
    assert (view_id, background, highlight, flags) == (0, 1, 2, 0)
    assert struct.unpack_from("<6f", data, 16) == tuple(
        _f32(v) for v in (1.2, 130.0, 500.0, 130.0, 40.0, 20.0))
    string_count, slot_count = struct.unpack_from("<II", data, 40)
    assert slot_count == 2
    # The string table starts at header_size, numbered in first-use order.
    (length,) = struct.unpack_from("<H", data, 48)
    assert data[50:50 + length] == b"staff"
    assert string_count == 11


def test_every_op_kind_round_trips():
    view = _every_op_kind()
    assert pack.unpack(pack.serialize(view)) == _quantized(view)


def test_format_golden():
    # Pins the byte layout itself. A change here is a format change: bump
    # FORMAT_VERSION, update docs/ANDROID.md and the Kotlin decoder.
    data = pack.serialize(_every_op_kind())
    assert len(data) == 428
    assert hashlib.sha256(data).hexdigest() == (
        "4d231a7da6edda5a6ca92211daa29f3c87e7d1ec92644fee0b09fe307c8cb1d7")


def test_bad_buffers_are_rejected():
    data = pack.serialize(_every_op_kind())
    with pytest.raises(ValueError):
        pack.unpack(b"XXXX" + data[4:])
    with pytest.raises(ValueError):
        pack.unpack(data[:4] + struct.pack("<H", 99) + data[6:])
    with pytest.raises(ValueError):
        pack.unpack(data + b"\0")


def test_packing_is_deterministic(song):
    for view_id in VIEWS:
        first = pack.pack_view(song, view_id, 1.0, HEIGHT)
        assert pack.pack_view(_render(SONG_TEXT), view_id, 1.0, HEIGHT) == first


# Pins the renderers' output for SONG_TEXT as well as the format. When a
# renderer change is intended, regenerate with:
#   pipenv run python -c "import sys; sys.path.insert(0, 'src'); sys.path.insert(0, 'tests'); \
#     import test_chord_sheet_pack as t, hashlib; s = t._render(t.SONG_TEXT); \
#     [print(v, len(d), hashlib.sha256(d).hexdigest()) for v in t.VIEWS \
#      for d in [t.pack.pack_view(s, v, 1.0, t.HEIGHT)]]"
VIEW_GOLDEN = {
    "keyboard": (5943, "baa0c981900aeb18fdf3bffaec7383b71b8a1eb3f5a701b468f09cf47fa0e57d"),
    "staff": (5107, "d8bf0af9da6622e18bfc8e3d6c824ccc437527b5a31217568aa26243d33cae5a"),
    "fret": (9378, "0d86117ac8fa0197ebd13c1dc35a2e058e93b616aba53d8bc6b07b17c29114c2"),
    "tab": (6547, "1b3d3fce7c458373b3dd45f602e281e476c21f24aeb085c3d1840398144cc9ea"),
}


@pytest.mark.parametrize("view_id", VIEWS)
def test_view_golden(song, view_id):
    data = pack.pack_view(song, view_id, 1.0, HEIGHT)
    assert (len(data), hashlib.sha256(data).hexdigest()) == VIEW_GOLDEN[view_id]

"""Tests for ``FretCardRenderer`` layout and painting."""

from models.chord import ChordInfo
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.fret_card import (
    DEFAULT_ROWS,
    REST_WIDTH,
    FretCardRenderer,
    _compute_geometry,
    _song_geometry_inputs,
)
from ui.chord_sheet.ops import DrawOps, LineOp, OvalOp, RectOp, TextOp
from ui.chord_sheet.renderer_interface import SheetContext

HEIGHT = 120.0


def make_chord(symbol="C", fingering=None, is_rest=False, bar=1):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=1, is_valid=True),
        chord_notes=None,
        midi_notes=None if is_rest else [60, 64, 67],
        line_index=0,
        item_index=0,
        start_beat=0.0,
        duration_beats=1.0,
        start_time=0.0,
        duration_seconds=0.0,
        bpm=120,
        time_sig=(4, 4),
        key=None,
        bar=bar,
        is_rest=is_rest,
        fingering=fingering,
    )


def make_song(*chords):
    return RenderedSong(chords=list(chords))


def slot_ops(ops, chord_index):
    tag = f"slot:{chord_index}"
    return [op for op in ops.ops if tag in op.tags]


def horizontal_lines(ops_list):
    return [op for op in ops_list if isinstance(op, LineOp) and op.points[0][1] == op.points[1][1]]


def vertical_lines(ops_list):
    return [op for op in ops_list if isinstance(op, LineOp) and op.points[0][0] == op.points[1][0]]


def test_layout_has_one_slot_per_chord():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]),
        make_chord("NC", is_rest=True),
        make_chord("G", fingering=None),
    )
    layout = FretCardRenderer().layout(SheetContext(song=song), height=HEIGHT)
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_rest_and_no_fingering_slots_are_slim():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]),
        make_chord("NC", is_rest=True),
        make_chord("G", fingering=None),
    )
    layout = FretCardRenderer().layout(SheetContext(song=song), height=HEIGHT)
    chord_slot, rest_slot, no_finger_slot = layout.slots
    assert chord_slot.width > REST_WIDTH
    assert rest_slot.width == REST_WIDTH
    assert no_finger_slot.width == REST_WIDTH


def test_rest_and_no_fingering_slots_paint_nothing():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]),
        make_chord("NC", is_rest=True),
        make_chord("G", fingering=None),
    )
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    assert slot_ops(ops, 1) == []
    assert slot_ops(ops, 2) == []


def test_open_shape_c_has_nut_muted_open_and_dots():
    # Standard open C: low E muted, A@3, D@2, G open, B@1, high e open.
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    card_ops = slot_ops(ops, 0)

    # Nut bar: a filled rect above the grid (base == 1).
    rects = [o for o in card_ops if isinstance(o, RectOp)]
    assert len(rects) == 1

    texts = [o for o in card_ops if isinstance(o, TextOp)]
    muted = [t for t in texts if t.s == "×"]
    assert len(muted) == 1
    symbol_texts = [t for t in texts if t.s == "C"]
    assert len(symbol_texts) == 1
    # No base-fret label when base == 1.
    assert not [t for t in texts if t.s.endswith("fr")]

    ovals = [o for o in card_ops if isinstance(o, OvalOp)]
    open_circles = [o for o in ovals if o.outline and not o.fill]
    dots = [o for o in ovals if o.fill]
    assert len(open_circles) == 2
    assert len(dots) == 3


def test_open_shape_dots_land_in_expected_rows():
    # index: string, value: fret (-1 muted, 0 open, >0 fretted).
    fingering = [-1, 3, 2, 0, 1, 0]
    song = make_song(make_chord("C", fingering=fingering))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    card_ops = slot_ops(ops, 0)
    slot = layout.slots[0]

    rows, string_count = _song_geometry_inputs(song)
    geo = _compute_geometry(HEIGHT, rows, string_count)
    grid_left = slot.x + geo.grid_left
    grid_top = geo.grid_top
    base = 1  # has an open string, so base is 1 regardless of fretted positions

    expected = {}
    for i, f in enumerate(fingering):
        if f > 0:
            x = grid_left + i * geo.string_gap
            y = grid_top + (f - base + 0.5) * geo.row_h
            expected[i] = (round(x, 2), round(y, 2))

    dots = [o for o in card_ops if isinstance(o, OvalOp) and o.fill]
    observed = {(round(o.x + o.w / 2.0, 2), round(o.y + o.h / 2.0, 2)) for o in dots}
    assert observed == set(expected.values())


def test_fifth_position_shape_has_no_nut_and_a_base_label():
    # A-shape barre at the 5th fret: no open strings, lowest fret is 5.
    song = make_song(make_chord("Dm", fingering=[5, 7, 7, 6, 5, 5]))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    card_ops = slot_ops(ops, 0)

    rects = [o for o in card_ops if isinstance(o, RectOp)]
    assert rects == []  # no nut bar

    texts = [o for o in card_ops if isinstance(o, TextOp)]
    labels = [t for t in texts if t.s == "5fr"]
    assert len(labels) == 1

    fingering = [5, 7, 7, 6, 5, 5]
    slot = layout.slots[0]
    rows, string_count = _song_geometry_inputs(song)
    geo = _compute_geometry(HEIGHT, rows, string_count)
    grid_left = slot.x + geo.grid_left
    base = 5  # no open strings, lowest fretted position is 5
    expected = {
        (
            round(grid_left + i * geo.string_gap, 2),
            round(geo.grid_top + (f - base + 0.5) * geo.row_h, 2),
        )
        for i, f in enumerate(fingering)
    }

    dots = [o for o in card_ops if isinstance(o, OvalOp) and o.fill]
    assert len(dots) == 6  # every string is fretted
    observed = {(round(o.x + o.w / 2.0, 2), round(o.y + o.h / 2.0, 2)) for o in dots}
    assert observed == expected


def test_four_string_fingering_draws_four_string_lines():
    # Ukulele: 4 strings.
    song = make_song(make_chord("C", fingering=[0, 0, 0, 3]))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    card_ops = slot_ops(ops, 0)
    verticals = vertical_lines(card_ops)
    assert len(verticals) == 4


def test_wide_span_extends_rows_for_every_card_in_the_song():
    # One chord needs 6 rows (frets 1..6, base 1); a plain open-C shape must
    # still draw the same (extended) row count for uniformity across the song.
    wide = make_chord("X", fingering=[1, 6, -1, -1, -1, -1])
    open_c = make_chord("C", fingering=[-1, 3, 2, 0, 1, 0])
    song = make_song(wide, open_c)
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    expected_rows = 6  # fret span 1..6 -> 6 rows, more than DEFAULT_ROWS
    assert expected_rows > DEFAULT_ROWS

    wide_ops = slot_ops(ops, 0)
    open_c_ops = slot_ops(ops, 1)
    wide_horiz = horizontal_lines(wide_ops)
    open_c_horiz = horizontal_lines(open_c_ops)
    assert len(wide_horiz) == expected_rows + 1
    assert len(open_c_horiz) == expected_rows + 1

    # Uniform card width across the song regardless of which chord needed rows.
    assert layout.slots[0].width == layout.slots[1].width


def test_empty_song_has_positive_width_and_no_slots():
    layout = FretCardRenderer().layout(SheetContext(song=make_song()), height=HEIGHT)
    assert layout.slots == ()
    assert layout.width > 0

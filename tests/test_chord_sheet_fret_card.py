"""Tests for ``FretCardRenderer`` layout and painting."""

import pytest

from models.chord import ChordInfo
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.fret_card import (
    DEFAULT_ROWS,
    MAX_CONTENT_HEIGHT,
    REST_WIDTH,
    FretCardRenderer,
    _capped_content_height,
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


def test_open_strings_with_high_position_shape_stays_compact():
    # Regression: a voicing mixing open strings with an 8th-position shape
    # (e.g. jazz voicings like G7#9#5) must NOT stretch the grid from the nut
    # to fret ten. It gets a '<base>fr' label at the lowest fretted note and
    # keeps its open circles above the grid; row count stays at the default.
    jazz = make_chord("G7#9#5", fingering=[-1, 8, 7, 8, 0, 0])
    open_c = make_chord("C", fingering=[-1, 3, 2, 0, 1, 0])
    song = make_song(jazz, open_c)
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    jazz_ops = slot_ops(ops, 0)

    # Position label, not a nut bar.
    texts = [op for op in jazz_ops if isinstance(op, TextOp)]
    assert any(t.s == "7fr" for t in texts), [t.s for t in texts]
    assert [op for op in jazz_ops if isinstance(op, RectOp)] == []  # no nut

    # Open-string circles still drawn above the grid (hollow ovals).
    hollow = [op for op in jazz_ops if isinstance(op, OvalOp) and op.fill is None]
    assert len(hollow) == 2

    # Rows stay at the default: span 7..8 is 2 rows, no song-wide extension.
    for slot_index in (0, 1):
        horiz = horizontal_lines(slot_ops(ops, slot_index))
        assert len(horiz) == DEFAULT_ROWS + 1


def test_label_is_fret_cards():
    assert FretCardRenderer.label == "Fret cards"
    assert FretCardRenderer.id == "fret"  # id is stable, only the label changed


def test_supports_zoom():
    assert FretCardRenderer.supports_zoom is True


def test_content_height_uncapped_below_max_is_unchanged():
    # Below the cap, current "scale to height" behavior stays: no padding,
    # geometry derives from the raw height.
    content_height, top_pad = _capped_content_height(HEIGHT, zoom=1.0)
    assert content_height == HEIGHT
    assert top_pad == 0.0


def test_content_height_capped_at_large_panel_heights():
    tall_height = 600.0
    content_height, top_pad = _capped_content_height(tall_height, zoom=1.0)
    assert content_height == MAX_CONTENT_HEIGHT
    assert top_pad == pytest.approx((tall_height - MAX_CONTENT_HEIGHT) / 2.0)


def test_zoom_scales_the_cap():
    tall_height = 1000.0
    doubled, _ = _capped_content_height(tall_height, zoom=2.0)
    halved, _ = _capped_content_height(tall_height, zoom=0.5)
    assert doubled == pytest.approx(MAX_CONTENT_HEIGHT * 2.0)
    assert halved == pytest.approx(MAX_CONTENT_HEIGHT * 0.5)


def test_card_is_vertically_centered_when_capped():
    # A tall panel must center the fixed-size card rather than blow its
    # geometry up: the blank space above the chord symbol should match the
    # blank space below the fret grid.
    tall_height = 600.0
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=tall_height)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    card_ops = slot_ops(ops, 0)

    rows, string_count = _song_geometry_inputs(song)
    content_height, top_pad = _capped_content_height(tall_height, zoom=1.0)
    geo = _compute_geometry(content_height, rows, string_count)

    symbol_text = next(t for t in card_ops if isinstance(t, TextOp) and t.s == "C")
    assert symbol_text.y == pytest.approx(top_pad + geo.symbol_h / 2.0)

    horiz = horizontal_lines(card_ops)
    grid_bottom_y = max(op.points[0][1] for op in horiz)
    bottom_gap = tall_height - grid_bottom_y
    # Approximately centered: the card geometry itself reserves a few px of
    # internal padding below the grid (independent of centering), so allow
    # slack rather than requiring an exact match.
    assert top_pad == pytest.approx(bottom_gap, abs=10.0)
    assert top_pad > 50.0  # plenty of blank space at this height


def test_card_does_not_grow_unbounded_past_the_cap():
    # Regression: a very tall panel must not keep scaling the card up --
    # geometry derived from a capped height at 600px must match geometry
    # derived directly from the cap itself.
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]))
    renderer = FretCardRenderer()
    ctx = SheetContext(song=song)

    rows, string_count = _song_geometry_inputs(song)
    capped_geo = _compute_geometry(MAX_CONTENT_HEIGHT, rows, string_count)

    for tall_height in (400.0, 600.0, 1200.0):
        layout = renderer.layout(ctx, height=tall_height)
        assert layout.slots[0].width == pytest.approx(capped_geo.card_width)

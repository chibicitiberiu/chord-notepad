"""Tests for ``TabStripRenderer`` layout and painting."""

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from models.chord import ChordInfo
from models.rendered_song import RenderedChord, RenderedSong
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from ui.chord_sheet.ops import DrawOps, LineOp, RectOp, TextOp
from ui.chord_sheet.renderer_interface import SheetContext, STRIP_BG
from ui.chord_sheet.tab_strip import (
    BOTTOM_MARGIN,
    LABEL_BOX_H,
    MAX_SLOT_WIDTH,
    MIN_SLOT_WIDTH,
    STRING_GAP,
    SYMBOL_MARGIN,
    TabStripRenderer,
    _string_line_ys,
)

HEIGHT = 120.0


def make_chord(symbol="C", fingering=None, is_rest=False, bar=1, duration_beats=1.0):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=1, is_valid=True),
        chord_notes=None,
        midi_notes=None if is_rest else [60, 64, 67],
        line_index=0,
        item_index=0,
        start_beat=0.0,
        duration_beats=duration_beats,
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


def _render_guitar(text, time_sig=(4, 4)):
    """Render a real song with guitar fingering data, for measure-accurate tests."""
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=time_sig,
        note_picker=GuitarChordPicker(),
        start_line_index=0,
        start_item_index=0,
    )


def slot_ops(ops, chord_index):
    tag = f"slot:{chord_index}"
    return [op for op in ops.ops if tag in op.tags]


def string_lines(ops):
    return [op for op in ops.ops if isinstance(op, LineOp) and "strings" in op.tags]


def bar_lines(ops):
    return [op for op in ops.ops if isinstance(op, LineOp) and "barlines" in op.tags]


def test_layout_has_one_slot_per_chord_in_song_order():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]),
        make_chord("NC", is_rest=True),
        make_chord("G", fingering=[3, 2, 0, 0, -1, -1]),
    )
    layout = TabStripRenderer().layout(SheetContext(song=song), height=HEIGHT)
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_string_lines_span_full_width():
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]))
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    lines = string_lines(ops)
    assert len(lines) == 6  # standard 6-string tuning
    for line in lines:
        xs = [p[0] for p in line.points]
        assert min(xs) == 0.0
        assert max(xs) == layout.width


def test_highest_string_on_top_lowest_fret_number_on_bottom_line():
    # fingering[0] is the lowest string; it must land on the bottom-most line.
    fingering = [-1, 3, 2, 0, 1, 0]
    song = make_song(make_chord("C", fingering=fingering))
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    lines = string_lines(ops)
    line_ys = sorted({line.points[0][1] for line in lines})
    bottom_y = line_ys[-1]

    card_ops = slot_ops(ops, 0)
    # fingering[0] == -1 (muted low E) -> its 'x' glyph should sit on bottom_y.
    muted_texts = [
        t for t in card_ops if isinstance(t, TextOp) and t.s == "x" and t.y == bottom_y
    ]
    assert len(muted_texts) == 1


def test_muted_open_and_fretted_glyphs_rendered():
    fingering = [-1, 3, 2, 0, 1, 0]
    song = make_song(make_chord("C", fingering=fingering))
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    card_ops = slot_ops(ops, 0)
    labels = sorted(t.s for t in card_ops if isinstance(t, TextOp) and t.s != "C")
    assert labels == sorted(["x", "3", "2", "0", "1", "0"])


def test_slot_width_proportional_to_duration_within_clamps():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0], duration_beats=1.0),
        make_chord("G", fingering=[3, 2, 0, 0, -1, -1], duration_beats=2.0),
    )
    layout = TabStripRenderer().layout(SheetContext(song=song), height=HEIGHT)
    one_beat, two_beat = layout.slots
    assert MIN_SLOT_WIDTH <= one_beat.width <= MAX_SLOT_WIDTH
    assert MIN_SLOT_WIDTH <= two_beat.width <= MAX_SLOT_WIDTH
    # Roughly double -- allow slack for clamping.
    assert 1.6 * one_beat.width <= two_beat.width <= 2.4 * one_beat.width


def test_slot_width_scales_with_zoom():
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0], duration_beats=1.0))
    zoomed_song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0], duration_beats=1.0)
    )
    base = TabStripRenderer().layout(SheetContext(song=song), height=HEIGHT)
    zoomed = TabStripRenderer().layout(
        SheetContext(song=zoomed_song, zoom=2.0), height=HEIGHT
    )
    assert zoomed.slots[0].width == pytest.approx(base.slots[0].width * 2.0)


def test_rest_gap_has_no_fret_texts():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]),
        make_chord("NC", is_rest=True),
    )
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    rest_ops = slot_ops(ops, 1)
    texts = [op for op in rest_ops if isinstance(op, TextOp)]
    rects = [op for op in rest_ops if isinstance(op, RectOp)]
    assert texts == []
    assert rects == []


def test_empty_song_has_positive_width_and_no_slots():
    layout = TabStripRenderer().layout(SheetContext(song=make_song()), height=HEIGHT)
    assert layout.slots == ()
    assert layout.width > 0


def test_string_gap_is_fixed_regardless_of_height():
    # The lane must not stretch string spacing to fill a taller panel: the
    # gap between adjacent string lines is the same at a short and a tall
    # height, as long as both are tall enough to hold the fixed spacing.
    short_ys = _string_line_ys(150.0, string_count=6)
    tall_ys = _string_line_ys(400.0, string_count=6)

    short_gaps = [round(b - a, 6) for a, b in zip(short_ys, short_ys[1:])]
    tall_gaps = [round(b - a, 6) for a, b in zip(tall_ys, tall_ys[1:])]

    assert short_gaps == tall_gaps
    assert all(gap > 0 for gap in short_gaps)


def test_string_gap_is_the_new_constant_at_zoom_one():
    ys = _string_line_ys(400.0, string_count=6, zoom=1.0)
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert all(gap == pytest.approx(STRING_GAP) for gap in gaps)


def test_string_gap_doubles_at_zoom_two():
    ys = _string_line_ys(800.0, string_count=6, zoom=2.0)
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert all(gap == pytest.approx(STRING_GAP * 2.0) for gap in gaps)


def test_string_block_is_vertically_centered_at_large_height():
    height = 400.0
    line_ys = _string_line_ys(height, string_count=6)
    top_string_y = line_ys[0]
    bottom_string_y = line_ys[-1]

    top_margin = top_string_y - SYMBOL_MARGIN
    bottom_margin = height - bottom_string_y - BOTTOM_MARGIN

    assert top_margin == pytest.approx(bottom_margin, abs=0.5)
    assert top_margin > 50.0  # plenty of blank space at this height


def test_string_gap_compresses_only_when_height_too_small():
    # Height far too small to hold the fixed gap for 6 strings: the gap must
    # shrink to fit rather than overflow the available height.
    tiny_ys = _string_line_ys(20.0, string_count=6)
    gaps = [b - a for a, b in zip(tiny_ys, tiny_ys[1:])]
    assert all(gap < STRING_GAP for gap in gaps)
    assert tiny_ys[0] >= 0.0
    assert tiny_ys[-1] <= 20.0 + 1e-6


def test_fret_number_background_rects_use_strip_bg():
    fingering = [-1, 3, 2, 0, 1, 0]
    song = make_song(make_chord("C", fingering=fingering))
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    rects = [op for op in slot_ops(ops, 0) if isinstance(op, RectOp)]
    assert rects  # one per string
    assert all(rect.fill == STRIP_BG for rect in rects)


def test_symbols_clear_the_top_string_fret_numbers():
    # Regression: the chord symbol must never overlap the top string's
    # fret-number boxes. The symbol's anchor y sits well above the box's top
    # edge (top_string_y - LABEL_BOX_H / 2), with real clearance to spare.
    song = make_song(make_chord("C", fingering=[-1, 3, 2, 0, 1, 0]))
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=400.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    lines = string_lines(ops)
    top_string_y = min(line.points[0][1] for line in lines)
    box_top = top_string_y - LABEL_BOX_H / 2.0

    symbol_op = next(
        t for t in slot_ops(ops, 0) if isinstance(t, TextOp) and t.s == "C" and t.bold
    )
    assert symbol_op.y <= box_top - 4.0


def test_bar_lines_at_measure_starts_never_at_the_first_chord():
    # Replaces the old bars-at-chord.bar-change assertion: bar lines now come
    # from the shared measure-boundary helper, not each chord's `bar` field.
    # Three full 4/4 bars -> lines at the 2nd and 3rd chords' starts, never
    # the first.
    song = _render_guitar("C*4  G*4  Am*4\n")
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    xs = sorted(line.points[0][0] for line in bar_lines(ops))
    c_slot, g_slot, am_slot = layout.slots
    assert xs == pytest.approx([g_slot.x, am_slot.x])


def test_a8_across_a_measure_boundary_shows_a_mid_chord_bar_line():
    # The regression this replaces: a chord held across a measure boundary
    # (A*8 in 4/4) must show a bar line mid-chord, not only at the next
    # chord's start. Real rendered song, per test_chord_sheet_barlines.py's
    # _render pattern (swapped to a guitar picker for fingering data).
    song = _render_guitar("A*8  C*4\n")
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    xs = sorted(line.points[0][0] for line in bar_lines(ops))
    a_slot, c_slot = layout.slots
    expected_mid_chord_x = a_slot.x + a_slot.width * (4.0 / 8.0)
    assert xs == pytest.approx([expected_mid_chord_x, c_slot.x])


def test_bar_lines_do_not_exceed_the_string_block_vertically():
    song = _render_guitar("A*8  C*4\n")
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=400.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    lines = string_lines(ops)
    line_ys = sorted({line.points[0][1] for line in lines})
    top_string_y, bottom_string_y = line_ys[0], line_ys[-1]

    bar_line = bar_lines(ops)[0]
    bar_ys = [p[1] for p in bar_line.points]
    # A bar line may extend a touch beyond the strings but must stay tightly
    # bound to the string block, not span the full 400px panel height (the
    # old bug drew bar lines from y=0 to the panel's bottom edge).
    assert min(bar_ys) >= top_string_y - 10.0
    assert max(bar_ys) <= bottom_string_y + 10.0
    assert max(bar_ys) - min(bar_ys) < layout.height / 2.0

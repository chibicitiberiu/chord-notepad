"""Tests for ``TabStripRenderer`` layout and painting."""

from models.chord import ChordInfo
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.ops import DrawOps, LineOp, RectOp, TextOp
from ui.chord_sheet.renderer_interface import SheetContext
from ui.chord_sheet.tab_strip import (
    MAX_SLOT_WIDTH,
    MIN_SLOT_WIDTH,
    TabStripRenderer,
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


def slot_ops(ops, chord_index):
    tag = f"slot:{chord_index}"
    return [op for op in ops.ops if tag in op.tags]


def string_lines(ops):
    return [op for op in ops.ops if isinstance(op, LineOp) and "strings" in op.tags]


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


def test_bar_line_drawn_only_when_bar_changes_and_never_at_first_chord():
    song = make_song(
        make_chord("C", fingering=[-1, 3, 2, 0, 1, 0], bar=1),
        make_chord("G", fingering=[3, 2, 0, 0, -1, -1], bar=1),
        make_chord("Am", fingering=[-1, 0, 2, 2, 1, 0], bar=2),
    )
    renderer = TabStripRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=HEIGHT)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    # A bar line is a vertical LineOp at a slot's x tagged with that slot.
    bar_line_slots = []
    for index, slot in enumerate(layout.slots):
        card_ops = slot_ops(ops, index)
        vertical = [
            op
            for op in card_ops
            if isinstance(op, LineOp) and op.points[0][0] == op.points[1][0]
        ]
        if vertical:
            bar_line_slots.append(index)

    assert bar_line_slots == [2]  # only the bar-2 chord, never the first chord


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

"""Tests for the placeholder ``NameCardRenderer`` layout and painting."""

from models.rendered_song import RenderedSong, RenderedChord
from models.chord import ChordInfo
from ui.chord_sheet.ops import DrawOps, TextOp, RectOp
from ui.chord_sheet.name_card import NameCardRenderer, CARD_WIDTH, REST_WIDTH
from ui.chord_sheet.renderer_interface import SheetContext


def make_chord(symbol="C", is_rest=False, start=0, end=1):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=start, end=end, is_valid=True),
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
        bar=1,
        is_rest=is_rest,
    )


def make_song(*chords):
    return RenderedSong(chords=list(chords))


def test_layout_slot_count_matches_chord_count():
    song = make_song(make_chord("C"), make_chord("G"), make_chord("Am"))
    layout = NameCardRenderer().layout(SheetContext(song=song), height=100.0)
    assert len(layout.slots) == 3
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_rest_slot_is_slimmer_than_chord_slot():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True))
    layout = NameCardRenderer().layout(SheetContext(song=song), height=100.0)
    chord_slot, rest_slot = layout.slots
    assert chord_slot.width == CARD_WIDTH
    assert rest_slot.width == REST_WIDTH
    assert rest_slot.width < chord_slot.width


def test_slot_x_positions_are_monotonic():
    song = make_song(make_chord("C"), make_chord("G"), make_chord("F"))
    layout = NameCardRenderer().layout(SheetContext(song=song), height=100.0)
    xs = [s.x for s in layout.slots]
    assert xs == sorted(xs)
    assert all(b > a for a, b in zip(xs, xs[1:]))


def test_content_width_covers_last_slot():
    song = make_song(make_chord("C"), make_chord("G"))
    layout = NameCardRenderer().layout(SheetContext(song=song), height=100.0)
    last = layout.slots[-1]
    assert layout.width >= last.x + last.width


def test_paint_emits_one_text_op_per_sounding_chord():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True), make_chord("G"))
    renderer = NameCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=100.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    texts = [o for o in ops.ops if isinstance(o, TextOp)]
    assert [t.s for t in texts] == ["C", "G"]  # rest gets no text
    # A border rect per slot (3 cards), plus text for the 2 sounding chords.
    rects = [o for o in ops.ops if isinstance(o, RectOp)]
    assert len(rects) == 3


def test_empty_song_has_positive_width_and_no_slots():
    layout = NameCardRenderer().layout(SheetContext(song=make_song()), height=100.0)
    assert layout.slots == ()
    assert layout.width > 0

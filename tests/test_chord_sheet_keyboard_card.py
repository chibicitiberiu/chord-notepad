"""Tests for ``KeyboardCardRenderer`` layout and painting."""

from models.rendered_song import RenderedSong, RenderedChord
from models.chord import ChordInfo
from ui.chord_sheet.ops import DrawOps, TextOp, RectOp
from ui.chord_sheet.keyboard_card import (
    KeyboardCardRenderer,
    REST_WIDTH,
    WHITE_PC,
    _WHITE_HL,
    _BLACK_HL,
)
from ui.chord_sheet.renderer_interface import SheetContext


def make_chord(symbol="C", is_rest=False, midi_notes=None, hand_split=None, start=0, end=1):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=start, end=end, is_valid=True),
        chord_notes=None,
        midi_notes=None if is_rest else (midi_notes if midi_notes is not None else [60, 64, 67]),
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
        hand_split=hand_split,
    )


def make_song(*chords):
    return RenderedSong(chords=list(chords))


def rects_by_tag_substr(ops, substr):
    return [o for o in ops.ops if isinstance(o, RectOp) and any(substr in t for t in o.tags)]


def test_layout_slot_count_matches_chord_count():
    song = make_song(make_chord("C"), make_chord("G"), make_chord("Am"))
    layout = KeyboardCardRenderer().layout(SheetContext(song=song), height=200.0)
    assert len(layout.slots) == 3
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_rest_slot_is_slimmer_than_chord_slot():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True))
    layout = KeyboardCardRenderer().layout(SheetContext(song=song), height=200.0)
    chord_slot, rest_slot = layout.slots
    assert rest_slot.width == REST_WIDTH
    assert rest_slot.width < chord_slot.width


def test_rest_paints_only_a_slim_empty_rect():
    song = make_song(make_chord("NC", is_rest=True))
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    assert len(ops.ops) == 1
    assert isinstance(ops.ops[0], RectOp)


def test_two_hand_song_emits_two_rows_and_highlights_correct_keys():
    # C major, piano model: bass C2 (36) in the left hand, C4/E4/G4 (60,64,67)
    # in the right hand.
    chord = make_chord("C", midi_notes=[36, 60, 64, 67], hand_split=1)
    song = make_song(chord)
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=220.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    lh_rects = rects_by_tag_substr(ops, "hand:lh")
    rh_rects = rects_by_tag_substr(ops, "hand:rh")
    assert lh_rects  # a left-hand row was emitted
    assert rh_rects  # a right-hand row was emitted

    def find(rects, note_tag):
        matches = [r for r in rects if note_tag in r.tags]
        assert len(matches) == 1
        return matches[0]

    assert find(lh_rects, "note:36").fill == _WHITE_HL
    assert find(rh_rects, "note:60").fill == _WHITE_HL
    assert find(rh_rects, "note:64").fill == _WHITE_HL
    assert find(rh_rects, "note:67").fill == _WHITE_HL

    # The right-hand row is drawn above (smaller y) the left-hand row --
    # grand-staff order.
    assert min(r.y for r in rh_rects) < min(r.y for r in lh_rects)


def test_no_hand_split_song_emits_a_single_row():
    chord = make_chord("C", midi_notes=[48, 52, 55], hand_split=None)
    song = make_song(chord)
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    assert not rects_by_tag_substr(ops, "hand:lh")
    assert not rects_by_tag_substr(ops, "hand:rh")
    assert rects_by_tag_substr(ops, "hand:all")


def test_song_wide_window_is_shared_and_octave_aligned():
    # Two guitar-style chords (no hand_split) sitting in very different
    # registers; the song-wide window must cover both and be identical for
    # every card.
    low_chord = make_chord("C", midi_notes=[36, 40, 43], hand_split=None)
    high_chord = make_chord("C", midi_notes=[84, 88, 91], hand_split=None)
    song = make_song(low_chord, high_chord)
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    slot0, slot1 = layout.slots
    rects0 = [o for o in ops.ops if isinstance(o, RectOp) and f"slot:{slot0.chord_index}" in o.tags]
    rects1 = [o for o in ops.ops if isinstance(o, RectOp) and f"slot:{slot1.chord_index}" in o.tags]

    def x_offset(rects, note_tag):
        matches = [r for r in rects if note_tag in r.tags]
        assert len(matches) == 1
        return matches[0].x - (slot0.x if rects is rects0 else slot1.x)

    # Note 36 (the low chord's root) is only *sounded* by the first card, but
    # since the window is song-wide it must still be a drawable key position
    # on the second card too, at the identical x offset -- proving both cards
    # share one window/key size rather than windowing per chord.
    assert x_offset(rects0, "note:36") == x_offset(rects1, "note:36")

    # Card widths must therefore match too (uniform card width).
    assert slot0.width == slot1.width


def test_black_key_chord_highlights_black_key_rects_not_white():
    # F#m triad: F#3 (54, black), A3 (57, white), C#4 (61, black).
    chord = make_chord("F#m", midi_notes=[54, 57, 61], hand_split=None)
    song = make_song(chord)
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)

    black_rects = rects_by_tag_substr(ops, "key:black")
    white_rects = rects_by_tag_substr(ops, "key:white")
    assert black_rects and white_rects

    def find(rects, note_tag):
        matches = [r for r in rects if note_tag in r.tags]
        assert len(matches) == 1
        return matches[0]

    sharp = find(black_rects, "note:54")
    flat = find(black_rects, "note:61")
    natural = find(white_rects, "note:57")
    assert sharp.fill == _BLACK_HL
    assert flat.fill == _BLACK_HL
    assert natural.fill == _WHITE_HL

    # Black keys are narrower than white keys.
    assert sharp.w < natural.w
    for n in range(54, 62):
        assert (n % 12 in WHITE_PC) == any(f"note:{n}" in r.tags for r in white_rects)


def test_uniform_card_width_across_varied_chords():
    narrow = make_chord("C", midi_notes=[60, 64, 67], hand_split=None)
    wide = make_chord("Cadd9", midi_notes=[48, 55, 60, 64, 67, 74], hand_split=None)
    song = make_song(narrow, wide)
    layout = KeyboardCardRenderer().layout(SheetContext(song=song), height=200.0)
    widths = [s.width for s in layout.slots]
    assert len(set(widths)) == 1


def test_empty_song_has_positive_width_and_no_slots():
    layout = KeyboardCardRenderer().layout(SheetContext(song=make_song()), height=200.0)
    assert layout.slots == ()
    assert layout.width > 0


def test_all_rests_degrade_gracefully():
    song = make_song(make_chord("NC", is_rest=True), make_chord("NC", is_rest=True))
    renderer = KeyboardCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    assert len(layout.slots) == 2
    assert all(s.width == REST_WIDTH for s in layout.slots)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)  # must not raise
    assert all(isinstance(o, RectOp) for o in ops.ops)

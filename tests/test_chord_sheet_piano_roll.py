"""Tests for ``PianoRollRenderer`` layout and painting."""

from audio.chord_picker import ChordNotePicker
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from models.rendered_song import RenderedSong, RenderedChord
from models.chord import ChordInfo
from ui.chord_sheet.ops import DrawOps, TextOp, RectOp, LineOp
from ui.chord_sheet.piano_roll import (
    PianoRollRenderer,
    GUTTER_W,
    WHITE_PC,
    _pitch_range,
    _slot_width,
)
from ui.chord_sheet.renderer_interface import (
    HAND_COLORS,
    NOTE_INK,
    SheetContext,
    VOICE_COLORS,
    bar_line_xs,
)


def make_chord(
    symbol="C",
    is_rest=False,
    midi_notes=None,
    hand_split=None,
    voice_notes=None,
    duration_beats=1.0,
    bar=1,
):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=1, is_valid=True),
        chord_notes=None,
        midi_notes=None if is_rest else (midi_notes if midi_notes is not None else [60, 64, 67]),
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
        hand_split=hand_split,
        voice_notes=voice_notes,
    )


def make_song(*chords):
    return RenderedSong(chords=list(chords))


def rects_by_tag_substr(ops, substr):
    return [o for o in ops.ops if isinstance(o, RectOp) and any(substr in t for t in o.tags)]


def render(song, height=220.0):
    renderer = PianoRollRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    return ctx, layout, ops


def render_gutter(song, height=220.0, scroll_x=0.0):
    renderer = PianoRollRenderer()
    ctx = SheetContext(song=song)
    ops = DrawOps()
    renderer.paint_gutter(ops, ctx, height, scroll_x)
    return ctx, ops


def render_real(text, time_sig=(4, 4), height=220.0):
    lines = SongParserService().detect_chords_in_text(text)
    song = SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=time_sig,
        note_picker=ChordNotePicker(),
        start_line_index=0,
        start_item_index=0,
    )
    return render(song, height)


def test_layout_slot_count_matches_chord_count_including_rests():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True), make_chord("Am"))
    _, layout, _ = render(song)
    assert len(layout.slots) == 3
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_rest_draws_no_note_bars():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True))
    _, layout, ops = render(song)
    rest_slot = layout.slots[1]
    rest_tag = f"slot:{rest_slot.chord_index}"
    rest_ops = [o for o in ops.ops if rest_tag in getattr(o, "tags", ())]
    # The rest gets no chord-symbol text and no note-bar rects (it may still
    # participate in a bar line, but that's keyed off the *next* chord, and
    # there is none here).
    assert not any(isinstance(o, TextOp) for o in rest_ops)
    assert not any(isinstance(o, RectOp) for o in rest_ops)


def test_higher_note_gets_smaller_y_than_lower_note():
    chord = make_chord("C", midi_notes=[48, 60, 72])
    song = make_song(chord)
    _, _, ops = render(song)

    def y_of(note):
        matches = [o for o in ops.ops if isinstance(o, RectOp) and f"note:{note}" in o.tags]
        assert len(matches) == 1
        return matches[0].y

    assert y_of(72) < y_of(60) < y_of(48)


def test_double_duration_slot_about_twice_single_duration_slot():
    short = make_chord("C", duration_beats=1.0)
    long = make_chord("G", duration_beats=2.0)
    song = make_song(short, long)
    _, layout, _ = render(song)
    w1, w2 = layout.slots[0].width, layout.slots[1].width
    assert w2 == _slot_width(2.0)
    assert w1 == _slot_width(1.0)
    assert abs(w2 - 2 * w1) < 1e-6


def test_hand_split_colors_lh_and_rh_bars():
    chord = make_chord("C", midi_notes=[36, 60, 64, 67], hand_split=1)
    song = make_song(chord)
    _, _, ops = render(song)

    lh = rects_by_tag_substr(ops, "hand:lh")
    rh = rects_by_tag_substr(ops, "hand:rh")
    assert len(lh) == 1
    assert len(rh) == 3
    assert lh[0].fill == HAND_COLORS["lh"]
    assert all(r.fill == HAND_COLORS["rh"] for r in rh)


def test_ensemble_voice_colors_follow_order_including_unison():
    # Four voices low to high; voices 1 and 2 share a note (a unison).
    chord = make_chord("C", midi_notes=None, voice_notes=[48, 60, 60, 72])
    song = make_song(chord)
    _, _, ops = render(song)

    for i in range(4):
        matches = rects_by_tag_substr(ops, f"voice:{i}")
        assert len(matches) == 1
        assert matches[0].fill == VOICE_COLORS[i % len(VOICE_COLORS)]

    unison_a = rects_by_tag_substr(ops, "voice:1")[0]
    unison_b = rects_by_tag_substr(ops, "voice:2")[0]
    assert unison_a.y == unison_b.y
    assert unison_a.fill != unison_b.fill


def test_no_voice_or_hand_structure_uses_flat_note_ink():
    chord = make_chord("C", midi_notes=[60, 64, 67], hand_split=None, voice_notes=None)
    song = make_song(chord)
    _, _, ops = render(song)
    bars = [o for o in ops.ops if isinstance(o, RectOp) and any(t.startswith("note:") for t in o.tags)]
    assert len(bars) == 3
    assert all(o.fill == NOTE_INK for o in bars)


def test_black_key_rows_shaded_count_matches_black_pitch_classes_in_range():
    song = make_song(make_chord("C", midi_notes=[60, 64, 67]))
    ctx = SheetContext(song=song)
    low, high = _pitch_range(ctx.song)
    expected_black = sum(1 for n in range(low, high + 1) if n % 12 not in WHITE_PC)

    _, _, ops = render(song)
    shaded = [o for o in ops.ops if isinstance(o, RectOp) and "row-shade" in o.tags]
    assert len(shaded) == expected_black
    assert expected_black > 0


def test_gutter_width_is_constant_and_positive():
    renderer = PianoRollRenderer()
    a = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    b = make_song(make_chord("C", midi_notes=[36, 60, 84]))  # wider range
    assert renderer.gutter_width(SheetContext(song=a), 220.0) == GUTTER_W
    assert renderer.gutter_width(SheetContext(song=b), 300.0) == GUTTER_W
    assert GUTTER_W > 0


def test_gutter_has_a_label_per_c_row():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    ctx = SheetContext(song=song)
    low, high = _pitch_range(ctx.song)
    expected_c_rows = sum(1 for n in range(low, high + 1) if n % 12 == 0)

    _, ops = render_gutter(song)
    labels = [o for o in ops.ops if isinstance(o, TextOp) and "label" in o.tags]
    assert len(labels) == expected_c_rows
    assert expected_c_rows > 0
    # Gutter coordinates are gutter-local: labels sit inside the gutter width.
    assert all(0.0 <= o.x < GUTTER_W for o in labels)
    assert any(o.s.startswith("C") for o in labels)


def test_gutter_emits_key_blocks_within_gutter_width():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, ops = render_gutter(song)
    keys = [o for o in ops.ops if isinstance(o, RectOp) and "gutter-key" in o.tags]
    assert keys, "gutter must draw keyboard key blocks"
    # Every key block stays within the gutter width.
    assert all(o.x >= 0.0 and o.x + o.w <= GUTTER_W + 1e-9 for o in keys)


def test_gutter_static_across_scroll():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, a = render_gutter(song, scroll_x=0.0)
    _, b = render_gutter(song, scroll_x=999.0)
    # The keyboard is pitch-indexed, so scrolling must not change it.
    assert [type(o) for o in a.ops] == [type(o) for o in b.ops]
    a_keys = [(o.x, o.y) for o in a.ops if isinstance(o, RectOp)]
    b_keys = [(o.x, o.y) for o in b.ops if isinstance(o, RectOp)]
    assert a_keys == b_keys


def test_content_has_no_keyboard_and_slots_start_at_margin():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, layout, ops = render(song)
    # No key-block / gutter ops leak into the scrolling content.
    assert not [o for o in ops.ops if "gutter-key" in getattr(o, "tags", ())]
    assert not [o for o in ops.ops if isinstance(o, TextOp) and "label" in o.tags]
    # Slots start at the content's left margin, not offset by the gutter.
    assert layout.slots[0].x == 0.0


def _bar_line_xs_drawn(ops):
    return sorted(
        o.points[0][0]
        for o in ops.ops
        if isinstance(o, LineOp) and "bar-line" in o.tags
        and len(set(p[0] for p in o.points)) == 1
    )


def test_bar_lines_at_measure_boundaries_real_song():
    # Four one-bar chords in 4/4: boundaries at the start of chords 2, 3, 4.
    ctx, layout, ops = render_real("C*4  G*4  Am*4  F*4\n")
    xs = _bar_line_xs_drawn(ops)
    expected = bar_line_xs(layout, ctx.song)
    assert xs == sorted(expected)
    # First chord's slot has no bar line at its own left edge (beat 0).
    assert layout.slots[0].x not in xs


def test_long_chord_shows_mid_slot_bar_line_regression():
    # A*8 in 4/4 held across a measure boundary must draw a bar line mid-slot,
    # not only at chord starts (the reported bug: two measures read as one).
    ctx, layout, ops = render_real("A*8  C*4\n")
    xs = _bar_line_xs_drawn(ops)
    a_slot = layout.slots[0]
    c_slot = layout.slots[1]
    # Boundary at beat 4 of the 8-beat A -> halfway into the A slot.
    mid = a_slot.x + a_slot.width * 0.5
    assert any(abs(x - mid) < 1e-6 for x in xs), (xs, mid)
    # And a boundary at beat 8 -> the start of the C slot.
    assert any(abs(x - c_slot.x) < 1e-6 for x in xs), (xs, c_slot.x)


def test_empty_song_degrades_gracefully():
    song = make_song()
    renderer = PianoRollRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height=200.0)
    assert layout.slots == ()
    assert layout.width > 0
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)  # must not raise
    assert ops.ops  # still draws the gutter/rows


def test_id_stays_keyboard_for_config_compatibility():
    assert PianoRollRenderer.id == "keyboard"

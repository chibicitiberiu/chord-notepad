"""Tests for ``PianoRollRenderer`` layout and painting."""

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
from ui.chord_sheet.renderer_interface import HAND_COLORS, NOTE_INK, SheetContext, VOICE_COLORS


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


def test_gutter_has_a_label_per_c_row():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    ctx = SheetContext(song=song)
    low, high = _pitch_range(ctx.song)
    expected_c_rows = sum(1 for n in range(low, high + 1) if n % 12 == 0)

    _, layout, ops = render(song)
    labels = [o for o in ops.ops if isinstance(o, TextOp) and "label" in o.tags]
    assert len(labels) == expected_c_rows
    assert expected_c_rows > 0
    assert all(o.x < GUTTER_W for o in labels)
    assert any(o.s.startswith("C") for o in labels)


def test_bar_line_at_bar_change_none_at_first_chord():
    c1 = make_chord("C", bar=1)
    c2 = make_chord("F", bar=1)
    c3 = make_chord("G", bar=2)
    song = make_song(c1, c2, c3)
    _, layout, ops = render(song)

    def has_bar_line(slot):
        tag = f"slot:{slot.chord_index}"
        return any(
            isinstance(o, LineOp) and tag in o.tags and len(set(p[0] for p in o.points)) == 1
            for o in ops.ops
        )

    assert not has_bar_line(layout.slots[0])
    assert not has_bar_line(layout.slots[1])
    assert has_bar_line(layout.slots[2])


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

"""Tests for ``PianoRollRenderer`` layout and painting."""

import pytest

from chordnotepad.audio.chord_picker import ChordNotePicker
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.song_renderer import SongRenderer
from chordnotepad.models.rendered_song import RenderedSong, RenderedChord
from chordnotepad.models.chord import ChordInfo
from chordnotepad.chord_sheet.ops import DrawOps, TextOp, RectOp, LineOp
from chordnotepad.chord_sheet import piano_roll
from chordnotepad.chord_sheet.piano_roll import NAME_PAD, NAME_PT, PX_PER_BEAT
from chordnotepad.chord_sheet.piano_roll import (
    PianoRollRenderer,
    GUTTER_W,
    GUTTER_W_EUROPEAN,
    LABEL_INSET,
    LABEL_MAX_PT,
    NOTE_FILL,
    NOTE_LABEL,
    SYMBOL_H,
    WHITE_PC,
    BLACK_KEY_W,
    _pitch_range,
    _row_metrics,
    _slot_width,
)
from chordnotepad.chord_sheet.renderer_interface import (
    HAND_COLORS,
    SheetContext,
    VOICE_COLORS,
    bar_line_xs,
    label_ems,
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


def render(song, height=220.0, zoom=1.0, notation="american"):
    renderer = PianoRollRenderer()
    ctx = SheetContext(song=song, zoom=zoom, notation=notation)
    layout = renderer.layout(ctx, height)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    return ctx, layout, ops


def render_gutter(song, height=220.0, scroll_x=0.0, notation="american"):
    renderer = PianoRollRenderer()
    ctx = SheetContext(song=song, notation=notation)
    ops = DrawOps()
    renderer.paint_gutter(ops, ctx, height, scroll_x)
    return ctx, ops


def note_labels(ops):
    return [o for o in ops.ops if isinstance(o, TextOp) and "note-label" in o.tags]


def render_real(text, time_sig=(4, 4), height=220.0, **kwargs):
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
    return render(song, height, **kwargs)


def test_layout_slot_count_matches_chord_count_including_rests():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True), make_chord("Am"))
    _, layout, _ = render(song)
    assert len(layout.slots) == 3
    assert [s.chord_index for s in layout.slots] == [0, 1, 2]


def test_rest_draws_its_label_but_no_note_bars():
    song = make_song(make_chord("C"), make_chord("NC", is_rest=True, duration_beats=4.0))
    _, layout, ops = render(song)
    rest_slot = layout.slots[1]
    rest_tag = f"slot:{rest_slot.chord_index}"
    rest_ops = [o for o in ops.ops if rest_tag in getattr(o, "tags", ())]
    # The rest gets its label and no note-bar rects: the empty lane is the
    # silence.
    assert [o.s for o in rest_ops if isinstance(o, TextOp)] == ["NC"]
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


def test_no_voice_or_hand_structure_uses_the_indigo_note_fill():
    chord = make_chord("C", midi_notes=[60, 64, 67], hand_split=None, voice_notes=None)
    song = make_song(chord)
    _, _, ops = render(song)
    bars = [o for o in ops.ops if isinstance(o, RectOp) and any(t.startswith("note:") for t in o.tags)]
    assert len(bars) == 3
    assert all(o.fill == NOTE_FILL and o.outline is None for o in bars)


def test_every_note_bar_is_rounded_without_an_outline():
    chords = [make_chord("C", midi_notes=[36, 60, 64, 67], hand_split=1),
              make_chord("C", midi_notes=None, voice_notes=[48, 60, 64, 72]),
              make_chord("C", midi_notes=[60, 64, 67])]
    for height in (130.0, 220.0, 600.0):
        _, layout, ops = render(make_song(*chords), height)
        bars = [o for o in ops.ops if isinstance(o, RectOp) and any(t.startswith("note:") for t in o.tags)]
        assert len(bars) == 11
        for bar in bars:
            assert bar.outline is None
            assert bar.radius == min(2.0, bar.h / 3.0) and bar.radius > 0
        # The 2 px inset in the slot stays.
        slot = layout.slots[0]
        assert bars[0].x == slot.x + 2.0 and bars[0].w == slot.width - 4.0


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
    # Wider for the European octave labels, whatever the range.
    for song in (a, b):
        ctx = SheetContext(song=song, notation="european")
        assert renderer.gutter_width(ctx, 220.0) == GUTTER_W_EUROPEAN > GUTTER_W


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


@pytest.mark.parametrize("notation", ["american", "european"])
def test_octave_labels_sit_clear_of_the_black_keys_on_top(notation):
    # L11: at the usual strip heights a label is taller than its row, and the
    # black keys beside the C cut it. It goes after every key, right-aligned
    # in the lane the black keys leave white, and the whole (estimated) text
    # stays right of the black keys: the European gutter is wider for "Do4".
    song = make_song(make_chord("C", midi_notes=[36, 48, 60, 72]))
    ctx, ops = render_gutter(song, notation=notation)
    width = PianoRollRenderer().gutter_width(ctx, 220.0)
    keys = [i for i, o in enumerate(ops.ops) if "gutter-key" in o.tags]
    labels = [(i, o) for i, o in enumerate(ops.ops) if "label" in o.tags]
    assert labels and all(i > max(keys) for i, _ in labels)
    black_right = max(o.x + o.w for o in ops.ops if "gutter-key" in o.tags and o.w < width)
    assert black_right == pytest.approx(BLACK_KEY_W)
    for _, o in labels:
        assert o.anchor == "e" and o.x < width
        text_left = o.x - label_ems(o.s) * o.size * 4.0 / 3.0
        assert text_left > black_right + 1.0, (o.s, text_left, black_right)


def test_octave_labels_follow_the_notation():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, american = render_gutter(song)
    _, european = render_gutter(song, notation="european")
    names = lambda ops: sorted(o.s for o in ops.ops if "label" in o.tags)  # noqa: E731
    assert names(american) == ["C3", "C4", "C5"]
    assert names(european) == ["Do3", "Do4", "Do5"]


def test_gutter_emits_key_blocks_within_gutter_width():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, ops = render_gutter(song)
    keys = [o for o in ops.ops if isinstance(o, RectOp) and "gutter-key" in o.tags]
    assert keys, "gutter must draw keyboard key blocks"
    # Every key block ends within the gutter width. White keys fill it, with
    # their border; black keys are rounded and start a radius left of the
    # gutter, so its clip leaves only their right-hand corners rounded.
    assert all(o.x + o.w <= GUTTER_W + 1e-9 for o in keys)
    white = [o for o in keys if o.w == GUTTER_W]
    black = [o for o in keys if o.w < GUTTER_W]
    assert white and black
    assert all(o.x == 0.0 and o.outline and o.radius == 0 for o in white)
    assert all(o.radius > 0 and o.x == -o.radius and o.outline is None for o in black)


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


# -- Note names in the bars ----------------------------------------------------------


def test_tall_bars_carry_their_note_names():
    # One octave and a bit at 220 px: rows of ~13 px, bars of ~12.
    _, layout, ops = render(make_song(make_chord("C", midi_notes=[60, 64, 67], duration_beats=4.0)))
    labels = note_labels(ops)
    assert sorted(o.s for o in labels) == ["C4", "E4", "G4"]
    bars = {o.tags[-1]: o for o in ops.ops if isinstance(o, RectOp) and "slot:0" in o.tags}
    for label in labels:
        bar = bars[f"note:{label.tags[-1].split(':')[1]}"]
        # Left-aligned 3 px in, centred on the bar, drawn after it, in its own colour.
        assert label.anchor == "w" and label.x == bar.x + LABEL_INSET
        assert label.y == pytest.approx(bar.y + bar.h / 2)
        assert ops.ops.index(label) > ops.ops.index(bar)
        assert label.fill == NOTE_LABEL and not label.bold and "slot:0" in label.tags
        # About three quarters of the bar tall (whole points, rounded up).
        assert label.size * 4 / 3 >= bar.h * 0.75
        assert (label.size - 1) * 4 / 3 < bar.h * 0.75


def test_names_hide_on_short_strips():
    # The default strip (130 px) gives the same song rows of ~6 px.
    song = make_song(make_chord("C", midi_notes=[48, 60, 64, 67, 72], duration_beats=4.0))
    _, _, ops = render(song, height=130.0)
    assert not note_labels(ops)
    _, _, ops = render(song, height=400.0)
    assert len(note_labels(ops)) == 5


def test_names_hide_in_bars_too_narrow_for_them():
    song = make_song(make_chord("C", midi_notes=[60, 64, 67], duration_beats=0.5),
                     make_chord("C", midi_notes=[60, 64, 67], duration_beats=4.0))
    _, layout, ops = render(song, height=400.0)
    assert layout.slots[0].width == 12.0
    labelled = {t for o in note_labels(ops) for t in o.tags if t.startswith("slot:")}
    assert labelled == {"slot:1"}
    # The estimate keeps every shown name inside its bar with 3 px to spare.
    for o in note_labels(ops):
        width = label_ems(o.s) * o.size * 4 / 3
        assert o.x + width <= layout.slots[1].x + layout.slots[1].width - 2 - LABEL_INSET


def test_names_stop_growing_on_very_tall_strips():
    song = make_song(make_chord("C", midi_notes=[60], duration_beats=4.0))
    _, _, ops = render(song, height=900.0)
    (label,) = note_labels(ops)
    assert label.size == LABEL_MAX_PT


def test_ensemble_and_hand_bars_are_named_too():
    chords = [make_chord("C", midi_notes=[48, 60, 64, 67], hand_split=1, duration_beats=4.0),
              make_chord("C", midi_notes=None, voice_notes=[48, 60, 60, 67], duration_beats=4.0)]
    _, _, ops = render(make_song(*chords), height=500.0)
    by_slot = {}
    for o in note_labels(ops):
        by_slot.setdefault(o.tags[0], []).append(o.s)
    assert sorted(by_slot["slot:0"]) == ["C3", "C4", "E4", "G4"]
    assert sorted(by_slot["slot:1"]) == ["C3", "C4", "C4", "G4"]    # the unison twice


def _names(ops, slot):
    return sorted(o.s for o in note_labels(ops) if f"slot:{slot}" in o.tags)


def test_names_are_spelled_from_the_chord_and_the_key():
    # Eb major in Eb: flats, never D#/A#. A B chord in Db stays B D# F#
    # (the staff's rule), and the key's flats name the rest.
    ctx, _, ops = render_real("{key: Eb}\nEb*4  Ab*4\n{key: Db}\nB*4\n", height=600.0)
    eb = {o.s[:-1] for o in note_labels(ops) if "slot:0" in o.tags}
    ab = {o.s[:-1] for o in note_labels(ops) if "slot:1" in o.tags}
    b = {o.s[:-1] for o in note_labels(ops) if "slot:2" in o.tags}
    assert eb and eb <= {"Eb", "G", "Bb"}
    assert ab and ab <= {"Ab", "C", "Eb"}
    assert b and b <= {"B", "D#", "F#"}
    # Each name is the note: letter, accidental and octave give its MIDI number.
    from chordnotepad.chord_sheet.spelling import note_name
    for i, chord in enumerate(ctx.song.chords):
        for note in chord.midi_notes:
            assert note_name(note, chord.chord_notes, chord.key) in _names(ops, i)


def test_names_follow_the_notation():
    text = "{key: Eb}\nEb*4\n"
    _, _, american = render_real(text, height=600.0)
    _, _, european = render_real(text, height=600.0, notation="european")
    names = _names(american, 0)
    assert names and all(n[0] in "EGB" for n in names)
    expected = sorted(n.replace("Eb", "Mib").replace("Bb", "Sib").replace("G", "Sol")
                      for n in names)
    assert _names(european, 0) == expected


# -- Zoom ---------------------------------------------------------------------------------


def test_the_roll_zooms_time_not_pitch():
    assert PianoRollRenderer.supports_zoom is True
    song = make_song(make_chord("C", duration_beats=1.0), make_chord("G", duration_beats=4.0),
                     make_chord("Am", duration_beats=0.25))
    _, base, base_ops = render(song, height=300.0)
    _, wide, wide_ops = render(song, height=300.0, zoom=1.5)
    assert [s.width for s in wide.slots] == [w * 1.5 for w in (24.0, 96.0, 6.0)]
    assert [s.width for s in base.slots] == [_slot_width(d) for d in (1.0, 4.0, 0.25)]
    assert _slot_width(30.0, 2.0) == 1440.0            # no clamp: time is linear
    # The rows (and so the bars' heights and the names' sizes) don't change.
    heights = lambda ops: [o.h for o in ops.ops if isinstance(o, RectOp)]  # noqa: E731
    assert heights(base_ops) == heights(wide_ops)
    assert {o.size for o in note_labels(base_ops)} == {o.size for o in note_labels(wide_ops)}
    # Wider bars only name more notes.
    assert len(note_labels(wide_ops)) > len(note_labels(base_ops))


# -- Grid ---------------------------------------------------------------------------------


def test_the_grid_lines_are_hairlines_and_the_band_is_closed():
    ctx, layout, ops = render_real("C*4  G*4  Am*4  F*4\n")
    lines = [o for o in ops.ops if isinstance(o, LineOp)]
    assert lines and all(o.width == 1.0 for o in lines)
    (rule,) = [o for o in lines if "header-rule" in o.tags]
    assert rule.points == ((0.0, SYMBOL_H), (layout.width, SYMBOL_H))
    bar_lines = [o for o in lines if "bar-line" in o.tags]
    assert {o.fill for o in bar_lines} == {rule.fill}


def test_octave_guides_sit_where_b_meets_c():
    song = make_song(make_chord("C", midi_notes=[48, 60, 72]))
    _, layout, ops = render(song)
    low, high, row_h = _row_metrics(song, layout.height)
    guides = [o for o in ops.ops if isinstance(o, LineOp) and "guide-c" in o.tags]
    c_rows = [n for n in range(low, high + 1) if n % 12 == 0]
    expected = sorted(SYMBOL_H + (high - n + 1) * row_h for n in c_rows)
    assert sorted(o.points[0][1] for o in guides) == pytest.approx(expected)
    # C4's is the darker one; every guide is drawn over the row shading.
    shades = [i for i, o in enumerate(ops.ops) if "row-shade" in o.tags]
    assert all(ops.ops.index(g) > max(shades) for g in guides)
    assert len({o.fill for o in guides}) == 2


# -- The time axis --------------------------------------------------------------------------


def _lines(ops, tag):
    return sorted(o.points[0][0] for o in ops.ops if isinstance(o, LineOp) and tag in o.tags)


def test_a_chord_twice_as_long_is_twice_as_wide_and_spans_two_bars():
    ctx, layout, ops = render_real("C*4 G*8 C*4\n")
    c, g, _ = layout.slots
    assert g.width == 2 * c.width == 2 * 4 * PX_PER_BEAT
    # The bar lines fall every 96 px, one in the middle of the long chord.
    assert _lines(ops, "bar-line") == [96.0, 192.0, 288.0]
    assert g.x < 192.0 == g.x + g.width / 2 < g.x + g.width


def test_every_bar_of_a_time_signature_has_one_width():
    _, layout, ops = render_real("C*1 D*1 E*1 F*2 G*0.5 A*2.5\n{time: 3/4}\nC*3 G*3 Am\n")
    bars = _lines(ops, "bar-line")
    widths = [b - a for a, b in zip([0.0] + bars, bars)]
    assert widths[:2] == [96.0, 96.0]
    assert widths[2:] == [72.0] * (len(widths) - 2)       # 3/4 bars: three quarters of a 4/4 one
    # NC is time too.
    _, rest_layout, _ = render_real("C*1 NC*2 G*1\n")
    assert [s.width for s in rest_layout.slots] == [24.0, 48.0, 24.0]


def test_half_beat_chords_are_half_a_beat_wide_and_their_names_shrink_never_hide():
    # Tibi, 2026-11-15: "we shouldn't hide names, if we have to we render smaller".
    _, layout, ops = render_real("C*0.5 G*0.5 Am*0.5 F*0.5 C*2 Cmaj7#11*2\n", height=400.0)
    assert [s.width for s in layout.slots] == [12.0] * 4 + [48.0, 48.0]
    names = {o.tags[0]: o for o in ops.ops
             if isinstance(o, TextOp) and "note-label" not in o.tags and o.tags[:1]
             and o.tags[0].startswith("slot:")}
    assert [names[f"slot:{i}"].s for i in range(6)] == ["C", "G", "Am", "F", "C", "Cmaj7#11"]
    # A name that fits keeps the full size; others shrink, never below the floor.
    assert names["slot:4"].size == NAME_PT
    assert all(piano_roll.NAME_MIN_PT <= names[f"slot:{i}"].size < NAME_PT for i in (0, 1, 2, 3, 5))
    # Every name is centred on the band's middle (no staircase).
    assert len({o.y for o in names.values()}) == 1
    assert all(o.anchor == "center" for o in names.values())
    # A shrunk name fits its slot whenever some size down to the floor does:
    # the largest that fits.
    long_name = names["slot:5"]
    assert piano_roll.name_fits("Cmaj7#11", 48.0, long_name.size)
    assert not piano_roll.name_fits("Cmaj7#11", 48.0, long_name.size + 1)
    # The short chords keep their bars.
    assert {o.tags[0] for o in ops.ops if isinstance(o, RectOp) and o.tags[:1]
            and o.tags[0].startswith("slot:")} == {f"slot:{i}" for i in range(6)}


def test_name_size_shrinks_to_fit_and_stops_at_the_floor():
    assert piano_roll.name_size("C", 96.0) == NAME_PT
    wide = piano_roll.name_size("Cmaj7#11", 30.0)
    assert piano_roll.NAME_MIN_PT <= wide < NAME_PT
    assert piano_roll.name_size("Cmaj7#11/G#", 4.0) == piano_roll.NAME_MIN_PT


def test_zoom_scales_the_axis_linearly():
    song_text = "C*4 G*2 Am*0.5\n"
    _, base, _ = render_real(song_text)
    for zoom in (0.5, 1.25, 2.5):
        _, zoomed, ops = render_real(song_text, zoom=zoom)
        assert [s.width for s in zoomed.slots] == [s.width * zoom for s in base.slots]
        assert [s.x for s in zoomed.slots] == [s.x * zoom for s in base.slots]


def test_beat_lines_mark_the_beats_between_bar_lines():
    _, layout, ops = render_real("C*4 G*4\n")
    assert _lines(ops, "beat-line") == [24.0, 48.0, 72.0, 120.0, 144.0, 168.0]
    assert {o.fill for o in ops.ops if "beat-line" in o.tags} == {piano_roll.BEAT_GRID}
    assert piano_roll.BEAT_GRID != piano_roll.GRID
    # Under the bar lines in paint order, fainter (lighter on the light paper).
    order = [o.tags[0] for o in ops.ops if isinstance(o, LineOp)
             and o.tags[0] in ("beat-line", "bar-line")]
    assert order.index("bar-line") > max(i for i, t in enumerate(order) if t == "beat-line")


def test_beat_lines_are_left_out_when_beats_get_too_close(monkeypatch):
    monkeypatch.setattr(piano_roll, "MIN_BEAT_SPACING", 13.0)
    _, _, close = render_real("C*4 G*4\n", zoom=0.5)       # 12 px a beat
    assert _lines(close, "beat-line") == []
    assert _lines(close, "bar-line") == [48.0]
    _, _, apart = render_real("C*4 G*4\n", zoom=0.6)
    assert len(_lines(apart, "beat-line")) == 6

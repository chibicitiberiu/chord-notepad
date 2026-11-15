"""Alternating section bands on the chord sheet (renderer_interface).

Every second section of the song (section and loop markers, counted as the
player's timeline counts them) sits on SECTION_BAND paper, drawn first in
every view so the rest draws over it.
"""

import pytest

from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.chord_sheet.ops import DrawOps, RectOp
from chordnotepad.chord_sheet.registry import default_renderers
from chordnotepad.chord_sheet import pack, piano_roll, tab_strip
from chordnotepad.chord_sheet.renderer_interface import (
    SECTION_BAND,
    STRIP_BG,
    SheetContext,
    gutter_paper,
    paper_at,
    section_band_spans,
)
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.song_renderer import SongRenderer

VIEWS = ("keyboard", "staff", "fret", "tab")


def _render(text):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines, initial_key="C", initial_bpm=100, initial_time_sig=(4, 4),
        note_picker=GuitarChordPicker("standard"),
    )


def _layout(text, view="tab", height=130.0):
    song = _render(text)
    renderer = {r.id: r for r in default_renderers()}[view]
    ctx = SheetContext(song=song)
    return song, renderer, ctx, renderer.layout(ctx, height)


def _start(layout, chord_index):
    """Where a section starting at ``chord_index`` begins: the slot before's right edge."""
    prev = layout.slots[chord_index - 1]
    return prev.x + prev.width


def test_every_second_section_is_banded():
    text = "{label: verse}\nC G\n{label: chorus}\nF C\n{label: bridge}\nAm G\n{label: outro}\nC\n"
    song, _, _, layout = _layout(text)
    assert section_band_spans(song, layout) == [
        (_start(layout, 2), _start(layout, 4)),
        (_start(layout, 6), layout.width),
    ]


def test_an_intro_before_the_first_label_is_the_first_section():
    song, _, _, layout = _layout("C G\n{label: verse}\nF C\n")
    assert section_band_spans(song, layout) == [(_start(layout, 2), layout.width)]


def test_no_labels_no_bands():
    song, _, _, layout = _layout("C G F C\n")
    assert section_band_spans(song, layout) == []


def test_two_labels_on_one_chord_start_one_section_and_a_trailing_label_none():
    text = "{label: a}\nC G\n{label: b}\n{label: c}\nF C\n{label: d}\nAm\n{label: end}\n"
    song, _, _, layout = _layout(text)
    # a | b+c (banded) | d; "end" has no chord after it.
    assert section_band_spans(song, layout) == [(_start(layout, 2), _start(layout, 4))]


def test_a_loop_pass_starts_a_section():
    song, _, _, layout = _layout("{label: chorus}\nC G\n{loop: chorus 2}\n{label: outro}\nF\n")
    kinds = [m.kind for m in song.markers if m.kind in ("section", "loop")]
    assert "loop" in kinds
    # chorus, chorus (pass 2, banded), outro.
    assert section_band_spans(song, layout) == [(_start(layout, 2), _start(layout, 4))]


@pytest.mark.parametrize("view", VIEWS)
def test_every_view_paints_the_bands_first(view):
    song, renderer, ctx, layout = _layout("{label: verse}\nC G\n{label: chorus}\nF C\n", view)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    first = ops.ops[0]
    assert isinstance(first, RectOp) and first.tags == ("section-band",)
    assert first.fill == SECTION_BAND
    assert (first.x, first.y, first.w, first.h) == (
        _start(layout, 2), 0.0, layout.width - _start(layout, 2), layout.height)
    assert [op for op in ops.ops if "section-band" in op.tags] == [first]


def test_the_rolls_black_rows_are_a_step_darker_over_a_band():
    song, renderer, ctx, layout = _layout("{label: verse}\nC G\n{label: chorus}\nF C\n", "keyboard")
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    x0 = _start(layout, 2)
    shades = [op for op in ops.ops if "row-shade" in op.tags]
    assert shades
    for op in shades:
        expected = piano_roll.BAND_BLACK_ROW_SHADE if op.x >= x0 else piano_roll.BLACK_ROW_SHADE
        assert op.fill == expected
    assert {op.x for op in shades} == {0.0, x0}
    assert piano_roll.BAND_BLACK_ROW_SHADE not in (piano_roll.BLACK_ROW_SHADE, SECTION_BAND)


def test_the_tabs_number_patches_take_the_paper_under_them():
    song, renderer, ctx, layout = _layout("{label: verse}\nC G\n{label: chorus}\nF C\n", "tab")
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    x0 = _start(layout, 2)
    patches = [op for op in ops.ops if isinstance(op, RectOp) and op.fill in (STRIP_BG, SECTION_BAND)
               and "section-band" not in op.tags]
    assert patches
    for op in patches:
        assert op.fill == (SECTION_BAND if op.x + op.w / 2 >= x0 else STRIP_BG)


def test_paper_at():
    spans = [(10.0, 20.0), (30.0, 40.0)]
    assert paper_at(5.0, spans) == STRIP_BG
    assert paper_at(10.0, spans) == SECTION_BAND
    assert paper_at(20.0, spans) == STRIP_BG
    assert paper_at(39.9, spans) == SECTION_BAND
    assert tab_strip.paper_at is paper_at


def test_gutter_paper():
    spans = [(10.0, 20.0), (30.0, 40.0)]
    assert gutter_paper(-5.0, spans) == STRIP_BG
    assert gutter_paper(10.0, spans) == STRIP_BG
    assert gutter_paper(10.5, spans) == SECTION_BAND
    assert gutter_paper(20.0, spans) == SECTION_BAND
    assert gutter_paper(20.5, spans) == STRIP_BG
    assert gutter_paper(35.0, spans) == SECTION_BAND
    assert gutter_paper(50.0, spans) == STRIP_BG
    assert gutter_paper(15.0, []) == STRIP_BG


FOUR_SECTIONS = "{label: verse}\nC G\n{label: chorus}\nF C\n{label: bridge}\nAm G\n{label: outro}\nC\n"


def _gutter_paper_op(renderer, ctx, height, scroll_x):
    ops = DrawOps()
    renderer.paint_gutter(ops, ctx, height, scroll_x)
    first = ops.ops[0]
    assert isinstance(first, RectOp) and first.tags == ("gutter",)
    assert (first.x, first.y, first.w, first.h) == (
        0.0, 0.0, renderer.gutter_width(ctx, height), height)
    return first.fill


def test_the_staff_gutter_takes_the_band_of_the_section_at_its_edge():
    height = 130.0
    song, renderer, ctx, layout = _layout(FOUR_SECTIONS, "staff", height)
    spans = section_band_spans(song, layout)
    assert len(spans) == 2
    (a0, a1), (b0, _) = spans
    for scroll_x in (-20.0, 0.0, a0 / 2, a0):
        assert _gutter_paper_op(renderer, ctx, height, scroll_x) == STRIP_BG, scroll_x
    for scroll_x in (a0 + 0.5, (a0 + a1) / 2, a1, b0 + 0.5, layout.width - 1.0):
        assert _gutter_paper_op(renderer, ctx, height, scroll_x) == SECTION_BAND, scroll_x
    for scroll_x in (a1 + 0.5, (a1 + b0) / 2, b0):
        assert _gutter_paper_op(renderer, ctx, height, scroll_x) == STRIP_BG, scroll_x


def test_the_staff_gutter_breaks_at_the_band_edges_and_the_key_changes():
    height = 130.0
    song, renderer, ctx, layout = _layout(
        "{label: verse}\nC G\n{label: chorus}\n{key: D}\nD A\n{label: outro}\nC\n", "staff", height)
    (x0, x1), = section_band_spans(song, layout)
    points = renderer.gutter_breakpoints(ctx, height, layout)
    assert points == sorted(set(points))
    assert x0 in points and x1 in points
    # The key change (C to D at chord 2) still breaks at the slot before it.
    assert layout.slots[1].x in points


def test_no_band_before_the_first_banded_section():
    height = 130.0
    song, renderer, ctx, layout = _layout(FOUR_SECTIONS, "staff", height)
    view = pack.collect_view(song, renderer, 1.0, height)
    first_band = section_band_spans(song, layout)[0][0]
    for run in view.gutter_runs:
        if run.start_x < first_band:
            assert view.gutter_variants[run.variant][0].fill == STRIP_BG


def test_the_packed_staff_gutter_has_a_variant_per_paper_and_dedups_them():
    height = 130.0
    song, renderer, ctx, layout = _layout(FOUR_SECTIONS, "staff", height)
    view = pack.collect_view(song, renderer, 1.0, height)
    (a0, a1), (b0, b1) = section_band_spans(song, layout)
    # One key: a plain gutter and a banded one, each painted once.
    assert [ops[0].fill for ops in view.gutter_variants] == [STRIP_BG, SECTION_BAND]
    assert [(run.start_x, run.variant) for run in view.gutter_runs] == [
        (float("-inf"), 0), (a0, 1), (a1, 0), (b0, 1), (b1, 0)]
    for scroll_x in ((a0 + a1) / 2, (b0 + b1) / 2):
        assert view.gutter_variants[view.gutter_variant_at(scroll_x)][0].fill == SECTION_BAND

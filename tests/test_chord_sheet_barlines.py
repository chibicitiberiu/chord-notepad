"""Tests for the shared measure-boundary helpers (renderer_interface).

Regression: a chord held across a measure boundary (``A*8`` in 4/4) drew no
bar line mid-chord, so two measures read as one.
"""

from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from audio.chord_picker import ChordNotePicker
from ui.chord_sheet.renderer_interface import (
    SlotBox,
    StripLayout,
    bar_line_xs,
    measure_boundaries,
)


def _render(text, time_sig=(4, 4)):
    lines = SongParserService().detect_chords_in_text(text)
    return SongRenderer().render(
        lines=lines,
        initial_key="C",
        initial_bpm=120,
        initial_time_sig=time_sig,
        note_picker=ChordNotePicker(),
        start_line_index=0,
        start_item_index=0,
    )


class TestMeasureBoundaries:
    def test_four_bars_of_four_four(self):
        song = _render("C*4  G*4  Am*4  F*4\n")
        assert measure_boundaries(song) == [4.0, 8.0, 12.0]

    def test_long_chord_spans_boundaries(self):
        song = _render("A*8  C*4\n")
        # 12 beats total: boundaries at 4 and 8, none at the end.
        assert measure_boundaries(song) == [4.0, 8.0]

    def test_meter_change_starts_a_fresh_bar(self):
        song = _render("C*4\n{time: 3/4}\nG*3  Am*3\n")
        # 4/4 bar (0-4), then 3/4 bars at 4, 7; end at 10.
        assert measure_boundaries(song) == [4.0, 7.0]

    def test_empty_song(self):
        song = _render("just lyrics, no chords at all\n")
        assert song is not None
        assert measure_boundaries(song) == []


class TestBarLineXs:
    def test_boundary_inside_long_chord_is_interpolated(self):
        song = _render("A*8\n")
        layout = StripLayout(
            width=220.0, height=100.0,
            slots=(SlotBox(chord_index=0, x=20.0, width=160.0),),
        )
        xs = bar_line_xs(layout, song)
        # One boundary at beat 4 of 8 -> halfway through the slot.
        assert xs == [20.0 + 80.0]

    def test_boundary_at_chord_start_lands_on_slot_edge(self):
        song = _render("C*4  G*4\n")
        layout = StripLayout(
            width=300.0, height=100.0,
            slots=(
                SlotBox(chord_index=0, x=10.0, width=100.0),
                SlotBox(chord_index=1, x=110.0, width=100.0),
            ),
        )
        assert bar_line_xs(layout, song) == [110.0]

    def test_a8_produces_two_visible_measures(self):
        # The regression itself: A*8 then C*4 must yield bar lines at beats
        # 4 (mid-A) and 8 (start of C).
        song = _render("A*8  C*4\n")
        layout = StripLayout(
            width=400.0, height=100.0,
            slots=(
                SlotBox(chord_index=0, x=0.0, width=200.0),
                SlotBox(chord_index=1, x=200.0, width=100.0),
            ),
        )
        assert bar_line_xs(layout, song) == [100.0, 200.0]

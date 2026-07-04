"""Headless geometry tests for the chord-sheet marker lane.

The lane is pure: :func:`build_marker_lane` records into a ``DrawOps`` we can
inspect without a display, and :func:`beat_to_x` / :func:`slot_anchors` are the
beat->x interpolation the panel relies on.
"""

import pytest

from models.chord import ChordInfo
from models.rendered_song import RenderedChord, RenderedSong, SongMarker
from ui.chord_sheet.ops import LineOp, RectOp, TextOp
from ui.chord_sheet.renderer_interface import SlotBox
from ui.chord_sheet.marker_lane import (
    LANE_HEIGHT,
    beat_to_x,
    build_marker_lane,
    slot_anchors,
)


def make_chord(start_beat, symbol="C"):
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=1, is_valid=True),
        chord_notes=None,
        midi_notes=[60],
        line_index=0,
        item_index=0,
        start_beat=start_beat,
        duration_beats=4.0,
        start_time=start_beat / 2.0,
        duration_seconds=2.0,
        bpm=120,
        time_sig=(4, 4),
        key=None,
        bar=1,
        is_rest=False,
    )


# --------------------------------------------------------------------------
# beat_to_x
# --------------------------------------------------------------------------

ANCHORS = [(0.0, 12.0), (4.0, 100.0), (8.0, 200.0)]


def test_beat_on_a_knot_lands_on_that_slot_edge():
    assert beat_to_x(4.0, ANCHORS, content_width=300.0) == 100.0


def test_beat_between_knots_is_linear():
    # halfway between beat 0 (x=12) and beat 4 (x=100) -> 56.
    assert beat_to_x(2.0, ANCHORS, 300.0) == pytest.approx(56.0)
    # halfway between beat 4 (x=100) and beat 8 (x=200) -> 150.
    assert beat_to_x(6.0, ANCHORS, 300.0) == pytest.approx(150.0)


def test_beat_clamps_before_first_and_after_last():
    assert beat_to_x(-2.0, ANCHORS, 300.0) == 12.0
    assert beat_to_x(99.0, ANCHORS, 300.0) == 200.0


def test_no_anchors_collapses_to_zero():
    assert beat_to_x(3.0, [], 300.0) == 0.0


def test_slot_anchors_pairs_start_beat_with_slot_x():
    chords = [make_chord(0.0), make_chord(4.0), make_chord(8.0)]
    slots = [
        SlotBox(chord_index=0, x=12.0, width=40.0),
        SlotBox(chord_index=1, x=60.0, width=40.0),
        SlotBox(chord_index=2, x=108.0, width=40.0),
    ]
    assert slot_anchors(chords, slots) == [(0.0, 12.0), (4.0, 60.0), (8.0, 108.0)]


# --------------------------------------------------------------------------
# build_marker_lane
# --------------------------------------------------------------------------


def _slots_for(chords):
    return [SlotBox(chord_index=i, x=12.0 + 50.0 * i, width=40.0) for i in range(len(chords))]


def test_lane_has_separator_and_one_rule_per_marker():
    chords = [make_chord(0.0), make_chord(4.0)]
    slots = _slots_for(chords)
    markers = [
        SongMarker(beat=0.0, time=0.0, kind="section", text="verse"),
        SongMarker(beat=4.0, time=2.0, kind="tempo", text="140 bpm"),
    ]
    ops = build_marker_lane(markers, chords, slots, LANE_HEIGHT, content_width=200.0).ops

    lines = [o for o in ops if isinstance(o, LineOp)]
    # 1 bottom separator + 1 vertical rule per marker.
    assert len(lines) == 1 + 2
    texts = [o for o in ops if isinstance(o, TextOp)]
    assert [t.s for t in texts] == ["verse", "140 bpm"]
    knobs = [o for o in ops if isinstance(o, RectOp)]
    assert len(knobs) == 2


def test_marker_rule_x_matches_beat_to_x():
    chords = [make_chord(0.0), make_chord(4.0)]
    slots = _slots_for(chords)  # x = 12, 62
    markers = [SongMarker(beat=4.0, time=2.0, kind="meter", text="3/4")]
    ops = build_marker_lane(markers, chords, slots, LANE_HEIGHT, 200.0).ops
    rule = [o for o in ops if isinstance(o, LineOp) and o.points[0][1] == 0.0][0]
    assert rule.points[0][0] == pytest.approx(62.0)  # slot 1's left edge


def test_distinct_kinds_get_distinct_colors():
    chords = [make_chord(0.0), make_chord(4.0)]
    slots = _slots_for(chords)
    markers = [
        SongMarker(beat=0.0, time=0.0, kind="section", text="a"),
        SongMarker(beat=4.0, time=2.0, kind="loop", text="a (2/2)"),
    ]
    ops = build_marker_lane(markers, chords, slots, LANE_HEIGHT, 200.0).ops
    knobs = [o for o in ops if isinstance(o, RectOp)]
    assert knobs[0].fill != knobs[1].fill


def test_same_beat_markers_fan_flags_out_without_overlap():
    chords = [make_chord(0.0)]
    slots = _slots_for(chords)
    markers = [
        SongMarker(beat=0.0, time=0.0, kind="tempo", text="90 bpm"),
        SongMarker(beat=0.0, time=0.0, kind="meter", text="3/4"),
    ]
    ops = build_marker_lane(markers, chords, slots, LANE_HEIGHT, 200.0).ops
    knobs = [o for o in ops if isinstance(o, RectOp)]
    # Both rules coincide, but the two flags' knobs sit at different x.
    assert knobs[0].x != knobs[1].x
    assert knobs[1].x > knobs[0].x


def test_empty_markers_still_draws_only_the_separator():
    chords = [make_chord(0.0)]
    ops = build_marker_lane([], chords, _slots_for(chords), LANE_HEIGHT, 200.0).ops
    assert len(ops) == 1
    assert isinstance(ops[0], LineOp)

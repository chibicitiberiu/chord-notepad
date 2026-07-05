"""Timeline marker lane for the chord-sheet strip (pure geometry).

A slim horizontal lane the panel draws ABOVE every renderer's content, so each
view shows the song's timeline markers -- section starts, loop repeats, tempo
changes, meter changes, key changes -- for free without any renderer knowing
about them. Each marker is a thin vertical rule at its x plus a small flag (a
colored knob and a short label); the five kinds get distinct muted colors.

x mapping. A marker's beat is interpolated against the chord slots: a marker at
a chord's ``start_beat`` sits at that slot's left edge, and between chords the x
is linear in beat (:func:`beat_to_x` over the :func:`slot_anchors` knots). This
keeps a marker aligned with the card whose beat it shares -- including loop-back
markers, whose beat equals a replayed chord's ``start_beat``.

Stacking. Markers that share a beat merge into ONE flag: a single vertical rule
at their x, one knob per marker drawn side by side (each in its kind color), and
one combined label joining the texts with " · ". Flags from different beats
never overlap either: each flag starts at its own rule (plus a small inset) or
just past the previous flag's estimated right edge, whichever is further right.
Only the flag shifts -- the rule always stays at the group's true x.

Pure and headless-testable: :func:`build_marker_lane` records into a
:class:`~ui.chord_sheet.ops.DrawOps` and returns it; the panel replays it onto
the lane's canvas.
"""

from typing import List, Sequence, Tuple

from models.rendered_song import RenderedChord, SongMarker
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import SlotBox

#: Height of the lane, px (the panel reserves this above the renderer content).
LANE_HEIGHT = 20.0
#: Left inset for a flag's knob/label from the marker's rule, px.
_FLAG_INSET = 3.0
#: Knob (colored tick) size at the head of each flag, px.
_KNOB_W = 4.0
_KNOB_H = 8.0
#: Font point size for a flag label.
_LABEL_SIZE = 8
#: Rough px advance per label character (no text metrics off-screen), used only
#: to estimate a flag's right edge so the next flag can clear it by _FLAG_PAD.
_CHAR_W = 5.5
_FLAG_PAD = 8.0
#: Horizontal gap between side-by-side knobs within one combined flag, px.
_KNOB_GAP = 1.0

#: Kind -> muted rule/knob color (module-local; echoes the strip palettes).
_KIND_COLOR = {
    "section": "#5f7a5a",  # muted green
    "loop": "#6b5a7a",     # muted purple
    "tempo": "#4f7076",    # muted teal
    "meter": "#7a6b5a",    # muted brown
    "key": "#7a5a6e",      # muted plum
}
_DEFAULT_COLOR = "#6b727a"
#: Flag label ink and the lane's bottom separator hairline.
_LABEL_INK = "#2a333a"
_SEPARATOR = "#c2ccd6"


def slot_anchors(
    chords: Sequence[RenderedChord], slots: Sequence[SlotBox]
) -> List[Tuple[float, float]]:
    """Build ``(start_beat, x)`` interpolation knots from the laid-out slots.

    One knot per slot, in song order (``slots`` is one :class:`SlotBox` per
    chord in order), pairing each chord's ``start_beat`` with its slot's left
    edge ``x``. These are the knots :func:`beat_to_x` interpolates between.
    """
    anchors: List[Tuple[float, float]] = []
    for slot in slots:
        if 0 <= slot.chord_index < len(chords):
            anchors.append((chords[slot.chord_index].start_beat, slot.x))
    return anchors


def beat_to_x(
    beat: float, anchors: Sequence[Tuple[float, float]], content_width: float
) -> float:
    """Map a marker ``beat`` to a content-space x via the slot ``anchors``.

    A beat that matches a knot lands on that slot's left edge; a beat between two
    knots is linear in beat between their x's. Beats before the first knot clamp
    to the first x; beats at or after the last knot clamp to the last x. With no
    knots (empty song) everything collapses to ``0.0``.
    """
    if not anchors:
        return 0.0
    if beat <= anchors[0][0]:
        return anchors[0][1]
    if beat >= anchors[-1][0]:
        return anchors[-1][1]
    for (b0, x0), (b1, x1) in zip(anchors, anchors[1:]):
        if b0 <= beat <= b1:
            span = b1 - b0
            if span <= 0:
                return x0
            frac = (beat - b0) / span
            return x0 + frac * (x1 - x0)
    return anchors[-1][1]  # pragma: no cover - covered by the clamps above


def build_marker_lane(
    markers: Sequence[SongMarker],
    chords: Sequence[RenderedChord],
    slots: Sequence[SlotBox],
    height: float,
    content_width: float,
) -> DrawOps:
    """Record the marker lane's draw ops (rules, flags, bottom separator).

    Consecutive markers whose beats match (within 1e-9) share one rule and one
    combined flag; flags are placed left to right so no two ever overlap (see
    the module docstring's "Stacking" paragraph).

    Args:
        markers: The song's timeline markers, in walk order.
        chords: The rendered chords (for each marker's ``start_beat`` anchor).
        slots: The active layout's slots (for each chord's x).
        height: The lane's height in px.
        content_width: Total strip content width (for the separator span).

    Returns:
        A :class:`DrawOps` the panel replays onto the lane canvas.
    """
    ops = DrawOps()

    # Bottom hairline so the lane reads as separate from the cards below.
    ops.line(
        [(0.0, height - 0.5), (content_width, height - 0.5)],
        fill=_SEPARATOR,
        width=1.0,
        tags=("marker-lane",),
    )

    anchors = slot_anchors(chords, slots)

    # Group consecutive markers that share a beat. Markers arrive in walk order
    # with non-decreasing beat, so same-beat runs are always contiguous.
    groups: List[List[Tuple[int, SongMarker]]] = []
    for i, marker in enumerate(markers):
        if groups and abs(groups[-1][0][1].beat - marker.beat) < 1e-9:
            groups[-1].append((i, marker))
        else:
            groups.append([(i, marker)])

    # Single monotonically advancing cursor: the estimated right edge of the
    # last flag drawn. A flag never overlaps its predecessor, even when their
    # rules sit at nearby (but different) x.
    prev_right = None

    for group in groups:
        x = beat_to_x(group[0][1].beat, anchors, content_width)
        group_tags = tuple(f"marker:{i}" for i, _ in group)

        # One vertical rule at the group's true x (the first marker's color).
        ops.line(
            [(x, 0.0), (x, height)],
            fill=_KIND_COLOR.get(group[0][1].kind, _DEFAULT_COLOR),
            width=1.0,
            tags=("marker-lane",) + group_tags,
        )

        # The flag starts at the rule (plus inset) or clear of the previous
        # flag, whichever is further right; only the flag shifts, never the rule.
        flag_x = x + _FLAG_INSET
        if prev_right is not None:
            flag_x = max(flag_x, prev_right + _FLAG_PAD)

        # One knob per marker in the group, side by side, each in its kind color.
        knob_x = flag_x
        for i, marker in group:
            ops.rect(
                knob_x, 1.0, _KNOB_W, _KNOB_H,
                fill=_KIND_COLOR.get(marker.kind, _DEFAULT_COLOR),
                outline=None, width=1.0,
                tags=("marker-lane", f"marker:{i}"),
            )
            knob_x += _KNOB_W + _KNOB_GAP

        # A single combined label to the right of the last knob.
        label = " · ".join(marker.text for _, marker in group)
        text_x = knob_x - _KNOB_GAP + 2.0
        ops.text(
            text_x, height / 2.0, label,
            anchor="w", size=_LABEL_SIZE, fill=_LABEL_INK,
            tags=("marker-lane",) + group_tags,
        )

        prev_right = text_x + len(label) * _CHAR_W

    return ops

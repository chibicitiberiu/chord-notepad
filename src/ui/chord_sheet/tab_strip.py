"""Guitar-tab renderer: a continuous fret-number lane, not cards.

:class:`TabStripRenderer` draws the whole strip as one continuous tab lane:
N horizontal string lines span the full content width, and each chord writes
its fret numbers onto those lines at its slot. Per the tab convention, the
*highest*-pitched string is drawn on top -- the opposite of
``RenderedChord.fingering``'s storage order, where index 0 is the lowest
string, so string ``i`` is drawn on line ``len(fingering) - 1 - i`` from the
top.

Unlike :class:`~ui.chord_sheet.fret_card.FretCardRenderer`'s uniform cards,
slot width here is proportional to ``duration_beats`` (clamped so a whole note
doesn't dwarf a sixteenth), and rests are empty gaps in the lane rather than
their own slim card -- the string lines simply continue underneath them, and
no glyphs are drawn.

Bar lines are measure-accurate, not chord-accurate: they are placed via the
shared :func:`~ui.chord_sheet.renderer_interface.bar_line_xs` helper, which
walks the song's meter map rather than each chord's ``bar`` field, so a chord
held across a measure boundary (e.g. ``A*8`` in 4/4) still shows a bar line
mid-chord instead of only at the next chord's start.

Future extension note: there is no per-string tuning/note-name data on
``SheetContext``/``RenderedSong`` yet (only ``fingering``, which is fret
numbers relative to an unlabeled tuning), so this renderer does not draw
string-name labels. Add a tuning-note-names field to ``SheetContext`` when
that's needed.
"""

from typing import List, Tuple

from models.rendered_song import RenderedSong
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    bar_line_xs,
    chord_symbol_label,
    SheetContext,
    SlotBox,
    STRIP_BG,
    StripLayout,
    StripRenderer,
)

#: Leading/trailing padding at the strip's left and right edges, px. Not
#: zoom-scaled: it's page margin, not part of the lane's internal proportions.
STRIP_MARGIN = 12.0
#: Pixels per beat before clamping, i.e. the "natural" width of a 1-beat slot,
#: at zoom 1.0.
PX_PER_BEAT = 24.0
#: Narrowest a slot may be regardless of duration, at zoom 1.0 (keeps
#: grace-note-length chords and rests tappable/visible).
MIN_SLOT_WIDTH = 20.0
#: Widest a slot may be regardless of duration, at zoom 1.0 (keeps whole notes
#: from dwarfing the rest of the lane).
MAX_SLOT_WIDTH = 120.0
#: Fallback string count when no chord in the song carries fingering data.
DEFAULT_STRING_COUNT = 6

#: Fixed vertical gap between adjacent string lines, px, at zoom 1.0. Never
#: stretched to fill a tall panel -- see :func:`_string_line_ys`.
#:
#: Was 14px, which left only ~1px of clearance between a fret-number glyph
#: box (:data:`LABEL_BOX_H` = 13px) on one string and the next -- the boxes
#: nearly touched, reading as a single smear of digits. 17px leaves ~4px
#: (2px above, 2px below) between adjacent boxes, enough to read as separate
#: rows without shrinking the font: :data:`_LABEL_SIZE` stays 10 rather than
#: dropping to 9, since a 9pt box would only be ~1.3px shorter and cost
#: legibility for a marginal gain once the gap itself grew ~21%.
STRING_GAP = 17.0
#: Vertical space above the top string line reserved for the chord-symbol
#: band, px, at zoom 1.0. Part of the fixed-size "tab block" that gets
#: centered. Was 18px, with the symbol centered in the band (9px above the
#: top string) -- at symbol size 12 that put the glyph's bottom edge *below*
#: the top string's fret-number box (which starts 6.5px above the string
#: line), i.e. overlapping it by a few px, matching the reported crowding.
#: Now 28px, paired with :data:`_SYMBOL_TOP_PAD` below, to guarantee real
#: clearance instead.
SYMBOL_MARGIN = 28.0
#: How far the chord symbol sits below the *top* of the symbol band, px, at
#: zoom 1.0 (rather than centered in the band): ``symbol_y = top_string_y -
#: (SYMBOL_MARGIN - _SYMBOL_TOP_PAD)`` = 18px above the top string. A size-12
#: bold label with no descenders (chord symbols use upper-case letters,
#: digits, #, b, /, m -- nothing that dips below the baseline) has a glyph
#: half-height of roughly 0.6 * size =~ 7px, so its bottom edge lands
#: ~18 - 7 = 11px above the string, versus the fret-number box's top edge at
#: 6.5px above the string: ~4.5px of clearance, comfortably non-overlapping.
_SYMBOL_TOP_PAD = 10.0
#: Vertical space below the lowest string line reserved for the lower half of
#: fret-number glyph boxes, px, at zoom 1.0. Part of the fixed-size "tab
#: block".
BOTTOM_MARGIN = 10.0
#: Bar lines extend this many px above the top string / below the bottom
#: string, so they read as a touch taller than the string block itself, at
#: zoom 1.0.
BAR_LINE_PAD = 3.0
#: Size of the background rect drawn behind each fret-number/x/0 glyph, px,
#: at zoom 1.0.
LABEL_BOX_W = 16.0
LABEL_BOX_H = 13.0

#: Palette (module-local; echoes the user's blog diagrams).
_INK = "#22323a"  # chord symbols, fret-number text
_GRID = "#b9c2c7"  # string lines, bar lines

#: Font sizes at zoom 1.0.
_SYMBOL_SIZE = 12
_LABEL_SIZE = 10
#: Floors applied after scaling by zoom, so a small zoom-out never shrinks
#: text past legibility.
_MIN_SYMBOL_SIZE = 8
_MIN_LABEL_SIZE = 7


def _slot_width(duration_beats: float, zoom: float) -> float:
    """Slot width proportional to duration, clamped to ``[MIN, MAX] * zoom``."""
    min_w = MIN_SLOT_WIDTH * zoom
    max_w = MAX_SLOT_WIDTH * zoom
    return max(min_w, min(max_w, duration_beats * PX_PER_BEAT * zoom))


def _song_string_count(song: RenderedSong) -> int:
    """First fingering's length in the song, or the 6-string default."""
    for chord in song.chords:
        if chord.fingering:
            return len(chord.fingering)
    return DEFAULT_STRING_COUNT


def _string_line_ys(
    height: float, string_count: int, zoom: float = 1.0
) -> Tuple[float, ...]:
    """Y positions of the string lines, top (highest string) to bottom (lowest).

    Strings use a FIXED gap (:data:`STRING_GAP`, scaled by ``zoom``) regardless
    of ``height`` -- the lane never stretches string spacing to fill a taller
    panel. The whole tab block (the chord-symbol band above the top string,
    plus the strings themselves) is vertically centered in ``height``, so any
    extra height becomes blank space above and below. Only when ``height`` is
    too small to fit the fixed spacing does the gap compress just enough to
    fit.
    """
    gap0 = STRING_GAP * zoom
    symbol_margin = SYMBOL_MARGIN * zoom
    bottom_margin = BOTTOM_MARGIN * zoom

    spread = (string_count - 1) * gap0 if string_count > 1 else 0.0
    block_height = symbol_margin + spread + bottom_margin
    gap = gap0

    if block_height > height and block_height > 0.0:
        # Too small even for the fixed spacing: shrink the gap AND the
        # symbol/bottom margins by the same factor, so the whole block (not
        # just the string spread) fits within `height` -- otherwise a very
        # short panel could still push the top string past the given height.
        scale = height / block_height
        gap = gap0 * scale
        symbol_margin *= scale
        bottom_margin *= scale
        block_height = height

    block_top = max(0.0, (height - block_height) / 2.0)
    top_string_y = block_top + symbol_margin
    if string_count <= 1:
        return (top_string_y,)
    return tuple(top_string_y + i * gap for i in range(string_count))


class TabStripRenderer(StripRenderer):
    """Draw a continuous guitar-tab lane with per-chord fret numbers."""

    id = "tab"
    label = "Tab"
    requires_fingering = True
    supports_zoom = True

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay slots out left to right, width proportional to duration.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord (rests included as
            empty gaps), in song order, contiguous (no inter-slot gap: the tab
            lane is continuous).
        """
        slots: List[SlotBox] = []
        x = STRIP_MARGIN
        for index, chord in enumerate(ctx.song.chords):
            width = _slot_width(chord.duration_beats, ctx.zoom)
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width

        content_width = (x + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw the string lines, bar lines, and per-chord fret numbers.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        chords = ctx.song.chords
        zoom = ctx.zoom
        string_count = _song_string_count(ctx.song)
        line_ys = _string_line_ys(layout.height, string_count, zoom)

        for y in line_ys:
            ops.line(
                [(0.0, y), (layout.width, y)], fill=_GRID, width=1.0, tags=("strings",)
            )

        top_y = line_ys[0]
        bottom_y = line_ys[-1]
        symbol_y = top_y - (SYMBOL_MARGIN - _SYMBOL_TOP_PAD) * zoom
        bar_line_pad = BAR_LINE_PAD * zoom
        bar_top = top_y - bar_line_pad
        bar_bottom = bottom_y + bar_line_pad

        # Measure-accurate bar lines: derived from the song's meter map, not
        # each chord's `bar` field, so a chord held across a measure boundary
        # still shows a bar line mid-chord.
        for x in bar_line_xs(layout, ctx.song):
            ops.line(
                [(x, bar_top), (x, bar_bottom)], fill=_GRID, width=1.5, tags=("barlines",)
            )

        symbol_size = max(_MIN_SYMBOL_SIZE, int(round(_SYMBOL_SIZE * zoom)))
        label_size = max(_MIN_LABEL_SIZE, int(round(_LABEL_SIZE * zoom)))
        label_box_w = LABEL_BOX_W * zoom
        label_box_h = LABEL_BOX_H * zoom

        for slot in layout.slots:
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"

            if chord.is_rest or not chord.fingering:
                continue  # empty gap: string lines already span underneath

            cx = slot.x + slot.width / 2.0
            ops.text(
                cx,
                symbol_y,
                chord_symbol_label(chord),
                anchor="center",
                size=symbol_size,
                fill=_INK,
                bold=True,
                tags=(tag,),
            )

            n = len(chord.fingering)
            for string_idx, f in enumerate(chord.fingering):
                line_i = n - 1 - string_idx  # highest string on top
                y = line_ys[line_i] if line_i < len(line_ys) else line_ys[-1]
                label = "x" if f == -1 else str(f)
                ops.rect(
                    cx - label_box_w / 2.0,
                    y - label_box_h / 2.0,
                    label_box_w,
                    label_box_h,
                    fill=STRIP_BG,
                    tags=(tag,),
                )
                ops.text(
                    cx,
                    y,
                    label,
                    anchor="center",
                    size=label_size,
                    fill=_INK,
                    tags=(tag,),
                )

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

A vertical bar line is drawn at the start of every chord whose ``bar`` differs
from the previous chord's (the first chord never gets one, since there is no
previous bar to differ from).

Future extension note: there is no per-string tuning/note-name data on
``SheetContext``/``RenderedSong`` yet (only ``fingering``, which is fret
numbers relative to an unlabeled tuning), so this renderer does not draw
string-name labels. Add a tuning-note-names field to ``SheetContext`` when
that's needed.
"""

from typing import List, Optional, Tuple

from models.rendered_song import RenderedSong
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    chord_symbol_label,
    SlotBox,
    STRIP_BG,
    StripLayout,
    StripRenderer,
)

#: Leading/trailing padding at the strip's left and right edges, px.
STRIP_MARGIN = 12.0
#: Pixels per beat before clamping, i.e. the "natural" width of a 1-beat slot.
PX_PER_BEAT = 24.0
#: Narrowest a slot may be regardless of duration (keeps grace-note-length
#: chords and rests tappable/visible).
MIN_SLOT_WIDTH = 20.0
#: Widest a slot may be regardless of duration (keeps whole notes from
#: dwarfing the rest of the lane).
MAX_SLOT_WIDTH = 120.0
#: Fallback string count when no chord in the song carries fingering data.
DEFAULT_STRING_COUNT = 6

#: Fixed vertical gap between adjacent string lines, px. Never stretched to
#: fill a tall panel -- see :func:`_string_line_ys`.
STRING_GAP = 14.0
#: Vertical space above the top string line reserved for the chord-symbol
#: band, px. Part of the fixed-size "tab block" that gets centered.
SYMBOL_MARGIN = 18.0
#: Vertical space below the lowest string line reserved for the lower half of
#: fret-number glyph boxes, px. Part of the fixed-size "tab block".
BOTTOM_MARGIN = 10.0
#: Bar lines extend this many px above the top string / below the bottom
#: string, so they read as a touch taller than the string block itself.
BAR_LINE_PAD = 3.0
#: Size of the background rect drawn behind each fret-number/x/0 glyph, px.
LABEL_BOX_W = 16.0
LABEL_BOX_H = 13.0

#: Palette (module-local; echoes the user's blog diagrams).
_INK = "#22323a"  # chord symbols, fret-number text
_GRID = "#b9c2c7"  # string lines, bar lines

_SYMBOL_SIZE = 12
_LABEL_SIZE = 10


def _slot_width(duration_beats: float) -> float:
    """Slot width proportional to duration, clamped to [MIN, MAX]."""
    return max(MIN_SLOT_WIDTH, min(MAX_SLOT_WIDTH, duration_beats * PX_PER_BEAT))


def _song_string_count(song: RenderedSong) -> int:
    """First fingering's length in the song, or the 6-string default."""
    for chord in song.chords:
        if chord.fingering:
            return len(chord.fingering)
    return DEFAULT_STRING_COUNT


def _string_line_ys(height: float, string_count: int) -> Tuple[float, ...]:
    """Y positions of the string lines, top (highest string) to bottom (lowest).

    Strings use a FIXED gap (:data:`STRING_GAP`) regardless of ``height`` --
    the lane never stretches string spacing to fill a tall panel. The whole
    tab block (the chord-symbol band above the top string, plus the strings
    themselves) is vertically centered in ``height``, so any extra height
    becomes blank space above and below. Only when ``height`` is too small to
    fit the fixed spacing does the gap compress just enough to fit.
    """
    spread = (string_count - 1) * STRING_GAP if string_count > 1 else 0.0
    block_height = SYMBOL_MARGIN + spread + BOTTOM_MARGIN
    gap = STRING_GAP

    if block_height > height:
        available = max(0.0, height - SYMBOL_MARGIN - BOTTOM_MARGIN)
        gap = available / (string_count - 1) if string_count > 1 else 0.0
        block_height = height

    block_top = max(0.0, (height - block_height) / 2.0)
    top_string_y = block_top + SYMBOL_MARGIN
    if string_count <= 1:
        return (top_string_y,)
    return tuple(top_string_y + i * gap for i in range(string_count))


class TabStripRenderer(StripRenderer):
    """Draw a continuous guitar-tab lane with per-chord fret numbers."""

    id = "tab"
    label = "Tab"
    requires_fingering = True

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
            width = _slot_width(chord.duration_beats)
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
        string_count = _song_string_count(ctx.song)
        line_ys = _string_line_ys(layout.height, string_count)

        for y in line_ys:
            ops.line(
                [(0.0, y), (layout.width, y)], fill=_GRID, width=1.0, tags=("strings",)
            )

        top_y = line_ys[0]
        bottom_y = line_ys[-1]
        symbol_y = top_y - SYMBOL_MARGIN / 2.0
        bar_top = top_y - BAR_LINE_PAD
        bar_bottom = bottom_y + BAR_LINE_PAD
        prev_bar: Optional[int] = None
        for index, slot in enumerate(layout.slots):
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"

            if index > 0 and chord.bar != prev_bar:
                ops.line(
                    [(slot.x, bar_top), (slot.x, bar_bottom)],
                    fill=_GRID,
                    width=1.5,
                    tags=(tag,),
                )
            prev_bar = chord.bar

            if chord.is_rest or not chord.fingering:
                continue  # empty gap: string lines already span underneath

            cx = slot.x + slot.width / 2.0
            ops.text(
                cx,
                symbol_y,
                chord_symbol_label(chord),
                anchor="center",
                size=_SYMBOL_SIZE,
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
                    cx - LABEL_BOX_W / 2.0,
                    y - LABEL_BOX_H / 2.0,
                    LABEL_BOX_W,
                    LABEL_BOX_H,
                    fill=STRIP_BG,
                    tags=(tag,),
                )
                ops.text(
                    cx,
                    y,
                    label,
                    anchor="center",
                    size=_LABEL_SIZE,
                    fill=_INK,
                    tags=(tag,),
                )

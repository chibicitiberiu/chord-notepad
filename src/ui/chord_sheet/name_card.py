"""Placeholder chord-sheet renderer: uniform chord-symbol cards.

:class:`NameCardRenderer` draws each sounding chord as a fixed-width bordered
card with its symbol centered, and each rest as a slim empty card. It carries no
fingering/keyboard/staff detail -- its job is to exercise the whole pipeline
(layout -> ops -> panel replay, plus hit-testing and the playhead) before the
four real renderers land. It follows the same contract they will
(:class:`~ui.chord_sheet.renderer_interface.StripRenderer`), so the panel and
viewmodel need no changes when those arrive.
"""

from typing import List

from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
)

#: Horizontal gap between adjacent cards, px.
CARD_GAP = 8.0
#: Leading/trailing padding at the strip's left and right edges, px.
STRIP_MARGIN = 12.0
#: Width of a sounding-chord card, px.
CARD_WIDTH = 76.0
#: Width of a rest's slim card, px (deliberately narrower than a chord card).
REST_WIDTH = 30.0
#: Vertical inset of a card within the content height, px.
CARD_VMARGIN = 12.0

#: Colors (kept literal here; theming is a later concern for the real panel).
_CARD_OUTLINE = "#8899aa"
_CARD_FILL = "#f4f6fa"
_REST_FILL = "#e9ebef"
_TEXT_FILL = "#1a2530"


class NameCardRenderer(StripRenderer):
    """Draw chord symbols as uniform bordered cards (rests slim and empty)."""

    id = "name"
    label = "Chord Names"
    requires_fingering = False

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay cards out left to right with uniform widths (rests narrower).

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slim slot per rest and one
            full-width slot per sounding chord, in song order.
        """
        slots: List[SlotBox] = []
        x = STRIP_MARGIN
        for index, chord in enumerate(ctx.song.chords):
            width = REST_WIDTH if chord.is_rest else CARD_WIDTH
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width + CARD_GAP

        # Trailing edge: drop the last gap, add the right margin. Empty songs
        # still get a small non-zero width so the canvas has a valid region.
        content_width = (x - CARD_GAP + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw a bordered card per slot, chord symbol centered on sounding cards.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        chords = ctx.song.chords
        top = CARD_VMARGIN
        card_h = max(1.0, layout.height - 2 * CARD_VMARGIN)

        for slot in layout.slots:
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"
            is_rest = chord.is_rest
            ops.rect(
                slot.x,
                top,
                slot.width,
                card_h,
                fill=_REST_FILL if is_rest else _CARD_FILL,
                outline=_CARD_OUTLINE,
                width=1.0,
                tags=(tag,),
            )
            if not is_rest:
                ops.text(
                    slot.x + slot.width / 2.0,
                    top + card_h / 2.0,
                    chord.chord_info.chord,
                    anchor="center",
                    size=12,
                    fill=_TEXT_FILL,
                    bold=True,
                    tags=(tag,),
                )

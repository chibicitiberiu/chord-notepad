"""Chord-sheet strip renderer: mini piano keyboard cards.

:class:`KeyboardCardRenderer` draws each sounding chord as a card with the
chord symbol on top and one or two miniature piano keyboards below, with the
voiced notes' keys highlighted. Geometry is ported from the user's own SVG
generator (``chord_diagrams.py``, function ``piano_svg``): white keys are laid
left to right for every white pitch class in a ``[low, high]`` window; each
black key is a rect centered on the boundary after its lower white neighbor,
drawn after (on top of) the whites.

Two layouts:

- **Piano model** (``RenderedChord.hand_split`` is not ``None`` for at least
  one sounding chord): two stacked rows per card, right hand on top, left
  hand below (grand-staff order). Each row's key window is computed **song-
  wide** for that hand -- every card shares the same window, so chord
  movement is visible across the strip.
- **Other models** (guitar/ensemble, ``hand_split`` always ``None``): one row
  per card, windowed song-wide over every voiced note.

Both windows are expanded outward to full octaves (start on a C, end on a
B) so the keyboard always reads as a recognizable span of the keyboard.

Rests get a slim, empty card (mirrors :class:`~ui.chord_sheet.name_card.NameCardRenderer`).
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from models.rendered_song import RenderedChord
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
)

#: Pitch classes that fall on a white key.
WHITE_PC = {0, 2, 4, 5, 7, 9, 11}

#: Horizontal gap between adjacent cards, px.
CARD_GAP = 8.0
#: Leading/trailing padding at the strip's left and right edges, px.
STRIP_MARGIN = 12.0
#: Width of a rest's slim card, px.
REST_WIDTH = 24.0
#: Vertical inset of a card within the content height, px.
CARD_VMARGIN = 10.0
#: Height reserved for the chord-symbol text atop each card, px.
TEXT_H = 16.0
#: Gap between the chord-symbol text and the first keyboard row, px.
ROWS_TOP_GAP = 4.0
#: Gap between the two keyboard rows (right hand / left hand), px.
ROW_GAP = 6.0
#: Floor on a row's height so keys stay drawable even in a squashed strip.
MIN_ROW_H = 20.0

#: White-key height-to-width aspect ratio (fixed; derives ``ww`` from row height).
WHITE_ASPECT = 4.2
#: Black-key width as a fraction of the white-key width.
BLACK_WIDTH_RATIO = 0.62
#: Black-key height as a fraction of the white-key height.
BLACK_HEIGHT_RATIO = 0.64

#: Fallback window (no notes at all voiced for a hand across the whole song).
_DEFAULT_LH_LOW, _DEFAULT_LH_HIGH = 48, 59  # C3 - B3
_DEFAULT_RH_LOW, _DEFAULT_RH_HIGH = 60, 71  # C4 - B4

#: Colors (kept literal here; theming is a later concern for the real panel).
_CARD_OUTLINE = "#8899aa"
_CARD_FILL = "#f4f6fa"
_REST_FILL = "#e9ebef"
_INK = "#22323a"
_KEY_BORDER = "#b9c2c7"
_WHITE_FILL = "#ffffff"
_WHITE_HL = "#6f97a4"
_BLACK_PLAIN = "#31424a"
_BLACK_HL = "#2a3d46"


def _octave_expand(low: int, high: int) -> Tuple[int, int]:
    """Expand ``[low, high]`` outward so it starts on a C and ends on a B."""
    low -= low % 12
    high += 11 - (high % 12)
    return low, high


def _window(notes: Sequence[int], default_low: int, default_high: int) -> Tuple[int, int]:
    """Compute an octave-aligned window covering ``notes``, or a fallback."""
    if not notes:
        return default_low, default_high
    return _octave_expand(min(notes), max(notes))


def _white_keys(low: int, high: int) -> List[int]:
    """List the white-key MIDI notes in ``[low, high]``, low to high."""
    return [n for n in range(low, high + 1) if n % 12 in WHITE_PC]


@dataclass(frozen=True)
class _Geometry:
    """Derived, song-wide layout numbers for one (ctx, height) pair."""

    two_row: bool
    lh_low: int
    lh_high: int
    rh_low: int
    rh_high: int
    ww: float
    wh: float
    bw: float
    bh: float
    row_h: float
    card_width: float


class KeyboardCardRenderer(StripRenderer):
    """Draw each chord as a chord-symbol label over a mini piano keyboard."""

    id = "keyboard"
    label = "Keyboard"
    requires_fingering = False

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay cards out left to right with a uniform, song-wide-derived width.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slim slot per rest and one
            keyboard-card slot per sounding chord, in song order.
        """
        geo = self._geometry(ctx, height)
        slots: List[SlotBox] = []
        x = STRIP_MARGIN
        for index, chord in enumerate(ctx.song.chords):
            width = REST_WIDTH if chord.is_rest else geo.card_width
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width + CARD_GAP

        content_width = (x - CARD_GAP + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw a card per slot: chord symbol on top, keyboard row(s) below.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``
                (geometry is recomputed from ``layout.height`` so the two stay
                in lockstep without ``StripLayout`` carrying extra fields).
        """
        geo = self._geometry(ctx, layout.height)
        chords = ctx.song.chords
        card_h = max(1.0, layout.height - 2 * CARD_VMARGIN)

        for slot in layout.slots:
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"

            if chord.is_rest:
                ops.rect(
                    slot.x,
                    CARD_VMARGIN,
                    slot.width,
                    card_h,
                    fill=_REST_FILL,
                    outline=_CARD_OUTLINE,
                    width=1.0,
                    tags=(tag,),
                )
                continue

            ops.rect(
                slot.x,
                CARD_VMARGIN,
                slot.width,
                card_h,
                fill=_CARD_FILL,
                outline=_CARD_OUTLINE,
                width=1.0,
                tags=(tag,),
            )
            ops.text(
                slot.x + slot.width / 2.0,
                CARD_VMARGIN + TEXT_H / 2.0,
                chord.chord_info.chord,
                anchor="center",
                size=11,
                fill=_INK,
                bold=True,
                tags=(tag,),
            )

            notes = chord.midi_notes or []
            rows_top = CARD_VMARGIN + TEXT_H + ROWS_TOP_GAP
            if geo.two_row:
                hand_split = chord.hand_split if chord.hand_split is not None else 0
                lh_notes = notes[:hand_split]
                rh_notes = notes[hand_split:]
                rh_y = rows_top
                lh_y = rh_y + geo.row_h + ROW_GAP
                self._paint_row(ops, slot, tag, "rh", geo.rh_low, geo.rh_high, rh_notes, rh_y, geo)
                self._paint_row(ops, slot, tag, "lh", geo.lh_low, geo.lh_high, lh_notes, lh_y, geo)
            else:
                self._paint_row(ops, slot, tag, "all", geo.rh_low, geo.rh_high, notes, rows_top, geo)

    def _paint_row(
        self,
        ops: DrawOps,
        slot: SlotBox,
        tag: str,
        hand_tag: str,
        low: int,
        high: int,
        highlighted: Sequence[int],
        y: float,
        geo: _Geometry,
    ) -> None:
        """Draw one keyboard row (white keys, then black keys on top).

        Args:
            ops: Recorder to append draw ops to.
            slot: The chord's slot (for horizontal centering within its width).
            tag: The slot's hit-test tag, shared by every op in this card.
            hand_tag: ``'lh'``, ``'rh'``, or ``'all'`` -- which row this is.
            low: Window low bound (a C), song-wide for this hand.
            high: Window high bound (a B), song-wide for this hand.
            highlighted: This chord's MIDI notes belonging to this hand.
            y: Top y coordinate of the row.
            geo: Precomputed key-size geometry, shared by every row/card.
        """
        whites = _white_keys(low, high)
        idx = {n: i for i, n in enumerate(whites)}
        row_width = len(whites) * geo.ww
        x0 = slot.x + (slot.width - row_width) / 2.0
        hl = set(highlighted)

        for n in whites:
            x = x0 + idx[n] * geo.ww
            fill = _WHITE_HL if n in hl else _WHITE_FILL
            ops.rect(
                x,
                y,
                geo.ww,
                geo.wh,
                fill=fill,
                outline=_KEY_BORDER,
                width=1.0,
                tags=(tag, f"hand:{hand_tag}", "key:white", f"note:{n}"),
            )

        for n in range(low, high + 1):
            if n % 12 in WHITE_PC:
                continue
            x = x0 + (idx[n - 1] + 1) * geo.ww - geo.bw / 2.0
            fill = _BLACK_HL if n in hl else _BLACK_PLAIN
            ops.rect(
                x,
                y,
                geo.bw,
                geo.bh,
                fill=fill,
                tags=(tag, f"hand:{hand_tag}", "key:black", f"note:{n}"),
            )

    def _geometry(self, ctx: SheetContext, height: float) -> _Geometry:
        """Derive song-wide windows and key sizes for a given content height.

        A pure function of ``(ctx, height)``: recomputing it in both
        :meth:`layout` and :meth:`paint` (the latter via ``layout.height``)
        yields identical numbers without ``StripLayout`` needing extra fields.
        """
        sounding = [c for c in ctx.song.chords if not c.is_rest and c.midi_notes]
        two_row = any(c.hand_split is not None for c in sounding)

        if two_row:
            lh_notes: List[int] = []
            rh_notes: List[int] = []
            for chord in sounding:
                hand_split = chord.hand_split if chord.hand_split is not None else 0
                lh_notes.extend(chord.midi_notes[:hand_split])
                rh_notes.extend(chord.midi_notes[hand_split:])
            lh_low, lh_high = _window(lh_notes, _DEFAULT_LH_LOW, _DEFAULT_LH_HIGH)
            rh_low, rh_high = _window(rh_notes, _DEFAULT_RH_LOW, _DEFAULT_RH_HIGH)
        else:
            all_notes: List[int] = []
            for chord in sounding:
                all_notes.extend(chord.midi_notes)
            rh_low, rh_high = _window(all_notes, _DEFAULT_RH_LOW, _DEFAULT_RH_HIGH)
            lh_low, lh_high = rh_low, rh_high  # Unused (single row), kept defined.

        row_gap = ROW_GAP if two_row else 0.0
        n_rows = 2 if two_row else 1
        available = max(
            0.0, height - 2 * CARD_VMARGIN - TEXT_H - ROWS_TOP_GAP - row_gap
        )
        row_h = max(MIN_ROW_H, available / n_rows)
        ww = row_h / WHITE_ASPECT
        wh = row_h
        bw = ww * BLACK_WIDTH_RATIO
        bh = wh * BLACK_HEIGHT_RATIO

        rh_width = len(_white_keys(rh_low, rh_high)) * ww
        if two_row:
            lh_width = len(_white_keys(lh_low, lh_high)) * ww
            card_width = max(rh_width, lh_width)
        else:
            card_width = rh_width

        return _Geometry(
            two_row=two_row,
            lh_low=lh_low,
            lh_high=lh_high,
            rh_low=rh_low,
            rh_high=rh_high,
            ww=ww,
            wh=wh,
            bw=bw,
            bh=bh,
            row_h=row_h,
            card_width=card_width,
        )

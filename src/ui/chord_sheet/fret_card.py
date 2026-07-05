"""Fretted-instrument chord-box renderer: one card per chord, nut at top.

:class:`FretCardRenderer` draws each sounding chord as a standard vertical
chord diagram (strings vertical, frets horizontal, nut/fret-position marker at
top) with the chord symbol printed above it. Rests and chords voiced without
fingering data (``RenderedChord.fingering is None``) get a slim empty card,
matching :class:`~ui.chord_sheet.name_card.NameCardRenderer`'s rest handling.

The diagram logic is a direct port of the user's own ``guitar_svg`` generator
(``scripts/music/chord_diagrams.py`` in the tibich.com blog repo): strings are
vertical lines with the *lowest* string leftmost (``fingering[0]`` is the
lowest string, per ``RenderedChord.fingering``'s documented convention), frets
are horizontal lines, and:

- ``base = 1`` (nut visible, thick bar drawn above the grid) when the whole
  fretted shape fits within the default rows (or nothing is fretted).
- otherwise ``base = min(fretted positions)``, and a ``'<base>fr'`` label is
  drawn to the left of the first fret row instead of a nut bar. Open strings
  keep their circle above the grid in either case -- an open marker means
  "open" regardless of position, so a voicing that mixes open strings with an
  8th-position shape stays a compact ``8fr`` box instead of stretching the
  grid from the nut (this deliberately diverges from the blog script, whose
  figures were all open-position shapes).
- a fretted position lands in row ``f - base + 0.5`` (centered in its row).

Unlike the static SVG script (fixed pixel constants), geometry here is a pure
function of ``(ctx, height)`` per the renderer contract: every length derives
from the given content ``height`` plus two song-wide quantities computed once
per render -- the string count (``len(fingering)`` of any chord that has one,
default 6) and the fret-row count (4 by default, extended for every card in
the song if some chord's fretted span needs more rows, so all cards stay
uniform). Card width is likewise a single value derived from those song-wide
quantities, so every sounding-chord card in the strip is the same width.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    chord_symbol_label,
    SlotBox,
    StripLayout,
    StripRenderer,
)

#: Horizontal gap between adjacent cards, px.
CARD_GAP = 8.0
#: Leading/trailing padding at the strip's left and right edges, px.
STRIP_MARGIN = 12.0
#: Width of a rest/no-fingering slot's slim card, px.
REST_WIDTH = 30.0
#: Minimum number of fret rows drawn, extended song-wide when a shape needs more.
DEFAULT_ROWS = 4
#: Fallback string count when no chord in the song carries fingering data.
DEFAULT_STRING_COUNT = 6

#: Content height above which a card stops growing with the panel and is
#: instead vertically centered in the available height, at zoom 1.0.
#:
#: Before this cap, every pixel length was a fraction of the raw panel
#: height, so a tall panel produced oversized boxes the user had to shrink
#: the panel to read comfortably. At height=230 with the default 4 rows:
#: symbol_h = 230 * 0.22 =~ 50.6, grid_h = 230 - 50.6 - 12 =~ 167.4,
#: row_h = 167.4 / 4 =~ 41.9, string_gap = row_h * 0.85 =~ 35.6,
#: dot_r =~ 12.1, open_r =~ 8.5 -- a comfortably large, crisp card. Past
#: this, growth stops and the fixed-size card centers instead, mirroring
#: the tab lane's fixed-size block centering.
MAX_CONTENT_HEIGHT = 230.0

#: Palette (module-local; echoes the user's blog diagrams).
_ACCENT = "#2a3d46"  # fretted-note dots
_INK = "#22323a"  # nut bar, open-circle outline, chord symbol
_MUTE = "#8b949b"  # muted-string '×', base-fret label
_GRID = "#b9c2c7"  # fret/string grid lines

# Geometry ratios: fractions of the given content height / row height that
# keep the diagram's proportions stable as the strip is resized. Mirrors the
# source SVG's fixed SG=15 / FG=18 (string gap ~0.83x the fret-row height).
_SYMBOL_FRAC = 0.22
_GRID_VPAD = 6.0
_SG_TO_ROW = 0.85
_SIDE_PAD_FACTOR = 1.35
_MARKER_GAP_FACTOR = 0.5
_DOT_RADIUS_FACTOR = 0.34
_OPEN_RADIUS_FACTOR = 0.24
_NUT_HEIGHT_FACTOR = 0.12


@dataclass(frozen=True)
class _Geometry:
    """Resolved pixel geometry for one render, shared by every card."""

    card_width: float
    symbol_h: float
    grid_top: float
    grid_left: float
    row_h: float
    string_gap: float
    box_w: float
    rows: int
    nut_h: float
    marker_gap: float
    dot_r: float
    open_r: float
    symbol_size: int
    label_size: int


def _chord_base(fingering: List[int]) -> int:
    """Return the fret-position base (1 = nut visible) for a fingering.

    The grid starts at the nut only when the whole fretted shape fits within
    the default rows; otherwise it starts at the lowest fretted note and gets
    a ``'<base>fr'`` position label. Open strings do NOT force the grid back
    to the nut: their circles above the grid mean "open" regardless of
    position (standard chord-chart practice), which keeps a shape like an
    open string against an 8th-position voicing to a few rows instead of
    stretching the grid from the nut to fret ten.
    """
    fretted = [f for f in fingering if f > 0]
    if not fretted or max(fretted) <= DEFAULT_ROWS:
        return 1
    return min(fretted)


def _song_geometry_inputs(song: RenderedSong) -> tuple:
    """Compute the song-wide row count and string count once per render.

    Walks every chord's fingering to find the widest fretted span (extending
    ``DEFAULT_ROWS`` if needed) and the string count, so every card in the
    strip draws the same number of rows/strings regardless of which chord's
    shape happens to need them.
    """
    rows = DEFAULT_ROWS
    string_count: Optional[int] = None
    for chord in song.chords:
        fingering = chord.fingering
        if not fingering:
            continue
        if string_count is None:
            string_count = len(fingering)
        base = _chord_base(fingering)
        fretted = [f for f in fingering if f > 0]
        if fretted:
            span = max(fretted) - base + 1
            rows = max(rows, span)
    return rows, (string_count or DEFAULT_STRING_COUNT)


def _compute_geometry(height: float, rows: int, string_count: int) -> _Geometry:
    """Derive every pixel length from the content ``height`` alone (plus the
    song-wide ``rows``/``string_count``), so painting is a pure function of
    ``(ctx, height)``."""
    symbol_h = max(14.0, height * _SYMBOL_FRAC)
    grid_h = max(24.0, height - symbol_h - 2 * _GRID_VPAD)
    row_h = grid_h / rows
    string_gap = row_h * _SG_TO_ROW
    box_w = string_gap * (string_count - 1) if string_count > 1 else string_gap
    side_pad = string_gap * _SIDE_PAD_FACTOR
    return _Geometry(
        card_width=box_w + 2 * side_pad,
        symbol_h=symbol_h,
        grid_top=symbol_h + _GRID_VPAD,
        grid_left=side_pad,
        row_h=row_h,
        string_gap=string_gap,
        box_w=box_w,
        rows=rows,
        nut_h=max(2.0, row_h * _NUT_HEIGHT_FACTOR),
        marker_gap=max(6.0, row_h * _MARKER_GAP_FACTOR),
        dot_r=max(2.5, string_gap * _DOT_RADIUS_FACTOR),
        open_r=max(2.0, string_gap * _OPEN_RADIUS_FACTOR),
        symbol_size=int(max(9, min(16, round(height * 0.11)))),
        label_size=int(max(7, min(11, round(height * 0.08)))),
    )


def _has_shape(chord: RenderedChord) -> bool:
    """Whether a chord gets a full fret-box card (vs. a slim empty one)."""
    return (not chord.is_rest) and bool(chord.fingering)


def _capped_content_height(height: float, zoom: float) -> Tuple[float, float]:
    """Resolve the content height used for geometry math, plus top padding.

    Content height never exceeds ``MAX_CONTENT_HEIGHT * zoom``: past that cap,
    the card's geometry stops growing with the panel, and the returned top
    padding centers the resulting (shorter, fixed-size) block within
    ``height`` instead. Below the cap, this returns ``height`` unchanged with
    zero padding, so the existing "scale to height" behavior is untouched.

    Args:
        height: Raw available content height in pixels.
        zoom: User zoom factor; scales the cap so ``+`` can grow cards past
            what the base cap allows and ``-`` shrinks them.

    Returns:
        ``(content_height, top_pad)``.
    """
    cap = MAX_CONTENT_HEIGHT * zoom
    content_height = min(height, cap)
    top_pad = max(0.0, (height - content_height) / 2.0)
    return content_height, top_pad


class FretCardRenderer(StripRenderer):
    """Draw fretted-instrument chords as vertical chord-box cards."""

    id = "fret"
    label = "Fret cards"
    requires_fingering = True
    supports_zoom = True

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay cards out left to right with a uniform width for every shape.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slim slot per rest/no-fingering
            chord and one full-width slot per chord with a fingering, in song
            order.
        """
        rows, string_count = _song_geometry_inputs(ctx.song)
        content_height, _ = _capped_content_height(height, ctx.zoom)
        geo = _compute_geometry(content_height, rows, string_count)

        slots: List[SlotBox] = []
        x = STRIP_MARGIN
        for index, chord in enumerate(ctx.song.chords):
            width = geo.card_width if _has_shape(chord) else REST_WIDTH
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width + CARD_GAP

        content_width = (x - CARD_GAP + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw each card's chord symbol and fret-box diagram.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        rows, string_count = _song_geometry_inputs(ctx.song)
        content_height, top_pad = _capped_content_height(layout.height, ctx.zoom)
        geo = _compute_geometry(content_height, rows, string_count)
        chords = ctx.song.chords

        for slot in layout.slots:
            chord = chords[slot.chord_index]
            if not _has_shape(chord):
                continue  # slim empty card: no ops
            self._paint_card(ops, chord, slot, geo, top_pad)

    def _paint_card(
        self,
        ops: DrawOps,
        chord: RenderedChord,
        slot: SlotBox,
        geo: _Geometry,
        top_pad: float = 0.0,
    ) -> None:
        """Draw one chord's symbol + fret-box diagram at its slot."""
        tag = f"slot:{slot.chord_index}"
        fingering = chord.fingering
        base = _chord_base(fingering)

        ops.text(
            slot.x + geo.card_width / 2.0,
            top_pad + geo.symbol_h / 2.0,
            chord_symbol_label(chord),
            anchor="center",
            size=geo.symbol_size,
            fill=_INK,
            bold=True,
            tags=(tag,),
        )

        grid_left = slot.x + geo.grid_left
        grid_top = top_pad + geo.grid_top
        box_w = geo.box_w
        row_h = geo.row_h

        if base == 1:
            ops.rect(
                grid_left,
                grid_top - geo.nut_h,
                box_w,
                geo.nut_h,
                fill=_INK,
                tags=(tag,),
            )
        else:
            ops.text(
                grid_left - 4.0,
                grid_top + row_h * 0.7,
                f"{base}fr",
                anchor="e",
                size=geo.label_size,
                fill=_MUTE,
                tags=(tag,),
            )

        for r in range(geo.rows + 1):
            y = grid_top + r * row_h
            ops.line(
                [(grid_left, y), (grid_left + box_w, y)], fill=_GRID, tags=(tag,)
            )

        n = len(fingering)
        grid_bottom = grid_top + geo.rows * row_h
        for i in range(n):
            x = grid_left + i * geo.string_gap
            ops.line([(x, grid_top), (x, grid_bottom)], fill=_GRID, tags=(tag,))

        for i, f in enumerate(fingering):
            x = grid_left + i * geo.string_gap
            if f == -1:
                ops.text(
                    x,
                    grid_top - geo.marker_gap,
                    "×",
                    anchor="center",
                    size=geo.label_size,
                    fill=_MUTE,
                    tags=(tag,),
                )
            elif f == 0:
                r = geo.open_r
                ops.oval(
                    x - r,
                    grid_top - geo.marker_gap - r,
                    2 * r,
                    2 * r,
                    outline=_INK,
                    width=1.1,
                    tags=(tag,),
                )
            else:
                r = geo.dot_r
                cy = grid_top + (f - base + 0.5) * row_h
                ops.oval(x - r, cy - r, 2 * r, 2 * r, fill=_ACCENT, tags=(tag,))

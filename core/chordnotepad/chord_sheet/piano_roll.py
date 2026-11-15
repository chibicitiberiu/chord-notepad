"""Chord-sheet strip renderer: a DAW-style piano roll.

:class:`PianoRollRenderer` replaces the earlier per-chord mini-keyboard cards
(``KeyboardCardRenderer``) with a single continuous lane, in the spirit of
:class:`~chord_sheet.tab_strip.TabStripRenderer`: one row per semitone,
spanning the song-wide voiced pitch range, with duration-proportional slots
carrying horizontal note bars instead of a repeated keyboard diagram. The
per-card keyboard read poorly once several cards were on screen at once (too
wide, highlighted keys hard to pick out); a continuous roll reads the way a
DAW piano-roll editor does -- pitch is a vertical position shared across the
whole strip, so contour and movement are visible at a glance.

Layout:

- **Pitch axis:** song-wide range from the lowest to the highest voiced MIDI
  note, padded by two semitones on each side, one row per semitone. Row height
  is simply ``usable_height / row_count`` -- for a narrow vocal-range song
  that comfortably exceeds a readable few pixels per row; for a song spanning
  many octaves rows shrink accordingly. The strip never scrolls vertically, so
  there is no floor enforced beyond what the division naturally yields.
- **Frozen left gutter (``GUTTER_W`` px, wider in European notation):** a
  small vertical keyboard aligned with the rows -- white-key row blocks span
  the full gutter width, black-key rows are narrower, darker and rounded on
  the right, and each C row gets a tiny octave label in the song's notation
  (``C3``/``Do3``), drawn last, at the right edge clear of the black keys. The gutter is painted by :meth:`PianoRollRenderer.paint_gutter`
  onto a separate, non-scrolling canvas so it stays visible while the content
  scrolls; it is static (``scroll_x`` is ignored). Chord slots in the scrolling
  content start at the content's left margin (x = 0), not offset by the gutter.
- **Section bands:** every second section is on ``SECTION_BAND`` paper
  (``renderer_interface.paint_section_bands``), drawn first.
- **Row shading:** black-key rows get a slightly darker fill than
  ``STRIP_BG`` across the whole lane for the classic DAW-roll look (over a
  banded section, ``BAND_BLACK_ROW_SHADE``, a step darker again). A light
  guide line marks every octave (under each C row, where B meets C: two
  white rows nothing else separates), a darker one under C4 (MIDI 60). Both
  live in the scrolling content, full width, under a hairline that closes
  the chord-name band.
- **Slots:** one per chord in song order (rests included, as gaps -- nothing
  is drawn for them beyond the shared bar-line/shading passes), exactly as
  wide as the chord is long: ``PX_PER_BEAT`` per beat, scaled by the view's
  zoom, never clamped. The x axis is time in beats, so every bar of one time
  signature has the same width (a ``C*8`` in 4/4 spans two bars), a 3/4 bar
  is three quarters of a 4/4 one, and a tempo change changes no width. Zoom
  widens time only: the rows always share the strip height.
- **Note bars:** one rounded horizontal bar per sounding note, positioned by
  row, without an outline. Ensemble voicings (``voice_notes`` present) color
  each bar by voice index low-to-high via ``VOICE_COLORS`` (iterating
  ``voice_notes`` rather than the deduplicated ``midi_notes``, so unison
  voices each draw their own bar). Piano voicings (``hand_split`` is not
  ``None``) color left-hand notes ``HAND_COLORS['lh']`` and right-hand notes
  ``HAND_COLORS['rh']``. Everything else (guitar) uses ``NOTE_FILL``.
- **Note names:** a bar tall and wide enough carries its note's name
  (``C#3``, ``Do#3``), spelled from the chord and the key in force as the
  staff spells it (:mod:`~chord_sheet.spelling`), in the song's notation.
- **Chord symbols** (``chord_symbol_label``) sit in a band above the roll,
  centered over each slot; a name too wide for its slot (a short chord) is
  left out, never shrunk or run into the next one.
- **Bar and beat lines:** a vertical light rule at every measure boundary,
  placed by the shared :func:`~chord_sheet.renderer_interface.bar_line_xs`
  helper, and a fainter one at every beat between them while beats are at
  least ``MIN_BEAT_SPACING`` apart. With the linear time axis both fall on a
  regular grid.
"""

import math
from typing import List, Optional, Tuple

from chordnotepad.models.rendered_song import RenderedChord, RenderedSong
from chordnotepad.chord_sheet.ops import DrawOps
from chordnotepad.chord_sheet.renderer_interface import (
    HAND_COLORS,
    SheetContext,
    VOICE_COLORS,
    bar_line_xs,
    beat_boundaries,
    beat_xs,
    chord_symbol_label,
    label_ems,
    paint_section_bands,
    SlotBox,
    StripLayout,
    StripRenderer,
)
from chordnotepad.chord_sheet.spelling import note_name, spelled_name, SpelledNote

#: Pitch classes that fall on a white key.
WHITE_PC = {0, 2, 4, 5, 7, 9, 11}

#: Width of the frozen left-hand mini-keyboard gutter, px (American octave
#: labels, ``C4``): the black keys, then a lane for the labels that keeps them
#: a couple of px clear of the keys.
GUTTER_W = 46.0
#: The gutter with European octave labels (``Do4``): the black keys keep their
#: length and the label lane beside them widens.
GUTTER_W_EUROPEAN = 54.0
#: Trailing padding after the last slot, px. The scrolling content has no
#: leading margin: slots start at the content's left edge (x = 0), and the
#: keyboard lives in the frozen gutter canvas, not in the content.
STRIP_MARGIN = 12.0
#: Pixels per beat at zoom 1. The roll's x axis is time: a slot is exactly
#: its chord's beats wide, never clamped, so every bar of a time signature has
#: one width (96 px in 4/4) and the bar and beat lines fall on a regular grid.
#: 24 is the tab and staff views' width for a beat, so the usual one- to
#: four-beat chords keep the size they have there and had here before.
PX_PER_BEAT = 24.0
#: Beat lines are left out when beats are closer than this, px.
MIN_BEAT_SPACING = 8.0
#: Room a chord name keeps from its slot's edges, px; a name that doesn't fit
#: is left out rather than shrunk or run into the next one.
NAME_PAD = 2.0
#: The chord names' size, pt.
NAME_PT = 12
#: The smallest a chord name gets when a short chord's slot is narrow.
NAME_MIN_PT = 6

#: Vertical space above the roll reserved for chord-symbol text, px.
SYMBOL_H = 22.0
#: Horizontal inset of a note bar within its slot, px.
NOTE_PAD = 2.0
#: Vertical gap left below each note bar (row height minus this), px.
ROW_GAP = 1.0
#: Largest corner radius of a note bar or a black key, px (a third of the
#: height below that, so thin bars stay bars).
CORNER_R = 2.0

#: Note names: shown in bars at least this tall, px.
LABEL_MIN_BAR_H = 9.0
#: The name's text height as a share of the bar's.
LABEL_HEIGHT_RATIO = 0.75
#: The name's size never goes past this, pt (tall strips with few rows).
LABEL_MAX_PT = 9
#: Inset of the name from the bar's left edge, px; it needs this much room
#: on both sides to be shown.
LABEL_INSET = 3.0
#: Text sizes are points at 96 dpi, as every front end draws them.
_PT_TO_PX = 4.0 / 3.0

#: Fallback pitch window (before padding) when the song has no voiced notes
#: at all (empty song, or every chord a rest) -- C4 to B4.
_DEFAULT_LOW, _DEFAULT_HIGH = 60, 71
#: Semitones of padding added on each side of the song-wide voiced range.
_PAD = 2

#: The guitar (and any voicing without hands or voices) bars: the app's
#: indigo, a step lighter than its accent.
NOTE_FILL = "#5c6bc0"
#: The note names inside the bars: white on the light theme's bars. The front
#: ends map it to a dark ink for the dark theme's lighter bars (Qt
#: ``sheet_paint.themed_color``, Android ``themedSheetColor``); it must stay
#: distinct from the keyboard's ``#ffffff``, which they map otherwise.
NOTE_LABEL = "#fdfdff"

#: The roll's chrome (cool greys, in the Qt window's neutrals): chord names,
#: bar lines and the band's hairline, black-key row shade, octave guides.
_INK = "#22323a"
GRID = "#cdd1d8"
#: The beat lines between bar lines: fainter than the bar lines.
BEAT_GRID = "#e2e5e9"
BLACK_ROW_SHADE = "#eceef2"
#: A black-key row over a banded section (``SECTION_BAND``): a step darker.
BAND_BLACK_ROW_SHADE = "#e7e9ed"
GUIDE_C = "#dfe2e7"
GUIDE_C4 = "#b4b9c2"
#: The keyboard in the gutter.
GUTTER_WHITE = "#ffffff"
GUTTER_BLACK = "#31424a"
GUTTER_BORDER = "#b9c2c7"

#: Length of a black key in the gutter, px: 62% of the 44 px keyboard the roll
#: had before the label lane widened, whatever the gutter's width.
BLACK_KEY_W = 27.28
#: The octave labels' size, pt, and their gap to the gutter's right edge, px.
_OCTAVE_LABEL_PT = 8
_OCTAVE_LABEL_INSET = 2.0


def _slot_width(duration_beats: float, zoom: float = 1.0) -> float:
    """Slot width: the chord's beats at ``PX_PER_BEAT * zoom``, unclamped
    (the x axis is time)."""
    return max(0.0, duration_beats) * PX_PER_BEAT * zoom


def name_fits(label: str, slot_w: float, size: int = NAME_PT) -> bool:
    """Whether a chord name fits over its slot at ``size`` pt (estimated
    bold width, ``NAME_PAD`` either side)."""
    return label_ems(label) * size * _PT_TO_PX <= slot_w - 2 * NAME_PAD


def name_size(label: str, slot_w: float) -> int:
    """The size a chord name is drawn at over its slot: ``NAME_PT`` when it
    fits, else the largest size down to ``NAME_MIN_PT`` that does, and
    ``NAME_MIN_PT`` when even that doesn't. A name is never hidden (Tibi,
    2026-11-15: "we shouldn't hide names, if we have to we render
    smaller"); every name is centred on the band's middle, so a smaller one
    doesn't sit higher than its neighbours."""
    for size in range(NAME_PT, NAME_MIN_PT - 1, -1):
        if name_fits(label, slot_w, size):
            return size
    return NAME_MIN_PT


def _gutter_width(notation: str) -> float:
    """The keyboard gutter's width for octave labels in ``notation``."""
    return GUTTER_W_EUROPEAN if notation == "european" else GUTTER_W


def _corner(h: float) -> float:
    """Corner radius for a bar or key ``h`` px tall."""
    return min(CORNER_R, h / 3.0)


def octave_label(note: int, notation: str = "american") -> str:
    """The gutter's label for a C row: ``C4`` or ``Do4`` (MIDI 60)."""
    return spelled_name(SpelledNote("C", 0, note // 12 - 1), notation)


def label_size(bar_h: float) -> int:
    """The note-name size in pt for a bar ``bar_h`` px tall: its text
    ``LABEL_HEIGHT_RATIO`` of the bar, rounded up to a whole point (Tk takes
    no fractions; up, because the smallest names are the hardest to read), at
    most ``LABEL_MAX_PT``."""
    return max(1, min(LABEL_MAX_PT, math.ceil(bar_h * LABEL_HEIGHT_RATIO / _PT_TO_PX - 1e-9)))


def label_fits(name: str, bar_w: float, bar_h: float) -> bool:
    """Whether a bar shows its note name: tall enough to read, and wide
    enough for the (estimated) text with ``LABEL_INSET`` either side."""
    if bar_h < LABEL_MIN_BAR_H:
        return False
    width = label_ems(name) * label_size(bar_h) * _PT_TO_PX
    return width <= bar_w - 2 * LABEL_INSET


def _row_metrics(song: RenderedSong, height: float) -> Tuple[int, int, float]:
    """Return ``(low, high, row_h)`` for the song's pitch rows at ``height``.

    Shared by the scrolling content (row shading / guides / note bars) and the
    frozen gutter keyboard so both agree on row positions.
    """
    low, high = _pitch_range(song)
    row_count = high - low + 1
    usable = max(0.0, height - SYMBOL_H)
    row_h = usable / row_count if row_count > 0 else 0.0
    return low, high, row_h


def _pitch_range(song: RenderedSong) -> Tuple[int, int]:
    """Song-wide voiced MIDI range, padded by ``_PAD`` semitones each way.

    Falls back to a default one-octave window (still padded) when the song
    has no voiced notes at all (empty song, or every chord a rest/skip).
    """
    notes: List[int] = []
    for chord in song.chords:
        if not chord.is_rest and chord.midi_notes:
            notes.extend(chord.midi_notes)
    low, high = (min(notes), max(notes)) if notes else (_DEFAULT_LOW, _DEFAULT_HIGH)
    return low - _PAD, high + _PAD


class PianoRollRenderer(StripRenderer):
    """Draw the whole song as a continuous DAW-style piano roll."""

    id = "keyboard"  # Stable id kept for config compatibility (persisted view).
    label = "Piano roll"
    requires_fingering = False
    supports_zoom = True

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay slots out left to right from the content's left margin, width
        proportional to duration and scaled by the zoom.

        The keyboard now lives in the frozen gutter (see :meth:`paint_gutter`),
        so content slots start at x = 0 -- no gutter offset.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord (rests included as
            gaps -- the roll draws nothing for them beyond shared shading/bar
            lines), in song order, contiguous starting at the content's left
            edge.
        """
        slots: List[SlotBox] = []
        x = 0.0
        for index, chord in enumerate(ctx.song.chords):
            width = _slot_width(chord.duration_beats, ctx.zoom)
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width

        content_width = (x + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def gutter_width(self, ctx: SheetContext, height: float) -> float:
        """Width of the frozen keyboard gutter (``GUTTER_W``, or
        ``GUTTER_W_EUROPEAN`` for the longer European octave labels)."""
        return _gutter_width(ctx.notation)

    def paint_gutter(self, ops: DrawOps, ctx: SheetContext, height: float,
                     scroll_x: float) -> None:
        """Paint the vertical mini-keyboard into the frozen gutter.

        A bed in the white keys' colour goes under the whole keyboard first.
        White-key rows fill the gutter width; black-key rows draw a narrower,
        darker block, rounded on the right (it starts a corner radius left of
        the gutter, which clips its left corners away); each C row gets a tiny
        octave label. Coordinates are gutter-local (x = 0 is the gutter's left
        edge) and static -- the keyboard is pitch-indexed, not time-indexed, so
        ``scroll_x`` is ignored.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            height: Available content height in pixels.
            scroll_x: Ignored (the keyboard does not scroll horizontally).
        """
        song = ctx.song
        low, high, row_h = _row_metrics(song, height)
        width = _gutter_width(ctx.notation)
        black_w = BLACK_KEY_W
        radius = _corner(row_h)

        # The bed: the white keys' colour under the whole keyboard, so the
        # space beside each black key is a key, not a hole (Android showed
        # the strip's background there; the desktop painted its own bed).
        ops.rect(0.0, SYMBOL_H, width, (high - low + 1) * row_h, fill=GUTTER_WHITE,
                 tags=("gutter", "gutter-bed"))
        for note in range(low, high + 1):
            y = SYMBOL_H + (high - note) * row_h
            pc = note % 12
            if pc not in WHITE_PC:
                ops.rect(-radius, y, black_w + radius, row_h, fill=GUTTER_BLACK,
                         radius=radius, tags=("gutter", "gutter-key"))
            else:
                ops.rect(0.0, y, width, row_h, fill=GUTTER_WHITE,
                         outline=GUTTER_BORDER, tags=("gutter", "gutter-key"))
        # The octave labels go on top of every key, in the lane to the right
        # of the black keys: a label is taller than a row at the usual strip
        # heights, and over the keys' left part the black key above the C
        # (and the Bb below it) cut it in half.
        for note in range(low, high + 1):
            if note % 12 == 0:
                y = SYMBOL_H + (high - note) * row_h
                ops.text(
                    width - _OCTAVE_LABEL_INSET, y + row_h / 2.0,
                    octave_label(note, ctx.notation),
                    anchor="e", size=_OCTAVE_LABEL_PT, fill=_INK, tags=("gutter", "label"),
                )

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw row shading/guides, measure bar lines, chord symbols, and
        per-note bars into the scrolling content (the keyboard lives in the
        frozen gutter, see :meth:`paint_gutter`).

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        song = ctx.song
        low, high, row_h = _row_metrics(song, layout.height)

        def y_of(note: int) -> float:
            return SYMBOL_H + (high - note) * row_h

        # The sections' paper first; a black-key row over a banded section
        # takes a shade one step darker, so the rows read the same on both.
        bands = paint_section_bands(ops, song, layout)
        segments = []
        x = 0.0
        for x0, x1 in bands:
            if x0 > x:
                segments.append((x, x0, BLACK_ROW_SHADE))
            segments.append((x0, x1, BAND_BLACK_ROW_SHADE))
            x = x1
        if x < layout.width:
            segments.append((x, layout.width, BLACK_ROW_SHADE))
        for note in range(low, high + 1):
            if note % 12 not in WHITE_PC:
                for x0, x1, shade in segments:
                    ops.rect(x0, y_of(note), x1 - x0, row_h,
                             fill=shade, tags=("row-shade",))

        # The octave guides, under each C row (where B meets C), drawn after
        # the shading so a shaded row never covers one.
        for note in range(low, high + 1):
            if note % 12 == 0:
                y = y_of(note) + row_h
                ops.line([(0.0, y), (layout.width, y)],
                         fill=GUIDE_C4 if note == 60 else GUIDE_C,
                         width=1.0, tags=("guide-c",))

        # Faint beat lines between the bar lines, while beats are far enough
        # apart to read as a grid.
        if PX_PER_BEAT * ctx.zoom >= MIN_BEAT_SPACING:
            for bx in beat_xs(layout, song, beat_boundaries(song)):
                ops.line([(bx, SYMBOL_H), (bx, layout.height)],
                         fill=BEAT_GRID, width=1.0, tags=("beat-line",))
        for bx in bar_line_xs(layout, song):
            ops.line([(bx, SYMBOL_H), (bx, layout.height)],
                     fill=GRID, width=1.0, tags=("bar-line",))
        # The hairline that closes the chord-name band.
        ops.line([(0.0, SYMBOL_H), (layout.width, SYMBOL_H)],
                 fill=GRID, width=1.0, tags=("header-rule",))

        chords = song.chords
        for slot in layout.slots:
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"

            label = chord_symbol_label(chord)
            ops.text(
                slot.x + slot.width / 2.0,
                SYMBOL_H / 2.0,
                label,
                anchor="center",
                size=name_size(label, slot.width),
                fill=_INK,
                bold=True,
                tags=(tag,),
            )
            if chord.is_rest:
                continue  # the label marks it; the empty lane is the silence

            self._paint_note_bars(ops, ctx, chord, slot, tag, row_h, y_of)

    def _paint_note_bars(
        self,
        ops: DrawOps,
        ctx: SheetContext,
        chord: RenderedChord,
        slot: SlotBox,
        tag: str,
        row_h: float,
        y_of,
    ) -> None:
        """Draw one rounded bar per sounding note in ``chord``, each with its
        name when it fits (:func:`label_fits`).

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context (the notation).
            chord: The chord being painted (already known not to be a rest).
            slot: The chord's slot.
            tag: The slot's shared hit-test tag.
            row_h: Row height in px, shared by every row.
            y_of: Row-top y position for a given MIDI note.
        """
        bar_x = slot.x + NOTE_PAD
        bar_w = max(1.0, slot.width - 2 * NOTE_PAD)
        bar_h = max(1.0, row_h - ROW_GAP)
        radius = _corner(bar_h)

        bars: List[Tuple[int, str, Tuple[str, ...]]] = []
        if chord.voice_notes is not None:
            for voice_index, note in enumerate(chord.voice_notes):
                bars.append((note, VOICE_COLORS[voice_index % len(VOICE_COLORS)],
                             (tag, f"voice:{voice_index}", f"note:{note}")))
        elif chord.hand_split is not None and chord.midi_notes:
            for note_index, note in enumerate(chord.midi_notes):
                hand = "lh" if note_index < chord.hand_split else "rh"
                bars.append((note, HAND_COLORS[hand], (tag, f"hand:{hand}", f"note:{note}")))
        elif chord.midi_notes:
            for note in chord.midi_notes:
                bars.append((note, NOTE_FILL, (tag, f"note:{note}")))

        show_names = bar_h >= LABEL_MIN_BAR_H
        size = label_size(bar_h)
        for note, color, tags in bars:
            y = y_of(note)
            ops.rect(bar_x, y, bar_w, bar_h, fill=color, radius=radius, tags=tags)
            if not show_names:
                continue
            name = self._note_name(note, chord, ctx.notation)
            if name is not None and label_fits(name, bar_w, bar_h):
                ops.text(bar_x + LABEL_INSET, y + bar_h / 2.0, name, anchor="w",
                         size=size, fill=NOTE_LABEL, tags=(tag, "note-label", f"note:{note}"))

    @staticmethod
    def _note_name(note: int, chord: RenderedChord, notation: str) -> Optional[str]:
        """``note``'s name as the staff spells it in ``chord`` and its key."""
        return note_name(note, chord.chord_notes, chord.key, notation)

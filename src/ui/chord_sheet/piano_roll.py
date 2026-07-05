"""Chord-sheet strip renderer: a DAW-style piano roll.

:class:`PianoRollRenderer` replaces the earlier per-chord mini-keyboard cards
(``KeyboardCardRenderer``) with a single continuous lane, in the spirit of
:class:`~ui.chord_sheet.tab_strip.TabStripRenderer`: one row per semitone,
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
- **Left gutter (``GUTTER_W`` px):** a small vertical keyboard aligned with the
  rows -- white-key row blocks span the full gutter width, black-key rows are
  narrower and darker, and each C row gets a tiny octave label (``C3``,
  ``C4``, ...). The gutter is part of the lane; chord slots start at its right
  edge.
- **Row shading:** black-key rows get a slightly darker fill than
  ``STRIP_BG`` across the whole lane (not just the gutter) for the classic
  DAW-roll look. A light guide line is drawn at every C row, a bolder one at
  C4 (MIDI 60).
- **Slots:** one per chord in song order (rests included, as gaps -- nothing
  is drawn for them beyond the shared bar-line/shading passes), duration-
  proportional using the same ``PX_PER_BEAT``/min/max clamp values as
  :mod:`~ui.chord_sheet.tab_strip` for cross-view consistency.
- **Note bars:** one horizontal bar per sounding note, positioned by row.
  Ensemble voicings (``voice_notes`` present) color each bar by voice index
  low-to-high via ``VOICE_COLORS`` (iterating ``voice_notes`` rather than the
  deduplicated ``midi_notes``, so unison voices each draw their own bar).
  Piano voicings (``hand_split`` is not ``None``) color left-hand notes
  ``HAND_COLORS['lh']`` and right-hand notes ``HAND_COLORS['rh']``. Everything
  else (guitar) uses the flat ``NOTE_INK``.
- **Chord symbols** (``chord_symbol_label``) sit in a band above the roll,
  centered over each slot.
- **Bar lines:** a vertical light rule at the start of every chord whose
  ``bar`` differs from the previous chord's (mirrors
  :class:`~ui.chord_sheet.tab_strip.TabStripRenderer`).
"""

from typing import List, Optional, Tuple

from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    HAND_COLORS,
    NOTE_INK,
    SheetContext,
    VOICE_COLORS,
    chord_symbol_label,
    SlotBox,
    StripLayout,
    StripRenderer,
)

#: Pitch classes that fall on a white key.
WHITE_PC = {0, 2, 4, 5, 7, 9, 11}

#: Width of the left-hand mini-keyboard gutter, px.
GUTTER_W = 44.0
#: Trailing padding after the last slot, px (mirrors tab_strip's leading
#: margin; the roll has no leading margin since the gutter fills that role).
STRIP_MARGIN = 12.0
#: Pixels per beat before clamping -- identical to tab_strip's, so a chord of
#: a given duration reads the same width across the tab and piano-roll views.
PX_PER_BEAT = 24.0
#: Narrowest a slot may be regardless of duration.
MIN_SLOT_WIDTH = 20.0
#: Widest a slot may be regardless of duration.
MAX_SLOT_WIDTH = 120.0

#: Vertical space above the roll reserved for chord-symbol text, px.
SYMBOL_H = 22.0
#: Horizontal inset of a note bar within its slot, px.
NOTE_PAD = 2.0
#: Vertical gap left below each note bar (row height minus this), px.
ROW_GAP = 1.0

#: Fallback pitch window (before padding) when the song has no voiced notes
#: at all (empty song, or every chord a rest) -- C4 to B4.
_DEFAULT_LOW, _DEFAULT_HIGH = 60, 71
#: Semitones of padding added on each side of the song-wide voiced range.
_PAD = 2

#: Palette (module-local; the shared palette in renderer_interface covers
#: note-fill colors, but the roll's own chrome -- gutter, shading, guides,
#: bar lines, text -- needs a few more).
_INK = "#22323a"
_GRID = "#b9c2c7"
_BLACK_ROW_SHADE = "#eef0ec"
_GUTTER_WHITE = "#ffffff"
_GUTTER_BLACK = "#31424a"
_GUTTER_BORDER = "#b9c2c7"
_GUIDE_C = "#d9ddd6"
_GUIDE_C4 = "#a9b0a6"

#: Black-key gutter blocks are narrower than the full gutter width.
_BLACK_GUTTER_RATIO = 0.62


def _slot_width(duration_beats: float) -> float:
    """Slot width proportional to duration, clamped to [MIN, MAX]."""
    return max(MIN_SLOT_WIDTH, min(MAX_SLOT_WIDTH, duration_beats * PX_PER_BEAT))


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

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay slots out left to right after the gutter, width proportional
        to duration.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord (rests included as
            gaps -- the roll draws nothing for them beyond shared shading/bar
            lines), in song order, contiguous starting at the gutter's right
            edge.
        """
        slots: List[SlotBox] = []
        x = GUTTER_W
        for index, chord in enumerate(ctx.song.chords):
            width = _slot_width(chord.duration_beats)
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width

        content_width = (x + STRIP_MARGIN) if slots else (GUTTER_W + 2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Draw row shading/guides, the gutter keyboard, bar lines, chord
        symbols, and per-note bars.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        song = ctx.song
        low, high = _pitch_range(song)
        row_count = high - low + 1
        usable = max(0.0, layout.height - SYMBOL_H)
        row_h = usable / row_count if row_count > 0 else 0.0

        def y_of(note: int) -> float:
            return SYMBOL_H + (high - note) * row_h

        for note in range(low, high + 1):
            y = y_of(note)
            pc = note % 12
            is_black = pc not in WHITE_PC

            if is_black:
                ops.rect(
                    GUTTER_W,
                    y,
                    max(0.0, layout.width - GUTTER_W),
                    row_h,
                    fill=_BLACK_ROW_SHADE,
                    tags=("row-shade",),
                )
                bw = GUTTER_W * _BLACK_GUTTER_RATIO
                ops.rect(0.0, y, bw, row_h, fill=_GUTTER_BLACK, tags=("gutter", "gutter-key"))
            else:
                ops.rect(
                    0.0,
                    y,
                    GUTTER_W,
                    row_h,
                    fill=_GUTTER_WHITE,
                    outline=_GUTTER_BORDER,
                    tags=("gutter", "gutter-key"),
                )

            if pc == 0:
                is_c4 = note == 60
                ops.line(
                    [(GUTTER_W, y), (layout.width, y)],
                    fill=_GUIDE_C4 if is_c4 else _GUIDE_C,
                    width=1.5 if is_c4 else 1.0,
                    tags=("guide-c",),
                )
                octave = note // 12 - 1
                ops.text(
                    3.0,
                    y + row_h / 2.0,
                    f"C{octave}",
                    anchor="w",
                    size=8,
                    fill=_INK,
                    tags=("gutter", "label"),
                )

        chords = song.chords
        prev_bar: Optional[int] = None
        for index, slot in enumerate(layout.slots):
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"

            if index > 0 and chord.bar != prev_bar:
                ops.line(
                    [(slot.x, SYMBOL_H), (slot.x, layout.height)],
                    fill=_GRID,
                    width=1.5,
                    tags=(tag,),
                )
            prev_bar = chord.bar

            if chord.is_rest:
                continue

            cx = slot.x + slot.width / 2.0
            ops.text(
                cx,
                SYMBOL_H / 2.0,
                chord_symbol_label(chord),
                anchor="center",
                size=12,
                fill=_INK,
                bold=True,
                tags=(tag,),
            )

            self._paint_note_bars(ops, chord, slot, tag, row_h, y_of)

    def _paint_note_bars(
        self,
        ops: DrawOps,
        chord: RenderedChord,
        slot: SlotBox,
        tag: str,
        row_h: float,
        y_of,
    ) -> None:
        """Draw one horizontal bar per sounding note in ``chord``.

        Args:
            ops: Recorder to append draw ops to.
            chord: The chord being painted (already known not to be a rest).
            slot: The chord's slot.
            tag: The slot's shared hit-test tag.
            row_h: Row height in px, shared by every row.
            y_of: Row-top y position for a given MIDI note.
        """
        bar_x = slot.x + NOTE_PAD
        bar_w = max(1.0, slot.width - 2 * NOTE_PAD)
        bar_h = max(1.0, row_h - ROW_GAP)

        if chord.voice_notes is not None:
            for voice_index, note in enumerate(chord.voice_notes):
                color = VOICE_COLORS[voice_index % len(VOICE_COLORS)]
                ops.rect(
                    bar_x,
                    y_of(note),
                    bar_w,
                    bar_h,
                    fill=color,
                    outline=_INK,
                    width=0.5,
                    tags=(tag, f"voice:{voice_index}", f"note:{note}"),
                )
        elif chord.hand_split is not None and chord.midi_notes:
            hand_split = chord.hand_split
            for note_index, note in enumerate(chord.midi_notes):
                hand = "lh" if note_index < hand_split else "rh"
                ops.rect(
                    bar_x,
                    y_of(note),
                    bar_w,
                    bar_h,
                    fill=HAND_COLORS[hand],
                    outline=_INK,
                    width=0.5,
                    tags=(tag, f"hand:{hand}", f"note:{note}"),
                )
        elif chord.midi_notes:
            for note in chord.midi_notes:
                ops.rect(
                    bar_x,
                    y_of(note),
                    bar_w,
                    bar_h,
                    fill=NOTE_INK,
                    outline=_INK,
                    width=0.5,
                    tags=(tag, f"note:{note}"),
                )

"""Grand-staff chord-sheet renderer: each chord as whole notes on a grand staff.

:class:`StaffCardRenderer` draws one uniform-width card per sounding chord --
the chord symbol at the top, then a grand staff (treble over bass, joined by a
left barline) with every voiced note as a stemless **whole note** (a hollow
oval). Rests get a slim empty card, like
:class:`~ui.chord_sheet.name_card.NameCardRenderer`.

The renderer is a pure function of ``(ctx, height)`` per the
:class:`~ui.chord_sheet.renderer_interface.StripRenderer` contract: all
geometry derives from the card ``height`` (which fixes the staff-space size),
so ``layout`` and ``paint`` agree on card widths and note positions without
sharing state.

Musical detail:

- **Staff assignment.** Ensemble songs (``RenderedChord.voice_notes`` set) route
  each voice by ``RenderedSong.voice_staves`` (falling back to a middle-C split
  when absent). Piano songs (``hand_split`` set) put the left hand on the bass
  staff and the right on the treble. Everything else splits at middle C
  (MIDI >= 60 -> treble).
- **Vertical placement is diatonic, from spelling, not raw MIDI.** A note's
  letter comes from the chord's parser note names (matched by pitch class) so a
  ``Bb`` sits on the B line with a flat and an ``F#`` on the F position with a
  sharp; unmatched pitch classes default to the sharp spelling. The octave is
  derived from the spelling so it reproduces the MIDI note even across the
  enharmonic seam (``B#3`` = MIDI 60, ``Cb5`` = MIDI 71).
- **Accidentals** are ``sharp``/``flat`` glyphs (present in normal fonts) drawn
  just left of the notehead; no naturals are needed since each card is
  context-free.
- **Ledger lines** are added above/below each staff as the note requires; a
  middle C between the staves gets exactly one.
- **Seconds collide:** two notes a diatonic step apart on the same staff offset
  the upper notehead one notehead-width to the right; a run of stacked seconds
  alternates sides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Tuple

from chord.midi_converter import parse_note_to_semitone
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.clef_assets import clef_placement
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    SheetContext,
    chord_symbol_label,
    SlotBox,
    StripLayout,
    StripRenderer,
)

# --- Strip layout constants (px) ------------------------------------------
#: Horizontal gap between adjacent cards.
CARD_GAP = 8.0
#: Leading/trailing padding at the strip's left and right edges.
STRIP_MARGIN = 12.0
#: Width of a rest's slim card (deliberately narrow, like the name card).
REST_WIDTH = 30.0

# --- Staff-space sizing ----------------------------------------------------
#: Card height is divided into this many staff-space units (10 for the grand
#: staff span F5..G2, ~2 ledger units above and below, plus the chord-symbol
#: band and outer padding); the staff space is ``height / this``.
_HEIGHT_UNITS = 19.0
_MIN_STAFF_SPACE = 4.0
_MAX_STAFF_SPACE = 16.0

# --- Colors / stroke (module-local; no edits to constants.py) --------------
_INK = "#22323a"
_STAFF_LINE = "#7c8b96"
_CARD_FILL = "#f6f8fb"
_CARD_OUTLINE = "#c2ccd6"
_REST_FILL = "#e9ebef"

# --- Diatonic tables -------------------------------------------------------
#: Letter -> its ordinal within an octave (C=0 .. B=6), for diatonic indexing.
_LETTER_VALUE = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}
#: Letter -> its natural semitone within an octave.
_LETTER_SEMITONE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
#: Default (letter, accidental) per pitch class, sharp convention.
_SHARP_SPELLING: Tuple[Tuple[str, int], ...] = (
    ('C', 0), ('C', 1), ('D', 0), ('D', 1), ('E', 0), ('F', 0),
    ('F', 1), ('G', 0), ('G', 1), ('A', 0), ('A', 1), ('B', 0),
)
#: Diatonic index of E4 (the treble staff's bottom line), the vertical anchor.
_E4_INDEX = 4 * 7 + _LETTER_VALUE['E']


def _diatonic_index(letter: str, octave: int) -> int:
    """Absolute diatonic step index of ``letter`` in ``octave`` (C4 -> 28)."""
    return octave * 7 + _LETTER_VALUE[letter]


def _accidental_offset(name: str) -> int:
    """Signed accidental total of a note name's tail (``#`` +1, ``b``/``-`` -1)."""
    offset = 0
    for ch in name[1:]:
        if ch == '#':
            offset += 1
        elif ch in ('b', '-'):
            offset -= 1
    return offset


def _match_letter(pc: int, chord_notes) -> Tuple[str, int]:
    """Return the ``(letter, accidental_offset)`` spelling a pitch class ``pc``.

    Prefers a name from the chord's parser spelling (``notes``, then
    ``bass_note``, then ``root``) whose pitch class matches ``pc`` -- so a
    ``Bb`` keeps its B-with-flat spelling and an ``F#`` its F-with-sharp. Falls
    back to the sharp spelling for a pitch class the chord doesn't name.
    """
    if chord_notes is not None:
        candidates: List[str] = list(chord_notes.notes or [])
        if chord_notes.bass_note:
            candidates.append(chord_notes.bass_note)
        if chord_notes.root:
            candidates.append(chord_notes.root)
        for name in candidates:
            if not name:
                continue
            if parse_note_to_semitone(name) == pc and name[0].upper() in _LETTER_VALUE:
                return name[0].upper(), _accidental_offset(name)
    return _SHARP_SPELLING[pc % 12]


def _spell(midi: int, chord_notes) -> Tuple[str, int, int]:
    """Spell a MIDI note as ``(letter, accidental_offset, diatonic_index)``.

    The letter/accidental come from :func:`_match_letter`; the octave is derived
    so ``letter+accidental`` reproduces ``midi`` exactly, which handles the
    enharmonic seam (``B#3`` = 60 lands on the B position below middle C;
    ``Cb5`` = 71 lands on the C5 position with a flat).
    """
    pc = midi % 12
    letter, acc = _match_letter(pc, chord_notes)
    natural = _LETTER_SEMITONE[letter] + acc
    octave = (midi - natural) // 12 - 1
    return letter, acc, _diatonic_index(letter, octave)


def _accidental_text(acc: int) -> str:
    """Render an accidental offset as sharp/flat glyphs (empty for natural)."""
    if acc > 0:
        return '♯' * acc
    if acc < 0:
        return '♭' * (-acc)
    return ''


class _Note(NamedTuple):
    """One resolved notehead: its staff, spelling glyph, and diatonic position."""

    midi: int
    staff: str            # 'treble' | 'bass'
    accidental: str       # sharp/flat glyphs, or ''
    diatonic_index: int


@dataclass(frozen=True)
class _Geometry:
    """Vertical/horizontal geometry for a card, all derived from ``height``."""

    staff_space: float
    y_symbol: float       # top y for the chord symbol band
    treble_top: float     # y of the treble top line (F5)
    x_barline: float      # card-relative x of the joining barline
    x_clef: float         # card-relative left x of the clefs
    clef_col_w: float     # width reserved for the clef column
    x_note: float         # card-relative center x of the note column
    notehead_w: float
    notehead_h: float
    card_width: float
    staff_line_w: float
    note_line_w: float

    def bass_top(self) -> float:
        """y of the bass top line (A3): six staff spaces below the treble top."""
        return self.treble_top + 6.0 * self.staff_space

    def y_for_index(self, diatonic_index: int) -> float:
        """y of a note by diatonic index (E4 sits on the treble bottom line)."""
        s = self.staff_space
        return self.treble_top + 4.0 * s + (_E4_INDEX - diatonic_index) * (s / 2.0)


def _staff_space(height: float) -> float:
    """Staff-space size (line-to-line gap) for a card of the given height."""
    return max(_MIN_STAFF_SPACE, min(_MAX_STAFF_SPACE, height / _HEIGHT_UNITS))


def _geometry(height: float) -> _Geometry:
    """Compute the full card geometry from ``height`` (pure, deterministic)."""
    s = _staff_space(height)

    top_pad = 0.6 * s
    symbol_h = 2.2 * s
    ledger_above = 2.0 * s
    ledger_below = 2.0 * s
    grand_h = 10.0 * s  # F5 (treble top) down to G2 (bass bottom)

    block_h = symbol_h + ledger_above + grand_h + ledger_below
    y_content_top = max(top_pad, (height - block_h) / 2.0)
    y_symbol = y_content_top
    treble_top = y_content_top + symbol_h + ledger_above

    notehead_w = 1.5 * s
    notehead_h = 1.0 * s

    left_pad = 0.9 * s
    clef_gap = 0.5 * s
    note_gap = 0.7 * s
    acc_room = 1.3 * s
    collision_room = notehead_w
    right_pad = 0.9 * s

    treble_w = float(clef_placement('treble', s).width)
    bass_w = float(clef_placement('bass', s).width)
    clef_col_w = max(treble_w, bass_w)

    x_barline = left_pad
    x_clef = x_barline + clef_gap
    x_note = x_clef + clef_col_w + note_gap + acc_room + notehead_w / 2.0
    card_width = x_note + notehead_w / 2.0 + collision_room + right_pad

    return _Geometry(
        staff_space=s,
        y_symbol=y_symbol,
        treble_top=treble_top,
        x_barline=x_barline,
        x_clef=x_clef,
        clef_col_w=clef_col_w,
        x_note=x_note,
        notehead_w=notehead_w,
        notehead_h=notehead_h,
        card_width=card_width,
        staff_line_w=max(1.0, 0.06 * s),
        note_line_w=max(1.0, 0.12 * s),
    )


def _note_staves(chord: RenderedChord, song: RenderedSong) -> List[Tuple[int, str]]:
    """Return ``(midi, staff)`` for every drawn note of a sounding chord.

    Ensemble chords route each voice by ``song.voice_staves`` (falling back to a
    middle-C split when it is absent); piano chords split at ``hand_split`` (LH
    -> bass, RH -> treble); everything else splits at middle C. Duplicate
    ``(midi, staff)`` pairs (unison voices) are collapsed so noteheads don't
    stack exactly.
    """
    pairs: List[Tuple[int, str]] = []
    if chord.voice_notes is not None:
        staves = song.voice_staves
        for i, midi in enumerate(chord.voice_notes):
            if staves is not None and i < len(staves):
                staff = staves[i]
            else:
                staff = 'treble' if midi >= 60 else 'bass'
            pairs.append((midi, staff))
    elif chord.hand_split is not None and chord.midi_notes is not None:
        for i, midi in enumerate(chord.midi_notes):
            pairs.append((midi, 'bass' if i < chord.hand_split else 'treble'))
    else:
        for midi in (chord.midi_notes or []):
            pairs.append((midi, 'treble' if midi >= 60 else 'bass'))

    seen = set()
    unique: List[Tuple[int, str]] = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return unique


def _resolve_notes(chord: RenderedChord, song: RenderedSong) -> List[_Note]:
    """Resolve a chord's drawn notes to spelled :class:`_Note` records."""
    notes: List[_Note] = []
    for midi, staff in _note_staves(chord, song):
        _letter, acc, idx = _spell(midi, chord.chord_notes)
        notes.append(_Note(midi, staff, _accidental_text(acc), idx))
    return notes


def _collision_offsets(notes: List[_Note]) -> dict:
    """Map each note (by identity index) to a horizontal notehead-width offset.

    Notes on the same staff a single diatonic step apart (a second) can't share
    a column, so the upper of the pair is pushed one notehead-width right; a run
    of stacked seconds alternates back and forth. Keyed by ``id(note)``.
    """
    offsets: dict = {}
    for staff in ('treble', 'bass'):
        staff_notes = sorted(
            (n for n in notes if n.staff == staff),
            key=lambda n: n.diatonic_index,
        )
        prev_idx: Optional[int] = None
        prev_off = 0
        for note in staff_notes:
            if prev_idx is not None and note.diatonic_index - prev_idx == 1:
                off = 0 if prev_off == 1 else 1
            else:
                off = 0
            offsets[id(note)] = off
            prev_idx = note.diatonic_index
            prev_off = off
    return offsets


class StaffCardRenderer(StripRenderer):
    """Draw each chord as whole notes on a grand staff (rests slim and empty)."""

    id = "staff"
    label = "Staff"
    requires_fingering = False

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay uniform grand-staff cards left to right (rests slim).

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord in song order.
        """
        geom = _geometry(height)
        slots: List[SlotBox] = []
        x = STRIP_MARGIN
        for index, chord in enumerate(ctx.song.chords):
            width = REST_WIDTH if chord.is_rest else geom.card_width
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width + CARD_GAP

        content_width = (x - CARD_GAP + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Emit the grand staff, clefs, and whole notes for every slot.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        song = ctx.song
        chords = song.chords
        geom = _geometry(layout.height)

        for slot in layout.slots:
            chord = chords[slot.chord_index]
            tag = f"slot:{slot.chord_index}"
            if chord.is_rest:
                self._paint_rest(ops, slot, layout.height, tag)
            else:
                self._paint_card(ops, slot, geom, chord, song, tag)

    # -- Rest ---------------------------------------------------------------

    def _paint_rest(self, ops: DrawOps, slot: SlotBox, height: float, tag: str) -> None:
        """Draw a slim empty card for a rest (mirrors the name card)."""
        vmargin = min(12.0, height / 4.0)
        card_h = max(1.0, height - 2 * vmargin)
        ops.rect(
            slot.x, vmargin, slot.width, card_h,
            fill=_REST_FILL, outline=_CARD_OUTLINE, width=1.0, tags=(tag,),
        )

    # -- Sounding chord -----------------------------------------------------

    def _paint_card(self, ops: DrawOps, slot: SlotBox, geom: _Geometry,
                    chord: RenderedChord, song: RenderedSong, tag: str) -> None:
        """Draw one grand-staff card: background, symbol, staves, clefs, notes."""
        x0 = slot.x
        s = geom.staff_space

        # Background card (opaque light fill; the playhead highlight shows in the
        # vertical bands the card does not cover).
        top = min(0.4 * s, geom.y_symbol)
        card_h = max(1.0, geom.bass_top() + 4.0 * s + 2.0 * s - top)
        ops.rect(
            x0, top, slot.width, card_h,
            fill=_CARD_FILL, outline=_CARD_OUTLINE, width=1.0, tags=(tag,),
        )

        # Chord symbol.
        ops.text(
            x0 + slot.width / 2.0, geom.y_symbol,
            chord_symbol_label(chord),
            anchor="n", size=max(8, int(round(1.3 * s))),
            fill=_INK, bold=True, tags=(tag,),
        )

        self._paint_staves(ops, x0, slot.width, geom, tag)
        self._paint_clefs(ops, x0, geom, tag)

        notes = _resolve_notes(chord, song)
        self._paint_notes(ops, x0, geom, notes, tag)

    def _paint_staves(self, ops: DrawOps, x0: float, width: float,
                      geom: _Geometry, tag: str) -> None:
        """Draw the two 5-line staves and the joining left barline."""
        s = geom.staff_space
        x_left = x0 + geom.x_barline
        x_right = x0 + width - 0.9 * s
        for base in (geom.treble_top, geom.bass_top()):
            for k in range(5):
                y = base + k * s
                ops.line([(x_left, y), (x_right, y)],
                         fill=_STAFF_LINE, width=geom.staff_line_w, tags=(tag,))
        # Barline from treble top line to bass bottom line.
        ops.line(
            [(x_left, geom.treble_top), (x_left, geom.bass_top() + 4.0 * s)],
            fill=_STAFF_LINE, width=geom.staff_line_w, tags=(tag,),
        )

    def _paint_clefs(self, ops: DrawOps, x0: float, geom: _Geometry, tag: str) -> None:
        """Emit clef image ops registered to each staff's reference line."""
        s = geom.staff_space
        # Treble G-clef: reference line is G4 (2nd line from the bottom).
        treble = clef_placement('treble', s)
        g4_y = geom.y_for_index(_diatonic_index('G', 4))
        ops.image(x0 + geom.x_clef, g4_y - treble.baseline_y, treble.key,
                  anchor="nw", tags=(tag,))
        # Bass F-clef: reference line is F3 (2nd line from the top).
        bass = clef_placement('bass', s)
        f3_y = geom.y_for_index(_diatonic_index('F', 3))
        ops.image(x0 + geom.x_clef, f3_y - bass.baseline_y, bass.key,
                  anchor="nw", tags=(tag,))

    def _paint_notes(self, ops: DrawOps, x0: float, geom: _Geometry,
                     notes: List[_Note], tag: str) -> None:
        """Draw ledger lines, hollow whole-note ovals, and accidentals."""
        offsets = _collision_offsets(notes)
        for note in notes:
            y = geom.y_for_index(note.diatonic_index)
            off = offsets.get(id(note), 0) * geom.notehead_w
            cx = x0 + geom.x_note + off

            self._paint_ledgers(ops, cx, y, note.staff, geom, tag)

            left = cx - geom.notehead_w / 2.0
            ops.oval(
                left, y - geom.notehead_h / 2.0, geom.notehead_w, geom.notehead_h,
                fill=None, outline=_INK, width=geom.note_line_w, tags=(tag,),
            )
            if note.accidental:
                ops.text(
                    left - 0.25 * geom.staff_space, y,
                    note.accidental,
                    anchor="e", size=max(8, int(round(1.7 * geom.staff_space))),
                    fill=_INK, tags=(tag,),
                )

    def _paint_ledgers(self, ops: DrawOps, cx: float, y: float, staff: str,
                       geom: _Geometry, tag: str) -> None:
        """Draw ledger lines between a notehead and the lines of its staff."""
        s = geom.staff_space
        top = geom.treble_top if staff == 'treble' else geom.bass_top()
        bottom = top + 4.0 * s
        half = geom.notehead_w * 0.75
        eps = 0.25 * s

        positions: List[float] = []
        # Above the staff top line.
        k = 1
        while True:
            p = top - k * s
            if p < y - eps:
                break
            positions.append(p)
            k += 1
        # Below the staff bottom line.
        k = 1
        while True:
            p = bottom + k * s
            if p > y + eps:
                break
            positions.append(p)
            k += 1

        for p in positions:
            ops.line([(cx - half, p), (cx + half, p)],
                     fill=_INK, width=geom.note_line_w, tags=(tag,))

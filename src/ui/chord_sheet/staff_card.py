"""Grand-staff chord-sheet renderer: one continuous engraved grand staff.

:class:`StaffCardRenderer` draws the whole song as a single continuous grand
staff -- two 5-line staves (treble over bass) spanning the full strip width,
joined at the left by a barline. Each sounding chord contributes its voiced
notes as stemless **whole notes** (Bravura noteheads) at a duration-proportional
slot; the chord symbol sits in a band above the treble staff. This replaces the
old one-card-per-chord layout with a continuous lane like the tab view.

The renderer stays a pure function of ``(ctx, height)`` per the
:class:`~ui.chord_sheet.renderer_interface.StripRenderer` contract: all vertical
geometry derives from ``height`` (which fixes the staff-space size) and all
horizontal geometry from the song's durations/keys, so ``layout`` and ``paint``
agree without sharing state.

Engraving detail:

- **Glyphs are Bravura images, not hand-drawn shapes.** Noteheads and
  accidentals come from :func:`~ui.chord_sheet.clef_assets.glyph_placement`
  (embedded, SMuFL-registered PNGs), tinted per voice/hand.
- **Wide staff gap.** The two staves are separated by more than three staff
  spaces so they never read as merged at middle C; a middle C gets its single
  ledger line clearly in the gap.
- **Vertical placement is diatonic, from spelling, not raw MIDI.** A note's
  letter comes from the chord's parser note names (matched by pitch class) so a
  ``Bb`` sits on the B line and an ``F#`` on the F position; the octave is
  derived from the spelling so it reproduces the MIDI note across the enharmonic
  seam (``B#3`` = 60, ``Cb5`` = 71). Each staff maps diatonic index by its own
  anchor (E4 on the treble bottom line; A3 on the bass top line).
- **Key signatures.** ``RenderedChord.key`` drives a key signature drawn right
  after the clefs, and again -- preceded by a thin double barline -- wherever
  the key changes chord-to-chord. Sharps/flats use the circle of fifths (minor
  keys via their relative major); unmappable keys draw no signature.
- **Accidentals are relative to the signature.** A note only gets an accidental
  glyph when its spelling deviates from the signature: F# in G major draws
  nothing, F natural in G major draws a natural. There is **no bar-carryover
  memory** -- every chord is annotated independently against the signature (a
  deliberate simplification). Double sharps/flats fall back to text.
- **Voice color coding.** Ensemble chords (``voice_notes``) tint each voice's
  notehead/accidental by ``VOICE_COLORS[voice_index]``; piano chords
  (``hand_split``) tint the left hand and right hand by ``HAND_COLORS``;
  everything else uses ``NOTE_INK``. A legend (when ``voice_labels`` is set) is
  drawn at the far left.
- **Ledger lines** are added above/below each staff as needed; **seconds**
  (two notes a diatonic step apart on one staff) offset the upper notehead one
  notehead-width to the right, alternating in a stacked run.
- Bass key-signature accidentals are placed two octaves below the treble
  letters (standard engraving on the bass staff), not one -- the latter would
  place them above the bass staff.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional, Tuple

from chord.midi_converter import parse_note_to_semitone
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.clef_assets import clef_placement, glyph_placement
from ui.chord_sheet.ops import DrawOps
from ui.chord_sheet.renderer_interface import (
    HAND_COLORS,
    NOTE_INK,
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
    VOICE_COLORS,
    chord_symbol_label,
)
# Duration->width constants are shared with the tab lane so both continuous
# views scale time identically.
from ui.chord_sheet.tab_strip import (
    MAX_SLOT_WIDTH,
    MIN_SLOT_WIDTH,
    PX_PER_BEAT,
)

logger = logging.getLogger(__name__)

# --- Strip layout constants (px) ------------------------------------------
#: Leading/trailing padding at the strip's left and right edges.
STRIP_MARGIN = 12.0
#: Width of a rest's slim slot (a gap where nothing is drawn).
REST_WIDTH = 18.0

# --- Staff-space sizing ----------------------------------------------------
#: Lane height is divided into this many staff-space units; the staff space is
#: ``height / this`` (clamped). Budget: top pad (0.6) + symbol band (2.2) +
#: ledger above (2) + treble (4) + inter-staff gap (3.5) + bass (4) + ledger
#: below (2) + bottom pad (0.6).
_HEIGHT_UNITS = 18.9
_MIN_STAFF_SPACE = 4.0
_MAX_STAFF_SPACE = 16.0
#: Vertical gap between the treble bottom line and the bass top line, in staff
#: spaces (> 3 so the staves never read as merged; middle C's ledger sits here).
_GAP_SPACES = 3.5

# --- Colors / stroke (module-local; no edits to constants.py) --------------
_INK = NOTE_INK
_STAFF_LINE = "#7c8b96"

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
#: Diatonic index of E4 (the treble staff's bottom line) and A3 (the bass
#: staff's top line): the per-staff vertical anchors.
_E4_INDEX = 4 * 7 + _LETTER_VALUE['E']
_A3_INDEX = 3 * 7 + _LETTER_VALUE['A']

# --- Key-signature tables --------------------------------------------------
#: Major key -> position on the circle of fifths (+ sharps / - flats).
_MAJOR_FIFTHS: Dict[str, int] = {
    'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
    'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
}
#: Minor key -> circle-of-fifths position (via its relative major).
_MINOR_FIFTHS: Dict[str, int] = {
    'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
    'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5, 'Ebm': -6, 'Abm': -7,
}
#: Order of sharps (F C G D A E B) with their treble-clef octaves.
_SHARP_ORDER: Tuple[Tuple[str, int], ...] = (
    ('F', 5), ('C', 5), ('G', 5), ('D', 5), ('A', 4), ('E', 5), ('B', 4),
)
#: Order of flats (B E A D G C F) with their treble-clef octaves.
_FLAT_ORDER: Tuple[Tuple[str, int], ...] = (
    ('B', 4), ('E', 5), ('A', 4), ('D', 5), ('G', 4), ('C', 5), ('F', 4),
)
#: Bass key-signature accidentals sit this many octaves below the treble
#: letters (two -> standard bass-clef positions on the staff).
_BASS_SIG_OCTAVE_DROP = 2


# --------------------------------------------------------------------------
# Spelling
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Key signatures
# --------------------------------------------------------------------------

def _key_fifths(key: Optional[str]) -> Optional[int]:
    """Circle-of-fifths position for ``key`` (+sharps/-flats), or ``None``.

    Minor keys resolve through their relative major. An unknown/unmappable key
    (or ``None``) yields ``None`` and logs at debug -- no signature is drawn.
    """
    if not key:
        return None
    k = key.strip()
    if k in _MINOR_FIFTHS:
        return _MINOR_FIFTHS[k]
    if k in _MAJOR_FIFTHS:
        return _MAJOR_FIFTHS[k]
    logger.debug("No key signature mapping for key %r", key)
    return None


class _SigEntry(NamedTuple):
    """One key-signature accidental: its glyph kind and per-clef positions."""

    kind: str              # 'sharp' | 'flat'
    letter: str
    treble_octave: int
    bass_octave: int


def _signature_entries(fifths: Optional[int]) -> List[_SigEntry]:
    """Ordered accidentals of a key signature (empty for 0/None)."""
    if not fifths:
        return []
    if fifths > 0:
        order, kind = _SHARP_ORDER[:fifths], 'sharp'
    else:
        order, kind = _FLAT_ORDER[:(-fifths)], 'flat'
    return [
        _SigEntry(kind, letter, octv, octv - _BASS_SIG_OCTAVE_DROP)
        for letter, octv in order
    ]


def _signature_letter_map(fifths: Optional[int]) -> Dict[str, int]:
    """Letter -> the accidental the signature applies to it (+1/-1)."""
    out: Dict[str, int] = {}
    for entry in _signature_entries(fifths):
        out[entry.letter] = 1 if entry.kind == 'sharp' else -1
    return out


def _accidental_kind(letter: str, acc: int, sig_map: Dict[str, int]) -> Optional[str]:
    """Accidental glyph a note needs given the signature, or ``None``.

    Only a spelling that *deviates* from the signature is annotated: a natural
    where the signature raises/lowers the letter, or a sharp/flat where the
    signature does not. Returns ``'sharp'``/``'flat'``/``'natural'``, ``'text'``
    for double accidentals (rare fallback), or ``None`` for no glyph.
    """
    expected = sig_map.get(letter, 0)
    if acc == expected:
        return None
    if acc == 0:
        return 'natural'
    if acc == 1:
        return 'sharp'
    if acc == -1:
        return 'flat'
    return 'text'


# --------------------------------------------------------------------------
# Resolved notes
# --------------------------------------------------------------------------

class _Note(NamedTuple):
    """One resolved notehead: staff, spelling, diatonic position, and color."""

    midi: int
    staff: str            # 'treble' | 'bass'
    letter: str
    acc: int
    diatonic_index: int
    color: str


def _voiced(chord: RenderedChord, song: RenderedSong) -> List[Tuple[int, str, str]]:
    """Return ``(midi, staff, color)`` for every drawn note of a chord.

    Ensemble chords iterate ``voice_notes`` low-to-high (one entry per voice,
    **not** the deduped ``midi_notes``), routed by ``song.voice_staves`` and
    tinted by ``VOICE_COLORS[voice_index]`` (wrapping). Piano chords split
    ``midi_notes`` at ``hand_split`` (left hand -> bass/``lh`` color, right hand
    -> treble/``rh`` color). Everything else splits at middle C with the default
    ink.
    """
    if chord.voice_notes is not None:
        staves = song.voice_staves
        out: List[Tuple[int, str, str]] = []
        for i, midi in enumerate(chord.voice_notes):
            if staves is not None and i < len(staves):
                staff = staves[i]
            else:
                staff = 'treble' if midi >= 60 else 'bass'
            out.append((midi, staff, VOICE_COLORS[i % len(VOICE_COLORS)]))
        return out
    if chord.hand_split is not None and chord.midi_notes is not None:
        out = []
        for i, midi in enumerate(chord.midi_notes):
            if i < chord.hand_split:
                out.append((midi, 'bass', HAND_COLORS['lh']))
            else:
                out.append((midi, 'treble', HAND_COLORS['rh']))
        return out
    return [
        (midi, 'treble' if midi >= 60 else 'bass', _INK)
        for midi in (chord.midi_notes or [])
    ]


def _resolve_notes(chord: RenderedChord, song: RenderedSong) -> List[_Note]:
    """Resolve a chord's drawn notes to spelled :class:`_Note` records."""
    notes: List[_Note] = []
    for midi, staff, color in _voiced(chord, song):
        letter, acc, idx = _spell(midi, chord.chord_notes)
        notes.append(_Note(midi, staff, letter, acc, idx, color))
    return notes


def _collision_offsets(notes: List[_Note]) -> Dict[int, int]:
    """Map each note (by ``id``) to a horizontal notehead-width offset.

    Notes on the same staff a single diatonic step apart (a second) can't share
    a column, so the upper of the pair is pushed one notehead-width right; a run
    of stacked seconds alternates back and forth.
    """
    offsets: Dict[int, int] = {}
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


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Geometry:
    """Vertical geometry for the whole lane, all derived from ``height``."""

    staff_space: float
    y_symbol: float       # top y of the chord-symbol band
    symbol_h: float
    treble_top: float     # y of the treble top line (F5)
    bass_top: float       # y of the bass top line (A3)
    staff_line_w: float
    note_line_w: float

    def treble_bottom(self) -> float:
        """y of the treble bottom line (E4)."""
        return self.treble_top + 4.0 * self.staff_space

    def bass_bottom(self) -> float:
        """y of the bass bottom line (G2)."""
        return self.bass_top + 4.0 * self.staff_space

    def y_for_index(self, diatonic_index: int, staff: str) -> float:
        """y of a diatonic index on a staff (E4 on treble bottom, A3 on bass top)."""
        half = self.staff_space / 2.0
        if staff == 'treble':
            return self.treble_bottom() + (_E4_INDEX - diatonic_index) * half
        return self.bass_top + (_A3_INDEX - diatonic_index) * half


def _staff_space(height: float) -> float:
    """Staff-space size (line-to-line gap) for a lane of the given height."""
    return max(_MIN_STAFF_SPACE, min(_MAX_STAFF_SPACE, height / _HEIGHT_UNITS))


def _geometry(height: float) -> _Geometry:
    """Compute the lane's vertical geometry from ``height`` (pure)."""
    s = _staff_space(height)

    top_pad = 0.6 * s
    symbol_h = 2.2 * s
    ledger_above = 2.0 * s

    block_h = (top_pad + symbol_h + ledger_above + 4.0 * s
               + _GAP_SPACES * s + 4.0 * s + 2.0 * s + 0.6 * s)
    y_top = max(0.0, (height - block_h) / 2.0)

    y_symbol = y_top + top_pad
    treble_top = y_symbol + symbol_h + ledger_above
    bass_top = treble_top + 4.0 * s + _GAP_SPACES * s

    return _Geometry(
        staff_space=s,
        y_symbol=y_symbol,
        symbol_h=symbol_h,
        treble_top=treble_top,
        bass_top=bass_top,
        staff_line_w=max(1.0, 0.06 * s),
        note_line_w=max(1.0, 0.10 * s),
    )


# --- Horizontal helpers ----------------------------------------------------

#: Spacing (in staff spaces) used for the clef/key-signature header and slots.
_CLEF_PAD_LEFT = 0.6
_CLEF_SIG_GAP = 0.7
_SIG_GLYPH_GAP = 0.35
_SIG_NOTES_GAP = 1.0
#: Double-barline room before a mid-song key change (staff spaces).
_KEY_CHANGE_PAD = 1.4


def _slot_width(chord: RenderedChord) -> float:
    """Slot width: slim for rests, else duration-proportional (clamped)."""
    if chord.is_rest:
        return REST_WIDTH
    return max(MIN_SLOT_WIDTH, min(MAX_SLOT_WIDTH, chord.duration_beats * PX_PER_BEAT))


def _signature_width(fifths: Optional[int], s: float) -> float:
    """Total px width of a key signature's accidental glyphs (0 if empty)."""
    total = 0.0
    for entry in _signature_entries(fifths):
        w = glyph_placement('accidental_' + entry.kind, s).width
        total += w + _SIG_GLYPH_GAP * s
    return total


def _key_change_lead(fifths: Optional[int], s: float) -> float:
    """Horizontal room a mid-song key change consumes before the next slot."""
    return _KEY_CHANGE_PAD * s + _signature_width(fifths, s)


def _header_geometry(song: RenderedSong, s: float) -> Tuple[float, float, float]:
    """Return ``(x_clef, x_sig, x_slots)`` for the clef + initial-signature header."""
    clef_w = max(
        clef_placement('treble', s).width,
        clef_placement('bass', s).width,
    )
    x_clef = STRIP_MARGIN + _CLEF_PAD_LEFT * s
    x_sig = x_clef + clef_w + _CLEF_SIG_GAP * s
    fifths0 = _key_fifths(song.chords[0].key) if song.chords else None
    x_slots = x_sig + _signature_width(fifths0, s) + _SIG_NOTES_GAP * s
    return x_clef, x_sig, x_slots


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------

class StaffCardRenderer(StripRenderer):
    """Draw the song as one continuous grand staff with Bravura glyphs."""

    id = "staff"
    label = "Staff"
    requires_fingering = False

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay slots left to right, width proportional to duration.

        Slots begin after the clef + initial-signature header; a chord whose key
        differs from the previous chord's reserves extra lead width for a double
        barline and a new signature.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord in song order (rests
            as slim gaps).
        """
        song = ctx.song
        s = _staff_space(height)
        _, _, x = _header_geometry(song, s)

        prev_fifths = _key_fifths(song.chords[0].key) if song.chords else None
        slots: List[SlotBox] = []
        for index, chord in enumerate(song.chords):
            if index > 0:
                fifths = _key_fifths(chord.key)
                if fifths != prev_fifths:
                    x += _key_change_lead(fifths, s)
                    prev_fifths = fifths
            width = _slot_width(chord)
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width

        content_width = (x + STRIP_MARGIN) if slots else (2 * STRIP_MARGIN)
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Emit the grand staff, clefs, signatures, and whole notes.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        song = ctx.song
        chords = song.chords
        geom = _geometry(layout.height)
        s = geom.staff_space

        x_left = STRIP_MARGIN
        x_right = max(x_left + 1.0, layout.width - STRIP_MARGIN)
        self._paint_staff_lines(ops, geom, x_left, x_right)

        x_clef, x_sig, _ = _header_geometry(song, s)
        self._paint_clefs(ops, x_clef, geom)
        fifths0 = _key_fifths(chords[0].key) if chords else None
        self._paint_signature(ops, x_sig, fifths0, geom, ("header",))
        if song.voice_labels:
            self._paint_legend(ops, song.voice_labels, geom)

        prev_fifths = fifths0
        prev_bar: Optional[int] = None
        for slot in layout.slots:
            index = slot.chord_index
            chord = chords[index]
            tag = f"slot:{index}"

            if index > 0:
                fifths = _key_fifths(chord.key)
                if fifths != prev_fifths:
                    lead = _key_change_lead(fifths, s)
                    self._paint_key_change(ops, slot.x - lead, fifths, geom, tag)
                    prev_fifths = fifths
                elif chord.bar != prev_bar and not chord.is_rest:
                    ops.line(
                        [(slot.x, geom.treble_top), (slot.x, geom.bass_bottom())],
                        fill=_STAFF_LINE, width=geom.staff_line_w, tags=(tag,),
                    )
            prev_bar = chord.bar

            if chord.is_rest:
                continue  # slim gap: staff lines already span underneath

            self._paint_symbol(ops, slot, chord, geom, tag)
            self._paint_notes(ops, slot, chord, song, geom, tag)

    # -- Staff / clefs ------------------------------------------------------

    def _paint_staff_lines(self, ops: DrawOps, geom: _Geometry,
                           x_left: float, x_right: float) -> None:
        """Draw the two 5-line staves and the joining left barline."""
        s = geom.staff_space
        for base in (geom.treble_top, geom.bass_top):
            for k in range(5):
                y = base + k * s
                ops.line([(x_left, y), (x_right, y)],
                         fill=_STAFF_LINE, width=geom.staff_line_w, tags=("staff",))
        ops.line(
            [(x_left, geom.treble_top), (x_left, geom.bass_bottom())],
            fill=_STAFF_LINE, width=geom.staff_line_w, tags=("staff",),
        )

    def _paint_clefs(self, ops: DrawOps, x_clef: float, geom: _Geometry) -> None:
        """Emit clef images registered to each staff's reference line."""
        treble = clef_placement('treble', geom.staff_space)
        g4_y = geom.y_for_index(_diatonic_index('G', 4), 'treble')
        ops.image(x_clef, g4_y - treble.baseline_y, treble.key,
                  anchor="nw", tags=("header",))
        bass = clef_placement('bass', geom.staff_space)
        f3_y = geom.y_for_index(_diatonic_index('F', 3), 'bass')
        ops.image(x_clef, f3_y - bass.baseline_y, bass.key,
                  anchor="nw", tags=("header",))

    def _paint_legend(self, ops: DrawOps, labels: List[str], geom: _Geometry) -> None:
        """Draw a tiny stacked voice legend at the far left, each in its color."""
        s = geom.staff_space
        size = max(6, int(round(0.85 * s)))
        line_h = size + 2.0
        y = geom.y_symbol
        for i, label in enumerate(labels):
            ops.text(
                STRIP_MARGIN + 1.0, y + i * line_h, label,
                anchor="nw", size=size,
                fill=VOICE_COLORS[i % len(VOICE_COLORS)], tags=("legend",),
            )

    # -- Key signatures -----------------------------------------------------

    def _paint_signature(self, ops: DrawOps, x_start: float, fifths: Optional[int],
                         geom: _Geometry, tags: Tuple[str, ...]) -> None:
        """Draw a key signature's accidentals on both staves from ``x_start``."""
        s = geom.staff_space
        x = x_start
        for entry in _signature_entries(fifths):
            name = 'accidental_' + entry.kind
            pl = glyph_placement(name, s)
            ty = geom.y_for_index(
                _diatonic_index(entry.letter, entry.treble_octave), 'treble')
            ops.image(x, ty - pl.origin_y, pl.key, anchor="nw", tags=tags)
            by = geom.y_for_index(
                _diatonic_index(entry.letter, entry.bass_octave), 'bass')
            ops.image(x, by - pl.origin_y, pl.key, anchor="nw", tags=tags)
            x += pl.width + _SIG_GLYPH_GAP * s

    def _paint_key_change(self, ops: DrawOps, x0: float, fifths: Optional[int],
                          geom: _Geometry, tag: str) -> None:
        """Draw a thin double barline then the new signature in the lead space."""
        s = geom.staff_space
        x1 = x0 + 0.2 * s
        x2 = x1 + 0.3 * s
        for xx in (x1, x2):
            ops.line([(xx, geom.treble_top), (xx, geom.bass_bottom())],
                     fill=_STAFF_LINE, width=geom.note_line_w, tags=(tag,))
        self._paint_signature(ops, x2 + 0.5 * s, fifths, geom, (tag,))

    # -- Chord content ------------------------------------------------------

    def _paint_symbol(self, ops: DrawOps, slot: SlotBox, chord: RenderedChord,
                      geom: _Geometry, tag: str) -> None:
        """Draw the chord symbol centered in the band above the treble staff."""
        ops.text(
            slot.x + slot.width / 2.0, geom.y_symbol,
            chord_symbol_label(chord),
            anchor="n", size=max(8, int(round(1.25 * geom.staff_space))),
            fill=_INK, bold=True, tags=(tag,),
        )

    def _paint_notes(self, ops: DrawOps, slot: SlotBox, chord: RenderedChord,
                     song: RenderedSong, geom: _Geometry, tag: str) -> None:
        """Draw ledger lines, tinted noteheads, and signature-relative accidentals."""
        s = geom.staff_space
        notes = _resolve_notes(chord, song)
        offsets = _collision_offsets(notes)
        sig_map = _signature_letter_map(_key_fifths(chord.key))
        nh = glyph_placement('notehead_whole', s)
        cx = slot.x + slot.width / 2.0

        for note in notes:
            y = geom.y_for_index(note.diatonic_index, note.staff)
            off = offsets.get(id(note), 0) * nh.width
            left = cx - nh.width / 2.0 + off
            center_x = left + nh.width / 2.0

            self._paint_ledgers(ops, center_x, y, note.staff, geom, nh.width, tag)

            head = glyph_placement('notehead_whole', s, note.color)
            ops.image(left - head.origin_x, y - head.origin_y, head.key,
                      anchor="nw", tags=(tag,))

            kind = _accidental_kind(note.letter, note.acc, sig_map)
            if kind == 'text':
                ops.text(
                    left - 0.2 * s, y, _accidental_text(note.acc),
                    anchor="e", size=max(8, int(round(1.6 * s))),
                    fill=note.color, tags=(tag,),
                )
            elif kind is not None:
                acc = glyph_placement('accidental_' + kind, s, note.color)
                ax = left - 0.2 * s - acc.width
                ops.image(ax, y - acc.origin_y, acc.key, anchor="nw", tags=(tag,))

    def _paint_ledgers(self, ops: DrawOps, cx: float, y: float, staff: str,
                       geom: _Geometry, notehead_w: float, tag: str) -> None:
        """Draw ledger lines between a notehead and the lines of its staff."""
        s = geom.staff_space
        top = geom.treble_top if staff == 'treble' else geom.bass_top
        bottom = top + 4.0 * s
        half = notehead_w * 0.75
        eps = 0.25 * s

        positions: List[float] = []
        k = 1
        while True:
            p = top - k * s
            if p < y - eps:
                break
            positions.append(p)
            k += 1
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

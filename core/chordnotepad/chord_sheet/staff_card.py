"""Grand-staff chord-sheet renderer: one continuous engraved grand staff.

:class:`StaffCardRenderer` draws the whole song as a single continuous grand
staff -- two 5-line staves (treble over bass) spanning the full strip width,
joined at the left by the gutter's opening barline. Each sounding chord
contributes its voiced notes as stemless **whole notes** (Bravura noteheads) at
a duration-proportional slot; the chord symbol sits in a band above the treble
staff, every name at one size on one baseline. A rest (NC) draws a whole-bar
rest on both staves in a slim slot. Repeated passes carry repeat signs and the
song ends with a final barline. This replaces the old one-card-per-chord
layout with a continuous lane like the tab view.

The renderer stays a pure function of ``(ctx, height)`` per the
:class:`~chord_sheet.renderer_interface.StripRenderer` contract: all vertical
geometry derives from ``height`` (which fixes the staff-space size) and all
horizontal geometry from the song's durations/keys, so ``layout`` and ``paint``
agree without sharing state.

Engraving detail:

- **Glyphs are Bravura images, not hand-drawn shapes.** Noteheads and
  accidentals come from :func:`~chord_sheet.clef_assets.glyph_placement`
  (embedded, SMuFL-registered PNGs), tinted per voice/hand.
- **Wide staff gap.** The two staves are separated by more than three staff
  spaces so they never read as merged at middle C; a middle C gets its single
  ledger line clearly in the gap.
- **Vertical placement is diatonic, from spelling, not raw MIDI.** A note's
  letter is key-aware: a note diatonic to the chord's key is spelled the way the
  signature spells it (a ``Db`` chord in F# major places its notes as C#/E#/G#,
  no accidentals), so the staff never fights its own signature; a chromatic note
  keeps the chord's parser spelling (a ``Bb`` sits on the B line). The octave is
  derived from the resolved spelling so it reproduces the MIDI note across the
  enharmonic seam (``B#3`` = 60, ``Cb5`` = 71), including when the key-aware
  spelling itself crosses it. Each staff maps diatonic index by its own anchor
  (E4 on the treble bottom line; A3 on the bass top line).
- **Frozen clefs + key signature.** The two clefs and the key signature are
  painted into a non-scrolling left gutter (:meth:`StaffCardRenderer.paint_gutter`)
  so they stay visible while the content scrolls. The gutter signature is
  scroll-aware: it shows the signature for the key in effect at the first
  visible chord. In-content key changes still draw a fresh signature (preceded
  by a thin double barline) at the change point; the gutter is a persistent
  reminder, not a replacement. Sharps/flats use the circle of fifths (minor
  keys via their relative major); a key spelled without a real signature of
  its own (Gbm, D#) engraves as its enharmonic twin (F#m, Eb), and only a
  wholly unparseable key draws no signature.
- **Size and zoom.** The staff space follows the strip's height up to a
  ceiling (strips up to about 190 px); a taller strip centres a staff of that
  size. The renderer honors ``SheetContext.zoom``: the staff space (and every
  glyph, gap, ledger extent, and slot width derived from it) scales by the
  zoom factor, but never past the size whose staff block still fits the
  strip.
- **Accidentals are relative to the signature.** A note only gets an accidental
  glyph when its spelling deviates from the signature: F# in G major draws
  nothing, F natural in G major draws a natural. There is **no bar-carryover
  memory** -- every chord is annotated independently against the signature (a
  deliberate simplification). Double sharps/flats are never sourced from chord
  spellings (they respell enharmonically); the text fallback remains as a
  last-ditch safety only.
- **Voice color coding.** Ensemble chords (``voice_notes``) tint each voice's
  notehead/accidental by ``VOICE_COLORS[voice_index]``; piano chords
  (``hand_split``) tint the left hand and right hand by ``HAND_COLORS``;
  everything else uses ``NOTE_INK``. A legend (when ``voice_labels`` is set) is
  drawn at the far left, top voice first (Soprano above Bass).
- **Ledger lines** are added above/below each staff as needed; **seconds**
  (two notes a diatonic step apart on one staff) offset the upper notehead one
  notehead-width to the right, alternating in a stacked run.
- Bass key-signature accidentals are placed two octaves below the treble
  letters (standard engraving on the bass staff), not one -- the latter would
  place them above the bass staff.
- **Octave-lower treble.** An ensemble whose ``upper_clef`` is ``'treble_8vb'``
  (a male choir's tenors) gets the treble clef with an 8 below, and every
  upper-staff note is written one octave (7 diatonic steps) above its sounding
  pitch: a sung C4 sits on the C5 space. Spelling, accidentals, ledger lines
  and second offsets all follow the written position; the key signature keeps
  its normal treble positions and the bass staff is unchanged.
"""

from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional, Tuple

from chordnotepad.models.ensemble_spec import auto_staff_split
from chordnotepad.models.rendered_song import RenderedChord, RenderedSong
from chordnotepad.chord_sheet.clef_assets import clef_placement, glyph_placement
from chordnotepad.chord_sheet.ops import DrawOps
# The spelling rules are shared with the piano roll (chord_sheet/spelling.py);
# the private names stay for this module's code and tests.
from chordnotepad.chord_sheet.spelling import (  # noqa: F401
    _LETTER_SEMITONE, _LETTER_VALUE, diatonic_index as _diatonic_index,
    diatonic_key_map as _diatonic_key_map, key_fifths as _key_fifths,
    match_letter as _match_letter, spell_midi,
)
from chordnotepad.chord_sheet.renderer_interface import (
    HAND_COLORS,
    NOTE_INK,
    STRIP_BG,
    WHOLE_REST_W,
    SheetContext,
    SlotBox,
    StripLayout,
    StripRenderer,
    VOICE_COLORS,
    chord_symbol_label,
    label_ems,
    paint_section_bands,
    paint_whole_rest,
)
# Duration->width constants are shared with the tab lane so both continuous
# views scale time identically.
from chordnotepad.chord_sheet.tab_strip import (
    MAX_SLOT_WIDTH,
    MIN_SLOT_WIDTH,
    PX_PER_BEAT,
)

logger = logging.getLogger(__name__)

# --- Strip layout constants (px) ------------------------------------------
#: Leading/trailing padding at the strip's left and right edges.
STRIP_MARGIN = 12.0
#: Minimum width of a rest's slim slot (at least the whole rest plus padding).
REST_WIDTH = 18.0
#: Space either side of the whole rest inside its slot, in staff spaces.
_REST_PAD = 0.7

# --- Staff-space sizing ----------------------------------------------------
#: Lane height is divided into this many staff-space units; the staff space is
#: ``height / this`` (clamped). Budget: top pad (0.6) + symbol band (2.2) +
#: ledger above (2) + treble (4) + inter-staff gap (3.5) + bass (4) + ledger
#: below (2) + bottom pad (0.6). The whole block is this many staff spaces
#: tall, so ``height / this`` is also the largest space that still fits.
_HEIGHT_UNITS = 18.9
_MIN_STAFF_SPACE = 4.0
#: The staff space at zoom 1.0 stops growing here (a strip about 190 px
#: tall): a taller strip centres the staff instead of drawing it bigger.
_MAX_STAFF_SPACE = 10.0
#: Vertical gap between the treble bottom line and the bass top line, in staff
#: spaces (> 3 so the staves never read as merged; middle C's ledger sits here).
_GAP_SPACES = 3.5
#: The thin and thick strokes of the system's opening bar line, the repeat
#: signs and the final bar line, in staff spaces (Bravura's engraving
#: defaults: 0.16 and 0.5).
_THIN_BAR_SPACES = 0.16
_THICK_BAR_SPACES = 0.5

# --- Chord-symbol labels ----------------------------------------------------
#: The label's size in pt per staff space (it grows with the staff) and its
#: floor. Every name in the strip has the same size and sits on one baseline;
#: a slot too narrow for its name is widened instead (layout), keeping this
#: much clear space in it (staff spaces, split either side), so neighbouring
#: names never run into each other.
_SYMBOL_PT_PER_SPACE = 1.25
_MIN_SYMBOL_PT = 8
_SYMBOL_CLEAR_SPACES = 0.8
#: pt to px (the front ends draw text sizes as pt at 96 dpi).
_PT_TO_PX = 4.0 / 3.0
#: A bold label's estimated width in ems (shared with the piano roll's note names).
_label_ems = label_ems


def _symbol_size(s: float) -> int:
    """The chord names' size in pt for a staff space of ``s`` px (1.25 staff
    spaces, never under the floor): the same for every name in the strip."""
    return max(_MIN_SYMBOL_PT, int(round(_SYMBOL_PT_PER_SPACE * s)))


def _label_min_width(label: str, s: float) -> float:
    """The slot width a label needs at the strip's name size, clear space
    included."""
    return _label_ems(label) * _symbol_size(s) * _PT_TO_PX + _SYMBOL_CLEAR_SPACES * s


# --- Colors / stroke (module-local; no edits to constants.py) --------------
_INK = NOTE_INK
_STAFF_LINE = "#7c8b96"

# --- Staff anchors -------------------------------------------------------
#: Diatonic index of E4 (the treble staff's bottom line) and A3 (the bass
#: staff's top line): the per-staff vertical anchors.
_E4_INDEX = 4 * 7 + _LETTER_VALUE['E']
_A3_INDEX = 3 * 7 + _LETTER_VALUE['A']

# --- Key-signature tables --------------------------------------------------
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

#: Diatonic steps an octave-lower treble clef (``'treble_8vb'``) writes its
#: notes above how they sound: one octave.
_TREBLE_8VB_SHIFT = 7


# --------------------------------------------------------------------------
# Spelling
# --------------------------------------------------------------------------

def _accidental_offset(name: str) -> int:
    """Signed accidental total of a note name's tail (``#`` +1, ``b``/``-`` -1)."""
    offset = 0
    for ch in name[1:]:
        if ch == '#':
            offset += 1
        elif ch in ('b', '-'):
            offset -= 1
    return offset


def _spell(midi: int, chord_notes, fifths: Optional[int] = None) -> Tuple[str, int, int]:
    """Spell a MIDI note as ``(letter, accidental_offset, diatonic_index)``
    (:func:`chord_sheet.spelling.spell_midi`, which the piano roll shares)."""
    note = spell_midi(midi, chord_notes, fifths)
    return note.letter, note.accidental, note.diatonic_index


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
    """One resolved notehead: staff, spelling, diatonic position, and color.

    ``diatonic_index`` is the *written* position: the sounding one, plus an
    octave on an octave-lower treble staff.
    """

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
    ink, or at C3 (written middle C) under an octave-lower treble clef.
    """
    split = auto_staff_split(song.upper_clef)
    if chord.voice_notes is not None:
        staves = song.voice_staves
        out: List[Tuple[int, str, str]] = []
        for i, midi in enumerate(chord.voice_notes):
            if staves is not None and i < len(staves):
                staff = staves[i]
            else:
                staff = 'treble' if midi >= split else 'bass'
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
        (midi, 'treble' if midi >= split else 'bass', _INK)
        for midi in (chord.midi_notes or [])
    ]


def _resolve_notes(chord: RenderedChord, song: RenderedSong) -> List[_Note]:
    """Resolve a chord's drawn notes to spelled :class:`_Note` records.

    Spelling is key-aware and keeps the chord one stack of thirds: a root
    diatonic to the chord's key is spelled to match the signature (so a ``Db``
    chord in F# major draws C#/E#/G# with no accidentals), a chromatic root
    keeps the user's spelling (``B`` in Db draws B/D#/F#), and the other notes
    follow the root. See :func:`_match_letter`. On an octave-lower treble staff
    (``song.upper_clef == 'treble_8vb'``) an upper-staff note is written an
    octave above its sounding position; the letter and accidental are the same.
    """
    notes: List[_Note] = []
    fifths = _key_fifths(chord.key)
    treble_shift = _TREBLE_8VB_SHIFT if song.upper_clef == 'treble_8vb' else 0
    for midi, staff, color in _voiced(chord, song):
        letter, acc, idx = _spell(midi, chord.chord_notes, fifths)
        if staff == 'treble':
            idx += treble_shift
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
    thin_bar_w: float     # the opening, repeat and final bar lines' thin stroke
    thick_bar_w: float    # the repeat and final bar lines' thick stroke

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


def _staff_space(height: float, zoom: float = 1.0) -> float:
    """Staff-space size (line-to-line gap) for a lane of the given height.

    At zoom 1.0 the space follows the height up to :data:`_MAX_STAFF_SPACE`
    (strips up to about 190 px), so a tall strip gets a staff of a readable
    size with room around it rather than oversized notes. ``zoom`` scales
    that size (and every glyph, gap and ledger extent derived from it), never
    below the pixel floor and never past the largest space whose whole block
    still fits the strip, so zooming in never clips the bass staff.
    """
    base = max(_MIN_STAFF_SPACE, min(_MAX_STAFF_SPACE, height / _HEIGHT_UNITS))
    cap = max(_MIN_STAFF_SPACE, height / _HEIGHT_UNITS)
    return max(_MIN_STAFF_SPACE, min(cap, base * zoom))


def _geometry(height: float, zoom: float = 1.0) -> _Geometry:
    """Compute the lane's vertical geometry from ``height``/``zoom`` (pure)."""
    s = _staff_space(height, zoom)

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
        thin_bar_w=max(1.0, _THIN_BAR_SPACES * s),
        thick_bar_w=max(2.0, _THICK_BAR_SPACES * s),
    )


# --- Horizontal helpers ----------------------------------------------------

#: Spacing (in staff spaces) used for the clef/key-signature header and slots.
_CLEF_PAD_LEFT = 0.6
_CLEF_SIG_GAP = 0.7
_SIG_GLYPH_GAP = 0.35
_SIG_NOTES_GAP = 1.0
#: Double-barline room before a mid-song key change (staff spaces).
_KEY_CHANGE_PAD = 1.4
#: Room after a repeat sign before the new signature that follows it, which
#: then needs no double barline of its own (staff spaces).
_SIG_AFTER_SIGN_PAD = 0.6

# --- Repeat signs and the final bar line (staff spaces) --------------------
#: Between a thin and a thick stroke (Bravura: barlineSeparation).
_BAR_SEP = 0.4
#: Between a thin stroke and its repeat dots.
_DOT_SEP = 0.25
#: A repeat dot's diameter, and its floor in px (smaller reads as dust).
_DOT_SPACES = 0.5
_MIN_DOT_PX = 2.5
#: Clear room before and after a repeat sign, inside its lead.
_SIGN_PAD_BEFORE = 0.5
_SIGN_PAD_AFTER = 0.8


def _slot_width(chord: RenderedChord, zoom: float = 1.0) -> float:
    """Slot width: slim for rests, else duration-proportional (clamped).

    The duration->width constants scale with ``zoom`` so the layout keeps its
    proportions (and does not cramp) as the staff space grows.
    """
    if chord.is_rest:
        return REST_WIDTH * zoom
    return max(
        MIN_SLOT_WIDTH * zoom,
        min(MAX_SLOT_WIDTH * zoom, chord.duration_beats * PX_PER_BEAT * zoom),
    )


def _signature_width(fifths: Optional[int], s: float) -> float:
    """Total px width of a key signature's accidental glyphs (0 if empty)."""
    total = 0.0
    for entry in _signature_entries(fifths):
        w = glyph_placement('accidental_' + entry.kind, s).width
        total += w + _SIG_GLYPH_GAP * s
    return total


def _key_change_lead(fifths: Optional[int], s: float, after_sign: bool = False) -> float:
    """Horizontal room a mid-song key change consumes before the next slot
    (less after a repeat sign, which stands in for its double barline)."""
    pad = _SIG_AFTER_SIGN_PAD if after_sign else _KEY_CHANGE_PAD
    return pad * s + _signature_width(fifths, s)


class _Repeat(NamedTuple):
    """The repeat sign at a slot's left edge: ``end`` (``:|``, the pass
    before it jumps back), ``start`` (``|:``, a pass of the looped part
    begins), or both (``:||:``)."""

    end: bool
    start: bool


def _repeat_signs(song: RenderedSong) -> Dict[int, _Repeat]:
    """Chord index -> the repeat sign drawn at its slot's left edge.

    The staff is the unrolled song, so a loop's passes follow one another.
    Every pass of the looped part opens with ``|:`` and every pass that jumps
    back ends with ``:|``; the last pass ends with a plain bar line. Each
    ``'loop'`` marker (one per jump, from the renderer's walk) says where the
    next pass starts (its beat, which takes ``:||:``) and where the pass it
    repeats began (its ``target_beat``: the loop's first pass for the first
    jump, the song start for ``@start``). Each jump is read on its own, so
    nested loops and two loops to one label keep their own passes; signs of
    different loops that meet at one chord merge.
    """
    chords = song.chords
    if not chords:
        return {}
    beats = [chord.start_beat for chord in chords]

    def index_at(beat: float) -> Optional[int]:
        i = bisect.bisect_left(beats, beat - 1e-6)
        return i if i < len(chords) else None

    ends, starts = set(), set()
    for marker in song.markers:
        if marker.kind != 'loop' or marker.pass_num < 2:
            continue
        jump = index_at(marker.beat)
        if jump is None:
            continue
        ends.add(jump)
        starts.add(jump)
        first = index_at(marker.target_beat or 0.0)
        if first is not None and first < jump:
            starts.add(first)
    return {i: _Repeat(i in ends, i in starts) for i in sorted(ends | starts)}


def _sign_strokes(sign: _Repeat, geom: "_Geometry") -> List[Tuple[str, float, float]]:
    """A repeat sign's parts left to right as ``(kind, x, width)``, from x 0:
    ``kind`` is ``'thin'``, ``'thick'`` or ``'dots'`` (``x`` is the part's
    left edge). ``:|`` is dots, thin, thick; ``|:`` its mirror; ``:||:`` dots,
    thin, thick, thin, dots."""
    s = geom.staff_space
    thin, thick = geom.thin_bar_w, geom.thick_bar_w
    dot = max(_MIN_DOT_PX, _DOT_SPACES * s)
    parts: List[Tuple[str, float]] = []
    if sign.end:
        parts += [('dots', dot), ('gap', _DOT_SEP * s), ('thin', thin), ('gap', _BAR_SEP * s)]
    parts.append(('thick', thick))
    if sign.start:
        parts += [('gap', _BAR_SEP * s), ('thin', thin), ('gap', _DOT_SEP * s), ('dots', dot)]
    out: List[Tuple[str, float, float]] = []
    x = 0.0
    for kind, width in parts:
        if kind != 'gap':
            out.append((kind, x, width))
        x += width
    return out


def _sign_lead(sign: _Repeat, geom: "_Geometry") -> float:
    """Horizontal room a repeat sign takes before its slot, pads included."""
    _, x, width = _sign_strokes(sign, geom)[-1]
    s = geom.staff_space
    return (_SIGN_PAD_BEFORE + _SIGN_PAD_AFTER) * s + x + width


def _final_bar_width(geom: "_Geometry") -> float:
    """Width of the final bar line (thin, a gap, thick)."""
    return geom.thin_bar_w + _BAR_SEP * geom.staff_space + geom.thick_bar_w


def _content_x0(s: float) -> float:
    """Left x where the first scrolling-content slot begins.

    The clef and initial key signature now live in the frozen gutter, so the
    content only reserves a small lead after its connecting barline.
    """
    return STRIP_MARGIN + _SIG_NOTES_GAP * s


def _upper_clef_kind(song: RenderedSong) -> str:
    """The upper staff's clef asset kind: ``'treble'`` or ``'treble_8vb'``."""
    return 'treble_8vb' if song.upper_clef == 'treble_8vb' else 'treble'


def _gutter_geometry(song: RenderedSong, s: float) -> Tuple[float, float, float]:
    """Return gutter-local ``(x_clef, x_sig, gutter_width)`` for the frozen pane.

    ``x_clef``/``x_sig`` are the gutter-local x of the clef and the signature's
    first accidental. ``gutter_width`` fits the clef plus the WIDEST key
    signature used anywhere in the song (so the width -- and thus the content's
    left edge -- does not jump when scrolling past a key change) plus a small
    trailing pad.
    """
    clef_w = max(
        clef_placement(_upper_clef_kind(song), s).width,
        clef_placement('bass', s).width,
    )
    x_clef = _CLEF_PAD_LEFT * s
    x_sig = x_clef + clef_w + _CLEF_SIG_GAP * s
    keys = {chord.key for chord in song.chords} or {None}
    max_sig = max(_signature_width(_key_fifths(key), s) for key in keys)
    width = x_sig + max_sig + _SIG_NOTES_GAP * s
    return x_clef, x_sig, width


# --------------------------------------------------------------------------
# Renderer
# --------------------------------------------------------------------------

class StaffCardRenderer(StripRenderer):
    """Draw the song as one continuous grand staff with Bravura glyphs."""

    id = "staff"
    label = "Staff"
    requires_fingering = False
    supports_zoom = True

    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Lay slots left to right, width proportional to duration.

        Slots begin after a small content lead (the clef + initial signature
        now live in the frozen gutter, not the content); a chord whose key
        differs from the previous chord's reserves extra lead width for a double
        barline and a new signature. All horizontal spacing scales with
        ``ctx.zoom`` via the zoom-aware staff space and slot widths.

        Args:
            ctx: Song-wide context.
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one slot per chord in song order (rests
            in slim slots).
        """
        song = ctx.song
        geom = _geometry(height, ctx.zoom)
        s = geom.staff_space
        x = _content_x0(s)
        signs = _repeat_signs(song)

        prev_fifths = _key_fifths(song.chords[0].key) if song.chords else None
        slots: List[SlotBox] = []
        for index, chord in enumerate(song.chords):
            sign = signs.get(index)
            if sign is not None:
                x += _sign_lead(sign, geom)
            if index > 0:
                fifths = _key_fifths(chord.key)
                if fifths != prev_fifths:
                    x += _key_change_lead(fifths, s, after_sign=sign is not None)
                    prev_fifths = fifths
            width = _slot_width(chord, ctx.zoom)
            if chord.is_rest:
                width = max(width, (WHOLE_REST_W + 2 * _REST_PAD) * s)
            # Room for the name at the strip's name size (a short slot, a
            # long name), for chords and rests alike.
            width = max(width, _label_min_width(chord_symbol_label(chord), s))
            slots.append(SlotBox(chord_index=index, x=x, width=width))
            x += width

        # The final bar line follows the last slot; the staff ends with it.
        content_width = ((x + _final_bar_width(geom) + STRIP_MARGIN) if slots
                         else (2 * STRIP_MARGIN))
        return StripLayout(width=content_width, height=height, slots=tuple(slots))

    # -- Frozen gutter (clefs + key signature) ------------------------------

    def gutter_width(self, ctx: SheetContext, height: float) -> float:
        """Width of the frozen gutter: clef + widest signature + padding.

        Sized for the widest key signature used anywhere in the song so the
        content's left edge does not shift when the scroll-aware signature
        changes. Honors ``ctx.zoom`` through the zoom-aware staff space.
        """
        s = _staff_space(height, ctx.zoom)
        _, _, width = _gutter_geometry(ctx.song, s)
        return width

    def paint_gutter(self, ops: DrawOps, ctx: SheetContext, height: float,
                     scroll_x: float) -> None:
        """Paint the frozen clefs and the scroll-aware key signature.

        Draws (in order) the strip background, both staves' lines across the
        gutter (they carry on into the content's at its right edge), the
        system's opening bar line at its left edge, the two clefs, then the
        key signature for the key in effect at the first chord whose slot is
        at-or-after ``scroll_x`` (empty song or before the first chord -> the
        initial key). Coordinates are gutter-local.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            height: Available content height in pixels.
            scroll_x: Content x at the viewport's left edge (drives which key
                signature to show).
        """
        song = ctx.song
        geom = _geometry(height, ctx.zoom)
        s = geom.staff_space
        x_clef, x_sig, width = _gutter_geometry(song, s)

        ops.rect(0.0, 0.0, width, height, fill=STRIP_BG, tags=("gutter",))
        for base in (geom.treble_top, geom.bass_top):
            for k in range(5):
                y = base + k * s
                ops.line([(0.0, y), (width, y)],
                         fill=_STAFF_LINE, width=geom.staff_line_w, tags=("gutter",))
        # The system's opening bar line, joining both staves at the gutter's
        # left edge (inset by half its width, so no clip shaves it).
        bar_x = geom.thin_bar_w / 2.0
        ops.line([(bar_x, geom.treble_top), (bar_x, geom.bass_bottom())],
                 fill=_STAFF_LINE, width=geom.thin_bar_w, tags=("gutter",))

        self._paint_clefs(ops, x_clef, geom, _upper_clef_kind(song), tags=("gutter",))
        fifths = self._key_at_scroll(ctx, height, scroll_x)
        self._paint_signature(ops, x_sig, fifths, geom, ("gutter",))

    def gutter_breakpoints(self, ctx: SheetContext, height: float,
                           layout: StripLayout) -> List[float]:
        """Scroll positions where the gutter's key signature changes.

        :meth:`_key_at_scroll` shows the key of the first slot whose left edge
        is at or past ``scroll_x``, so the key of slot ``j`` takes over once
        ``scroll_x`` passes slot ``j - 1``'s left edge. A breakpoint is that
        edge, for every ``j`` whose key signature differs from slot ``j - 1``'s.
        """
        chords = ctx.song.chords
        slots = layout.slots
        breakpoints: List[float] = []
        for j in range(1, len(slots)):
            if (_key_fifths(chords[slots[j].chord_index].key)
                    != _key_fifths(chords[slots[j - 1].chord_index].key)):
                breakpoints.append(slots[j - 1].x)
        return breakpoints

    def _key_at_scroll(self, ctx: SheetContext, height: float,
                       scroll_x: float) -> Optional[int]:
        """Circle-of-fifths of the key in effect at the first visible chord.

        Walks the (pure) layout slots and returns the fifths of the first chord
        whose slot begins at-or-after ``scroll_x``; before the first chord (or
        an empty song) returns the initial key; scrolled past every chord it
        returns the last chord's key.
        """
        song = ctx.song
        chords = song.chords
        if not chords:
            return None
        eps = 1e-6
        for slot in self.layout(ctx, height).slots:
            if slot.x >= scroll_x - eps:
                return _key_fifths(chords[slot.chord_index].key)
        return _key_fifths(chords[-1].key)

    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Emit the grand staff, clefs, signatures, and whole notes.

        Args:
            ops: Recorder to append draw ops to.
            ctx: Song-wide context.
            layout: Layout from :meth:`layout` for the same ``ctx``/``height``.
        """
        song = ctx.song
        chords = song.chords
        geom = _geometry(layout.height, ctx.zoom)
        s = geom.staff_space
        paint_section_bands(ops, song, layout)

        # The staff lines start at the content's left edge, where the
        # gutter's lines end, so the staff reads as one; the gutter draws the
        # system's opening bar line.
        x_left = 0.0
        x_right = max(x_left + 1.0, layout.width - STRIP_MARGIN)
        self._paint_staff_lines(ops, geom, x_left, x_right)
        if layout.slots:
            self._paint_final_bar(ops, x_right, geom)

        # Clefs and the initial signature live in the frozen gutter now; the
        # scrolling content only draws staff lines, legend, in-content key
        # changes, symbols, and notes.
        fifths0 = _key_fifths(chords[0].key) if chords else None
        if song.voice_labels:
            self._paint_legend(ops, song.voice_labels, geom)

        signs = _repeat_signs(song)
        prev_fifths = fifths0
        prev_bar: Optional[int] = None
        for slot in layout.slots:
            index = slot.chord_index
            chord = chords[index]
            tag = f"slot:{index}"
            sign = signs.get(index)

            # Before the slot, right to left: a key change's lead, then a
            # repeat sign's (the sign stands for the bar line).
            lead_x = slot.x
            if index > 0:
                fifths = _key_fifths(chord.key)
                if fifths != prev_fifths:
                    lead_x -= _key_change_lead(fifths, s, after_sign=sign is not None)
                    self._paint_key_change(ops, lead_x, fifths, geom, tag,
                                           double_bar=sign is None)
                    prev_fifths = fifths
                elif chord.bar != prev_bar and sign is None:
                    ops.line(
                        [(slot.x, geom.treble_top), (slot.x, geom.bass_bottom())],
                        fill=_STAFF_LINE, width=geom.staff_line_w, tags=(tag,),
                    )
            if sign is not None:
                self._paint_repeat(ops, lead_x - _sign_lead(sign, geom), sign, geom, tag)
            prev_bar = chord.bar

            self._paint_symbol(ops, slot, chord, geom, tag)
            if chord.is_rest:
                self._paint_rest(ops, slot, geom, tag)
                continue
            self._paint_notes(ops, slot, chord, song, geom, tag)

    def _paint_rest(self, ops: DrawOps, slot: SlotBox, geom: _Geometry, tag: str) -> None:
        """Draw a whole-bar rest on both staves, centred in the rest's slot.

        Every NC shows as one bar's rest whatever its length (note values are
        not engraved yet).
        """
        s = geom.staff_space
        cx = slot.x + slot.width / 2.0
        for top in (geom.treble_top, geom.bass_top):
            paint_whole_rest(ops, cx, top + s, s, _INK, tag)

    # -- Staff / clefs ------------------------------------------------------

    def _paint_staff_lines(self, ops: DrawOps, geom: _Geometry,
                           x_left: float, x_right: float) -> None:
        """Draw the two 5-line staves from ``x_left`` to ``x_right``."""
        s = geom.staff_space
        for base in (geom.treble_top, geom.bass_top):
            for k in range(5):
                y = base + k * s
                ops.line([(x_left, y), (x_right, y)],
                         fill=_STAFF_LINE, width=geom.staff_line_w, tags=("staff",))

    def _paint_bar_stroke(self, ops: DrawOps, x: float, width: float,
                          geom: _Geometry, tags: Tuple[str, ...]) -> None:
        """One vertical stroke through both staves, its left edge at ``x``."""
        cx = x + width / 2.0
        ops.line([(cx, geom.treble_top), (cx, geom.bass_bottom())],
                 fill=_STAFF_LINE, width=width, tags=tags)

    def _paint_final_bar(self, ops: DrawOps, x_end: float, geom: _Geometry) -> None:
        """The final bar line (thin, then thick), ending where the staff does."""
        x = x_end - _final_bar_width(geom)
        tags = ("staff", "final-bar")
        self._paint_bar_stroke(ops, x, geom.thin_bar_w, geom, tags)
        self._paint_bar_stroke(ops, x_end - geom.thick_bar_w, geom.thick_bar_w, geom, tags)

    def _paint_repeat(self, ops: DrawOps, x0: float, sign: _Repeat,
                      geom: _Geometry, tag: str) -> None:
        """Draw a repeat sign in the lead that starts at ``x0``: its strokes
        through both staves and its dots in the second and third spaces of
        each staff (either side of the middle line)."""
        s = geom.staff_space
        tags = (tag, "repeat")
        x = x0 + _SIGN_PAD_BEFORE * s
        for kind, dx, width in _sign_strokes(sign, geom):
            if kind == 'dots':
                for top in (geom.treble_top, geom.bass_top):
                    for space in (1.5, 2.5):
                        cy = top + space * s
                        ops.oval(x + dx, cy - width / 2.0, width, width,
                                 fill=_STAFF_LINE, tags=tags)
            else:
                self._paint_bar_stroke(ops, x + dx, width, geom, tags)

    def _paint_clefs(self, ops: DrawOps, x_clef: float, geom: _Geometry,
                     upper: str = 'treble', tags: Tuple[str, ...] = ("gutter",)) -> None:
        """Emit clef images registered to each staff's reference line.

        ``upper`` is the upper staff's clef kind (``'treble'`` or
        ``'treble_8vb'``); both register on the G line.
        """
        treble = clef_placement(upper, geom.staff_space)
        g4_y = geom.y_for_index(_diatonic_index('G', 4), 'treble')
        ops.image(x_clef, g4_y - treble.baseline_y, treble.key,
                  anchor="nw", tags=tags)
        bass = clef_placement('bass', geom.staff_space)
        f3_y = geom.y_for_index(_diatonic_index('F', 3), 'bass')
        ops.image(x_clef, f3_y - bass.baseline_y, bass.key,
                  anchor="nw", tags=tags)

    def _paint_legend(self, ops: DrawOps, labels: List[str], geom: _Geometry) -> None:
        """Draw a tiny stacked voice legend at the far left, each in its color.

        ``labels`` are stored low voice first; the legend lists them high to
        low (Soprano, Alto, Tenor, Bass), as the voices sit on the staff."""
        s = geom.staff_space
        size = max(6, int(round(0.85 * s)))
        line_h = size + 2.0
        y = geom.y_symbol
        top_first = list(enumerate(labels))[::-1]
        for row, (i, label) in enumerate(top_first):
            ops.text(
                STRIP_MARGIN + 1.0, y + row * line_h, label,
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
                          geom: _Geometry, tag: str, double_bar: bool = True) -> None:
        """Draw a thin double barline then the new signature in the lead space
        (just the signature after a repeat sign, which is the bar line)."""
        s = geom.staff_space
        if not double_bar:
            self._paint_signature(ops, x0, fifths, geom, (tag,))
            return
        x1 = x0 + 0.2 * s
        x2 = x1 + 0.3 * s
        for xx in (x1, x2):
            ops.line([(xx, geom.treble_top), (xx, geom.bass_bottom())],
                     fill=_STAFF_LINE, width=geom.note_line_w, tags=(tag,))
        self._paint_signature(ops, x2 + 0.5 * s, fifths, geom, (tag,))

    # -- Chord content ------------------------------------------------------

    def _paint_symbol(self, ops: DrawOps, slot: SlotBox, chord: RenderedChord,
                      geom: _Geometry, tag: str) -> None:
        """Draw the chord symbol centred in the band above the treble staff,
        at the strip's one name size and top (so one baseline); layout made
        the slot wide enough for it."""
        label = chord_symbol_label(chord)
        ops.text(
            slot.x + slot.width / 2.0, geom.y_symbol,
            label,
            anchor="n", size=_symbol_size(geom.staff_space),
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

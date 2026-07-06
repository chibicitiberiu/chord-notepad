"""Headless tests for the continuous grand-staff :class:`StaffCardRenderer`.

Every test inspects the recorded :class:`DrawOps` (no Tk/display). Coverage:
one slot per chord with slim empty rests; Bravura noteheads as tinted image ops
split across the two staves; diatonic placement and spelling (Bb/F#, the B#/Cb
seam); ledger lines; second-interval collision offsets; ensemble routing by
``voice_staves``; key signatures (glyph counts + per-clef positions); accidentals
drawn only when they deviate from the signature; a mid-song key change (double
barline + fresh signature); per-voice and per-hand notehead tints; a voice
legend; and the extended clef/glyph asset resolver.
"""
from typing import List, Optional

from audio.chord_picker import ChordNotePicker
from models.chord import ChordInfo
from models.chord_notes import ChordNotes
from models.line import Line
from models.rendered_song import RenderedChord, RenderedSong
from services.song_renderer import SongRenderer
from ui.chord_sheet.ops import DrawOps, ImageOp, LineOp, TextOp
from ui.chord_sheet.renderer_interface import (
    HAND_COLORS,
    NOTE_INK,
    SheetContext,
    VOICE_COLORS,
)
from ui.chord_sheet import clef_assets as ca
from ui.chord_sheet import staff_card as sc
from ui.chord_sheet.staff_card import StaffCardRenderer, REST_WIDTH


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

def make_chord(
    symbol: str = "C",
    *,
    is_rest: bool = False,
    midi_notes: Optional[List[int]] = None,
    chord_notes: Optional[ChordNotes] = None,
    key: Optional[str] = None,
    bar: int = 1,
    duration_beats: float = 1.0,
    hand_split: Optional[int] = None,
    voice_notes: Optional[List[int]] = None,
) -> RenderedChord:
    return RenderedChord(
        chord_info=ChordInfo(chord=symbol, start=0, end=1, is_valid=True, is_rest=is_rest),
        chord_notes=chord_notes,
        midi_notes=None if is_rest else midi_notes,
        line_index=0,
        item_index=0,
        start_beat=0.0,
        duration_beats=duration_beats,
        start_time=0.0,
        duration_seconds=0.0,
        bpm=120,
        time_sig=(4, 4),
        key=key,
        bar=bar,
        is_rest=is_rest,
        voice_notes=voice_notes,
        hand_split=hand_split,
    )


def make_song(*chords: RenderedChord, voice_staves=None, voice_labels=None) -> RenderedSong:
    return RenderedSong(
        chords=list(chords), voice_staves=voice_staves, voice_labels=voice_labels
    )


def paint(song: RenderedSong, height: float = 130.0, zoom: float = 1.0):
    renderer = StaffCardRenderer()
    ctx = SheetContext(song=song, zoom=zoom)
    layout = renderer.layout(ctx, height)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    return layout, ops


def paint_gutter(song: RenderedSong, height: float = 130.0, scroll_x: float = 0.0,
                 zoom: float = 1.0):
    renderer = StaffCardRenderer()
    ctx = SheetContext(song=song, zoom=zoom)
    ops = DrawOps()
    renderer.paint_gutter(ops, ctx, height, scroll_x)
    return ops


def noteheads(ops) -> List[ImageOp]:
    return [o for o in ops.ops
            if isinstance(o, ImageOp) and o.key.startswith("glyph_notehead_whole")]


def accidentals(ops, kind: str) -> List[ImageOp]:
    return [o for o in ops.ops
            if isinstance(o, ImageOp) and o.key.startswith("glyph_accidental_" + kind)]


def render_song(symbols: List[str], key: Optional[str], bpm: int = 120) -> RenderedSong:
    """Render ``symbols`` through the real pipeline in ``key`` (piano voicing).

    Builds a one-line song of absolute chords, renders it with a real
    :class:`ChordNotePicker`, and returns the :class:`RenderedSong` -- so each
    chord carries the parser's source spelling in ``chord_notes`` and a real
    voicing in ``midi_notes``, exactly as the app produces.
    """
    line = Line(content=" ".join(symbols), line_number=1)
    line.items = [
        ChordInfo(chord=sym, start=i, end=i + 1, is_relative=False, is_valid=True)
        for i, sym in enumerate(symbols)
    ]
    picker = ChordNotePicker()
    picker.reset()
    return SongRenderer().render(
        lines=[line], initial_key=key, initial_bpm=bpm,
        initial_time_sig=(4, 4), note_picker=picker,
    )


def content_accidental_ops(ops):
    """Every accidental glyph/text drawn on a note in the scrolling content.

    Image accidentals tagged to a chord slot plus the rare double-accidental
    text fallback -- i.e. everything a note contributes, excluding gutter and
    key-change signature glyphs.
    """
    out = []
    for o in ops.ops:
        in_slot = any(str(t).startswith("slot:") for t in o.tags)
        if not in_slot:
            continue
        if isinstance(o, ImageOp) and o.key.startswith("glyph_accidental_"):
            out.append(o)
        elif isinstance(o, TextOp) and ("♯" in o.s or "♭" in o.s):
            out.append(o)
    return out


def color_of(op: ImageOp) -> Optional[str]:
    """The tint suffix of a glyph key, or ``None`` for an untinted key."""
    parts = op.key.split(":")
    return parts[2] if len(parts) == 3 else None


def note_center_y(op: ImageOp, s: float) -> float:
    """Center y of a notehead image op (origin registers on its line/space)."""
    return op.y + ca.glyph_placement("notehead_whole", s).origin_y


def vertical_lines(ops) -> List[LineOp]:
    return [o for o in ops.ops if isinstance(o, LineOp)
            and o.fill == sc._STAFF_LINE and len(o.points) == 2
            and abs(o.points[0][0] - o.points[1][0]) < 1e-6]


def ink_ledgers(ops) -> List[LineOp]:
    """Horizontal ink lines are ledger lines (staff lines use the staff color)."""
    return [o for o in ops.ops
            if isinstance(o, LineOp) and o.fill == sc._INK
            and len(o.points) == 2 and o.points[0][1] == o.points[1][1]]


C_MAJOR = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')


# --------------------------------------------------------------------------
# Layout / rests
# --------------------------------------------------------------------------

class TestLayout:
    def test_one_slot_per_chord_in_order(self):
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR),
            make_chord("G", midi_notes=[55, 59, 62], chord_notes=C_MAJOR),
            make_chord("Am", midi_notes=[57, 60, 64], chord_notes=C_MAJOR),
        )
        layout, _ = paint(song)
        assert [s.chord_index for s in layout.slots] == [0, 1, 2]

    def test_slots_are_duration_proportional(self):
        song = make_song(
            make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, duration_beats=1.0),
            make_chord("G", midi_notes=[55], chord_notes=C_MAJOR, duration_beats=2.0),
        )
        layout, _ = paint(song)
        w1, w2 = layout.slots[0].width, layout.slots[1].width
        assert w2 > w1
        assert w1 == sc._slot_width(song.chords[0])
        assert w2 == sc._slot_width(song.chords[1])

    def test_rest_slot_is_slim_and_empty(self):
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, duration_beats=2.0),
            make_chord("NC", is_rest=True),
        )
        layout, ops = paint(song)
        chord_slot, rest_slot = layout.slots
        assert rest_slot.width == REST_WIDTH
        assert rest_slot.width < chord_slot.width
        # The rest emits nothing: no noteheads, accidentals, or symbol text.
        rest_ops = [o for o in ops.ops if "slot:1" in o.tags]
        assert rest_ops == []

    def test_geometry_is_pure_function_of_height(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        (l1, o1), (l2, o2) = paint(song, 130.0), paint(song, 130.0)
        assert l1.slots[0].width == l2.slots[0].width
        assert [type(o) for o in o1.ops] == [type(o) for o in o2.ops]
        assert [getattr(o, "key", None) for o in o1.ops] == \
               [getattr(o, "key", None) for o in o2.ops]


# --------------------------------------------------------------------------
# Whole notes across both staves
# --------------------------------------------------------------------------

class TestPianoChordBothStaves:
    def test_noteheads_on_both_staves_lh_below(self):
        # LH bass note 48 (C3), RH 60/64/67; hand_split=1.
        song = make_song(make_chord(
            "C", midi_notes=[48, 60, 64, 67], chord_notes=C_MAJOR, hand_split=1))
        _, ops = paint(song)
        heads = noteheads(ops)
        assert len(heads) == 4

        geom = sc._geometry(130.0)
        centers = sorted(note_center_y(o, geom.staff_space) for o in heads)
        split = geom.treble_bottom() + (_gap := (geom.bass_top - geom.treble_bottom())) / 2.0
        lh = [c for c in centers if c > split]
        rh = [c for c in centers if c <= split]
        assert len(lh) == 1 and len(rh) == 3
        assert min(lh) > max(rh)


# --------------------------------------------------------------------------
# Spelling: accidentals + diatonic position
# --------------------------------------------------------------------------

class TestSpellingAccidentals:
    def _heads_at_index(self, ops, geom, diatonic_index, staff):
        target = geom.y_for_index(diatonic_index, staff)
        return [o for o in noteheads(ops)
                if abs(note_center_y(o, geom.staff_space) - target) < 1e-6]

    def test_flat_sits_on_letter_position_with_flat_glyph(self):
        # Bb (MIDI 70) must land on the B position (not A#) with a flat glyph.
        cn = ChordNotes(notes=['B-', 'D', 'F'], bass_note='B-', root='B-')
        song = make_song(make_chord("Bb", midi_notes=[70], chord_notes=cn))
        _, ops = paint(song)
        geom = sc._geometry(130.0)
        b_index = sc._diatonic_index('B', 4)  # Bb4 -> B position, octave 4
        assert self._heads_at_index(ops, geom, b_index, 'treble')
        assert len(accidentals(ops, 'flat')) == 1
        assert not accidentals(ops, 'sharp')

    def test_sharp_sits_on_letter_position_with_sharp_glyph(self):
        # F# (MIDI 66) must land on the F position with a sharp glyph.
        cn = ChordNotes(notes=['F#', 'A', 'C#'], bass_note='F#', root='F#')
        song = make_song(make_chord("F#", midi_notes=[66], chord_notes=cn))
        _, ops = paint(song)
        geom = sc._geometry(130.0)
        f_index = sc._diatonic_index('F', 4)  # F#4 -> F position, octave 4
        assert self._heads_at_index(ops, geom, f_index, 'treble')
        assert len(accidentals(ops, 'sharp')) == 1

    def test_unmatched_pitch_class_defaults_to_sharp(self):
        # No chord_notes: a black-key MIDI note falls back to a sharp spelling.
        song = make_song(make_chord("?", midi_notes=[66], chord_notes=None))
        _, ops = paint(song)
        assert len(accidentals(ops, 'sharp')) == 1


class TestEnharmonicSeam:
    def test_b_sharp_lands_below_middle_c(self):
        cn = ChordNotes(notes=['B#', 'D#', 'F##'], bass_note='B#', root='B#')
        letter, acc, idx = sc._spell(60, cn)
        assert (letter, acc) == ('B', 1)
        assert idx == sc._diatonic_index('B', 3)
        assert idx < sc._diatonic_index('C', 4)

    def test_c_flat_lands_on_c5_position(self):
        cn = ChordNotes(notes=['C-', 'E-', 'G-'], bass_note='C-', root='C-')
        letter, acc, idx = sc._spell(71, cn)
        assert (letter, acc) == ('C', -1)
        assert idx == sc._diatonic_index('C', 5)
        assert idx > sc._diatonic_index('B', 4)


class TestDoubleAccidentalSources:
    """pychord spells Gbm as Gb-Bbb-Db; doubles must never reach the canvas."""

    GBM = ChordNotes(notes=['Gb', 'Bbb', 'Db'], bass_note='Gb', root='Gb')

    def test_double_flat_skipped_for_plain_fallback(self):
        # No key: the Bbb source spelling is skipped (no engraving glyph) and
        # pc 9 falls back to plain A instead of B-double-flat.
        assert sc._match_letter(9, self.GBM, None) == ('A', 0)

    def test_gbm_in_gbm_key_is_fully_diatonic(self):
        # Key Gbm engraves as F#m (3 sharps): every chord tone is diatonic, so
        # nothing carries an accidental -- including the Bbb (spelled A).
        fifths = sc._key_fifths('Gbm')
        assert fifths == 3
        assert sc._match_letter(6, self.GBM, fifths) == ('F', 1)   # F#
        assert sc._match_letter(9, self.GBM, fifths) == ('A', 0)
        assert sc._match_letter(1, self.GBM, fifths) == ('C', 1)   # C#
        sig_map = sc._signature_letter_map(fifths)
        for pc in (6, 9, 1):
            letter, acc = sc._match_letter(pc, self.GBM, fifths)
            assert sc._accidental_kind(letter, acc, sig_map) is None


# --------------------------------------------------------------------------
# Ledger lines
# --------------------------------------------------------------------------

class TestLedgerLines:
    def test_middle_c_gets_exactly_one_ledger(self):
        # Middle C (60) defaults to the treble staff and needs one ledger below.
        song = make_song(make_chord("C", midi_notes=[60], chord_notes=C_MAJOR))
        _, ops = paint(song)
        ledgers = ink_ledgers(ops)
        assert len(ledgers) == 1
        geom = sc._geometry(130.0)
        expected_y = geom.y_for_index(sc._diatonic_index('C', 4), 'treble')
        assert abs(ledgers[0].points[0][1] - expected_y) < 1e-6

    def test_note_inside_staff_needs_no_ledger(self):
        cn = ChordNotes(notes=['B', 'D', 'F'], bass_note='B', root='B')
        song = make_song(make_chord("B", midi_notes=[71], chord_notes=cn))
        _, ops = paint(song)
        assert ink_ledgers(ops) == []


# --------------------------------------------------------------------------
# Second-interval collisions
# --------------------------------------------------------------------------

class TestSecondCollisions:
    def test_cluster_offsets_alternate(self):
        # C4-D4-E4 (60,62,64) on one staff: the middle note is pushed right.
        cn = ChordNotes(notes=['C', 'D', 'E'], bass_note='C', root='C')
        song = make_song(make_chord(
            "cluster", midi_notes=[60, 62, 64], chord_notes=cn, hand_split=0))
        _, ops = paint(song)
        heads = noteheads(ops)
        assert len(heads) == 3
        xs = sorted(round(o.x, 3) for o in heads)
        nh = ca.glyph_placement('notehead_whole', sc._geometry(130.0).staff_space)
        assert xs[0] == xs[1]
        assert abs((xs[2] - xs[0]) - nh.width) < 1e-2

    def test_third_apart_does_not_collide(self):
        song = make_song(make_chord(
            "C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, hand_split=0))
        _, ops = paint(song)
        xs = {round(o.x, 3) for o in noteheads(ops)}
        assert len(xs) == 1


# --------------------------------------------------------------------------
# Ensemble routing + tint by voice_staves / VOICE_COLORS
# --------------------------------------------------------------------------

class TestEnsembleRouting:
    def test_voiced_follows_voice_staves(self):
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'])
        pairs = [(m, st) for m, st, _ in sc._voiced(chord, song)]
        assert pairs == [(43, 'bass'), (55, 'bass'), (60, 'treble'), (64, 'treble')]

    def test_missing_voice_staves_falls_back_to_middle_c_split(self):
        chord = make_chord(
            "C", midi_notes=[48, 55, 64, 67],
            chord_notes=C_MAJOR, voice_notes=[48, 55, 64, 67])
        song = make_song(chord, voice_staves=None)
        pairs = [(m, st) for m, st, _ in sc._voiced(chord, song)]
        assert pairs == [(48, 'bass'), (55, 'bass'), (64, 'treble'), (67, 'treble')]

    def test_ensemble_notes_carry_per_voice_tint(self):
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'])
        _, ops = paint(song)
        heads = noteheads(ops)
        assert [color_of(o) for o in heads] == \
               [VOICE_COLORS[i].lstrip('#') for i in range(4)]

    def test_ensemble_notes_on_both_staves(self):
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'])
        _, ops = paint(song)
        geom = sc._geometry(130.0)
        between = geom.treble_bottom() + (geom.bass_top - geom.treble_bottom()) / 2.0
        centers = [note_center_y(o, geom.staff_space) for o in noteheads(ops)]
        assert any(c < between for c in centers)
        assert any(c > between for c in centers)


class TestPianoTints:
    def test_lh_and_rh_carry_hand_colors(self):
        song = make_song(make_chord(
            "C", midi_notes=[48, 60, 64, 67], chord_notes=C_MAJOR, hand_split=1))
        _, ops = paint(song)
        colors = [color_of(o) for o in noteheads(ops)]
        assert colors[0] == HAND_COLORS['lh'].lstrip('#')
        assert colors[1:] == [HAND_COLORS['rh'].lstrip('#')] * 3

    def test_plain_notes_use_default_ink(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        _, ops = paint(song)
        assert all(color_of(o) == NOTE_INK.lstrip('#') for o in noteheads(ops))


# --------------------------------------------------------------------------
# Key signatures
# --------------------------------------------------------------------------

class TestKeySignatures:
    def _header_accidentals(self, ops, kind):
        # The initial key signature is painted into the frozen gutter.
        return [o for o in accidentals(ops, kind) if "gutter" in o.tags]

    def test_key_fifths_mapping(self):
        assert sc._key_fifths('C') == 0
        assert sc._key_fifths('G') == 1
        assert sc._key_fifths('F') == -1
        assert sc._key_fifths('Eb') == -3
        assert sc._key_fifths('Am') == 0      # relative minor of C
        assert sc._key_fifths('Em') == 1      # relative minor of G
        assert sc._key_fifths(None) is None
        assert sc._key_fifths('H7?') is None  # unmappable

    def test_key_without_real_signature_takes_enharmonic_twin(self):
        # Style-preserving transposition used to produce these; users can also
        # type them. Each engraves as the enharmonic key that actually exists.
        assert sc._key_fifths('Gbm') == 3     # F#m
        assert sc._key_fifths('Dbm') == 4     # C#m
        assert sc._key_fifths('D#') == -3     # Eb
        assert sc._key_fifths('G#') == -4     # Ab
        assert sc._key_fifths('A#') == -2     # Bb

    def test_g_major_one_sharp_on_both_clefs(self):
        # C-major chord in G major: no note accidentals, so all sharps are the sig.
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='G'))
        ops = paint_gutter(song)
        sharps = self._header_accidentals(ops, 'sharp')
        assert len(sharps) == 2  # F# on treble and bass
        geom = sc._geometry(130.0)
        oy = ca.glyph_placement('accidental_sharp', geom.staff_space).origin_y
        ys = sorted(o.y + oy for o in sharps)
        expected = sorted([
            geom.y_for_index(sc._diatonic_index('F', 5), 'treble'),
            geom.y_for_index(sc._diatonic_index('F', 3), 'bass'),
        ])
        assert all(abs(a - b) < 1e-6 for a, b in zip(ys, expected))

    def test_f_major_one_flat_on_both_clefs(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='F'))
        ops = paint_gutter(song)
        flats = self._header_accidentals(ops, 'flat')
        assert len(flats) == 2  # Bb on treble and bass
        geom = sc._geometry(130.0)
        oy = ca.glyph_placement('accidental_flat', geom.staff_space).origin_y
        ys = sorted(o.y + oy for o in flats)
        expected = sorted([
            geom.y_for_index(sc._diatonic_index('B', 4), 'treble'),
            geom.y_for_index(sc._diatonic_index('B', 2), 'bass'),
        ])
        assert all(abs(a - b) < 1e-6 for a, b in zip(ys, expected))

    def test_eb_major_three_flats_per_clef(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='Eb'))
        ops = paint_gutter(song)
        flats = self._header_accidentals(ops, 'flat')
        assert len(flats) == 6  # B, E, A on both staves
        geom = sc._geometry(130.0)
        between = geom.treble_bottom() + (geom.bass_top - geom.treble_bottom()) / 2.0
        oy = ca.glyph_placement('accidental_flat', geom.staff_space).origin_y
        treble = [o for o in flats if (o.y + oy) < between]
        bass = [o for o in flats if (o.y + oy) > between]
        assert len(treble) == 3 and len(bass) == 3

    def test_unmappable_key_draws_no_signature(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='???'))
        _, ops = paint(song)
        assert not accidentals(ops, 'sharp')
        assert not accidentals(ops, 'flat')


# --------------------------------------------------------------------------
# Accidentals relative to the signature
# --------------------------------------------------------------------------

class TestAccidentalsVsSignature:
    def _one_note(self, names, midi, key):
        cn = ChordNotes(notes=names, bass_note=names[0], root=names[0])
        song = make_song(make_chord("x", midi_notes=[midi], chord_notes=cn, key=key))
        return paint(song)[1]

    def _note_accidentals(self, ops, kind):
        return [o for o in accidentals(ops, kind) if "header" not in o.tags]

    def test_sharp_matching_signature_draws_nothing(self):
        # F# in G major: matches the signature -> no accidental on the note.
        ops = self._one_note(['F#'], 66, 'G')
        assert self._note_accidentals(ops, 'sharp') == []
        assert self._note_accidentals(ops, 'natural') == []

    def test_natural_against_sharp_signature_draws_natural(self):
        # F natural in G major: deviates from F# -> a natural.
        ops = self._one_note(['F'], 65, 'G')
        assert len(self._note_accidentals(ops, 'natural')) == 1

    def test_flat_matching_signature_draws_nothing(self):
        # Bb in F major: matches the signature -> nothing.
        ops = self._one_note(['B-'], 70, 'F')
        assert self._note_accidentals(ops, 'flat') == []
        assert self._note_accidentals(ops, 'natural') == []

    def test_natural_against_flat_signature_draws_natural(self):
        # B natural in F major: deviates from Bb -> a natural.
        ops = self._one_note(['B'], 71, 'F')
        assert len(self._note_accidentals(ops, 'natural')) == 1

    def test_accidental_kind_helper(self):
        gmaj = sc._signature_letter_map(sc._key_fifths('G'))
        assert sc._accidental_kind('F', 1, gmaj) is None      # F# matches sig
        assert sc._accidental_kind('F', 0, gmaj) == 'natural'  # F natural deviates
        assert sc._accidental_kind('C', 1, gmaj) == 'sharp'    # C# not in sig
        assert sc._accidental_kind('C', 0, gmaj) is None       # C natural matches
        assert sc._accidental_kind('F', 2, gmaj) == 'text'     # double -> fallback


# --------------------------------------------------------------------------
# Key-aware respelling (notes spelled to match the signature)
# --------------------------------------------------------------------------

class TestKeyAwareRespelling:
    def _letters(self, song, chord):
        notes = sc._resolve_notes(chord, song)
        return [(n.letter, n.acc) for n in notes]

    def test_flat_spelled_chords_in_f_sharp_carry_no_accidentals(self):
        # The reported bug: F# major song whose chords are typed with flats
        # (Ebm/Db/B). Every note is diatonic to F# and must be respelled to the
        # sharp signature -- so the content draws ZERO note accidentals.
        song = render_song(["Ebm", "Db", "B"], "F#")
        _, ops = paint(song)
        assert content_accidental_ops(ops) == []
        assert noteheads(ops)  # notes are still drawn
        # Ebm's flat root (Eb, pc 3) is respelled D#, landing on the D letter,
        # not the E line it used to sit on.
        ebm_letters = self._letters(song, song.chords[0])
        assert ("D", 1) in ebm_letters
        assert all(letter != "E" for letter, _ in ebm_letters)
        # Db's flat root (Db, pc 1) is respelled C#, on the C letter.
        assert ("C", 1) in self._letters(song, song.chords[1])

    def test_gb_in_f_sharp_lands_on_f_sharp_without_accidental(self):
        song = render_song(["Gb"], "F#")
        _, ops = paint(song)
        assert content_accidental_ops(ops) == []
        # Gb (pc 6) -> F#; Bb (pc 10) -> A#; Db (pc 1) -> C#: all sharp-family.
        letters = self._letters(song, song.chords[0])
        assert ("F", 1) in letters
        assert all(acc >= 0 for _, acc in letters)  # no flats survive

    def test_flat_spelled_chords_in_e_flat_minor_carry_no_accidentals(self):
        # The second screenshot: Eb minor (relative of Gb major, 6 flats). The
        # same Ebm/Db/B progression is fully diatonic and draws no accidentals.
        song = render_song(["Ebm", "Db", "B"], "Ebm")
        _, ops = paint(song)
        assert content_accidental_ops(ops) == []
        # The "B" chord's B (pc 11) is diatonic here and respells to Cb (the C
        # letter with a flat) -- a non-natural letter the map must include.
        b_letters = self._letters(song, song.chords[2])
        assert ("C", -1) in b_letters
        assert all(letter != "B" for letter, _ in b_letters)

    def test_seam_pc11_in_gb_major_spells_cb_one_step_above_b4(self):
        # MIDI 71 is B4 by source spelling; in a 6-flat key (Eb minor / Gb
        # major) it is diatonic pc 11 and must spell Cb5 -- one diatonic step
        # ABOVE where B4 sits, with the octave crossing the enharmonic seam.
        cn = ChordNotes(notes=["B", "D#", "F#"], bass_note="B", root="B")
        letter, acc, idx = sc._spell(71, cn, sc._key_fifths("Ebm"))
        assert (letter, acc) == ("C", -1)
        assert idx == sc._diatonic_index("C", 5)
        assert idx == sc._diatonic_index("B", 4) + 1

    def test_chromatic_note_keeps_source_spelling_in_key(self):
        # Ebm in the key of C: none of Eb/Gb/Bb is diatonic, so the source flat
        # spelling (and its flat glyphs) survives -- rule 2 regression.
        cn = ChordNotes(notes=["Eb", "Gb", "Bb"], bass_note="Eb", root="Eb")
        song = make_song(make_chord(
            "Ebm", midi_notes=[63, 66, 70], chord_notes=cn, key="C"))
        _, ops = paint(song)
        letters = [(n.letter, n.acc) for n in sc._resolve_notes(song.chords[0], song)]
        assert letters == [("E", -1), ("G", -1), ("B", -1)]
        assert len(accidentals(ops, "flat")) == 3
        assert not accidentals(ops, "sharp")

    def test_genuinely_chromatic_note_gets_natural_against_sharp_signature(self):
        # Bm in F#: the D natural (pc 2) is chromatic (F# major has D#), so it
        # keeps its natural spelling and draws a NATURAL cancelling the sig's D#.
        song = render_song(["Bm"], "F#")
        _, ops = paint(song)
        accs = content_accidental_ops(ops)
        assert len(accs) >= 1
        assert all(o.key.startswith("glyph_accidental_natural") for o in accs)
        # The natural sits on the D letter, not the D# line's neighbour.
        d_notes = [n for n in sc._resolve_notes(song.chords[0], song)
                   if n.letter == "D"]
        assert d_notes and all(n.acc == 0 for n in d_notes)

    def test_flat_key_respells_sharp_source_to_signature(self):
        # Eb major with a sharp-spelled source (D#m): D# (pc 3) is diatonic and
        # respells to Eb, drawing no accidental.
        cn = ChordNotes(notes=["D#", "F#", "A#"], bass_note="D#", root="D#")
        song = make_song(make_chord(
            "D#m", midi_notes=[63], chord_notes=cn, key="Eb"))
        _, ops = paint(song)
        letters = [(n.letter, n.acc) for n in sc._resolve_notes(song.chords[0], song)]
        assert letters == [("E", -1)]  # D# -> Eb
        assert content_accidental_ops(ops) == []

    def test_fallback_direction_follows_signature_in_flat_key(self):
        # Key Ab (4 flats): a pitch class matched by neither rule 1 nor rule 2
        # (no chord_notes) falls back to a FLAT spelling, not a sharp.
        assert sc._match_letter(6, None, sc._key_fifths("Ab")) == ("G", -1)
        song = make_song(make_chord("?", midi_notes=[66], chord_notes=None, key="Ab"))
        _, ops = paint(song)
        assert len(accidentals(ops, "flat")) == 1
        assert not accidentals(ops, "sharp")

    def test_diatonic_map_contains_enharmonic_letters(self):
        # The map is built from the signature, so it carries non-natural letters
        # that live on the seam (F# major's E#, Gb major's Cb) rather than
        # skipping them.
        assert sc._diatonic_key_map(sc._key_fifths("F#"))[5] == ("E", 1)
        assert sc._diatonic_key_map(sc._key_fifths("Gb"))[11] == ("C", -1)
        assert sc._diatonic_key_map(None) == {}


# --------------------------------------------------------------------------
# Mid-song key change
# --------------------------------------------------------------------------

class TestKeyChange:
    def test_key_change_draws_double_barline_and_new_signature(self):
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='C'),
            make_chord("G", midi_notes=[55, 59, 62], chord_notes=C_MAJOR, key='G'),
        )
        layout, ops = paint(song)
        s = sc._geometry(130.0).staff_space
        lead = sc._key_change_lead(sc._key_fifths('G'), s)
        slot1 = layout.slots[1]
        # Two thin vertical staff-color lines sit in the lead region left of slot 1.
        change_lines = [o for o in vertical_lines(ops)
                        if slot1.x - lead - 1 <= o.points[0][0] <= slot1.x]
        assert len(change_lines) == 2
        # The initial key (C) has no signature, so the two sharps are the new one.
        assert len(accidentals(ops, 'sharp')) == 2

    def test_no_change_when_signature_is_unchanged(self):
        # C major -> A minor: same 0-accidental signature, no double barline.
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, key='C'),
            make_chord("Am", midi_notes=[57, 60, 64], chord_notes=C_MAJOR, key='Am'),
        )
        _, ops = paint(song)
        # Only the initial connecting barline is a vertical staff line.
        assert len(vertical_lines(ops)) == 1


# --------------------------------------------------------------------------
# Legend
# --------------------------------------------------------------------------

class TestLegend:
    def test_legend_present_for_satb(self):
        labels = ['Bass', 'Tenor', 'Alto', 'Soprano']
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'],
                         voice_labels=labels)
        _, ops = paint(song)
        legend = [o for o in ops.ops if isinstance(o, TextOp) and "legend" in o.tags]
        assert [o.s for o in legend] == labels
        assert [o.fill for o in legend] == [VOICE_COLORS[i] for i in range(4)]

    def test_no_legend_without_voice_labels(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        _, ops = paint(song)
        assert not [o for o in ops.ops if isinstance(o, TextOp) and "legend" in o.tags]


# --------------------------------------------------------------------------
# Clef image ops
# --------------------------------------------------------------------------

class TestClefOps:
    def test_clef_ops_present_in_gutter_and_keys_parseable(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        ops = paint_gutter(song)
        keys = {o.key for o in ops.ops if isinstance(o, ImageOp)}
        assert any(k.startswith('clef_treble:') for k in keys)
        assert any(k.startswith('clef_bass:') for k in keys)
        for key in keys:
            img = ca.image_for_clef_key(key)
            assert img is not None
            assert img.size[1] == int(key.split(':')[1])

    def test_content_has_no_clef_ops(self):
        # The clefs now live in the frozen gutter, never the scrolling content.
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        _, ops = paint(song)
        assert not [o for o in ops.ops
                    if isinstance(o, ImageOp) and o.key.startswith('clef_')]

    def test_treble_clef_reference_line_lands_on_g4(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        ops = paint_gutter(song)
        geom = sc._geometry(130.0)
        placement = ca.clef_placement('treble', geom.staff_space)
        treble_op = next(o for o in ops.ops
                         if isinstance(o, ImageOp) and o.key.startswith('clef_treble:'))
        g4_y = geom.y_for_index(sc._diatonic_index('G', 4), 'treble')
        assert abs((treble_op.y + placement.baseline_y) - g4_y) < 1e-6


# --------------------------------------------------------------------------
# Frozen gutter: width stability + scroll-aware key signature
# --------------------------------------------------------------------------

class TestGutter:
    def test_gutter_width_positive(self):
        renderer = StaffCardRenderer()
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        assert renderer.gutter_width(SheetContext(song=song), 130.0) > 0.0

    def test_gutter_width_fits_widest_signature_and_is_scroll_stable(self):
        # A song whose key changes C (0 sharps) -> B major (5 sharps): the
        # gutter must be sized for the widest signature so its width -- and thus
        # the content's left edge -- does not jump when scrolling past the change.
        renderer = StaffCardRenderer()
        c_only = make_song(make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, key='C'))
        two_key = make_song(
            make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, key='C'),
            make_chord("B", midi_notes=[59], chord_notes=C_MAJOR, key='B'),
        )
        w_plain = renderer.gutter_width(SheetContext(song=c_only), 130.0)
        w_two = renderer.gutter_width(SheetContext(song=two_key), 130.0)
        # The B-major signature is wider than the empty C signature.
        assert w_two > w_plain
        # gutter_width is a pure function of (ctx, height): it does not depend on
        # scroll, so painting at any scroll uses this same width.
        s = sc._staff_space(130.0)
        _, _, geom_w = sc._gutter_geometry(two_key, s)
        assert abs(geom_w - w_two) < 1e-9

    def test_gutter_signature_at_scroll_zero_is_initial_key(self):
        # Two-key song C -> G. At scroll 0 the first visible chord is in C:
        # no signature accidentals.
        song = make_song(
            make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, key='C'),
            make_chord("G", midi_notes=[55], chord_notes=C_MAJOR, key='G'),
        )
        ops = paint_gutter(song, scroll_x=0.0)
        assert not accidentals(ops, 'sharp')
        assert not accidentals(ops, 'flat')
        # The clefs are always present regardless of scroll.
        assert any(o.key.startswith('clef_treble:')
                   for o in ops.ops if isinstance(o, ImageOp))

    def test_gutter_signature_follows_scroll_past_key_change(self):
        # Scrolled past the C chord to the G chord's slot: the gutter shows the
        # NEW key's signature (one sharp on each staff).
        song = make_song(
            make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, key='C'),
            make_chord("G", midi_notes=[55], chord_notes=C_MAJOR, key='G'),
        )
        renderer = StaffCardRenderer()
        ctx = SheetContext(song=song)
        layout = renderer.layout(ctx, 130.0)
        scroll_x = layout.slots[1].x + 1.0  # firmly inside the G slot
        ops = paint_gutter(song, scroll_x=scroll_x)
        assert len(accidentals(ops, 'sharp')) == 2  # F# treble + bass
        assert not accidentals(ops, 'flat')


# --------------------------------------------------------------------------
# Zoom
# --------------------------------------------------------------------------

class TestZoom:
    def test_supports_zoom_declared(self):
        assert StaffCardRenderer.supports_zoom is True

    def test_staff_space_scales_with_zoom_within_clamps(self):
        # At height 130 both zoom 1.0 and 2.0 stay within the staff-space clamps,
        # so the staff space doubles.
        s1 = sc._staff_space(130.0, 1.0)
        s2 = sc._staff_space(130.0, 2.0)
        assert sc._MIN_STAFF_SPACE < s1 < sc._MAX_STAFF_SPACE
        assert sc._MIN_STAFF_SPACE < s2 < sc._MAX_STAFF_SPACE
        assert abs(s2 - 2.0 * s1) < 1e-9
        # Geometry derived from the staff space scales too.
        g1 = sc._geometry(130.0, 1.0)
        g2 = sc._geometry(130.0, 2.0)
        assert abs(g2.staff_space - 2.0 * g1.staff_space) < 1e-9

    def test_layout_width_grows_with_zoom(self):
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, duration_beats=2.0),
            make_chord("G", midi_notes=[55, 59, 62], chord_notes=C_MAJOR, duration_beats=2.0),
        )
        l1, _ = paint(song, zoom=1.0)
        l2, _ = paint(song, zoom=2.0)
        assert l2.width > l1.width
        assert l2.slots[0].width > l1.slots[0].width

    def test_gutter_width_grows_with_zoom(self):
        renderer = StaffCardRenderer()
        song = make_song(make_chord("C", midi_notes=[60], chord_notes=C_MAJOR, key='G'))
        w1 = renderer.gutter_width(SheetContext(song=song, zoom=1.0), 130.0)
        w2 = renderer.gutter_width(SheetContext(song=song, zoom=2.0), 130.0)
        assert w2 > w1


# --------------------------------------------------------------------------
# Clef / glyph asset API
# --------------------------------------------------------------------------

class TestClefAssets:
    def test_downscaled_clef_bases_within_bound(self):
        for kind in ('treble', 'bass'):
            assert ca._CLEF_BASE[kind].height <= 256

    def test_downscaled_glyph_bases_within_bound(self):
        assert ca._GLYPH_BASE['notehead_whole'].height <= 64
        for name in ('accidental_sharp', 'accidental_flat', 'accidental_natural'):
            assert ca._GLYPH_BASE[name].height <= 160

    def test_get_clef_image_matches_placement_height(self):
        for kind in ('treble', 'bass'):
            img = ca.get_clef_image(kind, 9.0)
            placement = ca.clef_placement(kind, 9.0)
            assert img.size == (placement.width, placement.height)

    def test_clef_anchor_scales_proportionally(self):
        for kind in ('treble', 'bass'):
            small = ca.clef_placement(kind, 8.0)
            big = ca.clef_placement(kind, 16.0)
            assert abs(big.height / small.height - 2.0) < 0.05
            assert abs(big.baseline_y / small.baseline_y - 2.0) < 0.05

    def test_glyph_placement_scales_and_round_trips(self):
        for name in ('notehead_whole', 'accidental_sharp',
                     'accidental_flat', 'accidental_natural'):
            pl = ca.glyph_placement(name, 10.0)
            img = ca.image_for_clef_key(pl.key)
            assert img is not None
            assert img.size == (pl.width, pl.height)

    def test_glyph_origin_scales_proportionally(self):
        small = ca.glyph_placement('accidental_sharp', 8.0)
        big = ca.glyph_placement('accidental_sharp', 16.0)
        assert abs(big.origin_y / small.origin_y - 2.0) < 0.05

    def test_tinted_glyph_key_resolves(self):
        pl = ca.glyph_placement('notehead_whole', 12.0, '#3a5a8a')
        assert pl.key.endswith(':3a5a8a')
        img = ca.image_for_clef_key(pl.key)
        assert img is not None and img.size == (pl.width, pl.height)
        # Tint recolors the ink to the requested rgb (kept where alpha > 0).
        r, g, b, _ = img.getpixel((0, img.size[1] // 2))
        assert (r, g, b) == (0x3a, 0x5a, 0x8a)

    def test_tint_accepts_bare_and_hash_prefixed_colors(self):
        assert ca.glyph_placement('notehead_whole', 12.0, 'a04848').key.endswith(':a04848')
        assert ca.glyph_placement('notehead_whole', 12.0, '#A04848').key.endswith(':a04848')

    def test_malformed_clef_keys_return_none(self):
        for bad in ('', 'clef_treble', 'clef_treble:', 'clef_foo:10',
                    'clef_treble:abc', 'clef_treble:0', 'nope:10'):
            assert ca.image_for_clef_key(bad) is None

    def test_malformed_glyph_keys_return_none(self):
        for bad in ('glyph_notehead_whole', 'glyph_notehead_whole:',
                    'glyph_bogus:64', 'glyph_notehead_whole:0',
                    'glyph_notehead_whole:64:xyz', 'glyph_notehead_whole:64:3a5a8',
                    'glyph_notehead_whole:64:3a5a8a:9'):
            assert ca.image_for_clef_key(bad) is None

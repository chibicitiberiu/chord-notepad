"""Headless tests for the grand-staff :class:`StaffCardRenderer`.

Every test inspects the recorded :class:`DrawOps` (no Tk/display): one slot per
chord with slim rests; whole notes as hollow ovals split across the two staves;
diatonic placement and accidentals driven by spelling (Bb/F#, the B#/Cb seam);
ledger lines for middle C; second-interval collision offsets; ensemble routing
by ``voice_staves``; parseable clef image ops; and the clef-asset scaling API.
"""
from typing import List, Optional

from models.chord import ChordInfo
from models.chord_notes import ChordNotes
from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.ops import DrawOps, ImageOp, LineOp, OvalOp, TextOp
from ui.chord_sheet.renderer_interface import SheetContext
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
        duration_beats=1.0,
        start_time=0.0,
        duration_seconds=0.0,
        bpm=120,
        time_sig=(4, 4),
        key=None,
        bar=1,
        is_rest=is_rest,
        voice_notes=voice_notes,
        hand_split=hand_split,
    )


def make_song(*chords: RenderedChord, voice_staves=None) -> RenderedSong:
    return RenderedSong(chords=list(chords), voice_staves=voice_staves)


def paint(song: RenderedSong, height: float = 120.0):
    renderer = StaffCardRenderer()
    ctx = SheetContext(song=song)
    layout = renderer.layout(ctx, height)
    ops = DrawOps()
    renderer.paint(ops, ctx, layout)
    return layout, ops


def ovals(ops) -> List[OvalOp]:
    return [o for o in ops.ops if isinstance(o, OvalOp)]


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

    def test_rest_slot_is_slim_and_empty(self):
        song = make_song(
            make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR),
            make_chord("NC", is_rest=True),
        )
        layout, ops = paint(song)
        chord_slot, rest_slot = layout.slots
        assert rest_slot.width == REST_WIDTH
        assert rest_slot.width < chord_slot.width
        # The rest emits no noteheads and no clefs.
        rest_tag = "slot:1"
        rest_ops = [o for o in ops.ops if rest_tag in o.tags]
        assert not any(isinstance(o, (OvalOp, ImageOp)) for o in rest_ops)

    def test_geometry_is_pure_function_of_height(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        (l1, o1), (l2, o2) = paint(song, 120.0), paint(song, 120.0)
        assert l1.slots[0].width == l2.slots[0].width
        assert [type(o) for o in o1.ops] == [type(o) for o in o2.ops]


# --------------------------------------------------------------------------
# Whole notes across both staves
# --------------------------------------------------------------------------

class TestPianoChordBothStaves:
    def test_hollow_ovals_on_both_staves_lh_below(self):
        # LH bass note 48 (C3), RH 60/64/67; hand_split=1.
        song = make_song(make_chord(
            "C", midi_notes=[48, 60, 64, 67], chord_notes=C_MAJOR, hand_split=1))
        _, ops = paint(song)
        heads = ovals(ops)
        assert len(heads) == 4
        assert all(o.fill is None and o.outline == sc._INK for o in heads)  # hollow

        geom = sc._geometry(120.0)
        # The bass staff spans below the treble staff; the LH note (C3) sits
        # lower (greater y) than every right-hand note.
        centers = sorted(o.y + o.h / 2.0 for o in heads)
        bass_split = geom.treble_top + 5.0 * geom.staff_space  # between staves
        lh = [c for c in centers if c > bass_split]
        rh = [c for c in centers if c <= bass_split]
        assert len(lh) == 1 and len(rh) == 3
        assert min(lh) > max(rh)


# --------------------------------------------------------------------------
# Spelling: accidentals + diatonic position
# --------------------------------------------------------------------------

class TestSpellingAccidentals:
    def _note_center_y_at_index(self, ops, geom, diatonic_index):
        target = geom.y_for_index(diatonic_index)
        return [o for o in ovals(ops)
                if abs((o.y + o.h / 2.0) - target) < 1e-6]

    def test_flat_sits_on_letter_position_with_flat_glyph(self):
        # Bb (MIDI 70) must land on the B position (not A#) with a flat glyph.
        cn = ChordNotes(notes=['B-', 'D', 'F'], bass_note='B-', root='B-')
        song = make_song(make_chord("Bb", midi_notes=[70], chord_notes=cn))
        _, ops = paint(song)
        geom = sc._geometry(120.0)
        b_index = sc._diatonic_index('B', 4)  # Bb4 -> B position, octave 4
        assert self._note_center_y_at_index(ops, geom, b_index)
        flats = [o for o in ops.ops if isinstance(o, TextOp) and o.s == '♭']
        assert len(flats) == 1

    def test_sharp_sits_on_letter_position_with_sharp_glyph(self):
        # F# (MIDI 66) must land on the F position with a sharp glyph.
        cn = ChordNotes(notes=['F#', 'A', 'C#'], bass_note='F#', root='F#')
        song = make_song(make_chord("F#", midi_notes=[66], chord_notes=cn))
        _, ops = paint(song)
        geom = sc._geometry(120.0)
        f_index = sc._diatonic_index('F', 4)  # F#4 -> F position, octave 4
        assert self._note_center_y_at_index(ops, geom, f_index)
        sharps = [o for o in ops.ops if isinstance(o, TextOp) and o.s == '♯']
        assert len(sharps) == 1

    def test_unmatched_pitch_class_defaults_to_sharp(self):
        # No chord_notes: a black-key MIDI note falls back to a sharp spelling.
        song = make_song(make_chord("?", midi_notes=[66], chord_notes=None))
        _, ops = paint(song)
        assert any(isinstance(o, TextOp) and o.s == '♯' for o in ops.ops)


class TestEnharmonicSeam:
    def test_b_sharp_lands_below_middle_c(self):
        # B#3 sounds as MIDI 60 but is spelled on the B position below middle C.
        cn = ChordNotes(notes=['B#', 'D#', 'F##'], bass_note='B#', root='B#')
        _letter, acc, idx = sc._spell(60, cn)
        assert (_letter, acc) == ('B', 1)
        assert idx == sc._diatonic_index('B', 3)  # 27, one step below C4 (28)
        assert idx < sc._diatonic_index('C', 4)

    def test_c_flat_lands_on_c5_position(self):
        # Cb5 sounds as MIDI 71 but is spelled on the C5 position with a flat.
        cn = ChordNotes(notes=['C-', 'E-', 'G-'], bass_note='C-', root='C-')
        _letter, acc, idx = sc._spell(71, cn)
        assert (_letter, acc) == ('C', -1)
        assert idx == sc._diatonic_index('C', 5)  # 35, above B4 (34)
        assert idx > sc._diatonic_index('B', 4)


# --------------------------------------------------------------------------
# Ledger lines
# --------------------------------------------------------------------------

class TestLedgerLines:
    def test_middle_c_gets_exactly_one_ledger(self):
        # Middle C (60) defaults to the treble staff (>= 60) and needs one
        # ledger line below it.
        song = make_song(make_chord("C", midi_notes=[60], chord_notes=C_MAJOR))
        _, ops = paint(song)
        ledgers = ink_ledgers(ops)
        assert len(ledgers) == 1
        geom = sc._geometry(120.0)
        expected_y = geom.y_for_index(sc._diatonic_index('C', 4))
        assert abs(ledgers[0].points[0][1] - expected_y) < 1e-6

    def test_note_inside_staff_needs_no_ledger(self):
        # B4 (71) sits on the treble middle line -> no ledger.
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
        # Force all three onto the treble staff via a hand_split of 0.
        song = make_song(make_chord(
            "cluster", midi_notes=[60, 62, 64], chord_notes=cn, hand_split=0))
        _, ops = paint(song)
        heads = ovals(ops)
        assert len(heads) == 3
        xs = sorted(round(o.x, 3) for o in heads)
        geom = sc._geometry(120.0)
        # Two noteheads share the base column; one is offset a notehead-width.
        assert xs[0] == xs[1]
        assert abs((xs[2] - xs[0]) - geom.notehead_w) < 1e-2

    def test_third_apart_does_not_collide(self):
        # C4-E4-G4 (a triad, all thirds) never offsets: one shared column.
        song = make_song(make_chord(
            "C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR, hand_split=0))
        _, ops = paint(song)
        xs = {round(o.x, 3) for o in ovals(ops)}
        assert len(xs) == 1


# --------------------------------------------------------------------------
# Ensemble routing by voice_staves
# --------------------------------------------------------------------------

class TestEnsembleRouting:
    def test_note_staves_follow_voice_staves(self):
        # voice_notes low-to-high; voice_staves aligned low-to-high.
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'])
        pairs = sc._note_staves(chord, song)
        assert pairs == [(43, 'bass'), (55, 'bass'), (60, 'treble'), (64, 'treble')]

    def test_missing_voice_staves_falls_back_to_middle_c_split(self):
        chord = make_chord(
            "C", midi_notes=[48, 55, 64, 67],
            chord_notes=C_MAJOR, voice_notes=[48, 55, 64, 67])
        song = make_song(chord, voice_staves=None)
        pairs = sc._note_staves(chord, song)
        assert pairs == [(48, 'bass'), (55, 'bass'), (64, 'treble'), (67, 'treble')]

    def test_ensemble_song_paints_notes_on_both_staves(self):
        chord = make_chord(
            "C", midi_notes=[43, 55, 60, 64],
            chord_notes=C_MAJOR, voice_notes=[43, 55, 60, 64])
        song = make_song(chord, voice_staves=['bass', 'bass', 'treble', 'treble'])
        _, ops = paint(song, 140.0)
        geom = sc._geometry(140.0)
        between = geom.treble_top + 5.0 * geom.staff_space
        centers = [o.y + o.h / 2.0 for o in ovals(ops)]
        assert any(c < between for c in centers)   # treble
        assert any(c > between for c in centers)   # bass


# --------------------------------------------------------------------------
# Clef image ops
# --------------------------------------------------------------------------

class TestClefOps:
    def test_clef_ops_present_and_keys_parseable(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        _, ops = paint(song)
        clefs = [o for o in ops.ops if isinstance(o, ImageOp)]
        keys = {o.key for o in clefs}
        assert any(k.startswith('clef_treble:') for k in keys)
        assert any(k.startswith('clef_bass:') for k in keys)
        for key in keys:
            img = ca.image_for_clef_key(key)
            assert img is not None
            # Key height matches the image it resolves to.
            assert img.size[1] == int(key.split(':')[1])

    def test_treble_clef_reference_line_lands_on_g4(self):
        song = make_song(make_chord("C", midi_notes=[60, 64, 67], chord_notes=C_MAJOR))
        _, ops = paint(song)
        geom = sc._geometry(120.0)
        placement = ca.clef_placement('treble', geom.staff_space)
        treble_op = next(o for o in ops.ops
                         if isinstance(o, ImageOp) and o.key.startswith('clef_treble:'))
        g4_y = geom.y_for_index(sc._diatonic_index('G', 4))
        assert abs((treble_op.y + placement.baseline_y) - g4_y) < 1e-6


# --------------------------------------------------------------------------
# Clef asset API
# --------------------------------------------------------------------------

class TestClefAssets:
    def test_downscaled_bases_within_bound(self):
        for kind in ('treble', 'bass'):
            assert ca._CLEF_BASE[kind].height <= 256

    def test_get_clef_image_matches_placement_height(self):
        for kind in ('treble', 'bass'):
            img = ca.get_clef_image(kind, 9.0)
            placement = ca.clef_placement(kind, 9.0)
            assert img.size[1] == placement.height
            assert img.size[0] == placement.width

    def test_anchor_scales_proportionally_with_size(self):
        for kind in ('treble', 'bass'):
            small = ca.clef_placement(kind, 8.0)
            big = ca.clef_placement(kind, 16.0)
            # Doubling the staff space doubles height, width, and the baseline.
            assert abs(big.height / small.height - 2.0) < 0.05
            assert abs(big.width / small.width - 2.0) < 0.06
            assert abs(big.baseline_y / small.baseline_y - 2.0) < 0.05

    def test_image_for_key_round_trips_placement_key(self):
        placement = ca.clef_placement('bass', 10.0)
        img = ca.image_for_clef_key(placement.key)
        assert img is not None
        assert img.size == (placement.width, placement.height)

    def test_malformed_keys_return_none(self):
        for bad in ('', 'clef_treble', 'clef_treble:', 'clef_foo:10',
                    'clef_treble:abc', 'clef_treble:0', 'nope:10'):
            assert ca.image_for_clef_key(bad) is None

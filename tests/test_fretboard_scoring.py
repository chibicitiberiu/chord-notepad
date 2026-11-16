"""The fretboard search prefers the shapes guitarists play (C11).

Pass 2 found B = x21x02, F = 10321x and G#m7 = 421102 in standard tuning:
right notes, grips nobody uses. The scoring now counts fingers rather than
notes (a barre is one finger), earns the open-string bonus only in open
position, charges an open string sandwiched between fretted strings up the
neck, a grip that needs every finger with two of them side by side on the
lowest fret, and a mute that isn't next to the bass.

The engine has no shape list. The chord-book shapes below are an oracle the
search is measured against, nothing more: every rule is about hands and
strings, so the same rules run on any tuning.
"""

import pytest

from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.chord.helper import ChordHelper
from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec

_HELPER = ChordHelper()

#: Chord-book shapes for standard tuning, several per chord (test oracle).
STANDARD_BOOK = {
    'C': 'x32010 x35553 332010', 'C#': 'x46664 x43121 xx3121',
    'D': 'xx0232 x57775 x00232', 'Eb': 'x68886 xx1343', 'E': '022100 x79997',
    'F': '133211 xx3211', 'F#': '244322 xx4322', 'G': '320003 320033 355433 3x0033 3x0003',
    'Ab': '466544 xx6544', 'A': 'x02220 577655', 'Bb': 'x13331 688766 xx3331',
    'B': 'x24442 799877 xx4442',
    'Cm': 'x35543', 'C#m': 'x46654', 'Dm': 'xx0231 x57765 x00231',
    'Ebm': 'x68876 xx1342', 'Em': '022000', 'Fm': '133111 xx3111', 'F#m': '244222 xx4222',
    'Gm': '355333 xx5333', 'Abm': '466444 xx6444', 'Am': 'x02210 577555',
    'Bbm': 'x13321 688666 xx3321', 'Bm': 'x24432 799777 xx4432',
    'C7': 'x32310 x35353', 'C#7': 'x46464 x43424', 'D7': 'xx0212 x57575 x00212',
    'Eb7': 'x68686 xx1323', 'E7': '020100 022130 020130', 'F7': '131211 xx1211',
    'F#7': '242322', 'G7': '320001 353433', 'Ab7': '464544', 'A7': 'x02020 x02223 575655',
    'Bb7': 'x13131 686766', 'B7': 'x21202 x24242',
    'Cm7': 'x35343 x3134x', 'C#m7': 'x46454', 'Dm7': 'xx0211 x57565', 'Ebm7': 'x68676 xx1322',
    'Em7': '020000 022030 022033 020030', 'Fm7': '131111 xx1111', 'F#m7': '242222 2x222x',
    'Gm7': '353333 3x333x', 'Abm7': '464444 4x444x', 'Am7': 'x02010 575555',
    'Bbm7': 'x13121 686666', 'Bm7': 'x20202 x24232',
    'Cmaj7': 'x32000 x35453', 'C#maj7': 'x46564 x43111', 'Dmaj7': 'xx0222 x57675',
    'Ebmaj7': 'x68786 xx1333', 'Emaj7': '021100', 'Fmaj7': 'xx3210 1x221x 133210 x33210',
    'F#maj7': '2x332x xx4321', 'Gmaj7': '320002 3x443x', 'Abmaj7': '4x554x xx6543',
    'Amaj7': 'x02120', 'Bbmaj7': 'x13231 6x776x', 'Bmaj7': 'x24342 7x887x',
}

#: Chord-book shapes for ukulele (G C E A), string order (test oracle).
UKULELE_BOOK = {
    'C': '0003', 'D': '2220', 'E': '4442 1402', 'F': '2010', 'G': '0232', 'A': '2100',
    'B': '4322', 'Bb': '3211', 'Eb': '0331 3331', 'Am': '2000', 'Dm': '2210', 'Em': '0432',
    'Gm': '0231', 'F#m': '2120', 'Cm': '0333', 'C7': '0001', 'G7': '0212', 'D7': '2223 2020',
    'A7': '0100', 'E7': '1202', 'B7': '2322', 'Bb7': '1211',
}


def shape(fingering):
    return ''.join('x' if f < 0 else str(f) if f < 10 else f'({f})' for f in fingering)


def best(picker, chord):
    notes = _HELPER.compute_chord_notes(chord)
    picker.reset()
    return shape(picker._find_best_fingering(notes.notes, notes.bass_note))


def frets(text):
    return [-1 if c == 'x' else int(c) for c in text]


@pytest.fixture(scope="module")
def guitar():
    return GuitarChordPicker(BUILTIN_FRETBOARDS['standard'])


@pytest.mark.parametrize("chord, reported", [
    ('B', 'x21x02'), ('F', '10321x'), ('G#m7', '421102'),
])
def test_the_reported_shapes_lose_to_chord_book_ones(guitar, chord, reported):
    found = best(guitar, chord)
    assert found != reported
    assert found in STANDARD_BOOK[chord.replace('G#', 'Ab')].split()


def test_the_reported_shapes_in_a_song(guitar):
    # Pass 2 saw them in the chord sheet, through the whole-song search.
    chords = ['C', 'G', 'Am', 'F', 'B', 'E', 'F#m', 'G#m7']
    voiced = guitar.voice_sequence_details([_HELPER.compute_chord_notes(c) for c in chords])
    shapes = dict(zip(chords, (shape(v.fingering) for v in voiced)))
    assert shapes['B'] != 'x21x02' and shapes['F'] != '10321x' and shapes['G#m7'] != '421102'


def test_most_chords_get_a_chord_book_shape(guitar):
    # 30 of these 60 before the change, 50 after; the rest are fine grips
    # the books don't list (C#m x46650, Gm 310033).
    hits = [c for c, shapes in STANDARD_BOOK.items() if best(guitar, c) in shapes.split()]
    assert len(hits) >= 50, sorted(set(STANDARD_BOOK) - set(hits))


@pytest.mark.parametrize("chord", [
    # Chord-book shapes the search found before the change: kept.
    'C', 'D', 'E', 'G', 'A', 'F#', 'Ab', 'Dm', 'Em', 'Am', 'Fm', 'D7', 'E7', 'G7', 'A7',
    'B7', 'Eb7', 'Dm7', 'Em7', 'Am7', 'Bm7', 'Fm7', 'Ebm7', 'Cmaj7', 'Dmaj7', 'Emaj7',
    'Gmaj7', 'Amaj7', 'Ebmaj7', 'Ab7',
])
def test_the_open_chords_stay(guitar, chord):
    assert best(guitar, chord) in STANDARD_BOOK[chord].split()


def test_ukulele_gets_its_chord_book_shapes():
    uke = GuitarChordPicker(BUILTIN_FRETBOARDS['ukulele'])
    hits = [c for c, shapes in UKULELE_BOOK.items() if best(uke, c) in shapes.split()]
    # F was 5550 and Em 0402 before; both are book shapes now.
    assert {'F', 'Em', 'C', 'G', 'G7'} <= set(hits)
    assert len(hits) >= 18


def test_open_g_plays_its_barres_across():
    open_g = GuitarChordPicker(BUILTIN_FRETBOARDS['open_g'])
    assert best(open_g, 'C') == 'x55555'
    assert best(open_g, 'A') == 'x22222'


def test_dadgad_keeps_its_drones():
    # Open strings ringing beside a shape up the neck are free.
    dadgad = GuitarChordPicker(BUILTIN_FRETBOARDS['dadgad'])
    assert best(dadgad, 'D/F#') == '400200'


class TestRules:
    """Each rule on its own, on shapes picked to isolate it."""

    def score(self, picker, chord, text):
        notes = _HELPER.compute_chord_notes(chord)
        return picker._score_quality(frets(text), notes.notes, notes.bass_note)

    def test_a_barre_is_one_finger(self, guitar):
        # x24442: five fretted notes, four fingers (barre, ring mini-barre
        # counted note by note, so barre + 3).
        assert self.score(guitar, 'B', 'x24442') > self.score(guitar, 'B', 'x21x02')

    def test_no_open_bonus_up_the_neck(self, guitar):
        # The same open e, in open position and at the 6th fret.
        low = self.score(guitar, 'Em', '022000') - self.score(guitar, 'Em', '02200x')
        high = self.score(guitar, 'C#m', 'x46650') - self.score(guitar, 'C#m', 'x4665x')
        assert low > high

    def test_an_open_string_sandwiched_up_the_neck(self, guitar):
        assert self.score(guitar, 'Eb', 'x68886') > self.score(guitar, 'Eb', 'x65046')

    def test_a_cramped_grip(self, guitar):
        # F 10321x needs four fingers, two on fret 1 with no barre possible.
        assert self.score(guitar, 'F', '133211') > self.score(guitar, 'F', '10321x')

    def test_a_mute_next_to_the_bass_is_cheaper(self, guitar):
        # G 3x0033 (A damped by the bass finger) vs a mute inside the shape.
        picker = guitar
        next_to_bass = self.score(picker, 'G', '3x0033') - self.score(picker, 'G', '320033')
        inside = self.score(picker, 'G', '32x033') - self.score(picker, 'G', '320033')
        assert next_to_bass > inside

    def test_only_a_fretted_bass_finger_damps(self, guitar):
        # Above an open bass no finger damps the mute; under an index barre
        # reaching past it the barre would sound it. Both cost a buried mute.
        w = guitar.spec.weights
        assert w['damped_mute_penalty'] > 2 * w['interior_mute_penalty']
        damps = guitar._bass_finger_damps
        assert damps(frets('3x0033'), 0, [0, 4, 5])
        assert damps(frets('2x0232'), 0, [0, 3, 4, 5])
        assert damps(frets('4x2100'), 0, [0, 2, 3])
        assert not damps(frets('0x2010'), 0, [2, 4])
        assert not damps(frets('1x1211'), 0, [0, 2, 3, 4, 5])
        assert not damps(frets('3x3333'), 0, [0, 2, 3, 4, 5])

    def test_the_thumb_takes_a_low_bass(self, guitar):
        # D/F# 2x0232: four fingers, three on fret 2 with no barre, unless
        # the thumb over the neck frets the F# and damps the A string.
        w = guitar.spec.weights
        thumb = self.score(guitar, 'D/F#', '2x0232')
        cramped = (w['sounding_string_bonus'] * 5 + w['open_string_bonus']
                   + w['slash_bass_bonus'] + w['span_penalty'] + w['position_penalty'] * 9 / 4
                   + w['fretted_finger_penalty'] * 4 + w['damped_mute_penalty']
                   + w['awkward_stretch_penalty'])
        assert thumb == pytest.approx(cramped - w['awkward_stretch_penalty']
                                      - w['fretted_finger_penalty'])
        # Not with the next string ringing (F 10321x), not on the second
        # string (Bb x10331), not high up (fret 4 and above).
        take = guitar._thumb_frets_bass
        assert take(frets('2x0232'), 0, [0, 3, 4, 5])
        assert not take(frets('10321x'), 0, [0, 2, 3, 4])
        assert not take(frets('x10331'), 1, [1, 3, 4, 5])
        assert not take(frets('4x4554'), 0, [0, 2, 3, 4, 5])

    def test_a_thin_shape(self, guitar):
        # Three strings of six (Bb/F 110xxx) pay once on top of the strings
        # they lose; four don't. Not a power chord (two notes).
        w = guitar.spec.weights['thin_shape_penalty']
        assert w < 0
        assert guitar._full_strum_strings() == 4
        assert GuitarChordPicker(BUILTIN_FRETBOARDS['ukulele'])._full_strum_strings() == 3
        free = GuitarChordPicker(FretboardSpec.from_dict(
            'free', {'tuning': list(guitar.tuning_midi), 'weights': {'thin_shape_penalty': 0}}))
        for chord, shape_, charged in (('Bb/F', '110xxx', True), ('Bb/F', '1103xx', False),
                                       ('E5', '022xxx', False)):
            delta = self.score(guitar, chord, shape_) - self.score(free, chord, shape_)
            assert delta == pytest.approx(w if charged else 0.0), (chord, shape_)

    def test_the_thumb_measures_from_the_capo(self, guitar):
        # With a capo the picker's frets are capo-relative: the thumb rule
        # reads them as they are.
        capo = guitar.with_capo(5)
        assert capo._thumb_frets_bass(frets('2x0232'), 0, [0, 3, 4, 5])
        assert not capo._thumb_frets_bass(frets('7x5787'), 0, [0, 2, 3, 4, 5])

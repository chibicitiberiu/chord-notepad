"""A barre by the ring finger or pinky, above the index (the 9th-grip bug).

The playability model only knew a barre on the lowest fret, so a grip whose
index frets one low note while another finger lies across the top strings a
fret or two higher was rejected: E9 076777 (index D6, middle A7, ring across
G B e at 7), C9 x32333, D9 x54555. The engine then offered thinner or wider
shapes instead. ``GuitarChordPicker._finger_plan`` now models the hand: the
index on the lowest fret, the other fingers up the neck, and a ring finger or
pinky flattened over two or three strings when the fingers run out.

The engine has no shape list. The grips below are an oracle from the chord
book (written by hand, not by running the code), checked both ways: the
standard grips become candidates, and variants a hand can't hold stay out.
"""

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec

_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
_NINTH = [0, 4, 7, 10, 2]
_MINOR_NINTH = [0, 3, 7, 10, 2]


def frets(text):
    """'x32333' / 'x(12)(11)...' -> per-string frets, low string first."""
    out, i = [], 0
    while i < len(text):
        if text[i] == '(':
            j = text.index(')', i)
            out.append(int(text[i + 1:j]))
            i = j + 1
        else:
            out.append(-1 if text[i] == 'x' else int(text[i]))
            i += 1
    return out


def shape(fingering):
    return ''.join('x' if f < 0 else str(f) if f < 10 else f'({f})' for f in fingering)


def chord(root, intervals):
    r = _NAMES.index(root)
    return [_NAMES[(r + i) % 12] for i in intervals]


@pytest.fixture(scope="module")
def guitar():
    return GuitarChordPicker(BUILTIN_FRETBOARDS['standard'])


#: Chord-book grips that need a ring/pinky barre above the index (oracle).
FINGER_BARRE_GRIPS = [
    ('E', _NINTH, '076777'),               # ring across G B e at 7
    ('C', _NINTH, 'x32333'),
    ('D', _NINTH, 'x54555'),
    ('B', _NINTH, 'x21222'),
    ('A', _NINTH, 'x(12)(11)(12)(12)(12)'),
    ('C', _MINOR_NINTH, 'x31333'),         # index D1, ring across G B e at 3
    ('D', _MINOR_NINTH, 'x53555'),
]


@pytest.mark.parametrize("root, intervals, grip", FINGER_BARRE_GRIPS,
                         ids=[g[2] for g in FINGER_BARRE_GRIPS])
def test_the_ninth_grips_are_candidates(guitar, root, intervals, grip):
    notes = chord(root, intervals)
    assert guitar._is_playable(frets(grip))
    assert frets(grip) in guitar._build_candidate_ladder(notes, root)


@pytest.mark.parametrize("grip", [
    'x32355',    # C13: pinky across B e at 5
    'x32335',    # C13 with the 9th: ring across G B at 3, pinky e5
    '3x3455',    # G13: index across E-D at 3 (playable before too)
    '1x1233',    # F13
    'x3534x',    # Cm7, four fingers
    'x35343',    # Cm7, A-shape barre
    '133211',    # F, full barre
])
def test_playable_grips(guitar, grip):
    assert guitar._is_playable(frets(grip))


@pytest.mark.parametrize("grip, why", [
    ('x32343', 'five fingers: no run of strings shares a fret above the index'),
    ('12345x', 'five fingers, one per fret'),
    ('1x3333', 'a ring/pinky barre over four strings'),
    ('x57777', 'a ring/pinky barre over four strings'),
    ('133233', 'A D at 3 cannot share a finger (it would lie on G2): five fingers'),
    ('33323x', 'the flat finger across E A D at 3 would lie on G2'),
    ('x21322', 'G3 fretted higher on the bass side of the B e barre'),
    ('x23345', 'two fingers above the barre: it would be the middle finger'),
    ('x51555', 'a finger barre four frets from the index'),
    ('x3233(8)', 'wider than the span limit'),
    ('103311', 'open A inside the index barre'),
])
def test_unplayable_grips(guitar, grip, why):
    assert not guitar._is_playable(frets(grip)), why


def test_a_finger_barre_counts_its_fingers(guitar):
    # Index D6, middle A7, one finger across G B e: three fingers, three
    # strings under the finger barre.
    assert guitar._finger_plan(frets('076777')) == (3, 3)
    # C13: index D2, middle A3, ring G3, pinky across B e.
    assert guitar._finger_plan(frets('x32355')) == (4, 2)
    # An index barre alone leaves no finger barre: x13331 is four fingers.
    assert guitar._finger_plan(frets('x13331')) == (4, 0)


def test_a_finger_barre_costs_more_than_an_index_barre(guitar):
    """The same notes held two ways score apart by the finger-barre weight."""
    notes = chord('C', _NINTH)
    f = frets('x32333')
    plain = GuitarChordPicker(BUILTIN_FRETBOARDS['standard'])
    data = BUILTIN_FRETBOARDS['standard'].to_dict()
    data['weights']['finger_barre_penalty'] = 0.0
    free = GuitarChordPicker(FretboardSpec.from_dict('free', data))
    w = BUILTIN_FRETBOARDS['standard'].weight('finger_barre_penalty')
    assert w < 0
    assert plain._score_quality(f, notes, 'C') == pytest.approx(
        free._score_quality(f, notes, 'C') + 3 * w)


def test_no_barres_spec_still_rejects_them():
    data = BUILTIN_FRETBOARDS['standard'].to_dict()
    data['allow_barres'] = False
    picker = GuitarChordPicker(FretboardSpec.from_dict('no_barre', data))
    assert not picker._is_playable(frets('076777'))
    assert not picker._is_playable(frets('x32333'))


@pytest.mark.parametrize("root, intervals, grip", [
    ('C', _NINTH, 'x32333'),
    ('C#', _NINTH, 'x43444'),
    ('D', _NINTH, 'x54555'),
    ('D#', _NINTH, 'x65666'),
    ('B', _NINTH, 'x21222'),
    ('C', _MINOR_NINTH, 'x31333'),
])
def test_the_ninth_grips_are_chosen(guitar, root, intervals, grip):
    """Up the neck the chord-book 9th grip wins, not a thinner or wider shape."""
    notes = chord(root, intervals)
    guitar.reset()
    assert shape(guitar._find_best_fingering(notes, root)) == grip


def test_open_e9_keeps_its_open_shape(guitar):
    """In open position the open E9 (020102) still beats the 7th-fret grip."""
    notes = chord('E', _NINTH)
    guitar.reset()
    assert shape(guitar._find_best_fingering(notes, 'E')) == '020102'

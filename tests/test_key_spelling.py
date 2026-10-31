"""Key-aware spelling (services.key_spelling): naming keys, spelling a pitch
class by its degree in a key, and detecting a key from chords."""

import pytest

from services.key_spelling import (
    Key, detect_key, detected_target, key_tonic, leads_up, move_key, pitch_class,
    spell_in_key,
)

BANNED = {'E#', 'B#', 'Cb', 'Fb'}
LETTERS = 'CDEFGAB'
MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
MINOR_STEPS = (0, 2, 3, 5, 7, 8, 10)

#: Every key transpose can land in: the 24 that key_tonic names, plus the
#: other spelling of the two ties (Gb major, Ebm).
TARGET_KEYS = sorted({Key(key_tonic(pc, minor, style), minor)
                      for pc in range(12) for minor in (False, True)
                      for style in (None, 'sharp', 'flat')})


def test_there_are_26_target_keys():
    assert len(TARGET_KEYS) == 26
    assert Key('F#', False) in TARGET_KEYS and Key('Gb', False) in TARGET_KEYS
    assert Key('D#', True) in TARGET_KEYS and Key('Eb', True) in TARGET_KEYS


# --- spelling by degree -------------------------------------------------------

@pytest.mark.parametrize("key", TARGET_KEYS, ids=str)
def test_every_pitch_class_is_spelled_by_its_degree_or_refused(key):
    tonic = pitch_class(key.tonic)
    steps = MINOR_STEPS if key.minor else MAJOR_STEPS
    first = LETTERS.index(key.tonic[0])
    for pc in range(12):
        name = spell_in_key(pc, key)
        if name is None:
            continue
        assert pitch_class(name) == pc, (key, pc, name)
        assert name not in BANNED and len(name) <= 2, (key, pc, name)
        rel = (pc - tonic) % 12
        if rel in steps:
            # A diatonic note takes the key's letter for its degree.
            assert name[0] == LETTERS[(first + steps.index(rel)) % 7], (key, pc, name)


@pytest.mark.parametrize("key", TARGET_KEYS, ids=str)
def test_only_banned_or_double_spellings_are_refused(key):
    """A refusal happens only where the degree spelling would be E#, B#, Cb,
    Fb or a double accidental, so it always lands on a white key."""
    for pc in range(12):
        if spell_in_key(pc, key) is None:
            assert pc in (0, 2, 4, 5, 7, 9, 11), (key, pc)


def test_c_major_and_a_minor():
    c, am = Key('C', False), Key('A', True)
    assert [spell_in_key(pc, c) for pc in range(12)] == [
        'C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
    assert [spell_in_key(pc, am) for pc in range(12)] == [
        'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']


def test_b_major_uses_sharps_and_refuses_e_sharp():
    b = Key('B', False)
    assert [spell_in_key(pc, b) for pc in (1, 3, 6, 8, 10)] == ['C#', 'D#', 'F#', 'G#', 'A#']
    assert spell_in_key(5, b) is None   # raised 4 would be E#


def test_sharp_and_flat_keys_refuse_their_awkward_degrees():
    assert spell_in_key(5, Key('F#', False)) is None    # E#, the 7th
    assert spell_in_key(0, Key('C#', True)) is None     # B#, the raised 7th
    assert spell_in_key(11, Key('Gb', False)) is None   # Cb, the 4th
    assert spell_in_key(4, Key('Db', False)) is None    # Fb, the lowered 3rd
    assert spell_in_key(7, Key('G#', True)) is None     # F##, the raised 7th


def test_leading_raises_a_flat_only():
    c = Key('C', False)
    assert spell_in_key(1, c, leading=True) == 'C#'
    assert spell_in_key(8, c, leading=True) == 'G#'
    assert spell_in_key(6, c, leading=True) == 'F#'    # already sharp
    assert spell_in_key(11, c, leading=True) == 'B'    # natural stays
    assert spell_in_key(10, Key('F', False), leading=True) == 'A#'


# --- naming keys --------------------------------------------------------------------

def test_key_tonic_takes_the_signature_with_fewer_accidentals():
    assert [key_tonic(pc, False) for pc in range(12)] == [
        'C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
    assert [key_tonic(pc, True) for pc in range(12)] == [
        'C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']


def test_key_tonic_ties_follow_the_style():
    assert key_tonic(6, False, 'flat') == 'Gb'
    assert key_tonic(6, False, 'sharp') == 'F#'
    assert key_tonic(3, True, 'sharp') == 'D#'
    assert key_tonic(3, True, 'flat') == 'Eb'


def test_key_tonic_never_names_a_key_without_a_signature():
    for style in (None, 'sharp', 'flat'):
        assert key_tonic(1, False, style) == 'Db'    # C# major has 7 sharps
        assert key_tonic(3, False, style) == 'Eb'    # no D# major
        assert key_tonic(8, True, style) == 'G#'     # Abm has 7 flats
        assert key_tonic(1, True, style) == 'C#'     # no Dbm
        assert key_tonic(10, True, style) == 'Bb'    # A#m has 7 sharps


def test_move_key():
    assert move_key(Key('C', False), 1) == Key('Db', False)
    assert move_key(Key('A', True), -1) == Key('G#', True)
    assert move_key(Key('G', False), 4) == Key('B', False)
    assert move_key(Key('Db', False), 5) == Key('Gb', False)
    assert move_key(Key('C#', True), 2) == Key('D#', True)


# --- the leading-tone rule ----------------------------------------------------------

@pytest.mark.parametrize("chord, after, expected", [
    ("C#dim7", "Dm7", True),
    ("C#dim7", "G7/D", True),       # the bass is a semitone up
    ("C#°7", "Dm", True),
    ("C#m7b5", "Dm", True),         # half-diminished
    ("C#ø", "D", True),
    ("Do#dim", "Rem", True),        # European
    ("C#dim7", "Cm", False),        # down, not up
    ("C#7", "Dm", False),           # not diminished
    ("C#dim7", None, False),        # last chord
])
def test_leads_up(chord, after, expected):
    assert leads_up(chord, after) is expected


# --- detection ----------------------------------------------------------------------

@pytest.mark.parametrize("chords, key", [
    ("G D/F# Em C G B7 Em A7 C Cm G/D E7 Am7 D7 G", Key('G', False)),
    ("Am Dm E7 Am F G C E Am Dm E7 Am", Key('A', True)),
    ("F Bb F C7 F Bb F C7 F Bb F G7 C7", Key('F', False)),
    ("D C G D D C G D G A D C G A D", Key('D', False)),
    ("F# C# D#m B F# C# B F#", Key('F#', False)),
    ("Lam Rem Mi7 Lam Fa Sol Do Mi Lam", Key('A', True)),
])
def test_detect_key(chords, key):
    detection = detect_key(chords.split())
    assert detection.key == key
    assert detection.margin > 0


def test_detect_key_without_usable_chords():
    assert detect_key([]).key is None
    assert detected_target([], 2) is None


def test_a_sure_detection_gives_the_moved_key():
    pairs = [(c, None) for c in "G D Em C G D C G".split()]
    assert detected_target(pairs, 4) == Key('B', False)


def test_an_unsure_detection_whose_keys_disagree_gives_none():
    # G, D and C major are all close; they spell the moved chords differently.
    pairs = [(c, None) for c in "C G D".split()]
    assert detect_key(c for c, _ in pairs).margin < 0.3
    assert detected_target(pairs, 6) is None


def test_an_unsure_detection_whose_keys_agree_is_used():
    # Am, C and Em are close, but every one of them spells Am C up two the same.
    pairs = [("Am", "C"), ("C", None)]
    assert detect_key(["Am", "C"]).margin < 0.3
    assert detected_target(pairs, 2) == Key('B', True)

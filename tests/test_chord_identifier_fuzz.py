"""The chord identifier names every chord the app can write.

The notes come from the theory table (REFERENCE and OMITTED in
test_chord_notes_reference), never from the app's own resolver: each
quality the parser reads, on every root, in root position, over each of
its own notes (an inversion) and over each other note (a slash bass). They
reach the identifier the way the window sends them (piano keys, or typed
notes with flats or sharps, the answer shown in American or European), and
then at least one candidate must resolve to exactly those notes with the
same note lowest, and no candidate may resolve to any other notes. A
different name for the same notes counts (C6 or Am7/C).

Two notes count only as a power chord: C G is C5, but the identifier
names no other two-note selection (C E is no chord, though C(no5) parses).

The exhaustive grid (every quality, root and bass, on piano keys) and a
seeded random sample (voicings, typed spellings, solfège, European answers)
run with --fuzz (make fuzz); a slice of the grid runs always.
"""

import logging
import random

import pytest

from chord.helper import ChordHelper
from services.song_parser_service import SongParserService
from tests.test_chord_notes_reference import OMITTED, REFERENCE, pitch
from viewmodels.chord_identifier_viewmodel import NOTE_NAMES, ChordIdentifierViewModel

_HELPER = ChordHelper()

_FLATS = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')
_SOLFEGE = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa', 'G': 'Sol', 'A': 'La', 'B': 'Si'}

#: The seed of the random sample: a failure there names it, so it reproduces.
SEED = 20261109
SAMPLES = 4000


def _chords():
    """``(label, pitch classes above the root)`` for each different set of
    notes in the theory table, labelled with its first spelling."""
    sets = {}
    for spellings, intervals in {**REFERENCE, **OMITTED}.items():
        classes = frozenset(i % 12 for i in intervals)
        if len(classes) >= 3 or classes == {0, 7}:
            sets.setdefault(classes, spellings[0] or 'major')
    return [(label, tuple(sorted(classes))) for classes, label in sets.items()]


CHORDS = _chords()


@pytest.fixture(scope="module")
def vm():
    logging.disable(logging.INFO)  # the viewmodel logs every identification
    yield ChordIdentifierViewModel(SongParserService())
    logging.disable(logging.NOTSET)


def _sounds(name):
    """``(pitch classes, lowest pitch class)`` of a candidate as the app
    plays it, or None when it doesn't resolve."""
    played = _HELPER.compute_chord_notes(name)
    if played is None:
        return None
    return (frozenset(pitch(n) for n in played.notes) | {pitch(played.bass_note)},
            pitch(played.bass_note))


def _problem(candidates, wanted, lowest):
    """What's wrong with the candidates for the notes ``wanted`` with
    ``lowest`` in the bass, or None."""
    sounds = {name: _sounds(name) for name in candidates}
    wrong = [name for name, sound in sounds.items() if sound is None or sound[0] != wanted]
    if wrong:
        return f"candidates with other notes: {wrong}"
    if not any(sound == (wanted, lowest) for sound in sounds.values()):
        return f"no candidate with {NOTE_NAMES[lowest]} in the bass: {candidates}"
    return None


def _notes(intervals, root, bass):
    """The notes of a chord on ``root`` over ``bass`` (None: the root), and
    the bass: pitch classes."""
    classes = {(root + i) % 12 for i in intervals}
    lowest = root if bass is None else bass
    return frozenset(classes | {lowest}), lowest


def _keys(classes, lowest):
    """Piano keys: the bass on C4..B4, the others an octave up."""
    return [(NOTE_NAMES[lowest], 4)] + [(NOTE_NAMES[pc], 5) for pc in classes if pc != lowest]


def _check_keys(vm, label, intervals, root, bass):
    classes, lowest = _notes(intervals, root, bass)
    vm.set_notes(_keys(classes, lowest))
    problem = _problem(vm.candidates, classes, lowest)
    if problem:
        over = '' if bass is None else '/' + NOTE_NAMES[bass]
        return f"{NOTE_NAMES[root]}{label}{over}: {problem}"
    return None


def _basses(root):
    """Root position, then the bass on each other pitch class."""
    return [None] + [(root + b) % 12 for b in range(1, 12)]


@pytest.mark.parametrize("label, intervals", CHORDS, ids=[label for label, _ in CHORDS])
def test_every_chord_on_c_and_bb_is_named(vm, label, intervals):
    """The always-on slice: on C in root position, over each of its own
    notes and over the first note it doesn't have, and on Bb (flats) in
    root position."""
    outside = next(pc for pc in range(12) if pc not in intervals)
    cases = [(0, None)] + [(0, i % 12) for i in intervals if i % 12] + [(0, outside)]
    cases += [(10, None)]
    problems = [p for root, bass in cases
                for p in [_check_keys(vm, label, intervals, root, bass)] if p]
    assert not problems, "\n".join(problems)


@pytest.mark.fuzz
@pytest.mark.parametrize("label, intervals", CHORDS, ids=[label for label, _ in CHORDS])
def test_every_chord_on_every_root_over_every_bass_is_named(vm, label, intervals):
    problems = [p for root in range(12) for bass in _basses(root)
                for p in [_check_keys(vm, label, intervals, root, bass)] if p]
    assert not problems, f"{len(problems)} unnamed:\n" + "\n".join(problems[:40])


def _typed(midis, flats, solfege):
    """Typed notes with octaves, spelled with flats or sharps, in letters or
    solfège: ``Db4 F5``, ``Do#4 Fa5``."""
    words = []
    for midi in midis:
        name = (_FLATS if flats else NOTE_NAMES)[midi % 12]
        if solfege:
            name = _SOLFEGE[name[0]] + name[1:]
        words.append(f"{name}{midi // 12 - 1}")
    return ' '.join(words)


def _sample(rng):
    """A random chord, root, bass and voicing, and how it is entered."""
    label, intervals = rng.choice(CHORDS)
    root = rng.randrange(12)
    kind = rng.random()
    if kind < 0.4:
        bass = None
    elif kind < 0.75:
        bass = (root + rng.choice(intervals)) % 12
    else:
        bass = rng.randrange(12)
    classes, lowest = _notes(intervals, root, bass)
    # The bass on C4..B4, the others anywhere above it on the piano (to B5),
    # some doubled.
    bass_midi = 60 + lowest
    midis = [bass_midi]
    for pc in classes:
        choices = [m for m in range(bass_midi + 1, 84) if m % 12 == pc]
        midis += rng.sample(choices, min(len(choices), rng.choice((1, 1, 1, 2))))
    rng.shuffle(midis)
    return dict(label=label, root=root, bass=bass, classes=classes, lowest=lowest,
                midis=midis, typed=rng.random() < 0.6, flats=rng.random() < 0.5,
                solfege=rng.random() < 0.2,
                notation=rng.choice(('american', 'american', 'european')))


@pytest.mark.fuzz
def test_a_random_voicing_typed_or_played_is_named(vm):
    rng = random.Random(SEED)
    problems = []
    for index in range(SAMPLES):
        case = _sample(rng)
        vm.set_notation(case['notation'])
        if case['typed']:
            text = _typed(case['midis'], case['flats'], case['solfege'])
            vm.set_notes_from_string(text)
        else:
            text = sorted(set(case['midis']))
            vm.set_notes([(NOTE_NAMES[m % 12], m // 12 - 1) for m in text])
        problem = _problem(vm.candidates, case['classes'], case['lowest'])
        if problem:
            over = '' if case['bass'] is None else '/' + NOTE_NAMES[case['bass']]
            problems.append(f"#{index} {NOTE_NAMES[case['root']]}{case['label']}{over}"
                            f" as {text!r} ({case['notation']}): {problem}")
    vm.set_notation('american')
    assert not problems, (f"seed {SEED}, {len(problems)} of {SAMPLES} unnamed:\n"
                          + "\n".join(problems[:40]))

"""Key-aware spelling for transposed chords.

Transpose spells each moved chord by its scale degree in the key the chord
lands in, so a song moved into B gets ``F#``, ``C#`` and ``G#m`` rather than
``Gb``, ``Db`` and ``Abm``. This module is the music theory behind that: it
names keys, spells a pitch class in a key, and detects a key from chords. The
text side (which chord is in which key, rewriting tokens) is in
:mod:`services.transpose_service`.

Everything here works in American spelling with ASCII accidentals (``F#``,
``Bb``); the caller converts to the song's notation.

Spelling by degree
------------------
A pitch class is placed on a degree above the key's tonic and takes that
degree's letter. Diatonic degrees use the key's own letters. Chromatic ones:

* major: lowered 2, 3, 6 and 7 (``Db``, ``Eb``, ``Ab``, ``Bb`` in C), raised 4
  (``F#``);
* minor (natural minor letters): lowered 2, raised 3, 4, 6 and 7 (``Bb``,
  ``C#``, ``D#``, ``F#``, ``G#`` in A minor).

A diminished chord leading up a semitone (:func:`leads_up`: ``C#dim7 Dm7``,
``C#dim7 G7/D``) takes the sharp for a flat degree, as the leading tone of the
chord it resolves to.

A spelling that would be ``E#``, ``B#``, ``Cb``, ``Fb`` or a double accidental
is refused (:func:`spell_in_key` returns None) and the caller falls back to
:func:`plain_spelling`, which gives the natural (``F`` in F# major, ``C`` in
G# minor).

Naming a key
------------
:func:`key_tonic` names the tonic on a pitch class: the signature with fewer
accidentals (``Db`` major, not ``C#``; ``G#`` minor, not ``Ab``), the source's
accidental style breaking a tie (``F#``/``Gb`` major, ``D#``/``Eb`` minor). A
key with no real signature (``D#`` major, ``Dbm``) is never named.

Detecting a key
---------------
:func:`detect_key` ranks the 24 keys by a hand-made fit table (how usual each
chord is on each degree, with a bonus when the first or last chord is the
tonic) plus twice the correlation of the chords' pitch classes with the
Krumhansl-Kessler key profiles. It is trusted when the best key leads the
runner-up by :data:`MARGIN`, or when every key that close spells the chords
the same way (then the choice doesn't matter). It was tuned on 71 song
sections (69 right, no relative major/minor mix-ups).
"""

from collections import Counter
from functools import lru_cache
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple
from chord.converter import split_bass


LETTERS = 'CDEFGAB'
_NATURAL_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_PC_NATURAL = {pc: letter for letter, pc in _NATURAL_PC.items()}
_SHARP_NAME = {1: 'C#', 3: 'D#', 6: 'F#', 8: 'G#', 10: 'A#'}
_FLAT_NAME = {1: 'Db', 3: 'Eb', 6: 'Gb', 8: 'Ab', 10: 'Bb'}
#: The default spelling of a black key (no accidental style to follow).
_DEFAULT_BLACK = {1: 'C#', 3: 'Eb', 6: 'F#', 8: 'Ab', 10: 'Bb'}
_BANNED = frozenset({'E#', 'B#', 'Cb', 'Fb'})

#: Accidentals in each key signature. Keys missing here (D#, G#, A# major;
#: Dbm, Gbm minor) have none: they would need double sharps or flats.
_MAJOR_SIGNATURE = {'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
                    'F': 1, 'Bb': 2, 'Eb': 3, 'Ab': 4, 'Db': 5, 'Gb': 6, 'Cb': 7}
_MINOR_SIGNATURE = {'A': 0, 'E': 1, 'B': 2, 'F#': 3, 'C#': 4, 'G#': 5, 'D#': 6, 'A#': 7,
                    'D': 1, 'G': 2, 'C': 3, 'F': 4, 'Bb': 5, 'Eb': 6, 'Ab': 7}

_MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
_MINOR_STEPS = (0, 2, 3, 5, 7, 8, 10)
#: Semitones above the tonic -> (degree 0..6, alteration of that degree).
_MAJOR_DEGREE = {0: (0, 0), 2: (1, 0), 4: (2, 0), 5: (3, 0), 7: (4, 0), 9: (5, 0), 11: (6, 0),
                 1: (1, -1), 3: (2, -1), 6: (3, +1), 8: (5, -1), 10: (6, -1)}
_MINOR_DEGREE = {0: (0, 0), 2: (1, 0), 3: (2, 0), 5: (3, 0), 7: (4, 0), 8: (5, 0), 10: (6, 0),
                 1: (1, -1), 4: (2, +1), 6: (3, +1), 9: (5, +1), 11: (6, +1)}
_ACCIDENTAL = {-1: 'b', 0: '', 1: '#'}

#: The qualities the leading-tone rule treats as diminished.
DIMINISHED = frozenset({'dim', 'dim7', 'hdim'})


class Key(NamedTuple):
    """A key: its tonic in American spelling (``'F#'``, ``'Bb'``) and mode."""
    tonic: str
    minor: bool

    def __str__(self) -> str:
        return self.tonic + ('m' if self.minor else '')


def pitch_class(name: str) -> int:
    """The pitch class of an American note name (``'Bb'`` -> 10)."""
    pc = _NATURAL_PC[name[0].upper()]
    for c in name[1:]:
        if c in '#♯':
            pc += 1
        elif c in 'b♭':
            pc -= 1
    return pc % 12


def _style(name: str) -> Optional[str]:
    if name.endswith('#'):
        return 'sharp'
    if name.endswith('b') and len(name) > 1:
        return 'flat'
    return None


def plain_spelling(pc: int, style: Optional[str]) -> str:
    """The spelling without a key: the natural, or for a black key the
    source's accidental ``style`` ('sharp'/'flat'), else the default
    ``C# Eb F# Ab Bb``."""
    if pc in _PC_NATURAL:
        return _PC_NATURAL[pc]
    if style == 'sharp':
        return _SHARP_NAME[pc]
    if style == 'flat':
        return _FLAT_NAME[pc]
    return _DEFAULT_BLACK[pc]


# --- naming and moving keys ---------------------------------------------------

def key_tonic(pc: int, minor: bool, style: Optional[str] = None) -> str:
    """Name the tonic of a key on pitch class ``pc`` (American).

    The spelling whose signature has fewer accidentals wins; ``style``
    ('sharp', 'flat' or None for the default table) breaks a tie and never
    picks a key that has no signature.
    """
    if pc in _PC_NATURAL:
        return _PC_NATURAL[pc]
    signature = _MINOR_SIGNATURE if minor else _MAJOR_SIGNATURE
    if style == 'sharp':
        preferred = _SHARP_NAME[pc]
    elif style == 'flat':
        preferred = _FLAT_NAME[pc]
    else:
        preferred = _DEFAULT_BLACK[pc]
    names = [n for n in (_SHARP_NAME[pc], _FLAT_NAME[pc]) if n in signature]
    return min(names, key=lambda n: (signature[n], n != preferred))


def move_key(key: Key, semitones: int) -> Key:
    """``key`` transposed by ``semitones``, named by :func:`key_tonic`."""
    pc = (pitch_class(key.tonic) + semitones) % 12
    return Key(key_tonic(pc, key.minor, _style(key.tonic)), key.minor)


# --- spelling ---------------------------------------------------------------------

@lru_cache(maxsize=64)
def _scale(key: Key) -> Tuple[Tuple[str, int], ...]:
    """The key's seven (letter, accidental) pairs; natural minor for minor."""
    first = LETTERS.index(key.tonic[0])
    tonic = pitch_class(key.tonic)
    steps = _MINOR_STEPS if key.minor else _MAJOR_STEPS
    out = []
    for degree in range(7):
        letter = LETTERS[(first + degree) % 7]
        wanted = (tonic + steps[degree]) % 12
        out.append((letter, ((wanted - _NATURAL_PC[letter] + 6) % 12) - 6))
    return tuple(out)


@lru_cache(maxsize=1024)
def spell_in_key(pc: int, key: Key, leading: bool = False) -> Optional[str]:
    """Spell pitch class ``pc`` by its degree in ``key`` (American).

    Returns None when that spelling would be E#, B#, Cb, Fb or a double
    accidental; the caller then uses its plain spelling. ``leading`` asks for
    the raised spelling of a flat (``Db`` -> ``C#``): a diminished chord
    leading up a semitone to the next chord.
    """
    rel = (pc - pitch_class(key.tonic)) % 12
    degree, alteration = (_MINOR_DEGREE if key.minor else _MAJOR_DEGREE)[rel]
    letter, accidental = _scale(key)[degree]
    accidental += alteration
    if accidental not in _ACCIDENTAL:
        return None
    name = letter + _ACCIDENTAL[accidental]
    if name in _BANNED:
        return None
    if leading and accidental == -1 and pc in _SHARP_NAME:
        name = _SHARP_NAME[pc]
    return name


# --- chord facts ------------------------------------------------------------------

class ChordFacts(NamedTuple):
    """What key detection and the leading-tone rule read from a chord."""
    root: int
    quality: str          # maj, dom, min, dim, dim7, hdim, aug or neutral
    pitches: frozenset
    bass: Optional[int]   # the slash bass, None without one
    root_name: str        # American spelling of the root, as written
    bass_name: str        # and of the bass


def _quality(intervals: Iterable[int]) -> str:
    s = set(intervals)
    if 4 in s and 8 in s and 7 not in s:
        return 'aug'
    if 4 in s:
        return 'dom' if 10 in s else 'maj'
    if 3 in s and 6 in s and 7 not in s:
        return 'dim7' if 9 in s else ('hdim' if 10 in s else 'dim')
    if 3 in s:
        return 'min'
    return 'neutral'


_HELPER = None


@lru_cache(maxsize=4096)
def chord_facts(chord: str) -> Optional[ChordFacts]:
    """Read ``chord`` (American or European) through the playback helper;
    None when it has no notes."""
    global _HELPER
    if _HELPER is None:
        from chord.helper import ChordHelper
        _HELPER = ChordHelper()
    notes = _HELPER.compute_chord_notes(chord)
    if notes is None:
        return None
    root_name, bass_name = notes.root.replace('-', 'b'), notes.bass_note.replace('-', 'b')
    root = pitch_class(root_name)
    if notes.intervals:
        intervals = [i % 12 for i in notes.intervals]
    else:
        intervals = [(pitch_class(n.replace('-', 'b')) - root) % 12 for n in notes.notes]
    pitches = frozenset(pitch_class(n.replace('-', 'b')) for n in notes.notes)
    bass = pitch_class(bass_name) if split_bass(chord)[1] is not None else None
    return ChordFacts(root, _quality(intervals), pitches, bass, root_name, bass_name)


def leads_up(chord: str, next_chord: Optional[str]) -> bool:
    """Whether ``chord`` is diminished and ``next_chord``'s root or bass is a
    semitone above its root (``C#dim7 Dm7``, ``C#dim7 G7/D``)."""
    if not next_chord:
        return False
    this, after = chord_facts(chord), chord_facts(next_chord)
    if this is None or after is None or this.quality not in DIMINISHED:
        return False
    return (after.root - this.root) % 12 == 1 or (
        after.bass is not None and (after.bass - this.root) % 12 == 1)


# --- key detection ----------------------------------------------------------------

#: How usual each (degree in semitones, quality) is in a major key.
_MAJOR_FIT = {
    (0, 'maj'): 3.0, (0, 'dom'): 2.5, (5, 'maj'): 2.0, (5, 'dom'): 1.5,
    (7, 'maj'): 2.0, (7, 'dom'): 2.5, (9, 'min'): 1.5, (2, 'min'): 1.5,
    (4, 'min'): 1.0, (11, 'dim'): 0.8, (11, 'hdim'): 0.8,
    # borrowed from the parallel minor
    (10, 'maj'): 0.6, (10, 'dom'): 0.4, (8, 'maj'): 0.4, (5, 'min'): 0.5,
    (3, 'maj'): 0.3, (0, 'min'): 0.0,
    # secondary dominants, tritone substitutes, passing diminished chords
    (2, 'maj'): 0.6, (2, 'dom'): 0.8, (4, 'maj'): 0.5, (4, 'dom'): 0.8,
    (9, 'maj'): 0.3, (9, 'dom'): 0.6, (11, 'maj'): 0.2, (11, 'dom'): 0.5,
    (1, 'dom'): 0.3, (1, 'dim7'): 0.3, (3, 'dim7'): 0.2, (8, 'dim7'): 0.3,
    (6, 'hdim'): 0.4, (6, 'dim'): 0.4, (6, 'dim7'): 0.4, (11, 'dim7'): 0.8,
}
_MINOR_FIT = {
    (0, 'min'): 3.0, (5, 'min'): 2.0, (7, 'maj'): 2.0, (7, 'dom'): 2.5,
    (7, 'min'): 1.0, (8, 'maj'): 1.5, (3, 'maj'): 1.5, (10, 'maj'): 1.5,
    (10, 'dom'): 1.0, (2, 'dim'): 1.0, (2, 'hdim'): 1.2, (11, 'dim'): 1.0,
    (11, 'dim7'): 1.2, (5, 'maj'): 0.4, (5, 'dom'): 0.4, (2, 'min'): 0.3,
    (1, 'maj'): 0.4, (0, 'maj'): 0.3, (0, 'dom'): 0.6, (2, 'dom'): 0.4,
    (3, 'dom'): 0.3, (8, 'dom'): 0.6, (9, 'hdim'): 0.6,
}
_MISS = -1.0


def _best_on_degree(table: Dict[Tuple[int, str], float]) -> Dict[int, float]:
    best: Dict[int, float] = {}
    for (rel, _), value in table.items():
        best[rel] = max(best.get(rel, _MISS), value)
    return best


_MAJOR_BEST, _MINOR_BEST = _best_on_degree(_MAJOR_FIT), _best_on_degree(_MINOR_FIT)

# Krumhansl-Kessler key profiles (tonic first).
_KK_MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_KK_MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)

#: The lead the best key needs over the runner-up to be trusted.
MARGIN = 0.3


def _fit(rel: int, quality: str, minor: bool) -> float:
    table = _MINOR_FIT if minor else _MAJOR_FIT
    if quality in ('neutral', 'aug'):
        # A power chord or sus chord fits like the best chord on its degree.
        best = (_MINOR_BEST if minor else _MAJOR_BEST).get(rel, _MISS)
        return best * (0.7 if quality == 'neutral' else 0.5) if best > 0 else _MISS
    return table.get((rel, quality), _MISS)


def _tonic_like(facts: ChordFacts, tonic: int, minor: bool) -> bool:
    if facts.root != tonic:
        return False
    return facts.quality in (('min', 'neutral') if minor else ('maj', 'dom', 'neutral'))


def _correlation(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def _rank(facts: List[ChordFacts]) -> List[Tuple[float, int, bool]]:
    """All 24 keys as ``(score, tonic, minor)``, best first."""
    # Count each kind of chord once: the score is a sum over chords.
    kinds = Counter((f.root, f.quality) for f in facts)
    histogram = [0.0] * 12
    for f in facts:
        for p in f.pitches:
            histogram[p] += 1
        histogram[f.root] += 1
    # The first and last chords say the most about the key.
    histogram[facts[0].root] += 2
    histogram[facts[-1].root] += 2

    ranked = []
    for tonic in range(12):
        for minor, profile in ((False, _KK_MAJOR), (True, _KK_MINOR)):
            fit = sum(count * _fit((root - tonic) % 12, quality, minor)
                      for (root, quality), count in kinds.items())
            if _tonic_like(facts[0], tonic, minor):
                fit += 1.5
            if _tonic_like(facts[-1], tonic, minor):
                fit += 2.0
            rotated = [profile[(p - tonic) % 12] for p in range(12)]
            score = fit / len(facts) + 2.0 * _correlation(histogram, rotated)
            ranked.append((score, tonic, minor))
    ranked.sort(key=lambda r: -r[0])
    return ranked


def _name_detected(tonic: int, minor: bool, spellings: Counter) -> Key:
    """Name a detected key: a natural as is; a black key as the song spells
    that root most often, else by :func:`key_tonic`."""
    if tonic in _PC_NATURAL:
        return Key(_PC_NATURAL[tonic], minor)
    for name, _ in spellings.most_common():
        if len(name) == 2 and pitch_class(name) == tonic:
            return Key(name, minor)
    return Key(key_tonic(tonic, minor), minor)


class Detection(NamedTuple):
    """A detected key, the lead of the best key over the runner-up, and every
    key as ``(score, Key)`` best first."""
    key: Optional[Key]
    margin: float
    ranked: List[Tuple[float, Key]]


def detect_key(chords: Iterable[str]) -> Detection:
    """Detect the key of ``chords`` (chord strings, American or European).

    ``key`` is None when none of the chords has notes.
    """
    facts, spellings = [], Counter()
    for chord in chords:
        f = chord_facts(chord)
        if f is not None:
            facts.append(f)
            spellings[f.root_name] += 1
    if not facts:
        return Detection(None, 0.0, [])
    ranked = _rank(facts)
    named = [(score, _name_detected(tonic, minor, spellings)) for score, tonic, minor in ranked]
    return Detection(named[0][1], ranked[0][0] - ranked[1][0], named)


def _spelled(chords: Sequence[Tuple[str, Optional[str]]], key: Key, semitones: int) -> tuple:
    """How ``key`` spells the (chord, next chord) pairs moved by ``semitones``:
    the root and bass names transpose writes (refused degree spellings
    replaced by the plain one)."""
    def spell(pc: int, written: str, leading: bool = False) -> str:
        pc = (pc + semitones) % 12
        return spell_in_key(pc, key, leading) or plain_spelling(pc, _style(written))

    out = []
    for chord, next_chord in chords:
        f = chord_facts(chord)
        if f is None:
            continue
        root = spell(f.root, f.root_name, leads_up(chord, next_chord))
        bass = None if f.bass is None else spell(f.bass, f.bass_name)
        out.append((root, bass))
    return tuple(out)


def detected_target(chords: Sequence[Tuple[str, Optional[str]]], semitones: int) -> Optional[Key]:
    """The key ``chords`` land in after moving by ``semitones``, or None when
    the detection isn't sure.

    ``chords`` are ``(chord, next chord)`` pairs (the next chord for the
    leading-tone rule; None at the end). Sure means the best key leads by
    :data:`MARGIN`, or every key within :data:`MARGIN` of it spells these
    chords the same way.
    """
    detection = detect_key(chord for chord, _ in chords)
    if detection.key is None:
        return None
    target = move_key(detection.key, semitones)
    if detection.margin >= MARGIN:
        return target
    best = detection.ranked[0][0]
    # Distinct chords only: the spelling of a pair doesn't depend on where it is.
    unique = sorted(set(chords), key=lambda pair: (pair[0], pair[1] or ''))
    spellings = {_spelled(unique, move_key(key, semitones), semitones)
                 for score, key in detection.ranked if score >= best - MARGIN}
    return target if len(spellings) == 1 else None

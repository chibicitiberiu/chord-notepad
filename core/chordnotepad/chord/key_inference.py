"""Key inference for songs without a ``{key:}`` line.

The ensemble voicer's leading-tone rules (resolve it up to the tonic, don't
double it) need a key. Most chord sheets don't set one, so this module
estimates the key around each chord from its neighbours: a window of chords
centred on it, the whole song being known before any of it is voiced.

For every possible tonic, each chord in the window scores by the function it
would have in that key (tonic, dominant, subdominant, the other diatonic
chords, or none), weighted by its distance from the centre; a dominant
followed by its tonic scores extra (a cadence). Major and minor on the same
tonic are scored separately and the better counts, since both share the
leading tone (the semitone below the tonic), which is all the voicer needs.

The **confidence** is how far the best tonic leads the runner-up, per unit of
window weight, times the share of the window (by weight) whose chords belong
to the best key: about 0.25 to 0.6 for a plain diatonic loop, about 1.5 for a
minor-key cadence, below 0.2 for a chromatic passage that fits no key much
better than another (a cycle of major thirds, chromatic planing). Callers
apply the key-based rules only above a threshold and scale them in just
above it.

Pure music theory on pitch classes: chord spelling doesn't matter here.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple, TYPE_CHECKING

from chordnotepad.chord.midi_converter import parse_note_to_semitone, intervals_from_note_names

if TYPE_CHECKING:
    from chordnotepad.models.chord_notes import ChordNotes


#: Function weights in a major key: (root's semitones above the tonic,
#: triad quality) -> weight. I, V (and V7), IV, ii, vi, iii, vii°.
MAJOR_FUNCTIONS: Dict[Tuple[int, str], float] = {
    (0, 'maj'): 3.0,
    (7, 'maj'): 2.0,
    (5, 'maj'): 1.5,
    (2, 'min'): 1.0,
    (9, 'min'): 1.0,
    (4, 'min'): 0.5,
    (11, 'dim'): 1.0,
}

#: The same in a minor key: i, V (major, from the harmonic minor), iv, ii°,
#: VI, III, VII, v, vii°.
MINOR_FUNCTIONS: Dict[Tuple[int, str], float] = {
    (0, 'min'): 3.0,
    (7, 'maj'): 2.0,
    (5, 'min'): 1.5,
    (2, 'dim'): 1.0,
    (8, 'maj'): 1.0,
    (3, 'maj'): 0.5,
    (10, 'maj'): 0.5,
    (7, 'min'): 0.5,
    (11, 'dim'): 1.0,
}

#: Scale pitch classes above the tonic: major, and minor (natural plus the
#: raised seventh of the harmonic minor).
MAJOR_SCALE: FrozenSet[int] = frozenset((0, 2, 4, 5, 7, 9, 11))
MINOR_SCALE: FrozenSet[int] = frozenset((0, 2, 3, 5, 7, 8, 10, 11))

#: Weight of a chord in the key's scale with no function in the tables
#: (a sus chord, an added-note chord on a scale degree).
DIATONIC_OTHER = 0.25
#: Weight of a chord with a tone outside the key's scale.
CHROMATIC = -1.0
#: Extra weight for a dominant (V, V7 or vii°) followed by its tonic.
CADENCE_BONUS = 1.5

_MODES = ((MAJOR_FUNCTIONS, MAJOR_SCALE), (MINOR_FUNCTIONS, MINOR_SCALE))


@dataclass(frozen=True)
class KeyEstimate:
    """The key around one chord: its tonic pitch class and how sure."""
    tonic_pc: int
    confidence: float

    @property
    def leading_tone_pc(self) -> int:
        """The semitone below the tonic."""
        return (self.tonic_pc + 11) % 12


@dataclass(frozen=True)
class _Chord:
    root_pc: int
    quality: str
    core_pcs: FrozenSet[int]


def triad_quality(intervals: Sequence[int]) -> str:
    """``'maj'``, ``'min'``, ``'dim'``, ``'aug'`` or ``'other'`` from a chord's
    intervals above its root (only the tones below the octave count)."""
    core = {iv % 12 for iv in intervals if iv < 12}
    if 4 in core and 3 not in core:
        if 8 in core and 7 not in core:
            return 'aug'
        return 'maj' if 6 not in core or 7 in core else 'other'
    if 3 in core and 4 not in core:
        if 6 in core and 7 not in core:
            return 'dim'
        return 'min' if 7 in core or 6 not in core else 'other'
    return 'other'


def _describe(chord: 'ChordNotes') -> Optional[_Chord]:
    notes = chord.notes
    if not notes:
        return None
    root = parse_note_to_semitone(chord.root or notes[0])
    if root is None:
        return None
    intervals = chord.intervals
    if not intervals or len(intervals) != len(notes):
        intervals = intervals_from_note_names(notes)
    core = frozenset((root + iv) % 12 for iv in intervals if iv < 12)
    return _Chord(root, triad_quality(intervals), core)


def _function_weight(chord: _Chord, tonic: int, functions: Dict[Tuple[int, str], float],
                     scale: FrozenSet[int]) -> float:
    degree = (chord.root_pc - tonic) % 12
    weight = functions.get((degree, chord.quality))
    if weight is not None:
        return weight
    if all((pc - tonic) % 12 in scale for pc in chord.core_pcs):
        return DIATONIC_OTHER
    return CHROMATIC


def _is_dominant_of(chord: _Chord, tonic: int) -> bool:
    degree = (chord.root_pc - tonic) % 12
    return (degree == 7 and chord.quality == 'maj') or (degree == 11 and chord.quality == 'dim')


def infer_keys(chords: Sequence['ChordNotes'], window: int = 4) -> List[Optional[KeyEstimate]]:
    """Estimate the key around every chord of a song.

    Args:
        chords: The song's chords in order (empty or unreadable ones are
            skipped and get ``None``).
        window: How many chords before and after the centre count. A chord
            ``d`` places away weighs ``(window + 1 - d) / (window + 1)``.

    Returns:
        One :class:`KeyEstimate` (or ``None``) per chord.
    """
    described = [_describe(c) for c in chords]
    positions = [i for i, d in enumerate(described) if d is not None]
    seq = [described[i] for i in positions]
    n = len(seq)
    # Per chord and tonic: its function weight (best of major and minor), and
    # whether it is that key's dominant resolving to the next chord's tonic.
    unit: List[List[float]] = []
    for i, chord in enumerate(seq):
        row = []
        nxt = seq[i + 1] if i + 1 < n else None
        for tonic in range(12):
            best = None
            for functions, scale in _MODES:
                w = _function_weight(chord, tonic, functions, scale)
                if nxt is not None and nxt.root_pc == tonic and _is_dominant_of(chord, tonic):
                    w += CADENCE_BONUS
                best = w if best is None or w > best else best
            row.append(best)
        unit.append(row)

    result: List[Optional[KeyEstimate]] = [None] * len(chords)
    for i in range(n):
        totals = [0.0] * 12
        weight_sum = 0.0
        for j in range(max(0, i - window), min(n, i + window + 1)):
            w = (window + 1 - abs(i - j)) / (window + 1)
            weight_sum += w
            for tonic in range(12):
                totals[tonic] += w * unit[j][tonic]
        ranked = sorted(range(12), key=lambda t: (-totals[t], t))
        best, second = ranked[0], ranked[1]
        confidence = (totals[best] - totals[second]) / weight_sum if weight_sum else 0.0
        if weight_sum:
            fitted = sum((window + 1 - abs(i - j)) / (window + 1)
                         for j in range(max(0, i - window), min(n, i + window + 1))
                         if unit[j][best] > 0)
            confidence *= fitted / weight_sum
        result[positions[i]] = KeyEstimate(best, confidence)
    return result

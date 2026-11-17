"""Low interval limits, shared by every voicing engine.

Two notes close together sound muddy when they sit low: the lower the pair,
the wider it has to be to stay clear. The usual orchestration and arranging
table gives, per interval, the lowest note its lower pitch may sit on. This
module holds that one table; each engine reads it through
:func:`semitones_below_limit`, with an offset where its instrument hears it
differently (a guitar's low strings blur less than sustained voices, so the
fretboard reads the seconds and thirds three semitones lower).

The table (lower pitch, MIDI with C4 = 60) is the usual arranging one.
Sources differ by a semitone on a few entries: some put the tritone at B2
and the perfect fourth at Bb2. The compound intervals (ninths, tenths) only
matter for voices more than an octave apart, such as a double bass under a
cello.

====================  =========
interval              limit
====================  =========
minor second          E3  (52)
major second          Eb3 (51)
minor third           C3  (48)
major third           Bb2 (46)
perfect fourth        A2  (45)
tritone               Bb2 (46)
perfect fifth         Bb1 (34)
minor sixth           G2  (43)
major sixth           F2  (41)
minor seventh         F2  (41)
major seventh         F2  (41)
minor ninth           E2  (40)
major ninth           Eb2 (39)
minor tenth           C2  (36)
major tenth           Bb1 (34)
====================  =========

A unison and an octave have no limit; neither has anything wider than a
tenth.
"""

from typing import Dict, Iterable, Optional

#: Interval in semitones -> the lowest MIDI note its lower pitch may sit on.
LOW_INTERVAL_LIMITS: Dict[int, int] = {
    1: 52,   # minor second: E3
    2: 51,   # major second: Eb3
    3: 48,   # minor third: C3
    4: 46,   # major third: Bb2
    5: 45,   # perfect fourth: A2
    6: 46,   # tritone: Bb2
    7: 34,   # perfect fifth: Bb1
    8: 43,   # minor sixth: G2
    9: 41,   # major sixth: F2
    10: 41,  # minor seventh: F2
    11: 41,  # major seventh: F2
    13: 40,  # minor ninth: E2
    14: 39,  # major ninth: Eb2
    15: 36,  # minor tenth: C2
    16: 34,  # major tenth: Bb1
}


def semitones_below_limit(lower: int, upper: int, offset: int = 0,
                          intervals: Optional[Iterable[int]] = None) -> int:
    """How many semitones ``lower`` sits below the limit of the interval
    ``upper - lower`` (0 when it is at or above it, or the interval has none).

    Args:
        lower, upper: The two MIDI pitches, ``lower <= upper``.
        offset: Added to every limit (negative lowers it).
        intervals: When given, only these interval sizes are checked.
    """
    size = upper - lower
    if intervals is not None and size not in intervals:
        return 0
    limit = LOW_INTERVAL_LIMITS.get(size)
    if limit is None:
        return 0
    return max(0, limit + offset - lower)

"""The toolbar's value logic: keys, tempo, the multiplier and value snapping.

Every UI shows the same key list, converts the key the same way when the
notation flips, parses a typed multiplier the same way and snaps a dragged
value to the same grid. The session normalizes the values its commands get
with these too, so a view that sends a raw slider position still lands on
the values the desktop scrubber would.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from chord.converter import NotationConverter
# TIME_SIGNATURE_UNITS and MIN_BEATS/MAX_BEATS are re-exported: the beat units
# a time signature may have and the beats a bar may have.
from constants import (  # noqa: F401
    DEFAULT_BPM, MAX_BEATS, MAX_BPM, MIN_BEATS, MIN_BPM, TIME_SIGNATURE_UNITS)
from models.notation import Notation

_AMERICAN_KEYS = (
    "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#",
    "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
)
_EUROPEAN_KEYS = (
    "Do", "Do#", "Reb", "Re", "Re#", "Mib", "Mi", "Fa", "Fa#",
    "Solb", "Sol", "Sol#", "Lab", "La", "La#", "Sib", "Si",
)


def key_options(notation: str) -> Tuple[str, ...]:
    """The keys the toolbar (and the Insert Key dialog) offer.

    Root notes only: a roman numeral's case already says major or minor.

    Args:
        notation: ``american`` or ``european``.

    Raises:
        ValueError: For any other notation.
    """
    return _EUROPEAN_KEYS if Notation(notation) is Notation.EUROPEAN else _AMERICAN_KEYS


def convert_key(key: str, notation: str) -> str:
    """``key`` spelled in ``notation`` (``"C"`` -> ``"Do"`` for European).

    Args:
        key: A key in either notation.
        notation: The notation to spell it in.

    Raises:
        ValueError: For an unknown notation.
    """
    if Notation(notation) is Notation.EUROPEAN:
        return NotationConverter.chord_american_to_european(key)
    return NotationConverter.chord_european_to_american(key)


def shown_key(key: Optional[str], notation: str) -> str:
    """The key the toolbar shows: ``key``, or the first option when unset."""
    return key or key_options(notation)[0]


@dataclass(frozen=True)
class ScrubScale:
    """The range and grid of a value the user drags or types (a "scrubber").

    ``step`` is the grid. With ``snap_tolerance`` 0 every value snaps to it;
    above 0 the grid is magnetic: a value within the tolerance of a grid
    point latches to it, any other value is kept. A drag moves the value in
    ``drag_step`` increments, then applies the same magnetic snap.

    Attributes:
        min_value: The smallest value (also the grid's origin).
        max_value: The largest value.
        step: The grid spacing (<= 0: no grid).
        drag_step: How far one drag or wheel increment moves the value.
        snap_tolerance: How close to a grid point a value latches to it.
        default: The value a reset goes back to, or None.
    """

    min_value: float
    max_value: float
    step: float = 1.0
    drag_step: Optional[float] = None
    snap_tolerance: float = 0.0
    default: Optional[float] = None

    @property
    def increment(self) -> float:
        """One drag or wheel step (``drag_step``, else ``step``)."""
        return self.drag_step if self.drag_step is not None else self.step

    def clamp(self, value: float) -> float:
        """``value`` limited to ``[min_value, max_value]``."""
        if value < self.min_value:
            return self.min_value
        if value > self.max_value:
            return self.max_value
        return value

    def snap(self, value: float, tolerance: Optional[float] = None) -> float:
        """``value`` on the grid: always when ``tolerance`` is None or <= 0,
        else only when it is within ``tolerance`` of a grid point."""
        if self.step <= 0:
            return value
        steps = round((value - self.min_value) / self.step)
        snapped = self.min_value + steps * self.step
        if snapped > self.max_value:
            snapped = self.max_value
        if tolerance is None or tolerance <= 0:
            return snapped
        if abs(snapped - value) <= tolerance:
            return snapped
        return value

    def normalize(self, value: float) -> float:
        """A set, typed or dragged value as the control keeps it: clamped,
        then snapped by the scale's own tolerance."""
        return self.snap(self.clamp(value), tolerance=self.snap_tolerance)

    def stepped(self, value: float, steps: int) -> float:
        """``value`` moved by ``steps`` drag increments, normalized."""
        return self.normalize(value + steps * self.increment)


#: The BPM control: 20-400, magnetic to tens.
BPM_SCALE = ScrubScale(min_value=MIN_BPM, max_value=MAX_BPM, step=10, drag_step=1,
                       snap_tolerance=1, default=DEFAULT_BPM)
#: The speed multiplier, in percent: 12.5-400, kept as set (a drag moves it
#: by 1 %). No grid: the scheduler takes any multiplier, and a grid made the
#: Android slider's 5 % stops play at other speeds (110 % as 112.5 %).
MULTIPLIER_SCALE = ScrubScale(min_value=12.5, max_value=400, step=0, drag_step=1,
                              default=100)


def normalize_bpm(bpm: float) -> int:
    """A BPM as the toolbar keeps it (clamped, snapped, whole)."""
    return int(round(BPM_SCALE.normalize(bpm)))


def format_bpm(bpm: float) -> str:
    """The BPM as the toolbar shows it, e.g. ``120``."""
    return f"{int(round(bpm))}"


def parse_bpm(text: str) -> int:
    """A typed BPM (``"120"``, ``"119.6"``).

    Raises:
        ValueError: If it isn't a number.
    """
    return int(round(float(text)))


def format_multiplier_pct(pct: float) -> str:
    """The multiplier as the toolbar shows it, e.g. ``150`` or ``87.5``."""
    return f"{pct:g}"


def parse_multiplier_pct(text: str) -> float:
    """A typed multiplier in percent; accepts ``150``, ``150%`` and ``1.5x``.

    Raises:
        ValueError: If it isn't one of those.
    """
    s = text.strip().lower().replace(" ", "")
    if s.endswith("x"):
        return float(s[:-1]) * 100.0
    if s.endswith("%"):
        return float(s[:-1])
    return float(s)

"""
Directive model for song instructions like BPM, time signature, etc.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple

from constants import MAX_BPM, MIN_BPM


def clamp_bpm(bpm: float) -> int:
    """``bpm`` as a whole tempo within the app's range (MIN_BPM-MAX_BPM)."""
    return int(min(MAX_BPM, max(MIN_BPM, int(bpm))))


class DirectiveType(IntEnum):
    """Enum for directive types."""
    BPM = 0
    TIME_SIGNATURE = 1
    KEY = 2
    LOOP = 3
    LABEL = 4
    CAPO = 5
    UNKNOWN = 6  # For invalid/unparseable directives


class BPMModifierType(IntEnum):
    """Enum for BPM modifier types."""
    ABSOLUTE = 0        # {bpm: 120} - set to exact value
    RELATIVE = 1        # {bpm: +20} or {bpm: -20} - add/subtract from current
    PERCENTAGE = 2      # {bpm: 50%} - percentage of current
    MULTIPLIER = 3      # {bpm: 2x} or {bpm: 0.5x} - multiply current
    RESET = 4           # {bpm: reset} or {bpm: original} - restore initial


#: The directive keywords and what each is called in the text (``tempo`` is
#: another name for ``bpm``).
DIRECTIVE_KEYWORDS = ('bpm', 'tempo', 'time', 'key', 'capo', 'label', 'loop')

#: The correct syntax of each directive, for hints while typing and for the
#: tooltip of an invalid one.
DIRECTIVE_SYNTAX = {
    'bpm': '{bpm: 120} · {bpm: +10} · {bpm: 50%} · {bpm: 2x} · {bpm: reset}',
    'tempo': '{tempo: 120} · {tempo: +10} · {tempo: 50%} · {tempo: 2x} · {tempo: reset}',
    'time': '{time: 4/4} · {time: 3/4} · {time: 6/8}',
    'key': '{key: G} · {key: Am} · {key: F#m} · {key: Sol}',
    'capo': '{capo: 3} · {capo: 0}',
    'label': '{label: verse}',
    'loop': '{loop: verse} · {loop: verse 3} · {loop: @start 2}',
}
#: The hint for a directive whose keyword isn't one of the above.
UNKNOWN_DIRECTIVE_SYNTAX = '{bpm: …} · {time: …} · {key: …} · {capo: …} · {label: …} · {loop: …}'


def directive_syntax(keyword: Optional[str]) -> str:
    """The syntax hint for ``keyword`` (any case), or the list of directives
    when it isn't one."""
    return DIRECTIVE_SYNTAX.get((keyword or '').strip().lower(), UNKNOWN_DIRECTIVE_SYNTAX)


@dataclass
class Directive:
    """Represents a directive instruction in the song.

    Directives are instructions like BPM, time signature, key changes, or loop markers.
    """

    type: DirectiveType
    """The type of directive"""

    start: int
    """Character position where directive starts in the full text"""

    end: int
    """Character position where directive ends in the full text"""

    is_valid: bool = True
    """Whether the directive is valid"""

    # Parameters for different directive types
    bpm: Optional[int] = None
    """BPM value (for DirectiveType.BPM with absolute values)"""

    bpm_modifier_type: Optional[BPMModifierType] = None
    """Type of BPM modification (for DirectiveType.BPM)"""

    bpm_modifier_value: Optional[float] = None
    """Value for BPM modification (relative offset, percentage, or multiplier)"""

    beats: Optional[int] = None
    """Number of beats (for DirectiveType.TIME_SIGNATURE)"""

    unit: Optional[int] = None
    """Beat unit (for DirectiveType.TIME_SIGNATURE)"""

    key: Optional[str] = None
    """Key signature (for DirectiveType.KEY)"""

    label: Optional[str] = None
    """Label name (for DirectiveType.LOOP)"""

    loop_count: int = 2
    """Number of times to loop (for DirectiveType.LOOP). Must be >= 1. Default is 2."""

    capo: Optional[int] = None
    """Capo fret position (for DirectiveType.CAPO). 0 means no capo. Applies to
    fretboard voicings only; the fret/tab views draw shapes relative to it."""

    keyword: Optional[str] = None
    """The directive's name as written, lower-cased (``bpm``, ``tempo``,
    ``soc``...); None for directives built in code."""

    message: Optional[str] = None
    """Why the directive is invalid (``Tempo must be 20-400``) or has no
    effect (see ``redundant``), for the user; None otherwise."""

    redundant: bool = False
    """A valid value directive that another of its kind replaces before any
    chord plays, so it has no effect (``message`` says by which)."""

    @property
    def syntax(self) -> str:
        """The correct syntax for this directive's keyword (a hint)."""
        return directive_syntax(self.keyword)

    def apply_bpm(self, current: int, reset_bpm: int) -> int:
        """The tempo after this ``{bpm}`` directive.

        Relative changes (+N, N%, Nx) apply to ``current`` and are clamped to
        the app's tempo range; ``reset`` returns ``reset_bpm``. The parser
        only lets absolute values within the range through.

        Args:
            current: The tempo in effect before the directive.
            reset_bpm: The tempo ``{bpm: reset}`` goes back to.
        """
        return self.apply_bpm_checked(current, reset_bpm)[0]

    def apply_bpm_checked(self, current: int, reset_bpm: int) -> Tuple[int, bool]:
        """:meth:`apply_bpm`, plus whether the result had to be clamped."""
        kind, value = self.bpm_modifier_type, self.bpm_modifier_value
        if kind == BPMModifierType.RELATIVE:
            raw = current + value
        elif kind == BPMModifierType.PERCENTAGE:
            raw = current * value / 100
        elif kind == BPMModifierType.MULTIPLIER:
            raw = current * value
        elif kind == BPMModifierType.RESET:
            return reset_bpm, False
        else:
            return (int(self.bpm) if self.bpm is not None else current), False
        bpm = clamp_bpm(raw)
        return bpm, bpm != int(raw)

    def __repr__(self) -> str:
        """String representation of the directive."""
        if self.type == DirectiveType.BPM:
            if self.bpm_modifier_type == BPMModifierType.ABSOLUTE:
                return f"Directive(BPM={self.bpm})"
            elif self.bpm_modifier_type == BPMModifierType.RELATIVE:
                sign = "+" if self.bpm_modifier_value >= 0 else ""
                return f"Directive(BPM={sign}{int(self.bpm_modifier_value)})"
            elif self.bpm_modifier_type == BPMModifierType.PERCENTAGE:
                return f"Directive(BPM={self.bpm_modifier_value}%)"
            elif self.bpm_modifier_type == BPMModifierType.MULTIPLIER:
                return f"Directive(BPM={self.bpm_modifier_value}x)"
            elif self.bpm_modifier_type == BPMModifierType.RESET:
                return f"Directive(BPM=reset)"
            return f"Directive(BPM={self.bpm})"
        elif self.type == DirectiveType.TIME_SIGNATURE:
            return f"Directive(TIME_SIG={self.beats}/{self.unit})"
        elif self.type == DirectiveType.KEY:
            return f"Directive(KEY={self.key})"
        elif self.type == DirectiveType.CAPO:
            return f"Directive(CAPO={self.capo})"
        elif self.type == DirectiveType.LOOP:
            return f"Directive(LOOP={self.label}, count={self.loop_count})"
        elif self.type == DirectiveType.LABEL:
            return f"Directive(LABEL={self.label})"
        return f"Directive(type={self.type})"

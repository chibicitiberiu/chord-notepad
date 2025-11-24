"""
Directive model for song instructions like BPM, time signature, etc.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class DirectiveType(IntEnum):
    """Enum for directive types."""
    BPM = 0
    TIME_SIGNATURE = 1
    KEY = 2
    LOOP = 3
    LABEL = 4
    UNKNOWN = 5  # For invalid/unparseable directives


class BPMModifierType(IntEnum):
    """Enum for BPM modifier types."""
    ABSOLUTE = 0        # {bpm: 120} - set to exact value
    RELATIVE = 1        # {bpm: +20} or {bpm: -20} - add/subtract from current
    PERCENTAGE = 2      # {bpm: 50%} - percentage of current
    MULTIPLIER = 3      # {bpm: 2x} or {bpm: 0.5x} - multiply current
    RESET = 4           # {bpm: reset} or {bpm: original} - restore initial


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
        elif self.type == DirectiveType.LOOP:
            return f"Directive(LOOP={self.label}, count={self.loop_count})"
        elif self.type == DirectiveType.LABEL:
            return f"Directive(LABEL={self.label})"
        return f"Directive(type={self.type})"

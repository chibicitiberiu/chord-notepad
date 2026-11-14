"""
Playback state model for tracking dynamic playback context
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LoopContext:
    """Represents a single loop level in the playback stack.

    Used for tracking nested loops during song playback.
    """

    label: str
    """Name of the label being looped"""

    start_line: int
    """Line number where the loop starts (1-indexed)"""

    current_iteration: int
    """Current iteration (1-indexed)"""

    max_iterations: int
    """Total number of iterations to perform"""

    def should_continue(self) -> bool:
        """Check if loop should continue.

        Returns:
            True if more iterations remain, False otherwise
        """
        return self.current_iteration < self.max_iterations

    def increment(self) -> None:
        """Increment the current iteration counter."""
        self.current_iteration += 1

    def __repr__(self) -> str:
        """String representation of the loop context."""
        return f"LoopContext(label='{self.label}', iteration={self.current_iteration}/{self.max_iterations})"


@dataclass
class PlaybackState:
    """Represents the dynamic state during song playback.

    This tracks all state that can change as directives are encountered
    during playback, including BPM, time signature, key, and loop contexts.
    """

    current_line: int = 0
    """Current line being played (0-indexed)"""

    current_chord_index: int = 0
    """Index of current chord within the line"""

    bpm: int = 120
    """Current beats per minute"""

    initial_bpm: int = 120
    """Initial BPM value (for reset functionality)"""

    time_signature_beats: int = 4
    """Current time signature numerator (beats per measure)"""

    time_signature_unit: int = 4
    """Current time signature denominator (beat unit)"""

    key: Optional[str] = None
    """Current key signature (e.g., 'C', 'Am', 'D')"""

    loop_stack: List[LoopContext] = field(default_factory=list)
    """Stack of active loop contexts (for nested loops)"""

    def set_bpm(self, bpm: int) -> None:
        """Update the current BPM.

        Args:
            bpm: New beats per minute value
        """
        self.bpm = bpm

    def reset_bpm(self) -> None:
        """Reset BPM to its initial value."""
        self.bpm = self.initial_bpm

    def set_time_signature(self, beats: int, unit: int) -> None:
        """Update the current time signature.

        Args:
            beats: Number of beats per measure
            unit: Beat unit (4 = quarter note, etc.)
        """
        self.time_signature_beats = beats
        self.time_signature_unit = unit

    def set_key(self, key: str) -> None:
        """Update the current key signature.

        Args:
            key: New key signature
        """
        self.key = key

    def push_loop(self, label: str, start_line: int, max_iterations: int) -> None:
        """Enter a new loop context.

        Args:
            label: Name of the loop label
            start_line: Line number where loop starts
            max_iterations: Total number of iterations
        """
        loop_ctx = LoopContext(
            label=label,
            start_line=start_line,
            current_iteration=1,
            max_iterations=max_iterations
        )
        self.loop_stack.append(loop_ctx)

    def pop_loop(self) -> Optional[LoopContext]:
        """Exit the current loop context.

        Returns:
            The popped LoopContext, or None if stack was empty
        """
        if self.loop_stack:
            return self.loop_stack.pop()
        return None

    def current_loop(self) -> Optional[LoopContext]:
        """Get the current active loop without removing it.

        Returns:
            The current LoopContext, or None if no active loops
        """
        if self.loop_stack:
            return self.loop_stack[-1]
        return None

    def is_in_loop(self) -> bool:
        """Check if currently inside a loop.

        Returns:
            True if loop_stack is not empty, False otherwise
        """
        return len(self.loop_stack) > 0

    def __repr__(self) -> str:
        """String representation of the playback state."""
        return (f"PlaybackState(line={self.current_line}, "
                f"bpm={self.bpm}, key={self.key}, loops={len(self.loop_stack)})")

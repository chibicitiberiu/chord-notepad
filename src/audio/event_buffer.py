"""Thread-safe event buffer for producer-consumer playback architecture."""
import threading
from collections import deque
from typing import Optional

from models.playback_event_internal import MidiEvent


class EventBuffer:
    """Thread-safe circular buffer for MIDI events.

    This buffer decouples event production (chord computation) from event
    consumption (playback). The producer thread pushes pre-computed events,
    and the playback thread pops them for playback.

    The buffer has a fixed capacity and will block the producer when full,
    providing backpressure to prevent unbounded memory growth.
    """

    def __init__(self, capacity: int = 100):
        """Initialize the event buffer.

        Args:
            capacity: Maximum number of events the buffer can hold
        """
        self._capacity = capacity
        self._buffer = deque()
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)
        self._closed = False

    def push_event(self, event: MidiEvent, timeout: Optional[float] = None) -> bool:
        """Push an event to the buffer (blocks if full).

        Args:
            event: The MIDI event to add to the buffer
            timeout: Maximum time to wait if buffer is full (None = wait forever)

        Returns:
            True if event was added, False if timeout occurred or buffer closed

        Raises:
            ValueError: If buffer is closed
        """
        with self._not_full:
            # Wait until buffer has space or timeout
            while len(self._buffer) >= self._capacity and not self._closed:
                if not self._not_full.wait(timeout=timeout):
                    return False  # Timeout occurred

            if self._closed:
                raise ValueError("Cannot push to closed buffer")

            self._buffer.append(event)
            self._not_empty.notify()  # Wake up consumer
            return True

    def pop_event(self, timeout: Optional[float] = None) -> Optional[MidiEvent]:
        """Pop an event from the buffer (blocks if empty).

        Args:
            timeout: Maximum time to wait if buffer is empty (None = wait forever)

        Returns:
            The next MIDI event, or None if timeout occurred or buffer closed
        """
        with self._not_empty:
            # Wait until buffer has events or timeout
            while len(self._buffer) == 0 and not self._closed:
                if not self._not_empty.wait(timeout=timeout):
                    return None  # Timeout occurred

            if len(self._buffer) == 0:
                return None  # Buffer closed and empty

            event = self._buffer.popleft()
            self._not_full.notify()  # Wake up producer
            return event

    def peek_next(self) -> Optional[MidiEvent]:
        """Peek at the next event without removing it.

        Returns:
            The next MIDI event, or None if buffer is empty
        """
        with self._lock:
            return self._buffer[0] if self._buffer else None

    def clear(self) -> None:
        """Clear all events from the buffer."""
        with self._lock:
            self._buffer.clear()
            self._not_full.notify_all()  # Wake up any waiting producers

    def close(self) -> None:
        """Close the buffer, preventing further pushes and waking all waiting threads."""
        with self._lock:
            self._closed = True
            self._not_full.notify_all()
            self._not_empty.notify_all()

    def is_empty(self) -> bool:
        """Check if the buffer is empty.

        Returns:
            True if buffer has no events
        """
        with self._lock:
            return len(self._buffer) == 0

    def is_full(self) -> bool:
        """Check if the buffer is full.

        Returns:
            True if buffer is at capacity
        """
        with self._lock:
            return len(self._buffer) >= self._capacity

    def size(self) -> int:
        """Get the current number of events in the buffer.

        Returns:
            Number of events currently in buffer
        """
        with self._lock:
            return len(self._buffer)

    def remaining_capacity(self) -> int:
        """Get the remaining capacity of the buffer.

        Returns:
            Number of additional events that can be added
        """
        with self._lock:
            return self._capacity - len(self._buffer)

    @property
    def capacity(self) -> int:
        """Get the total capacity of the buffer."""
        return self._capacity

    def __len__(self) -> int:
        """Get the current size of the buffer."""
        return self.size()

    def __repr__(self) -> str:
        """String representation for debugging."""
        with self._lock:
            return f"EventBuffer(size={len(self._buffer)}/{self._capacity}, closed={self._closed})"

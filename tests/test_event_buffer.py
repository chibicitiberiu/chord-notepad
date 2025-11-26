"""Comprehensive tests for EventBuffer."""
import pytest
import threading
import time
from models.playback_event_internal import MidiEvent, MidiEventType


@pytest.fixture
def event_buffer():
    """Create an EventBuffer instance."""
    from audio.event_buffer import EventBuffer
    return EventBuffer(capacity=10)


class TestEventBufferBasics:
    """Test basic EventBuffer operations."""

    def test_buffer_creation(self, event_buffer):
        """Test buffer is created with correct capacity."""
        assert event_buffer.capacity == 10
        assert event_buffer.is_empty()
        assert not event_buffer.is_full()
        assert event_buffer.size() == 0

    def test_push_single_event(self, event_buffer):
        """Test pushing a single event."""
        event = MidiEvent(timestamp=0.0, event_type=MidiEventType.NOTE_ON, midi_notes=[60])
        result = event_buffer.push_event(event)

        assert result is True
        assert event_buffer.size() == 1
        assert not event_buffer.is_empty()

    def test_pop_single_event(self, event_buffer):
        """Test popping a single event."""
        event = MidiEvent(timestamp=0.0, event_type=MidiEventType.NOTE_ON, midi_notes=[60])
        event_buffer.push_event(event)

        popped = event_buffer.pop_event()
        assert popped is not None
        assert popped.timestamp == 0.0
        assert popped.midi_notes == [60]
        assert event_buffer.is_empty()

    def test_peek_event(self, event_buffer):
        """Test peeking at next event without removing it."""
        event = MidiEvent(timestamp=0.0, event_type=MidiEventType.NOTE_ON, midi_notes=[60])
        event_buffer.push_event(event)

        peeked = event_buffer.peek_next()
        assert peeked is not None
        assert peeked.timestamp == 0.0
        assert event_buffer.size() == 1  # Should still be there

    def test_buffer_capacity(self, event_buffer):
        """Test buffer respects capacity."""
        # Fill buffer to capacity
        for i in range(10):
            event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
            result = event_buffer.push_event(event, timeout=0.1)
            assert result is True

        assert event_buffer.is_full()
        assert event_buffer.size() == 10

        # Try to add one more - should timeout
        event = MidiEvent(timestamp=11.0, event_type=MidiEventType.NOTE_ON, midi_notes=[71])
        result = event_buffer.push_event(event, timeout=0.1)
        assert result is False  # Timeout

    def test_fifo_order(self, event_buffer):
        """Test events are retrieved in FIFO order."""
        events = [
            MidiEvent(timestamp=0.0, event_type=MidiEventType.NOTE_ON, midi_notes=[60]),
            MidiEvent(timestamp=1.0, event_type=MidiEventType.NOTE_ON, midi_notes=[62]),
            MidiEvent(timestamp=2.0, event_type=MidiEventType.NOTE_OFF, midi_notes=[60]),
        ]

        for event in events:
            event_buffer.push_event(event)

        # Pop in order
        for i, expected_event in enumerate(events):
            popped = event_buffer.pop_event()
            assert popped.timestamp == expected_event.timestamp
            assert popped.midi_notes == expected_event.midi_notes

    def test_clear_buffer(self, event_buffer):
        """Test clearing the buffer."""
        # Add some events
        for i in range(5):
            event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
            event_buffer.push_event(event)

        assert event_buffer.size() == 5

        event_buffer.clear()

        assert event_buffer.is_empty()
        assert event_buffer.size() == 0


class TestEventBufferThreadSafety:
    """Test EventBuffer thread safety."""

    def test_concurrent_push_pop(self, event_buffer):
        """Test concurrent pushes and pops."""
        pushed_count = [0]
        popped_count = [0]

        def producer():
            for i in range(20):
                event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
                if event_buffer.push_event(event, timeout=1.0):
                    pushed_count[0] += 1
                time.sleep(0.01)

        def consumer():
            while popped_count[0] < 20:
                event = event_buffer.pop_event(timeout=0.1)
                if event:
                    popped_count[0] += 1
                if popped_count[0] >= 20:
                    break

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join(timeout=5.0)
        consumer_thread.join(timeout=5.0)

        assert pushed_count[0] == 20
        assert popped_count[0] == 20

    def test_blocking_on_empty(self, event_buffer):
        """Test pop blocks when buffer is empty."""
        start_time = time.time()
        event = event_buffer.pop_event(timeout=0.2)
        elapsed = time.time() - start_time

        assert event is None
        assert elapsed >= 0.2

    def test_blocking_on_full(self, event_buffer):
        """Test push blocks when buffer is full."""
        # Fill buffer
        for i in range(10):
            event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
            event_buffer.push_event(event)

        # Try to push with timeout
        start_time = time.time()
        event = MidiEvent(timestamp=11.0, event_type=MidiEventType.NOTE_ON, midi_notes=[71])
        result = event_buffer.push_event(event, timeout=0.2)
        elapsed = time.time() - start_time

        assert result is False
        assert elapsed >= 0.2


class TestEventBufferClosure:
    """Test EventBuffer closure behavior."""

    def test_close_buffer(self, event_buffer):
        """Test closing the buffer."""
        event_buffer.close()

        # Try to push - should raise ValueError
        event = MidiEvent(timestamp=0.0, event_type=MidiEventType.NOTE_ON, midi_notes=[60])
        with pytest.raises(ValueError):
            event_buffer.push_event(event)

    def test_pop_from_closed_buffer(self, event_buffer):
        """Test popping from closed buffer returns None."""
        event_buffer.close()

        event = event_buffer.pop_event(timeout=0.1)
        assert event is None


class TestEventBufferEdgeCases:
    """Test edge cases for EventBuffer."""

    def test_pop_from_empty_buffer(self, event_buffer):
        """Test popping from empty buffer with timeout."""
        event = event_buffer.pop_event(timeout=0.1)
        assert event is None

    def test_remaining_capacity(self, event_buffer):
        """Test remaining capacity calculation."""
        assert event_buffer.remaining_capacity() == 10

        # Add 3 events
        for i in range(3):
            event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
            event_buffer.push_event(event)

        assert event_buffer.remaining_capacity() == 7

    def test_len_method(self, event_buffer):
        """Test __len__ method."""
        assert len(event_buffer) == 0

        for i in range(5):
            event = MidiEvent(timestamp=float(i), event_type=MidiEventType.NOTE_ON, midi_notes=[60+i])
            event_buffer.push_event(event)

        assert len(event_buffer) == 5

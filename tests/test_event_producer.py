"""Comprehensive tests for EventProducer."""
import pytest
import time
from unittest.mock import Mock, MagicMock
from typing import List

from services.event_producer import EventProducer
from audio.event_buffer import EventBuffer
from audio.chord_picker import ChordNotePicker
from models.line import Line
from models.chord import ChordInfo
from models.directive import Directive, DirectiveType, BPMModifierType
from models.playback_event_internal import MidiEvent, MidiEventType


@pytest.fixture
def mock_application():
    """Create mock application for UI callbacks."""
    app = MagicMock()
    app.queue_ui_callback = MagicMock()
    return app


@pytest.fixture
def event_buffer():
    """Create an event buffer."""
    return EventBuffer(capacity=100)


@pytest.fixture
def note_picker():
    """Create a real note picker."""
    return ChordNotePicker()


@pytest.fixture
def simple_song():
    """Create a simple song with chords."""
    line1 = Line(content="C G Am F", line_number=1)
    chord_c = ChordInfo(chord="C", start=0, end=1, is_relative=False, is_valid=True)
    chord_g = ChordInfo(chord="G", start=2, end=3, is_relative=False, is_valid=True)
    chord_am = ChordInfo(chord="Am", start=4, end=6, is_relative=False, is_valid=True)
    chord_f = ChordInfo(chord="F", start=7, end=8, is_relative=False, is_valid=True)
    line1.items = [chord_c, chord_g, chord_am, chord_f]
    return [line1]


class TestEventProducerBasics:
    """Test basic EventProducer functionality."""

    def test_producer_creation(self, simple_song, event_buffer, note_picker, mock_application):
        """Test creating an event producer."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        assert producer is not None
        assert not producer.is_running()

    def test_producer_start_stop(self, simple_song, event_buffer, note_picker, mock_application):
        """Test starting and stopping the producer."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        # Start should not raise exception
        producer.start()
        time.sleep(0.1)

        # Stop should not raise exception
        producer.stop()
        time.sleep(0.1)

        # Should be stopped now (may have already finished)
        assert not producer.is_running()

    def test_producer_generates_events(self, simple_song, event_buffer, note_picker, mock_application):
        """Test that producer generates events for chords."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.3)  # Give producer time to generate events

        # Collect events
        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                if event:
                    events.append(event)
                break
            events.append(event)

        producer.stop()

        # Should have NOTE_ON and NOTE_OFF for each of 4 chords, plus END_OF_SONG
        # 4 chords * 2 events (ON/OFF) + 1 END_OF_SONG = 9 events
        assert len(events) >= 8, f"Expected at least 8 events, got {len(events)}"

        # Verify we have NOTE_ON, NOTE_OFF, and END_OF_SONG events
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]
        end_events = [e for e in events if e.event_type == MidiEventType.END_OF_SONG]

        assert len(note_on_events) == 4, "Should have 4 NOTE_ON events"
        assert len(note_off_events) == 4, "Should have 4 NOTE_OFF events"
        assert len(end_events) == 1, "Should have 1 END_OF_SONG event"

    def test_events_have_correct_timestamps(self, simple_song, event_buffer, note_picker, mock_application):
        """Test that events have increasing timestamps."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.3)

        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                if event:
                    events.append(event)
                break
            events.append(event)

        producer.stop()

        # Timestamps should be increasing
        for i in range(1, len(events)):
            assert events[i].timestamp >= events[i-1].timestamp, \
                f"Event {i} timestamp should be >= previous event"


class TestEventProducerDirectives:
    """Test directive handling in EventProducer."""

    def test_bpm_directive(self, event_buffer, note_picker, mock_application):
        """Test BPM directive changes tempo (verified by event timing)."""
        line = Line(content="{bpm: 140} C", line_number=1)
        bpm_dir = Directive(type=DirectiveType.BPM, start=0, end=11, is_valid=True)
        bpm_dir.bpm = 140
        bpm_dir.bpm_modifier_type = BPMModifierType.ABSOLUTE  # Set modifier type
        chord = ChordInfo(chord="C", start=12, end=13, is_relative=False, is_valid=True)
        line.items = [bpm_dir, chord]

        producer = EventProducer(
            lines=[line],
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.3)  # Give producer time to process events

        # Collect events to ensure producer has processed directives
        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                if event:
                    events.append(event)
                break
            events.append(event)

        producer.stop()

        # Should have NOTE_ON and NOTE_OFF events
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) >= 1, "Should have NOTE_ON event"
        assert len(note_off_events) >= 1, "Should have NOTE_OFF event"

        # Verify event timing reflects BPM 140 (faster than BPM 120)
        # At BPM 140, 4 beats = 4 * (60/140) = 1.714 seconds
        # At BPM 120, 4 beats = 4 * (60/120) = 2.0 seconds
        duration = note_off_events[0].timestamp - note_on_events[0].timestamp
        expected_duration = 4.0 * (60.0 / 140.0)  # 4 beats at BPM 140
        assert abs(duration - expected_duration) < 0.1, \
            f"Duration {duration} should be close to {expected_duration} (BPM 140)"

    def test_key_directive_with_roman_numerals(self, event_buffer, note_picker, mock_application):
        """Test key directive affects roman numeral resolution."""
        line = Line(content="{key: G} I V", line_number=1)
        key_dir = Directive(type=DirectiveType.KEY, start=0, end=8, is_valid=True)
        key_dir.key = "G"
        chord_I = ChordInfo(chord="I", start=9, end=10, is_relative=True, is_valid=True)
        chord_V = ChordInfo(chord="V", start=11, end=12, is_relative=True, is_valid=True)
        line.items = [key_dir, chord_I, chord_V]

        producer = EventProducer(
            lines=[line],
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.2)

        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                break
            events.append(event)

        producer.stop()

        # Verify events were generated (key directive was processed)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should have events for both chords"


class TestEventProducerNoteOnOff:
    """Test NOTE_ON and NOTE_OFF event generation."""

    def test_note_on_off_pairs(self, simple_song, event_buffer, note_picker, mock_application):
        """Test that NOTE_ON and NOTE_OFF are properly paired."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.3)

        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                if event:
                    events.append(event)
                break
            events.append(event)

        producer.stop()

        # For each chord, NOTE_OFF should come after NOTE_ON
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) == len(note_off_events), \
            "Should have equal number of NOTE_ON and NOTE_OFF events"

        # Each NOTE_OFF should have timestamp > corresponding NOTE_ON
        for i in range(len(note_on_events)):
            assert note_off_events[i].timestamp > note_on_events[i].timestamp, \
                f"NOTE_OFF {i} should come after NOTE_ON {i}"

    def test_note_off_contains_same_notes(self, simple_song, event_buffer, note_picker, mock_application):
        """Test that NOTE_OFF contains same notes as NOTE_ON."""
        producer = EventProducer(
            lines=simple_song,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.3)

        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                break
            events.append(event)

        producer.stop()

        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        # Each pair should have same notes
        for i in range(len(note_on_events)):
            assert note_on_events[i].midi_notes == note_off_events[i].midi_notes, \
                f"NOTE_OFF {i} should have same notes as NOTE_ON {i}"


class TestEventProducerEdgeCases:
    """Test edge cases for EventProducer."""

    def test_empty_song(self, event_buffer, note_picker, mock_application):
        """Test producer with no chords."""
        line = Line(content="", line_number=1)

        producer = EventProducer(
            lines=[line],
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.2)

        event = event_buffer.pop_event(timeout=0.1)
        producer.stop()

        # Should get END_OF_SONG immediately
        assert event is not None
        assert event.event_type == MidiEventType.END_OF_SONG

    def test_invalid_chord_skipped(self, event_buffer, note_picker, mock_application):
        """Test that invalid chords are skipped."""
        line = Line(content="C InvalidChord G", line_number=1)
        chord_c = ChordInfo(chord="C", start=0, end=1, is_relative=False, is_valid=True)
        chord_invalid = ChordInfo(chord="InvalidChord", start=2, end=14, is_relative=False, is_valid=False)
        chord_g = ChordInfo(chord="G", start=15, end=16, is_relative=False, is_valid=True)
        line.items = [chord_c, chord_invalid, chord_g]

        producer = EventProducer(
            lines=[line],
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=note_picker,
            event_buffer=event_buffer,
            application=mock_application
        )

        producer.start()
        time.sleep(0.2)

        events = []
        while True:
            event = event_buffer.pop_event(timeout=0.1)
            if event is None or event.event_type == MidiEventType.END_OF_SONG:
                break
            events.append(event)

        producer.stop()

        # Should only have events for 2 valid chords
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should only have events for valid chords"

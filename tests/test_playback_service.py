"""Comprehensive unit tests for PlaybackService."""

import pytest
import time
from unittest.mock import Mock, MagicMock, call, patch
from typing import List, Optional, Tuple

from services.playback_service import PlaybackService
from services.config_service import ConfigService
from src.models.line import Line
from src.models.chord import ChordInfo
from src.models.directive import Directive, DirectiveType, BPMModifierType
from src.models.playback_state import PlaybackState
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from models.playback_event_internal import MidiEvent, MidiEventType


@pytest.fixture
def mock_config():
    """Create a mock config service."""
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: {
        "bpm": 120,
        "time_signature_beats": 4,
        "time_signature_unit": 4,
        "soundfont_path": None
    }.get(key, default)
    return config


@pytest.fixture
def mock_player():
    """Create a mock NotePlayer that simulates event consumption."""
    import threading
    player = MagicMock()
    player.is_playing = False
    player.event_buffer = None
    player.on_event_callback = None
    player.application = None
    player.consumed_events = []  # Store consumed events for test verification

    def mock_start_playback():
        """Simulate playback by consuming events from buffer and firing callbacks."""
        def consume_events():
            if not player.event_buffer:
                return
            while True:
                event = player.event_buffer.pop_event(timeout=0.1)
                if event is None:
                    continue
                # Store event for test verification
                player.consumed_events.append(event)
                from models.playback_event_internal import MidiEventType
                if event.event_type == MidiEventType.END_OF_SONG:
                    break
                # Fire callback if this is a NOTE_ON event with callback data
                if (event.event_type == MidiEventType.NOTE_ON and
                    player.on_event_callback and player.application and
                    event.metadata.get('has_callback')):
                    from models.playback_event import PlaybackEventArgs, PlaybackEventType
                    event_args = PlaybackEventArgs(
                        event_type=PlaybackEventType.CHORD_START,
                        chord_info=event.metadata.get('chord_info'),
                        bpm=event.metadata.get('bpm'),
                        time_signature_beats=event.metadata.get('time_signature_beats'),
                        time_signature_unit=event.metadata.get('time_signature_unit'),
                        key=event.metadata.get('key'),
                        current_line=event.metadata.get('line_index'),
                        current_bar=event.metadata.get('bar'),
                        total_bars=event.metadata.get('total_bars')
                    )
                    player.application.queue_ui_callback(lambda args=event_args: player.on_event_callback(args))

        thread = threading.Thread(target=consume_events, daemon=True)
        thread.start()

    player.start_playback.side_effect = mock_start_playback

    def mock_set_event_buffer(buffer):
        player.event_buffer = buffer
    player.set_event_buffer.side_effect = mock_set_event_buffer

    def mock_set_event_callback(callback, application):
        player.on_event_callback = callback
        player.application = application
    player.set_event_callback.side_effect = mock_set_event_callback

    return player


@pytest.fixture
def mock_application():
    """Create a mock Application."""
    app = MagicMock()
    app.queue_ui_callback = MagicMock()
    return app


@pytest.fixture
def playback_service(mock_config, mock_player, mock_application):
    """Create a PlaybackService instance with mocked dependencies."""
    service = PlaybackService(mock_config, player=mock_player, application=mock_application)
    # Initialize playback state since we're injecting the player
    service._playback_state = PlaybackState(
        bpm=120,
        initial_bpm=120,
        time_signature_beats=4,
        time_signature_unit=4
    )
    return service


@pytest.fixture
def initialized_service(playback_service, mock_player):
    """Create an initialized PlaybackService with mocked player."""
    return playback_service, mock_player


def collect_events_from_buffer(service, max_events=100, timeout=2.0):
    """Helper function to collect events from the event buffer for testing.

    Since the mock player consumes events from the buffer, this function
    retrieves events from the mock player's consumed_events list instead.

    Args:
        service: PlaybackService instance
        max_events: Maximum number of events to collect
        timeout: Maximum time to wait for events in seconds

    Returns:
        List of MidiEvent objects
    """
    start_time = time.time()

    # Wait for events to be consumed by the mock player
    while (time.time() - start_time) < timeout:
        if hasattr(service._player, 'consumed_events'):
            # Check if we have enough events or if END_OF_SONG was received
            events = service._player.consumed_events
            if len(events) >= max_events:
                return events[:max_events]
            if any(e.event_type == MidiEventType.END_OF_SONG for e in events):
                return events
        time.sleep(0.05)

    # Return whatever events were collected
    if hasattr(service._player, 'consumed_events'):
        return service._player.consumed_events[:max_events]
    return []


class TestInitialization:
    """Tests for PlaybackService initialization."""

    def test_player_injected_on_construction(self, playback_service, mock_player):
        """Test that player is properly injected during construction."""
        assert playback_service.is_initialized is True
        assert playback_service._player is mock_player

    def test_initialize_player_creates_real_player(self, mock_config):
        """Test that initialize_player creates a real player when none injected."""
        service = PlaybackService(mock_config)  # No player injected

        with patch('services.playback_service.NotePlayer') as mock_note_player_class:
            mock_player = Mock()
            mock_note_player_class.return_value = mock_player

            result = service.initialize_player()

            assert result is True
            assert service.is_initialized is True
            mock_note_player_class.assert_called_once_with(
                soundfont_path=None,
                bpm=120,
                time_signature=(4, 4)
            )

    def test_initialize_player_failure(self, mock_config):
        """Test player initialization failure handling."""
        service = PlaybackService(mock_config)  # No player injected

        with patch('services.playback_service.NotePlayer', side_effect=Exception("Init failed")):
            result = service.initialize_player()

            assert result is False
            assert service.is_initialized is False


class TestChordPlayback:
    """Tests for immediate chord playback."""

    def test_play_chord_immediate_absolute(self, initialized_service):
        """Test playing an absolute chord immediately."""
        service, mock_player = initialized_service

        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)
        service.play_chord_immediate(chord, current_key=None)

        # Verify play_notes_immediate was called
        mock_player.play_notes_immediate.assert_called_once()

        # Get the MIDI notes that were played
        call_args = mock_player.play_notes_immediate.call_args[0]
        midi_notes = call_args[0]

        # C major chord should have notes (3+ depending on voicing)
        assert len(midi_notes) >= 3
        assert all(isinstance(note, int) for note in midi_notes)

    def test_play_chord_immediate_roman_numeral(self, initialized_service):
        """Test playing a roman numeral chord with key context."""
        service, mock_player = initialized_service

        # I in C = C major
        chord = ChordInfo(chord="I", start=0, end=1, is_valid=True, is_relative=True)
        service.play_chord_immediate(chord, current_key="C")

        mock_player.play_notes_immediate.assert_called_once()
        call_args = mock_player.play_notes_immediate.call_args[0]
        midi_notes = call_args[0]

        assert len(midi_notes) >= 3
        assert all(isinstance(note, int) for note in midi_notes)

    def test_play_chord_immediate_invalid_chord(self, initialized_service):
        """Test that invalid chords don't crash."""
        service, mock_player = initialized_service

        chord = ChordInfo(chord="XYZ123", start=0, end=6, is_valid=False, is_relative=False)
        service.play_chord_immediate(chord, current_key=None)

        # Should not call player for invalid chord
        mock_player.play_notes_immediate.assert_not_called()

    def test_play_chord_immediate_not_initialized(self, playback_service):
        """Test that playing without initialization fails gracefully."""
        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)

        # Should not crash when not initialized
        playback_service.play_chord_immediate(chord, current_key=None)


class TestSongPlayback:
    """Tests for song playback with lines and directives."""

    def test_start_song_playback_basic(self, initialized_service, song_parser):
        """Test basic song playback with simple chords."""
        service, mock_player = initialized_service

        # Parse lines with chords
        text = "C G"
        lines = song_parser.detect_chords_in_text(text)

        result = service.start_song_playback(lines, initial_key="C")

        assert result is True
        # Check that event buffer was set on player (new producer-consumer architecture)
        mock_player.set_event_buffer.assert_called_once()
        mock_player.start_playback.assert_called_once()
        # Verify event buffer and producer were created
        assert service._event_buffer is not None
        assert service._event_producer is not None

    def test_start_song_playback_no_chords(self, initialized_service):
        """Test that playback returns False when no chords present."""
        service, mock_player = initialized_service

        line = Line(content="Just text", line_number=1)
        lines = [line]

        result = service.start_song_playback(lines, initial_key="C")

        assert result is False
        mock_player.start_playback.assert_not_called()

    def test_start_song_playback_with_callback(self, initialized_service, song_parser):
        """Test that finished callback is registered."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        callback = Mock()
        result = service.start_song_playback(lines, initial_key="C", on_finished_callback=callback)

        assert result is True
        mock_player.set_playback_finished_callback.assert_called_once_with(callback)


class TestDirectiveHandling:
    """Tests for directive processing during playback."""

    def test_bpm_directive(self, initialized_service, song_parser):
        """Test BPM directive changes tempo."""
        service, mock_player = initialized_service

        # Parse line with BPM directive and chord
        text = "{bpm: 140} C"
        lines = song_parser.detect_chords_in_text(text)

        # Start playback - this creates the event producer
        service.start_song_playback(lines, initial_key="C")

        # Give producer time to process directive
        time.sleep(0.1)

        # Verify BPM was changed on the player
        mock_player.set_bpm.assert_called_with(140)

    def test_key_directive_changes_resolution(self, initialized_service, song_parser):
        """Test KEY directive changes roman numeral resolution."""
        service, mock_player = initialized_service

        # Parse line: {key: G} I (should resolve to G, not C)
        text = "{key: G} I"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]

        # Should have NOTE_ON event for I in G (G major)
        assert len(note_on_events) >= 1, "Should have NOTE_ON event for chord"
        assert len(note_on_events[0].midi_notes) >= 3, "Chord should have at least 3 notes"

    def test_time_signature_directive(self, initialized_service, song_parser):
        """Test TIME directive changes default duration."""
        service, mock_player = initialized_service

        text = "{time: 3/4} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) == 1
        assert len(note_off_events) == 1

        # Duration should be 3 beats (full measure in 3/4)
        # 3 beats at 120 BPM = 3 * (60/120) = 1.5 seconds
        duration_seconds = note_off_events[0].timestamp - note_on_events[0].timestamp
        expected_duration = 3.0 * (60.0 / 120.0)
        assert abs(duration_seconds - expected_duration) < 0.1


class TestEnhancedBPMDirectives:
    """Tests for enhanced BPM directive handling during playback."""

    def test_relative_bpm_increase(self, initialized_service, song_parser):
        """Test relative BPM increase during playback."""
        service, mock_player = initialized_service

        # Parse line with relative BPM directive
        text = "{bpm: +20} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)  # Give producer time to process directives

        # Verify BPM increased from 120 to 140
        mock_player.set_bpm.assert_called_with(140)

    def test_relative_bpm_decrease(self, initialized_service, song_parser):
        """Test relative BPM decrease during playback."""
        service, mock_player = initialized_service

        text = "{bpm: -30} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)

        # Verify BPM decreased from 120 to 90
        mock_player.set_bpm.assert_called_with(90)

    def test_percentage_bpm_half_speed(self, initialized_service, song_parser):
        """Test percentage BPM (50% = half speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 50%} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)

        # Verify BPM set to 50% (60)
        mock_player.set_bpm.assert_called_with(60)

    def test_percentage_bpm_faster(self, initialized_service, song_parser):
        """Test percentage BPM (150% = 1.5x speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 150%} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)

        # Verify BPM set to 150% (180)
        mock_player.set_bpm.assert_called_with(180)

    def test_multiplier_bpm_half_speed(self, initialized_service, song_parser):
        """Test multiplier BPM (0.5x = half speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 0.5x} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)

        # Verify BPM multiplied by 0.5 (60)
        mock_player.set_bpm.assert_called_with(60)

    def test_multiplier_bpm_double_speed(self, initialized_service, song_parser):
        """Test multiplier BPM (2x = double speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 2x} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.1)

        # Verify BPM multiplied by 2 (240)
        mock_player.set_bpm.assert_called_with(240)

    def test_reset_bpm_after_changes(self, initialized_service, song_parser):
        """Test reset BPM returns to initial value."""
        service, mock_player = initialized_service

        # Parse multi-line text with BPM change and reset
        text = "{bpm: 180} C\n{bpm: reset} G"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        # Verify BPM was set to 180, then reset to 120
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(180) for call in calls), "Should set BPM to 180"
        assert any(call == call(120) for call in calls), "Should reset BPM to 120"

    def test_chained_bpm_modifiers(self, initialized_service, song_parser):
        """Test multiple BPM modifiers applied in sequence."""
        service, mock_player = initialized_service

        # Start at 120, double to 240, then halve to 120
        text = "{bpm: 2x} C\n{bpm: 50%} G"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        # Verify BPM progression
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(240) for call in calls), "Should set BPM to 240 (2x)"
        assert any(call == call(120) for call in calls), "Should set BPM to 120 (50% of 240)"


class TestLoopStateRestoration:
    """Tests for state restoration when looping back to labels."""

    def test_bpm_restored_on_loop(self, initialized_service, song_parser):
        """Test that BPM is restored when looping back to a label."""
        service, mock_player = initialized_service

        # Create a song where BPM changes inside a loop
        # loop count 2 means: original play + 1 repeat = 2 total
        text = """{label: verse} C
{bpm: 2x} G
{loop: verse 2}
F"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]

        # Should play: C, G (loop), C, G, F = 5 chords
        assert len(note_on_events) == 5, f"Should have 5 chords (C, G, C, G, F), got {len(note_on_events)}"

        # Verify BPM was set to 240 (2x) and restored to 120
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(240) for call in calls), "Should set BPM to 240 (2x)"
        assert any(call == call(120) for call in calls), "Should restore BPM to 120"

    def test_key_restored_on_loop_with_relative_chords(self, initialized_service, song_parser):
        """Test that key is restored when looping with relative (roman numeral) chords."""
        service, mock_player = initialized_service

        # Create a song where key changes inside a loop with roman numerals
        text = """{label: chorus} I
{key: G} I
{loop: chorus 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]

        # Should play: I in C, I in G, (loop), I in C, I in G = 4 chords
        assert len(note_on_events) == 4, f"Should have 4 chords, got {len(note_on_events)}"

        # Verify the key changed and was restored by checking MIDI notes
        # Events 0 and 2 should be I in C (same notes)
        # Events 1 and 3 should be I in G (same notes)
        assert note_on_events[0].midi_notes != note_on_events[1].midi_notes, \
            "I in C and I in G should have different notes"
        assert note_on_events[0].midi_notes == note_on_events[2].midi_notes, \
            "I chord should be same notes after loop (key restored)"

    def test_key_directive_doesnt_affect_absolute_chords(self, initialized_service, song_parser):
        """Test that key directives don't affect absolute chords (they shouldn't)."""
        service, mock_player = initialized_service

        # Absolute chords should play the same regardless of key directive
        text = """{label: start} C
{key: G} C
{loop: start 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]

        # Should play: C, C, (loop), C, C = 4 chords
        assert len(note_on_events) == 4, f"Should have 4 chords, got {len(note_on_events)}"

        # All C chords should be identical (absolute chord not affected by key)
        for i in range(1, len(note_on_events)):
            assert note_on_events[i].midi_notes == note_on_events[0].midi_notes, \
                f"All C chords should have same notes (event {i})"

    def test_time_signature_restored_on_loop(self, initialized_service, song_parser):
        """Test that time signature is restored when looping back to a label."""
        service, mock_player = initialized_service

        # Create a song where time signature changes inside a loop
        text = """{label: section} C
{time: 3/4} G
{loop: section 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        # Should play: C (4/4), G (3/4), (loop), C (4/4), G (3/4) = 4 chords
        assert len(note_on_events) == 4, f"Should have 4 chords, got {len(note_on_events)}"

        # Check durations of first and third chord (both C in 4/4)
        dur1 = note_off_events[0].timestamp - note_on_events[0].timestamp
        dur3 = note_off_events[2].timestamp - note_on_events[2].timestamp
        expected_4_4 = 4.0 * (60.0 / 120.0)  # 4 beats at 120 BPM

        assert abs(dur1 - expected_4_4) < 0.1, "First C should be 4 beats"
        assert abs(dur3 - expected_4_4) < 0.1, "Third C should be 4 beats (time sig restored)"

    def test_multiple_state_changes_restored(self, initialized_service, song_parser):
        """Test that all state changes (BPM, key, time sig) are restored together."""
        service, mock_player = initialized_service

        # Create a song with multiple state changes in a loop
        text = """{label: bridge} {bpm: 100} C
{bpm: 2x} {key: G} {time: 3/4} I
{loop: bridge 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]

        # Should play: C, I (loop), C, I = 4 chords
        assert len(note_on_events) >= 4, f"Should have at least 4 chords, got {len(note_on_events)}"

        # Verify BPM was set and restored
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(100) for call in calls), "Should set BPM to 100"
        assert any(call == call(200) for call in calls), "Should set BPM to 200 (2x)"


class TestChordDurations:
    """Tests for chord duration handling."""

    def test_chord_with_explicit_duration(self, initialized_service, song_parser):
        """Test chord with *N duration notation."""
        service, mock_player = initialized_service

        # Parse chord with duration
        text = "C*2"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)  # Give producer time to generate events

        # Collect events from buffer
        events = collect_events_from_buffer(service)

        # Should have NOTE_ON and NOTE_OFF events
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) == 1, "Should have 1 NOTE_ON event"
        assert len(note_off_events) == 1, "Should have 1 NOTE_OFF event"

        # Check duration by looking at timestamp difference
        # Duration of 2 beats at 120 BPM = 2 * (60/120) = 1.0 seconds
        duration_seconds = note_off_events[0].timestamp - note_on_events[0].timestamp
        expected_duration = 2.0 * (60.0 / 120.0)  # 2 beats at 120 BPM
        assert abs(duration_seconds - expected_duration) < 0.1, \
            f"Expected duration ~{expected_duration}s, got {duration_seconds}s"

    def test_chord_default_duration(self, initialized_service, song_parser):
        """Test chord without duration uses measure length."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        note_off_events = [e for e in events if e.event_type == MidiEventType.NOTE_OFF]

        assert len(note_on_events) == 1
        assert len(note_off_events) == 1

        # Default 4/4 time = 4 beats at 120 BPM = 4 * (60/120) = 2.0 seconds
        duration_seconds = note_off_events[0].timestamp - note_on_events[0].timestamp
        expected_duration = 4.0 * (60.0 / 120.0)
        assert abs(duration_seconds - expected_duration) < 0.1


class TestLoopMechanics:
    """Tests for label and loop directive handling."""

    def test_label_directive(self, initialized_service, song_parser):
        """Test that labels are processed and chord is played."""
        service, mock_player = initialized_service

        text = "{label: verse} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        # Should have NOTE_ON event for the chord after label
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 1, "Should have 1 NOTE_ON event for chord after label"

    def test_loop_directive_jumps_to_label(self, initialized_service, song_parser):
        """Test that loop directive jumps back to label."""
        service, mock_player = initialized_service

        # Create multi-line song with label and loop
        # loop count 2 means: play 2 times total (original + 1 repeat)
        text = """{label: start} C
G
{loop: start 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)

        # Should play: C, G, (loop back), C, G = 4 chords total
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 4, f"Should have 4 NOTE_ON events (C, G, C, G), got {len(note_on_events)}"


class TestRomanNumeralResolution:
    """Tests for roman numeral chord resolution with key changes."""

    def test_roman_numeral_in_different_keys(self, initialized_service, song_parser):
        """Test that same roman numeral resolves differently in different keys."""
        service, mock_player = initialized_service

        # Create song with I in two different keys
        text = """I
{key: G} I"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        # Should have 2 NOTE_ON events
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should have 2 NOTE_ON events"

        # Different keys should produce different MIDI notes
        # I in C = C major, I in G = G major
        midi1 = note_on_events[0].midi_notes
        midi2 = note_on_events[1].midi_notes

        # The root notes should be different (C vs G = 7 semitones apart)
        assert midi1 != midi2, "I in C and I in G should have different notes"

    def test_progression_with_roman_numerals(self, initialized_service, song_parser):
        """Test common chord progression I-IV-V."""
        service, mock_player = initialized_service

        text = "I IV V"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        # Should have 3 NOTE_ON events for the progression
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 3, "Should have 3 NOTE_ON events for I-IV-V"

        # All three chords should have notes
        for event in note_on_events:
            assert len(event.midi_notes) >= 3, "Each chord should have at least 3 notes"


class TestSequentialPlayback:
    """Tests for sequential playback through multiple lines."""

    def test_multiple_lines_sequential(self, initialized_service, song_parser):
        """Test that playback processes lines in order."""
        service, mock_player = initialized_service

        # Create 3 lines with chords
        text = """C
G
Am"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)

        # Should have 3 NOTE_ON events (one per chord)
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 3, "Should have 3 NOTE_ON events for 3 chords"

        # Verify timestamps are increasing (sequential playback)
        for i in range(1, len(note_on_events)):
            assert note_on_events[i].timestamp > note_on_events[i-1].timestamp, \
                "Events should be in sequential order"

    def test_playback_ends_correctly(self, initialized_service, song_parser):
        """Test that playback ends with END_OF_SONG event."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.3)

        events = collect_events_from_buffer(service)

        # Should have NOTE_ON, NOTE_OFF, and END_OF_SONG
        end_events = [e for e in events if e.event_type == MidiEventType.END_OF_SONG]
        assert len(end_events) == 1, "Should have END_OF_SONG event"

        # END_OF_SONG should be the last event
        assert events[-1].event_type == MidiEventType.END_OF_SONG


class TestPlaybackControls:
    """Tests for playback control methods."""

    def test_pause_playback(self, initialized_service):
        """Test pause playback."""
        service, mock_player = initialized_service

        service.pause_playback()

        mock_player.pause_playback.assert_called_once()

    def test_resume_playback(self, initialized_service):
        """Test resume playback."""
        service, mock_player = initialized_service

        service.resume_playback()

        mock_player.resume_playback.assert_called_once()

    def test_stop_playback(self, initialized_service):
        """Test stop playback."""
        service, mock_player = initialized_service

        service.stop_playback()

        mock_player.stop_playback.assert_called_once()

    def test_set_bpm(self, initialized_service):
        """Test BPM change."""
        service, mock_player = initialized_service

        service.set_bpm(140)

        mock_player.set_bpm.assert_called_once_with(140)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_line_list(self, initialized_service):
        """Test playback with empty line list."""
        service, mock_player = initialized_service

        result = service.start_song_playback([], initial_key="C")

        assert result is False

    def test_line_with_only_directives(self, initialized_service, song_parser):
        """Test line containing only directives, no chords."""
        service, mock_player = initialized_service

        text = """{bpm: 100}
C"""
        lines = song_parser.detect_chords_in_text(text)

        result = service.start_song_playback(lines, initial_key="C")

        assert result is True

        time.sleep(0.2)
        events = collect_events_from_buffer(service)

        # Should process directive and play chord
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 1, "Should have NOTE_ON event for chord"

    def test_mixed_absolute_and_relative_chords(self, initialized_service, song_parser):
        """Test mixing absolute and relative chords in same song."""
        service, mock_player = initialized_service

        text = "C I"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        # Both should resolve successfully
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) == 2, "Should have NOTE_ON events for both chords"

    def test_loop_to_nonexistent_label(self, initialized_service, song_parser):
        """Test that loop to nonexistent label is handled gracefully."""
        service, mock_player = initialized_service

        # Create loop directive without corresponding label
        text = "{loop: nonexistent 1} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        time.sleep(0.2)

        events = collect_events_from_buffer(service)

        # Should not crash - should still play the chord
        note_on_events = [e for e in events if e.event_type == MidiEventType.NOTE_ON]
        assert len(note_on_events) >= 1, "Should play chord despite invalid loop"


class TestPlaybackEventCallback:
    """Tests for playback event callback functionality via Application.queue_ui_callback."""

    def test_event_callback_called_for_each_chord(self, initialized_service, song_parser, mock_application):
        """Test that event callback is queued for each chord played."""
        service, mock_player = initialized_service

        text = "C G Am"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        # Give producer time to generate events and fire callbacks
        time.sleep(0.3)

        # Application.queue_ui_callback should be called for each chord
        # The EventProducer wraps the callback in a lambda
        ui_callback_count = mock_application.queue_ui_callback.call_count

        assert ui_callback_count >= 3, f"Should have at least 3 UI callbacks for 3 chords, got {ui_callback_count}"

    def test_event_args_contains_chord_info(self, initialized_service, song_parser, mock_application):
        """Test that PlaybackEventArgs contains correct chord info."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.2)

        # Execute the queued lambdas to trigger the event_callback
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()  # Execute the lambda

        # Now check that event_callback was called
        assert event_callback.call_count >= 1, "Event callback should have been called"

        # Get the PlaybackEventArgs from the event_callback calls
        event_args = event_callback.call_args_list[0][0][0]

        assert isinstance(event_args, PlaybackEventArgs)
        assert event_args.event_type == PlaybackEventType.CHORD_START
        assert event_args.chord_info is not None
        assert event_args.chord_info.chord == "C"

    def test_event_args_contains_playback_state(self, initialized_service, song_parser, mock_application):
        """Test that PlaybackEventArgs contains current playback state."""
        service, mock_player = initialized_service

        text = "{bpm: 140} {key: G} {time: 3/4} C"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.2)

        # Execute the queued lambdas to trigger the event_callback
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 1, "Event callback should have been called"
        event_args = event_callback.call_args_list[0][0][0]

        # Verify playback state is included
        assert event_args.bpm == 140
        assert event_args.key == "G"
        assert event_args.time_signature_beats == 3
        assert event_args.time_signature_unit == 4

    def test_event_args_bar_number_tracking(self, initialized_service, song_parser, mock_application):
        """Test that bar numbers are tracked correctly."""
        service, mock_player = initialized_service

        # Create song with multiple chords (4 beats each in 4/4 time)
        text = "C G Am F"  # 4 bars
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.3)

        # Execute the queued lambdas to trigger the event_callback
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 4, f"Should have at least 4 event callbacks, got {event_callback.call_count}"

        # Extract bar numbers from the event_callback calls
        bar_numbers = [call[0][0].current_bar for call in event_callback.call_args_list[:4]]

        # Bar numbers should be 1, 2, 3, 4
        assert bar_numbers == [1, 2, 3, 4], f"Expected [1, 2, 3, 4], got {bar_numbers}"

    def test_event_args_bar_number_with_custom_durations(self, initialized_service, song_parser, mock_application):
        """Test bar number calculation with custom chord durations."""
        service, mock_player = initialized_service

        # C for 2 beats, G for 2 beats (same bar), Am for 4 beats (next bar)
        text = "C*2 G*2 Am*4"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.3)

        # Execute the queued lambdas
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 3, f"Should have at least 3 event callbacks, got {event_callback.call_count}"

        bar_numbers = [call[0][0].current_bar for call in event_callback.call_args_list[:3]]

        # C at bar 1 (beats 0-2), G at bar 1 (beats 2-4), Am at bar 2 (beats 4-8)
        assert bar_numbers == [1, 1, 2], f"Expected [1, 1, 2], got {bar_numbers}"

    def test_event_args_total_bars_calculated(self, initialized_service, song_parser, mock_application):
        """Test that total bars is calculated correctly."""
        service, mock_player = initialized_service

        # 3 chords, each 4 beats = 12 beats / 4 = 3 bars
        text = "C G Am"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.2)

        # Execute the queued lambdas
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 1, "Event callback should have been called"
        event_args = event_callback.call_args_list[0][0][0]

        assert event_args.total_bars == 3

    def test_event_args_line_number_tracking(self, initialized_service, song_parser, mock_application):
        """Test that line numbers are tracked correctly."""
        service, mock_player = initialized_service

        text = """C
G
Am"""
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.3)

        # Execute the queued lambdas
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 3, f"Should have at least 3 event callbacks, got {event_callback.call_count}"

        line_numbers = [call[0][0].current_line for call in event_callback.call_args_list[:3]]

        # Line numbers should be 0, 1, 2 (0-indexed)
        assert line_numbers == [0, 1, 2], f"Expected [0, 1, 2], got {line_numbers}"

    def test_event_callback_not_called_without_callback(self, initialized_service, song_parser, mock_application):
        """Test that playback works without event callback."""
        service, mock_player = initialized_service

        text = "C G"
        lines = song_parser.detect_chords_in_text(text)

        # Start playback without event callback
        result = service.start_song_playback(lines, initial_key="C", on_event_callback=None)

        assert result is True
        time.sleep(0.2)

        # Verify playback started (mock player's start_playback should have been called)
        mock_player.start_playback.assert_called()

    def test_event_callback_exception_handling(self, initialized_service, song_parser, mock_application):
        """Test that exceptions in event callback don't crash playback."""
        service, mock_player = initialized_service

        text = "C G"
        lines = song_parser.detect_chords_in_text(text)

        def failing_callback(event_args):
            raise Exception("Callback failed!")

        service.start_song_playback(lines, initial_key="C", on_event_callback=failing_callback)
        time.sleep(0.3)

        # Playback should continue normally despite callback exceptions
        # Verify playback started
        mock_player.start_playback.assert_called()

    def test_event_callback_with_directives(self, initialized_service, song_parser, mock_application):
        """Test that event callback reflects directive changes."""
        service, mock_player = initialized_service

        text = """C
{bpm: 160} G"""
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        time.sleep(0.3)

        # Execute the queued lambdas
        for call in mock_application.queue_ui_callback.call_args_list:
            if len(call[0]) > 0 and callable(call[0][0]):
                queued_lambda = call[0][0]
                queued_lambda()

        assert event_callback.call_count >= 2, f"Should have at least 2 event callbacks, got {event_callback.call_count}"

        # Check BPM in event args
        first_event = event_callback.call_args_list[0][0][0]
        second_event = event_callback.call_args_list[1][0][0]

        assert first_event.bpm == 120
        assert second_event.bpm == 160

    def test_event_callback_preserves_finished_callback(self, initialized_service, song_parser, mock_application):
        """Test that event callback doesn't interfere with finished callback."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        finished_callback = Mock()

        service.start_song_playback(
            lines,
            initial_key="C",
            on_event_callback=event_callback,
            on_finished_callback=finished_callback
        )

        time.sleep(0.2)

        # Both callbacks should be registered
        mock_player.set_playback_finished_callback.assert_called_once_with(finished_callback)

        # Event callback should have been queued
        ui_callback_count = mock_application.queue_ui_callback.call_count
        assert ui_callback_count >= 1, "Event callback should have been queued"

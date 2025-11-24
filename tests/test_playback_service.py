"""Comprehensive unit tests for PlaybackService."""

import pytest
from unittest.mock import Mock, MagicMock, call, patch
from typing import List, Optional, Tuple

from services.playback_service import PlaybackService
from services.config_service import ConfigService
from src.models.line import Line
from src.models.chord import ChordInfo
from src.models.directive import Directive, DirectiveType, BPMModifierType
from src.models.playback_state import PlaybackState
from models.playback_event import PlaybackEventArgs, PlaybackEventType


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
    """Create a mock NotePlayer."""
    player = MagicMock()
    player.is_playing = False
    return player


@pytest.fixture
def playback_service(mock_config, mock_player):
    """Create a PlaybackService instance with mocked dependencies."""
    service = PlaybackService(mock_config, player=mock_player)
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
        mock_player.set_next_note_callback.assert_called_once()
        mock_player.start_playback.assert_called_once()

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

        # Mock the get_next callback
        service.start_song_playback(lines, initial_key="C")

        # Get the callback that was set
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First call should process BPM directive and return first chord
        result = callback()

        # Verify BPM was changed
        mock_player.set_bpm.assert_called_with(140)

        # Verify chord was returned
        assert result is not None
        midi_notes, duration = result
        assert len(midi_notes) > 0

    def test_key_directive_changes_resolution(self, initialized_service, song_parser):
        """Test KEY directive changes roman numeral resolution."""
        service, mock_player = initialized_service

        # Parse line: {key: G} I (should resolve to G, not C)
        text = "{key: G} I"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Get the chord - should be G major (I in G)
        result = callback()

        assert result is not None
        midi_notes, duration = result
        # G major should have notes (voicing may vary, at least 3 notes)
        assert len(midi_notes) >= 3

    def test_time_signature_directive(self, initialized_service, song_parser):
        """Test TIME directive changes default duration."""
        service, mock_player = initialized_service

        text = "{time: 3/4} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        assert result is not None
        midi_notes, duration = result
        # Duration should be 3 beats (full measure in 3/4)
        assert duration == 3.0


class TestEnhancedBPMDirectives:
    """Tests for enhanced BPM directive handling during playback."""

    def test_relative_bpm_increase(self, initialized_service, song_parser):
        """Test relative BPM increase during playback."""
        service, mock_player = initialized_service

        # Parse line with relative BPM directive
        text = "{bpm: +20} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Process directive and chord
        result = callback()

        # Verify BPM increased from 120 to 140
        mock_player.set_bpm.assert_called_with(140)
        assert result is not None

    def test_relative_bpm_decrease(self, initialized_service, song_parser):
        """Test relative BPM decrease during playback."""
        service, mock_player = initialized_service

        text = "{bpm: -30} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        # Verify BPM decreased from 120 to 90
        mock_player.set_bpm.assert_called_with(90)
        assert result is not None

    def test_percentage_bpm_half_speed(self, initialized_service, song_parser):
        """Test percentage BPM (50% = half speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 50%} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        # Verify BPM set to 50% (60)
        mock_player.set_bpm.assert_called_with(60)
        assert result is not None

    def test_percentage_bpm_faster(self, initialized_service, song_parser):
        """Test percentage BPM (150% = 1.5x speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 150%} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        # Verify BPM set to 150% (180)
        mock_player.set_bpm.assert_called_with(180)
        assert result is not None

    def test_multiplier_bpm_half_speed(self, initialized_service, song_parser):
        """Test multiplier BPM (0.5x = half speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 0.5x} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        # Verify BPM multiplied by 0.5 (60)
        mock_player.set_bpm.assert_called_with(60)
        assert result is not None

    def test_multiplier_bpm_double_speed(self, initialized_service, song_parser):
        """Test multiplier BPM (2x = double speed)."""
        service, mock_player = initialized_service

        text = "{bpm: 2x} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        # Verify BPM multiplied by 2 (240)
        mock_player.set_bpm.assert_called_with(240)
        assert result is not None

    def test_reset_bpm_after_changes(self, initialized_service, song_parser):
        """Test reset BPM returns to initial value."""
        service, mock_player = initialized_service

        # Parse multi-line text with BPM change and reset
        text = "{bpm: 180} C\n{bpm: reset} G"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First chord (with BPM 180)
        result1 = callback()
        assert result1 is not None

        # Second chord (with BPM reset to 120)
        result2 = callback()
        assert result2 is not None

        # Verify BPM was set to 180, then reset to 120
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(180) for call in calls)
        assert any(call == call(120) for call in calls)

    def test_chained_bpm_modifiers(self, initialized_service, song_parser):
        """Test multiple BPM modifiers applied in sequence."""
        service, mock_player = initialized_service

        # Start at 120, double to 240, then halve to 120
        text = "{bpm: 2x} C\n{bpm: 50%} G"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First chord (120 * 2 = 240)
        result1 = callback()
        assert result1 is not None

        # Second chord (240 * 50% = 120)
        result2 = callback()
        assert result2 is not None

        # Verify BPM progression
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(240) for call in calls)
        assert any(call == call(120) for call in calls)


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
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First iteration: C at 120, G at 240
        result1 = callback()  # C chord, BPM still 120
        assert result1 is not None

        result2 = callback()  # G chord, BPM changed to 240
        assert result2 is not None
        mock_player.set_bpm.assert_called_with(240)

        # Loop back - should restore BPM to 120
        result3 = callback()  # C chord again, BPM restored to 120
        assert result3 is not None

        # Verify BPM was restored to 120
        calls = mock_player.set_bpm.call_args_list
        # Should have: set to 240, then back to 120
        assert any(call == call(240) for call in calls)
        assert any(call == call(120) for call in calls)
        # The last call before the second C should be restoring to 120
        bpm_calls = [c[0][0] for c in calls if len(c[0]) > 0]
        assert 120 in bpm_calls[1:]  # Should restore to 120 at some point

    def test_key_restored_on_loop_with_relative_chords(self, initialized_service, song_parser):
        """Test that key is restored when looping with relative (roman numeral) chords."""
        service, mock_player = initialized_service

        # Create a song where key changes inside a loop with roman numerals
        text = """{label: chorus} I
{key: G} I
{loop: chorus 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First iteration: I in C, then I in G
        result1 = callback()  # I in C (should be C major)
        assert result1 is not None
        midi1, _ = result1

        result2 = callback()  # I in G (should be G major)
        assert result2 is not None
        midi2, _ = result2

        # Loop back - should restore key to C
        result3 = callback()  # I in C again (should be C major again)
        assert result3 is not None
        midi3, _ = result3

        # Verify the key changed and then was restored
        # The chords should be different when key changes, then restored after loop
        assert midi1 != midi2, "I in C and I in G should produce different notes"
        assert midi1 == midi3, "I chord should be restored to same notes after loop"

    def test_key_directive_doesnt_affect_absolute_chords(self, initialized_service, song_parser):
        """Test that key directives don't affect absolute chords (they shouldn't)."""
        service, mock_player = initialized_service

        # Absolute chords should play the same regardless of key directive
        text = """{label: start} C
{key: G} C
{loop: start 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # All three C chords should be identical
        result1 = callback()  # C chord (first time)
        assert result1 is not None
        midi1, _ = result1

        result2 = callback()  # C chord (after key change)
        assert result2 is not None
        midi2, _ = result2

        # Loop back
        result3 = callback()  # C chord (third time, state restored)
        assert result3 is not None
        midi3, _ = result3

        # All should be the same - C is an absolute chord
        assert midi1 == midi2, "Key directive should not affect absolute chord C"
        assert midi1 == midi3, "C chord should be same after loop restoration"

    def test_time_signature_restored_on_loop(self, initialized_service, song_parser):
        """Test that time signature is restored when looping back to a label."""
        service, mock_player = initialized_service

        # Create a song where time signature changes inside a loop
        text = """{label: section} C
{time: 3/4} G
{loop: section 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First iteration
        result1 = callback()  # C in 4/4 (default duration = 4)
        assert result1 is not None
        _, duration1 = result1
        assert duration1 == 4.0

        result2 = callback()  # G in 3/4 (default duration = 3)
        assert result2 is not None
        _, duration2 = result2
        assert duration2 == 3.0

        # Loop back - should restore time signature to 4/4
        result3 = callback()  # C in 4/4 again
        assert result3 is not None
        _, duration3 = result3
        assert duration3 == 4.0  # Back to 4 beats

    def test_multiple_state_changes_restored(self, initialized_service, song_parser):
        """Test that all state changes (BPM, key, time sig) are restored together."""
        service, mock_player = initialized_service

        # Create a song with multiple state changes in a loop
        text = """{label: bridge} {bpm: 100} C
{bpm: 2x} {key: G} {time: 3/4} G
{loop: bridge 2}"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First iteration
        result1 = callback()  # C at BPM 100, key C, 4/4
        assert result1 is not None

        result2 = callback()  # G at BPM 200, key G, 3/4
        assert result2 is not None

        # Loop back - all state should be restored
        result3 = callback()  # C at BPM 100, key C, 4/4 again
        assert result3 is not None

        # Verify BPM was restored
        calls = mock_player.set_bpm.call_args_list
        assert any(call == call(100) for call in calls)
        assert any(call == call(200) for call in calls)


class TestChordDurations:
    """Tests for chord duration handling."""

    def test_chord_with_explicit_duration(self, initialized_service, song_parser):
        """Test chord with *N duration notation."""
        service, mock_player = initialized_service

        # Parse chord with duration
        text = "C*2"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        assert result is not None
        midi_notes, duration = result
        assert duration == 2.0

    def test_chord_default_duration(self, initialized_service, song_parser):
        """Test chord without duration uses measure length."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        result = callback()

        assert result is not None
        midi_notes, duration = result
        # Default 4/4 time = 4 beats
        assert duration == 4.0


class TestLoopMechanics:
    """Tests for label and loop directive handling."""

    def test_label_directive(self, initialized_service, song_parser):
        """Test that labels are indexed correctly."""
        service, mock_player = initialized_service

        text = "{label: verse} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should process label silently and return chord
        result = callback()

        assert result is not None

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
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should play: C, G, (loop back), C, G, None
        chords_played = []
        for _ in range(6):
            result = callback()
            if result is None:
                break
            chords_played.append(result)

        # Should have played 4 chords (C, G, C, G)
        assert len(chords_played) == 4


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
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Get both chords
        result1 = callback()
        result2 = callback()

        # Both should succeed but have different notes
        assert result1 is not None
        assert result2 is not None

        midi1, _ = result1
        midi2, _ = result2

        # Different keys should produce different MIDI notes
        # (C root vs G root - 7 semitones apart)
        assert midi1 != midi2

    def test_progression_with_roman_numerals(self, initialized_service, song_parser):
        """Test common chord progression I-IV-V."""
        service, mock_player = initialized_service

        text = "I IV V"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        results = []
        for _ in range(3):
            result = callback()
            assert result is not None
            results.append(result)

        # All three chords should be playable
        assert len(results) == 3


class TestSequentialPlayback:
    """Tests for sequential playback through multiple lines."""

    def test_multiple_lines_sequential(self, initialized_service, song_parser):
        """Test that playback processes lines in order."""
        service, mock_player = initialized_service

        # Create 3 lines with chords
        text = """C
C
C"""
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should be able to get 3 chords
        count = 0
        while True:
            result = callback()
            if result is None:
                break
            count += 1

        assert count == 3

    def test_playback_ends_correctly(self, initialized_service, song_parser):
        """Test that playback returns None when done."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # First call returns chord
        result1 = callback()
        assert result1 is not None

        # Second call should return None (end of playback)
        result2 = callback()
        assert result2 is None


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

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should process directive and return chord
        result = callback()
        assert result is not None

    def test_mixed_absolute_and_relative_chords(self, initialized_service, song_parser):
        """Test mixing absolute and relative chords in same song."""
        service, mock_player = initialized_service

        text = "C I"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Both should resolve successfully
        result1 = callback()
        result2 = callback()

        assert result1 is not None
        assert result2 is not None

    def test_loop_to_nonexistent_label(self, initialized_service, song_parser):
        """Test that loop to nonexistent label is handled gracefully."""
        service, mock_player = initialized_service

        # Create loop directive without corresponding label
        text = "{loop: nonexistent 1} C"
        lines = song_parser.detect_chords_in_text(text)

        service.start_song_playback(lines, initial_key="C")
        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should not crash - either skip loop or log warning
        result = callback()
        # Should still play the chord
        assert result is not None


class TestPlaybackEventCallback:
    """Tests for playback event callback functionality."""

    def test_event_callback_called_for_each_chord(self, initialized_service, song_parser):
        """Test that event callback is called for each chord played."""
        service, mock_player = initialized_service

        text = "C G Am"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Play all chords
        callback()  # C
        callback()  # G
        callback()  # Am

        # Event callback should be called 3 times
        assert event_callback.call_count == 3

    def test_event_args_contains_chord_info(self, initialized_service, song_parser):
        """Test that PlaybackEventArgs contains correct chord info."""
        service, mock_player = initialized_service

        text = "C"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]
        callback()  # Play C

        # Get the event args
        assert event_callback.called
        event_args = event_callback.call_args[0][0]

        assert isinstance(event_args, PlaybackEventArgs)
        assert event_args.event_type == PlaybackEventType.CHORD_START
        assert event_args.chord_info is not None
        assert event_args.chord_info.chord == "C"

    def test_event_args_contains_playback_state(self, initialized_service, song_parser):
        """Test that PlaybackEventArgs contains current playback state."""
        service, mock_player = initialized_service

        text = "{bpm: 140} {key: G} {time: 3/4} C"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]
        callback()  # Play C with all directives applied

        event_args = event_callback.call_args[0][0]

        # Verify playback state is included
        assert event_args.bpm == 140
        assert event_args.key == "G"
        assert event_args.time_signature_beats == 3
        assert event_args.time_signature_unit == 4

    def test_event_args_bar_number_tracking(self, initialized_service, song_parser):
        """Test that bar numbers are tracked correctly."""
        service, mock_player = initialized_service

        # Create song with multiple chords (4 beats each in 4/4 time)
        text = "C G Am F"  # 4 bars
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Play all chords and collect bar numbers
        bar_numbers = []
        for _ in range(4):
            callback()
            event_args = event_callback.call_args[0][0]
            bar_numbers.append(event_args.current_bar)

        # Bar numbers should be 1, 2, 3, 4
        assert bar_numbers == [1, 2, 3, 4]

    def test_event_args_bar_number_with_custom_durations(self, initialized_service, song_parser):
        """Test bar number calculation with custom chord durations."""
        service, mock_player = initialized_service

        # C for 2 beats, G for 2 beats (same bar), Am for 4 beats (next bar)
        text = "C*2 G*2 Am*4"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        bar_numbers = []
        for _ in range(3):
            callback()
            event_args = event_callback.call_args[0][0]
            bar_numbers.append(event_args.current_bar)

        # C at bar 1 (beats 0-2), G at bar 1 (beats 2-4), Am at bar 2 (beats 4-8)
        assert bar_numbers == [1, 1, 2]

    def test_event_args_total_bars_calculated(self, initialized_service, song_parser):
        """Test that total bars is calculated correctly."""
        service, mock_player = initialized_service

        # 3 chords, each 4 beats = 12 beats / 4 = 3 bars
        text = "C G Am"
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]
        callback()

        event_args = event_callback.call_args[0][0]
        assert event_args.total_bars == 3

    def test_event_args_line_number_tracking(self, initialized_service, song_parser):
        """Test that line numbers are tracked correctly."""
        service, mock_player = initialized_service

        text = """C
G
Am"""
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        line_numbers = []
        for _ in range(3):
            callback()
            event_args = event_callback.call_args[0][0]
            line_numbers.append(event_args.current_line)

        # Line numbers should be 0, 1, 2 (0-indexed)
        assert line_numbers == [0, 1, 2]

    def test_event_callback_not_called_without_callback(self, initialized_service, song_parser):
        """Test that playback works without event callback."""
        service, mock_player = initialized_service

        text = "C G"
        lines = song_parser.detect_chords_in_text(text)

        # Start playback without event callback
        result = service.start_song_playback(lines, initial_key="C", on_event_callback=None)

        assert result is True

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should not crash when callback is None
        result1 = callback()
        result2 = callback()

        assert result1 is not None
        assert result2 is not None

    def test_event_callback_exception_handling(self, initialized_service, song_parser):
        """Test that exceptions in event callback don't crash playback."""
        service, mock_player = initialized_service

        text = "C G"
        lines = song_parser.detect_chords_in_text(text)

        def failing_callback(event_args):
            raise Exception("Callback failed!")

        service.start_song_playback(lines, initial_key="C", on_event_callback=failing_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Should not crash despite callback exception
        result1 = callback()
        result2 = callback()

        # Playback should continue normally
        assert result1 is not None
        assert result2 is not None

    def test_event_callback_with_directives(self, initialized_service, song_parser):
        """Test that event callback reflects directive changes."""
        service, mock_player = initialized_service

        text = """C
{bpm: 160} G"""
        lines = song_parser.detect_chords_in_text(text)

        event_callback = Mock()
        service.start_song_playback(lines, initial_key="C", on_event_callback=event_callback)

        callback = mock_player.set_next_note_callback.call_args[0][0]

        # Play both chords
        callback()  # C at 120 BPM
        callback()  # G at 160 BPM

        # Check BPM in event args
        first_event = event_callback.call_args_list[0][0][0]
        second_event = event_callback.call_args_list[1][0][0]

        assert first_event.bpm == 120
        assert second_event.bpm == 160

    def test_event_callback_preserves_finished_callback(self, initialized_service, song_parser):
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

        # Both callbacks should be registered
        mock_player.set_playback_finished_callback.assert_called_once_with(finished_callback)

        # Event callback should be usable
        callback = mock_player.set_next_note_callback.call_args[0][0]
        callback()

        assert event_callback.called

"""Audio playback service wrapping NotePlayer."""

import logging
from typing import Optional, List, Callable, Tuple

from audio.player_interface import IPlayer
from audio.player import NotePlayer
from audio.note_picker_interface import INotePicker
from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from models.chord_notes import ChordNotes
from models.chord import ChordInfo
from models.playback_state import PlaybackState
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from models.line import Line
from models.directive import Directive, DirectiveType, BPMModifierType
from services.config_service import ConfigService


class PlaybackService:
    """High-level audio playback orchestration service.

    Provides business-level API for audio playback, abstracting FluidSynth/NotePlayer details.
    """

    def __init__(self, config_service: ConfigService, player: Optional[IPlayer] = None):
        self._config = config_service
        self._player: Optional[IPlayer] = player
        self._note_picker = self._create_note_picker(self._config.get("voicing", "piano"))
        self._logger = logging.getLogger(__name__)
        self._initialized = player is not None
        self._playback_state = PlaybackState()

    def _create_note_picker(self, voicing: str) -> INotePicker:
        """Create appropriate note picker based on voicing string.

        Args:
            voicing: Voicing string like 'piano', 'guitar:standard', 'guitar:drop_d', etc.

        Returns:
            INotePicker instance
        """
        if voicing.startswith("guitar:"):
            # Extract tuning from voicing string
            tuning_name = voicing.split(":", 1)[1]

            # Check if it's a custom tuning
            custom_tunings = self._config.get("custom_tunings", {})
            if tuning_name in custom_tunings:
                tuning = custom_tunings[tuning_name]
            else:
                # Use built-in tuning
                tuning = tuning_name

            return GuitarChordPicker(tuning=tuning)
        else:
            # Default to piano voicing
            return ChordNotePicker()

    def set_voicing(self, voicing: str) -> None:
        """Change the voicing style.

        Args:
            voicing: Voicing string like 'piano', 'guitar:standard', etc.
        """
        self._logger.debug(f"Setting voicing to {voicing}")
        self._note_picker = self._create_note_picker(voicing)
        self._config.set("voicing", voicing)

    def initialize_player(self, soundfont_path: Optional[str] = None) -> bool:
        """Initialize the audio player.

        Args:
            soundfont_path: Optional path to soundfont file (.sf2)

        Returns:
            True if initialized successfully, False otherwise
        """
        if self._initialized:
            self._logger.debug("Audio player already initialized")
            return True

        try:
            # Get config values
            bpm = self._config.get("bpm", 120)
            sf_path = soundfont_path or self._config.get("soundfont_path")
            time_sig_beats = self._config.get("time_signature_beats", 4)
            time_sig_unit = self._config.get("time_signature_unit", 4)

            # Initialize playback state with config values
            self._playback_state = PlaybackState(
                bpm=bpm,
                initial_bpm=bpm,
                time_signature_beats=time_sig_beats,
                time_signature_unit=time_sig_unit
            )

            # Create player
            self._logger.info("Initializing audio player")
            self._player = NotePlayer(
                soundfont_path=sf_path,
                bpm=bpm,
                time_signature=(time_sig_beats, time_sig_unit)
            )
            self._initialized = True
            self._logger.info("Audio player initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize audio player: {e}", exc_info=True)
            self._player = None
            self._initialized = False
            return False

    def play_chord_immediate(self, chord_info: ChordInfo, current_key: Optional[str] = None) -> None:
        """Play a chord immediately (click-to-play) with dynamic note resolution.

        Args:
            chord_info: Chord information
            current_key: Current key signature for resolving roman numerals
        """
        if not self._ensure_initialized():
            return

        try:
            # Resolve chord notes dynamically
            chord_notes = self._resolve_chord_notes(chord_info, current_key)
            if not chord_notes:
                self._logger.warning(f"Could not resolve chord: {chord_info.chord}")
                return

            # Convert to MIDI
            midi_notes = self._notes_to_midi(chord_notes)
            if midi_notes:
                self._logger.debug(f"Playing chord immediately: {chord_info.chord} -> {chord_notes.notes} (bass: {chord_notes.bass_note})")
                self._player.play_notes_immediate(midi_notes)
            else:
                self._logger.warning(f"Could not convert chord to MIDI notes: {chord_info.chord}")

        except Exception as e:
            self._logger.error(f"Error playing chord: {e}", exc_info=True)

    def play_notes_immediate(self, midi_notes: List[int]) -> None:
        """Play MIDI notes immediately.

        Args:
            midi_notes: List of MIDI note numbers to play
        """
        if not self._ensure_initialized():
            return

        try:
            if midi_notes:
                self._logger.debug(f"Playing MIDI notes immediately: {midi_notes}")
                self._player.play_notes_immediate(midi_notes)
            else:
                self._logger.warning("No MIDI notes provided to play")

        except Exception as e:
            self._logger.error(f"Error playing notes: {e}", exc_info=True)

    def pause_playback(self) -> None:
        """Pause ongoing playback."""
        if self._player:
            self._logger.debug("Pausing playback")
            self._player.pause_playback()

    def resume_playback(self) -> None:
        """Resume paused playback."""
        if self._player:
            self._logger.debug("Resuming playback")
            self._player.resume_playback()

    def stop_playback(self) -> None:
        """Stop ongoing playback."""
        if self._player:
            self._logger.debug("Stopping playback")
            self._player.stop_playback()

    def set_bpm(self, bpm: int) -> None:
        """Change playback speed.

        Args:
            bpm: Beats per minute (60-240)
        """
        if self._player:
            self._logger.debug(f"Setting BPM to {bpm}")
            self._player.set_bpm(bpm)
            self._config.set("bpm", bpm)

        # Update playback state
        self._playback_state.set_bpm(bpm)

    def set_instrument(self, program: int) -> None:
        """Change MIDI instrument.

        Args:
            program: MIDI program number (0-127)
                     0 = Acoustic Grand Piano
                     24-31 = Guitars
                     40-47 = Strings
                     56-63 = Brass
        """
        if self._player:
            self._logger.debug(f"Setting instrument to program {program}")
            self._player.set_instrument(program)

    def cleanup(self) -> None:
        """Cleanup audio resources."""
        if self._player:
            self._logger.info("Cleaning up audio player")
            self._player.cleanup()
            self._player = None
            self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Ensure player is initialized, initialize if needed.

        Returns:
            True if initialized, False if initialization failed
        """
        if not self._initialized:
            return self.initialize_player()
        return True

    @property
    def is_initialized(self) -> bool:
        """Check if audio player is initialized."""
        return self._initialized

    @property
    def is_playing(self) -> bool:
        """Check if playback is active."""
        return self._player.is_playing if self._player else False

    @property
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._player.is_paused if self._player else False

    def reset_playback_state(self) -> None:
        """Reset playback state for new playback session.

        Resets line position, chord index, and loop stack while preserving
        BPM, time signature, and key settings. Also resets chord picker state
        for consistent voice leading.
        """
        self._logger.debug("Resetting playback state")
        bpm = self._playback_state.bpm
        initial_bpm = self._playback_state.initial_bpm
        time_sig_beats = self._playback_state.time_signature_beats
        time_sig_unit = self._playback_state.time_signature_unit
        key = self._playback_state.key

        self._playback_state = PlaybackState(
            bpm=bpm,
            initial_bpm=initial_bpm,
            time_signature_beats=time_sig_beats,
            time_signature_unit=time_sig_unit,
            key=key
        )

        # Reset chord picker state for consistent voice leading
        self._note_picker.reset()

    def set_time_signature_from_state(self, beats: int, unit: int) -> None:
        """Update time signature in both playback state and player.

        Args:
            beats: Number of beats per measure
            unit: Beat unit (4 = quarter note, etc.)
        """
        self._logger.debug(f"Setting time signature to {beats}/{unit}")
        self._playback_state.set_time_signature(beats, unit)

        # Update player if initialized
        if self._player:
            # NotePlayer doesn't have a set_time_signature method yet
            # This would need to be implemented in NotePlayer if needed
            pass

    def set_key(self, key: str) -> None:
        """Update the current key signature in playback state.

        Args:
            key: Key signature (e.g., 'C', 'Am', 'G')
        """
        self._logger.debug(f"Setting key to {key}")
        self._playback_state.set_key(key)

    def get_playback_state(self) -> PlaybackState:
        """Get the current playback state.

        Returns:
            The current PlaybackState object
        """
        return self._playback_state

    def get_time_signature(self) -> Tuple[int, int]:
        """Get the current time signature from playback state.

        Returns:
            Tuple of (beats_per_measure, beat_unit), e.g., (4, 4) for 4/4 time
        """
        return (self._playback_state.time_signature_beats,
                self._playback_state.time_signature_unit)

    def start_song_playback(
        self,
        lines: List[Line],
        initial_key: Optional[str],
        on_finished_callback: Optional[Callable[[], None]] = None,
        on_event_callback: Optional[Callable[[PlaybackEventArgs], None]] = None
    ) -> bool:
        """Start playback of a song with lines containing chords and directives.

        Args:
            lines: List of Line objects with chords and directives
            initial_key: Initial key signature (from UI)
            on_finished_callback: Optional callback when playback finishes
            on_event_callback: Optional callback for playback events (chord start/end)

        Returns:
            True if playback started, False otherwise
        """
        if not self._ensure_initialized():
            return False

        # Reset chord picker state for consistent voice leading at start of playback
        self._note_picker.reset()

        # Count total chords
        total_chords = sum(len(line.chords) for line in lines)
        if total_chords == 0:
            self._logger.info("No chords found for playback")
            return False

        self._logger.info(f"Starting song playback with {total_chords} chords")

        # Calculate total bars (sum of all chord durations divided by time signature)
        time_sig_beats, time_sig_unit = self.get_time_signature()
        total_beats = 0.0
        for line in lines:
            for item in line.items:
                if isinstance(item, ChordInfo) and item.is_valid:
                    duration = float(item.duration) if item.duration is not None else float(time_sig_beats)
                    total_beats += duration
        total_bars = max(1, int(total_beats / time_sig_beats))

        # Initialize playback state
        playback_state = {
            'lines': lines,
            'line_index': 0,
            'item_index': 0,
            'current_key': initial_key,
            'current_time_sig': self.get_time_signature(),
            'loop_stack': [],
            'labels': {},
            'label_states': {},  # Store playback state at each label
            'on_event_callback': on_event_callback,
            'current_bar': 1,
            'total_bars': total_bars,
            'current_beat_position': 0.0
        }

        # Build label index
        self._build_label_index(playback_state)

        # Create playback callback
        def get_next_chord():
            return self._get_next_playback_item(playback_state)

        # Start playback
        self._player.set_next_note_callback(get_next_chord)
        if on_finished_callback:
            self._player.set_playback_finished_callback(on_finished_callback)
        self._player.start_playback()

        return True

    def _build_label_index(self, playback_state: dict) -> None:
        """Build an index of labels for loop jumps.

        Args:
            playback_state: Playback state dictionary
        """
        for line_idx, line in enumerate(playback_state['lines']):
            for item_idx, item in enumerate(line.items):
                if isinstance(item, Directive) and item.type == DirectiveType.LABEL:
                    playback_state['labels'][item.label] = (line_idx, item_idx)
                    self._logger.debug(f"Found label '{item.label}' at line {line_idx}, item {item_idx}")

    def _get_next_playback_item(self, state: dict) -> Optional[Tuple[List[int], float]]:
        """Get next playback item (processes directives, returns chord MIDI notes).

        Args:
            state: Playback state dictionary

        Returns:
            Tuple of (midi_notes, duration_in_beats) or None when done
        """
        while True:
            # Check if we've reached the end
            if state['line_index'] >= len(state['lines']):
                return None

            line = state['lines'][state['line_index']]

            # Check if we've processed all items in this line
            if state['item_index'] >= len(line.items):
                state['line_index'] += 1
                state['item_index'] = 0
                continue

            item = line.items[state['item_index']]
            state['item_index'] += 1

            # Process directives
            if isinstance(item, Directive):
                self._handle_directive(item, state)
                continue

            # Process chords
            elif isinstance(item, ChordInfo):
                result = self._play_chord_item(item, state)
                if result:
                    return result
                # If result is None, chord couldn't be played, continue to next
                continue

        return None

    def _handle_directive(self, directive: Directive, state: dict) -> None:
        """Handle a directive during playback.

        Args:
            directive: Directive object
            state: Playback state dictionary
        """
        # Skip invalid directives (they are kept for editor highlighting only)
        if not directive.is_valid:
            self._logger.debug(f"Skipping invalid directive at position {directive.start}")
            return

        if directive.type == DirectiveType.BPM:
            self._handle_bpm_directive(directive)
        elif directive.type == DirectiveType.KEY:
            self._handle_key_directive(directive, state)
        elif directive.type == DirectiveType.TIME_SIGNATURE:
            self._handle_time_signature_directive(directive, state)
        elif directive.type == DirectiveType.LOOP:
            self._handle_loop_directive(directive, state)
        elif directive.type == DirectiveType.LABEL:
            self._handle_label_directive(directive, state)

    def _handle_bpm_directive(self, directive: Directive) -> None:
        """Handle BPM directive with support for multiple modifier types.

        Args:
            directive: Directive with BPM value
        """
        current_bpm = self._playback_state.bpm
        new_bpm = current_bpm

        if directive.bpm_modifier_type == BPMModifierType.ABSOLUTE:
            # Absolute value: {bpm: 120}
            new_bpm = directive.bpm
            self._logger.debug(f"Directive: Setting BPM to {new_bpm}")

        elif directive.bpm_modifier_type == BPMModifierType.RELATIVE:
            # Relative adjustment: {bpm: +20} or {bpm: -20}
            new_bpm = int(current_bpm + directive.bpm_modifier_value)
            self._logger.debug(f"Directive: Adjusting BPM by {directive.bpm_modifier_value:+.0f} "
                             f"({current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.PERCENTAGE:
            # Percentage: {bpm: 50%}
            new_bpm = int(current_bpm * directive.bpm_modifier_value / 100)
            self._logger.debug(f"Directive: Setting BPM to {directive.bpm_modifier_value}% "
                             f"({current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.MULTIPLIER:
            # Multiplier: {bpm: 2x} or {bpm: 0.5x}
            new_bpm = int(current_bpm * directive.bpm_modifier_value)
            self._logger.debug(f"Directive: Multiplying BPM by {directive.bpm_modifier_value}x "
                             f"({current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.RESET:
            # Reset to initial: {bpm: reset} or {bpm: original}
            new_bpm = self._playback_state.initial_bpm
            self._logger.debug(f"Directive: Resetting BPM to initial value "
                             f"({current_bpm} -> {new_bpm})")

        # Apply the new BPM value
        self.set_bpm(new_bpm)

    def _handle_key_directive(self, directive: Directive, state: dict) -> None:
        """Handle key change directive.

        Args:
            directive: Directive with key value
            state: Playback state dictionary
        """
        self._logger.debug(f"Directive: Setting key to {directive.key}")
        state['current_key'] = directive.key

    def _handle_time_signature_directive(self, directive: Directive, state: dict) -> None:
        """Handle time signature directive.

        Args:
            directive: Directive with time signature
            state: Playback state dictionary
        """
        self._logger.debug(f"Directive: Setting time signature to {directive.beats}/{directive.unit}")
        state['current_time_sig'] = (directive.beats, directive.unit)

    def _handle_loop_directive(self, directive: Directive, state: dict) -> None:
        """Handle loop directive (restore state and jump to label).

        Args:
            directive: Directive with loop information
            state: Playback state dictionary
        """
        if directive.label in state['labels']:
            label_pos = state['labels'][directive.label]

            # Check if we're already in a loop for this label
            already_looping = any(loop['label'] == directive.label for loop in state['loop_stack'])

            if not already_looping:
                # First time hitting loop directive - initialize loop
                self._logger.debug(f"Directive: Loop to label '{directive.label}' {directive.loop_count} times")

                # Restore the saved state from the label before jumping back
                if directive.label in state['label_states']:
                    saved_state = state['label_states'][directive.label]
                    self._logger.debug(f"Restoring state at loop: BPM={saved_state['bpm']}, "
                                     f"time_sig={saved_state['time_sig']}, key={saved_state['key']}")
                    self.set_bpm(saved_state['bpm'])
                    state['current_time_sig'] = saved_state['time_sig']
                    state['current_key'] = saved_state['key']

                    # Restore chord picker state for consistent voice leading
                    from audio.chord_picker import ChordPickerState
                    self._note_picker.state = ChordPickerState.from_dict(saved_state['chord_picker_state'])

                state['loop_stack'].append({
                    'label': directive.label,
                    'count': directive.loop_count,
                    'remaining': directive.loop_count - 1,
                    'target': label_pos
                })
                # Jump to label
                state['line_index'], state['item_index'] = label_pos
            # else: We're already looping, so we'll hit the label which handles continuation
        else:
            self._logger.warning(f"Label '{directive.label}' not found for loop")

    def _handle_label_directive(self, directive: Directive, state: dict) -> None:
        """Handle label directive (save state on first encounter, check loop completion).

        Args:
            directive: Directive with label
            state: Playback state dictionary
        """
        # First time encountering this label - save the current playback state
        if directive.label not in state['label_states']:
            saved_state = {
                'bpm': self._playback_state.bpm,
                'time_sig': state['current_time_sig'],
                'key': state['current_key'],
                'chord_picker_state': self._note_picker.state.to_dict()
            }
            state['label_states'][directive.label] = saved_state
            self._logger.debug(f"Saved state at label '{directive.label}': BPM={saved_state['bpm']}, "
                             f"time_sig={saved_state['time_sig']}, key={saved_state['key']}")

        # Check if we're in a loop and need to continue or finish
        if state['loop_stack']:
            current_loop = state['loop_stack'][-1]
            # Check if this is the label we're looping on
            if current_loop['label'] == directive.label:
                if current_loop['remaining'] > 0:
                    self._logger.debug(f"Continuing loop '{directive.label}' ({current_loop['remaining']} more times)")
                    current_loop['remaining'] -= 1
                    # Continue playing from after the label
                else:
                    # Loop finished
                    self._logger.debug(f"Loop '{directive.label}' finished")
                    state['loop_stack'].pop()

    def _play_chord_item(self, chord: ChordInfo, state: dict) -> Optional[Tuple[List[int], float]]:
        """Resolve and prepare a chord for playback.

        Args:
            chord: ChordInfo object
            state: Playback state dictionary

        Returns:
            Tuple of (midi_notes, duration) or None if chord can't be played
        """
        if not chord.is_valid:
            self._logger.warning(f"Skipping invalid chord: {chord.chord}")
            return None

        # Resolve chord to notes
        chord_notes = self._resolve_chord_notes(chord, state['current_key'])
        if not chord_notes:
            self._logger.warning(f"Could not resolve chord: {chord.chord}")
            return None

        # Convert to MIDI
        midi_notes = self._notes_to_midi(chord_notes)
        if not midi_notes:
            self._logger.warning(f"Could not convert chord to MIDI: {chord.chord}")
            return None

        # Determine duration
        if chord.duration is not None:
            duration = float(chord.duration)
        else:
            # Default to full measure
            duration = float(state['current_time_sig'][0])

        # Calculate current bar number based on beat position
        time_sig_beats = state['current_time_sig'][0]
        current_bar = int(state['current_beat_position'] / time_sig_beats) + 1

        # Fire playback event callback if provided
        if state.get('on_event_callback'):
            try:
                event_args = PlaybackEventArgs(
                    event_type=PlaybackEventType.CHORD_START,
                    chord_info=chord,
                    bpm=self._playback_state.bpm,
                    time_signature_beats=state['current_time_sig'][0],
                    time_signature_unit=state['current_time_sig'][1],
                    key=state['current_key'],
                    current_line=state['line_index'],
                    current_bar=current_bar,
                    total_bars=state['total_bars']
                )
                state['on_event_callback'](event_args)
            except Exception as e:
                self._logger.error(f"Error in playback event callback: {e}", exc_info=True)

        # Update beat position for next chord
        state['current_beat_position'] += duration

        self._logger.debug(f"Playing chord: {chord.chord} -> {chord_notes.notes} (bass: {chord_notes.bass_note}, duration={duration})")
        return (midi_notes, duration)

    def _resolve_chord_notes(self, chord: ChordInfo, current_key: Optional[str]) -> Optional[ChordNotes]:
        """Resolve a chord to its note names based on current key.

        Args:
            chord: ChordInfo object
            current_key: Current key signature (for roman numerals only)

        Returns:
            ChordNotes object with notes, bass_note, and root, or None if resolution fails
        """
        from chord.helper import ChordHelper

        helper = ChordHelper()
        # Only pass key for relative (roman numeral) chords
        # Absolute chords should ignore the key parameter
        key_to_use = current_key if chord.is_relative else None
        chord_notes_result = helper.compute_chord_notes(
            chord.chord,
            key=key_to_use,
            is_relative=chord.is_relative
        )

        return chord_notes_result

    def _notes_to_midi(self, chord_notes: ChordNotes) -> Optional[List[int]]:
        """Convert ChordNotes to MIDI note numbers.

        Args:
            chord_notes: ChordNotes object with notes, bass_note, and root

        Returns:
            List of MIDI note numbers or None
        """
        # Use the injected note picker
        return self._note_picker.chord_to_midi(chord_notes)

"""Event producer for pre-computing MIDI events in a separate thread."""
import logging
import threading
from typing import List, Optional, Callable, Tuple
from queue import Queue

from models.line import Line
from models.chord import ChordInfo
from models.chord_notes import ChordNotes
from models.directive import Directive, DirectiveType, BPMModifierType
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from models.playback_event_internal import MidiEvent, MidiEventType
from audio.event_buffer import EventBuffer
from audio.note_picker_interface import INotePicker
from audio.chord_picker import ChordPickerState


class EventProducer:
    """Produces MIDI events in advance by pre-computing chords.

    This class runs in a separate thread and generates MIDI events with absolute
    timestamps, pushing them to a buffer for consumption by the playback thread.
    This decouples expensive chord computation from timing-critical playback.
    """

    def __init__(
        self,
        lines: List[Line],
        initial_key: Optional[str],
        initial_bpm: int,
        initial_time_sig: Tuple[int, int],
        note_picker: INotePicker,
        event_buffer: EventBuffer,
        application,  # Application instance for UI callbacks
        player=None,  # Player instance for set_bpm/set_time_signature calls
        on_event_callback: Optional[Callable[[PlaybackEventArgs], None]] = None,
        logger: Optional[logging.Logger] = None,
        start_line_index: int = 0,
        start_item_index: int = 0
    ):
        """Initialize the event producer.

        Args:
            lines: List of Line objects with chords and directives
            initial_key: Initial key signature
            initial_bpm: Initial BPM
            initial_time_sig: Initial time signature (beats, unit)
            note_picker: Note picker for converting chords to MIDI
            event_buffer: Buffer to push events to
            application: Application instance for UI thread callbacks
            player: Player instance for calling set_bpm/set_time_signature
            on_event_callback: Optional callback for playback events (chord highlighting)
            logger: Optional logger instance
            start_line_index: Line index to start playback from (default: 0)
            start_item_index: Item index within the line to start from (default: 0)
        """
        self._lines = lines
        self._initial_key = initial_key
        self._initial_bpm = initial_bpm
        self._initial_time_sig = initial_time_sig
        self._note_picker = note_picker
        self._event_buffer = event_buffer
        self._application = application
        self._player = player
        self._on_event_callback = on_event_callback
        self._logger = logger or logging.getLogger(__name__)
        self._start_line_index = start_line_index
        self._start_item_index = start_item_index

        self._thread = None
        self._stop_event = threading.Event()
        self._current_bpm = initial_bpm
        self._current_time_position = 0.0  # Absolute time in seconds

    def start(self) -> None:
        """Start the event producer thread."""
        if self._thread and self._thread.is_alive():
            self._logger.warning("Event producer already running")
            return

        self._stop_event.clear()
        self._current_bpm = self._initial_bpm
        self._current_time_position = 0.0
        self._thread = threading.Thread(target=self._produce_events, daemon=True, name="EventProducer")
        self._thread.start()
        self._logger.info("Event producer started")

    def stop(self) -> None:
        """Stop the event producer thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._logger.info("Event producer stopped")

    def is_running(self) -> bool:
        """Check if the producer thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def _produce_events(self) -> None:
        """Main event production loop (runs in separate thread)."""
        try:
            # Calculate total bars for UI progress
            total_beats = 0.0
            for line in self._lines:
                for item in line.items:
                    if isinstance(item, ChordInfo) and item.is_valid:
                        duration = float(item.duration) if item.duration is not None else float(self._initial_time_sig[0])
                        total_beats += duration
            total_bars = max(1, int(total_beats / self._initial_time_sig[0]))

            # Initialize state
            state = {
                'lines': self._lines,
                'line_index': 0,
                'item_index': 0,
                'current_key': self._initial_key,
                'current_time_sig': self._initial_time_sig,
                'loop_stack': [],
                'labels': {},
                'label_states': {},
                'current_bar': 1,
                'total_bars': total_bars,
                'current_beat_position': 0.0,
                'start_line_index': self._start_line_index,
                'start_item_index': self._start_item_index,
                'in_playback_range': self._start_line_index == 0 and self._start_item_index == 0
            }

            # Build label index
            self._build_label_index(state)

            # Generate events
            while not self._stop_event.is_set():
                event = self._get_next_event(state)
                if event is None:
                    # End of song - push END_OF_SONG event
                    end_event = MidiEvent(
                        timestamp=self._current_time_position,
                        event_type=MidiEventType.END_OF_SONG
                    )
                    try:
                        self._event_buffer.push_event(end_event)
                        self._logger.info("Reached end of song, sent END_OF_SONG event")
                    except ValueError:
                        self._logger.debug("Buffer closed while sending END_OF_SONG")
                    break

                # Push event to buffer (blocks if buffer is full - this is intentional)
                # No timeout - producer should wait for consumer to make space
                try:
                    self._event_buffer.push_event(event)
                except ValueError:
                    # Buffer was closed - stop producing
                    self._logger.debug("Buffer closed, stopping event production")
                    break

        except Exception as e:
            self._logger.error(f"Error in event producer: {e}", exc_info=True)
        finally:
            self._logger.info("Event producer finished")

    def _build_label_index(self, state: dict) -> None:
        """Build an index of labels for loop jumps."""
        for line_idx, line in enumerate(state['lines']):
            for item_idx, item in enumerate(line.items):
                if isinstance(item, Directive) and item.type == DirectiveType.LABEL:
                    state['labels'][item.label] = (line_idx, item_idx)
                    self._logger.debug(f"Found label '{item.label}' at line {line_idx}, item {item_idx}")

    def _get_next_event(self, state: dict) -> Optional[MidiEvent]:
        """Get next MIDI event (processes directives, returns chord event).

        Args:
            state: Production state dictionary

        Returns:
            MidiEvent or None when done
        """
        # Check if there's a pending NOTE_OFF event to send first
        if 'pending_note_off' in state and state['pending_note_off']:
            event = state['pending_note_off']
            state['pending_note_off'] = None
            return event

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
            current_line_idx = state['line_index']
            current_item_idx = state['item_index']
            state['item_index'] += 1

            # Check if we've reached the start position
            if not state['in_playback_range']:
                if (current_line_idx > state['start_line_index'] or
                    (current_line_idx == state['start_line_index'] and
                     current_item_idx >= state['start_item_index'])):
                    state['in_playback_range'] = True
                    self._logger.debug(f"Entered playback range at line {current_line_idx}, item {current_item_idx}")

            # Process directives (always process, regardless of playback range)
            if isinstance(item, Directive):
                self._handle_directive(item, state)
                continue

            # Process chords
            elif isinstance(item, ChordInfo):
                if state['in_playback_range']:
                    # In playback range - create and return events
                    events = self._create_chord_events(item, state)
                    if events:
                        first_event, second_event = events
                        # REST events have no NOTE_OFF (second_event is None)
                        if second_event is not None:
                            state['pending_note_off'] = second_event
                        return first_event
                    # If event is None, chord couldn't be played, continue to next
                else:
                    # Not in playback range yet - update counters but don't play
                    self._update_position_for_chord(item, state)
                continue

        return None

    def _handle_directive(self, directive: Directive, state: dict) -> None:
        """Handle a directive during event production."""
        # Skip invalid directives
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
        """Handle BPM directive with support for multiple modifier types."""
        new_bpm = self._current_bpm

        if directive.bpm_modifier_type == BPMModifierType.ABSOLUTE:
            new_bpm = directive.bpm
            self._logger.debug(f"Directive: Setting BPM to {new_bpm}")

        elif directive.bpm_modifier_type == BPMModifierType.RELATIVE:
            new_bpm = int(self._current_bpm + directive.bpm_modifier_value)
            self._logger.debug(f"Directive: Adjusting BPM by {directive.bpm_modifier_value:+.0f} "
                             f"({self._current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.PERCENTAGE:
            new_bpm = int(self._current_bpm * directive.bpm_modifier_value / 100)
            self._logger.debug(f"Directive: Setting BPM to {directive.bpm_modifier_value}% "
                             f"({self._current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.MULTIPLIER:
            new_bpm = int(self._current_bpm * directive.bpm_modifier_value)
            self._logger.debug(f"Directive: Multiplying BPM by {directive.bpm_modifier_value}x "
                             f"({self._current_bpm} -> {new_bpm})")

        elif directive.bpm_modifier_type == BPMModifierType.RESET:
            new_bpm = self._initial_bpm
            self._logger.debug(f"Directive: Resetting BPM to initial value "
                             f"({self._current_bpm} -> {new_bpm})")

        self._current_bpm = new_bpm

        # Update player's BPM
        if self._player:
            self._player.set_bpm(new_bpm)

    def _handle_key_directive(self, directive: Directive, state: dict) -> None:
        """Handle key change directive."""
        self._logger.debug(f"Directive: Setting key to {directive.key}")
        state['current_key'] = directive.key

    def _handle_time_signature_directive(self, directive: Directive, state: dict) -> None:
        """Handle time signature directive."""
        self._logger.debug(f"Directive: Setting time signature to {directive.beats}/{directive.unit}")
        state['current_time_sig'] = (directive.beats, directive.unit)

        # Update player's time signature
        if self._player:
            self._player.set_time_signature(directive.beats, directive.unit)

    def _handle_loop_directive(self, directive: Directive, state: dict) -> None:
        """Handle loop directive (restore state and jump to label)."""
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
                    self._current_bpm = saved_state['bpm']
                    state['current_time_sig'] = saved_state['time_sig']
                    state['current_key'] = saved_state['key']

                    # Update player with restored state
                    if self._player:
                        self._player.set_bpm(saved_state['bpm'])
                        self._player.set_time_signature(saved_state['time_sig'][0], saved_state['time_sig'][1])

                    # Restore chord picker state for consistent voice leading
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
        """Handle label directive (save state on first encounter, check loop completion)."""
        # First time encountering this label - save the current production state
        if directive.label not in state['label_states']:
            saved_state = {
                'bpm': self._current_bpm,
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

    def _update_position_for_chord(self, chord: ChordInfo, state: dict) -> None:
        """Update beat position counter for a chord without playing it.

        This is used when skipping chords before the playback start position,
        so the bar counter stays accurate. We only update beat position, not time
        position, so playback starts immediately when we reach the start position.

        Args:
            chord: ChordInfo object
            state: Production state dictionary
        """
        if not chord.is_valid:
            return

        # Determine duration in beats
        if chord.duration is not None:
            duration_beats = float(chord.duration)
        else:
            # Default to full measure
            duration_beats = float(state['current_time_sig'][0])

        # Update ONLY beat position for bar counting
        # Do NOT update _current_time_position so playback starts immediately
        state['current_beat_position'] += duration_beats

    def _create_chord_events(self, chord: ChordInfo, state: dict) -> Optional[Tuple[MidiEvent, MidiEvent]]:
        """Create MIDI events (NOTE_ON and NOTE_OFF, or REST) for a chord.

        Args:
            chord: ChordInfo object
            state: Production state dictionary

        Returns:
            Tuple of (NOTE_ON event, NOTE_OFF event) or (REST event, None) for NC,
            or None if chord can't be played
        """
        if not chord.is_valid:
            self._logger.warning(f"Skipping invalid chord: {chord.chord}")
            return None

        # Determine duration in beats
        if chord.duration is not None:
            duration_beats = float(chord.duration)
        else:
            # Default to full measure
            duration_beats = float(state['current_time_sig'][0])

        # Calculate duration in seconds
        beats_per_second = self._current_bpm / 60.0
        duration_seconds = duration_beats / beats_per_second

        # Calculate current bar number based on beat position
        time_sig_beats = state['current_time_sig'][0]
        current_bar = int(state['current_beat_position'] / time_sig_beats) + 1

        # Handle NC (No Chord / rest) - create REST event
        if chord.is_rest:
            rest_event = MidiEvent(
                timestamp=self._current_time_position,
                event_type=MidiEventType.REST,
                midi_notes=[],
                velocity=0,
                metadata={
                    'chord_info': chord,
                    'duration_seconds': duration_seconds,
                    'line_index': state['line_index'],
                    'bar': current_bar,
                    # Callback data
                    'bpm': self._current_bpm,
                    'time_signature_beats': state['current_time_sig'][0],
                    'time_signature_unit': state['current_time_sig'][1],
                    'key': state['current_key'],
                    'total_bars': state['total_bars'],
                    'has_callback': self._on_event_callback is not None
                }
            )

            # Update time position and beat position
            self._current_time_position += duration_seconds
            state['current_beat_position'] += duration_beats

            self._logger.debug(f"Created REST event for NC at t={rest_event.timestamp:.3f}s "
                             f"(duration={duration_seconds:.3f}s)")
            return (rest_event, None)

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

        # Create NOTE_ON event at current time
        # Store callback data in metadata - Player will fire the callback when event is played
        note_on_event = MidiEvent(
            timestamp=self._current_time_position,
            event_type=MidiEventType.NOTE_ON,
            midi_notes=midi_notes,
            velocity=100,
            metadata={
                'chord_info': chord,
                'chord_notes': chord_notes,
                'duration_seconds': duration_seconds,
                'line_index': state['line_index'],
                'bar': current_bar,
                # Callback data
                'bpm': self._current_bpm,
                'time_signature_beats': state['current_time_sig'][0],
                'time_signature_unit': state['current_time_sig'][1],
                'key': state['current_key'],
                'total_bars': state['total_bars'],
                'has_callback': self._on_event_callback is not None
            }
        )

        # Create NOTE_OFF event at end of duration
        note_off_event = MidiEvent(
            timestamp=self._current_time_position + duration_seconds,
            event_type=MidiEventType.NOTE_OFF,
            midi_notes=midi_notes,
            velocity=0,
            metadata={
                'chord_info': chord,
                'line_index': state['line_index'] - 1,
                'bar': current_bar
            }
        )

        # Update time position and beat position
        self._current_time_position += duration_seconds
        state['current_beat_position'] += duration_beats

        self._logger.debug(f"Created events for {chord.chord}: NOTE_ON at t={note_on_event.timestamp:.3f}s, "
                         f"NOTE_OFF at t={note_off_event.timestamp:.3f}s (duration={duration_seconds:.3f}s)")
        return (note_on_event, note_off_event)

    def _resolve_chord_notes(self, chord: ChordInfo, current_key: Optional[str]) -> Optional[ChordNotes]:
        """Resolve a chord to its note names based on current key."""
        from chord.helper import ChordHelper

        helper = ChordHelper()
        # Only pass key for relative (roman numeral) chords
        key_to_use = current_key if chord.is_relative else None
        chord_notes_result = helper.compute_chord_notes(
            chord.chord,
            key=key_to_use,
            is_relative=chord.is_relative
        )

        return chord_notes_result

    def _notes_to_midi(self, chord_notes: ChordNotes) -> Optional[List[int]]:
        """Convert ChordNotes to MIDI note numbers using note picker."""
        try:
            midi_notes = self._note_picker.chord_to_midi(chord_notes)
            return midi_notes
        except Exception as e:
            self._logger.error(f"Error converting notes to MIDI: {e}", exc_info=True)
            return None

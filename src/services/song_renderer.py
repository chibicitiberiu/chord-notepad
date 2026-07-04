"""Synchronous, whole-song renderer for the pre-computed playback pipeline.

``SongRenderer.render`` walks a parsed song (chords + directives) exactly once
and produces a :class:`models.rendered_song.RenderedSong`: every chord resolved
and voiced, with absolute beat/time positions, bar numbers, and tempo/meter
change points. It is a one-to-one port of the traversal that the old streaming
``EventProducer`` performed inline, minus the threading and event emission --
turning MIDI events into a stream is now the compiler's job
(:func:`services.event_compiler.compile_events`).

Voicing happens inline during the walk via ``note_picker.chord_to_midi``, and
loop-backs snapshot/restore the note picker's state so each pass voices
identically -- preserving the exact behaviour of the streaming producer.
Resetting the picker before rendering is the caller's responsibility, as it was
before.
"""
import logging
import threading
from typing import List, Optional, Tuple

from models.line import Line
from models.chord import ChordInfo
from models.chord_notes import ChordNotes
from models.directive import Directive, DirectiveType, BPMModifierType
from models.rendered_song import RenderedSong, RenderedChord
from audio.note_picker_interface import INotePicker


class SongRenderer:
    """Renders a parsed song into a fully pre-computed :class:`RenderedSong`."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(__name__)

    def render(
        self,
        lines: List[Line],
        initial_key: Optional[str],
        initial_bpm: int,
        initial_time_sig: Tuple[int, int],
        note_picker: INotePicker,
        start_line_index: int = 0,
        start_item_index: int = 0,
        cancel_event: Optional[threading.Event] = None,
    ) -> Optional[RenderedSong]:
        """Render the whole song synchronously.

        Args:
            lines: Parsed lines with chords and directives.
            initial_key: Initial key signature.
            initial_bpm: Initial BPM.
            initial_time_sig: Initial time signature (beats, unit).
            note_picker: Voicer; the caller must ``reset()`` it beforehand.
            start_line_index: Line index to begin playback from.
            start_item_index: Item index within that line to begin from.
            cancel_event: If set during the walk, rendering aborts and returns
                ``None`` (used to cancel a render that is stopped mid-flight).

        Returns:
            A :class:`RenderedSong`, or ``None`` if cancelled.
        """
        self._note_picker = note_picker
        self._initial_key = initial_key
        self._initial_bpm = initial_bpm
        self._initial_time_sig = initial_time_sig

        state = {
            'lines': lines,
            'line_index': 0,
            'item_index': 0,
            'current_key': initial_key,
            'current_time_sig': initial_time_sig,
            'current_bpm': initial_bpm,
            'loop_stack': [],
            'labels': {},
            'label_states': {},
            'current_bar': 1,
            'beats_in_bar': 0.0,
            'current_beat_position': 0.0,
            'current_time_position': 0.0,
            # Whole-song bar accounting (ignores start position) so total_bars
            # matches what the old separate _compute_total_bars walk produced.
            'total_bar_count': 0,
            'total_beats_in_bar': 0.0,
            'start_line_index': start_line_index,
            'start_item_index': start_item_index,
            'in_playback_range': start_line_index == 0 and start_item_index == 0,
        }

        self._build_label_index(state)

        rendered: List[RenderedChord] = []
        tempo_map: List[Tuple[float, int]] = [(0.0, initial_bpm)]
        meter_map: List[Tuple[float, Tuple[int, int]]] = [(0.0, initial_time_sig)]
        state['tempo_map'] = tempo_map
        state['meter_map'] = meter_map

        while True:
            if cancel_event is not None and cancel_event.is_set():
                self._logger.debug("Render cancelled")
                return None

            # End of song
            if state['line_index'] >= len(state['lines']):
                break

            line = state['lines'][state['line_index']]
            if state['item_index'] >= len(line.items):
                state['line_index'] += 1
                state['item_index'] = 0
                continue

            item = line.items[state['item_index']]
            current_line_idx = state['line_index']
            current_item_idx = state['item_index']
            state['item_index'] += 1

            # Enter the playback range once we reach the start position.
            if not state['in_playback_range']:
                if (current_line_idx > state['start_line_index'] or
                        (current_line_idx == state['start_line_index'] and
                         current_item_idx >= state['start_item_index'])):
                    state['in_playback_range'] = True

            if isinstance(item, Directive):
                self._handle_directive(item, state)
                continue

            if isinstance(item, ChordInfo):
                if not item.is_valid:
                    self._logger.warning(f"Skipping invalid chord: {item.chord}")
                    continue
                if state['in_playback_range']:
                    rc = self._render_chord(item, state, current_line_idx, current_item_idx)
                    if rc is not None:
                        rendered.append(rc)
                else:
                    rc = self._render_skipped_chord(item, state, current_line_idx, current_item_idx)
                    if rc is not None:
                        rendered.append(rc)
                continue

        # Finalize whole-song bar count (round up any partial bar), matching the
        # old _compute_total_bars behaviour.
        total_bar_count = state['total_bar_count']
        if state['total_beats_in_bar'] > 0:
            total_bar_count += 1
        total_bars = max(1, total_bar_count)

        return RenderedSong(
            chords=rendered,
            total_bars=total_bars,
            total_beats=state['current_beat_position'],
            total_seconds=state['current_time_position'],
            tempo_map=tempo_map,
            meter_map=meter_map,
        )

    # ------------------------------------------------------------------
    # Label indexing
    # ------------------------------------------------------------------
    def _build_label_index(self, state: dict) -> None:
        """Index labels for loop jumps and snapshot the built-in '@start'."""
        for line_idx, line in enumerate(state['lines']):
            for item_idx, item in enumerate(line.items):
                if isinstance(item, Directive) and item.type == DirectiveType.LABEL:
                    state['labels'][item.label] = (line_idx, item_idx)

        # '@start' is a built-in label for the top of the document; snapshot the
        # initial state so a loop back to it restores the starting BPM/time/key
        # and voicing.
        state['labels'].setdefault('@start', (0, 0))
        state['label_states'].setdefault('@start', {
            'bpm': state['current_bpm'],
            'time_sig': state['current_time_sig'],
            'key': state['current_key'],
            'chord_picker_state': self._note_picker.state,
        })

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------
    def _handle_directive(self, directive: Directive, state: dict) -> None:
        if not directive.is_valid:
            return
        if directive.type == DirectiveType.BPM:
            self._handle_bpm_directive(directive, state)
        elif directive.type == DirectiveType.KEY:
            state['current_key'] = directive.key
        elif directive.type == DirectiveType.TIME_SIGNATURE:
            self._handle_time_signature_directive(directive, state)
        elif directive.type == DirectiveType.LOOP:
            self._handle_loop_directive(directive, state)
        elif directive.type == DirectiveType.LABEL:
            self._handle_label_directive(directive, state)

    def _handle_bpm_directive(self, directive: Directive, state: dict) -> None:
        current = state['current_bpm']
        new_bpm = current
        if directive.bpm_modifier_type == BPMModifierType.ABSOLUTE:
            new_bpm = directive.bpm
        elif directive.bpm_modifier_type == BPMModifierType.RELATIVE:
            new_bpm = int(current + directive.bpm_modifier_value)
        elif directive.bpm_modifier_type == BPMModifierType.PERCENTAGE:
            new_bpm = int(current * directive.bpm_modifier_value / 100)
        elif directive.bpm_modifier_type == BPMModifierType.MULTIPLIER:
            new_bpm = int(current * directive.bpm_modifier_value)
        elif directive.bpm_modifier_type == BPMModifierType.RESET:
            new_bpm = self._initial_bpm
        state['current_bpm'] = new_bpm
        self._record_tempo(state, new_bpm)

    def _handle_time_signature_directive(self, directive: Directive, state: dict) -> None:
        # Flush the playback bar accumulator so beats don't lump across meters.
        if state.get('beats_in_bar', 0.0) > 0:
            state['current_bar'] = state.get('current_bar', 1) + 1
            state['beats_in_bar'] = 0.0
        # Flush the whole-song bar accumulator identically.
        if state.get('total_beats_in_bar', 0.0) > 0:
            state['total_bar_count'] += 1
            state['total_beats_in_bar'] = 0.0
        state['current_time_sig'] = (directive.beats, directive.unit)
        self._record_meter(state, state['current_time_sig'])

    def _handle_loop_directive(self, directive: Directive, state: dict) -> None:
        if directive.label not in state['labels']:
            self._logger.warning(f"Label '{directive.label}' not found for loop")
            return
        label_pos = state['labels'][directive.label]
        if directive.loop_count <= 1:
            return
        completed_key = f"loop_done_{directive.start}"
        if completed_key in state:
            return
        loop_stack = state['loop_stack']
        already_looping = bool(loop_stack) and loop_stack[-1].get('directive_pos') == directive.start
        if not already_looping:
            loop_stack.append({
                'label': directive.label,
                'count': directive.loop_count,
                'remaining': directive.loop_count - 1,
                'directive_pos': directive.start,
            })
        else:
            loop_stack[-1]['remaining'] -= 1
        if loop_stack[-1]['remaining'] > 0:
            self._restore_loop_state(directive.label, state)
            state['line_index'], state['item_index'] = label_pos
        else:
            state[completed_key] = True
            loop_stack.pop()

    def _restore_loop_state(self, label: str, state: dict) -> None:
        if label not in state['label_states']:
            return
        saved = state['label_states'][label]
        state['current_bpm'] = saved['bpm']
        state['current_time_sig'] = saved['time_sig']
        state['current_key'] = saved['key']
        self._note_picker.state = saved['chord_picker_state']
        self._record_tempo(state, saved['bpm'])
        self._record_meter(state, saved['time_sig'])

    def _handle_label_directive(self, directive: Directive, state: dict) -> None:
        if directive.label not in state['label_states']:
            state['label_states'][directive.label] = {
                'bpm': state['current_bpm'],
                'time_sig': state['current_time_sig'],
                'key': state['current_key'],
                'chord_picker_state': self._note_picker.state,
            }

    # ------------------------------------------------------------------
    # Tempo / meter change points (future-proofing for MIDI export)
    # ------------------------------------------------------------------
    def _record_tempo(self, state: dict, bpm: int) -> None:
        beat = state['current_beat_position']
        tempo_map = state['tempo_map']
        if tempo_map and abs(tempo_map[-1][0] - beat) < 1e-9:
            if tempo_map[-1][1] != bpm:
                tempo_map[-1] = (beat, bpm)
        elif not tempo_map or tempo_map[-1][1] != bpm:
            tempo_map.append((beat, bpm))

    def _record_meter(self, state: dict, time_sig: Tuple[int, int]) -> None:
        beat = state['current_beat_position']
        meter_map = state['meter_map']
        if meter_map and abs(meter_map[-1][0] - beat) < 1e-9:
            if meter_map[-1][1] != time_sig:
                meter_map[-1] = (beat, time_sig)
        elif not meter_map or meter_map[-1][1] != time_sig:
            meter_map.append((beat, time_sig))

    # ------------------------------------------------------------------
    # Chord rendering
    # ------------------------------------------------------------------
    def _duration_beats(self, chord: ChordInfo, state: dict) -> float:
        if chord.duration is not None:
            return float(chord.duration)
        return float(state['current_time_sig'][0])

    def _advance_bar_counter(self, state: dict, duration_beats: float, time_sig_beats: int) -> None:
        """Advance the playback bar counter, rolling over on each completed bar."""
        beats_in_bar = state.get('beats_in_bar', 0.0) + duration_beats
        bar = state.get('current_bar', 1)
        while beats_in_bar >= time_sig_beats:
            bar += 1
            beats_in_bar -= time_sig_beats
        state['current_bar'] = bar
        state['beats_in_bar'] = beats_in_bar

    def _advance_total_bar_counter(self, state: dict, duration_beats: float, time_sig_beats: int) -> None:
        """Advance the whole-song bar counter (counts every valid chord,
        including those skipped before the start position)."""
        beats_in_bar = state['total_beats_in_bar'] + duration_beats
        count = state['total_bar_count']
        while beats_in_bar >= time_sig_beats:
            count += 1
            beats_in_bar -= time_sig_beats
        state['total_bar_count'] = count
        state['total_beats_in_bar'] = beats_in_bar

    def _render_skipped_chord(
        self, chord: ChordInfo, state: dict, line_idx: int, item_idx: int
    ) -> Optional[RenderedChord]:
        """Account for a chord before the start position without voicing it.

        Only the absolute beat position and the whole-song bar count advance --
        NOT the time position (so playback starts immediately at the start
        position) and NOT the rebased playback bar counter.
        """
        duration_beats = self._duration_beats(chord, state)
        start_beat = state['current_beat_position']
        time_sig = state['current_time_sig']
        rc = RenderedChord(
            chord_info=chord,
            chord_notes=None,
            midi_notes=None,
            line_index=line_idx,
            item_index=item_idx,
            start_beat=start_beat,
            duration_beats=duration_beats,
            start_time=state['current_time_position'],
            duration_seconds=0.0,
            bpm=state['current_bpm'],
            time_sig=time_sig,
            key=state['current_key'],
            bar=state['current_bar'],
            is_rest=chord.is_rest,
            skipped=True,
        )
        state['current_beat_position'] += duration_beats
        self._advance_total_bar_counter(state, duration_beats, time_sig[0])
        return rc

    def _render_chord(
        self, chord: ChordInfo, state: dict, line_idx: int, item_idx: int
    ) -> Optional[RenderedChord]:
        duration_beats = self._duration_beats(chord, state)
        bpm = state['current_bpm']
        beats_per_second = bpm / 60.0
        duration_seconds = duration_beats / beats_per_second
        time_sig = state['current_time_sig']
        start_beat = state['current_beat_position']
        start_time = state['current_time_position']
        current_bar = state['current_bar']

        if chord.is_rest:
            rc = RenderedChord(
                chord_info=chord,
                chord_notes=None,
                midi_notes=None,
                line_index=line_idx,
                item_index=item_idx,
                start_beat=start_beat,
                duration_beats=duration_beats,
                start_time=start_time,
                duration_seconds=duration_seconds,
                bpm=bpm,
                time_sig=time_sig,
                key=state['current_key'],
                bar=current_bar,
                is_rest=True,
                skipped=False,
            )
            state['current_time_position'] += duration_seconds
            state['current_beat_position'] += duration_beats
            self._advance_bar_counter(state, duration_beats, time_sig[0])
            self._advance_total_bar_counter(state, duration_beats, time_sig[0])
            return rc

        chord_notes = self._resolve_chord_notes(chord, state['current_key'])
        if not chord_notes:
            self._logger.warning(f"Could not resolve chord: {chord.chord}")
            return None
        midi_notes = self._notes_to_midi(chord_notes)
        if not midi_notes:
            self._logger.warning(f"Could not convert chord to MIDI: {chord.chord}")
            return None

        rc = RenderedChord(
            chord_info=chord,
            chord_notes=chord_notes,
            midi_notes=midi_notes,
            line_index=line_idx,
            item_index=item_idx,
            start_beat=start_beat,
            duration_beats=duration_beats,
            start_time=start_time,
            duration_seconds=duration_seconds,
            bpm=bpm,
            time_sig=time_sig,
            key=state['current_key'],
            bar=current_bar,
            is_rest=False,
            skipped=False,
        )
        state['current_time_position'] += duration_seconds
        state['current_beat_position'] += duration_beats
        self._advance_bar_counter(state, duration_beats, time_sig[0])
        self._advance_total_bar_counter(state, duration_beats, time_sig[0])
        return rc

    def _resolve_chord_notes(self, chord: ChordInfo, current_key: Optional[str]) -> Optional[ChordNotes]:
        from chord.helper import ChordHelper

        helper = ChordHelper()
        key_to_use = current_key if chord.is_relative else None
        return helper.compute_chord_notes(
            chord.chord,
            key=key_to_use,
            is_relative=chord.is_relative,
        )

    def _notes_to_midi(self, chord_notes: ChordNotes) -> Optional[List[int]]:
        try:
            return self._note_picker.chord_to_midi(chord_notes)
        except Exception as e:
            self._logger.error(f"Error converting notes to MIDI: {e}", exc_info=True)
            return None

"""Synchronous, whole-song renderer for the pre-computed playback pipeline.

``SongRenderer.render`` walks a parsed song (chords + directives) exactly once
and produces a :class:`models.rendered_song.RenderedSong`: every chord resolved
and voiced, with absolute beat/time positions, bar numbers, and tempo/meter
change points. It is a one-to-one port of the traversal that the old streaming
``EventProducer`` performed inline, minus the threading and event emission --
turning MIDI events into a stream is now the compiler's job
(:func:`services.event_compiler.compile_events`).

Rendering runs in two phases. A *structure pass* walks the song once, resolving
every chord's notes and computing all timing/bar/tempo/meter information, but
leaves each chord's ``midi_notes`` unset. A *voicing pass* then hands the played
chords (in playback order, loop repeats included) to
``note_picker.voice_sequence`` in a single call, so the voicer can optimize the
whole song in context, and assigns the results back. Determinism is owned by
``voice_sequence`` (which resets the picker itself), so the renderer no longer
resets the picker or snapshots its state across loops.
"""
import logging
import threading
from typing import Callable, List, Optional, Tuple

from models.line import Line
from models.chord import ChordInfo
from models.chord_notes import ChordNotes
from models.directive import Directive, DirectiveType, BPMModifierType
from models.rendered_song import RenderedSong, RenderedChord, SongMarker
from audio.note_picker_interface import INotePicker
from exceptions import RenderAborted


def _dedupe_preserve_order(notes: List[int]) -> List[int]:
    """Return ``notes`` with duplicates removed, keeping first-seen order.

    Used to derive a fixed-ensemble picker's ``midi_notes`` (one synth
    trigger per distinct pitch) from its full per-voice voicing (one entry
    per voice, duplicates allowed for unisons).
    """
    seen = set()
    result = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            result.append(note)
    return result


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
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> Optional[RenderedSong]:
        """Render the whole song synchronously.

        Args:
            lines: Parsed lines with chords and directives.
            initial_key: Initial key signature.
            initial_bpm: Initial BPM.
            initial_time_sig: Initial time signature (beats, unit).
            note_picker: Voicer; ``voice_sequence`` resets it internally, so no
                prior ``reset()`` is required for deterministic voicing.
            start_line_index: Line index to begin playback from.
            start_item_index: Item index within that line to begin from.
            cancel_event: If set during the walk, rendering aborts and returns
                ``None`` (used to cancel a render that is stopped mid-flight).
            should_abort: Optional cooperative-abort predicate threaded into the
                whole-song voicing pass. When it fires the voicer raises
                :class:`~exceptions.RenderAborted`, which propagates out of
                ``render``. ``None`` (default) never aborts -- the playback and
                export call sites pass nothing, so behaviour is unchanged.

        Returns:
            A :class:`RenderedSong`, or ``None`` if cancelled.
        """
        self._note_picker = note_picker
        self._should_abort = should_abort
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
            # Timeline markers for the chord-sheet strip (see SongMarker) and the
            # beat of the most recent 'loop' marker, used to suppress the
            # redundant 'section' marker emitted when a loop re-walks its target
            # label at the same beat.
            'markers': [],
            'last_loop_beat': None,
        }

        self._build_label_index(state)

        rendered: List[RenderedChord] = []
        tempo_map: List[Tuple[float, int]] = [(0.0, initial_bpm)]
        meter_map: List[Tuple[float, Tuple[int, int]]] = [(0.0, initial_time_sig)]
        # key_map stays internal to the walk (it only drives 'key' markers);
        # unlike tempo_map/meter_map it is not stored on the RenderedSong.
        key_map: List[Tuple[float, Optional[str]]] = [(0.0, initial_key)]
        state['tempo_map'] = tempo_map
        state['meter_map'] = meter_map
        state['key_map'] = key_map

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

        # Voicing pass: hand every played (non-rest, non-skipped) chord's
        # resolved notes to the voicer in one call so it can optimize the whole
        # song in context, then assign the results back. Rests and skipped
        # chords keep midi_notes=None.
        voice_labels, voice_staves = self._voice_rendered_chords(rendered)

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
            markers=state['markers'],
            voice_labels=voice_labels,
            voice_staves=voice_staves,
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
        # initial state so a loop back to it restores the starting BPM/time/key.
        # Voicing is no longer snapshotted here -- the whole-song voicing pass
        # handles loop repeats in context.
        state['labels'].setdefault('@start', (0, 0))
        state['label_states'].setdefault('@start', {
            'bpm': state['current_bpm'],
            'time_sig': state['current_time_sig'],
            'key': state['current_key'],
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
            self._record_key(state, directive.key)
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
            # A real jump: emit a 'loop' marker at the jump beat/time. 'p' is the
            # pass about to play (2..count); with 'remaining' passes still to go
            # after this one, p = count - remaining + 1. Emitted before the
            # state restore so the loop flag sorts ahead of any tempo/meter
            # markers the restore records at the same beat. Recording the beat
            # lets the re-walked target label suppress its redundant 'section'
            # marker (the loop flag supersedes it on repeat passes).
            count = loop_stack[-1]['count']
            remaining = loop_stack[-1]['remaining']
            pass_num = count - remaining + 1
            self._emit_marker(
                state, 'loop', f'{directive.label} ({pass_num}/{count})')
            state['last_loop_beat'] = state['current_beat_position']
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
        self._record_tempo(state, saved['bpm'])
        self._record_meter(state, saved['time_sig'])
        self._record_key(state, saved['key'])

    def _handle_label_directive(self, directive: Directive, state: dict) -> None:
        if directive.label not in state['label_states']:
            state['label_states'][directive.label] = {
                'bpm': state['current_bpm'],
                'time_sig': state['current_time_sig'],
                'key': state['current_key'],
            }
        # Emit a 'section' marker for user labels. The built-in '@start' label is
        # synthetic (never an item in the walk), but guard it anyway. Suppress
        # the marker when a 'loop' marker was just emitted at this same beat:
        # that happens when a loop jump re-walks its target label, and the loop
        # flag supersedes the section flag on repeat passes. First encounters
        # (no preceding loop marker at this beat) always emit.
        if directive.label == '@start':
            return
        last_loop_beat = state.get('last_loop_beat')
        if (last_loop_beat is not None and
                abs(last_loop_beat - state['current_beat_position']) < 1e-9):
            return
        self._emit_marker(state, 'section', directive.label)

    # ------------------------------------------------------------------
    # Tempo / meter / key change points (tempo/meter future-proof MIDI export;
    # the key map only feeds 'key' markers and stays internal to the walk)
    # ------------------------------------------------------------------
    def _record_tempo(self, state: dict, bpm: int) -> None:
        beat = state['current_beat_position']
        tempo_map = state['tempo_map']
        changed = False
        if tempo_map and abs(tempo_map[-1][0] - beat) < 1e-9:
            if tempo_map[-1][1] != bpm:
                tempo_map[-1] = (beat, bpm)
                changed = True
        elif not tempo_map or tempo_map[-1][1] != bpm:
            tempo_map.append((beat, bpm))
            changed = True
        # Marker on every effective-bpm change past beat 0, mirroring each write
        # to tempo_map (append or same-beat overwrite). Loop-state restoration
        # goes through here too, so a loop that restores the label's saved tempo
        # emits a 'tempo' marker at the jump beat; if a {bpm} directive at the
        # top of the loop body then re-sets the tempo at that same beat, both the
        # restored value and the re-set value produce a marker there -- an honest
        # picture of what the tempo does across the loop seam. The initial bpm at
        # beat 0 is seeded directly into tempo_map, never via this method, so it
        # correctly produces no marker.
        if changed and beat > 1e-9:
            self._emit_marker(state, 'tempo', f'{bpm} bpm')

    def _record_meter(self, state: dict, time_sig: Tuple[int, int]) -> None:
        beat = state['current_beat_position']
        meter_map = state['meter_map']
        changed = False
        if meter_map and abs(meter_map[-1][0] - beat) < 1e-9:
            if meter_map[-1][1] != time_sig:
                meter_map[-1] = (beat, time_sig)
                changed = True
        elif not meter_map or meter_map[-1][1] != time_sig:
            meter_map.append((beat, time_sig))
            changed = True
        if changed and beat > 1e-9:
            self._emit_marker(state, 'meter', f'{time_sig[0]}/{time_sig[1]}')

    def _record_key(self, state: dict, key: Optional[str]) -> None:
        beat = state['current_beat_position']
        key_map = state['key_map']
        changed = False
        if key_map and abs(key_map[-1][0] - beat) < 1e-9:
            if key_map[-1][1] != key:
                key_map[-1] = (beat, key)
                changed = True
        elif not key_map or key_map[-1][1] != key:
            key_map.append((beat, key))
            changed = True
        # Marker on every effective-key change past beat 0, mirroring each write
        # to key_map exactly like _record_tempo mirrors tempo_map: a repeated
        # {key} with the same effective key writes nothing and so emits nothing,
        # and loop-state restoration comes through here too, so a loop that
        # restores the label's saved key emits a 'key' marker at the jump beat.
        # The initial key at beat 0 is seeded directly into key_map, never via
        # this method, so it correctly produces no marker. A key of None (song
        # started without one and a loop restored that) has no honest label, so
        # the map records it but no marker is emitted.
        if changed and beat > 1e-9 and key is not None:
            self._emit_marker(state, 'key', f'Key {key}')

    # ------------------------------------------------------------------
    # Timeline markers (chord-sheet strip)
    # ------------------------------------------------------------------
    def _emit_marker(self, state: dict, kind: str, text: str) -> None:
        """Append a :class:`SongMarker` at the current beat/time position.

        Called from the single render walk, so markers land in walk order with
        non-decreasing ``beat``. ``time`` is the current time position, which is
        ``0.0`` throughout the skipped play-from-cursor prefix (matching the
        skipped chords there).
        """
        state['markers'].append(SongMarker(
            beat=state['current_beat_position'],
            time=state['current_time_position'],
            kind=kind,
            text=text,
        ))

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
        # Voicing is deferred to the whole-song voicing pass; leave midi_notes
        # unset here so the voicer sees the chords in playback order at once.

        rc = RenderedChord(
            chord_info=chord,
            chord_notes=chord_notes,
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
            is_rest=False,
            skipped=False,
        )
        state['current_time_position'] += duration_seconds
        state['current_beat_position'] += duration_beats
        self._advance_bar_counter(state, duration_beats, time_sig[0])
        self._advance_total_bar_counter(state, duration_beats, time_sig[0])
        return rc

    def _resolve_chord_notes(self, chord: ChordInfo, current_key: Optional[str]) -> Optional[ChordNotes]:
        """Resolve a chord to its ``ChordNotes``, stamped with the current key.

        ``current_key`` is always passed through, not just for roman-numeral
        chords: absolute chords still resolve against the song's key for
        their own notes, but ``ChordNotes.key`` records the key in effect so
        key-aware voicing rules (e.g. leading-tone handling) can see it
        regardless of how the chord was spelled. This mirrors
        ``RenderedChord.key``, which is likewise unconditional.
        """
        from chord.helper import ChordHelper

        helper = ChordHelper()
        return helper.compute_chord_notes(
            chord.chord,
            key=current_key,
            is_relative=chord.is_relative,
        )

    def _voice_rendered_chords(
        self, rendered: List[RenderedChord]
    ) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        """Voice every played chord in one whole-song pass.

        Collects the played (non-rest, non-skipped) chords in playback order,
        voices them together via ``note_picker.voice_sequence``, and writes each
        result back onto its :class:`RenderedChord`. Rests and skipped chords are
        left with ``midi_notes=None``.

        For fixed-ensemble pickers -- ``note_picker.voice_labels`` is not
        ``None`` (checked via ``getattr`` so picker fakes without the
        property still work) -- each chord's full voicing (duplicates
        allowed, one note per voice) is written to ``voice_notes`` and
        ``midi_notes`` becomes an order-preserving deduplicated copy of it,
        so a unison doesn't double-strike one synth note. The picker reports
        ``voice_labels`` top-voice-first; this returns them reversed to
        low-to-high so they align index-for-index with ``voice_notes``. The
        matching per-voice ``voice_staves`` (also reported top-voice-first) are
        reversed to low-to-high the same way and returned alongside.

        For free-voiced pickers (piano, guitar; ``voice_labels`` is
        ``None``), behaviour is exactly as before: ``midi_notes`` is the
        voicing unchanged, ``voice_notes`` stays ``None``, and this returns
        ``(None, None)``. Their model-specific display detail -- the guitar
        ``fingering`` and the piano ``hand_split`` -- rides along on each
        :class:`VoicedChord` from ``voice_sequence_details`` and is copied
        onto the ``RenderedChord``; models that don't supply it leave those
        fields ``None``.

        Returns:
            A ``(voice_labels, voice_staves)`` pair, each a low-to-high list to
            store on the ``RenderedSong``, or ``(None, None)`` for free-voiced
            pickers.
        """
        played = [rc for rc in rendered
                  if not rc.is_rest and not rc.skipped and rc.chord_notes is not None]
        if not played:
            return None, None
        try:
            voicings = self._note_picker.voice_sequence_details(
                [rc.chord_notes for rc in played],
                should_abort=getattr(self, '_should_abort', None))
        except RenderAborted:
            # Cooperative abort: a newer render generation superseded this one.
            # Propagate so the caller can drop the abandoned work; this is
            # control flow, not a voicing error, so it must not be swallowed by
            # the broad except below.
            raise
        except Exception as e:
            self._logger.error(f"Error voicing chords: {e}", exc_info=True)
            return None, None

        voice_labels = getattr(self._note_picker, 'voice_labels', None)
        if voice_labels is None:
            for rc, voiced in zip(played, voicings):
                rc.midi_notes = voiced.midi_notes
                rc.fingering = voiced.fingering
                rc.hand_split = voiced.hand_split
            return None, None

        for rc, voiced in zip(played, voicings):
            rc.voice_notes = list(voiced.midi_notes)
            rc.midi_notes = _dedupe_preserve_order(voiced.midi_notes)
        voice_staves = getattr(self._note_picker, 'voice_staves', None)
        staves = list(reversed(voice_staves)) if voice_staves is not None else None
        return list(reversed(voice_labels)), staves

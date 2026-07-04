"""Compile a :class:`RenderedSong` into the flat ``MidiEvent`` stream.

This is a one-to-one port of the streaming producer's ``_create_chord_events``
and ``_build_metronome_ticks``: it turns each pre-rendered chord into its
ordered burst of METRONOME_TICK / NOTE_ON / NOTE_OFF (or REST) events, then
appends a final END_OF_SONG. The player consumes the resulting list exactly as
it consumed the old streamed events.
"""
from typing import List

from models.rendered_song import RenderedSong, RenderedChord
from models.playback_event_internal import MidiEvent, MidiEventType


def _build_metronome_ticks(
    chord_start_time: float,
    chord_start_beat: float,
    duration_beats: float,
    seconds_per_beat: float,
    beats_per_measure: int,
) -> List[MidiEvent]:
    """Emit a click event at each beat boundary covered by a chord.

    Ticks are always emitted; the player decides at consumption time whether
    they actually sound. A chord that doesn't start on a beat boundary gets no
    ticks.
    """
    if duration_beats <= 0:
        return []
    if abs(chord_start_beat - round(chord_start_beat)) > 1e-6:
        return []
    bpm_int = max(1, beats_per_measure)
    start_beat_index = int(round(chord_start_beat))
    ticks: List[MidiEvent] = []
    beats_to_cover = int(duration_beats)  # ignore fractional remainder
    for i in range(beats_to_cover):
        is_downbeat = ((start_beat_index + i) % bpm_int) == 0
        ticks.append(
            MidiEvent(
                timestamp=chord_start_time + i * seconds_per_beat,
                event_type=MidiEventType.METRONOME_TICK,
                midi_notes=[],
                velocity=0,
                metadata={'is_downbeat': is_downbeat},
            )
        )
    return ticks


def _sorted_burst(events: List[MidiEvent]) -> List[MidiEvent]:
    """Order a chord's events by timestamp, ticks before notes at a tie."""
    return sorted(
        events,
        key=lambda e: (e.timestamp, 0 if e.event_type == MidiEventType.METRONOME_TICK else 1),
    )


def _compile_rest(rc: RenderedChord, total_bars: int, has_callback: bool) -> List[MidiEvent]:
    rest_event = MidiEvent(
        timestamp=rc.start_time,
        event_type=MidiEventType.REST,
        midi_notes=[],
        velocity=0,
        metadata={
            'chord_info': rc.chord_info,
            'duration_seconds': rc.duration_seconds,
            'line_index': rc.line_index,
            'bar': rc.bar,
            'bpm': rc.bpm,
            'time_signature_beats': rc.time_sig[0],
            'time_signature_unit': rc.time_sig[1],
            'key': rc.key,
            'total_bars': total_bars,
            'has_callback': has_callback,
        },
    )
    ticks = _build_metronome_ticks(
        chord_start_time=rc.start_time,
        chord_start_beat=rc.start_beat,
        duration_beats=rc.duration_beats,
        seconds_per_beat=60.0 / rc.bpm,
        beats_per_measure=rc.time_sig[0],
    )
    return _sorted_burst(ticks + [rest_event])


def _compile_chord(rc: RenderedChord, total_bars: int, has_callback: bool) -> List[MidiEvent]:
    note_on_event = MidiEvent(
        timestamp=rc.start_time,
        event_type=MidiEventType.NOTE_ON,
        midi_notes=rc.midi_notes,
        velocity=100,
        metadata={
            'chord_info': rc.chord_info,
            'chord_notes': rc.chord_notes,
            'duration_seconds': rc.duration_seconds,
            'line_index': rc.line_index,
            'bar': rc.bar,
            'bpm': rc.bpm,
            'time_signature_beats': rc.time_sig[0],
            'time_signature_unit': rc.time_sig[1],
            'key': rc.key,
            'total_bars': total_bars,
            'has_callback': has_callback,
        },
    )
    note_off_event = MidiEvent(
        timestamp=rc.start_time + rc.duration_seconds,
        event_type=MidiEventType.NOTE_OFF,
        midi_notes=rc.midi_notes,
        velocity=0,
        metadata={
            'chord_info': rc.chord_info,
            # Preserve the streaming producer's line_index - 1 quirk exactly.
            'line_index': rc.line_index - 1,
            'bar': rc.bar,
        },
    )
    ticks = _build_metronome_ticks(
        chord_start_time=rc.start_time,
        chord_start_beat=rc.start_beat,
        duration_beats=rc.duration_beats,
        seconds_per_beat=60.0 / rc.bpm,
        beats_per_measure=rc.time_sig[0],
    )
    return _sorted_burst(ticks + [note_on_event, note_off_event])


def compile_events(rendered: RenderedSong, has_callback: bool) -> List[MidiEvent]:
    """Flatten a :class:`RenderedSong` into its ordered ``MidiEvent`` stream.

    Args:
        rendered: The pre-rendered song.
        has_callback: Whether a playback event callback is registered (stored in
            NOTE_ON/REST metadata so the player knows to fire it).

    Returns:
        The full event list, terminated by an END_OF_SONG event.
    """
    events: List[MidiEvent] = []
    total_bars = rendered.total_bars
    for rc in rendered.chords:
        if rc.skipped:
            continue
        if rc.is_rest:
            events.extend(_compile_rest(rc, total_bars, has_callback))
        else:
            events.extend(_compile_chord(rc, total_bars, has_callback))

    events.append(
        MidiEvent(
            timestamp=rendered.total_seconds,
            event_type=MidiEventType.END_OF_SONG,
        )
    )
    return events

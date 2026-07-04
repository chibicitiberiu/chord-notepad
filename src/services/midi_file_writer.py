"""Write a :class:`RenderedSong` to a Standard MIDI File (SMF).

This is the export counterpart to :func:`services.event_compiler.compile_events`:
where the compiler turns a pre-rendered song into the seconds-domain event stream
the player consumes, this module turns the same ``RenderedSong`` into a
tick-domain, format-1 SMF that any DAW or notation program can open.

Track 0 is always a conductor track carrying tempo, meter and key-signature
metadata derived from the song's ``tempo_map``/``meter_map`` and per-chord
``key``. For a free-voiced render (piano, guitar) track 1 carries every voiced
chord as note_on/note_off pairs on channel 0, named 'Chords'. For a
fixed-ensemble render (``rendered.voice_labels`` set, e.g. an SATB voicer),
one track per voice follows the conductor instead, ordered top voice first,
each named after its voice and carrying only that voice's note per chord --
see :func:`write_midi_file` for the exact fallback rule. All timing comes from
the beat domain of the render, converted to MIDI ticks through the meter map,
so the exported file matches playback exactly.

Beat/tempo domain note: in Chord Notepad one "beat" is one meter-denominator
note, so ``seconds_per_beat = 60/bpm`` regardless of the denominator. A quarter
note is therefore ``unit/4`` app-beats, which is why the exported MIDI tempo is
``60_000_000 * unit / (4 * bpm)`` µs per quarter (this reduces to the familiar
``60e6/bpm`` in 4/4) and why a meter change alters the tempo meta even at constant
BPM.
"""
import logging
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import mido

from models.rendered_song import RenderedChord, RenderedSong
from exceptions import FileOperationError

logger = logging.getLogger(__name__)

PPQ = 480
"""Pulses (ticks) per quarter note used for the exported file."""

_DEFAULT_TITLE = "Chord Notepad export"


def _is_power_of_two(value: int) -> bool:
    """Return True if ``value`` is a positive power of two (SMF-encodable unit)."""
    return value > 0 and (value & (value - 1)) == 0


class _BeatToTick:
    """Convert absolute app-beats to MIDI ticks through a meter map.

    Ticks accrue at ``PPQ * 4 / unit`` per beat within each meter segment, so a
    change of denominator changes the tick rate. Cumulative float tick offsets at
    each segment boundary are precomputed once; rounding happens per lookup (never
    accumulated) to avoid drift.
    """

    def __init__(self, meter_map: List[Tuple[float, Tuple[int, int]]]):
        # meter_map always has a first entry at beat 0.0; guard anyway.
        self._starts = [entry[0] for entry in meter_map] or [0.0]
        self._units = [entry[1][1] for entry in meter_map] or [4]
        self._cum: List[float] = [0.0]
        for i in range(1, len(self._starts)):
            span_beats = self._starts[i] - self._starts[i - 1]
            rate = PPQ * 4 / self._units[i - 1]
            self._cum.append(self._cum[i - 1] + span_beats * rate)

    def tick(self, beat: float) -> int:
        """Return the integer tick position of an absolute app-beat."""
        i = 0
        for j, start in enumerate(self._starts):
            if start <= beat + 1e-9:
                i = j
            else:
                break
        rate = PPQ * 4 / self._units[i]
        return round(self._cum[i] + (beat - self._starts[i]) * rate)


def _latest_value(change_map: list, beat: float):
    """Return the value of the last (start_beat, value) entry with start <= beat."""
    result = change_map[0][1]
    for start, value in change_map:
        if start <= beat + 1e-9:
            result = value
        else:
            break
    return result


def _tempo_for(bpm: int, unit: int) -> int:
    """MIDI tempo (µs per quarter note) for an app-BPM under meter denominator."""
    return round(60_000_000 * unit / (4 * bpm))


def _build_conductor_track(
    rendered: RenderedSong,
    b2t: _BeatToTick,
    title: Optional[str],
) -> mido.MidiTrack:
    """Build track 0: name, tempo map, meter map, and key-signature changes."""
    # Absolute-tick events as (tick, order_hint, message); order_hint keeps a
    # deterministic layout when several metas share a tick.
    events: List[Tuple[int, int, mido.MetaMessage]] = []
    events.append((0, 0, mido.MetaMessage(
        'track_name', name=title if title else _DEFAULT_TITLE, time=0)))

    # Tempo metas at the union of tempo_map and meter_map change points: a meter
    # change alters µs/quarter even at constant BPM.
    tempo_map = rendered.tempo_map or [(0.0, 120)]
    meter_map = rendered.meter_map or [(0.0, (4, 4))]
    union_beats = sorted({b for b, _ in tempo_map} | {b for b, _ in meter_map})
    last_tempo: Optional[int] = None
    for beat in union_beats:
        bpm = _latest_value(tempo_map, beat)
        unit = _latest_value(meter_map, beat)[1]
        tempo = _tempo_for(bpm, unit)
        if tempo == last_tempo:
            continue
        last_tempo = tempo
        events.append((b2t.tick(beat), 1, mido.MetaMessage(
            'set_tempo', tempo=tempo, time=0)))

    # Time-signature metas at each meter change; skip units SMF can't encode.
    for beat, (beats, unit) in meter_map:
        if not _is_power_of_two(unit):
            logger.warning(
                "Skipping time_signature at beat %s: denominator %s is not a "
                "power of two and cannot be encoded in a MIDI file", beat, unit)
            continue
        events.append((b2t.tick(beat), 2, mido.MetaMessage(
            'time_signature', numerator=beats, denominator=unit, time=0)))

    # Key-signature metas: emit whenever a chord's key differs from the last
    # emitted key (first non-None included). Skipped chords are ignored.
    prev_key: Optional[str] = None
    for rc in rendered.chords:
        if rc.skipped:
            continue
        if rc.key is None or rc.key == prev_key:
            continue
        try:
            msg = mido.MetaMessage('key_signature', key=rc.key, time=0)
        except (ValueError, KeyError):
            logger.warning("Skipping unencodable key signature '%s'", rc.key)
            prev_key = rc.key
            continue
        events.append((b2t.tick(rc.start_beat), 3, msg))
        prev_key = rc.key

    return _finalize_track(events, b2t.tick(rendered.total_beats))


def _build_chord_track(
    rendered: RenderedSong,
    b2t: _BeatToTick,
    program: int,
    track_name: str,
    note_source: Callable[[RenderedChord], Optional[List[int]]],
) -> mido.MidiTrack:
    """Build one chord track: name, program change, and note_on/note_off per chord.

    ``note_source`` extracts the notes to sound for each chord. The single
    combined-chord export passes ``lambda rc: rc.midi_notes``; a per-voice
    export passes one closure per voice that reads a single entry out of
    ``rc.voice_notes``. Sharing this builder keeps out-of-range handling,
    event ordering, and end-of-track placement identical across both paths.
    """
    events: List[Tuple[int, int, mido.Message]] = []
    events.append((0, 0, mido.MetaMessage('track_name', name=track_name, time=0)))
    events.append((0, 0, mido.Message(
        'program_change', channel=0, program=program, time=0)))

    for rc in rendered.chords:
        if rc.skipped or rc.is_rest:
            continue
        notes = note_source(rc)
        if not notes:
            continue
        on_tick = b2t.tick(rc.start_beat)
        off_tick = b2t.tick(rc.start_beat + rc.duration_beats)
        for note in notes:
            if note < 0 or note > 127:
                logger.warning(
                    "Skipping out-of-range MIDI note %s in chord '%s'",
                    note, rc.chord_info.chord)
                continue
            # note_off ordered before note_on at a shared tick (hint 1 vs 2).
            events.append((off_tick, 1, mido.Message(
                'note_off', channel=0, note=note, velocity=0, time=0)))
            events.append((on_tick, 2, mido.Message(
                'note_on', channel=0, note=note, velocity=100, time=0)))

    return _finalize_track(events, b2t.tick(rendered.total_beats))


def _voice_notes_complete(rendered: RenderedSong) -> bool:
    """True if every played chord's ``voice_notes`` matches ``voice_labels`` in length.

    "Played" means not skipped, not a rest, and carrying ``midi_notes``
    (chords that failed to resolve, if any, are exempt). Assumes the caller
    has already checked ``rendered.voice_labels`` is truthy.
    """
    n = len(rendered.voice_labels)
    for rc in rendered.chords:
        if rc.skipped or rc.is_rest or not rc.midi_notes:
            continue
        if rc.voice_notes is None or len(rc.voice_notes) != n:
            return False
    return True


def _build_voice_track(
    rendered: RenderedSong,
    b2t: _BeatToTick,
    program: int,
    voice_index: int,
    label: str,
) -> mido.MidiTrack:
    """Build one voice's track: the single note from ``voice_notes[voice_index]`` per chord."""

    def note_source(rc: RenderedChord) -> Optional[List[int]]:
        if rc.voice_notes is None:
            return None
        return [rc.voice_notes[voice_index]]

    return _build_chord_track(rendered, b2t, program, label, note_source)


def _finalize_track(events: list, total_tick: int) -> mido.MidiTrack:
    """Sort absolute-tick events, append end_of_track, convert to delta times."""
    events.sort(key=lambda e: (e[0], e[1]))
    last_tick = max((e[0] for e in events), default=0)
    end_tick = max(total_tick, last_tick)

    track = mido.MidiTrack()
    prev_tick = 0
    for tick, _hint, message in events:
        message.time = tick - prev_tick
        track.append(message)
        prev_tick = tick
    track.append(mido.MetaMessage('end_of_track', time=end_tick - prev_tick))
    return track


def write_midi_file(
    rendered: RenderedSong,
    path: Path,
    program: int = 0,
    title: Optional[str] = None,
) -> None:
    """Write a pre-rendered song to a format-1 Standard MIDI File.

    Args:
        rendered: The whole-song render whose beat domain and tempo/meter maps
            drive the exported timing.
        path: Destination file path.
        program: General MIDI program (instrument) number for the chord track(s).
        title: Track name for the conductor track; a default is used if omitted.

    Raises:
        FileOperationError: If the file cannot be written.

    When ``rendered.voice_labels`` is set (a fixed-ensemble picker voiced the
    song) and every played chord's ``voice_notes`` matches it in length, the
    song is written as one chord track per voice -- conductor first, then
    voices top-first (``voice_labels`` is stored low-to-high, so it is
    reversed for track order) -- instead of the single combined 'Chords'
    track. Unisons are legal: two voice tracks may carry the same pitch at
    the same time. If any played chord is missing matching ``voice_notes``,
    this falls back to the single-track path unchanged.
    """
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    b2t = _BeatToTick(rendered.meter_map or [(0.0, (4, 4))])
    midi.tracks.append(_build_conductor_track(rendered, b2t, title))

    if rendered.voice_labels and _voice_notes_complete(rendered):
        for voice_index in reversed(range(len(rendered.voice_labels))):
            label = rendered.voice_labels[voice_index]
            midi.tracks.append(
                _build_voice_track(rendered, b2t, program, voice_index, label)
            )
    else:
        if rendered.voice_labels:
            logger.debug(
                "voice_labels present but voice_notes incomplete; "
                "falling back to single 'Chords' track")
        midi.tracks.append(
            _build_chord_track(rendered, b2t, program, 'Chords', lambda rc: rc.midi_notes)
        )

    try:
        midi.save(str(path))
    except (OSError, IOError) as exc:
        raise FileOperationError(f"Failed to write MIDI file '{path}': {exc}") from exc

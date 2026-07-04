"""Pre-rendered song model for the pre-computed playback pipeline.

A ``RenderedSong`` is the whole-song, deterministic result of walking a parsed
song (chords + directives) once: resolving/voicing every chord, computing
absolute beat and time positions, and recording tempo/meter change points. It
is produced by :class:`services.song_renderer.SongRenderer` and consumed by
:func:`services.event_compiler.compile_events` to build the ``MidiEvent`` stream.

The beat-domain fields (``start_beat``/``duration_beats``) and the
``tempo_map``/``meter_map`` are deliberate future-proofing for MIDI file export
(SMF is tick/tempo-map based). Playback itself only needs the seconds-domain
fields, but the beat domain is populated correctly regardless.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from models.chord import ChordInfo
from models.chord_notes import ChordNotes


@dataclass
class RenderedChord:
    """A single voiced chord (or rest) at an absolute position in the song."""

    chord_info: ChordInfo
    """Source token, carrying the chord symbol and its char offsets."""

    chord_notes: Optional[ChordNotes]
    """Resolved note names; ``None`` for rests and skipped chords."""

    midi_notes: Optional[List[int]]
    """Voiced MIDI notes; ``None`` for rests and skipped chords."""

    line_index: int
    """Index of the line this chord came from."""

    item_index: int
    """Index of the item within its line."""

    start_beat: float
    """Absolute beat position at the chord's start (never rebased)."""

    duration_beats: float
    """Duration of the chord in beats."""

    start_time: float
    """Absolute song time in seconds at the chord's start."""

    duration_seconds: float
    """Duration of the chord in seconds."""

    bpm: int
    """Tempo in effect for this chord."""

    time_sig: Tuple[int, int]
    """Time signature (beats, unit) in effect for this chord."""

    key: Optional[str]
    """Key signature in effect (used to resolve roman numerals)."""

    bar: int
    """1-based bar number at the chord's start (rebased to the start position)."""

    is_rest: bool
    """Whether this entry is a rest (NC) rather than a sounding chord."""

    skipped: bool = False
    """True for chords before the playback start position: they advance beat
    accounting but are never voiced and emit no events."""


@dataclass
class RenderedSong:
    """The fully pre-rendered song: every chord voiced with absolute timing."""

    chords: List[RenderedChord] = field(default_factory=list)
    total_bars: int = 1
    total_beats: float = 0.0
    total_seconds: float = 0.0
    tempo_map: List[Tuple[float, int]] = field(default_factory=list)
    """(start_beat, bpm) change points, first entry at beat 0."""
    meter_map: List[Tuple[float, Tuple[int, int]]] = field(default_factory=list)
    """(start_beat, time_sig) change points, first entry at beat 0."""

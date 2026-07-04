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

    voice_notes: Optional[List[int]] = None
    """Per-voice MIDI notes, low to high, for fixed-ensemble pickers (e.g. a
    future SATB voicer). Duplicates are legal (unisons, when two voices land
    on the same note). ``None`` for free-voiced pickers (piano, guitar),
    rests, and skipped chords.

    Alignment: both this list and ``RenderedSong.voice_labels`` are stored
    LOW to HIGH, so ``voice_notes[i]`` is always the note sung by
    ``RenderedSong.voice_labels[i]`` -- despite the picker itself reporting
    ``voice_labels`` top-voice-first (see ``INotePicker.voice_labels``), the
    renderer reverses it once when copying it onto the ``RenderedSong`` so
    indices line up with the low-to-high ``voice_notes``/``midi_notes``
    convention used everywhere else in this pipeline.

    When this is set, ``midi_notes`` is an order-preserving deduplicated copy
    of this list (so a unison doesn't double-strike one synth note)."""

    fingering: Optional[List[int]] = None
    """Winning fretboard fingering for fretted-instrument (guitar) models.

    One entry per string in the picker's string order (lowest string first, as
    in ``GuitarChordPicker.tuning_midi``): ``-1`` = muted, ``0`` = open, a
    positive integer = that fret. A non-muted string ``s`` sounds
    ``tuning_midi[s] + fingering[s]``, so the fretted notes reconstruct
    ``midi_notes``. ``None`` for non-fretboard models (piano, ensemble), rests,
    and skipped chords."""

    hand_split: Optional[int] = None
    """Left-/right-hand split point for the piano model.

    With ``midi_notes`` read low-to-high, ``midi_notes[:hand_split]`` is the
    left hand and ``midi_notes[hand_split:]`` is the right hand. ``0`` when the
    model emits no left-hand (bass) notes (e.g. ``add_bass`` disabled). ``None``
    for non-piano models (guitar, ensemble), rests, and skipped chords."""


@dataclass(frozen=True)
class SongMarker:
    """A point-in-time annotation on the song timeline for a chord-sheet strip.

    Markers live in the same unrolled beat/time domain as ``RenderedChord`` so a
    strip view can draw a vertical rule (with a small flag) at each one: section
    starts, loop repeats, tempo changes, and meter changes. They are produced as
    a side effect of the renderer's single walk and are purely informational --
    playback, MIDI export, and voicing never read them.
    """

    beat: float
    """Absolute beat position, same domain as ``RenderedChord.start_beat``
    (never rebased for play-from-cursor)."""

    time: float
    """Absolute song time in seconds, same domain as
    ``RenderedChord.start_time``. In the skipped play-from-cursor prefix this is
    ``0.0`` -- matching the skipped chords there, whose time position also does
    not advance."""

    kind: str
    """One of ``'section'``, ``'loop'``, ``'tempo'``, ``'meter'``."""

    text: str
    """Display text, e.g. ``'chorus'``, ``'chorus (2/3)'``, ``'140 bpm'``,
    ``'3/4'``."""


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
    markers: List["SongMarker"] = field(default_factory=list)
    """Timeline markers in walk order (non-decreasing ``beat``): section
    starts, loop repeats, tempo changes, and meter changes. Empty for a song
    with no directives. See :class:`SongMarker`."""
    voice_labels: Optional[List[str]] = None
    """Ordered voice names for a fixed-ensemble picker (e.g. ``["Bass",
    "Tenor", "Alto", "Soprano"]``), or ``None`` for free-voiced pickers
    (piano, guitar).

    Stored LOW to HIGH -- reversed from ``INotePicker.voice_labels``, which
    reports top-voice-first -- so it aligns index-for-index with each
    ``RenderedChord.voice_notes`` (also low to high)."""
    voice_staves: Optional[List[str]] = None
    """Per-voice grand-staff assignment for a fixed-ensemble picker (each entry
    ``'treble'`` or ``'bass'``), or ``None`` for free-voiced pickers (piano,
    guitar).

    Stored LOW to HIGH, aligned index-for-index with :attr:`voice_labels` and
    each ``RenderedChord.voice_notes`` -- reversed once from
    ``INotePicker.voice_staves`` (which reports top-voice-first, matching
    ``voice_labels``) exactly like ``voice_labels`` is. A chord-sheet staff
    renderer uses ``voice_staves[i]`` to decide which staff of a grand staff
    the note ``voice_notes[i]`` (sung by ``voice_labels[i]``) is drawn on."""

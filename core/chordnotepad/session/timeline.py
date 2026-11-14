"""The song's timeline for a player's scrubber: its sections in bars, and
where a bar or a chord is on it.

:func:`song_sections` turns a rendered song's ``section`` and ``loop``
markers (``RenderedSong.markers``) into :class:`~session.state.TimelineSection`
values that tile the song's bars, counted from the top of the song as
``RenderedChord.song_bar`` counts them. A marker belongs to the bar its first
chord starts in, so a label in the middle of a bar starts its section at that
bar and the section before it ends one bar earlier. Two markers that land in
the same bar keep the later one. A label with no chord after it starts no
section. Bars before the first label form a section with an empty label.

:func:`chord_at_bar` is where a click on the timeline seeks to, and
:class:`TimelinePosition` what the player shows as bar:beat (the Qt desktop
reads both through ``AppSession.timeline_offset`` and
``AppSession.timeline_position``).
"""

import math
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from chordnotepad.session.state import TimelineSection

#: Marker kinds that start a section; ``loop`` is a repeated pass.
_SECTION_KINDS = ("section", "loop")
_EPS = 1e-9


def song_sections(song: Optional[Any]) -> Tuple[TimelineSection, ...]:
    """The sections of ``song`` (a ``RenderedSong``) from bar 1 to its last bar.

    Returns ``()`` for None or a song without chords.
    """
    chords = list(getattr(song, "chords", None) or ())
    if not chords:
        return ()
    total = max(1, int(song.total_bars))
    starts: List[Tuple[int, str, bool]] = []   # (first bar, label, repeat)
    index = 0
    for marker in getattr(song, "markers", None) or ():
        if marker.kind not in _SECTION_KINDS:
            continue
        while index < len(chords) and chords[index].start_beat < marker.beat - _EPS:
            index += 1
        if index == len(chords):
            break
        chord = chords[index]
        bar = min(total, max(1, chord.song_bar or chord.bar))
        start = (bar, marker.label or marker.text, marker.kind == "loop")
        if starts and starts[-1][0] >= bar:
            starts[-1] = start
        else:
            starts.append(start)
    if not starts or starts[0][0] > 1:
        starts.insert(0, (1, "", False))
    ends = [first - 1 for first, _, _ in starts[1:]] + [total]
    return tuple(TimelineSection(label, first, last, repeat)
                 for (first, label, repeat), last in zip(starts, ends))


@dataclass(frozen=True)
class TimelinePosition:
    """Where a chord is in the song's time, and how fast its beats go.

    Attributes:
        bar: Its bar, 1-based, counted from the top of the song.
        beat: Where in ``bar`` it starts, in beats from 1 (``2.5`` is halfway
            through the second beat).
        beats_per_bar: The time signature's beats per bar in effect.
        bpm: The tempo in effect (directives applied; the speed multiplier
            isn't).
        total_bars: The song's bars.
        duration_beats: How long the chord lasts, in beats (0 if unknown).
    """

    bar: int
    beat: float
    beats_per_bar: int
    bpm: int
    total_bars: int
    duration_beats: float = 0.0

    @property
    def beat_number(self) -> int:
        """The beat the chord starts on (a chord at 2.5 is on beat 2)."""
        return max(1, int(math.floor(self.beat + _EPS)))


def chord_position(song: Any, index: int) -> Optional[TimelinePosition]:
    """The position of chord ``index`` of ``song`` (a ``RenderedSong``)."""
    chords = list(getattr(song, "chords", None) or ())
    if not 0 <= index < len(chords):
        return None
    chord = chords[index]
    return TimelinePosition(
        bar=max(1, chord.song_bar or chord.bar),
        beat=float(chord.song_beat or 1.0),
        beats_per_bar=int(chord.time_sig[0]),
        bpm=int(chord.bpm),
        total_bars=max(1, int(song.total_bars)),
        duration_beats=float(chord.duration_beats),
    )


def chord_at_bar(song: Any, bar: int, playable: Any = None) -> Optional[int]:
    """The index of the chord a seek to ``bar`` lands on, or None.

    The first chord starting in ``bar`` or later; past the last one, the last
    chord. ``playable(index)`` (default: every chord that isn't skipped)
    leaves out chords that can't be sought to, like rests.
    """
    chords = list(getattr(song, "chords", None) or ())
    if playable is None:
        def playable(i: int) -> bool:
            return not chords[i].skipped
    last = None
    for index, chord in enumerate(chords):
        if not playable(index):
            continue
        if (chord.song_bar or chord.bar) >= bar:
            return index
        last = index
    return last

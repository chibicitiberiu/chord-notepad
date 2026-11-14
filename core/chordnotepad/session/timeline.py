"""The song's timeline for a player's scrubber: its sections in bars.

:func:`song_sections` turns a rendered song's ``section`` and ``loop``
markers (``RenderedSong.markers``) into :class:`~session.state.TimelineSection`
values that tile the song's bars, counted from the top of the song as
``RenderedChord.song_bar`` counts them. A marker belongs to the bar its first
chord starts in, so a label in the middle of a bar starts its section at that
bar and the section before it ends one bar earlier. Two markers that land in
the same bar keep the later one. A label with no chord after it starts no
section. Bars before the first label form a section with an empty label.
"""

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

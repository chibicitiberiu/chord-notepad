"""What a song starts with: its tempo, time signature and key.

A song may set them with directives before its first chord; whatever it
doesn't set comes from the toolbar (the user's defaults, not saved with the
song). Android's player shows the result as a pill ("90 · 3/4 · G") and a
Song defaults sheet, from which the missing directives can be written into
the song.
"""

from typing import List, Optional, Sequence, Tuple

from models.chord import ChordInfo
from models.directive import BPMModifierType, Directive, DirectiveType
from models.line import Line
from session.state import SongDefault, SongDefaultsState

#: Between the values in :attr:`SongDefaultsState.summary`.
SEPARATOR = " · "


def _directives_before_first_chord(lines: Sequence[Line]) -> List[Directive]:
    """The valid directives that come before the song's first valid chord."""
    found = []
    for line in lines:
        for item in line.items:
            if isinstance(item, ChordInfo):
                if item.is_valid and line.is_chord_line():
                    return found
            elif item.is_valid:
                found.append(item)
    return found


def _apply_bpm(directive: Directive, current: int, initial: int) -> int:
    """The tempo after a ``{bpm}`` directive (as the song renderer applies it)."""
    kind, value = directive.bpm_modifier_type, directive.bpm_modifier_value
    if kind == BPMModifierType.RELATIVE:
        return int(current + value)
    if kind == BPMModifierType.PERCENTAGE:
        return int(current * value / 100)
    if kind == BPMModifierType.MULTIPLIER:
        return int(current * value)
    if kind == BPMModifierType.RESET:
        return initial
    return int(directive.bpm) if directive.bpm is not None else current


def song_defaults(lines: Sequence[Line], bpm: int, time_signature: Tuple[int, int],
                  key: Optional[str]) -> SongDefaultsState:
    """The values the song starts with.

    Args:
        lines: The detected lines of the song.
        bpm: The toolbar tempo (the default, and what relative tempo
            directives apply to).
        time_signature: The toolbar's ``(beats, unit)``.
        key: The toolbar key, or None.
    """
    tempo, tempo_at = int(bpm), None
    beats, unit = time_signature
    time_at = None
    song_key, key_at = key or "", None
    for directive in _directives_before_first_chord(lines):
        if directive.type == DirectiveType.BPM:
            tempo = _apply_bpm(directive, tempo, int(bpm))
            if tempo_at is None:
                tempo_at = directive.start
        elif directive.type == DirectiveType.TIME_SIGNATURE:
            beats, unit = directive.beats, directive.unit
            if time_at is None:
                time_at = directive.start
        elif directive.type == DirectiveType.KEY and directive.key:
            song_key = directive.key
            if key_at is None:
                key_at = directive.start
    values = (
        SongDefault(str(tempo), tempo_at is not None, tempo_at),
        SongDefault(f"{beats}/{unit}", time_at is not None, time_at),
        SongDefault(song_key, key_at is not None, key_at),
    )
    summary = SEPARATOR.join(v.value for v in values if v.value)
    return SongDefaultsState(tempo=values[0], time=values[1], key=values[2], summary=summary)


def missing_directives(state: SongDefaultsState) -> List[str]:
    """The directives that would make the song set what it now takes from
    the toolbar, in tempo, time, key order (no key directive without a key)."""
    missing = []
    if not state.tempo.from_directive:
        missing.append(f"{{bpm: {state.tempo.value}}}")
    if not state.time.from_directive:
        missing.append(f"{{time: {state.time.value}}}")
    if not state.key.from_directive and state.key.value:
        missing.append(f"{{key: {state.key.value}}}")
    return missing

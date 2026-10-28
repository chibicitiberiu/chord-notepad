"""User-facing strings the session builds, so every UI words things the same.

So far: the status-line texts of playback and of the editing commands, and
the audio and playback error messages. Titles, the multiplier parse and the menu models join with the
steps that move them into the session (``docs/architecture/session.md``).
"""

from typing import Optional, Union

READY = "Ready"
PAUSED = "Paused playback"
RESUMED = "Resumed playback"
STOPPED = "Stopped playback"
AUDIO_UNAVAILABLE_STATUS = "Audio is not available"
PLAYBACK_FAILED = "Playback failed"

PLAYBACK_ERROR_TITLE = "Playback Error"
AUDIO_ERROR_TITLE = "Audio Error"


def playback_started_status(chord_count: int, from_cursor: bool) -> str:
    """The status after Play started a song.

    Args:
        chord_count: Valid chords in the text.
        from_cursor: Whether playback started at the cursor (Shift+Play).
    """
    if from_cursor:
        return f"Playing from cursor ({chord_count} chords)..."
    return f"Playing {chord_count} chords..."


def nothing_to_play_status(from_cursor: bool) -> str:
    """The status when Play found no chords (after the cursor, with Shift)."""
    return "No chords to play from cursor" if from_cursor else "No chords to play"


def playing_chord_status(bar: int, total_bars: int, bpm: Union[int, float, None],
                         beats: int, unit: int, key: Optional[str], chord: str) -> str:
    """The status while a song plays, e.g. ``Bar 2/8 | 120 BPM | 4/4 | Key: C | Playing: G``.

    Args:
        bar: The current bar, 1-based.
        total_bars: Bars in the song.
        bpm: The effective tempo.
        beats: Time-signature numerator.
        unit: Time-signature denominator.
        key: The current key, or None (then the key part is left out).
        chord: The chord sounding now, as written.
    """
    parts = [f"Bar {bar}/{total_bars}", f"{bpm} BPM", f"{beats}/{unit}"]
    if key:
        parts.append(f"Key: {key}")
    parts.append(f"Playing: {chord}")
    return " | ".join(parts)


def tapped_chord_status(chord: str) -> str:
    """The status after a tapped chord was played."""
    return f"Playing: {chord}"


def playback_error_message(reason: str) -> str:
    """The message for a song that couldn't be rendered for playback."""
    return f"Could not play the song.\n\n{reason}"


def audio_unavailable_message(reason: str, from_click: bool) -> str:
    """The message for audio that couldn't be started.

    Args:
        reason: Why, usually the ``AudioInitializationError`` text; empty for
            a generic message.
        from_click: True for click-to-hear actions, which are reported only
            once per session, so the message says clicks stay silent.
    """
    message = reason or "Audio is not available."
    if from_click:
        message += "\n\nClicked chords won't play until this is fixed."
    return message


# -- editing commands ------------------------------------------------------------


def _scope(has_selection: bool) -> str:
    return "selection" if has_selection else "whole song"


def transposed_status(semitones: int, has_selection: bool) -> str:
    """The status after Transpose, e.g. ``Transposed whole song by +2 semitones``."""
    return f"Transposed {_scope(has_selection)} by {semitones:+d} semitones"


def converted_status(notation: str) -> str:
    """The status after converting the text to ``american`` or ``european`` notation."""
    return f"Converted to {notation.capitalize()} notation"


def inserted_status(text: str) -> str:
    """The status after a directive was inserted, e.g. ``Inserted: {bpm: 90}``."""
    return f"Inserted: {text}"


def capo_suggested_status(capo: int, has_selection: bool, voicing: str) -> str:
    """The status after Suggest Capo inserted ``{capo: N}``.

    Args:
        capo: The suggested fret.
        has_selection: Whether only the selection was scored.
        voicing: The voicing's display name.
    """
    return f"Suggested capo {capo} for the {_scope(has_selection)} on {voicing}"


def no_capo_status(has_selection: bool, voicing: str) -> str:
    """The status when no capo makes the song (or selection) easier to play."""
    return f"No capo makes the {_scope(has_selection)} easier on {voicing}"

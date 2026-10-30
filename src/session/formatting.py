"""User-facing strings the session builds, so every UI words things the same.

The status-line texts of playback, the editing commands and the document
flows; the window title; the audio, playback and file error messages and the
unsaved-changes question; the Voicing and Instrument menu models.
"""

from typing import Iterable, Mapping, Optional, Sequence, Tuple, Union

from models.ensemble_spec import BUILTIN_ENSEMBLES
from models.fretboard_spec import BUILTIN_FRETBOARDS
from session.platform import ANDROID, DESKTOP, pick
from session.state import InstrumentFamily, MenuItem

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


def tempo_clamped_warning(bpm: int, line: int) -> str:
    """The status note while a clamped relative tempo change plays:
    ``Tempo clamped to 400 BPM at line 5``."""
    return f"Tempo clamped to {bpm} BPM at line {line}"


def with_tempo_clamp(status: str, tempo_clamp, separator: str) -> str:
    """``status`` with the clamped-tempo note appended when ``tempo_clamp``
    (``(bpm, line)``) is set."""
    if not tempo_clamp:
        return status
    return f"{status}{separator}{tempo_clamped_warning(*tempo_clamp)}"


def tapped_chord_status(chord: str) -> str:
    """The status after a tapped chord was played."""
    return f"Playing: {chord}"


# -- the Android player's status line ----------------------------------------------
#
# Android shows the status inside the player, so while something plays (or
# a playhead is set) it holds only the position and what is happening:
# "Bar 6/24 · Playing Em". The desktop keeps its longer texts above.

#: Between the position and the activity in the player's status.
POSITION_SEPARATOR = " · "
#: Android's status while a song is being rendered before its first chord.
STARTING = "Starting…"
#: Why the voicing can't change while a song plays (it is rendered up front).
VOICING_LOCKED_REASON = "Pause to change the voicing"
#: Why the song defaults' tempo and "Write into song" wait while a song plays
#: or is paused (the tempo is rendered up front; the text is locked).
SONG_DEFAULTS_LOCKED_REASON = "Stop playback to change the tempo or write into the song"


def position_status(bar: int, total_bars: int, activity: Optional[str] = None) -> str:
    """The player's status: ``Bar 6/24``, or ``Bar 6/24 · Playing Em``.

    Args:
        bar: The bar, 1-based; 0 when unknown (then only the activity, or
            :data:`READY` without one).
        total_bars: Bars in the song.
        activity: What is happening (``Playing Em``, ``Paused``), or None.
    """
    if bar <= 0 or total_bars <= 0:
        return activity or READY
    position = f"Bar {bar}/{total_bars}"
    return f"{position}{POSITION_SEPARATOR}{activity}" if activity else position


def playing_activity(chord: str) -> str:
    """The player's activity while ``chord`` sounds: ``Playing Em``."""
    return f"Playing {chord}"


#: The player's activity while paused.
PAUSED_ACTIVITY = "Paused"

#: Between a directive's reason and its syntax in a one-line hint.
HINT_REASON_SEPARATOR = " — "


def directive_hint_status(message: str, syntax: str) -> str:
    """A directive hint (``DirectiveHint``) on one line, for a status bar:
    ``Tempo must be 20-400 — {bpm: 120} · {bpm: +10} · …``.

    The reason (invalid, or has no effect) goes first; the syntax's lines
    (one per directive a half-typed keyword could become) are joined with
    " · ". "" when there is no hint (``syntax`` is "").

    Args:
        message: Why the directive is invalid or has no effect, or "".
        syntax: The directive's correct syntax, one line per directive.
    """
    if not syntax:
        return ""
    examples = POSITION_SEPARATOR.join(line for line in syntax.splitlines() if line)
    return f"{message}{HINT_REASON_SEPARATOR}{examples}" if message else examples


def directive_hint_tooltip(message: str, syntax: str) -> str:
    """A directive hint for a hover tooltip: the reason, then the syntax on
    its own line(s). "" when there is neither."""
    return "\n".join(part for part in (message, syntax) if part)


def playback_error_message(reason: str) -> str:
    """The message for a song that couldn't be rendered for playback."""
    return f"Could not play the song.\n\n{reason}"


_CLICKS_SILENT = {
    DESKTOP: "\n\nClicked chords won't play until this is fixed.",
    ANDROID: "\n\nTapped chords won't play until this is fixed.",
}


def audio_unavailable_message(reason: str, from_click: bool, platform: str = DESKTOP) -> str:
    """The message for audio that couldn't be started.

    Args:
        reason: Why, usually the ``AudioInitializationError`` text; empty for
            a generic message.
        from_click: True for click-to-hear actions, which are reported only
            once per session, so the message says clicks (taps) stay silent.
        platform: ``desktop`` or ``android`` (``session.platform``).
    """
    message = reason or "Audio is not available."
    if from_click:
        message += pick(_CLICKS_SILENT, platform)
    return message


# -- documents -------------------------------------------------------------------

APP_TITLE = "Chord Notepad"
UNTITLED = "Untitled"
#: The name Save As suggests for a document that was never saved.
UNTITLED_FILE_NAME = "Untitled.txt"
NEW_DOCUMENT_STATUS = "New file created"

FILE_ERROR_TITLE = "Error"
OPEN_FAILED = "Failed to open file"
SAVE_FAILED = "Failed to save file"
EXPORT_FAILED = "Failed to export MIDI file"

CONFIRM_DISCARD_TITLE = "Unsaved Changes"
CONFIRM_DISCARD_MESSAGE = "Do you want to save your changes?"


def window_title(display_name: Optional[str], is_modified: bool) -> str:
    """The window title, e.g. ``song.txt* - Chord Notepad``.

    Args:
        display_name: The document's name, or None for a new one (``Untitled``).
        is_modified: Whether it has unsaved changes (marked with ``*``).
    """
    marker = "*" if is_modified else ""
    return f"{display_name or UNTITLED}{marker} - {APP_TITLE}"


def midi_export_name(stem: Optional[str]) -> str:
    """The name Export MIDI suggests, e.g. ``song.mid`` (``Untitled.mid`` without a document)."""
    return f"{stem or UNTITLED}.mid"


def opened_status(location: str) -> str:
    """The status after a document was opened."""
    return f"Opened: {location}"


def saved_status(location: str) -> str:
    """The status after the document was saved."""
    return f"Saved: {location}"


def exporting_midi_status(location: str) -> str:
    """The status while a MIDI file is being rendered."""
    return f"Exporting MIDI: {location}..."


def exported_midi_status(location: str) -> str:
    """The status after a MIDI file was exported."""
    return f"Exported MIDI: {location}"


def file_error_message(action: str, location: str, reason: Optional[str]) -> str:
    """The message for a failed open, save or export.

    Args:
        action: What failed, e.g. :data:`OPEN_FAILED`.
        location: The document, as the user sees it.
        reason: Why (the store's or the renderer's message), if known.
    """
    message = f"{action}:\n{location}"
    if reason:
        message += f"\n\n{reason}"
    return message


def renamed_status(display_name: str) -> str:
    """The status after the document was renamed (or an untitled one named)."""
    return f"Renamed to {display_name}"


#: The extension a never-saved document gets with its name.
DEFAULT_EXTENSION = ".txt"
#: The longest document name accepted, in UTF-8 bytes (common file systems).
MAX_NAME_BYTES = 255
NAME_EMPTY = "Please enter a name."
NAME_HAS_SEPARATOR = "A name can't contain / or \\."
NAME_RESERVED = "That name isn't allowed."
NAME_CONTROL = "A name can't contain control characters."
NAME_TOO_LONG = "That name is too long."
NOTHING_TO_WRITE_STATUS = "The song already sets its tempo, time signature and key"


# -- editing commands ------------------------------------------------------------


def _scope(has_selection: bool) -> str:
    return "selection" if has_selection else "whole song"


def transposed_status(semitones: int, has_selection: bool) -> str:
    """The status after Transpose, e.g. ``Transposed whole song by +2 semitones``."""
    return f"Transposed {_scope(has_selection)} by {semitones:+d} semitones"


def converted_status(notation: str) -> str:
    """The status after converting the text to ``american`` or ``european`` notation."""
    return f"Converted to {notation.capitalize()} notation"


def nothing_to_convert_status(source: str) -> str:
    """The status when a convert from ``source`` notation changed nothing,
    e.g. ``No American chords to convert``."""
    return f"No {source.capitalize()} chords to convert"


def inserted_status(text: str) -> str:
    """The status after a directive was inserted, e.g. ``Inserted: {bpm: 90}``."""
    return f"Inserted: {text}"


def inserted_chord_status(chord: str) -> str:
    """The status after the chord identifier inserted ``chord``."""
    return f"Inserted chord: {chord}"


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


def finding_capo_status(has_selection: bool, voicing: str) -> str:
    """The status while Suggest Capo scores the song (or selection)."""
    return f"Finding a capo for the {_scope(has_selection)} on {voicing}..."


def capo_scope_text(has_selection: bool) -> str:
    """The Suggest Capo dialog's line on where the capo goes."""
    if has_selection:
        return "Applies to the selected part only: inserted at the start of the selection."
    return "Applies to the whole song: inserted at the top of the song, replacing a capo there."


#: The status when the text changed while Suggest Capo was scoring it.
CAPO_STALE_STATUS = "The song changed while finding a capo; nothing was inserted"


# -- settings ------------------------------------------------------------------------

#: The title of the error naming the first invalid voicing at Save.
INVALID_VOICING_TITLE = "Invalid Voicing"
SETTINGS_TITLE = "Settings"


def settings_save_failed(reason: str) -> str:
    """The message for a config that couldn't be written at Save."""
    return f"Could not save settings.\n\n{reason}"


# -- chord identifier --------------------------------------------------------------

IDENTIFIER_TITLE = "Identify Chord"
#: What the identifier shows before any note is selected.
IDENTIFIER_PROMPT = "Select notes to identify chords..."


def identifier_not_notes(tokens: Sequence[str]) -> str:
    """The typed-notes error naming what wasn't a note, e.g. ``Not a note: H, x7``."""
    label = "Not a note" if len(tokens) == 1 else "Not notes"
    return f"{label}: {', '.join(tokens)}"


# -- menus -------------------------------------------------------------------------

#: The built-in fretboard tunings, in menu order.
BUILTIN_FRETBOARD_ORDER = ("standard", "drop_d", "dadgad", "open_g", "ukulele")
#: The built-in ensembles, in menu order.
BUILTIN_ENSEMBLE_ORDER = ("satb", "ttbb", "ssa", "quartet")

#: General MIDI's instrument families: (first program, last program, name).
INSTRUMENT_FAMILIES = (
    (0, 7, "Piano"),
    (8, 15, "Chromatic Percussion"),
    (16, 23, "Organ"),
    (24, 31, "Guitar"),
    (32, 39, "Bass"),
    (40, 47, "Strings"),
    (48, 55, "Ensemble"),
    (56, 63, "Brass"),
    (64, 71, "Reed"),
    (72, 79, "Pipe"),
    (80, 87, "Synth Lead"),
    (88, 95, "Synth Pad"),
    (96, 103, "Synth Effects"),
    (104, 111, "Ethnic"),
    (112, 119, "Percussive"),
    (120, 127, "Sound Effects"),
)


def voicing_menu_groups(voicings: Mapping[str, Mapping]) -> Tuple[Tuple[MenuItem, ...], ...]:
    """The Voicing menu's choices, in separated groups.

    Piano; the built-in fretboards; the built-in ensembles; then the user's
    voicings (the registry), grouped by model and sorted by name, if any.

    Args:
        voicings: The voicings registry, ``{name: {"model": ..., ...}}``.
    """
    groups = [
        (MenuItem("Piano", "piano"),),
        tuple(MenuItem(BUILTIN_FRETBOARDS[key].label, f"guitar:{key}")
              for key in BUILTIN_FRETBOARD_ORDER),
        tuple(MenuItem(BUILTIN_ENSEMBLES[key].label, f"ensemble:{key}")
              for key in BUILTIN_ENSEMBLE_ORDER),
    ]
    if voicings:
        names = sorted(voicings, key=lambda n: (voicings[n].get("model", ""), n.lower()))
        groups.append(tuple(MenuItem(name, f"voicing:{name}") for name in names))
    return tuple(groups)


def instrument_label(program: int, name: str) -> str:
    """An Instrument menu entry, e.g. `` 24 - Nylon Guitar``."""
    return f"{program:3d} - {name}"


def instrument_families(instruments: Iterable[Sequence], current: int
                        ) -> Tuple[InstrumentFamily, ...]:
    """The Instrument menu: the soundfont's programs by General MIDI family.

    Args:
        instruments: ``(program, name)`` pairs from the soundfont.
        current: The program in use; its family is marked current.
    """
    available = [(int(program), str(name)) for program, name in instruments]
    return tuple(
        InstrumentFamily(
            name=family,
            is_current=first <= current <= last,
            items=tuple(MenuItem(instrument_label(program, name), str(program))
                        for program, name in available if first <= program <= last),
        )
        for first, last, family in INSTRUMENT_FAMILIES
    )

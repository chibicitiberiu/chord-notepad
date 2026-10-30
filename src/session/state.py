"""The session's state DTOs: what a view needs to draw itself.

States are frozen dataclasses holding only ``str``/``int``/``float``/``bool``/
``None``, tuples of those and ``str`` enums, so the bridge can serialize them
and no live object (a ``ChordInfo``, a ``Line``) leaks to a view. A field
typed ``Any`` holds plain JSON data (dicts with ``str`` keys, lists, scalars;
the voicing form's values), copied when the state is made and never changed
after. The session
keeps the latest value of each state type, replays them to a new listener,
and coalesces repeated changes (see :mod:`session.emitter`).

Only the states the session already publishes are defined here; the rest of
the design's list (``docs/architecture/session.md``) arrives with the steps
that publish them.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from session.documents import DocumentRef
from session.settings import SettingsValues


class SpanKind(str, Enum):
    """What a highlighted range of the text is."""

    CHORD = "chord"
    CHORD_INVALID = "chord_invalid"
    DIRECTIVE = "directive"
    DIRECTIVE_INVALID = "directive_invalid"
    COMMENT = "comment"


@dataclass(frozen=True)
class Span:
    """A highlighted range ``[start, end)`` of the text, in code points.

    ``message`` says why an invalid directive is invalid (``Tempo must be
    20-400``), for a tooltip; it is "" for every other span.
    """

    start: int
    end: int
    kind: SpanKind
    message: str = ""


@dataclass(frozen=True)
class HighlightState:
    """The highlight spans for one version of the text.

    Attributes:
        text_revision: The session's revision of the text the spans were
            computed for. It goes up on every change to the session's copy.
        client_token: The token the view passed with the ``set_text`` that
            produced that text (0 for edits the session made). A view whose
            text has moved on since can tell the spans are stale and wait for
            the next state.
        spans: Comments, then chords, then directives, each in text order.
    """

    text_revision: int
    client_token: int
    spans: Tuple[Span, ...]


class PlaybackStatus(str, Enum):
    """Whether a song is playing."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass(frozen=True)
class PlaybackState:
    """Song playback: the transport status and the chord that is sounding.

    Attributes:
        status: Idle, playing or paused.
        playing_span: The chord sounding now (kind ``CHORD``), in code points
            of the text playback started from; None when idle or before the
            first chord.
        chord_index: Index of that chord in the played song's unrolled chord
            list (loop passes have distinct indices), or None.
        bar: The current bar, 1-based (0 when idle).
        total_bars: Bars in the played song (0 when idle).
        playhead_offset: Where the playhead is: the start of the chord Play
            starts from (``play_pause`` without an offset), in code points;
            None for no playhead (Play starts at the top). Set with
            ``set_playhead`` or ``rewind``; on Android also by chord taps,
            by playback (it follows the chord sounding) and by the end of
            the song (back to the first chord). Kept on chord spans across
            edits.

    The effective tempo of the chord sounding is the toolbar's
    (``ToolbarState.bpm_display``).
    """

    status: PlaybackStatus
    playing_span: Optional[Span] = None
    chord_index: Optional[int] = None
    bar: int = 0
    total_bars: int = 0
    playhead_offset: Optional[int] = None


class PlayAction(str, Enum):
    """What the Play/Pause button does when pressed."""

    PLAY = "play"
    PAUSE = "pause"
    RESUME = "resume"


@dataclass(frozen=True)
class ToolbarState:
    """The toolbar: notation, tempo, key, time signature, metronome, transport.

    Attributes:
        notation: ``american`` or ``european`` (detection and the key list).
        bpm: The user's base tempo.
        bpm_display: The tempo to show: while a song plays, that of the
            chord sounding (directives applied) once known; else ``bpm``.
        bpm_editable: False while a song plays or is paused (the tempo field
            then only displays ``bpm_display``).
        multiplier_pct: The speed multiplier in percent (100 = as written);
            adjustable during playback.
        key: The key for roman numerals, in ``notation`` (the first key
            option when none is set).
        key_options: The keys to choose from, in ``notation``.
        beats: Time-signature numerator.
        unit: Time-signature denominator.
        metronome: Whether the click track plays with the song.
        play_action: What the Play/Pause button does now.
    """

    notation: str
    bpm: int
    bpm_display: int
    bpm_editable: bool
    multiplier_pct: float
    key: str
    key_options: Tuple[str, ...]
    beats: int
    unit: int
    metronome: bool
    play_action: PlayAction


@dataclass(frozen=True)
class StatusState:
    """The status line under the editor."""

    text: str


@dataclass(frozen=True)
class EditorState:
    """How the editor looks and behaves.

    Attributes:
        font_family: The editor font's family, as configured (a view maps
            names it lacks to a fallback).
        font_size: The editor font's size in points.
        read_only: True while a song plays or is paused (the editor is locked
            so the playing-chord offsets stay valid).
        notation: ``american`` or ``european``: how chords are detected.
    """

    font_family: str
    font_size: int
    read_only: bool
    notation: str


@dataclass(frozen=True)
class MenuItem:
    """One choice in a menu or list a view shows.

    Attributes:
        label: What the user sees.
        value: What the view sends back when it is chosen.
    """

    label: str
    value: str


@dataclass(frozen=True)
class VoicingMenuState:
    """The Playback > Voicing menu: how chords are voiced.

    Attributes:
        selected: The value of the voicing in use (``piano``,
            ``guitar:standard``, ``ensemble:satb``, ``voicing:<name>``...).
        groups: The choices, in groups a view separates: piano, the built-in
            fretboards, the built-in ensembles, then the user's voicings (a
            group that would be empty is left out). Send a value back with
            ``set_voicing``.
        locked_reason: None while the voicing can be changed; while a song
            plays (not paused: it is rendered up front, so a change applies
            to a paused song when it resumes) the reason it can't, which a
            view shows on the disabled menu. ``set_voicing`` is refused then.
    """

    selected: str
    groups: Tuple[Tuple[MenuItem, ...], ...]
    locked_reason: Optional[str] = None


@dataclass(frozen=True)
class InstrumentFamily:
    """One General MIDI family (8 programs) in the Instrument menu.

    Attributes:
        name: The family, e.g. ``Guitar``.
        is_current: Whether it holds the instrument in use.
        items: The soundfont's programs in it; each value is the program
            number as a string.
    """

    name: str
    is_current: bool
    items: Tuple[MenuItem, ...]


@dataclass(frozen=True)
class InstrumentMenuState:
    """The Playback > Instrument menu.

    Attributes:
        current: The MIDI program in use (0-127). Send another with
            ``set_instrument``.
        families: The 16 General MIDI families, in program order (a family
            the soundfont has nothing for has no items).
    """

    current: int
    families: Tuple[InstrumentFamily, ...]


@dataclass(frozen=True)
class ChordSheetView:
    """One of the chord sheet's views (keyboard, staff, chord boxes, tab).

    Attributes:
        view_id: Send it back with ``set_chord_sheet_view``.
        label: The tab's label.
        available: False while the song can't be shown that way (fretted
            views need a fretboard voicing and some chords).
    """

    view_id: str
    label: str
    available: bool


@dataclass(frozen=True)
class ChordSheetState:
    """The chord-sheet strip under the editor.

    Attributes:
        visible: Whether the strip is shown.
        height: Its height in pixels (desktop; kept across runs).
        active_view: The view shown.
        views: Every view, in tab order, with its availability.
        disabled_reason: Why the unavailable views are unavailable, or None.
        zoom: The active view's zoom factor (1.0 = default).
        zoom_supported: Whether the active view zooms.
        current_index: The chord under the playhead (an index into the
            rendered song), or None.
        song_revision: Goes up whenever the strip rendered a new song, so a
            view knows to repaint.
        cursor_index: The rendered-song index of the playhead's chord
            (``PlaybackState.playhead_offset``), its first occurrence when
            loops repeat it, for the edge mark while nothing plays; None
            without a playhead or before the strip rendered that text.
    """

    visible: bool
    height: int
    active_view: str
    views: Tuple[ChordSheetView, ...]
    disabled_reason: Optional[str]
    zoom: float
    zoom_supported: bool
    current_index: Optional[int]
    song_revision: int
    cursor_index: Optional[int] = None


@dataclass(frozen=True)
class SongDefault:
    """One value a song starts with (tempo, time signature or key).

    Attributes:
        value: The value at the start of the song, as written in a
            directive: ``"90"``, ``"3/4"``, ``"G"``. ``""`` for a key when
            neither the song nor the toolbar sets one.
        from_directive: Whether a directive before the song's first chord
            sets it (then it is read-only in Song defaults); otherwise the
            value is the toolbar default (``set_bpm``,
            ``set_time_signature``, ``set_key`` change it; it is not saved
            with the song).
        directive_offset: The start of the first such directive (code
            points), for "Edit" to put the cursor there; None otherwise.
    """

    value: str
    from_directive: bool
    directive_offset: Optional[int] = None


@dataclass(frozen=True)
class SongDefaultsState:
    """What the song starts with: the Song defaults sheet and its pill.

    Republished when the text is detected again and when the toolbar values
    change. ``write_song_defaults`` writes the values no directive sets into
    the top of the song.

    Attributes:
        tempo: The starting tempo in BPM (directives before the first chord
            applied, relative ones too).
        time: The starting time signature, ``"beats/unit"``.
        key: The starting key (``""`` when none is set anywhere).
        summary: The pill's text, the values joined by ``" · "``
            (``"90 · 3/4 · G"``; an empty key is left out).
        locked_reason: None while the tempo and "Write into song" can be
            used; while a song plays or is paused (``set_bpm`` is ignored and
            ``write_song_defaults`` refused) the sentence saying why, e.g.
            "Stop playback to change the tempo or write into the song".
    """

    tempo: SongDefault
    time: SongDefault
    key: SongDefault
    summary: str
    locked_reason: Optional[str] = None


@dataclass(frozen=True)
class DocumentState:
    """The open document, for the window title and the Save As suggestion.

    Attributes:
        display_name: Its name (``song.txt``), or ``Untitled`` for a new
            document that was never saved.
        location: Where it is, as the user should see it; None for a new
            document.
        is_modified: Whether it has unsaved changes.
        title: The window title, e.g. ``song.txt* - Chord Notepad``.
        document_id: The open document's ``DocumentRef.id``, or None for a
            new document (Android keeps it with its draft, to restore it
            after the process was killed).
    """

    display_name: str
    location: Optional[str]
    is_modified: bool
    title: str
    document_id: Optional[str] = None


@dataclass(frozen=True)
class RecentDocumentsState:
    """The recently opened or saved documents (File > Recent Files).

    Attributes:
        items: Newest first, only those still available, at most the
            configured number. Send one back with ``open_recent``.
    """

    items: Tuple[DocumentRef, ...]


@dataclass(frozen=True)
class IdentifierNote:
    """A note selected in the chord identifier.

    Attributes:
        name: The note name, with sharps (``C``, ``C#`` ... ``B``).
        octave: Its octave (C4 is middle C).
        midi: Its MIDI number (C4 = 60).
    """

    name: str
    octave: int
    midi: int


@dataclass(frozen=True)
class IdentifierState:
    """The chord identifier: the selected notes and the chords they make.

    Attributes:
        notes: The selected notes, lowest first. A piano shows these; typed
            notes keep the octave typed (4 when left out), which may lie
            outside the keys a piano shows.
        notes_text: The selection as the typed-notes field shows it after a
            key was toggled: the distinct note names in pitch-class order,
            space separated (``"C E G"``). Don't overwrite the field with it
            while the user types there.
        typed_text_error: Set when the typed notes had something that isn't a
            note (it was skipped); None otherwise, and after a key toggle.
        candidates: The chords the notes make, simplest first. Tap one to
            hear it (``play_identified_chord``), insert it with
            ``insert_chord``.
        message: What to show instead of (or for lack of) candidates: the
            prompt to select notes, "no standard chord found", an error; None
            when there are candidates.
    """

    notes: Tuple[IdentifierNote, ...]
    notes_text: str
    typed_text_error: Optional[str]
    candidates: Tuple[str, ...]
    message: Optional[str]


@dataclass(frozen=True)
class SettingsState:
    """The settings a mobile Settings screen shows, and their limits.

    Published when the session starts and whenever the config changes
    (the toolbar writes the tempo, key, time signature and notation; Quick
    Start's "don't show again"; a save). ``values`` holds exactly the
    settings Android shows (the visibility rule: no log level, audio
    driver, SoundFont path or window geometry); send changed values back
    with ``save_settings`` (or ``apply_settings``).

    Attributes:
        values: The current settings.
        american_keys: The key choices in American notation (``values.key``
            may also be "" for none).
        european_keys: The key choices in European notation.
        font_size_min: Smallest editor font size.
        font_size_max: Largest editor font size.
        bpm_min: Slowest tempo.
        bpm_max: Fastest tempo.
        max_recent_files_max: Longest recent list (the shortest is 1).
        time_signature_units: The beat units to choose from.
    """

    values: SettingsValues
    american_keys: Tuple[str, ...]
    european_keys: Tuple[str, ...]
    font_size_min: int
    font_size_max: int
    bpm_min: int
    bpm_max: int
    max_recent_files_max: int
    time_signature_units: Tuple[int, ...]


@dataclass(frozen=True)
class VoicingGroup:
    """One model's voicings in the voicings editor's list.

    Attributes:
        model: ``fretboard``, ``piano`` or ``ensemble``.
        label: The group's heading.
        names: The working copy's voicings of that model, sorted.
    """

    model: str
    label: str
    names: Tuple[str, ...]


@dataclass(frozen=True)
class VoicingPreset:
    """An entry of the "Load config" menu; send both back with ``load_voicing_preset``.

    Attributes:
        label: What the menu shows.
        group: ``fretboard``, ``ensemble``, ``piano`` or ``custom`` (a view
            separates the groups).
    """

    label: str
    group: str


@dataclass(frozen=True)
class VoicingEditorState:
    """The voicings editor of a Settings screen (``begin_settings_edit``).

    Attributes:
        active: Whether a settings edit is open. It ends (``active`` False)
            when ``save_settings`` succeeded or ``cancel_settings_edit`` ran.
        revision: Goes up with every edit command, also one that changed
            nothing (a refused rename), so a view can reset its fields from
            this state.
        groups: The working copy's voicings by model, in list order.
        invalid: The voicings Save would refuse.
        presets: The "Load config" entries.
        selected: The voicing in the form, or None (show the placeholder).
        model: Its form's model (``voicing_editor_schema``'s ``forms`` key),
            or None.
        values: The form's values, keyed by field id (JSON; see
            ``settings_forms.voicing_form``); ``{}`` with nothing selected.
        field_errors: ``{field_id: message}`` for values that don't parse
            (``voice:<i>:<column>`` for a records cell).
        form_errors: Errors of the whole form (the spec's message).
        hints: ``{field_id: text}``: the grey hint under fields that have
            one, filled in from the values.
        dirty: Whether the selected voicing was edited since it was
            selected (a model switch asks for confirmation then).
    """

    active: bool
    revision: int
    groups: Tuple[VoicingGroup, ...]
    invalid: Tuple[str, ...]
    presets: Tuple[VoicingPreset, ...]
    selected: Optional[str]
    model: Optional[str]
    values: Any
    field_errors: Any
    form_errors: Tuple[str, ...]
    hints: Any
    dirty: bool


#: The voicings editor while no settings edit is open.
INACTIVE_VOICING_EDITOR = VoicingEditorState(
    active=False, revision=0, groups=(), invalid=(), presets=(), selected=None, model=None,
    values={}, field_errors={}, form_errors=(), hints={}, dirty=False)

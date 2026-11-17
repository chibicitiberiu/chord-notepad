# AppSession: the shared application layer

The shared layer every front end sits on: the Qt Quick desktop app, the
Kotlin/Compose Android app and, later, SwiftUI. "Where the session stands"
says what each area does and what is still interim, and why. The wire format Kotlin
and QML see is in `docs/ANDROID.md`, "Bridge contract".

The core is the `chordnotepad` package in `core/` (the session is
`chordnotepad.session`); the Qt front end is `chordnotepad_desktop` in
`desktop/`, and the Android glue is `chordnotepad_android`. Nothing is installed: each
front end puts the folders on `sys.path` (`pytest.ini`, the Makefile, the
launchers, the PyInstaller spec, Chaquopy's `srcDir`). Paths like
`session/bridge.py` below are inside `core/chordnotepad/`.

## Why

The viewmodels in `core/chordnotepad/viewmodels/` know nothing of any UI. The
wiring *between* them used to live in the first desktop window (a Tk one,
since removed). That wiring is:
- the chord-sheet feed and the playback-event fan-out;
- re-detection after transpose;
- applying settings and the notation toggle;
- the file flows and the status text.

A second UI (Kotlin/Compose on Android, later SwiftUI) would have to copy all of
it. AppSession moves that wiring into a host-agnostic core layer.
**Every** UI is a thin view over it, so the wiring exists once. The Qt
desktop app was written that way from the start: its QML only shows states
and sends commands.

## Decisions

- **The existing viewmodels stay as internal components.** AppSession composes
  them and is their only observer. They keep the domain logic, and their tests
  stay valid.
- **One outbound stream of frozen DTOs.**
  - *States* are coalesced: latest value wins.
  - *Events* are delivered in order.
  - Dialogs are request/response pairs.
- **The host owns the session thread.**
  - Qt: the GUI thread is the session thread.
  - Android: a Python-owned `ThreadedHost` thread.
- **Offsets are Unicode code points everywhere in Python.** Conversion to UTF-16
  happens only in the Kotlin `OffsetMapper`.

## Responsibilities

**AppSession (`core/chordnotepad/session/`)**
- **Text:** the text mirror and the modified flag; debounced chord detection;
  immediate re-detection after programmatic edits.
- **Highlighting:** highlight spans (chords, directives, comments); chord
  hit-testing by offset.
- **Chord sheet:** the feed (`detected_lines`, `key` and `voicing` →
  `ChordSheetViewModel.set_song`).
- **Playback:** the event fan-out (playhead, playing span, status text); the
  idle/playing transitions and editor read-only state.
- **Notation:** the toggle, including converting the key and swapping the key
  list.
- **Editing flows:** transpose, capo, convert notation, insert directive or chord;
  the existing-label lookup.
- **Settings:** applying them.
- **Document flows:** new, open, save, save-as, close, export MIDI and recent
  files; the unsaved-changes decision.
- **Formatting:** status texts, the title, BPM-multiplier parsing; the
  voicing-menu model and ordering; the instrument-family table; key options
  (`session/toolbar.py` holds the toolbar's value logic).

**Views (Qt, Compose, later SwiftUI)**
- Widgets, theme, icons, tooltip wording, dialog layout.
- Pixel/cursor ↔ offset conversion.
- Applying the undo policy carried by each edit event.
- Splitter and window-geometry persistence (stored through
  `set_window_geometry` / `set_chord_sheet_height`).
- Presenting requests as modal dialogs; native file pickers.
- Chord-sheet painting (replaying `DrawOps`).

**Existing viewmodels**
- All domain logic: parsing, rendering, transposing, capo scoring, MIDI export,
  and the chord sheet's own debounce, generations and gating.
- `TextEditorViewModel` becomes the detection component, driven only by the
  session.
- `SettingsViewModel` and `ChordIdentifierViewModel` stay scoped to their
  dialogs. The identifier's "insert" calls `session.insert_text`.

## Modules

```
core/chordnotepad/session/
  host.py          Host protocol, Cancellable, HostDispatch (queue_ui_callback shim)
  threaded_host.py ThreadedHost (queue + timer heap; Android/headless)
  settings.py      SettingsValues: the settings as plain values (bridge views);
                   DesktopSettingsValues adds the Qt desktop's (values_type(platform))
  testing.py       ManualHost (virtual clock), InMemoryDocumentStore, FakePlayer, EventRecorder
  errors.py        unexpected-error routing (handler registry; the handler throttles)
  documents.py     DocumentRef, DocumentStore, FileSystemDocumentStore
  state.py         frozen state DTOs
  events.py        one-off event + request DTOs
  audio_policy.py  AudioFailurePolicy: Play reports every time, clicks once per session
  emitter.py       Emitter: output buffering, coalescing and flush (the delivery contract)
  formatting.py    titles, status strings, voicing/instrument menu models
  toolbar.py       key list + key respelling, BPM/multiplier parse+format, ScrubScale (clamp/snap/quantize)
  directives.py    Insert-menu directives: field validation + messages, directive text, labels, loop choices
  pickers.py       the Qt ▾ value pickers' options (keys with twins, times, tempos, capo, loops)
  snippets.py      the Qt Directives palette: tiles, fill_snippet, select_range
  status_line.py   StatusLine: what a desktop status bar shows (status, directive hint, playback)
  support.py       the Android support prompt's policy (should_show_support_prompt, NAG_DELAY_DAYS), LaunchKind
  highlighting.py  find_comments, compute_spans(lines, text), chord_at(lines, offset),
                   nearest_chord(lines, text, offset) (the playhead's snap), first_chord
  song_defaults.py song_defaults(lines, bpm, time, key) -> SongDefaultsState; missing_directives
  flows.py         generator-based request/response FlowRunner
  workers.py       BackgroundWorker (single-thread executor, results via host.post)
  bootstrap.py     CoreServices, build_core_services(appdata, dispatch, paths=, player=, audio_options=),
                   create_session(host, services, documents, chord_sheet=)
  bridge.py        encode(dto) -> (type_name, json); decode_args/dispatch; SessionBridge;
                   ErrorEvents (throttled UnexpectedError); schema dump for Kotlin
  session.py       AppSession
core/chordnotepad/utils/paths.py    display_path / is_document_portal_path
core/chordnotepad/models/window_geometry.py  the window's and the sheet's sizes (logical pixels)
core/chordnotepad/audio/volume.py   the volume slider's curve (config volume -> synth.gain)
```

### Host

```python
class Cancellable(Protocol):
    def cancel(self) -> None: ...

class Host(Protocol):
    def post(self, cb: Callable[[], None]) -> None: ...            # any thread; FIFO onto session thread
    def call_later(self, delay_s: float, cb: Callable[[], None]) -> Cancellable: ...  # session thread only
    def is_session_thread(self) -> bool: ...
    def monotonic(self) -> float: ...
```

There are three implementations:
- **`QtHost`** (`desktop/chordnotepad_desktop/qt_host.py`): the Qt GUI thread
  is the session thread. `post` is a queued signal, `call_later` a
  single-shot `QTimer`. It exists before the window, and what is posted
  before `start()` waits.
- **`ManualHost`** (tests)
  - `run_pending()` runs posted callbacks.
  - `advance(seconds)` moves the virtual clock forward.
- **`ThreadedHost`** (Android, headless): `start()`, `shutdown()`.
  - One daemon thread. Each round fires the timers due at that moment
    (deadline order, ties in scheduling order), then runs what was posted by
    then (FIFO), so neither starves the other. A timer cancelled by a
    callback earlier in the same round doesn't fire.
  - A callback that raises goes to `session.errors` and the thread goes on.
  - `shutdown()` runs what was already posted, drops pending timers and
    later posts, and joins (returns at once on the session thread).
  - `call(fn, timeout)` runs `fn` on the session thread and waits for its
    result: the Android host builds the session that way, because the
    session and the chord sheet arm timers.

`HostDispatch(host).queue_ui_callback = host.post` keeps `PlaybackService`,
`NotePlayer` and `MainWindowViewModel` unchanged.

### Documents

```python
@dataclass(frozen=True)
class DocumentRef:
    id: str            # opaque: absolute path (desktop) / content URI (Android)
    display_name: str  # "song.txt" -> titles, Save-As suggestion
    location: str      # user-facing, for messages
    @property
    def stem(self) -> str: ...   # MIDI title

class DocumentStore(Protocol):
    def read_text(self, ref: DocumentRef) -> str: ...       # normalized; raises FileOperationError
    def write_text(self, ref: DocumentRef, text: str) -> None: ...
    def write_bytes(self, ref: DocumentRef, data: bytes) -> None: ...
    def is_available(self, ref: DocumentRef) -> bool: ...
    def recent(self) -> list[DocumentRef]: ...                # prunes unavailable ones
    def add_recent(self, ref: DocumentRef) -> None: ...       # capped (max_recent_files)
    def ref_for(self, document_id: str) -> DocumentRef: ...   # a picker's answer as a ref
    def rename(self, ref: DocumentRef, display_name: str) -> DocumentRef: ...
        # in place, never over another document; RenameNotSupported / FileOperationError
```

Reading and writing never touch the recent list: the
session's document flows call `add_recent` after a successful open or save,
and exports never join.

- **`FileSystemDocumentStore(file_service)`** delegates to `FileService`, which
  handles normalization, pruning recent files and error messages. It adds
  `ref_for_path(path)`. The desktop id is `os.path.abspath`, not `resolve()`:
  resolving would rewrite symlinks and mapped network drives in the location
  the user sees. `write_bytes` goes through `FileService.save_bytes`.
- **`MainWindowViewModel`** works on `DocumentRef`s instead of `Path`:
  - `_current_document` replaces `_current_file`;
  - `open_file`, `save_file_as` and `export_midi_file` take refs.
- **MIDI export** calls `midi_file_writer.render_midi_bytes(...)`, then
  `write_bytes`. A failed write now reports `FileService`'s wording
  ("Permission denied: …", "Failed to write file: …") like a failed save.
- **`ref_for(id)`** makes the ref for a document a picker returned
  (`FileSystemDocumentStore`: `ref_for_path`); the views reach it through
  `session.document_ref(id)`.

### States (frozen; only str/int/float/bool/None, tuples, str-Enums)

```python
class SpanKind(str, Enum): CHORD, CHORD_INVALID, DIRECTIVE, DIRECTIVE_INVALID, COMMENT
Span(start, end, kind)
MenuItem(label, value)
DocumentState(display_name, location, is_modified, title, document_id, read_only)
EditorState(font_family, font_size, read_only, notation, word_wrap)
HighlightState(text_revision, client_token, spans)
PlaybackState(status, playing_span, chord_index, bar, total_bars, playhead_offset,  # idle|playing|paused
              beat, sections, key, time_signature, tempo_clamped)       # in force at the chord sounding
TimelineSection(label, first_bar, last_bar, repeat)
ToolbarState(notation, bpm, bpm_display, bpm_editable, multiplier_pct, key, key_options,
             beats, unit, metronome, play_action,                       # play|pause|resume
             bpm_set_by, time_set_by, key_set_by)                       # "{bpm: 90}" or None
StatusState(text)
VoicingMenuState(selected, groups)
InstrumentMenuState(current, families)                                  # InstrumentFamily(name, is_current, items)
RecentDocumentsState(items)
ChordSheetState(visible, height, active_view, views, disabled_reason, zoom, zoom_supported,
                current_index, song_revision, cursor_index)
SongDefaultsState(tempo, time, key, summary, locked_reason)             # SongDefault(value, from_directive, directive_offset)
StartupState(screen)                                                    # none|quick_start|support_prompt (Android)
CapoAdviceState(active, scope, voicings, voicing, status, message,      # status: computing|ready|error
                playing, rows)                                          # CapoRow(capo, label, shapes, ease, recommended, current)
```

`HighlightState.text_revision` is the session's revision of the text the spans
were computed for; it goes up on every change to the session's copy.
`client_token` echoes the token of the `set_text` that produced that text (0
for edits the session made), so a view whose text has moved on can tell the
spans are stale. Spans are listed comments first, then chords, then directives;
kinds may overlap and the view decides which wins.

### One-off events and requests

```python
TextEdited(text_revision, start, end, replacement, undo, cursor, anchor=None)
                                    # undo: group|plain|reset; anchor: select anchor..cursor
ConfirmDiscardRequest(request_id)                                  # answer DiscardChoice: save|discard|cancel
PickDocumentRequest(request_id, mode, suggested_name)              # PickMode: open|save|export_midi
InsertDirectiveRequest(request_id, kind, existing_labels, notation, key_options)
UserError(title, message)
AudioUnavailable(message, from_click)
UnexpectedError(message, context)                                  # context: "bridge", a command, a callback
CloseApproved()
RenameFailed(name, reason, can_save_as)
```

Every programmatic edit is a splice-shaped `TextEdited`, with an undo policy:

| Edit | Splice | Undo policy |
|---|---|---|
| Transpose, capo | `(0, len, new)` | `group` (one undo step) |
| Convert notation, New | | `plain` |
| Open file | | `reset` |
| Insert | `(at, at, text)`, with the cursor placed after the inserted text (a space goes in front of a chord or directive right after a non-space) | |
| Palette snippet (Qt) | `(at, at, text)`, spaced on both sides, the value selected (`anchor`) | `group` |
| ▾ picker value (Qt) | the value's span only, the cursor after the directive | `group` |

Transpose and convert take the view's `cursor` and put it back on the same
line and column (the end of the line if it got shorter); without one, it goes
to the start of the first changed line (a selection's end, for a selection).

### Commands (primitive-typed, session thread)

```python
class AppSession:
    def __init__(self, host: Host, *, main_window_viewmodel, text_editor_viewmodel,
                 chord_sheet_viewmodel=None, worker=None, services: CoreServices | None = None)
                 # built by bootstrap.create_session(host, services, documents)
    def subscribe(self, listener: Callable[[object], None]) -> Cancellable   # replays current states first
    def start(self) -> None;  def shutdown(self) -> None
    # editing
    def set_text(self, text: str, client_token: int = 0) -> None          # debounced detection
    def insert_text(self, at: int, text: str) -> None                     # immediate detection
    def request_insert_directive(self, kind: str, at: int) -> None
    def transpose(self, semitones: int, selection: tuple[int, int] | None,
                  cursor: int | None = None) -> None
    def capo_advice_open(self, selection: tuple[int, int] | None) -> None   # Suggest Capo (CapoAdviceState)
    def capo_advice_voicing(self, voicing: str) -> None
    def capo_advice_apply(self, capo: int) -> None;  def capo_advice_close(self) -> None
    def convert_notation(self, target: str, cursor: int | None = None) -> None
    # playback / toolbar
    def play_pause(self, from_offset: int | None = None) -> None;  def stop(self) -> None
    def set_playhead(self, offset: int) -> None;  def rewind(self) -> None
    def tap_chord_at(self, offset: int) -> None
    def write_song_defaults(self) -> None
    def set_bpm(self, bpm: int) -> None;  def set_multiplier_pct(self, pct: float) -> None
    def set_key(self, key: str | None) -> None;  def set_time_signature(self, beats: int, unit: int) -> None
    def toggle_metronome(self) -> None;  def set_voicing(self, voicing: str) -> None;  def set_instrument(self, program: int) -> None
    def set_notation(self, notation: str) -> None
    def set_font(self, family: str, size: int) -> None;  def step_font_size(self, delta: int) -> None;  def reset_font_size(self) -> None
    def set_word_wrap(self, on: bool) -> None
    def set_chord_sheet_visible(self, v: bool) -> None;  def set_chord_sheet_height(self, px: int) -> None
    def set_chord_sheet_view(self, view_id: str) -> None;  def chord_sheet_zoom(self, step: int) -> None;  def chord_sheet_zoom_reset(self) -> None
    def audition(self, index: int) -> None
    # documents / app
    def new_document(self) -> None;  def open_document(self, ref: DocumentRef | None = None, read_only: bool = False) -> None
    def save(self) -> None;  def save_as(self, name: str | None = None) -> None
    def rename_document(self, name: str) -> None
    def export_midi(self) -> None;  def request_close(self) -> None
    def respond(self, request_id: int, value: object) -> None
    def apply_settings(self, changes: SettingsChanges | SettingsValues) -> None
    # lifecycle (Android)
    def pause(self) -> None                                               # only if playing
    def restore_draft(self, text: str, document: DocumentRef | None, modified: bool, read_only: bool = False) -> None
    def app_started(self, launch_kind: str, today: str, installed_on: str, can_ask_for_support: bool) -> None
    def dismiss_startup_screen(self) -> None                              # startup screen (Android)
    def save_config(self) -> None;  def report_unexpected(self, message: str, context: str | None) -> None
```

Desktop-only queries and commands (Android ignores them):
`show_quick_start_on_startup` / `set_show_quick_start_on_startup(show)` and
`licence_catalog(base_path)` (the Licences window's list, from
`services.licence_catalog`; Android reads the same kind of data in Kotlin).
The old Tk window also used `window_geometry` / `set_window_geometry(geometry)`,
`settings_model()`, `chord_identifier_model()`, `has_chord_sheet`,
`chord_sheet_model` and `report_audio_failure(reason, from_click)`; nothing
calls them since it was removed, and they are on the backlog to delete.
Queries the views call synchronously on the session thread:
`text`, `text_revision`, `chord_at(offset) -> Span | None` (the pointer over a
chord), `document_ref(id) -> DocumentRef` (a picker's answer;
`DocumentStore.ref_for`), `pending_request` (the bridge decodes `respond`'s
value by its type) and `settings_values() -> SettingsValues`; plus
`chord_sheet_buffer(height) -> bytes | None`, the one query meant for other
threads. Other commands added on the way:
`open_recent(ref)` and `insert_chord(at, chord)` (the chord identifier:
inserts `chord + " "` and says "Inserted chord: X").

The Qt desktop's (its window talks through the bridge too: the commands
QML sends are bridge commands, Android never sends them; the queries and
the geometry are direct calls): `logical_window_geometry(scale)` /
`set_logical_window_geometry(WindowGeometry, scale)` and
`logical_chord_sheet_height(scale)` / `set_logical_chord_sheet_height(height,
scale)` (logical pixels: `models/window_geometry.py`);
`set_chord_sheet_on_screen(True | False | None)` (renders apart from
`chord_sheet_visible`: True in Play, None to follow it); `volume`, `muted`,
`set_volume(v)`, `set_muted(on)`, `step_volume(steps)`;
`insert_snippet(offset, text, snap=False)`,
`replace_directive_value((start, end), value)` and `picker_at(offset)`.
On `desktop_qt`, `settings_values()` and `SettingsState.values` are
`DesktopSettingsValues`.

**Flows** (`flows.py`) are generators. They yield requests and receive answers
through `respond()`, so a request/response flow reads as plain sequential code.
Only one flow can be pending at a time: starting another closes the pending
one (so a view that lost a request can't wedge the session), and answers to
anything but the pending request id are ignored. `respond(id, None)` cancels
by convention.

**Delivery contract**
- Listeners are called only on the session thread, and only at flush points,
  never in the middle of a command.
- Every command and posted callback runs through a wrapper that flushes the
  buffered output on its outermost exit.
- If a state changes more than once before a flush, it keeps its first position
  and carries its latest value.
- Setting a state to the value it already has delivers nothing (so `start()`
  right after `subscribe()` doesn't repeat the replayed highlight).
- Events keep their order.
- Output produced outside a command raises: a missing wrapper fails loudly
  instead of delivering in the middle of something. Viewmodel observers the
  session registers are wrapped like timers.
- Payloads never contain live objects (`ChordInfo`, `Line`, `Path`,
  `RenderedSong`).

## Where the session stands

What each area does now, then what is still interim, and why.

### Final

**Text and highlighting.** The session keeps its own copy of the text and a
revision that goes up on every change; `set_text` re-detects after the
0.5 s debounce, every programmatic edit at once. Every programmatic edit
reaches the views as one `TextEdited` followed, in the same flush, by the
`HighlightState` of the new text. Spans are listed comments first, then
chords, then directives; the view decides which wins. Navigation keys no
longer trigger re-detection. Selections are `(start, end)` code-point pairs;
an empty one means none.

**Programmatic edits and undo.**
- Transpose and capo are `group` edits of the whole text, convert and New
  `plain`, Open `reset` (a reopened document with the same text still emits
  a `reset` splice, so the view's undo history starts over); inserts are
  `(at, at, text)` with the cursor after the text. Transpose and convert
  keep the cursor the view passes on its line and column; Open and New put
  it at the end.
- Transpose, convert and capo still run through `MainWindowViewModel`
  (`transpose`, `convert_text_to_*`, `insert_capo`); the session observes
  `current_text` and turns each replacement into `TextEdited(0, len, new)`
  with the undo policy of the command running at the time. Edit commands
  don't re-detect up front: convert reuses the detector's lines only when no
  detection is pending, and the label lookup parses afresh when one is.
- Programmatic edits are refused (logged, no output) while a song plays or
  is paused: `transpose`, `convert_notation`, `insert_text`, `insert_chord`,
  the answers to the insert-directive requests and `capo_advice_apply`. The
  requests are still emitted and Suggest Capo still opens and scores, so the
  dialogs open as before (`CapoAdviceState.playing` says Apply waits). `ChordTextEditor.apply_edit`
  applies `TextEdited` even while the widget is locked and clears the
  widget's modified flag afterwards, so the edit isn't sent back.
- The transpose dialog stays view-side (no request).
- Requests: `InsertDirectiveRequest(request_id, kind, existing_labels,
  notation, key_options)` (for `key`, the 15 major and 15 minor keys that have
  a signature, `toolbar.insert_key_options`; the toolbar's `key_options` are
  roots only), answered with a `{field: value}` mapping (`directives.py`
  documents the fields) or None; invalid fields at answer time emit
  `UserError` (a view can check them live with
  `directives.check_directive`, same messages). A view presents requests after the listener returns, never from
  inside it: a modal dialog there would hold back the session's output.

**Playback.** The session drives `MainWindowViewModel`'s
`start_playback(from_char_offset)`, `pause_playback`, `resume_playback`,
`stop_playback` and `on_chord_clicked`, and turns its transport flags and
progress pings into `PlaybackState`, `StatusState`, `EditorState.read_only`
and the toolbar. Status texts come from `formatting.py`; the chord count in
"Playing N chords..." is taken from the latest detection. It forwards each
`CHORD_START` ping to the strip's playhead (cleared when a song finishes,
kept after Stop). Pings that arrive after the session went idle are dropped;
each run's pings, end and render error also carry a
generation (`MainWindowViewModel`), so what an old run posted before it saw
a stop is dropped during the next run too. Shift+▶ sends
`play_pause(from_offset)` with the text cursor as a code-point offset.

**The player (Android Edit/Play redesign, 2026-10-29).** The session owns a
playhead: the start of the chord Play starts from (`PlaybackState.
playhead_offset`; `ChordSheetState.cursor_index` is that chord's first index
in the strip's song, for the edge mark). `play_pause()` without an offset
starts there (an explicit `from_offset` still wins; none at all plays from
the top). `set_playhead(offset)` snaps with `highlighting.nearest_chord`:
the valid chord covering the offset, else the nearest on its line (a tie:
the later chord), else on the nearest line with chords (a tie: the line
above, as lyrics sit under their chords), at the offset's column. While
paused it drops the paused run (so Play starts at the new playhead); while
playing it restarts playback there. `rewind()` stops and puts it on the
first chord. Edits carry it with the text (`_shift_offset`: one diffed
range per change), and the next detection re-snaps it to a chord. What
moves it on its own is a platform behaviour (`platform.TRACKS_PLAYHEAD`):
on Android, playback (it follows the chord sounding), the end of the song
(back to the first chord), chord taps (`tap_chord_at` moves it and
auditions; while playing it jumps there instead), taps on a strip chord
(`audition(index)` does the same when the strip's chord is still the text's
chord at the same span; otherwise it only auditions), and a default on the
first chord whenever the song has chords (an opened document starts
there). The Qt desktop (`platform="desktop_qt"`) has all of them too, with
the desktop's status texts: a clicked chord sounds and takes the playhead,
▶ plays from it and Shift+▶ (`from_offset`) from the cursor, and only a
cursor start says "from cursor". The `"desktop"` platform is what the
removed Tk window used: no playhead, so Play, Shift+Play, click and status
behave as they did before the playhead; no front end passes it now, but the
core and its tests still carry it (`platform.py`), and `desktop_qt` falls
back to its texts where it has none of its own. Android's
status line is position + activity (`formatting.position_status`): "Bar
6/24 · Playing Em", "Bar 6/24 · Paused", "Starting…" before the first
chord, and while idle the playhead's bar ("Bar 6/24", from the strip's song
or the last run's pings over the same text) or "Ready"; Android counts bars
from the top of the song even when playback started later
(`RenderedChord.song_bar`, carried in the pings as
`PlaybackEventArgs.song_bar`), and so does the Qt desktop, in
`PlaybackState.bar` and its "Bar n/N" status; the `"desktop"` platform keeps
the old rebased bars (`platform.COUNTS_SONG_BARS`). `PlaybackState.beat` is the
beat of that bar the chord started on (`RenderedChord.song_beat` or `beat`).

**Timeline.** `PlaybackState.sections` is the song's timeline for a
scrubber (`session/timeline.py`): the strip's rendered song's `section` and
`loop` markers (`SongMarker.label`) placed on the bar of their first chord,
tiling bars 1 to `total_bars`, with an unlabelled section for the bars
before the first label and `repeat` on every pass after a loop's first. The
session recomputes it when the strip's song changes and publishes it only
when it changed; it isn't cleared when playback stops.

**Defaults vs. the song's values** (Tibi, 2026-10-30). The Settings
defaults (tempo, time signature, key) live in the config and only Settings
writes them. The viewmodel's `bpm`, `key` and time signature are the current
document's: the defaults until changed from the toolbar or Playback settings, for
that document only; `new_file`/`open_file` reload them from the config
(`MainWindowViewModel.load_defaults`, the key respelled in the current
notation) and nothing copies an opened song's directives into them (or into
the config). A value the song sets with a directive before its first chord is
the song's: `set_bpm`, `set_time_signature` and `set_key` ignore it
(`song_defaults.setting_directives`). Playback, MIDI export and Suggest Capo
start from the document's values (`start_song_playback(initial_bpm=,
initial_time_sig=)`), and the config saves (desktop exit, Android
`app_background`) never carry them. A Settings change shows from the next
New/Open (`general_changed` is still ignored by `apply_settings`).

**Song defaults.** `SongDefaultsState(tempo, time, key, summary)`: each value
is what the song starts with. A valid directive before the first chord sets
it (`from_directive`, `directive_offset` = the first such directive; relative
tempo directives apply to the document's tempo); otherwise it is the
document's value. A mid-song change doesn't count: the value stays the
starting one. The key is `""` when neither sets one. `summary` is the pill text,
`"90 · 3/4 · G"`. Republished after every detection and toolbar change,
and when playback starts, pauses, resumes or stops: `locked_reason` says why
the values and the write wait while a song plays (None when idle or paused).
`write_song_defaults()` inserts the missing directives as one line at the
top, one `group` edit, highlighted at once (no `{key}` without a key).
While paused it first stops the paused run (its offsets go stale) with the
playhead on the paused chord, and the edit carries it along, so Play starts
there.

**Changes while paused.** The song is rendered when Play starts it, with the
voicing, tempo, key and time signature of that moment (`_RENDER_INPUTS`). A
change to any of them is refused while a song plays and allowed while
paused: the observer marks the paused run stale (`_render_stale`), and the
next `play_pause()` stops it and starts again from the paused chord instead
of resuming the old event buffer. A stop clears the mark.

**Rename.** `rename_document(name)`: the name is typed without the
extension; the document's own is kept (a name already ending in it isn't
doubled). `DocumentStore.rename` renames in place (desktop: `os.rename` in
the same folder, refusing to replace another file; Android: Kotlin's
`DocumentsContract.renameDocument`); the viewmodel's `document_renamed(ref)`
switches the open document without reading or writing, then the recent list,
`DocumentState` and the status ("Renamed to X") follow. An invalid name
(empty, `/` or `\`, control characters, `.`/`..`, over 255 bytes) or a refusal
emits `RenameFailed(name, reason, can_save_as)`: `can_save_as` is True when
the storage refused (no rename support, a name in use), so the view offers
`save_as(name)`, which suggests that name with the extension. An untitled
document only takes the name (`DocumentState.display_name`, the Save
suggestion) until its first save; New, Open and a restored draft forget it.

**Capo in Insert.** `request_insert_directive("capo", at)` answers with
`{"capo": "N"}`, 0-12 (`directives.check_directive`, same message live and
at answer time). The Insert Capo dialog's Suggest opens Suggest Capo.

**Suggest Capo.** A stateful dialog, like the voicings editor, not a
request: `capo_advice_open(selection)` publishes `CapoAdviceState` active
and `computing` and scores every capo 0..7 on the worker
(`MainWindowViewModel.capo_job`: render with a guitar picker on the chosen
voicing, then `capo_advisor.rank_capos`, `ease_of` and `capo_shapes`). The
rows come back ranked, the recommended one first: the top scorer when it
beats capo 0 by `max(CAPO_MIN_GAIN * chords, CAPO_MIN_TOTAL_GAIN)`, else
no capo; the rest by score, ties to the lower capo. A row's `label` is its
words ("Capo 3 · G D Em C · Easier"); `current` marks the capo in force
where it would go (`MainWindowViewModel.current_capo`; no capo when there
is none). `capo_advice_voicing` scores again; `capo_advice_apply(capo)`
inserts or rewrites the directive (`insert_capo`, one `group` edit), or
changes nothing for the capo already in force, then closes; it scores
again instead when the text changed since. `capo_advice_close` cancels.
The session publishes the inactive state at construction (with or without
services) and closes the dialog whenever the document is replaced.

**Audio failures.** `AudioUnavailable.message` is the full user-facing text.
Play, chord taps, chord-sheet auditions and the chord identifier all go
through the session's one `AudioFailurePolicy` (Play reports every time,
click-to-hear once per session); playback render failures are `UserError`.

**Toolbar.** `ToolbarState(notation, bpm, bpm_display, bpm_editable,
multiplier_pct, key, key_options, beats, unit, metronome, play_action,
bpm_set_by, time_set_by, key_set_by)`. `bpm`, `beats`/`unit` and `key` are
what the song starts with (the same values as `SongDefaultsState`);
`*_set_by` is the directive that sets one, as written in the song (`"{bpm:
90}"`), or None. A view greys a set value out with the tooltip "Set by {bpm: 90} in
the song". `bpm_display` is the effective tempo of the chord sounding while
a song plays (it follows mid-song changes; after a stop it is `bpm` again),
`bpm_editable` is `status != playing` and no `{bpm}` sets the start,
`play_action` drives the Play/Pause icon and tooltip. `key` is the first key
option when none is set. The toolbar is republished after every detection. `set_bpm`
is ignored while playing (so are `set_key` and `set_time_signature`; the
views disable those controls then); `set_bpm` and `set_multiplier_pct` clamp
and snap with the scrubber's own `ScrubScale`. The notation observer
re-detects, respells the key (`toolbar.convert_key`) and publishes the new
key list. A view only maps `ToolbarState`; controls send commands
from user actions, never from property bindings.

**Settings, fonts and menus.** `apply_settings(changes)` applies a new font
and word wrap, rebuilds the Voicing menu and re-applies the voicing in use when it was
renamed, removed or possibly edited in place; `general_changed` and
`audio_changed` are ignored on purpose (defaults for the next start). The
Settings dialog keeps `SettingsViewModel` as its own model, now handed out
by `session.settings_model()`; its `commit()` writes the config and the
window passes the changes to `apply_settings`. `EditorState(font_family,
font_size, read_only, notation, word_wrap)`; `set_font`, `step_font_size` (clamped
6-72), `reset_font_size`, `set_word_wrap` (View > Word Wrap; config key
`word_wrap`, default off: the editors scroll sideways so chord lines stay
over their lyrics; Android sets it through `SettingsValues.word_wrap`). `VoicingMenuState(selected, groups)` (built by
`formatting.voicing_menu_groups`; `set_voicing` only takes those values);
`InstrumentMenuState(current, families)` (the General MIDI table is
`formatting.INSTRUMENT_FAMILIES`).

**Chord sheet.** The feed starts at `start()` (seeding the strip once, since
feeding arms its debounce timer), then re-feeds `set_song` when the detected
lines, the key or the voicing change. `ChordSheetState(visible, height,
active_view, views, disabled_reason, zoom, zoom_supported, current_index,
song_revision)`; commands `set_chord_sheet_visible`, `set_chord_sheet_height`,
`set_chord_sheet_view`, `chord_sheet_zoom(step)`, `chord_sheet_zoom_reset()`,
`audition(index)`. The
window uses the state for the pane, the View menu check and the sash height.

**Documents.** `new_document()`, `open_document(ref=None)`,
`open_recent(ref)`, `save()`, `save_as()`, `export_midi()`,
`request_close()`, each a `FlowRunner` flow. `ConfirmDiscardRequest`
(answered `save|discard|cancel`), `PickDocumentRequest(mode,
suggested_name)` answered with a `DocumentRef` or None (anything else raises
`TypeError`). The flows contain no path logic: the desktop view answers with
`session.document_ref(picked path)`. Semantics as before: unsaved changes
ask first; "save" on a never-saved document goes through Save As; a failed
or cancelled save stops the New/Open/close. Save As suggests the document's
name (`Untitled.txt`), Export MIDI `<stem>.mid`. New and Open start the
document from the Settings defaults; the song's own directives show on the
toolbar through `ToolbarState`, not by changing any value. `request_close` emits
`CloseApproved()`; the window saves its geometry, stops playback, cancels its
subscription and closes; the application then shuts the session and services down
and saves the config. Failures are `UserError("Error", "<action>:\n<location>
\n\n<reason>")`. `DocumentState(display_name, location, is_modified,
title)`; `RecentDocumentsState(items)` has one owner, the flows'
`add_recent` after a successful open or save.

**Background work.** `BackgroundWorker(host)` (`workers.py`) runs
jobs one at a time on a daemon thread started by the first `submit`;
`submit(fn, on_done)` returns a `Job` whose `cancel()` drops the outcome
(skipping the job if it hasn't started). With `pass_abort=True` the job is
called as `fn(should_abort)`; `should_abort()` turns True once the job is
cancelled or the worker shut down, so a render or search stops early
(`RenderAborted`). The `Outcome(value, error)` comes
back through `host.post`; the session wraps `on_done` like a timer.
`shutdown()` (from `AppSession.shutdown`) drops outcomes still on their way
and doesn't wait for a running job; `wait_idle()` is for tests. Jobs only use
what they captured on the session thread: `MainWindowViewModel.capo_job` and
`midi_export_job` snapshot the text, notation, key, tempo and time signature
(passed to `PlaybackService.render_song` as `initial_bpm`/`initial_time_sig`),
and the export renders with its own note picker
(`PlaybackService.create_note_picker`), not the shared one a playback render
may be using.
- Suggest Capo: `CapoAdviceState.status` is `computing` while it is
  scored; the job gets `should_abort`, passed to `render_song` and
  `rank_capos`, so a voicing switch, a close or a newer open stops the old
  scoring early. The rows show when they arrive, whatever happened to the
  text meanwhile; Apply scores again if the text revision moved on, rather
  than insert into a song the rows weren't computed for. A render failure is
  logged and shown in the dialog (`status="error"`, "Couldn't score the
  capos: <error>").
- Export MIDI: the song as it is when the file is picked is rendered on the
  worker ("Exporting MIDI: <location>..."); the bytes are written on the
  session thread when it arrives (`finish_midi_export`), so failures keep
  their wording and closing mid-render leaves no half-written file (the
  export is dropped). On failure the status returns to "Ready".
- `PlaybackService.stop_playback` doesn't join the render thread (it waited
  up to 2 s). `_start_lock` orders the render thread's "check cancel → wire
  the player → `player.start_playback()`" against stop's "cancel and take the
  event buffer"; stop then calls `player.stop_playback()`. A stopped render
  never starts the player, and one it did start is stopped; a failed render
  reports under the same lock, so a stopped one reports nothing. `cleanup()`
  cancels a render in flight the same way. A new render waits, on its own
  thread, for the previous one to finish before it resets and uses
  playback's note picker.

**The Qt window.** `chordnotepad_desktop` builds the core the same way
(`QtApplication.start`: services, logging and the error presenter, audio,
then `create_session(..., platform=DESKTOP_QT)`) and puts a `SessionStore`
(`session_store.py`) between the session and QML. The store sits on the same
`SessionBridge` Android uses, so QML gets the states as property maps, the
events and requests as signals, and sends the same JSON-shaped commands; a
short list of direct calls answers what must come back at once. Every other
model in the package (`editor_bridge`, `player_bar`, `chord_sheet`,
`sidebars`, `identifier`, `settings_window`, `dialogs`, `chrome`) wraps the
store for one part of the window and keeps view work only: the painted chord
sheet, offsets, geometry, the device pixel ratio. The `DESKTOP_QT` platform
adds the playhead, song-counted bars and its own Quick Start and help texts;
see "Per-platform texts" below. `tests/qt/` runs the window offscreen.

**Construction.** `bootstrap.build_core_services(appdata,
dispatch, paths=..., player=None, audio_options=None)` is the UI-free half of the old
`Application.on_initialize_services`: it creates the data directories,
loads the config and builds `CoreServices(appdata, config, song_parser,
playback, files, paths)`. `create_session(host, services, documents, dispatch=None,
chord_sheet=True)` builds `MainWindowViewModel`, `TextEditorViewModel`, the
chord-sheet strip (imported only when asked for) and the `AppSession`, whose
optional `services` argument replaced `config_service`,
`song_parser_service` and `playback_service`. The desktop `Application`
uses both (passing itself as `dispatch`, as before) and keeps only the
desktop-only services (resources, logging setup) and the document store.
`AppSession.shutdown` also drops whatever still observes its viewmodels,
which `Application` used to do.
`AppDataService(root=...)` takes the data directory from the host (Android:
`filesDir`; the same layout the `XDG_*` shim gave). Config writes are atomic
(temp file, `fsync`, `os.replace`).

**Where the app's files are.** `paths` is an `AppPaths`
(`core/chordnotepad/app_paths.py`: the root, VERSION, `resources/`, the built
help, the bundled SoundFont, the Windows dev DLL folder). The front end resolves it once at its entry point
and passes it down; no core module walks up from its own `__file__`
(`tests/test_app_paths.py` scans for that). The desktop's resolver is
`resolve_desktop_paths` (in `chordnotepad_desktop`): the PyInstaller bundle
(`sys._MEIPASS`), the Flatpak (`/app/share/chord-notepad`), the snap
(`$SNAP/share/chord-notepad`), else the checkout. `chordnotepad_desktop/launcher.py` calls it and, through `main.run`,
hands it to `QtApplication(paths)`, which passes it to `build_core_services` and
`ResourceService`. The Android host passes its own (no bundled files; the
SoundFont path comes in `audio_options`). The default, `NO_BUNDLED_FILES`,
is for tests that bring their own player.

**The bridge.** `session/bridge.py`:
- `encode(dto) -> (type_name, json)` for every state, event and request:
  field names as in the dataclasses, enums as values, tuples as arrays,
  nested DTOs as objects. Anything else raises `TypeError`. `EventRecorder`
  encodes every item it records and the test suite fails a test that
  recorded something that doesn't encode, so every golden flow is also a
  DTO-purity test.
- `dispatch(session, command, args_json)` decodes the arguments by the
  command's declared types (`SESSION_COMMANDS`, `HOST_COMMANDS`): ints
  (never bools), floats, strings, bools, `[start, end]` selections,
  `DocumentRef` and `SettingsValues` objects (exact field sets), `|null`.
  `respond`'s value is decoded by the pending request's type (picker:
  `DocumentRef`/null; unsaved changes: `save|discard|cancel`/null;
  directive: an object of strings/null). An unknown command or
  argument, a missing one or a wrong type emits
  `UnexpectedError(context="bridge")`; a command that raises emits
  `UnexpectedError(context=<command>)`. Nothing reaches the session thread
  as an exception. Parameters with a default may be left out.
- Lifecycle: `pause` and `restore_draft` are session commands;
  `app_background` (pause if playing, save the config) and `app_foreground`
  (reopens the audio output) run on them; `app_background` also releases it
  (`suspend_audio`).
- `SessionBridge(host, session, sink)` subscribes `sink(type_name, json)`
  and posts every `submit(command, args_json)` to the session thread.
  `ErrorEvents` is the Android `session.errors` handler: it posts an
  `UnexpectedError`, at most once per message and context per 30 s and five
  per minute.
- `python -m chordnotepad.session.bridge --schema` dumps types, enums, commands with
  their parameter types and the answer types; the committed
  `android/bridge_schema.json` is checked against it in both test suites.
- Settings over the bridge: `settings_values()` reads a `SettingsValues`
  (the General and Playback settings that carry over to Android), and
  `apply_settings(SettingsValues)` range-checks it and commits it through a
  `SettingsViewModel`, so the config writes and change flags are the
  dialog's. The desktop path (`SettingsChanges`) is unchanged.
- The Android host (`android/app/src/main/python/chordnotepad_android/
  host.py`) wires these: `ThreadedHost`, `AppDataService(root=filesDir)`,
  `build_core_services`, an `AndroidDocumentStore` over Kotlin's SAF store,
  `create_session` on the session thread, `SessionBridge`, `ErrorEvents`.

### Still interim, and why

- **`MainWindowViewModel` still owns the values.** It holds the document
  text, the modified flag and the open document, does the document I/O,
  owns the toolbar values and their config writes, the font, the notation
  preference, the window preferences, and runs playback (including the
  generation token). The session observes 16 of its properties and keeps
  its own text copy in step. Moving the values into the session would
  touch about 15 test files for no behaviour change; the viewmodel is now
  reachable only through the session, so this can happen any time.
- **The chord sheet's painting.** The old Tk panel painted from the strip
  (`session.chord_sheet_model`, live renderers and `RenderedSong`); nothing
  uses that path now. Both Qt and Android get the drawing as bytes
  instead: `AppSession.chord_sheet_buffer(height)` packs the active view
  (`chord_sheet.pack.pack_view`) from a snapshot the session thread
  replaces with every `ChordSheetState`, on the caller's thread, so Kotlin
  calls it directly through `SessionHandle.chord_sheet_buffer` without
  waiting for the session thread. The renderers are shared with the strip;
  they are treated as pure (as `pack_view` requires), which nothing checks.
- **Dialog-scoped screens are held by the session.** Qt and Android both
  use them (the old Tk dialogs held live viewmodels through
  `settings_model()` and `chord_identifier_model()`, which nothing calls
  now):
  - the chord identifier is a session-owned `ChordIdentifierViewModel`
    behind `identifier_*` / `play_note` / `play_identified_chord` commands
    and an `IdentifierState`; the note helpers (`note_to_midi`,
    `bass_note`, `parse_notes`) are module functions.
  - a Settings screen is a `SettingsEdit` (`session/settings_edit.py`): a
    `SettingsViewModel` working copy plus the voicing in the form, edited
    through `settings_forms.voicing_form`, saved with the gate
    (`validate_all`, then `commit`, then the same apply as
    `apply_settings`). One edit at a time; begin drops an older one. The Qt
    window keeps its edit until **Save** or **Discard**.
  - `SettingsState` is re-read from the config at the end of every
    outermost command (`Emitter.set_before_flush`), because several
    viewmodels write the config and none notifies; an unchanged value is
    dropped, so this costs nine attribute reads per command.
  - these three states are published only by a session built with
    services (Android always is; the headless test sessions without
    services keep their old replay).
  - `VoicingEditorState` and the editor schema carry plain JSON in fields
    typed `Any` (schema type `json`): the voicing form is a dict keyed by
    field id, and mirroring every field as a DTO would duplicate the schema.
- **Per-platform texts.** `create_session(platform=...)` (`desktop` by
  default, `android` from the Android host, `desktop_qt` from the Qt window) picks the wording of the few
  strings that name a gesture or a menu: the click-to-hear audio message,
  the chord sheet's disabled-tab reason, the voicing editor's name help and
  the Quick Start pages (`session/quick_start.py`). The `desktop` variant is
  the text of the removed Tk window; tests pin it
  (`tests/fixtures/quick_start_desktop.json`). `desktop_qt` falls back to
  the desktop text, so only texts that name a menu or control the Qt window
  words differently have a Qt variant; its Quick Start picture is
  `resources/quickstart/chord_sheet_qt.png`.
- **A clicked chord sounds as the chord sheet shows it.** With the
  `click_plays_chart_voicing` setting on (config, `SettingsValues`; on by
  default and for a config without the key), `tap_chord_at` plays the
  chord sheet's notes for the chord (`ChordSheetViewModel.audition`, rolled
  for a Shift+click), which are the ones Play sounds
  (`_chart_index_of_tap`). Only from a render of the text as it is now:
  detection is up to date (`_detected_text == _text`), the sheet's render is
  of the latest song it was fed (`render_is_current`: its generation, so a
  new text, key, voicing or time signature makes it stale until the next
  render lands, and a hidden sheet stays stale), and the strip chord has the
  tapped chord's span and name. Of a chord a loop repeats it takes the
  occurrence in the pass a paused (Tk desktop: playing) song is on, else the
  first; "the same pass" means the strip never goes back in the text between
  the two (`_same_pass`). Where the playhead follows taps, the tap seeks to
  that pass, so the sheet's cursor is on the card that sounds. Each tap logs
  (debug) which way it went.
- **Otherwise click-to-hear has its own picker.** With the setting off, or
  without such a render (none yet, stale, the chord not in it),
  `play_chord_immediate` voices on the session thread with
  `PlaybackService._click_picker`, built on the first click and dropped by
  `set_voicing`, never with the picker a playback render uses on the
  RenderThread. Those clicks voice-lead from one to the next, across
  playback. On Android the session thread is not the UI thread, so a slow
  voicing delays the next command, not the UI.
- **Audio across the app lifecycle.** `app_background` pauses, saves the
  config, then calls `suspend_audio`, which deletes only the FluidSynth audio
  driver (the synth, SoundFont, program and sequencer stay; the sequencer
  runs on the synth's sample clock, so a paused song resumes where it was).
  It is refused while a song plays or renders. `app_foreground` calls
  `resume_audio`; `PlaybackService._require_audio` also reopens lazily, so a
  play/tap/audition after a background without a foreground still works, and
  a failed reopen raises `AudioInitializationError` ("The audio output could
  not be reopened."). Whether the stream should close at all is still to be
  measured on the phone.

## Threading contract

1. **One session thread owns all session state, viewmodel state and config
   writes.** `queue_ui_callback` is `host.post`.
2. **Background threads never mutate state.** This covers the render thread,
   the playback loop, the chord-sheet job thread and `BackgroundWorker`. They
   only `host.post`, and they only read inputs that can't change.
3. **The chord sheet's debounce uses `host.call_later`.** Given a host, a
   `HostScheduler` adapter replaces `_TimerScheduler` as the default, and
   `marshal` defaults to `host.post` (`_TimerScheduler` stays only for a
   viewmodel built without a host). The timer only dispatches the job; the
   render still runs on the executor's thread.
4. **The session thread never renders.**
   - MIDI export and capo suggestion run on `BackgroundWorker`.
   - `PlaybackService.stop_playback` no longer joins the render thread. A start
     lock orders "check cancel → `player.start_playback()`" against
     "`cancel.set()` → `player.stop`".
5. **Qt:** the GUI thread is the session thread.
6. **Android:**
   - A `ThreadedHost` thread is the session thread.
   - Kotlin calls `bridge.submit(name, json)` from a non-Main dispatcher, and
     that call only enqueues.
   - Python delivers output through the Kotlin `EventSink` on the session
     thread.
   - The Android main thread never calls Python.
7. **Re-entrancy**
   - Listeners may call commands; the resulting output is delivered after the
     output already being delivered.
   - Nothing on the session thread may wait for work that needs the session
     thread.
   - Kotlin `DocumentStore`/`EventSink` callbacks never wait on the Python
     dispatcher.

## Errors

- **`session/errors.py`** provides `set_handler(fn)` and
  `report_from_any_thread(exc_info, context)`. With no handler installed, it
  logs. Throttling is the handler's job: the Qt presenter
  (`chordnotepad_desktop/error_presenter.py`) throttles its dialogs, and the
  Android handler throttles its events.
- **`Observable.notify`** reports through it.
- **Android** installs a handler that emits `UnexpectedError`, throttled.
- **Expected failures are events:** `last_error` becomes `UserError`, and
  `AudioInitializationError` becomes `AudioUnavailable`. The session owns the
  "report click failures once per session" policy (`AudioFailurePolicy`;
  playback render failures are `UserError`).

## Tests

- **Fixture:** `ManualHost`, `InMemoryDocumentStore`, the real
  `SongParserService`, and the real `PlaybackService` with a `FakePlayer`.
- **`EventRecorder`** golden flows:
  - type text → highlight spans after 0.5 s;
  - play → progress → finished;
  - transpose → re-detect → key shift;
  - open a file with directives → toolbar state;
  - unsaved changes → save → cancel.
- **Bridge flows** (`tests/test_session_bridge.py`, `tests/test_android_host.py`):
  a `ThreadedHost` session built by `bootstrap`, driven only through
  `submit(command, json)` and read only as `(type_name, json)`: typing →
  `HighlightState`; play → `PlaybackState` sequence → idle; open through a
  `PickDocumentRequest` answered with a ref object; transpose → `TextEdited`;
  restore draft; lifecycle commands; bad input → `UnexpectedError`.
- **Guard tests:**
  - `session` imports without tkinter, Pillow, jeepney or PySide6;
  - DTO purity (every `EventRecorder` item, and every output type emitted
    over the bridge at least once);
  - the committed bridge schema matches the code.

# AppSession: the shared application layer

The shared layer both the Tk UI and the Android UI sit on. "Where the session
stands" says what each area does and what is still interim, and why. The
wire format Kotlin sees is in `docs/ANDROID.md`, "Bridge contract".

## Why

The viewmodels in `src/viewmodels/` don't import Tk. The wiring *between* them
does live in the Tk window, `src/ui/main_window.py`. That includes:
- the chord-sheet feed and the playback-event fan-out;
- re-detection after transpose;
- applying settings and the notation toggle;
- the file flows and the status text.

A second UI (Kotlin/Compose on Android, later SwiftUI) would have to copy all of
it. AppSession moves that wiring into a Tk-free, host-agnostic core layer.
**Both** the Tk UI and the mobile UIs become thin views over it, so the wiring
exists once.

## Decisions

- **The existing viewmodels stay as internal components.** AppSession composes
  them and is their only observer. They keep the domain logic, and their tests
  stay valid.
- **One outbound stream of frozen DTOs.**
  - *States* are coalesced: latest value wins.
  - *Events* are delivered in order.
  - Dialogs are request/response pairs.
- **The host owns the session thread.**
  - Tk: the main thread is the session thread.
  - Android: a Python-owned `ThreadedHost` thread.
- **Offsets are Unicode code points everywhere in Python.** Conversion to UTF-16
  happens only in the Kotlin `OffsetMapper`.

## Responsibilities

**AppSession (`src/session/`)**
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

**Views (Tk now, Compose later)**
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
src/session/
  host.py          Host protocol, Cancellable, HostDispatch (queue_ui_callback shim)
  threaded_host.py ThreadedHost (queue + timer heap; Android/headless)
  settings.py      SettingsValues: the settings as plain values (bridge views)
  testing.py       ManualHost (virtual clock), InMemoryDocumentStore, FakePlayer, EventRecorder
  errors.py        Tk-free unexpected-error routing (handler registry; the handler throttles)
  documents.py     DocumentRef, DocumentStore, FileSystemDocumentStore
  state.py         frozen state DTOs
  events.py        one-off event + request DTOs
  audio_policy.py  AudioFailurePolicy: Play reports every time, clicks once per session
  emitter.py       Emitter: output buffering, coalescing and flush (the delivery contract)
  formatting.py    titles, status strings, voicing/instrument menu models
  toolbar.py       key list + key respelling, BPM/multiplier parse+format, ScrubScale (clamp/snap/quantize)
  directives.py    Insert-menu directives: field validation + messages, directive text, labels, loop choices
  support.py       the Android support prompt's policy (should_show_support_prompt, NAG_DELAY_DAYS), LaunchKind
  highlighting.py  find_comments, compute_spans(lines, text), chord_at(lines, offset),
                   nearest_chord(lines, text, offset) (the playhead's snap), first_chord
  song_defaults.py song_defaults(lines, bpm, time, key) -> SongDefaultsState; missing_directives
  flows.py         generator-based request/response FlowRunner
  workers.py       BackgroundWorker (single-thread executor, results via host.post)
  bootstrap.py     CoreServices, build_core_services(appdata, dispatch, player=, audio_options=),
                   create_session(host, services, documents, chord_sheet=)
  bridge.py        encode(dto) -> (type_name, json); decode_args/dispatch; SessionBridge;
                   ErrorEvents (throttled UnexpectedError); schema dump for Kotlin
  session.py       AppSession
src/ui/tk_host.py  TkHost (the queue drain that used to live in application.py)
src/utils/paths.py display_path / is_document_portal_path (moved from utils/file_dialogs.py)
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
- **`TkHost(root=None)`**
  - `post` puts the callback on a queue, which the existing 100 ms `after()`
    drain runs.
  - `call_later` wraps `root.after` and returns a handle that calls
    `after_cancel`.
  - The host is built before the window (services and viewmodels come
    first), so the root is attached later with `attach(root)`; `start()` and
    `stop()` run the drain. Posts made before `start()` wait in the queue.
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
EditorState(font_family, font_size, read_only, notation)
HighlightState(text_revision, client_token, spans)
PlaybackState(status, playing_span, chord_index, bar, total_bars, playhead_offset)  # idle|playing|paused
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
```

`HighlightState.text_revision` is the session's revision of the text the spans
were computed for; it goes up on every change to the session's copy.
`client_token` echoes the token of the `set_text` that produced that text (0
for edits the session made), so a view whose text has moved on can tell the
spans are stale. Spans are listed comments first, then chords, then directives;
kinds may overlap and the view decides which wins (Tk: tag priority).

### One-off events and requests

```python
TextEdited(text_revision, start, end, replacement, undo, cursor)   # undo: group|plain|reset
ConfirmDiscardRequest(request_id)                                  # answer DiscardChoice: save|discard|cancel
PickDocumentRequest(request_id, mode, suggested_name)              # PickMode: open|save|export_midi
CapoChoiceRequest(request_id, options, default)
InsertDirectiveRequest(request_id, kind, existing_labels, notation)
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
| Insert | `(at, at, text)`, with the cursor placed after the inserted text | |

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
    def transpose(self, semitones: int, selection: tuple[int, int] | None) -> None
    def request_suggest_capo(self, selection: tuple[int, int] | None) -> None
    def convert_notation(self, target: str) -> None
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
    def set_chord_sheet_visible(self, v: bool) -> None;  def set_chord_sheet_height(self, px: int) -> None
    def set_chord_sheet_view(self, view_id: str) -> None;  def chord_sheet_zoom(self, step: int) -> None;  def audition(self, index: int) -> None
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

Desktop-only queries and commands (the Tk window's needs; Android ignores
them): `window_geometry` / `set_window_geometry(geometry)`,
`show_quick_start_on_startup` / `set_show_quick_start_on_startup(show)`,
`settings_model()` and `chord_identifier_model()` (new dialog-scoped models),
`licence_catalog(base_path)` (the Licences window's list, from
`services.licence_catalog`; Android reads the same kind of data in Kotlin),
`has_chord_sheet` and `chord_sheet_model` (the panel's painting read; see
"Still interim"). Queries the views call synchronously on the session thread:
`text`, `text_revision`, `chord_at(offset) -> Span | None` (the Tk hand
cursor), `document_ref(id) -> DocumentRef` (a picker's answer;
`DocumentStore.ref_for`), `pending_request` (the bridge decodes `respond`'s
value by its type) and `settings_values() -> SettingsValues`; plus
`chord_sheet_buffer(height) -> bytes | None`, the one query meant for other
threads. Other commands added on the way:
`open_recent(ref)`, `insert_chord(at, chord)` (the chord identifier: inserts
`chord + " "` and says "Inserted chord: X") and
`report_audio_failure(reason, from_click)`.

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
  `(at, at, text)` with the cursor after the text. Whole-text edits put the
  cursor at the end, where Tk's delete+insert left it before.
- Transpose, convert and capo still run through `MainWindowViewModel`
  (`transpose`, `convert_text_to_*`, `insert_capo`); the session observes
  `current_text` and turns each replacement into `TextEdited(0, len, new)`
  with the undo policy of the command running at the time. Edit commands
  don't re-detect up front: convert reuses the detector's lines only when no
  detection is pending, and the label lookup parses afresh when one is.
- Programmatic edits are refused (logged, no output) while a song plays or
  is paused: `transpose`, `convert_notation`, `insert_text`, `insert_chord`
  and the answers to the insert-directive and capo requests. The requests are
  still emitted, so the dialogs open as before. `ChordTextEditor.apply_edit`
  applies `TextEdited` even while the widget is locked and clears the
  widget's modified flag afterwards, so the edit isn't sent back.
- The transpose dialog stays view-side (no request). Before any edit command
  the Tk view sends the widget's text with `set_text`.
- Requests: `InsertDirectiveRequest(request_id, kind, existing_labels,
  notation)`, answered with a `{field: value}` mapping (`directives.py`
  documents the fields) or None; invalid fields at answer time emit
  `UserError` (the Tk dialogs check them live with
  `directives.check_directive`, same messages). `CapoChoiceRequest(request_id,
  options, default)` with `MenuItem(label, value)` options, answered with a
  value or None. The Tk window presents requests from `after_idle`, never from
  inside the listener: a modal dialog there would hold back the session's
  output.

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
a stop is dropped during the next run too. The Tk Play button sends
`set_text`, then `play_pause(from_offset)` with the Shift+click cursor as a
code-point offset (`ChordTextEditor.offset_of`); the old `"line.col"` API
(`start_playback_from_cursor`) is gone.

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
auditions; while playing it jumps there instead), and a default on the
first chord whenever the song has chords (an opened document starts
there). The desktop has none of these, so its Play, Shift+Play, click and
status behave as before; it would only get a playhead from an explicit
`set_playhead`/`rewind`, which the Tk window doesn't send yet. Android's
status line is position + activity (`formatting.position_status`): "Bar
6/24 · Playing Em", "Bar 6/24 · Paused", "Starting…" before the first
chord, and while idle the playhead's bar ("Bar 6/24", from the strip's song
or the last run's pings over the same text) or "Ready"; Android counts bars
from the top of the song even when playback started later
(`RenderedChord.song_bar`, carried in the pings as
`PlaybackEventArgs.song_bar`), the desktop keeps its rebased bars.

**Defaults vs. the song's values** (Tibi, 2026-10-30). The Settings
defaults (tempo, time signature, key) live in the config and only Settings
writes them. The viewmodel's `bpm`, `key` and time signature are the current
document's: the defaults until changed from the toolbar or Song defaults, for
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
and when playback starts or stops: `locked_reason` says why the tempo and
the write wait while a song plays or is paused (None when idle).
`write_song_defaults()` inserts the missing directives as one line at the
top, one `group` edit, highlighted at once (no `{key}` without a key).

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
at answer time). Suggest Capo is unchanged.

**Audio failures.** `AudioUnavailable.message` is the full user-facing text.
Play, chord taps, chord-sheet auditions and the chord identifier all go
through the session's one `AudioFailurePolicy` (Play reports every time,
click-to-hear once per session); playback render failures are `UserError`.
The Tk window parents that dialog to the focused toplevel.

**Toolbar.** `ToolbarState(notation, bpm, bpm_display, bpm_editable,
multiplier_pct, key, key_options, beats, unit, metronome, play_action,
bpm_set_by, time_set_by, key_set_by)`. `bpm`, `beats`/`unit` and `key` are
what the song starts with (the same values as `SongDefaultsState`);
`*_set_by` is the directive that sets one, as written in the song (`"{bpm:
90}"`), or None. The Tk toolbar greys a set value out (key and time
disabled, the BPM scrubber read-only) with the tooltip "Set by {bpm: 90} in
the song". `bpm_display` is the effective tempo of the chord sounding while
a song plays (it follows mid-song changes; after a stop it is `bpm` again),
`bpm_editable` is `status == idle` and no `{bpm}` sets the start,
`play_action` drives the Play/Pause icon and tooltip. `key` is the first key
option when none is set. The toolbar is republished after every detection. `set_bpm`
is ignored while playing or paused; `set_bpm` and `set_multiplier_pct` clamp
and snap with the scrubber's own `ScrubScale`. The notation observer
re-detects, respells the key (`toolbar.convert_key`) and publishes the new
key list. The Tk toolbar only maps `ToolbarState`; widgets send commands
from user actions, never from variable traces.

**Settings, fonts and menus.** `apply_settings(changes)` applies a new font,
rebuilds the Voicing menu and re-applies the voicing in use when it was
renamed, removed or possibly edited in place; `general_changed` and
`audio_changed` are ignored on purpose (defaults for the next start). The
Settings dialog keeps `SettingsViewModel` as its own model, now handed out
by `session.settings_model()`; its `commit()` writes the config and the
window passes the changes to `apply_settings`. `EditorState(font_family,
font_size, read_only, notation)`; `set_font`, `step_font_size` (clamped
6-72), `reset_font_size`. `VoicingMenuState(selected, groups)` (built by
`formatting.voicing_menu_groups`; `set_voicing` only takes those values);
`InstrumentMenuState(current, families)` (the General MIDI table is
`formatting.INSTRUMENT_FAMILIES`).

**Chord sheet.** The feed starts at `start()` (seeding the strip once, since
feeding arms its debounce timer), then re-feeds `set_song` when the detected
lines, the key or the voicing change. `ChordSheetState(visible, height,
active_view, views, disabled_reason, zoom, zoom_supported, current_index,
song_revision)`; commands `set_chord_sheet_visible`, `set_chord_sheet_height`,
`set_chord_sheet_view`, `chord_sheet_zoom(step)`, `audition(index)`. The
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
`CloseApproved()`; the Tk window saves its geometry through
`set_window_geometry`, stops playback, cancels its subscription and
destroys itself; the application then shuts the session and services down
and saves the config. Failures are `UserError("Error", "<action>:\n<location>
\n\n<reason>")`. `DocumentState(display_name, location, is_modified,
title)`; `RecentDocumentsState(items)` has one owner, the flows'
`add_recent` after a successful open or save.

**Background work.** `BackgroundWorker(host)` (`workers.py`) runs
jobs one at a time on a daemon thread started by the first `submit`;
`submit(fn, on_done)` returns a `Job` whose `cancel()` drops the outcome
(skipping the job if it hasn't started). The `Outcome(value, error)` comes
back through `host.post`; the session wraps `on_done` like a timer.
`shutdown()` (from `AppSession.shutdown`) drops outcomes still on their way
and doesn't wait for a running job; `wait_idle()` is for tests. Jobs only use
what they captured on the session thread: `MainWindowViewModel.capo_job` and
`midi_export_job` snapshot the text, notation, key, tempo and time signature
(passed to `PlaybackService.render_song` as `initial_bpm`/`initial_time_sig`),
and the export renders with its own note picker
(`PlaybackService.create_note_picker`), not the shared one a playback render
may be using.
- Suggest Capo: "Finding a capo for the whole song on X..." while it is
  scored. When the result arrives it is refused while a song plays or is
  paused, and dropped if the text revision moved on (status: "The song
  changed while finding a capo; nothing was inserted"); the user asks again.
  Dropping is the simplest correct choice: re-running on its own could insert
  a capo into text the user is still editing. A newer Suggest Capo cancels
  an older one. A render failure goes to the unexpected-error handler (as
  the exception escaping `respond` did before) and the status returns to
  "Ready".
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

**The Tk window.** `MainWindow(session, host, resources)` talks only to the
session (commands, subscribed states and events, the queries above) and does
view work: widgets and theme, dialogs and pickers, pixel/cursor ↔ offset,
the sash and the window geometry. A guard test
(`tests/test_main_window_guard.py`) keeps `ui/main_window.py` free of
viewmodels, services and the `Application`. The chord identifier gets its
model from `session.chord_identifier_model()`, inserts with `insert_chord`
and reports audio failures with `report_audio_failure`. The Quick Start
snippets paint `compute_spans` with the dialog's own parser (display only).
`AppSession.shutdown` clears the viewmodels' remaining observers (the
window used to, then `Application.on_shutdown`).

**Construction.** `bootstrap.build_core_services(appdata,
dispatch, player=None, audio_options=None)` is the Tk-free half of the old
`Application.on_initialize_services`: it creates the data directories,
loads the config and builds `CoreServices(appdata, config, song_parser,
playback, files)`. `create_session(host, services, documents, dispatch=None,
chord_sheet=True)` builds `MainWindowViewModel`, `TextEditorViewModel`, the
chord-sheet strip (imported only when asked for) and the `AppSession`, whose
optional `services` argument replaced `config_service`,
`song_parser_service` and `playback_service`. The desktop `Application`
uses both (passing itself as `dispatch`, as before) and keeps only the
desktop-only services (resources, logging setup) and the document store.
`AppSession.shutdown` now also drops whatever still observes its viewmodels
(the Tk panel observes the strip), which `Application` used to do.
`AppDataService(root=...)` takes the data directory from the host (Android:
`filesDir`; the same layout the `XDG_*` shim gave). Config writes are atomic
(temp file, `fsync`, `os.replace`).

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
  `DocumentRef`/null; unsaved changes: `save|discard|cancel`/null; capo: a
  string/null; directive: an object of strings/null). An unknown command or
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
- `python -m session.bridge --schema` dumps types, enums, commands with
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
- **The Tk panel still paints from the strip** (`session.chord_sheet_model`,
  live renderers and `RenderedSong`). Android gets the drawing as bytes
  instead: `AppSession.chord_sheet_buffer(height)` packs the active view
  (`chord_sheet.pack.pack_view`) from a snapshot the session thread
  replaces with every `ChordSheetState`, on the caller's thread, so Kotlin
  calls it directly through `SessionHandle.chord_sheet_buffer` without
  waiting for the session thread. The renderers are shared with the strip;
  they are treated as pure (as `pack_view` requires), which nothing checks.
- **Dialog-scoped models: desktop dialogs vs session-held screens.** The
  desktop Settings dialog and chord identifier still hold live viewmodels
  (`settings_model()`, `chord_identifier_model()`). Bridge views get the
  same logic held by the session instead:
  - the chord identifier is a session-owned `ChordIdentifierViewModel`
    behind `identifier_*` / `play_note` / `play_identified_chord` commands
    and an `IdentifierState`; the note helpers (`note_to_midi`,
    `bass_note`, `parse_notes`) are module functions the Tk piano widget
    uses too. The desktop dialog doesn't go through the session path yet:
    it would need to subscribe to the session for `IdentifierState`, and
    its listbox mixes chords with explanation lines, so it was left as is
    (same viewmodel, so the same answers).
  - a Settings screen is a `SettingsEdit` (`session/settings_edit.py`): a
    `SettingsViewModel` working copy plus the voicing in the form, edited
    through `settings_forms.voicing_form` exactly as the Tk Voicings page
    does, saved with the dialog's gate (`validate_all`, then `commit`, then
    the same apply as `apply_settings`). One edit at a time; begin drops an
    older one.
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
  default, `android` from the Android host) picks the wording of the few
  strings that name a gesture or a menu: the click-to-hear audio message,
  the chord sheet's disabled-tab reason, the voicing editor's name help and
  the Quick Start pages (`session/quick_start.py`, which the Tk dialog now
  reads too). The desktop variant is always the old text; tests pin it
  (`tests/fixtures/quick_start_desktop.json`).
- **Click-to-hear has its own picker.** `play_chord_immediate` voices on the
  session thread with `PlaybackService._click_picker`, built on the first
  click and dropped by `set_voicing`, never with the picker a playback render
  uses on the RenderThread. Clicks voice-lead from one to the next, across
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
   render still runs on the executor's thread. On desktop `MainWindow`
   attaches itself to the `TkHost` first thing, because building the chord
   sheet already arms that timer.
4. **The session thread never renders.**
   - MIDI export and capo suggestion run on `BackgroundWorker`.
   - `PlaybackService.stop_playback` no longer joins the render thread. A start
     lock orders "check cancel → `player.start_playback()`" against
     "`cancel.set()` → `player.stop`".
5. **Tk:** the main thread is the session thread.
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
  logs. Throttling is the handler's job: the Tk presenter already throttles
  its dialogs, and the Android handler will throttle its events.
- **`Observable.notify`** reports through it.
- **`utils/error_reporting.py`** stays the Tk presenter and registers itself as
  the handler at import time. `application.py` imports it at the top, so it is
  installed before anything can fail. Its tkinter import is guarded: without
  Tk it still imports but installs nothing. Existing test patch points keep
  working.
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
  - `session` imports without tkinter;
  - DTO purity (every `EventRecorder` item, and every output type emitted
    over the bridge at least once);
  - the committed bridge schema matches the code;
  - no viewmodel, service or `Application` references in
    `ui/main_window.py` (`tests/test_main_window_guard.py`).

# AppSession: the shared application layer

Status: design, approved 2026-10-28. Implemented in steps (see "Migration" below);
this document is the reference for that work and for the Android port
(`docs/ANDROID_PORT_PLAN.md`).

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
  voicing-menu model and ordering; the instrument-family table; key options.

**Views (Tk now, Compose later)**
- Widgets, theme, icons, tooltip wording, dialog layout.
- Pixel/cursor ↔ offset conversion.
- Applying the undo policy carried by each edit event.
- Splitter and window-geometry persistence.
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
  testing.py       ManualHost (virtual clock), InMemoryDocumentStore, FakePlayer, EventRecorder
  errors.py        Tk-free unexpected-error routing (handler registry; the handler throttles)
  documents.py     DocumentRef, DocumentStore, FileSystemDocumentStore
  state.py         frozen state DTOs
  events.py        one-off event + request DTOs
  emitter.py       Emitter: output buffering, coalescing and flush (the delivery contract)
  formatting.py    titles, status strings, multiplier parse, voicing/instrument menu models, key conversion
  highlighting.py  find_comments, compute_spans(lines, text), chord_at(lines, offset)
  flows.py         generator-based request/response FlowRunner
  workers.py       BackgroundWorker (single-thread executor, results via host.post)
  bootstrap.py     CoreServices + build_core_services(appdata, player=None)
  bridge.py        encode(event) -> (type_name, json); schema dump for Kotlin
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
    def recent(self) -> list[DocumentRef]: ...
    def add_recent(self, ref: DocumentRef) -> None: ...
```

- **`FileSystemDocumentStore(file_service)`** delegates to `FileService`, which
  handles normalization, pruning recent files and error messages. It adds
  `ref_for_path(path)`. The desktop id is `os.path.abspath`, not `resolve()`:
  resolving would rewrite symlinks and mapped network drives in the location
  the user sees. `write_bytes` goes through `FileService.save_bytes`, which
  does not add exports to the recent list.
- **`MainWindowViewModel`** works on `DocumentRef`s instead of `Path`:
  - `_current_document` replaces `_current_file`;
  - `open_file`, `save_file_as` and `export_midi_file` take refs.
- **MIDI export** calls `midi_file_writer.render_midi_bytes(...)`, then
  `write_bytes`. A failed write now reports `FileService`'s wording
  ("Permission denied: …", "Failed to write file: …") like a failed save.
- **Until step 13** the viewmodel keeps a `current_file -> Optional[Path]`
  shim, `MainWindow` turns picker paths into refs with
  `application.documents.ref_for_path`, and the Recent Files menu reopens a
  ref through `load_file(ref.id)`.

### States (frozen; only str/int/float/bool/None, tuples, str-Enums)

```python
class SpanKind(str, Enum): CHORD, CHORD_INVALID, DIRECTIVE, DIRECTIVE_INVALID, COMMENT
Span(start, end, kind)
MenuItem(label, value)
DocumentState(display_name, location, is_modified, title)
EditorState(font_family, font_size, read_only, notation)
HighlightState(text_revision, client_token, spans)
PlaybackState(status, playing_span, chord_index, bar, total_bars)      # idle|playing|paused
ToolbarState(notation, bpm, bpm_display, bpm_editable, multiplier_pct, key, key_options,
             beats, unit, metronome, play_action)                       # play|pause|resume
StatusState(text)
VoicingMenuState(selected, groups)
InstrumentMenuState(current, families)                                  # InstrumentFamily(name, is_current, items)
RecentDocumentsState(items)
ChordSheetState(visible, height, active_view, views, disabled_reason, zoom, zoom_supported,
                current_index, song_revision)
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
ConfirmDiscardRequest(request_id)
PickDocumentRequest(request_id, mode, suggested_name)              # open|save|export_midi
CapoChoiceRequest(request_id, options, default)
InsertDirectiveRequest(request_id, kind, existing_labels, notation)
UserError(title, message)
AudioUnavailable(message, from_click)
UnexpectedError(message, context)
CloseApproved()
```

Every programmatic edit is a splice-shaped `TextEdited`, with an undo policy:

| Edit | Splice | Undo policy |
|---|---|---|
| Transpose, capo | `(0, len, new)` | `group` (one undo step) |
| Convert notation | | `plain` |
| Open file | | `reset` |
| Insert | `(at, at, text)`, with the cursor placed after the inserted text | |

### Commands (primitive-typed, session thread)

```python
class AppSession:
    def __init__(self, host: Host, services: CoreServices, documents: DocumentStore) -> None
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
    def tap_chord_at(self, offset: int) -> None
    def set_bpm(self, bpm: int) -> None;  def set_multiplier_pct(self, pct: float) -> None
    def set_key(self, key: str | None) -> None;  def set_time_signature(self, beats: int, unit: int) -> None
    def toggle_metronome(self) -> None;  def set_voicing(self, voicing: str) -> None;  def set_instrument(self, program: int) -> None
    def set_notation(self, notation: str) -> None
    def set_font(self, family: str, size: int) -> None;  def step_font_size(self, delta: int) -> None;  def reset_font_size(self) -> None
    def set_chord_sheet_visible(self, v: bool) -> None;  def set_chord_sheet_height(self, px: int) -> None
    def set_chord_sheet_view(self, view_id: str) -> None;  def chord_sheet_zoom(self, step: int) -> None;  def audition(self, index: int) -> None
    # documents / app
    def new_document(self) -> None;  def open_document(self, ref: DocumentRef | None = None) -> None
    def save(self) -> None;  def save_as(self) -> None;  def export_midi(self) -> None;  def request_close(self) -> None
    def respond(self, request_id: int, value: object) -> None
    def apply_settings(self, changes: SettingsChanges) -> None
```

**Interim shape (recorded in step 5).** Until the remaining steps land:
- The constructor takes the viewmodels it composes
  (`AppSession(host, *, main_window_viewmodel, text_editor_viewmodel)`), built
  by `Application`; `CoreServices` replaces them in step 14. `Application.on_run`
  calls `start()` once the window has attached the host; `on_shutdown` calls
  `shutdown()`.
- `MainWindowViewModel` still holds the document text and the modified flag
  (playback, save and export read it there). The session keeps its own copy for
  detection and forwards every change to `on_text_changed`.
- The session observes `MainWindowViewModel.notation` to switch the detection
  notation (re-detecting immediately) until `set_notation` moves in (step 9).
- Queries the views call synchronously on the session thread:
  `chord_at(offset) -> Span | None` (the Tk hand cursor), `text`,
  `text_revision`.
- Transitional commands, removed by the step named:
  - `set_text_now(text)`: the Tk view applied a programmatic edit (open,
    transpose, convert, capo) itself and reports the result, which is
    re-detected immediately (steps 8 and 11 move those edits in).
  - `detected_chord_at(offset) -> ChordInfo`: the Tk click-to-play still calls
    the viewmodel itself (step 7's `tap_chord_at`).
- `insert_text(at, text)` splices the session's copy and re-detects at once; the
  Tk view still inserts into the widget itself. Emitting `TextEdited` comes
  with step 8.
- The Quick Start snippets paint `compute_spans` directly (display only, no
  session).

**Flows** (`flows.py`) are generators. They yield requests and receive answers
through `respond()`, so a request/response flow reads as plain sequential code.
Only one flow can be pending at a time.

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
  "report click failures once per session" policy.

## Migration (desktop, one commit per step, full test suite green each time)

| # | Step | Risk |
|---|---|---|
| 1 | `Host`, `ManualHost`, `TkHost`; `Application.queue_ui_callback` delegates | Low |
| 2 | `session/errors.py`; `Observable` uses it; Tk presenter registers itself | Low–med |
| 3 | Chord-sheet debounce/marshal through the host | Med |
| 4 | `DocumentRef`/`DocumentStore`/FS store, `utils/paths.py`, `render_midi_bytes` | Med |
| 5 | AppSession skeleton: emitter/flush, `set_text`, detection debounce, `HighlightState` | High |
| 6 | Chord-sheet feed into the session | Low |
| 7 | Playback commands/state/status/playhead, `AudioUnavailable` | High |
| 8 | Programmatic edits with undo policy (transpose, capo, convert, insert) | High |
| 9 | `ToolbarState`, notation/key conversion, multiplier parse | Med |
| 10 | Settings apply, voicing/instrument menu models | Med |
| 11 | Document flows as generators + requests, `DocumentState`/title | High |
| 12 | `BackgroundWorker` for export/capo; non-blocking `stop_playback` | Med |
| 13 | `MainWindow(session, host, resources)`; remove compatibility shims | Low |
| 14 | `ThreadedHost`, `bootstrap`, `bridge.encode` + schema | Med |

Manual check after each step (`make run`):
- open a file with directives;
- type;
- play, loop and shift-play;
- transpose, then undo;
- toggle the chord sheet and switch voicing;
- change settings;
- close with unsaved changes.

Behaviour changes to call out in commit messages:
- an inserted directive is highlighted after the debounce;
- navigation keys no longer trigger re-detection;
- stopping playback no longer blocks for up to 2 s.

## Tests

- **Fixture:** `ManualHost`, `InMemoryDocumentStore`, the real
  `SongParserService`, and the real `PlaybackService` with a `FakePlayer`.
- **`EventRecorder`** golden flows:
  - type text → highlight spans after 0.5 s;
  - play → progress → finished;
  - transpose → re-detect → key shift;
  - open a file with directives → toolbar state;
  - unsaved changes → save → cancel.
- **Guard tests:**
  - `session` imports without tkinter;
  - DTO purity;
  - no viewmodel references in `ui/main_window.py` (after step 13).

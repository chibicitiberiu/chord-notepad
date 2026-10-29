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
  voicing-menu model and ordering; the instrument-family table; key options
  (`session/toolbar.py` holds the toolbar's value logic).

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
  audio_policy.py  AudioFailurePolicy: Play reports every time, clicks once per session
  emitter.py       Emitter: output buffering, coalescing and flush (the delivery contract)
  formatting.py    titles, status strings, voicing/instrument menu models
  toolbar.py       key list + key respelling, BPM/multiplier parse+format, ScrubScale (clamp/snap/quantize)
  directives.py    Insert-menu directives: field validation + messages, directive text, labels, loop choices
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
    def recent(self) -> list[DocumentRef]: ...                # prunes unavailable ones
    def add_recent(self, ref: DocumentRef) -> None: ...       # capped (max_recent_files)
```

Reading and writing never touch the recent list (since step 11): the
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
- **Until step 13** the viewmodel keeps a `current_file -> Optional[Path]`
  shim (unused by the window since step 11), and `MainWindow` turns picker
  paths into refs with `application.documents.ref_for_path` when it answers
  a `PickDocumentRequest`.

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
ConfirmDiscardRequest(request_id)                                  # answer DiscardChoice: save|discard|cancel
PickDocumentRequest(request_id, mode, suggested_name)              # PickMode: open|save|export_midi
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
| Convert notation, New | | `plain` |
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
  (`AppSession(host, *, main_window_viewmodel, text_editor_viewmodel,
  chord_sheet_viewmodel=None)`), built by `Application`; `CoreServices`
  replaces them in step 14. `Application.on_run` calls `start()` once the
  window has attached the host; `on_shutdown` calls `shutdown()`.
- The chord-sheet feed (step 6) starts at `start()`, which seeds the strip
  once: feeding arms the strip's debounce timer, and on desktop the host has
  no window to run timers on before that. After it, a change of the detected
  lines, the key or the voicing re-feeds `set_song` (the voicing notifies even
  for the same value, because the note picker was rebuilt).
- `MainWindowViewModel` still holds the document text and the modified flag
  (playback, save and export read it there). The session keeps its own copy for
  detection and forwards every change to `on_text_changed`.
- The session observes `MainWindowViewModel.notation` to switch the detection
  notation (re-detecting immediately) until `set_notation` moves in (step 9).
- Queries the views call synchronously on the session thread:
  `chord_at(offset) -> Span | None` (the Tk hand cursor), `text`,
  `text_revision`.
- Transitional commands, removed by the step named:
  - `set_text_now(text)`: removed in step 8 (see below).
  - `show_status(text)`: the Tk view words the chord identifier's
    "Inserted chord: X" (`MainWindow.update_statusbar` sends it here), so the
    status line has one owner (`StatusState`) and a repeated playback status
    is never lost behind a view-written one. Its only caller since step 11;
    goes with step 13.
- The Quick Start snippets paint `compute_spans` directly (display only, no
  session).

**Interim shape (recorded in step 7, playback).**
- The session observes `MainWindowViewModel`'s `is_playing`, `is_paused`,
  `current_playback_event` and `playback_error`, and drives
  `start_playback(from_char_offset)`, `pause_playback`, `resume_playback`,
  `stop_playback` and `on_chord_clicked`; the viewmodel and
  `PlaybackService` are unchanged. It forwards each `CHORD_START` ping to
  `ChordSheetViewModel.on_playback_chord` (the strip's playhead); the panel
  still observes the strip viewmodel's `current_index` until
  `ChordSheetState` exists.
- `PlaybackState` carried an extra `bpm` (the effective tempo) until step 9
  moved it to `ToolbarState.bpm_display`.
- `EditorState` had only `read_only` until step 10 added the font and
  notation fields.
- Status texts come from `session/formatting.py`. The chord count in
  "Playing N chords..." is taken from the latest detection, as before (it can
  lag a just-typed edit by the 0.5 s debounce).
- `AudioUnavailable.message` is the full user-facing text (the click variant
  says clicked chords stay silent). Since step 10 every click source goes
  through the session's one `AudioFailurePolicy` (see below).
- Playback pings that reach the session after it went idle (posted by the
  player before a Stop reached it) are dropped, so a stopped song no longer
  re-highlights a chord or rewrites the status line.
- The strip's playhead is cleared when a song finishes, but stays on the
  last chord after Stop (unchanged behaviour; `PlaybackState` itself goes
  idle with no chord).
- The Tk Play button first sends the widget's text with `set_text` (a no-op
  when `<<Modified>>` already did), then `play_pause(from_offset)`, with the
  Shift+click cursor as a code-point offset (`ChordTextEditor.offset_of`).

**Interim shape (recorded in step 8, programmatic edits).**
- Every programmatic edit reaches the views as one `TextEdited` followed, in
  the same flush, by the `HighlightState` of the new text (no debounce).
  `insert_text` and the directive insert are session splices `(at, at, text)`;
  transpose, convert and capo still run through `MainWindowViewModel`
  (`transpose`, `convert_text_to_*`, `insert_capo`), which replaces the whole
  text with `set_and_notify("current_text")`. The session observes
  `current_text` and turns each replacement into `TextEdited(0, len, new)`
  carrying the undo policy of the command running at the time (`group` for
  transpose and capo, `plain` otherwise); the cursor goes to the end of the
  text, where Tk's delete+insert left it before.
- Open and New replaced the text through the viewmodel from the Tk window,
  as `plain` edits, with `MainWindow.load_file` calling `edit_reset()`
  afterwards. Since step 11 the session's flows run them: Open is a `reset`
  edit, New stays `plain`.
- Programmatic edits are refused (logged, no output) while a song plays or is
  paused: `transpose`, `convert_notation`, `insert_text`, and the answers to
  the insert-directive and capo requests. The requests themselves are still
  emitted, so the dialogs open as before; the answer is refused. (Before, the
  locked widget silently ignored these edits while the viewmodel and session
  copies took them, so the copies disagreed with the editor.)
- `TextEdited` is applied by `ChordTextEditor.apply_edit` even while the
  widget is locked (Open/New during playback now update the editor instead
  of leaving it showing the old text). It clears the widget's modified flag
  afterwards: `<<Modified>>` is queued, so that is what keeps the edit from
  being sent back with `set_text`.
- Ordering: a state keeps its first position when set twice in one flush, so
  the session never publishes a `HighlightState` before a `TextEdited` in the
  same command. Edit commands don't re-detect up front: convert reuses the
  detector's lines only when no detection is pending, and the label lookup
  parses afresh (`TextEditorViewModel.detect_chords`, no notify) when one is.
- Requests: `InsertDirectiveRequest(request_id, kind, existing_labels,
  notation)`, answered with a `{field: value}` mapping (`session/directives.py`
  documents the fields) or None; `CapoChoiceRequest(request_id, options,
  default)` with `MenuItem(label, value)` options, answered with a value or
  None. Invalid directive fields at answer time emit `UserError`; the Tk
  dialogs check them live with `directives.check_directive` (same messages as
  before) so that only happens to a view that skips the check. The capo
  suggestion runs on the worker since step 12 (see below). The Tk window
  presents requests from `after_idle`, never from inside
  the listener: a modal dialog there would hold back the session's output
  (playback progress) until it closed.
- The transpose dialog stays view-side (no request): the view asks for the
  semitones and calls `transpose(semitones, selection)`. Before any edit
  command the Tk view sends the widget's text with `set_text`.
- Selections are `(start, end)` code-point pairs; an empty one means none.

**Interim shape (recorded in step 9, toolbar).**
- `ToolbarState(notation, bpm, bpm_display, bpm_editable, multiplier_pct, key,
  key_options, beats, unit, metronome, play_action)`. `bpm_display` is the
  effective tempo of the chord sounding while a song plays (once the first
  chord is known), else `bpm`; `bpm_editable` is `status == idle`;
  `play_action` is `play|pause|resume` and drives the Tk Play/Pause icon and
  tooltip. `key` is the first key option when no key is set (what the Tk
  combobox always showed); a notation flip with no key set therefore no
  longer writes one.
- `MainWindowViewModel` still owns the values (and their config writes); the
  session observes `bpm`, `bpm_multiplier`, `metronome_enabled`, `key` and the
  time signature and republishes the whole state, so file directives and a
  whole-song transpose reach the toolbar too. (`set_bpm_multiplier` used to
  assign before `set_and_notify`, so it never notified; fixed.)
- Commands: `set_notation`, `set_bpm` (ignored while playing or paused, like
  the read-only Tk field), `set_multiplier_pct` (works during playback),
  `set_key` (None/"" clears), `set_time_signature` (invalid values logged and
  ignored by the viewmodel), `toggle_metronome`. `set_bpm` and
  `set_multiplier_pct` clamp and snap with the scrubber's own `ScrubScale`
  (`toolbar.BPM_SCALE`, `toolbar.MULTIPLIER_SCALE`), so a raw slider value
  lands where a Tk drag would.
- Notation: the session's `notation` observer re-detects, respells the key in
  the new notation (`toolbar.convert_key`, via `set_key`) and publishes the
  new key list. It runs for `set_notation` and for the flip at the end of
  convert; in the latter the `TextEdited` is already queued, so the views
  get the edit, then its highlight, then the toolbar.
- The Tk toolbar starts neutral and only maps `ToolbarState`; widgets send
  commands from user actions (`<<ComboboxSelected>>`, spinbox `command`,
  scrubber `on_change`), never from variable traces. `ui.scrubber.Scrubber`
  does its math through `ScrubScale`. `utils/key_helpers.py` is gone
  (`toolbar.key_options`).

**Interim shape (recorded in step 10, settings and menus).**
- `apply_settings(changes)` does what `MainWindow._on_options_apply` did:
  `font_changed` re-reads the font from the config
  (`MainWindowViewModel.reload_font_settings`); `voicings_changed`
  republishes `VoicingMenuState`; `new_active_voicing` is applied with
  `set_voicing`, else a `voicing:` voicing in use is re-applied when the
  registry changed (it may have been edited in place). `general_changed`
  and `audio_changed` are still ignored on purpose: the dialog saves those
  as defaults for the next start, and the running toolbar keeps its values.
  The dialog itself still commits the config (`SettingsViewModel`, scoped
  to the dialog).
- `EditorState(font_family, font_size, read_only, notation)`; the session
  observes the viewmodel's font. Commands: `set_font(family, size)`,
  `step_font_size(delta)` (Ctrl +/-, Ctrl+wheel; clamped 6-72),
  `reset_font_size()`. The Tk window keeps the last `EditorState` for the
  font dialog and the Quick Start snippets.
- `VoicingMenuState(selected, groups)`: groups of `MenuItem`s (piano, the
  built-in fretboards, the built-in ensembles, the user's voicings by model
  then name; empty groups left out), built by
  `formatting.voicing_menu_groups`. `set_voicing` only takes those values
  (ValueError otherwise) and re-applies the same value when chosen again.
  The Tk menu is rebuilt only when the groups change; otherwise only the
  radio selection moves.
- `InstrumentMenuState(current, families)` with `InstrumentFamily(name,
  is_current, items)`; item values are program numbers as strings. The
  General MIDI family table is `formatting.INSTRUMENT_FAMILIES`. The
  soundfont's list is read again on every publish (startup and each
  `set_instrument`), as the Tk menu did on each rebuild. The Tk menu
  destroys the old family submenus on a rebuild and styles the new ones
  (before, submenus built after startup lost the clam outline).
- `ChordSheetState(visible, height, active_view, views, disabled_reason,
  zoom, zoom_supported, current_index, song_revision)`, with
  `ChordSheetView(view_id, label, available)`. The session observes the
  strip viewmodel's `visible`, `active_view`, `available_views`, `zoom`,
  `current_index` and `rendered_song` (which bumps `song_revision`).
  Commands: `set_chord_sheet_visible`, `set_chord_sheet_height`,
  `set_chord_sheet_view` (unavailable views
  ignored), `chord_sheet_zoom(step)`, `audition(index)`; all do nothing
  without a strip.
- Interim: the Tk `ChordSheetPanel` still paints from the strip viewmodel
  (the `RenderedSong` and the renderers are live objects; painting is a
  view job until draw ops cross the bridge) and observes its display
  state for repaints. Only its commands (zoom buttons, tabs, clicks) go
  through the session (`ChordSheetPanel(parent, vm, session=...)`). The
  window uses `ChordSheetState` for the pane, the View menu check and the
  sash height.
- Audio failures: chord-sheet auditions are played by the session and the
  chord identifier hands its `AudioInitializationError`s to
  `report_audio_failure(reason, from_click=True)`; both go through the
  session's `AudioFailurePolicy`, so all click sources still report once
  between them. `ui/audio_errors.py` lost its module-global policy
  (`use_policy`, `show_audio_error`); it only presents `AudioUnavailable`.
  The Tk window parents that dialog to the focused toplevel, so the
  identifier's error still shows over the identifier.
- `session.testing.FakeChordSheet` stands in for the strip viewmodel in
  session tests; `EventRecorder.compact(skip=...)` leaves out states a
  golden isn't about.

**Interim shape (recorded in step 11, documents).**
- Commands `new_document()`, `open_document(ref=None)`, `open_recent(ref)`,
  `save()`, `save_as()`, `export_midi()`, `request_close()`, each a
  `FlowRunner` flow. The unsaved-changes question is
  `ConfirmDiscardRequest`, answered `"save"`, `"discard"` or `"cancel"`
  (`DiscardChoice`; None cancels). Pickers are `PickDocumentRequest(mode,
  suggested_name)`, answered with a `DocumentRef` or None; any other answer
  raises `TypeError` (the bridge decodes refs in step 14). The flows contain
  no path logic: the desktop view answers with `ref_for_path(picked path)`,
  Android will answer with a ref for a SAF URI.
- Semantics, as before: with unsaved changes New, Open (also a recent one)
  and close ask first; "save" on a never-saved document goes through the
  Save As picker; a failed or cancelled save stops the New/Open/close;
  cancel anywhere stops. Save As suggests the document's name
  (`Untitled.txt` without one), Export MIDI `<stem>.mid` (`Untitled.mid`).
  Open is a `reset` edit, highlighted in the same delivery, and the file's
  first tempo, key and time-signature directives set the toolbar
  (`MainWindowViewModel._apply_initial_settings_from_content`, unchanged).
  Reopening a document whose text equals the editor's still emits a `reset`
  splice (same text), so the view's undo history starts over as before.
  `request_close` emits `CloseApproved()`; the view then tears itself down
  (Tk: `_close_window`, from `after_idle`, since it shuts the session down).
- Failures are `UserError("Error", "<action>:\n<location>\n\n<reason>")`,
  the wording of the old dialogs; the reason still comes from
  `MainWindowViewModel.last_error` (open/save/export keep returning bool).
  Status texts ("Opened: …", "Saved: …", "Exported MIDI: …", "New file
  created") are `StatusState`s from the flows.
- The viewmodel still holds the open document, the text and the modified
  flag, and does the I/O (`open_file`, `save_file_as`, `export_midi_file`,
  `new_file`); the session observes `current_document` and `is_modified`
  and publishes `DocumentState(display_name, location, is_modified, title)`
  (`"Untitled"` and None for a new document; the title from
  `formatting.window_title`). The session uses the viewmodel's store
  (`MainWindowViewModel.documents`) until it gets its own in step 14, so
  the two can't diverge.
- Recents have one owner: the flows call `add_recent` after a successful
  open or save (any save, so the list is republished then too) and publish
  `RecentDocumentsState(items)`, a tuple of `DocumentRef`s (frozen, strings
  only). `FileService.open_file/save_file` and the viewmodel no longer add
  to it (both did, so each open/save wrote the list twice). The store caps
  the list (`max_recent_files`) and prunes unavailable entries when it is
  read: at startup and after each open or save, as when the Tk menu was
  rebuilt.
- Tk: the File menu and its shortcuts send the editor text with `set_text`,
  then the command; requests are presented from `after_idle`
  (`askyesnocancel`, the native pickers in `utils/file_dialogs.py`); the
  title and the Recent Files menu come from the states. `MainWindow` no
  longer reads `last_error`, `current_file`, `get_window_title` or
  `get_recent_files` (the last two are gone from the viewmodel).
- Behaviour changes: Open with unsaved changes answered "No" asked the
  question a second time (the picker path ran the check again); it asks
  once now. The title reads "Untitled - Chord Notepad" from startup (it was
  "Chord Notepad" until the first edit or open).

**Interim shape (recorded in step 12, background work).**
- `session/workers.py`: `BackgroundWorker(host)` runs jobs one at a time on a
  daemon thread (started by the first `submit`); `submit(fn, on_done)`
  returns a `Job` whose `cancel()` drops the outcome (and skips the job if it
  hasn't started). The `Outcome(value, error)` comes back through
  `host.post`, so `on_done` runs on the session thread; the session wraps it
  like a timer. `shutdown()` (from `AppSession.shutdown`) drops outcomes still
  on their way and doesn't wait for a running job. `wait_idle()` is for
  tests. `AppSession(..., worker=None)` makes its own on the host.
- Jobs only use what they captured on the session thread:
  `MainWindowViewModel.capo_job(voicing, region)` and `midi_export_job()`
  snapshot the text, notation, key, tempo and time signature (passed to
  `PlaybackService.render_song` as `initial_bpm`/`initial_time_sig`), and
  the export takes its own note picker (`PlaybackService.create_note_picker`)
  instead of the shared one a playback render may be using. The synchronous
  `suggest_capo_for` and `export_midi_file` remain (job + finish in one
  go) for direct callers and tests.
- Suggest Capo: after the answer the status reads "Finding a capo for the
  whole song on X..." and the result is applied when it arrives, after
  re-checking two things. While a song plays or is paused the result is
  refused (logged, like every programmatic edit). If the text revision moved
  on (the user typed), the result is dropped and the status says "The song
  changed while finding a capo; nothing was inserted"; the user asks again.
  That is the simplest correct choice: re-running automatically could insert
  a capo into text the user is still editing. A newer Suggest Capo cancels
  an older one still being scored. A render failure goes to the unexpected-
  error handler (as the exception escaping `respond` did before) and the
  status goes back to "Ready".
- Export MIDI: the song as it is when the file is picked is rendered on the
  worker ("Exporting MIDI: <location>..."); the bytes are written on the
  session thread when the render arrives
  (`MainWindowViewModel.finish_midi_export`), so a failure has the same
  wording as before and nothing half-written is left if the app closes
  mid-render. An export still rendering at shutdown is dropped. On failure
  the status goes back to "Ready".
- `PlaybackService.stop_playback` no longer joins the render thread (it
  waited up to 2 s). `_start_lock` orders the render thread's "check cancel
  → wire the player → `player.start_playback()`" against stop's "cancel and
  take the event buffer", after which stop calls `player.stop_playback()`:
  a render stopped before it reached the lock never starts the player, and
  a player it did start is stopped. A failed render reports under the same
  lock, so a stopped render reports nothing. `cleanup()` cancels a render in
  flight the same way. A new render waits on its own thread for the
  previous (cancelled) one to finish before it resets and uses the shared
  note picker, so two playback renders never share it.
- Playback generation: `MainWindowViewModel` tags each run's callbacks
  (pings, end of song, render error) with a generation that goes up on
  every start and stop, and drops them on the session thread when stale.
  So a ping or an end the old run posted before it saw a stop can't
  highlight a chord or end the new run (the session's own "drop pings while
  idle" check only covered the gap before a new run).

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
  playback render failures are `UserError` since step 7).

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
- an inserted directive is highlighted after the debounce (steps 5-7; since
  step 8 it is highlighted at once again);
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

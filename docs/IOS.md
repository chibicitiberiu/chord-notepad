# iOS and iPadOS build

The iOS app: a SwiftUI front end over the shared Python core and the same
JSON session bridge Android uses. One universal app for iPhone and iPad.
This file covers the rules, the Swift kit, the bridge as Swift sees it, the
development loops and the sessions on borrowed Apple devices. The Android
counterpart is `docs/ANDROID.md`; the bridge itself is specified there
("Bridge contract", "Chord sheet op buffer") and only the differences are
repeated here.

**Status (2026-11-24):** the core knows the `ios` platform (section B of the
plan), `ios/ChordNotepadKit` is built and tested on Linux (section C), and
CI builds the app and tests it on iPhone and iPad simulators with no Apple
account (section D, `.github/workflows/ios.yml`). The screen slices so far:
the chord sheet ("The chord sheet" below), the song editor with the Edit
ribbon ("The song editor") and the main screen with the Edit / Play tabs, the
player and the ☰ menu ("The main screen"), file handling: Open, New,
Save, Save As, Recent, Export MIDI and audio, Examples and songs opened from
Files ("Files"), and the player's sheets with the ribbon's tools: Voicing,
Instrument, Playback speed, Playback settings, Insert, Transpose, Suggest
Capo and the chord identifier ("The player's sheets and the ribbon's
tools"), and Settings, About and the licences ("Settings, About and
Licences"). Still to come: enrollment, signing and TestFlight (A, E), then the
other screens (F, in `BACKLOG.md`): the guide, the Quick Start tour and Export
PDF.

## Decisions and constraints

- **A straight port of today's app**, fitted to the platform the way Android
  is (Edit/Play modes, sheets, tap-to-rename). iOS-specific UX is in scope
  and is recorded as a deliberate difference, not a new feature.
- **Logic lives in the shared Python core.** Swift is view-only: it never
  re-implements wiring, formatting or highlighting, never touches a Python
  object outside the kit's bridge, and never calls Python on the main thread.
  App flows belong in `core/chordnotepad/session/`
  (`docs/architecture/session.md`).
- **Offsets are code points in Python**; `OffsetMapper` is the only place
  that converts to UTF-16 (`NSRange`, `UITextView`).
- **Settings visibility rule:** as on Android. iOS shows every setting whose
  meaning carries over and hides the rest without replacements: no log level,
  audio driver, SoundFont path or window geometry.
- **Swift sees plain C only.** Every Python C API call is in the kit's
  `CNBridge` C target; Swift calls a small C surface (start, submit, buffer,
  shutdown, the callbacks).
- **One interpreter per process**, started once and never finalized. A
  process starts one session.
- **Audio** stays in Python on its own threads: FluidSynth's CoreAudio driver
  on iOS. The licensing route is in `BACKLOG.md` (iOS entry).
- **No money beyond the developer membership.** No rented Macs, no extra
  hardware: Linux, GitHub's macOS runners (free for a public repo) and a few
  borrowed sessions on his wife's MacBook and iPhone. Her devices are never
  signed into his Apple ID; he works under his own macOS user there.
- **Tooling** lives under `/mnt/data_linux/Bin/`, never in `~` (`/home` is
  nearly full).

## Layout

```
ios/
  project.yml                   XcodeGen spec of the app (the .xcodeproj isn't committed)
  .xcode-version                the Xcode CI selects (and her MacBook should match)
  ChordNotepad/                 the app target (SwiftUI, Swift 5 mode)
    App/                        AppModel (the session), paths, the document store (AppDocumentStore,
                                ScopedFileAccess, DocumentPicking), diagnostics, self-test
    Screens/                    MainScreen (pure), MainView (live), AppBar, PlayerBar, PlayerSheets (the
                                player's and Insert's sheets), Overlays (menu, dialogs, snackbar),
                                DiagnosticsView (self-test, export), SettingsView, VoicingsView,
                                SettingsWidgets, AboutView (About, the licences)
    Tools/                      ToolDialogs (Transpose, Suggest Capo, the Insert dialogs, Manual… speed,
                                the tempo), ChordIdentifierView (the identifier and its piano)
    Editor/                     the song editor: EditorTextView and EditorHost, EditorController, SongEditor,
                                PlayText (Play mode), EditRibbon, EditorAppearance, EditorPreview, EditorScript (CI)
    ChordSheet/                 the chord sheet: CGSheetCanvas, ChordSheetSource, ChordSheetPane
    Catalog/PreviewCatalog.swift  the screens drawn from Fixtures, and the PNG renderer
    Assets.xcassets             the app icon (ios/tools/make_app_icon.py), Icons/ (ios/tools/mdi_assets.py)
    PrivacyInfo.xcprivacy       the app's privacy manifest
  ChordNotepadTests/            XCTest hosted in the app: the session, the catalog
  ChordNotepadKit/              SwiftPM package, no UIKit or SwiftUI
    Package.swift
    .swift-version              the toolchain swiftly and the Makefile use
    Sources/CPython/            system library: Python.h, linked only for Linux/macOS hosts
    Sources/CNBridge/           C: interpreter start, the _cnbridge module, calls into Python
    Sources/ChordNotepadKit/
      PythonRuntime.swift       the interpreter and its bridge thread
      BridgeThread.swift        the one thread every Swift → Python call runs on
      Session.swift             start / submit / chordSheetBuffer / shutdown, events
      SessionSnapshot.swift     the output folded into what a screen shows; Fixture
      DocumentStore.swift       the store protocol and its C callbacks
      BridgeValues.swift        JSONValue, Selection, BridgeCommand
      Generated/Bridge.swift    DTOs, enums, SessionOutput, command builders (generated)
      OffsetMapper.swift        code points <-> UTF-16
      SheetBuffer.swift         op-buffer v2 decoder (values, no drawing)
      ChordSheet/               the chord sheet's logic: geometry, theme, split, loader, painter
      Editor/                   the song editor's logic: EditorModel, EditHistory, text arithmetic,
                                styles, paste and wrap, scrolling, shortcuts, directive hints
      Main/                     the main screen's logic: modes, layout, playback, rename, menus,
                                playhead gestures, snackbars, the screen's own state, AppColors
      Sheets/                   the player's sheets: routes, speed, Playback settings' rows, Insert's
                                entries, SheetController (every tap in a sheet or a tool, as commands)
      Tools/                    the ribbon's tools: forms, the session's check, Suggest Capo's pick,
                                the identifier's piano and model, RibbonEdges
      Files/                    file handling's logic: document ids, the store (FileDocumentStore over
                                DocumentFileAccess), the bookmark table, examples, the session's requests
      Settings/                 Settings' logic: the draft, SettingsController, the voicing form's schema
                                and items, pending edits, steppers, the field's echo, the texts
      About/                    the licence list and texts, About's build info, links and texts
      Python/chordnotepad_ios/  the Python glue (host.py, diagnostics.py), shipped as a resource
    Tests/ChordNotepadKitTests/ XCTest; python/ holds a tiny test module
  Fixtures/                     recorded session output per scene, for the preview catalog
  Licenses/components.json      the licences of what the iOS app ships (About › Open source licences)
  tools/
    gen_swift_bridge.py         writes Generated/Bridge.swift from the schema
    install_python.sh           the app's "Install Python" build phase
    export_glyphs.sh            the "Chord sheet glyphs" build phase
    make_app_icon.py            renders the icon from resources/chord-notepad-icon.svg
    mdi_assets.py               Android's Material Design Icons as SVG image sets (and the Settings
                                and About icons from their Kotlin paths)
    copy_licences.py            the "Licences" build phase: the list and its texts into the app
    ci_simulators.py, ci_screenshots.sh   CI helpers
  build/                        not committed: frameworks, the Python bundle, DerivedData
packaging/ios/
  build_fluidsynth.sh           FluidSynth.xcframework from the pinned source
  fetch_python.sh               Python.xcframework (pinned), trimmed and precompiled
  build_python_bundle.py        the core and its packages, precompiled
  compile_pyc.py                unchecked-hash .pyc files
  privacy/                      privacy manifests for binary modules (OpenSSL)
```

## Setup on Linux

Swift comes from swiftly, installed in user space (no sudo) under
`/mnt/data_linux/Bin/swiftly`:

```sh
mkdir -p /mnt/data_linux/Bin/swiftly/dl && cd /mnt/data_linux/Bin/swiftly/dl
curl -sSLO https://download.swift.org/swiftly/linux/swiftly-$(uname -m).tar.gz
tar zxf swiftly-$(uname -m).tar.gz
export SWIFTLY_HOME_DIR=/mnt/data_linux/Bin/swiftly/home
export SWIFTLY_BIN_DIR=/mnt/data_linux/Bin/swiftly/bin
export SWIFTLY_TOOLCHAINS_DIR=/mnt/data_linux/Bin/swiftly/toolchains
./swiftly init --no-modify-profile --skip-install --quiet-shell-followup -y --platform fedora39
/mnt/data_linux/Bin/swiftly/bin/swiftly install 6.3.3
```

Fedora 44 has no build of its own; the `fedora39` toolchain works (6.3.3,
2026-11-24). The Makefile doesn't need swiftly's environment: it puts
`$(SWIFTLY_TOOLCHAINS)/<.swift-version>/usr/bin` first on `PATH`. To use the
`swift` proxy in a shell instead, export the three `SWIFTLY_*` variables
above and put `$SWIFTLY_BIN_DIR` on `PATH` (it also holds a `clang`, so keep
that out of your normal `PATH`).

CPython comes from the system: Fedora's `python3-devel` (3.14) provides
`Python.h` and `libpython3.14.so`, found through `pkg-config python3-embed`.
The core's packages come from the pipenv venv, which is made from the same
`/usr/bin/python3.14`, so its compiled wheels load in the embedded
interpreter. The system `libfluidsynth` is needed because the core loads
it at import even with the fake player.

## Running the tests

```sh
make ios-kit-test      # swift test: 399 tests, about 35 s after the first build
make ios-bridge-gen    # regenerate Generated/Bridge.swift after a schema change
make ios-fixtures      # rewrite ios/Fixtures after an intended output change
```

Never run bare `make`: its default target starts the desktop app.

- `make ios-kit-test` sets `CN_SITE_PACKAGES` to the venv's site-packages,
  found with `pipenv --venv` (which never creates one). A git worktree has no
  venv of its own, so pass the main checkout's:
  `make ios-kit-test IOS_SITE_PACKAGES=$HOME/.local/share/virtualenvs/chord-notepad-IF5b83s2/lib/python3.14/site-packages`.
- The make targets also set `CN_REQUIRE_CORE=1`: without the core's packages
  the tests that need them fail. In a bare `swift test` they are skipped,
  and the runtime, decoder and offset tests still run.
- `CN_CORE_DIR` points the tests at another `core/` (default: the checkout's).
- `tests/test_ios_swift_bridge.py` (pytest, no Swift needed) fails while the
  generated Swift is stale.
- On a Mac host (CI), the manifest links Python only when
  `CN_PYTHON_PKGCONFIG` names a pkg-config package (Homebrew's
  `python3-embed`). A manifest is evaluated for the host, so an unconditional
  `pkgConfig` would pass the Mac's Python flags into the iOS build.

What the tests cover:

| Suite | What |
|---|---|
| `RuntimeTests` | isolated `PyConfig`, UTF-8 mode, `sys.path` order, tracebacks as Swift errors, one interpreter per process, events from Python threads in order, every store call and its error mapping, the GIL released while Swift blocks |
| `BridgeCodecTests` | generated facts against the schema file, every builder (null and set) accepted by the core's own `decode_args` and answer decoders, required nullable keys written as null, decoding by type name |
| `OffsetMapperTests` | Android's `OffsetMapperTest`, case for case (lone surrogates through UTF-16 code units) |
| `SheetBufferTests` | Android's `ChordSheetBufferTest` on the same fixtures, plus every truncation throwing, huge counts, `Data` slices |
| `SnapshotTests` | `SessionSnapshot` (code-point edits, the message cap), every fixture folding into a screen's snapshot, the chord sheet scenes' buffers (view, zoom, playhead, heights), the Scarborough Fair scenes frozen while their chord sounds, the editor scenes folded into the editor (the selection a command made, every span kind, the notation) |
| `EditorTextTests` | Android's `SpanShiftTest` and `TextEditsTest`, case for case: the one changed range, surrogate pairs, spans moving like Tk tags, a session edit's cursor before, inside and after its replacement against a code-point reference (500 random edits), the anchor's selection |
| `EditorModelTests` | Android's `EditorControllerTest` and `EditorWiringTest` as behaviour (tokens, stale highlights, spans moving with typing, no echo, `group`/`plain`/`reset`, a highlight that arrives before its edit, code-point taps and cursor, the playing chord), plus the undo history (typing runs, a new line or a caret move ends one, redo, undone text highlighted under its token, read-only), composition, paste, Convert and the line commands, every fixture folding into the editor |
| `EditorLookTests` | Android's `EditorLookTest` (font kinds, points × 4/3, the pinch, the redundant directive's alpha, tag priority) and `ShortcutsTest` with Command; the style runs (no overlaps, priority, the playing chord on top, clamping, merging) |
| `TextInputTests` | Android's `PasteNormalizationTest`, `ChordWrapTest`, `TextScrollTest` and `DirectiveHintControllerTest`, case for case |
| `ChordSheetGeometryTests` | Android's `ChordSheetGeometryTest`, case for case: anchors, hit-testing, gutter variants, culling, lane clips, auto-scroll, zoom steps, Tk colours, requests; the scroll after a new buffer |
| `ChordSheetThemeTests` | Android's `ChordSheetThemeTest` and `ChordSheetPaperTest` as behaviour: the light theme keeps the buffer's colours, the dark one maps them; the palette |
| `ChordSheetLayoutTests` | Android's `ChordSheetSplitTest`, the pane's content height, when the strip follows the playhead |
| `ChordSheetLoaderTests` | Android's `ChordSheetControllerTest`: one fetch per distinct request after the settle time, no song, a newer version, the loading flag, stale replies dropped |
| `SheetPainterTests` | the painter on the Android fixtures with a recording canvas: paint order, clips and translations, glyph rectangles and tints (widths against `clef_assets.scaled_width`), text anchoring and pixel snapping, lane clips, the playhead marks, the key bed, culling |
| `DiagnosticsTests` | the offline render of a chord is not silent (system libfluidsynth, the repo's SoundFont), a missing SoundFont is reported, the fault handler's file |
| `MainScreenTests` | Android's `ModeControllerTest`, `ScreenLayoutTest`, `PlaybackUiTest`, `RenameFlowTest` and `MenuModelsTest`, case for case; the chord sheet pane's height upright and on its side, the speed badge, the snackbars, the menu's entries, the rename dialog's state, the player's state from a snapshot |
| `PlayheadGesturesTests` | Android's `PlayheadGesturesTest`, case for case, and the marker's shape |
| `FileDocumentStoreTests` | Android's `SafDocumentStoreTest` as behaviour on real files (`PlainFileAccess`): raw bytes, the desktop's wording with the document's location, a recent file that has gone (named from its entry, dropped with its bookmark), the 5 MB cap, a cloud file not downloaded, the same file picked twice, a stale bookmark made again under its id, a moved file, a relaunch, corrupt lists, writes in place, `copyFromFile`, the shipped song, example copies (rename, a taken name), rename keeping the id, the recent list's order, cap and pruning, exports and their written callback; the id scheme |
| `ExampleLibraryTests` | Android's `ExampleLibraryTest`, case for case (ids are `app:examples/<name>`) |
| `SessionRequestsTests` | Android's `RequestControllerTest` and `DocumentPickersTest` as behaviour: the snapshot's pending request, a picker once per request, a stale result ignored, Save As's move, an export answered at once with the store's file, the unsaved-changes answers, an Insert dialog's fields checked and answered (Cancel answers null), PDF requests cancelled once |
| `PlayerSheetsTests` | Android's `SheetRouteTest`, case for case (the instrument's two levels, the speed dialog, typed and snapped speeds, the badge, the pill and Write into song), the slider letting go once the session has its value, Manual…'s check, Playback settings' rows and choices, Insert's entries |
| `ToolsTests` | Android's `ToolFormsTest` and `DirectiveVerdictTest`, case for case (selections in code points, Transpose's range, each directive's answer, loop targets, key lists, Suggest Capo's pick and Apply, a stale or foreign check ignored), the messages in the fields' order, the tools' commands from the editor's model, `RibbonEdges` |
| `IdentifierTests` | Android's `IdentifierTest`, case for case: the piano's keys and hit testing, labels in either notation, the model's field and pick, a notation switch, the layout, key looks, sounding keys and their token |
| `SheetControllerTests` | every tap in the sheets and the tools through the reducer: the route, the dialogs' fields, the commands (speed, Playback settings and its locked reason, voicing, instrument, Insert, Transpose with and without a selection, an Insert dialog checked as it changes, Suggest from Insert Capo, Suggest Capo's pick and Apply, the identifier), Edit voicings… opening Settings |
| `SettingsControllerTests` | Android's `SettingsControllerTest`, case for case but its three `snapshot()`/`restore()` cases (no state restoration on iOS): the edit's life, autosave and the 400 ms rest, a number only saved when valid, the voicing commands each followed by a save, leaving and the problems question, values kept from last time, the navigation on a phone and with two panes, the split, the dialogs, Add voicing's presets and sections, a built-in and a newer release's voicing read-only, pending edits, the key's spelling; the problems' lines, the steppers; `SettingsScenesTests`: every Settings scene folds into an editing screen with its schema |
| `VoicingFormTests` | Android's `VoicingFormTest`, case for case: the schema, every field and section kind, the three models' forms with their errors and hints, records and the bottom voice's gap, a read-only form, the payloads, pending edits, steppers; the field's echo and the errors banner's timing |
| `LicencesTests` | Android's `LicencesTest` on the iOS list, case for case but its Maven cases: every entry's fields and text, the texts the build phase copies, the components the app ships (and none it doesn't), the versions the build pins, the AGPL and the SoundFont's licence, the LGPL source, the Python pins without chardet, the order, bad data, the pages' ← and an opened song, the build info, the FOSS support link |
| `IntegrationTests` | one real session: restore a draft, code-point highlights, save through the store, a refused rename, a decoded chord sheet buffer; open songs from the store, save a typed change, Save As to a new id, Export MIDI through the store, the unsaved-changes question on Open and New (Don't save, Cancel), a recent song that has gone; the speed and its Reset, Write into song, every Insert request with the session's check, an answered Insert, Suggest Capo scored and applied, the identifier naming Cmaj7 and its Insert, Transpose of the song and of a selection; Settings through the controller (a General value, a staged number, My 7-String, an unbuildable value refused and fixed with the config unchanged, Jazz Vocal Trio, a built-in, a refused rename, leaving); the thirty scenes (three of them frozen while a chord sounds) |

## The Swift kit

### Starting Python

`PythonRuntime.start(configuration)` starts the interpreter on the bridge
thread, once per process (the same configuration again returns the running
runtime; another one is an error):

- `PyPreConfig_InitIsolatedConfig` with `utf8_mode = 1`, then
  `PyConfig_InitIsolatedConfig`: no `PYTHON*` variables, no user site
  folder, no script folder on the path.
- `install_signal_handlers = 0`: the app owns the signals.
- `write_bytecode` off by default (the app bundle is read-only; ship `.pyc`).
- `home` is the bundled stdlib's prefix on iOS; nil on Linux, where CPython
  finds its own.
- `use_system_logger = 1` on iOS only (the field exists only in Apple builds
  of CPython), so `print` and logging reach the unified log.
- `_cnbridge` is registered with `PyImport_AppendInittab` before the start.
- The configured `searchPaths`, then the kit's glue folder, go in front of
  the `sys.path` CPython computed.
- `environment` is applied with `setenv` before the start:
  `CHORD_NOTEPAD_LIBFLUIDSYNTH` on iOS (the framework's binary, which
  `audio/fluid_ctypes.py` loads at import time), `CN_TEST_FAKE_PLAYER=1`
  in the tests.
- After the start the GIL is released (`PyEval_SaveThread`). A failed
  `PyStatus` comes back as a Swift error; nothing calls `exit`.

### Threading contract

This is `docs/architecture/session.md` "Threading contract" point 6 for iOS.

1. **One bridge thread** ("python-bridge") runs every Swift → Python call,
   in the order they were made: the start, each `submit`, each
   `chordSheetBuffer`, the shutdown. It is a dedicated `Thread` with a 16 MB
   stack rather than a `DispatchQueue`: Python always sees the same OS thread
   (its main thread, since the interpreter starts there), and secondary
   threads on Apple platforms get 512 KB by default, too little for the
   core's imports. Linux's 8 MB default would hide that.
2. **The main thread never runs Python.** `Session.submit` only queues and
   returns; `chordSheetBuffer` and `shutdown` are `async`.
3. **Each call takes the GIL itself** (`PyGILState_Ensure/Release` in C),
   so Swift knows nothing of Python thread states.
4. **Python's threads call Swift**: `python-session` delivers events and
   calls the store; an export's worker thread calls `writeBytes` and
   `copyFromFile`. The C side releases the GIL around each callback, so a
   store may block on file I/O, but no callback may wait for the bridge
   thread: it may be waiting for `python-session` at that moment
   (`BridgeContract.kt:52-57`).
5. **Events never wait.** `_cnbridge.emit` yields into an unbounded
   `AsyncStream`. The sink and the store are registered before Python's
   `start` runs, because the replay of every state arrives from
   `python-session` while the bridge thread is still inside `start`.

### Bridge contract: what differs from Android

The wire format is Android's: `submit(command, args_json)` in,
`onEvent(type_name, json)` out, both described by `android/bridge_schema.json`;
`chord_sheet_buffer(height)` returns op-buffer v2 bytes. The Python entry
point is shared too: `core/chordnotepad/session/embedded_host.py`, with
`session/callback_store.py` turning the store callbacks into a
`DocumentStore`.

| | Android | iOS |
|---|---|---|
| Entry point | `chordnotepad_android.host.start(files_dir, native_lib_dir, store, sink, audio_options)` | `chordnotepad_ios.host.start(options_json)`: `{files_dir, soundfont_path, sample_rate, frames_per_buffer, configure_logging, platform}` |
| Platform | `android` | `ios` (`session.platform.IOS`: Android's flags, texts fall back from ios to android) |
| Calls into Python | Chaquopy `PyObject.callAttr` | `CNBridge` C functions (`cn_start_handle`, `cn_handle_submit`, ...) |
| Events | Kotlin `EventSink.onEvent` | `_cnbridge.emit` → C function pointer → `AsyncStream<(typeName, json)>` |
| Store | Kotlin `DocumentStoreBridge`; exceptions mapped by class name | Swift `DocumentStore`; `_cnbridge.store_*` with `(code, message)` from C; `StoreError(message)` / `RenameUnsupportedError(message)` → `FileOperationError` / `RenameNotSupported` |
| Store values | `recent()` and `describe()` return JSON strings | the Swift protocol uses `DocumentRef`; the kit encodes the JSON |
| Bytes | `byte[]` | `(pointer, length)`, copied on each side |
| Buffer | `ByteArray?` | `Data?` (nil without a rendered song) |
| Codec | hand-written `@Serializable` DTOs, `ignoreUnknownKeys` | generated `Codable` structs; unknown keys ignored, a missing non-optional field is an error |
| Commands | hand-written builders | a generated builder per command in the schema, `respondTo<Request>` helpers per answer type |

Rules the generated code follows:

- Swift names are lowerCamelCase with explicit `CodingKeys`; no key
  strategy. Keywords are backticked (`TimelineSection.repeat`); the
  `StartupScreen` value `none` is the case `noScreen`.
- Every struct encodes every key, nil as `null`. `decode_args` rejects a
  missing key (`session/bridge.py`), and a `DocumentRef` or `SettingsValues`
  must carry exactly its fields.
- Builders take every parameter and always write every key, so no default
  can drift between Swift and Python. The schema lists parameters
  alphabetically, so the labels are in that order:
  `.restoreDraft(document:modified:readOnly:text:)`.
- `json` and `any` are `JSONValue`; `selection` is `Selection?` (`[start,
  end]` or null).
- A command whose arguments don't encode (a non-finite `Double`) and a
  failed C call show up on `events` as `UnexpectedError(context="bridge")`,
  as on Android.

Regenerate after changing a DTO or a command: first the schema
(`cd core && python -m chordnotepad.session.bridge --schema >
../android/bridge_schema.json`), then `make ios-bridge-gen`.

### Fixtures for the preview catalog

`IntegrationTests` records thirty scenes into `ios/Fixtures/`: `empty_song`,
`quick_start_edit`, `play_with_chord_sheet` (the complete example with the
chord sheet shown as the piano roll and the playhead on the third chord),
`errors` (a document that can't be opened, a rename the storage refuses),
`chord_sheet_staff` (the staff, zoomed in one step, playhead on chord 24),
`chord_sheet_fret` (fret cards after `set_voicing guitar:standard`, which
makes the view available), four of Scarborough Fair as the Android store
screenshots show it (`android/tools/store_shots.json`, the song in
`android/tools/help_shot_songs/`, the strip 330 pt tall): `scarborough_edit`,
then `scarborough_piano_roll`, `scarborough_fret` (`guitar:standard`, zoom
0.5) and `scarborough_tab` (zoom 0.833) frozen while chord 4, 3 and 6 sound,
`editor_mid_edit` (the quick-start song with a
line of an invalid and a redundant directive and an unknown chord put in by
`insert_text`, then two lines commented out by `toggle_comment`, whose
`anchor` leaves them selected: every span kind) and `editor_european` (the
quick-start song after `convert_notation european`), then the file scenes:
`files_recent` (three songs opened from the store, the recent list with them
and the song saved earlier), `export_done` (the lullaby's copy, saved with
Save As and reopened from Recent so the scene carries its text, exported as
MIDI: "Exported MIDI: Lullaby (2).mid") and `discard_question` (a session edit,
then New: the scene ends on `ConfirmDiscardRequest`), then the sheets' and
tools' scenes on Amazing Grace, as Android's help screenshots show it
(`android/tools/help_shots.json`, the songs in `android/tools/help_shot_songs/`):
`player_sheets` (the tempo set by `{bpm: 90}`, 3/4 and G as the song's own
values, the speed at 125 %, Steel Guitar), `insert_bpm`, `insert_time`,
`insert_key`, `insert_capo`, `insert_label` and `insert_loop` (each ends on
its `InsertDirectiveRequest`, the cursor after "me"; the tempo's carries the
session's check of "999", the label's a clean check of "chorus"),
`grace_edit` (the song restored again, nothing pending), `capo_advice`
(Suggest Capo scored for the whole song) and `identifier_cmaj7` (C, E, G and
B selected, Cmaj7 played), then Settings' scenes, last, each from Amazing
Grace's restore so it carries the text and the schema (an event):
`settings_open` (the edit begun, the defaults, no voicings of the user's),
`settings_voicing_form` (My 7-String made from a blank fretboard with strings
B1 E2 A2 D3 G3 B3 E4, as `android/tools/help_shots.json` has it),
`settings_voicing_refused` (its strings B1 E2 X9 G3 and a relaxed span of 2:
two problems, nothing saved), `settings_voicing_ensemble` (Jazz Vocal Trio:
Lead A3–F5, Harmony F3–D5, Bass E2–C4) and `settings_builtin` (the standard
guitar read-only). A fixture has no answers, so a request in it
stays pending; only the question draws, and the scenes after the Insert
requests start from a fresh restore. Each scene comes after
the ones whose states it would change, so theirs stay as they were; the
editor's come last, with the sheet hidden again. A scene starts at the mark
before its song's `restore_draft`, so it carries the `TextEdited` with the
text. The user's own typing can't be recorded (the session doesn't echo
`set_text`), so the editor scenes are made of the session's edits. A
playing scene can't be recorded as it is either: the FakePlayer plays the
whole song at once, so the scene is the session's output up to the status
that names the chord (`PlaybackState` playing with that `chord_index`, then
"Bar 5/56 · Playing G"; the strip's `current_index` agrees). Android's store
screenshots freeze playback the same way, by publishing the states seen
while the chord sounded again. The later scenes' states change with these
(the voicing, the strip's view and height), and the editor's stay stale
from the sheet's last render, as before. Each file has the newest JSON of every state (the whole
screen) and the other outputs of the scene in order, exactly as they crossed
the bridge, sorted and indented, with the temporary files folder written
`$FILES_DIR`. A normal run checks them; `make ios-fixtures` rewrites them.
They are the same on every run.

The catalog can't call Python, so each scene with the sheet shown also keeps
its op buffers: `chord_sheet_buffers`, a list of `{height, base64}`, packed at
the content heights the main screen asks for in Play in the catalog's four
windows (`MainSheetPane`: below the text upright, the split's height; in the
side column on its side, the window less the app bar and the player; then
less the pane's header, progress bar, inset and the 20 pt marker lane): 102,
185, 355 and 603 pt for a 160 pt sheet, 185, 272 and 603 pt for 330.
`CatalogTests` checks the heights still match the catalog's devices. The theme is applied at paint
time, so light and dark share the recordings.

## The app

### The app bundle

```
ChordNotepad.app/
  ChordNotepad                      the Swift executable (kit linked in statically)
  Frameworks/Python.framework       CPython 3.14 (Python.xcframework)
  Frameworks/FluidSynth.framework   libfluidsynth 2.6.1, LGPL, loaded by path
  Frameworks/_ssl.framework, ...    one per binary stdlib module ("Install Python")
  python/lib/python3.14/            the standard library, .pyc next to each .py
  python/app/                       chordnotepad (the core), chordnotepad_ios (the glue)
  python/app_packages/              the core's packages
  chord_sheet/                      the clef and glyph PNGs and glyphs.json ("Chord sheet glyphs")
  licenses/                         components.json and the texts it names ("Licences")
  GeneralUser-GS.sf2, Fixtures/, 01_quick_start.txt, PrivacyInfo.xcprivacy
```

- **Python.xcframework** is BeeWare's support package for 3.14
  (Python-Apple-support `3.14-b14`: CPython 3.14.10, OpenSSL 3.5.9).
  python.org publishes iOS builds only from 3.15. It is CPython's own iOS
  framework build with its dependencies compiled in and the App Store
  compliance patch applied. `packaging/ios/fetch_python.sh` checks its
  sha256, drops what the app never imports (the test suite, IDLE, Tkinter,
  ensurepip, the test extension modules) and precompiles the stdlib.
- **"Install Python"** (`ios/tools/install_python.sh`, the target's last
  build phase) is CPython's "Process Python libraries" step
  (`Doc/using/ios.rst`): it copies the stdlib for the slice and architecture
  being built, the core and the packages, then turns every `.so` into
  `Frameworks/<dotted.name>.framework` with a `.fwork` file in its place and
  a `.origin` file inside, the only form in which iOS loads native code. A
  module's `.xcprivacy` becomes its framework's privacy manifest. It signs
  those frameworks only when the build signs, so the unsigned device build
  works.
- **.pyc files:** the bundle is read-only and `write_bytecode` is off, so
  every `.py` is shipped with an unchecked-hash `.pyc`
  (`packaging/ios/compile_pyc.py`, run with the host's 3.14). Timestamp
  ones would go stale when a copy touches the files, and Python would then
  compile every module at every start without saying so.
- **Packages:** `packaging/ios/build_python_bundle.py` installs the pins of
  `android/requirements.txt` with `pip --no-deps --target` from the
  hash-checked wheelhouse (`android/tools/build_wheelhouse.py`): every one is
  a pure `py3-none-any` wheel. chardet stays out (as on the desktop; requests
  falls back to charset-normalizer) and music21 is the trimmed wheel from
  `android/tools/strip_music21.py`. The app reaches FluidSynth only
  through the core's ctypes binding, `audio/fluid_ctypes.py`.
- **FluidSynth.xcframework** (`packaging/ios/build_fluidsynth.sh`): 2.6.1
  from the macOS build's pinned tarball and gcem, `CMAKE_SYSTEM_NAME=iOS`,
  device arm64 and simulator arm64, `--target libfluidsynth`, CoreAudio on
  (the iOS RemoteIO driver, which sets up its AVAudioSession itself),
  CoreMIDI, libsndfile, GLib, network and signalsmith off. The script
  fails if CMake took the macOS HAL path, if AVFoundation isn't linked, or
  if anything outside `/usr/lib` and `/System` is. Each slice is a
  hand-made `FluidSynth.framework` (`install_name_tool -id
  @rpath/FluidSynth.framework/FluidSynth`, an Info.plist with the slice's
  platform and `MinimumOSVersion` 17.0). Two flags FluidSynth's CMake
  doesn't set for iOS: `CMAKE_MACOSX_BUNDLE=OFF` (CMake makes every iOS
  executable a bundle, and the install rule for FluidSynth's program has no
  bundle destination) and `-lobjc -framework Foundation` for the
  AVAudioSession code. That code also asks for `defaultToSpeaker` with the
  Playback category, which CoreAudio logs as an error and ignores; the
  session still ends up in Playback.
- **Start:** `AppModel.start` starts Python with `home = <app>/python`,
  `python/app` and `python/app_packages` in front of `sys.path`, and
  `CHORD_NOTEPAD_LIBFLUIDSYNTH=<app>/Frameworks/FluidSynth.framework/FluidSynth`;
  then the session with `files_dir` = Application Support and the bundled
  SoundFont. The app opens the quick-start song as a draft (store id
  `bundle:01_quick_start.txt`), so it starts in Play, as a saved song does.
- **Kit headers on iOS:** `Package.swift` gives `CNBridge` `-F
  ios/build/Frameworks/Python.xcframework/ios-arm64` for iOS (both slices
  have the same headers); the app target links and embeds the framework.
  The shims include `<Python/Python.h>` only when `TARGET_OS_IOS`; a Mac
  host always uses pkg-config's `<Python.h>`, since `/Library/Frameworks`
  is on clang's default path and may hold another version's
  Python.framework. The kit imports `CNBridge` with `internal import`, so
  the app and its tests never need the C module.

### Diagnostics

`SessionSnapshot` (in the kit, tested on Linux) folds the session's output
into what a screen reads; `EditorState` carries no text, so its `text` is
rebuilt from `TextEdited`. That is the session's edits only: the editor's
own model (`EditorModel`, fed the same outputs in the same order by
`AppModel.receive`) owns the text the user sees and types.

**Diagnostics** is the ☰ menu's last entry (a top-level entry of its own,
not under About), in every build, TestFlight included: a sheet with the
build stamp, the self-test (run when it opens; "Run again") and "Export
diagnostics" in its bottom bar.

- **Logs:** `os_log` subsystem `com.tibich.chordnotepad`, categories
  `bridge`, `python`, `audio`, `store`, `ui`. Python's own output reaches
  the unified log through `use_system_logger`. On a Mac:
  `log stream --predicate 'subsystem == "com.tibich.chordnotepad"'`.
- **Signposts** (category `audio`): `audition`, from the tap to the
  session's first output after it, with a `submitted` event when the
  command is queued; `offline render` and `start` (category `python`). The
  note-on and the render happen in Python's threads; signposts there need a
  `_cnbridge` hook (`BACKLOG.md`).
- **Files** under Application Support: the core's rotating log
  (`data/chord-notepad/logs`) and `Diagnostics/`: `faulthandler.log`
  (Python's tracebacks of every thread on a native crash), `metrickit/`
  (MetricKit's metric and diagnostic payloads; a device delivers them
  about once a day, the simulator never), `build.json`, `launch.json`
  (start-up timings, written when the first song is on screen) and
  `selftest.json`.
- **Visible in Files:** Files can only see Documents
  (`UIFileSharingEnabled`, `LSSupportsOpeningDocumentsInPlace`), so the app
  copies all of the above into `Documents/Diagnostics` at launch, when it
  goes to the background and before an export. "Export diagnostics" zips
  that folder (`NSFileCoordinator`'s `.forUploading`) for the share sheet.
- **Build stamp:** Info.plist `CNGitCommit` and `CNBuildDate`, passed by CI
  on the xcodebuild command line, with `MARKETING_VERSION` from `VERSION`
  and the run number as the build. Diagnostics shows it.
- **Self-test** (also `-CNScreen selftest` at launch): Python boot, session
  start and first-text times; an offline render of a C major chord on a
  FluidSynth synth with no audio driver (the core's audio export renderer,
  `chordnotepad_ios.diagnostics.offline_render`), which must not be silent;
  a live audition and whether FluidSynth's CoreAudio player started; the
  AVAudioSession category, route, sample rate and buffer.

### The chord sheet

The first screen slice: the Play tab's strip, shown under the text (or
beside it on its side) in Play while `ChordSheetState.visible`; the player's
last button shows and hides it. It is a port of Android's `ui/chordsheet/`.

- **In the kit** (`Sources/ChordNotepadKit/ChordSheet/`, tested on Linux):
  `ChordSheetGeometry` (anchors, the desktop's 25 % / 70 % auto-scroll,
  zoom steps for a pinch, the scroll that keeps the same music in view after
  a zoom or a view change, lane label clips), `ChordSheetTheme` (Android's
  light and dark tokens as `SheetColor` RGBA values, the dark mapping of the
  buffer's colours, a buffer's palette), `ChordSheetLayout` (the split's
  heights, the pane's fixed parts, `PlayheadFollower`), `ChordSheetLoader`
  (`SheetRequest`, the `ChordSheetLoad` state machine, and a main-actor
  driver that settles height changes for 60 ms, fetches through a closure
  and decodes off the main actor) and `SheetPainter`, which paints a
  `PreparedSheet` on the small `SheetCanvas` protocol: rectangles (square or
  rounded), ellipses, polylines, filled paths, text runs with a measure call,
  and glyph images. No CGFloat, no Combine, no UIKit.
- **In the app** (`ChordNotepad/ChordSheet/`): `CGSheetCanvas` implements
  `SheetCanvas` on CoreGraphics and CoreText (system font at the op's size ×
  4/3; glyphs pre-scaled to device pixels and tinted SrcIn, cached);
  `ChordSheetSource` is the `ObservableObject` over the kit's loader (live,
  `Session.chordSheetBuffer` on the bridge thread) or a fixture's recorded
  buffers (the catalog); `ChordSheetPane` has the split, the header and the
  strip.
- **Why a `Canvas` and not a UIView:** ImageRenderer draws SwiftUI only, so a
  `Canvas` (whose `withCGContext` hands the CoreGraphics canvas its context)
  is the same view live and in the catalog. A transparent `UIScrollView`
  sits over it in the live app only: it gives the strip iOS's scrolling
  (momentum, bounce), and its offset is the strip's scroll; it also takes the
  tap (`audition` for the slot under it) and the pinch.
- **Glyphs:** the "Chord sheet glyphs" build phase (`ios/tools/export_glyphs.sh`)
  runs `android/tools/export_clef_glyphs.py` into `<app>/chord_sheet/`, as
  Android's Gradle task does: the seven base PNGs and `glyphs.json` (base
  sizes; the painter sizes a key `max(1, round(base_w × h / base_h))`, with
  Python's rounding). Standard library only, so the system `python3` on a Mac
  is enough.
- **Live check:** `SessionTests` shows the sheet, fetches through
  `ChordSheetSource`, decodes and paints the buffer into an image (attached
  as `chordsheet-live.png`); `-CNScreen chordsheet` shows the sheet at launch
  and writes `Diagnostics/chordsheet.json` when the first buffer is drawn,
  which CI's screenshot waits for.

Deliberate differences from Android:

- The piano roll's keyboard sits on a bed of its white keys' colour (the
  desktop's `key_bed`), so the gaps beside the black keys aren't the strip's
  paper, in the dark theme especially.
- Scrolling is a `UIScrollView`'s (it bounces at the ends); a jump to the
  playhead is `setContentOffset(animated:)`.
- The first buffer opens with the playhead's chord in view; after that the
  strip follows the playhead only when it moves, as on Android.
- A tap on an unavailable view shows the core's reason in a capsule over the
  strip for 2.5 s (Android: a Toast).
- The header is a fixed 32 pt, so its labels follow Dynamic Type up to
  `xLarge` only; the strip's own text ignores the text size (its geometry
  comes from the renderers), as on Android.
- While a pinch is in progress the whole strip scales, the gutter too.
- The height the drag stores is in points (`set_chord_sheet_height`).

### The song editor

The second slice: the main screen's text is the song editor, a port of
Android's `ui/editor/` with the Edit ribbon (`ui/main/EditRibbon.kt`).

- **In the kit** (`Sources/ChordNotepadKit/Editor/`, tested on Linux):
  `EditorModel` is the whole editor as a value: the text the view shows,
  its selection, the painted spans, the sounding chord, the undo history and
  the text exchange with the session. Every input is a mutating call that
  returns `EditorEffects` (commands to send, `ViewEdit`s for the text
  storage, the selection, whether to restyle or scroll):
  - the user's edits (`viewChanged(text:selection:composing:)`, from the
    text view's delegate) go out as `set_text` with an increasing client
    token; the session doesn't echo them;
  - the session's `TextEdited` come back as `ViewEdit`s in UTF-16
    (`TextEdited.utf16(in:)`, with the selection its `anchor` and `cursor`
    make), folded into the history by their `undo`, never sent back; while
    an input method composes (marked text) they wait for the composition to
    end;
  - a `HighlightState` is painted only for the text it was computed for
    (Android's `TextIdentity`: the client token, or a session edit's
    revision); until then the old spans move with each edit the way Tk tags
    do. A state that arrives before its text (a fixture folds the states
    first) is painted once the text is there;
  - `EditHistory`: undo is the view's, as on every front end (the session
    has no undo command; Android uses `TextFieldState`'s history, the Qt
    desktop `QTextDocument`'s). Typing merges into one step per run
    (insertions that continue where the last one ended, a run of Backspace
    or Delete; a new line or a caret move starts a new step), a `group` or
    `plain` session edit is a step of its own, `reset` clears the history,
    and each step puts back its selection. The text an undo or redo leaves
    goes to the session as a user edit;
  - `perform(_:)` runs the ribbon's and the key commands' actions (undo,
    redo, the font steps, the notation, Convert, the desktop's line
    commands), with the text synced first and offsets in code points.

  `EditorStyles.swift` has `EditorPalette` (Android's `AppColors` for the
  editor and the ribbon: Tk's colours in light, readable hues in dark),
  `styleRuns` (the spans and the sounding chord flattened into runs that
  don't overlap, merged in the desktop's tag priority; a field a span leaves
  unset keeps the lower span's, as in Tk and Compose) and `EditorFont`.
  `TextInput.swift` has the paste normalisation, the chord join points and
  `JoinedText`, and `TextScroll`; `EditorShortcuts.swift` the key bindings;
  `DirectiveHints.swift` Play mode's long-press explanation (Android's
  controller as plain state; Edit mode shows no hint).
- **In the app** (`ChordNotepad/Editor/`): `EditorTextView` (a UITextView on
  a TextKit 1 stack built by hand) in its `EditorHost` (the sideways
  scroll), `EditorController` (the main actor's
  `ObservableObject` over the model; it applies the effects to the view and
  sends the commands), `SongEditor` (the `UIViewRepresentable` and its
  delegate), `EditRibbon`, `EditorAppearance` (fonts and attributes from the
  kit's runs), `EditorPreview` (the catalog's drawing), `PlayText` (Play
  mode, "The main screen" below) and `EditorScript` (CI's typing).
- **The text is never assigned.** SwiftUI only places the view
  (`updateUIView` does nothing). The session's edits, undo and redo go into
  the text storage with `replaceCharacters`, the delegate's callbacks
  ignored meanwhile; the model's bookkeeping is done first. Should the view
  and the model ever differ, it is logged and the model's text wins.
- **Styles** are attributes on the text storage, repainted from the kit's
  runs after each change, never while an input method has marked text
  (changing its attributes ends the composition). The typing attributes are
  reset after every change, so what is typed after a chord isn't blue.
- **TextKit 1** rather than TextKit 2: the layout manager's
  `shouldBreakLineByWordBeforeCharacterAt` keeps a chord whole when the text
  wraps (`D/F#` never splits after the slash), so the song never holds a word
  joiner and a copy needs no cleaning (Android draws joiners and rewrites
  the clipboard). The stack is built by hand at init, since asking a
  TextKit 2 view for its layout manager switches it over mid-life.
- **Word wrap off** (the default, `EditorState.word_wrap`): the container is
  100 000 pt wide and the text view as wide as the longest line, inside
  `EditorHost`, a scroll view of its own that scrolls sideways (Android's
  `horizontalScroll` around its field). The text view scrolls up and down
  and follows the caret that way itself; the host follows it sideways
  (`TextScroll.followCursor`), and the sounding chord on both axes
  (`TextScroll.followChord`). UIKit sizes a text view's container to its
  frame even with `widthTracksTextView` off, so the text view puts the
  container back to its full width after every layout (CI measured 563 pt
  in a 587 pt view without that). A first try let the text view scroll
  both ways with a widened `contentSize`: the width was right (868 pt in a
  402 pt view) but the iPhone's sideways offset still ended at 0 after the
  typing; the cause wasn't pinned down, and the separate host avoids it.
- **Undo:** the view's undo manager is an `EditorUndoManager` whose undo,
  redo and "can undo" are the kit's, so the Edit menu, shake to undo, the
  three-finger gestures, the iPad's shortcut bar and Command-Z all reach
  the same history as the ribbon. UIKit still registers its own typing
  actions there; they are never run, and one level is kept.
- **The ribbon** is a SwiftUI row under the header, as on Android, rather
  than an `inputAccessoryView`: it stays with a hardware keyboard or none,
  the catalog can draw it, and iPhone and iPad share one layout. Its
  captions follow Dynamic Type up to `xLarge` (the row is a fixed 48 pt).
- **Font:** the session's size in desktop points × 4/3, scaled like body
  text by `UIFontMetrics`, so it follows Dynamic Type; the configured
  family's kind picks the system's monospaced design (the default), the
  system font or its serif design (New York).
- **Input:** no autocorrection, capitalisation, spell checking, smart quotes
  or dashes, smart insert and delete, or inline prediction. A change that
  needs normalising (a paste, a drop, dictation, a keyboard's non-breaking
  space) is refused in `shouldChangeTextIn` and put in normalised.
- **Live check:** `SessionTests` puts a real `EditorTextView` in a window,
  types through UIKit's `insertText` (the keyboard's path, which calls the
  delegate), waits for the session's highlight under the editor's own
  token, checks the unwrapped content is wider than the view with the caret
  at the end of the typed line scrolled into sight, a session
  `insert_text` lands without a `set_text` going back, and undo and redo
  (the ribbon's and the undo manager's) go back as user edits; the view is
  attached as `editor-live.png`. `-CNScreen editor` does the typing at
  launch on the screen itself and writes `Diagnostics/editor.json`, which
  CI's screenshot waits for and checks.

Deliberate differences from Android:

- Hardware keys use Command, not Ctrl; redo is Shift-Command-Z (no
  Command-Y). The Qt desktop's line commands come along: Command-/ (toggle
  comment), Command-D (duplicate), Shift-Command-K (delete lines) and
  Option-Command-Up/Down (move lines; the desktop's Shift-Ctrl-arrows would
  take over "select to the start/end" on Apple platforms).
- A session edit with an `anchor` selects from it to the cursor, as the Qt
  desktop does (Android ignores the anchor).
- The session's edits wait while an input method composes.
- Dragging the text down hides the keyboard (`keyboardDismissMode =
  .interactive`).
- The empty editor says "Type or paste a song here" in the system's
  monospaced body font, as Android's placeholder.

What CI doesn't test: a person typing on the software keyboard (its
suggestions bar, a long-press menu), input method composition (Japanese,
Chinese) and dictation on a device, the hardware key commands (XCTest
sends no key events without UI tests), shake and the three-finger gestures,
dropping text, rotation, VoiceOver, and the editor's speed on a long song
(every change repaints the whole text's attributes). Word wrap on never runs
live (the break hook, the tracking container, the host not scrolling), nor
do finger scrolling and the selection handles inside the host. The live
placeholder is the system's monospaced body font in the secondary colour;
the catalog's is the editor's font at 45 % of the text colour (Android's).

### The main screen

The third slice: the app's frame, a port of Android's `ui/main/`
(`SongScreen.kt`, `AppBar.kt`, `ModeController.kt`, `ScreenLayout.kt`,
`PlaybackUi.kt`, `RenameFlow.kt`, `AppDrawer.kt`) and `ui/play/` (`Player.kt`,
`PlayheadGestures.kt`). It replaces the shell and its test buttons.

- **In the kit** (`Sources/ChordNotepadKit/Main/`, tested on Linux):
  `ModeController` (which tab is open: the first document decides, a saved
  one opens in Play, an untitled one in Edit; Edit while a song plays or is
  paused stops it), `ScreenLayout` and `MainMetrics` (phone or tablet, the
  one-line header of a phone on its side in Edit, the chord sheet below the
  text upright or in a side column on its side, the collapsing header, the
  column's share), `MainSheetPane` (the pane's height in a window, for the
  screen and the recorded buffers), `PlaybackUi.swift` (starting, keeping the
  screen awake, when a status is a snackbar, the speed badge, `PlayerState`
  from a snapshot), `RenameFlow.swift`, `MenuModels.swift` (the voicing and
  instrument lists, the recent songs), `PlayheadGestures.swift` (chord boxes,
  taps, the marker's grab strip, scrubbing, the explainable directives, the
  marker's shape), `Snackbars` (what shows, and for how long), `AppMenu`
  (the ☰ menu's entries) and `MainUiState` (the tab, what is open over the
  screen, the keyboard's height, the rename dialog's refusal), and
  `AppColors` (Android's). `SessionSnapshot` keeps the toolbar, the song
  defaults, the voicing and instrument menus, the recent songs, the
  settings, the directive hint and a refused rename (no longer a message).
- **In the app** (`Screens/`): `MainScreen` draws the whole screen from a
  snapshot, the editor's model and a `MainUiState` (the catalog makes one
  per scene); `MainView` keeps the live state in `AppModel` and presents the
  sheets. `AppBar` (☰, the title with its • and tap to rename, Edit / Play,
  Save), `PlayerBar`, `Overlays` (the menu, the dialogs, the snackbar),
  `PlayerSheets`, `DiagnosticsView`. Play mode is `Editor/PlayText.swift`
  with `EditorController`'s Play part.
- **Icons:** Android's Material Design Icons, so the bar and the player look
  the same: `ios/tools/mdi_assets.py` turns Android's generated vector
  drawables into SVG image sets rendered as templates
  (`Assets.xcassets/Icons`), tinted like Android's `MdiIcon`. The ribbon
  keeps its SF Symbols; Diagnostics has the stethoscope.
- **Play mode** is the same `EditorTextView`, frozen: not editable or
  selectable (the keyboard goes), so both tabs share the layout and the
  scroll position. The marker is a `CAShapeLayer` in the text's own
  coordinates; the chord boxes come from TextKit (`rect(of:)`). A tap
  (`tap_chord_at`, or `set_playhead` for the nearest chord when it misses
  and nothing plays), the scrub (`MarkerScrub`, a pan that fails at once
  unless it starts on the marker, so the text's scroll views, which wait for
  it, scroll without delay; one `set_playhead` on release) and the
  long-press on a red or faded directive (`request_directive_hint`; the
  answer in a `HintCardView` by the directive for 6 s or until the next
  touch) are decided by the kit; the controller's handlers are plain
  methods, so `SessionTests` calls them. The sounding chord is painted and
  followed by the editor, as before.
- **The player** is Android's: the song pill ("𝄞 100 · 3/4 · Am ⌄", the
  session's `SongDefaultsState.summary`), voicing, instrument, ⏮, ▶/⏸ (a
  ring while the song renders), metronome, speed (with its badge) and the
  chord sheet's toggle, then the status line ("Bar 5/56 · Playing G", the
  session's `StatusState`). The voicing button is greyed while a song plays
  and a tap says why (`locked_reason`). The pill, Voicing, Instrument and
  Speed open their sheets ("The player's sheets and the ribbon's tools").
- **Rename** (tap the title): the name without its extension, "Saved as
  “name.txt”" or why the name can't be used under it; a name the session
  refuses stays in the dialog with the reason, a storage that can't rename
  closes it and offers "Save a copy under the new name instead?" with
  Save as… (`save_as {name}`), as Android does.
- **The menu** has Android's drawer's entries in its order (New song,
  Open…, Recent, Save as…, the three exports, Settings, Examples, User
  guide, Quick start, About) and Diagnostics last. The file entries,
  Recent, Examples, Settings and About work; Export PDF, the guide and the
  Quick Start tour are greyed with "Coming soon". The panel runs
  the screen's whole height, under the status bar and the home indicator,
  as Android's drawer does; its entries stay inside the safe area.
- **Layout:** as `ScreenLayout.kt`. The chord sheet is a Play-mode view, so
  the shell's case of the keyboard up with the sheet showing doesn't arise
  any more; the header collapses in Edit with the keyboard up when the text
  would get less than 170 pt (a phone on its side), and undo and redo then
  float by the keyboard, as on Android. Edit has no status line: the
  session's status shows as a snackbar there, errors in both modes.
- **Large text:** the bar is a fixed 48 pt; its title is body text, which
  follows Dynamic Type up to `accessibility2`, and on a phone at the
  accessibility sizes the tabs drop their captions (icons only) so the title
  keeps its room. The player (a fixed 110 pt) follows it up to `xxLarge`.
- **Launch hooks:** `-CNScreen selftest` opens Diagnostics,
  `-CNScreen chordsheet` opens Play with the sheet shown, `-CNScreen editor`
  switches to Edit before typing, `-CNScreen menu` opens the menu,
  `-CNScreen export` exports the song as audio ("Files"), `-CNScreen speed`,
  `insert`, `capo` and `identify` open a sheet or a tool ("The player's sheets
  and the ribbon's tools"), `-CNScreen settings`, `voicings` and `about` a
  page ("Settings, About and Licences").

Deliberate differences from Android:

- The menu is a panel from the leading edge over a dimmed screen, opened by
  ☰ only; there's no edge swipe (Android allows the swipe only while the
  drawer is open, and an edge swipe would fight the marker's grab strip at
  a line's first chord). It lists Diagnostics, which Android doesn't have.
- The dialogs (rename, a refused rename) are cards in the app's colours over
  a dimmed screen, so the catalog draws them; Diagnostics and Examples are
  iOS sheets.
- Snackbars are drawn by the screen (no Material snackbar host); a greyed
  button's reason is a short snackbar (Android: a Toast).
- The screen stays awake while a song plays through the idle timer.
- The side column's width isn't kept across launches (Android keeps it in
  its preferences; on iOS that needs UserDefaults and its privacy reason).
- The tabs drop their captions on a phone at the accessibility text sizes.

What CI doesn't test: a finger on the marker (the scrub's recognizer and
the scroll views waiting for it), the long-press and its card, the menu,
the dialogs live (the catalog draws them), the keyboard collapsing the
header live, rotation, VoiceOver.

### Files

The fourth slice: Open, New song, Save, Save As, Recent, Export MIDI and
audio, Examples, the unsaved-changes question and songs opened from Files,
ported from Android's `files/` and `ui/requests/`. The session runs every
flow (`session.py`: `_open_flow`, `_save_as_flow`, `_export_flow`, ...);
Swift answers its requests and does the file I/O for the store.

- **In the kit** (`Sources/ChordNotepadKit/Files/`, tested on Linux):
  `DocumentId` (the id scheme below), `DocumentFileAccess` (file I/O by URL:
  bookmarks, facts, read, write in place, copy, rename) with
  `PlainFileAccess` (FileManager only, a bookmark that is the path; the
  tests use it, and its helpers do the app's I/O too), `BookmarkTable`,
  `FileDocumentStore` (Android's `SafDocumentStore`: the `DocumentStore`
  protocol, `adopt` for a picked file, the recent list, exports, example
  copies), `ExampleLibrary` (Android's, case for case) and
  `SessionRequests.swift`: `SessionRequest`, `presentationOf`, `PickerLaunch`
  and `pickerFor`, the question's texts (`DiscardQuestion`) and
  `RequestController` (Android's). `SessionSnapshot.request` is the pending
  request until the app answers it (`requestAnswered`).
- **In the app** (`App/`): `AppDocumentStore.make()` (the kit's store over
  `ScopedFileAccess`, its lists in Application Support), `ScopedFileAccess`
  (the real bookmarks, `startAccessingSecurityScopedResource` around each
  call, stopped only when it returned true, since a file in the container
  returns false; `NSFileCoordinator` for every read, write and rename),
  `DocumentPicking` (the seam over `UIDocumentPickerViewController`,
  `SystemDocumentPicker`), and `AppModel`'s menu actions, request handling,
  export hand-off, Examples and `openURL`. The screens: `DiscardDialog`,
  `RenameFailedDialog` with Save as…, `ExamplesSheet` (`Screens/Overlays.swift`).

**Ids.** Python compares ids as strings (Recent, the mode controller), so an
id stays the same as long as the document does:

| Id | What | Store |
|---|---|---|
| `bundle:<file>` | a song the app ships (the quick-start song at launch) | read only: Save runs Save As (`restore_draft` with `read_only`), rename is refused |
| `app:examples/<file>` | a copy Examples made | Application Support/examples, always writable, in Recent until deleted, not in Files |
| `app:exports/<uuid>/<file>` | an export waiting for the export picker | Application Support/exports, deleted after the picker, all of them at launch |
| `bookmark:<uuid>` | a song the user picked (Open, Save As) or opened from Files | its bookmark in `bookmarks.json` |

A picked file's id is a key into the bookmark table, never its URL: a URL
changes when the file moves or is renamed, and a bookmark follows it. Each
entry keeps the bookmark, the path it last resolved to (picking the same
file again gives the same id, so Recent doesn't list it twice), its name
and its location (for a message once the file is gone). A stale bookmark is
made again under the same id; one that doesn't resolve is "File not found"
and, read from Recent, drops out of the list with its bookmark, for good
(Android does the same with a revoked grant). An entry that falls off the
recent list loses its bookmark, except the newest, which is the open
document (Android's grants). The table and the recent list are JSON files in
Application Support (no UserDefaults, which would need a privacy reason).
Bookmarks are made with no options: `.withSecurityScope` is macOS only, and
on iOS the bookmark of a security-scoped URL carries the scope.

**Locations** (status lines and messages): "song.txt (Chord Notepad)" for the
app's Documents (Files' name for it), otherwise the name and the folder as
Files names it ("song.txt (iCloud Drive)", "song.txt (Downloads)"); the
shipped song and the copies are "x.txt (Examples)", an export its name.

**The flows.**

- **Open** (`open_document {}`): the session asks about changes first, then
  `PickDocumentRequest(open)`; the picker
  (`forOpeningContentTypes: [plain text, text, data]`, Android's
  text-then-anything) returns a security-scoped URL, which is adopted off the
  main actor and answered. Recent entries send `open_recent`.
- **Save** writes through the store in place (`Data.write` without
  `.atomic`, which would need a temporary file in a folder the app may not
  reach). Never saved, or the shipped song: Save As.
- **Save As**: iOS's export picker needs a file before it opens, so the app
  makes an empty one with the suggested name in its temporary folder, and
  `UIDocumentPickerViewController(forExporting:asCopy: false)` moves it where
  the user chooses; the moved file is adopted, the request answered, and the
  session writes the song into it. A failed write leaves the empty file
  there.
- **Exports** (`PICKER_CREATES_FILE` is false for iOS): the request is
  answered at once with a store file (`app:exports/...`), the session renders
  and writes it through the store, and the store's `onExportWritten` (after
  `writeBytes` for MIDI, `copyFromFile` for audio) has the app offer it with
  `forExporting:asCopy: true`. The export picker rather than the share sheet:
  Android's exports are saved to a place the user picks, and the share sheet
  would put AirDrop and Messages before "Save to Files". The status says
  "Exported MIDI: song.mid" before the user has picked a place, and a
  cancelled picker drops the file without a word (a note for the core:
  an iOS wording such as "Ready to save").
- **Export PDF stays greyed.** The core doesn't make the PDF: it sends
  `PaintPdfRequest` with the pages laid out (`PdfLayout`), and Android paints
  them itself (`PdfExporter`). iOS has no painter yet (`UIGraphicsPDFRenderer`
  would do; `BACKLOG.md`); a `PaintPdfRequest` that arrives anyway is
  cancelled.
- **The unsaved-changes question** (`ConfirmDiscardRequest`, before New,
  Open, a recent song, an example, a song from Files): a card over the
  screen with "Unsaved Changes", "Do you want to save your changes?" and
  Don't save, Cancel, Save (stacked when they don't fit one line).
- **Recent** comes from `RecentDocumentsState`: the store keeps the list
  (`recent`, `addRecent`, `setMaxRecent`), so it survives a relaunch, and a
  recent song reopens through its bookmark.
- **Examples** (Android's sheet): the songs in `examples/` (bundled as a
  folder), a tap copies one to `app:examples/` (Android's `copyFor`: the same
  copy while it is unchanged, `x (2).txt` after an edit) and opens it.
  **Quick start** stays greyed: on Android it is a tour
  (`request_quick_start`, `QuickStartContent`), not a song.
- **From Files and other apps:** `CFBundleDocumentTypes` lists plain text
  as an Alternate handler (never the default for `.txt`), and
  `LSSupportsOpeningDocumentsInPlace` opens it in place: `onOpenURL` gets a
  security-scoped URL, which is adopted and opened like a picked one. A URL
  that arrives before the session runs waits for it, after the quick-start
  song. `.cho` and `.chordpro` files aren't plain text to iOS, so they open
  through Open only.
- **iCloud and providers:** a read of a cloud file whose content isn't on the
  device asks for it and waits up to 20 s, then says "File not downloaded
  yet (open it in the Files app to download it, then try again)", rather
  than letting a coordinated read wait for the network with the session
  stuck behind it. Renaming a picked file needs its folder, which the app
  doesn't have: a refused move is "stored where Chord Notepad can't rename
  it", and the dialog offers Save As.
- **Messages** are the store's, in the desktop's wording, with the document's
  location: "File not found: song.txt (Downloads)", "Permission denied: …",
  "File too large to open (over 5 MB): …", "Failed to write file: …". An
  error of the app's own (an example it couldn't copy, a file from Files it
  can't bookmark) is a snackbar like the session's. An error snackbar takes
  up to 12 lines (a status, 3), since the reason comes after the action and
  the document ("Failed to open file:", the location, then "File not
  found"); CI run 45396385003's catalog cut it off at 3.

Deliberate differences from Android:

- Save As suggests the name as the file the picker moves. The iOS 26 export
  picker shows it in a "Save as" field (CI's `<device>-export.png`, run
  45411606228); that typing a new name there keeps the extension is a device
  item below. A rename afterwards (tap the title) works either way.
- Exports go through the export picker after the file is written, so a
  failed export leaves nothing behind, and the status line names the export
  before it is saved.
- Errors are snackbars, as in the main-screen slice (Android: dialogs).
- Example copies, the recent list and the bookmarks live in Application
  Support: not in Files, not removed by anything but the app.
- No Quick Start tour yet, and no Export PDF.

What CI checks: `SessionTests` drives the real store on files in the app's
Documents with a stand-in for the pickers (Open, Save, Save As, Export
MIDI, Recent after a second store reads the lists, a song from Files
renamed, an example, a song that has gone, New's question). Audio export
needs the real player's SoundFont, which the test's FakePlayer hasn't (the
core refuses before asking for a file), so `-CNScreen export` runs it in the
launched app: `export.json` must report a WAV of more than 10 KB that the
store wrote from the export's worker, and `<device>-export.png` shows the
export picker that follows.

What CI doesn't test (see the device checklist below):
`UIDocumentPickerViewController` driven by a person (Open, the Save As
move, choosing where the export goes) and the security scope of a URL from it or from Files, a file
outside the container (iCloud Drive, On My iPhone, a third-party provider),
a bookmark resolved after a reboot or an app update, an iCloud file that
isn't downloaded, renaming a picked file, a song opened from the Files app
or another app's "Open in…" (`onOpenURL` is called directly), an export
whose picker is cancelled, and the live dialogs.

### The player's sheets and the ribbon's tools

The fifth slice, ported from Android's `ui/sheets/` (`PickerSheet.kt`,
`PlayerSheets.kt`, `SongDefaultsSheet.kt`, `SheetRoute.kt`), `ui/tools/`
(`ToolDialogs.kt`, `ToolForms.kt`, `ToolActions.kt`, `DirectiveVerdict.kt`),
`ui/identifier/` and the ribbon's four tools (`EditRibbon.kt`). The session
does the work (`transpose`, `request_insert_directive` and `check_directive`,
`capo_advice_*`, `identifier_*`, `insert_chord`, `set_multiplier_pct`,
`set_bpm_text`, `set_time_signature`, `set_key`, `write_song_defaults`);
nothing in the core or the schema changed.

- **In the kit** (`Sources/ChordNotepadKit/Sheets/` and `Tools/`, tested on
  Linux): the routes (`MainRoute.instrument(family:)`, `.speed(manual:)`,
  `.insert`, `.transpose(selection:)`, `.identify`, with Android's `back()`
  and `afterSheetDismissed()`), the speed's limits, snapping and texts
  (`parseSpeedPct`, `snapSpeedPct`, `speedPctText`, `SpeedSlider`,
  `SpeedEntry`), Playback settings' rows (`songDefaultRows`,
  `songDefaultChoice`, `anythingToWrite`, `canWrite`), `insertEntries`,
  `TransposeForm`, `DirectiveKind` (its fields, title and hint),
  `DirectiveForm`, `DirectiveVerdict` (the session's check for exactly these
  fields; the messages in the fields' order, since a JSON object has none in
  Swift), `loopChoices`, `keyChoices`, `capoChoice`, `capoCanApply`,
  `PianoKeyboard`, `KeyLook`, `IdentifierModel`, `identifierLayout`,
  `RibbonEdges`, and the tools' commands on `EditorModel` (the text first,
  the selection and cursor in code points). `SheetController.swift` is one
  reducer, `MainUiState.handle(_:snapshot:editor:)`: every tap in a sheet, a
  tool or their dialogs is a `SheetEvent`, and it returns the commands, the
  request it answered, a notice or where to put the caret. The dialogs'
  fields are the screen's (`MainUiState.tools`), so the catalog sets them.
  `SessionSnapshot` keeps `CapoAdviceState`, `IdentifierState` and
  `DirectiveCheck`; an `InsertDirectiveRequest` is a dialog now, not
  cancelled.
- **In the app**: `Screens/PlayerSheets.swift` (`BottomSheet`, Android's
  `PickerSheet`: a handle, the title row, the body, the actions under a
  divider; `SheetRow`, `SheetSection`, the text and Done buttons, the radio
  mark, `DropdownChip`; the Voicing, Instrument, Speed, Playback settings and
  Insert sheets), `Tools/ToolDialogs.swift` (`ToolDialog`, `OutlinedField`,
  `DialogPicker`, `ValueStepper`, `Spinner`; Manual…, the tempo, Transpose,
  Suggest Capo, the Insert dialogs) and `Tools/ChordIdentifierView.swift`
  (the identifier and `PianoView`, a `Canvas`). `MainScreen` draws them over
  itself from the route, the pending request and `CapoAdviceState.active`;
  `AppModel.sheet(_:)` runs the reducer. The ribbon gains Insert, Transpose,
  Capo and Identify (Android's icons) and scrolls sideways when it doesn't
  fit.
- **The flows**, as Android's: Voicing and Instrument apply a choice at once
  and stay open (Done closes); Instrument opens a family's programs, ← goes
  back. Speed sends each new 5 % stop while the finger moves; Manual… checks
  12.5–400 before OK. Playback settings shows a value a directive sets as
  "Set by `{bpm: 90}` in the song · Edit" (Edit goes to Edit mode with the
  caret on the directive); the others are dropdowns (the tempo a typed
  dialog) for this song only; Write into song puts the missing directives at
  the top; while a song plays a tap says why not. Insert asks the session for
  the kind's dialog at the caret; the dialog sends its fields to
  `check_directive` as they change and Insert waits for a clean reply for
  exactly those fields; Insert Capo's Suggest drops the request and opens
  Suggest Capo. Transpose knows when it opens whether there is a selection.
  The ribbon's Capo opens Suggest Capo for the selection or the song; the
  recommended row is chosen, a new voicing or new rows choose it again, Apply
  waits while a song plays. Identify clears the notes, a key tap toggles it,
  a long press sounds it, the typed notes follow the keys until the user
  types, a candidate tap plays it (long press rolled, double tap inserts),
  Insert puts the chord and a space at the editor's caret.
- **Live check:** `SessionTests` drives the speed sheet (a drag, a refused
  and an accepted Manual… value, Reset), Playback settings' Edit, and from
  the ribbon Transpose, Insert › Tempo with the session's check, Suggest Capo
  and the identifier's Insert, checking the editor's text after each.
  `-CNScreen speed`, `insert`, `capo` and `identify` open each live for CI's
  screenshots and write `Diagnostics/tool-<name>.json` when ready.

Deliberate differences from Android:

- The sheets and the tools' dialogs are drawn by the screen over a dimmed
  copy of itself (a panel from the bottom with a handle, cards for the
  dialogs), not iOS sheets and alerts: a dialog (Manual…, the tempo) stacks
  over its sheet as on Android, and the catalog draws them. A tap on the
  dimmed screen or a swipe down on the handle closes a sheet.
- The dropdowns (Playback settings' time and key, the Insert dialogs'
  pickers, Suggest Capo's voicing) are iOS pop-up menus with the same
  choices.
- The speed slider is drawn in Material's shape (a thick track, a bar
  thumb, a stop dot) instead of a UISlider, so it looks like Android's and
  the catalog draws it; VoiceOver adjusts it in 5 % steps.
- A greyed value's reason in Playback settings is a short snackbar over the
  sheet (Android: a Toast).
- The ribbon's › chevron scrolls to the end of the row (Android scrolls
  140 dp; on a phone that is the end).
- The Insert dialogs, Manual… and the tempo don't keep their fields across a
  relaunch (Android saves them for a rotation; on iOS a rotation keeps them
  anyway).

What CI doesn't test: a finger on the slider, a swipe down on a sheet, the
pop-up menus, a long press on a piano key, Play or a candidate, a double tap
on a candidate (the session test sends the same events the gestures send),
the keyboard over the Insert dialogs and the identifier's field, the live
sound of the identifier's notes (the session test has the FakePlayer;
`-CNScreen identify` plays them in the simulator), VoiceOver, rotation with a
sheet open.

### Settings, About and Licences

The sixth slice, ported from Android's `ui/settings/` (`SettingsScreen.kt`,
`SettingsController.kt`, `SettingsDraft.kt`, `SettingsWidgets.kt`,
`GeneralPages.kt`, `VoicingsPage.kt`, `VoicingForm.kt`, `VoicingFormView.kt`,
`VoicingSchema.kt`), `ui/about/` and `about/` (`Licences.kt`, `BuildInfo.kt`).
The session runs the settings edit (`begin_settings_edit`, `commit_settings`,
`cancel_settings_edit`, `discard_settings_problems`, the voicing commands,
`request_voicing_editor_schema`); nothing in the core or the schema changed.

- **In the kit** (`Sources/ChordNotepadKit/Settings/` and `About/`, tested on
  Linux): `SettingsDraft` (the key always American, as the config keeps it;
  `respellKey`, `shownKey`), `NumberSetting` (ranges, labels, the range
  text), `SettingsController` (Android's, as a value: each call queues its
  commands in `outbox`, which the app sends; the phases, `SettingsNav`,
  `SettingsDialog`, the problems' lines, the bar's title, the restored
  banner, `showing(_:nav:)` for the catalog), `EditorSchema` (the form
  schema), `buildForm` and `FormItem`, `VoicingEdits`, `PendingEdits`,
  `stepNumber` and `canStep` (decimal arithmetic, strict number parsing),
  `FieldEcho` (Android's `StateTextField`: typed text stays until the value
  becomes something the field didn't send), `ErrorsBanner` (the form's
  banner after 400 ms), `addVoicingSections`, `Licences` (the list, its
  sections and texts), `AboutBuildInfo`, `AboutLinks`, `AboutTexts` and
  `SettingsTexts` (Android's strings word for word). `SessionSnapshot` keeps
  `VoicingEditorState` and the schema. `MainRoute` gains `.settings`,
  `.about`, `.licences` and `.licence(id:fromAbout:)` with Android's
  `Pages.parent` and `onSongOpened`.
- **In the app** (`Screens/`): `SettingsScreen` (`SettingsView.swift`: the
  bar, the pages, General, Playback, the dialogs), `VoicingsView.swift` (the
  list, Add voicing, the voicing's detail, the form by kind, the records as
  cards or a table through `WeightedRow`), `SettingsWidgets.swift` (the
  outlined field with its label on the outline, − and +, the dropdown, the
  Material switch, the segmented buttons, section titles, the error banner,
  list rows, `PageColumn`) and `AboutView.swift` (About, the licences, a
  licence's text). `AppModel` keeps the controller while Settings is open
  (`openSettings`, `settingsAct`: the commands go out, a typed number is
  saved 400 ms after the last change, the screen goes once the edit ends)
  and the parsed schema; `MainScreen` draws the page over itself, under the
  snackbar.
- **Licences.** Android's list is its own (`assets/licenses/components.json`),
  not the core's: `core/chordnotepad/services/licence_catalog.py` and
  `resources/licenses/components.json` are the desktop builds' inventory
  (`tests/test_licences.py` ties each entry to those builds and their
  pins). So iOS has its own too, `ios/Licenses/components.json` in Android's
  format, listing what the iOS app ships: the app and its logo; CPython
  3.14.10 from BeeWare's support package 3.14-b14 with OpenSSL 3.5.9,
  libFFI 3.4.7, BZip2 1.0.8, XZ 5.6.4, mpdecimal 4.0.0 and Zstandard 1.5.7
  (its `VERSIONS` file) and Expat; FluidSynth 2.6.1 (LGPL-2.1, a separate
  dynamic framework, unmodified, its source and the build script named) and
  GCE-Math; the Python packages at `android/requirements.txt`'s pins without
  chardet; GeneralUser GS, Bravura, Material Design Icons and Google's
  Material Icons (the Settings icons). SQLite and zlib are the system's.
  The user guide isn't shipped yet, so neither is its group. The "Licences"
  build phase (`ios/tools/copy_licences.py`) copies the list and the texts it
  names from `resources/licenses/texts` into `<app>/licenses`; a missing
  text fails the build. `licence_catalog.detect_build` still returns None
  on iOS; nothing there calls it.
- **The flows**, as Android's: ☰ › Settings begins the edit (and asks for the
  schema once per process); a phone shows the pages list, then a page, then
  the voicing form; from 600 pt the pages list stays on the left (General
  when none is picked), and the voicings list and form sit side by side when
  the window less the pages list is 720 pt or more (an iPad on its side). A
  switch, a dropdown or the notation is saved at once (`commit_settings`); a
  typed number 400 ms after the last change, only when it is a whole number
  in range (else its range shows in red and the text is staged in Python
  for next time). Every voicing command is followed by `commit_settings`;
  the core writes each voicing's valid fields and returns the rest as
  `problems` (a value it can't build is never saved). ← goes up a page, then
  leaves (`cancel_settings_edit`), asking first while something is wrong
  (Discard, or Edit to go to the first). Values kept from last time come
  back with the restored banner. A built-in is read-only (`select_builtin`)
  with Copy to a new voicing. Edit voicings… in the Voicing sheet opens
  Settings › Voicings. About shows the version, build type, build number
  and commit (Info.plist), the licence (the app's own text), the source and
  the FOSS flavour's Ko-fi link, then Open source licences; each opens in
  the browser only when tapped.
- **Live check:** `SessionTests` toggles word wrap (saved and applied to the
  editor), types a tempo (nothing until the typing rests, then saved), one
  out of range (staged, not saved), makes a voicing from a blank fretboard,
  renames it, types its strings (in the Voicing sheet), then a string that
  isn't a note (refused: a problem, the voicing invalid, leaving asks, Edit
  goes back to it), fixes and removes it, opens Settings from Edit
  voicings…, and checks About's routes and every licence text in the
  bundle. `-CNScreen settings` (General), `voicings` (the built-in standard
  guitar's form) and `about` open each live for CI's screenshots.

Deliberate differences from Android:

- The pages are drawn by the main screen over itself (no navigation stack),
  with Android's bar; there is no edge swipe back.
- The dialogs (problems, remove, model, rename) are cards over a dimmed
  screen, like the other dialogs, so the catalog draws them.
- The dropdowns and Add voicing's menu are iOS pop-up menus with the same
  choices and group titles; the catalog draws Add voicing's menu as a card.
- Switches are drawn in Material's shape (a UISwitch looks like iOS's and
  the catalog can't draw it); VoiceOver reads them as switches.
- The voicing form's number fields bring up the numbers and punctuation
  keyboard (the number and decimal pads have no minus sign, and weights are
  negative); General's and Playback's take the number pad.
- The rename dialog opens with the caret after the name; Android selects
  the whole name, ready to type over (SwiftUI's text field can't select).
- No support card above the pages: the FOSS flavour hides it (no purchase),
  and iOS has no StoreKit yet.
- No state restoration: SwiftUI keeps Settings across a rotation, and the
  app doesn't bring a screen back after the system ends it, so Android's
  three `snapshot()`/`restore()` cases have no counterpart.
- The licences list has no Android libraries group (no AboutLibraries);
  Apple's frameworks are the system's.
- About's build type is Debug or Release of the Xcode build; the build
  number is CI's run number.

What CI doesn't test: a person typing into the fields (the echo of a late
state, the software keyboard over a field low on the page, the keyboard's
Done), the pop-up menus, a tap on the switches, Edit in the problems
question putting the cursor in a number field, scrolling a long form on a
small phone, links opening in Safari, rotation with Settings open (two
panes to one), VoiceOver.

### Preview catalog

`PreviewCatalog.screens` lists every screen with the fixtures it is shown
with and the windows it is drawn in; adding a screen is one line there.
`#Preview`s use the same `PreviewCatalog.scene("<scene>")`. `CatalogTests`
renders each entry with `ImageRenderer` at iPhone 17 (402×874 pt, @3x) and
iPad Air 11-inch (820×1180 pt, @2x), and on their sides (874×402,
1180×820) where the layout differs, light and dark, default and
`accessibility2` text: 440 PNGs.

| Screen | Scenes | Windows |
|---|---|---|
| `edit` | `scarborough_edit`, `empty_song`, `editor_mid_edit`, `editor_european` | iPhone, iPad, iPad on its side |
| `play` | the three Scarborough Fair scenes, `play_with_chord_sheet`, `chord_sheet_staff`, `quick_start_edit` (no sheet) | all four |
| `keyboard` | `scarborough_edit` in Edit with a grey stand-in for the keyboard (the header collapses on the phone on its side) | iPhone on its side, iPhone |
| `menu` | `scarborough_edit`; `files_recent` (the recent songs) | iPhone, iPad |
| `rename` | `scarborough_edit`; `errors` for the refused rename with Save as… | iPhone, iPad |
| `discard` | `discard_question` in Edit: the unsaved-changes question | iPhone, iPad |
| `export`, `export_edit` | `export_done`: "Exported MIDI: …" in Play's status line; in Edit as a snackbar | iPhone, iPad; iPhone |
| `open_error` | `errors` in Play with the open failure as a snackbar | iPhone, iPad |
| `examples` | the Examples sheet, from the bundle's `examples/` | iPhone |
| `diagnostics` | a sample self-test report | iPhone, iPad |
| `voicing`, `instrument`, `instrument_programs`, `speed`, `speed_manual`, `song_defaults` | `player_sheets` in Play: the sheet over the screen (the Guitar family's programs; Manual… over the speed sheet) | iPhone, iPad |
| `insert_sheet`, `transpose` | `grace_edit` in Edit: the Insert sheet; Transpose at +2 for the whole song | iPhone, iPad |
| `insert` | the six `insert_*` scenes: each Insert dialog as it opens | iPhone |
| `insert_error` | `insert_bpm` with "999" typed: the session's check under the field, Insert off | iPhone, iPad |
| `capo` | `capo_advice`: Suggest Capo scored | iPhone, iPad |
| `identify` | `identifier_cmaj7`, Cmaj7 picked: full screen, side by side on the phone on its side, a card on the iPad | iPhone, iPad, iPhone on its side |
| `settings`, `settings_general`, `settings_playback` | `settings_open`: the pages list (two panes on the iPad: General), General, Playback | iPhone, iPad; iPhone; iPhone, iPad |
| `settings_voicings`, `settings_add_voicing` | `settings_voicing_form`: the Voicings list; with Add voicing's menu open (a stand-in) | iPhone, iPad; iPhone |
| `settings_voicing_form` | My 7-String's form; on the iPad on its side the list and the form side by side | iPhone, iPad, iPad on its side |
| `settings_voicing_voices`, `settings_voicing_ensemble` | Jazz Vocal Trio: its voices as cards (the form scrolled to them, drawn from its records item); the whole form as a table | iPhone; iPad on its side |
| `settings_voicing_refused`, `settings_problems` | `settings_voicing_refused`: the banner and the red fields; leaving with them and a tempo of 1000 | iPhone, iPad |
| `settings_builtin`, `settings_rename` | the standard guitar read-only with Copy; My 7-String's rename dialog | iPhone, iPad on its side; iPhone |
| `about`, `licences`, `licence` | About (a sample build), the licences from the bundle's list, FluidSynth's page with its text | iPhone, iPad; iPhone, iPad; iPhone |

The chord sheet's strip draws there too: it is a SwiftUI `Canvas`, and only
its scroll view (live only) is UIKit. ImageRenderer can't draw a
`ScrollView`, a `TextField`, a sheet or an alert (or other UIKit-backed
views), so a screen takes `scrolls: false` in the catalog and draws plain
SwiftUI: the menu doesn't scroll, the rename field is drawn as text, and
what is presented as a sheet live (Diagnostics, the player's lists) is drawn
on its own. The editor's UITextView is one of those: the catalog draws
`EditorPreview`, the same `EditorModel` (folded from the scene's outputs)
laid out and drawn by TextKit 1 into a `Canvas` the way the live view lays
it out (the same storage attributes from `styleRuns`, container width, chord
breaks and insets), so the playhead marker lands where the live view puts
it, and the selection as a 25 % tint of the primary colour. It has no caret,
and the live view's selection colour is the system's; unwrapped lines run
past the right edge, as the live view shows them before it is scrolled.

### App Store requirements already in place

`ITSAppUsesNonExemptEncryption = NO` (the app uses no encryption beyond
the system's); `PrivacyInfo.xcprivacy` with no tracking and no collected
data, and the required-reason APIs the embedded CPython links: file
timestamps (`C617.1`, files in the container), system boot time (`35F9.1`,
`time.monotonic` and Swift's clocks) and disk space (`E174.1`, `statvfs` is
in the binary), plus `3B52.1` for the size of a song the user picked or
opened from Files; add the user defaults category if the app ever uses
them. `_ssl` and `_hashlib` (which
link OpenSSL, on Apple's list of SDKs that need a manifest) get one each
from `packaging/ios/privacy/`. The icon is one 1024 px PNG, flattened on the
Android icon's cream (`ios/tools/make_app_icon.py`, Inkscape and Pillow).

## CI

`.github/workflows/ios.yml` runs on every push to main that touches `ios/`,
`core/`, `packaging/ios/`, the schema, the Python pins, the SoundFont, the
glyph export script, Android's chord sheet and voicing form fixtures, the
help screenshots' songs the scenes use (the kit's tests read them), the
examples, Android's icons the asset catalog copies (the drawables and
`SettingsIcons.kt`), the licence texts, Android's FOSS support link and
`VERSION`, and by hand (workflow_dispatch). Each push gets its own run; a
newer one doesn't cancel an older one.
`build.yml` ignores pushes that touch only `ios/`, `packaging/ios/`,
`ios.yml` or this file. Two jobs on `macos-26` (arm64):

- **kit:** `swift test` on the Mac host with setup-python's 3.14 (through
  `CN_PYTHON_PKGCONFIG=python3-embed`, set only for that step), the app's
  packages from `build_python_bundle.py` as `CN_SITE_PACKAGES`, and the
  macOS app's own libfluidsynth (`packaging/macos/build_fluidsynth.sh`,
  cached) as `CHORD_NOTEPAD_LIBFLUIDSYNTH`.
- **app:** the frameworks (cached on the scripts, the pins and the Xcode
  version), the Python bundle, XcodeGen, one `build-for-testing` for the
  simulator, `test-without-building` on the iPhone and the iPad (the
  session test with the FakePlayer, the blocking offline render and the
  diagnostics zip; the
  catalog on the iPhone only, since it renders both sizes anyway), the
  real app launched on both simulators for screenshots and the self-test,
  the live CoreAudio check (non-blocking: a runner may have no audio
  device), and a Release `generic/platform=iOS` build with
  `CODE_SIGNING_ALLOWED=NO`, checked for the privacy manifests, the
  compiled icon and the stdlib.

| Pin | Value | Where |
|---|---|---|
| Xcode | 26.5 (the image's iOS 26.5 runtime matches its SDK) | `ios/.xcode-version` |
| Runner | `macos-26` | `ios.yml` |
| Python.xcframework | BeeWare Python-Apple-support `3.14-b14` (3.14.10), sha256 `703ff822…c1ee` | `packaging/ios/fetch_python.sh` |
| FluidSynth | 2.6.1 + gcem `012ae73`, the macOS build's hashes | `packaging/ios/build_fluidsynth.sh` |
| XcodeGen | 2.46.0, `xcodegen.zip` sha256 `4d9e34b6…6806` | `ios.yml` |
| Simulators | iPhone 17 and iPad Air 11-inch (M4), newest runtime | `ios/tools/ci_simulators.py` |

Artifacts of each run:

- `ios-catalog`: the catalog PNGs,
  `<screen>-<scene>-<iphone|ipad>-<light|dark>-<default|large>.png`.
- `ios-screenshots`: `<iphone|ipad>-main.png` (the quick-start song in
  Play, as it opens), `<iphone|ipad>-menu.png` (`-CNScreen menu`),
  `<iphone|ipad>-selftest.png` (Diagnostics),
  `<iphone|ipad>-chordsheet.png` (Play with the chord sheet shown, its
  buffer from the live session), `<iphone|ipad>-editor.png` (Edit after the
  app typed a long chord line into the editor, the session's highlight
  painted, the keyboard up), `<iphone|ipad>-speed.png`, `-insert.png`,
  `-capo.png` and `-identify.png` (the speed sheet at 125 %, Insert › Tempo
  with the keyboard up, Suggest Capo scored, the identifier with Cmaj7
  picked; `tool-<name>.json` says each got there), `<iphone|ipad>-settings.png`,
  `-voicings.png` and `-about.png` (Settings › General, Settings › Voicings
  with the standard guitar's form, About),
  `<iphone|ipad>-export.png` (the export picker
  over the song after an audio export), the app's Diagnostics
  folder from each simulator (`launch.json`, `chordsheet.json`, `editor.json`,
  `export.json`, `selftest.json` with the live
  audio result, the core's log) and `<device>-app.log` (the unified log of
  the app's process).
- `ios-results`: the `.xcresult` bundles (open in Xcode, or
  `xcrun xcresulttool` on a Mac; the catalog PNGs and the test's
  `selftest.json`, `chordsheet-live.png`, `editor-live.png` and `play-live.png` are attached) and the xcodebuild logs.
- `ios-kit-tests`: the kit's `swift test` output on macOS.

`gh run download <run> -n ios-screenshots` fetches one on Linux.

What the first green run (2026-11-24, Xcode 26.5, iOS 26.5 simulators)
measured: Python boot 0.15–0.6 s, session start 3.2–4.4 s (most of it the
core's imports, music21 included), first song text about 4 s; the offline
render peaks at about 5700 of 32767; the live player started on both
simulators (route Speaker, 48 kHz, 10 ms buffer); the simulator app is
141 MB and the device build 114 MB (the SoundFont is 32 MB of it). The kit's
45 tests pass on the Mac host as on Linux, fixtures included. The first
layout issue the catalog showed: at accessibility text sizes the shell's
title truncated beside its three buttons; the main screen's app bar has
Android's buttons only and drops the tabs' captions there on a phone.

To build the same on a Mac (S0's `mac_bootstrap.sh` will do this):

```sh
packaging/ios/build_fluidsynth.sh ios/build/Frameworks
packaging/ios/fetch_python.sh ios/build/Frameworks python3.14
python3.14 -I packaging/ios/build_python_bundle.py ios/build/python-bundle
xcodegen generate --spec ios/project.yml
open ios/ChordNotepad.xcodeproj
```

## Development loops

1. **Linux, every change:** `make ios-kit-test`. Everything below the UI
   (the interpreter, the bridge, offsets, the buffer decoder, the core's
   output) is tested here against the real core.
2. **CI, every push to `ios/**`, `core/**`, `packaging/ios/**` or the
   schema** (`ios.yml`, "CI" below): kit tests on a Mac host, `xcodebuild
   test` on an iPhone and an iPad simulator with an offline synth render,
   the preview catalog rendered to PNGs, screenshots of the running app and
   an unsigned device build.
3. **TestFlight, after enrollment** (section E): her iPhone installs the
   build under her own Apple ID and runs the scripted checklist.

## Device sessions

Her devices are borrowed for 2–3 hours at a time, so each session is
prepared on Linux and CI first: nothing is downloaded or built on her
machines, and every session ends with artifacts analysed offline.

| # | Session | Devices | When | Length |
|---|---|---|---|---|
| S0 | Bootstrap and enrollment | MacBook (iPhone for 10 min) | after D is green, right before E | 2.5 h |
| U1 | Simulator runtimes and a re-verify | MacBook, overnight under his user | after S0 | – |
| T1…Tn | TestFlight smoke | iPhone only | after E, then each screen milestone | 30 min |
| S1 | Layout polish (needs Metal, so not a VM) | MacBook | mid-F | 2.5 h |
| S2 | Device debugging and Instruments | MacBook and iPhone, or the VM and iPhone | late F | 3 h |
| S3 | Mac App Store sandbox for the Qt app | MacBook | later | 2 h |

**S0, bootstrap and enrollment.** Before: the Xcode `.xip` (matched to her
macOS and CI's Xcode), the iOS runtime `.dmg` and xcodegen on a USB SSD;
`ios/tools/mac_bootstrap.sh` and a green CI; her macOS version, free disk
(60 GB or more) and iPhone iOS version known. Agenda: she creates his user
(0–10); copy and start `xip -x` (10–20); enrollment in the Apple Developer
app (20–85); Xcode into /Applications, licence, `-runFirstLaunch`, `simctl
runtime add` with her admin password (85–110); `mac_bootstrap.sh --verify`,
then `devicectl list devices` with her iPhone trusted to record UDID, model
and iOS version, Developer Mode only if she agrees (110–135); session log
(135–150). Bring back the verify report, the enrollment confirmation, the
UDID (a secret) and a screenshot. Fallback: ID rejected, bootstrap only and
a support case; Xcode won't install, enrollment only.

**T sessions (30 min, no Mac).** Before: her invite accepted, the build
processed and 30 or more days from expiry, the checklist printed. Agenda:
install; under a screen recording, the quick-start song, tap a chord and
hear it, play and pause, background and resume, the silent switch, a
headphone or Bluetooth route change, an alarm interruption (later the Files
picker and a StoreKit purchase); then Export diagnostics and TestFlight
feedback. Fallback: a screenshot of the install error and the self-test
screen.

**S1, layout polish.** Before: the CI catalog PNGs reviewed offline into a
numbered issue list. Agenda: readiness check and generate (0–15); fix issues
in Previews and the simulator, iPad split view, rotation, keyboard, Dynamic
Type, one commit per issue (15–125); push and record what snapshots can't
show (125–150). Fallback: snapshots plus the simulator if Previews break.

**S2, device debugging and Instruments.** Before: UDID registered, the CI
development IPA and dSYM on the SSD, Developer Mode on, Xcode matching her
iOS, a repro list from TestFlight logs. Agenda: connect and install with
`devicectl device install app` (0–25, device preparation can take 10–30
min); Instruments, saving each `.trace`: Audio System Trace with signposts
for tap-to-sound latency, Time Profiler for launch including the music21
import, Allocations during playback (25–90); LLDB on the open issues with
`log stream` on our subsystem (90–150); copy everything off (150–170).
Fallback: simulator Instruments and the TestFlight build's timing logs.

### Readiness checklist (before each session)

`ios/tools/readiness.py` (to come) checks CI is green, the artifacts are
there (IPA, dSYM, catalog), the TestFlight build is processed and when it
expires, her tester status and the issue list. By hand:

- [ ] her consent, and the date
- [ ] her macOS version and free disk space
- [ ] her iPhone's iOS version against the pinned Xcode
- [ ] Developer Mode on (S2 only)
- [ ] the downloads already on the SSD
- [ ] a numbered issue list, each issue with its expected result. Standing
  item until a device run clears it: cold-launch the app five times and
  watch for an abort while FluidSynth starts CoreAudio. CI's iPad simulator
  aborted once with "CoreAudio Initialize: RPC timeout. Apparently
  deadlocked." (run 45341096346). The session starts off the main thread,
  so it's most likely the runner's audio server, but only a device can
  show that. Standing items for file handling, until a device run clears
  them (docs "Files", what CI doesn't test), first of all Save As: does the
  URL the export picker returns after moving the empty file stay writable
  and bookmarkable?
  1. Save As into iCloud Drive and into On My iPhone: the song is written
     there, the title shows its name, Recent lists it. Can the name be
     changed in the picker? Into a folder that already has the name?
  2. Open… a song in iCloud Drive, one in On My iPhone and one from a
     third-party provider if she has one; change and Save each in place.
  3. Quit the app (swipe it away), reopen, reopen each from Recent; again
     after a reboot.
  4. A song in iCloud Drive removed from the device ("Remove Download"),
     then opened from Recent online and in flight mode: it downloads, or
     the "not downloaded yet" message after 20 s.
  5. Rename (tap the title) a picked song: renamed, or the Save As offer.
  6. Export MIDI and audio: the export picker after the render, the file
     plays in Files; cancel the picker once.
  7. In Files, long-press a `.txt` › Share or Open in › Chord Notepad, with
     the app running and with it closed; a `.txt` from Mail's attachments.
  8. Delete a recent song in Files, then open it from Recent: "File not
     found" and it leaves the list.

  Standing items for Settings, About and the licences:
  1. General: change the font family, size (type a value and wait, then out
     of range), word wrap, notation, default key and recent files; each shows
     in the editor or the menus. Playback: tempo, time signature, clicked
     chords.
  2. A wrong number, then ←: the question; Edit puts the cursor in the field.
     Quit the app with a wrong number, reopen Settings: the restored banner.
  3. Voicings on a phone upright and on its side, and on an iPad both ways:
     Add voicing's menu, rename, type a tuning that isn't a note (red, the
     banner after a moment), Edit voicings… from the Voicing sheet, a
     built-in's Copy, the ensemble's voices (↑, ↓, copy, ✕, Add voice), the
     keyboard over a field low on the page.
  4. About: each link opens Safari; the licence pages scroll and their text
     selects.

  Standing items for the sheets and the tools:
  1. Speed: drag the slider end to end and back (the value follows, the
     song's tempo changes while it plays), Manual… with the decimal pad,
     Reset; swipe the sheet down and tap the dimmed screen to close it.
  2. Playback settings on a song without directives: pick a time signature
     and a key from the menus, type a tempo, Write into song; on a song with
     `{bpm: 90}`, tap Edit (Edit mode, the caret on the directive, the
     keyboard up); while a song plays, tap a value (the reason shows).
  3. Each Insert dialog with the keyboard up: a bad tempo (the reason under
     the field, Insert off), a label, a loop back to it, a capo, Suggest.
  4. Transpose with and without a selection; Suggest Capo with another
     voicing, Apply.
  5. Identify: tap and long-press keys, type notes, long-press Play and a
     candidate (rolled), double-tap a candidate (inserted), on the phone
     upright and on its side and on an iPad; the notes sound.
  6. The ribbon on the smallest phone: drag it sideways, tap ›.
- [ ] the checklist printed, screen recording on
- [ ] where the artifacts go
- [ ] which fallback agenda applies
- [ ] the session log template

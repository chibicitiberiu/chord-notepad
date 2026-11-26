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
tools"), Settings, About and the licences ("Settings, About and
Licences"), the user guide, the Quick Start tour and Export PDF ("The user guide,
Quick Start and Export PDF"), and the editor's remaining features: Find and
Replace, the font settings, a pinch on the text, the keyboard shortcuts and
the side column's width kept ("Find, the font, the pinch and the keys"), and the
platform glue: interruptions, route changes and the background pausing as on
Android, iPad multitasking widths, VoiceOver labels and the iOS export
status ("Audio, multitasking and accessibility"). Every launch reopens the
last song with its unsaved changes ("The last song"). Ready and waiting for the
Apple Developer account (2026-11-25): the release lanes in `ios.yml`
(TestFlight, a development IPA; "Release lanes"), the notarized DMG in
`build.yml` (`docs/RELEASE.md`), and the session tools in `ios/tools/`
("Enrollment day", "Device sessions"). Still to come: enrollment itself, then
what `BACKLOG.md` lists.

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
                                ScopedFileAccess, DocumentPicking), diagnostics, self-test, PdfPainter
                                (UIGraphicsPDFRenderer, PdfReport), HelpShotSongs (CI's help screenshots),
                                AppShortcuts (the menu commands, UserDefaults preferences)
    Screens/                    MainScreen (pure), MainView (live), AppBar, PlayerBar, PlayerSheets (the
                                player's and Insert's sheets), Overlays (menu, dialogs, snackbar),
                                DiagnosticsView (self-test, export), SettingsView, VoicingsView,
                                SettingsWidgets, AboutView (About, the licences), UserGuideView (the
                                guide's web view and scheme handler), QuickStartView (the tour)
    Tools/                      ToolDialogs (Transpose, Suggest Capo, the Insert dialogs, Manual… speed,
                                the tempo), ChordIdentifierView (the identifier and its piano)
    Editor/                     the song editor: EditorTextView and EditorHost, EditorController, SongEditor,
                                PlayText (Play mode), EditRibbon, FindBarView, EditorAppearance, EditorPreview,
                                EditorScript (CI)
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
      Generated/PythonText.swift  what Python's re folds and calls a word character (the find bar)
      OffsetMapper.swift        code points <-> UTF-16
      SheetBuffer.swift         op-buffer v2 decoder (values, no drawing)
      ChordSheet/               the chord sheet's logic: geometry, theme, split, loader, painter
      Editor/                   the song editor's logic: EditorModel, EditHistory, text arithmetic,
                                styles, paste and wrap, scrolling, shortcuts, directive hints, find and
                                replace, the pinch
      Main/                     the main screen's logic: modes, layout, playback, rename, menus,
                                playhead gestures, snackbars, the screen's own state, AppColors, the app's
                                shortcuts, UiPreferences
      Sheets/                   the player's sheets: routes, speed, Playback settings' rows, Insert's
                                entries, SheetController (every tap in a sheet or a tool, as commands)
      Tools/                    the ribbon's tools: forms, the session's check, Suggest Capo's pick,
                                the identifier's piano and model, RibbonEdges
      Files/                    file handling's logic: document ids, the store (FileDocumentStore over
                                DocumentFileAccess), the bookmark table, examples, the session's requests,
                                Export PDF's painting (PdfExporter, paintPdf, paperFor)
      Settings/                 Settings' logic: the draft, SettingsController, the voicing form's schema
                                and items, pending edits, steppers, the field's echo, the texts
      About/                    the licence list and texts, About's build info, links and texts
      Help/                     Quick Start's pager and snippet runs, the guide's links, the launch kind
      Python/chordnotepad_ios/  the Python glue (host.py, diagnostics.py), shipped as a resource
    Tests/ChordNotepadKitTests/ XCTest; python/ holds a tiny test module
  Fixtures/                     recorded session output per scene, for the preview catalog
  Licenses/components.json      the licences of what the iOS app ships (About › Open source licences)
  tools/
    gen_swift_bridge.py         writes Generated/Bridge.swift from the schema
    gen_find_tables.py          writes Generated/PythonText.swift from Python's re
    install_python.sh           the app's "Install Python" build phase
    export_glyphs.sh            the "Chord sheet glyphs" build phase
    make_app_icon.py            renders the icon from resources/chord-notepad-icon.svg
    mdi_assets.py               Android's Material Design Icons as SVG image sets (and the Settings
                                and About icons from their Kotlin paths)
    copy_licences.py            the "Licences" build phase: the list and its texts into the app
    build_help.sh               the user guide's iOS edition (sphinx -t ios), for the "User guide" phase
    help_images.py, help_shots.json   the guide's iOS screenshots from CI's artifacts
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
make ios-kit-test      # swift test: 493 tests, about 50 s after the first build
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
  generated Swift is stale; `tests/test_ios_find_tables.py` while
  `Generated/PythonText.swift` is (`python3 -I ios/tools/gen_find_tables.py`
  with a 3.14 Python rewrites it).
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
| `FindReplaceTests` | the core's `test_text_ops.py` find cases (case, whole words, literal queries, no overlaps, code points, `next_match`), Python's own folds (`ſ`, `ς`, the Kelvin sign, `ß`), the count's texts; the matching against the core's `text_ops.find_all` on 2400 random cases and a song, and the tables against the running interpreter's `re` (every BMP code point, each table boundary, a stride over the rest); the desktop's `test_qt_find_bar.py` as the model's behaviour: find as you type from the caret, next and previous with the notices, match case and whole word, no matches, close and Command-G, a one-line selection as the query, tints that follow the text, Replace then the next match (after the session's edit, or its refusal), Replace when the selection isn't a match, Replace all's arguments, Play without Replace, undo, the catalog's bar; the tints under the playing chord |
| `AppShortcutsTests` | Android's `ShortcutsTest` for New, Open, Save, Save As and the text size with Command, the find keys (Option-Command-F, Command-G; no Command-H), no key both the app's and the text view's, the menus' titles, shortcuts only on the bare main screen; Android's pinch as steps (clamped, adding up to `pinchSize`); the side column's width kept clamped under Android's key |
| `TextInputTests` | Android's `PasteNormalizationTest`, `ChordWrapTest`, `TextScrollTest` and `DirectiveHintControllerTest`, case for case |
| `ChordSheetGeometryTests` | Android's `ChordSheetGeometryTest`, case for case: anchors, hit-testing, gutter variants, culling, lane clips, auto-scroll, zoom steps, Tk colours, requests; the scroll after a new buffer |
| `ChordSheetThemeTests` | Android's `ChordSheetThemeTest` and `ChordSheetPaperTest` as behaviour: the light theme keeps the buffer's colours, the dark one maps them; the palette |
| `ChordSheetLayoutTests` | Android's `ChordSheetSplitTest`, the pane's content height, when the strip follows the playhead |
| `ChordSheetLoaderTests` | Android's `ChordSheetControllerTest`: one fetch per distinct request after the settle time, no song, a newer version, the loading flag, stale replies dropped |
| `SheetPainterTests` | the painter on the Android fixtures with a recording canvas: paint order, clips and translations, glyph rectangles and tints (widths against `clef_assets.scaled_width`), text anchoring and pixel snapping, lane clips, the playhead marks, the key bed, culling |
| `DiagnosticsTests` | the offline render of a chord is not silent (system libfluidsynth, the repo's SoundFont), a missing SoundFont is reported, the fault handler's file |
| `MainScreenTests` | Android's `ModeControllerTest`, `ScreenLayoutTest`, `PlaybackUiTest`, `RenameFlowTest` and `MenuModelsTest`, case for case; the chord sheet pane's height upright and on its side, the speed badge, the snackbars, the menu's entries, the rename dialog's state, the player's state from a snapshot |
| `PlaybackAudioPolicyTests` | Android's `PlaybackAudioPolicyTest` case for case (focus at play, kept through a pause, asked again after a loss, a denial pauses; the noisy receiver as the route-change filter) and `AppLifecycleHooks`' case; iOS's interruptions (the output released and reopened, no resume, the suspended note ignored, one in the background, one that never ends), route changes, the media services reset, the scene phases, a late focus answer, AVFoundation's userInfo values |
| `AccessibilityLabelsTests` | every icon button's VoiceOver label against Android's string resource (`res/values/strings*.xml`), the find bar's against the Qt desktop's tooltips |
| `MultitaskingTests` | the layouts at an iPad's Split View, Slide Over and Stage Manager window sizes (Android's sw600dp line, the Settings panes, the identifier's dialog, the sheet's pane), the keyboard over a window that isn't the whole screen |
| `PlayheadGesturesTests` | Android's `PlayheadGesturesTest`, case for case, and the marker's shape |
| `FileDocumentStoreTests` | Android's `SafDocumentStoreTest` as behaviour on real files (`PlainFileAccess`): raw bytes, the desktop's wording with the document's location, a recent file that has gone (named from its entry, dropped with its bookmark), the 5 MB cap, a cloud file not downloaded, the same file picked twice, a stale bookmark made again under its id, a moved file, a relaunch, corrupt lists, writes in place, `copyFromFile`, the shipped song, example copies (rename, a taken name), rename keeping the id, the recent list's order, cap and pruning, exports and their written callback; the id scheme |
| `ExampleLibraryTests` | Android's `ExampleLibraryTest`, case for case (ids are `app:examples/<name>`) |
| `SessionRequestsTests` | Android's `RequestControllerTest` and `DocumentPickersTest` as behaviour: the snapshot's pending request, a picker once per request, a stale result ignored, Save As's move, an export answered at once with the store's file, the unsaved-changes answers, an Insert dialog's fields checked and answered (Cancel answers null), a PDF's pages painted once per request off the main actor and always answered (with a reason, or a thrown error's) |
| `PlayerSheetsTests` | Android's `SheetRouteTest`, case for case (the instrument's two levels, the speed dialog, typed and snapped speeds, the badge, the pill and Write into song), the slider letting go once the session has its value, Manual…'s check, Playback settings' rows and choices, Insert's entries |
| `ToolsTests` | Android's `ToolFormsTest` and `DirectiveVerdictTest`, case for case (selections in code points, Transpose's range, each directive's answer, loop targets, key lists, Suggest Capo's pick and Apply, a stale or foreign check ignored), the messages in the fields' order, the tools' commands from the editor's model, `RibbonEdges` |
| `IdentifierTests` | Android's `IdentifierTest`, case for case: the piano's keys and hit testing, labels in either notation, the model's field and pick, a notation switch, the layout, key looks, sounding keys and their token |
| `SheetControllerTests` | every tap in the sheets and the tools through the reducer: the route, the dialogs' fields, the commands (speed, Playback settings and its locked reason, voicing, instrument, Insert, Transpose with and without a selection, an Insert dialog checked as it changes, Suggest from Insert Capo, Suggest Capo's pick and Apply, the identifier), Edit voicings… opening Settings |
| `SettingsControllerTests` | Android's `SettingsControllerTest`, case for case but its three `snapshot()`/`restore()` cases (no state restoration on iOS): the edit's life, autosave and the 400 ms rest, a number only saved when valid, the voicing commands each followed by a save, leaving and the problems question, values kept from last time, the navigation on a phone and with two panes, the split, the dialogs, Add voicing's presets and sections, a built-in and a newer release's voicing read-only, pending edits, the key's spelling; the problems' lines, the steppers; `SettingsScenesTests`: every Settings scene folds into an editing screen with its schema |
| `VoicingFormTests` | Android's `VoicingFormTest`, case for case: the schema, every field and section kind, the three models' forms with their errors and hints, records and the bottom voice's gap, a read-only form, the payloads, pending edits, steppers; the field's echo and the errors banner's timing |
| `LicencesTests` | Android's `LicencesTest` on the iOS list, case for case but its Maven cases: every entry's fields and text, the texts the build phase copies, the components the app ships (and none it doesn't), the versions the build pins, the AGPL and the SoundFont's licence, the LGPL source, the Python pins without chardet, the guide's entries Android's word for word with the Sphinx stack's pins, the order, bad data, the pages' ← and an opened song, the build info, no support link |
| `PdfExportTests` | Android's `PdfExporterTest`, case for case: every page at its size with the layout's positions and colours, Letter pages, the file written and "" answered, a failed write's reason, the paper by country; the letter countries are the core's |
| `HelpTests` | Android's `QuickStartModelTest`, case for case (the guide's links on iOS's `cnhelp://guide/`), plus the guide's files (nothing outside its folder, percent-decoding, a folder's index) and types, a snippet styled as the editor's text, the tour's checkbox, the launch kind, local ISO days, the startup screen forgotten once dismissed |
| `IntegrationTests` | one real session: restore a draft, code-point highlights, save through the store, a refused rename, a decoded chord sheet buffer; open songs from the store, save a typed change, Save As to a new id, Export MIDI through the store, the unsaved-changes question on Open and New (Don't save, Cancel), a recent song that has gone; the speed and its Reset, Write into song, every Insert request with the session's check, an answered Insert, Suggest Capo scored and applied, the identifier naming Cmaj7 and its Insert, Transpose of the song and of a selection; Settings through the controller (a General value, a staged number, My 7-String, an unbuildable value refused and fixed with the config unchanged, Jazz Vocal Trio, a built-in, a refused rename, leaving); the Quick Start tour; the find bar on Scarborough Fair (Replace on the span the kit found, then the next match; Replace all as one edit and its status; no matches), the pinch's steps, the serif font at 16 from Settings in the editor's model; the forty scenes (five of them frozen while a chord sounds) |

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
  in the kit's tests (`hold` in the app's session test: a FakePlayer that
  keeps a started song playing).
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

`IntegrationTests` records the scenes into `ios/Fixtures/`: `empty_song`,
then `identifier_cmaj7` (Amazing Grace under the chord identifier: C, E, G
and B selected, Cmaj7 played; recorded here, while the status is still the
start's "Ready", as in Android's help screenshot of a fresh app, and cleared
again after), `quick_start_edit`, `play_with_chord_sheet` (the complete example with the
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
MIDI and saved, `export_finished` with a place: "Exported MIDI: Lullaby
(2).mid (iCloud Drive)") and `discard_question` (a session edit,
then New: the scene ends on `ConfirmDiscardRequest`), then the sheets' and
tools' scenes on Amazing Grace, as Android's help screenshots show it
(`android/tools/help_shots.json`, the songs in `android/tools/help_shot_songs/`):
`player_sheets` (the tempo set by `{bpm: 90}`, 3/4 and G as the song's own
values, the speed at 125 %, Steel Guitar), `insert_bpm`, `insert_time`,
`insert_key`, `insert_capo`, `insert_label` and `insert_loop` (each ends on
its `InsertDirectiveRequest`, the cursor after "me", and the session's check
of the fields the dialog opens with, so Insert is on for the time, key and
loop as on Android; the tempo's then carries a check of "999", the label's a
clean check of "chorus"),
`grace_edit` (the song restored again, nothing pending) and `capo_advice`
(Suggest Capo scored for the whole song); `player_sheets` and the scenes
after it are on Piano, as Android's help screenshots' config is. Then
Settings' scenes, each from Amazing
Grace's restore so it carries the text and the schema (an event):
`settings_open` (the edit begun, the defaults, no voicings of the user's),
`settings_voicing_form` (My 7-String made from a blank fretboard with strings
B1 E2 A2 D3 G3 B3 E4, as `android/tools/help_shots.json` has it),
`settings_voicing_refused` (its strings B1 E2 X9 G3 and a relaxed span of 2:
two problems, nothing saved), `settings_voicing_ensemble` (Jazz Vocal Trio:
Lead A3–F5, Harmony F3–D5, Bass E2–C4) and `settings_builtin` (the standard
guitar read-only). Last, the guide's scenes (`IntegrationHelpTests.swift`),
set up as Android's help screenshots are (`android/tools/help_shots.json`:
Amazing Grace, Piano, the first program, the piano roll 330 pt tall):
`quick_start_tour` (`request_quick_start`'s seven pages), `grace_play`,
`grace_staff`, `grace_fret` and `grace_tab` (the playhead on the first chord,
each view at its default zoom, the standard guitar for the last two),
`grace_playing` (frozen as chord 5, Em in bar 6, sounds),
`grace_playing_metronome` (the same with the metronome on at 125 %),
`grace_playhead` (the playhead on Em, nothing playing) and `colours_edit`
(`android/tools/help_shot_songs/colours.txt` in Edit, every span kind), and after them
`find_replaced` (Scarborough Fair after the find bar's Replace on the first
Am chord, match case and whole words, then Replace all with Em: "Replaced
12 matches"). A fixture has no answers, so a request in it
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
the content heights the main screen asks for in Play in the catalog's six
windows (`MainSheetPane`: below the text upright, the split's height; in the
side column on its side, the window less the app bar and the player; then
less the pane's header, progress bar, inset and the 20 pt marker lane): 102,
185, 355 and 603 pt for a 160 pt sheet, 185, 272 and 603 pt for 330 (the iPad's Split View third and half ask for heights already there).
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
  Playback category; the session ends up in Playback with both options
  (the self-test's `audioOptions`, run 45517323581).
- **Start:** `AppModel.start` starts Python with `home = <app>/python`,
  `python/app` and `python/app_packages` in front of `sys.path`, and
  `CHORD_NOTEPAD_LIBFLUIDSYNTH=<app>/Frameworks/FluidSynth.framework/FluidSynth`;
  then the session with `files_dir` = Application Support and the bundled
  SoundFont. The app then reopens the last song ("The last song"); at the
  first launch that is the quick-start song, opened as a draft (store id
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
  strip follows the playhead only when it moves, as on Android. Its
  handlers get the sheet, the two indices and the width as one value
  (`StripInputs`, one `onChange`): an `onChange` action may run with the
  closure of the update before the change, so indices read from the view
  there can be one state old. That is the likely cause of S0 issue 7: after
  ⏮ the follower would still see the paused chord, and the strip stayed near
  it (the core and `PlayheadFollower` give the right chord for that sequence). `SessionTests` hosts the strip,
  plays it chord by chord, then ⏮, and checks the scroll view is back at 0.
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
    end. A `reset` (another document) puts the caret at the text's start, as
    the Qt desktop does: the session's cursor after the text is Tk's unseen
    insert mark, and a caret there sent the next Transpose (which keeps the
    caret's line) and its Undo to the song's end (S0 issue 14). An edit that
    rewrites the whole text in place (Transpose, Convert, Suggest Capo's
    Apply), and the undo or redo of one, sets `keepScroll`: the view stays
    where it was instead of scrolling to the caret;
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
    `plain` session edit is a step of its own, `reset` (Open, Recent, an
    example, New, a restored draft) clears the history, and each step puts
    back its selection. The text an undo or redo leaves goes to the session
    as a user edit;
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
  Command-Y). The text size keys are the app's (they work in Play too; "Find,
  the font, the pinch and the keys"); the text view adds Command-+ beside
  the app's Command-=. The Qt desktop's line commands come along: Command-/ (toggle
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
- **The iOS look** (Tibi's call on 2026-11-26, after using the app on a
  Mac's simulator: "still a bit too material-y"). The layout and the
  behaviour are Android's; the controls and their drawing are iOS's, so the
  app reads as an iPhone and iPad app rather than a port:
  - SF Symbols for every icon of the chrome, named by role in the kit's
    `AppSymbols` (a test checks each exists on iOS 17, the deployment
    target). Chord Notepad's own drawings stay for a capo, transposing and
    a time signature, which no symbol shows (`ic_capo`, `ic_transpose`,
    `ic_time_signature`, template images from Android's drawables through
    `ios/tools/mdi_assets.py`).
  - The system accent colour (blue) and the system's dynamic colours
    (`Screens/Theme.swift`: backgrounds, label greys, separators, red), so
    dark mode and Increase Contrast are the system's. The kit's
    `AppColors`, `EditorPalette` and `ChordSheetColors` hold the same values
    for what needs a number. The editor's syntax colours and the chord
    sheet's drawing are content and keep Android's; only the sheet's
    playhead mark and playing column take the accent.
  - The bar is drawn as a navigation bar (☰ and Save as symbols in the
    accent colour, the title as a headline), Edit / Play is the system's
    segmented control, as are AB/Do in the ribbon and the chord sheet's
    views. The ribbon is a toolbar of symbols with captions; the player's
    buttons are symbols, one that is on filled and tinted, ▶/⏸ a filled
    accent circle.
  - The player's and the ribbon's sheets, the tools and the Insert dialogs
    are iOS sheets with a navigation bar and inset grouped lists ("The
    player's sheets and the ribbon's tools"); Settings, About and the
    licences are grouped lists with navigation bars ("Settings, About and
    Licences").
  - Alerts are the system's where it can show them; the ones with a field
    whose state must stay (Rename, a voicing's rename), the unsaved-changes
    question and the catalog's pictures of alerts are drawn in the system's
    alert look (`Screens/Alerts.swift`, as "Preparing export…" is). See the
    differences below.
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
  guide, Quick start, About) and Diagnostics last; every entry works. The panel runs
  the screen's whole height, under the status bar and the home indicator,
  as Android's drawer does; its entries stay inside the safe area.
- **Layout:** as `ScreenLayout.kt`. The chord sheet is a Play-mode view, so
  the shell's case of the keyboard up with the sheet showing doesn't arise
  any more; the header collapses in Edit with the keyboard up when the text
  would get less than 170 pt (a phone on its side), and undo and redo then
  float by the keyboard, as on Android. Edit has no status line: the
  session's status shows as a snackbar there, errors in both modes. A full
  page (Quick Start, Settings, the guide, About) shows no status snackbar:
  one that is up goes when the page opens and a status that comes while it
  is up is passed over (`Snackbars.pageOpened`, `update(page:)`), as
  Android's pages replace `SongScreen` and its snackbar host. Errors and a
  greyed control's reason still show over a page (Android's errors are
  dialogs over its pages). Any change of tab puts a status from Edit away,
  the user's or an open's (the launch's song opens in Play), as Android's
  `StatusSnackbars` does on a mode change; before, the start's "Ready"
  stayed over Play's player for its 4 s (CI's export-preparing shot showed
  it behind the export's status). No status shows during the launch state.
- **Launch state:** from `launch()` until the song the app opens at launch
  arrives (`MainUiState.launching`: `launchBegan`, then `documentChanged`
  once `ModeController.opened` counts it), the screen is the app's
  background and a spinner: no title, tabs or editor. The session's start-up
  replay reports an empty untitled song first, which on a slow start read as
  a lost song (S0 issue 4). A failed start, a missing bundled song, an
  error while it waits (the last song's open failed: `errorArrived`), an
  empty last song or 60 s without the song end it too ("The last song"). `launch.json` says whether it was still up
  (`launching`, which CI's main launch checks is false) and whether it hid
  the untitled song (`hidUntitled`). Off in the catalog and under XCTest.
- **Large text:** the bar is a fixed 48 pt; its title is a headline, which
  follows Dynamic Type up to `accessibility2`, and on a phone at the
  accessibility sizes the Edit / Play segments show their symbols instead of
  their words so the title keeps its room. The player (a fixed 110 pt)
  follows it up to `xxLarge`. The ☰ menu, the sheets, Settings and the
  alerts follow it all the way and scroll; a menu entry's name wraps
  (Tibi's session at Accessibility Extra Large: "Export MID…" cut short,
  Diagnostics cut off at the bottom, and the outlined fields' labels over
  their values in Settings and Identify).
- **Launch hooks:** `-CNScreen selftest` opens Diagnostics,
  `-CNScreen chordsheet` opens Play with the sheet shown, `-CNScreen editor`
  switches to Edit before typing, `-CNScreen menu` opens the menu,
  `-CNScreen export` exports the song as audio ("Files"), `-CNScreen speed`,
  `instrument`, `insert`, `capo` and `identify` open a sheet or a tool ("The player's sheets
  and the ribbon's tools"), `-CNScreen settings`, `voicings` and `about` a
  page ("Settings, About and Licences"). `-CNScreen main` does nothing but
  make the launch not a direct one (CI's main screenshot, with no tour over
  it); `-CNScreen guide` and `pdf` open the guide and an export of the song
  as a PDF, `-CNScreen quickstart` is a direct launch that waits for the tour
  (CI's first launch after the install checks that already), and `families`, `hint`, `keyboard` and
  `landscape` set up the guide's live screenshots ("The user guide, Quick
  Start and Export PDF"). `-CNScreen find` opens the find bar ("Find, the font,
  the pinch and the keys"). `-CNScreen draft` and `restored` are the relaunch
  check ("The last song"). Every hook but those two opens the quick-start
  song and never reads or writes the last song.

Deliberate differences from Android:

- The menu is a panel from the leading edge over a dimmed screen, drawn as
  an iPad's sidebar (an inset grouped list), opened by ☰ only; there's no
  edge swipe (Android allows the swipe only while the drawer is open, and an
  edge swipe would fight the marker's grab strip at a line's first chord).
  It lists Diagnostics, which Android doesn't have. It stays a panel rather
  than an iOS pull-down menu: a menu can't be opened by the app
  (`-CNScreen menu`) and has no room for the recent songs' names.
- Rename is drawn in the system's alert look with its field: the session's
  refusal of a name stays under the field, and a system alert closes on any
  button. A refused rename (Save a copy…) is the system's alert. Diagnostics
  and Examples are iOS sheets.
- The unsaved-changes question is drawn in the system's alert look over
  everything: the session can ask while a sheet is up or going away
  (Examples, a song from Files), when the system can't present an alert.
  While it is asked no sheet shows.
- Snackbars are drawn by the screen as iOS banners on the system material
  (iOS has no snackbar); a greyed button's reason is a short one (Android: a
  Toast). A sheet that is up shows them itself.
- The Edit / Play control is a segmented control, not tabs: its segments
  carry the words, not the `tab-edit` and `tab-play` identifiers.
- While the app starts it shows a spinner until the launch's song is open
  (Android shows the empty song, its title and Edit tab with a progress bar
  under the header while Python starts; BACKLOG).
- The screen stays awake while a song plays through the idle timer.
- The side column's width is kept across launches in UserDefaults, as
  Android keeps it in its preferences ("Find, the font, the pinch and the
  keys").
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
| `bundle:<file>` | a song the app ships (the quick-start song at the first launch) | read only: Save runs Save As (`restore_draft` with `read_only`), rename is refused |
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
Application Support (UserDefaults holds only the side column's width).
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
- **Exports** (`PICKER_CREATES_FILE` is false for iOS,
  `SAVES_EXPORT_AFTER_WRITE` true): the request is answered at once with a
  store file (`app:exports/...`), and the session renders and writes it
  through the store. Meanwhile "Preparing export…" is up
  (`ExportProgressDialog`, drawn as iOS draws an alert: the system material,
  a system spinner, the audio export's percentage, Cancel), from the
  session's `ExportState` (the export's store id, its kind, the audio
  progress, whether the file is written). The store's `onExportWritten`
  (after `writeBytes` for MIDI and PDF, `copyFromFile` for audio) has the
  app open the export picker (`forExporting:asCopy: true`), one at a time;
  the dialog stays until the picker's presentation finished, since the
  picker took about 12 s to appear on an 8 GB Mac's simulator. The export
  picker rather than the share sheet: Android's exports are saved to a
  place the user picks, and the share sheet would put AirDrop and Messages
  before "Save to Files". When the picker closes the app tells the session
  `export_finished {document_id, saved, location}`: saved, the status says
  the desktop's "Exported MIDI: song.mid (iCloud Drive)" ("Exported audio",
  "Exported PDF"), the place read from the picker's URL as the store names
  places (`FileDocumentStore.savedLocation`); not saved, nothing is said and
  the status goes back to rest. The store's file is deleted either way.
  Cancel on the dialog sends `export_finished` (not saved) at once: the
  session cancels a render still running (the job's cancel, the same one
  the shutdown uses, so a long audio render stops at its next block and
  another audio export may start), a file written all the same is deleted
  when it arrives, and a picker already opening is closed as soon as it is
  up. The session keeps pending exports by store id, so the wording knows
  the kind; an unknown or repeated id is ignored, and a save that arrives
  before the write's own outcome (the audio job's, the PDF's answer) stays.
  A failed export is the same error as before: the state empties and the
  dialog goes. While an export runs, its statuses aren't snackbars in Edit,
  nor is the status at rest after a cancel; "Exported …" is. The kit's
  `ExportHandoff` keeps the app's side (tested on Linux); Android and the
  desktop never publish the state or send the command.
- **Export PDF** is an export like these with one step more: the core
  doesn't make the PDF, it sends `PaintPdfRequest` with the pages laid out
  (`PdfLayout`); the app paints them and writes the file through the store,
  whose write offers it with the export picker ("The user guide, Quick Start
  and Export PDF").
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
- **From Files and other apps:** `CFBundleDocumentTypes` lists plain text
  as an Alternate handler (never the default for `.txt`), and
  `LSSupportsOpeningDocumentsInPlace` opens it in place: `onOpenURL` gets a
  security-scoped URL, which is adopted and opened like a picked one. A URL
  that arrives before the session runs waits for it and wins over the last
  song, which then opens only if it has unsaved words ("The last song"). `.cho` and `.chordpro` files aren't plain text to iOS, so they open
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
  failed export leaves nothing behind. "Preparing export…" with Cancel is
  up while the file is made (Android shows only the status line), and the
  status names the place only after the save.
- Errors are snackbars, as in the main-screen slice (Android: dialogs).
- Example copies, the recent list and the bookmarks live in Application
  Support: not in Files, not removed by anything but the app.

What CI checks: `SessionTests` drives the real store on files in the app's
Documents with a stand-in for the pickers (Open, Save, Save As, Export
MIDI saved with its place in the status, then its picker cancelled with
nothing said, then "Preparing export…" cancelled while the picker is slow
to come up: closed as it appears, the file deleted; Recent after a second
store reads the lists, a song from Files renamed, an example, a song that
has gone, New's question). Audio export needs the real player's SoundFont,
which the test's FakePlayer hasn't (the core refuses before asking for a
file), so `-CNScreen export` runs it in the launched app, in step with
`ci_screenshots.sh` through files in the Diagnostics folder: the dialog up
(`<device>-export-preparing.png`), the export picker after the store's
write (`<device>-export.png`), then a save made as the picker's Save would
(the file copied into the app's Documents, the picker closed with that URL)
and the status that follows (`<device>-export-saved.png`). `export.json`
must report all of it: the dialog seen, a WAV of more than 10 KB, the
picker up with the dialog gone, "Exported audio: …".

What CI doesn't test (see the device checklist below):
`UIDocumentPickerViewController` driven by a person (Open, the Save As
move, choosing where the export goes, its Cancel) and the security scope of a URL from it or from Files, a file
outside the container (iCloud Drive, On My iPhone, a third-party provider),
the place a real save names (iCloud Drive, a provider's folder),
a bookmark resolved after a reboot or an app update, an iCloud file that
isn't downloaded, renaming a picked file, a song opened from the Files app
or another app's "Open in…" (`onOpenURL` is called directly), and the live
dialogs (Cancel on "Preparing export…" is tested through the model, not a tap).

### The last song

Every launch reopens the song that was open last, with its unsaved
changes, whether iOS ended the app in the background, the user swiped it
away, or it crashed (Tibi, 2026-11-26). Quick Start's song opens only at
the first launch, and from ☰ › Quick start as before. Android's
`DraftHook` (`lifecycle/DraftRestore.kt`) is the model, but Android
restores only after process death; this is a deliberate difference.

- **In the kit** (`Lifecycle/LastSong.swift`, tested on Linux in
  `LastSongTests`): `LastSong` (the text, the store id, its name and
  location, the modified flag, `DocumentState.readOnly` and the tab),
  `LastSongPolicy.launchSong` (what a launch opens), `LastSongPolicy.restore`
  (the `restore_draft` for a draft, once its document is resolved),
  `LastSongFile` (the JSON file). `ModeController.expectRestore` and
  `MainUiState.errorArrived` end the launch state (`MainScreenTests`).
- **In the app:** `AppModel.openLastSong`, `restoreLastDraft`,
  `saveLastSong` and the hooks below. The core is unchanged: `restore_draft`
  and `open_document {ref, read_only}` do the restore.

**What is kept, and when.** The song on screen: the editor's text (the
session's copy lacks typing not sent yet, and such typing counts as a
change), the session's `DocumentState` (id, name, location, modified,
read only) and the tab. It is written to `Application Support/last_song.json`
(not in Files, not cleared by the system) when the scene goes inactive or
to the background, and 2 s after the last change to the text, the document
or the tab, so a crash loses at most that. Nothing is written while the
launch state shows, or before the launch's song has been sent: the start-up
replay's empty song would otherwise replace the one about to come back.
There is no size limit (Android's 100,000 characters come from the saved
state's binder transaction).

**What a launch opens** (`LastSongPolicy.launchSong`):

| Last song | Opens |
|---|---|
| No file (the first launch) | the quick-start song, read only, in Play (`bundle:01_quick_start.txt`, as before) |
| A file that can't be read | the empty song: the app ran before, so not Quick Start. The file is moved aside (`last_song.unreadable-<time>.json`, logged) rather than written over |
| Untitled and empty (New, nothing typed) | the empty song |
| Untitled with text | the text as an unsaved draft (`restore_draft`, no document, modified) |
| Saved, no changes | the document read again through the store (`open_document {ref, read_only}`), so changes made elsewhere show |
| The quick-start song, no changes | the quick-start song, as at the first launch |
| Changes (a saved song, an example copy, the quick-start song) | the text as a draft of its document (`restore_draft {document, modified: true, read_only}`): an example copy stays an example copy, the quick-start song stays read only (Save runs Save As) |

- **A document that is gone.** A draft's document is resolved off the main
  actor first (`FileDocumentStore.refFor`: a bookmark once took a minute to
  fail in CI). If the store can't reach it (deleted, a bookmark that no
  longer resolves), the text is kept as unsaved changes of a new song, as
  Android's `DraftPolicy.restore` does, and an error snackbar says "Couldn't
  find song.txt (Downloads): its unsaved changes are open as a new song."
  (Android says nothing.) A saved song without changes is opened as a recent
  song is: if the file is gone or an iCloud file can't be downloaded in 20 s,
  the open's usual error ("Failed to open file: … File not found") shows
  over the empty song, and a bookmark that doesn't resolve leaves Recent.
  The user's words are never dropped: only an unchanged song can fail to
  come back, and its text is in its file.
- **The tab.** The song lands in the tab it was left in, Play or Edit
  (`ModeController.expectRestore`), where an open would always go to Play.
  The quick-start song opens in Play.
- **The launch state** ends when the restored song's document state
  arrives (the one with the expected id and modified flag, so the start-up
  replay's empty untitled song doesn't count, while an untitled draft
  does), when the session reports an error while it waits (the open
  failed: the empty song with the error), at once for the empty song, and
  after 60 s at most, as before. `launch.json` names what the launch
  reopened (`lastSong`: `quickStart`, `empty`, `open` or `draft`) and has
  the modified flag; it is now written for an untitled draft too.
- **Songs from Files.** A song opened from Files at launch wins, as it won
  over the quick-start song: when the last song has no unsaved words, it
  isn't opened at all and the launch state waits for the song from Files
  (a failure ends it with the error). When it has unsaved words, they come
  back first and the song from Files opens once the launch state is over,
  so the unsaved-changes question shows over them, on screen. URLs that
  arrive while the last song is being put back wait for it.
- **Quick Start's tour** is unchanged: the session shows it at a direct
  launch while "Show quick start at startup" is on ("The user guide, Quick
  Start and Export PDF"), over whichever song opened (Tibi, 2026-11-26:
  the setting keeps its meaning; only the quick-start song stops opening
  after the first launch). The first launch shows the quick-start song with
  the tour over it, as before.
- **CI's hooks** (`-CNScreen …`) and XCTest's session neither read nor
  write the last song: they always open the quick-start song, so their
  screenshots and checks don't depend on the launches before them. Only
  the relaunch check's two hooks keep it (`AppModel.keepsLastSong`).

Deliberate differences from Android:

- Every launch reopens the last song (Android: only after process death; a
  launch from the launcher after a swipe-away or a reboot opens a new
  song). It is kept in a file, not the activity's saved state, so it
  survives a swipe-away and a crash.
- A saved song without changes is read again from its file (Android
  restores the draft's text without reading it).
- A draft whose document is gone says so in a snackbar (Android drops the
  document silently).
- The song comes back in the tab it was left in.

What CI checks: the kit's tests (every row of the table, the gone
document, the file; the launch state for an untitled draft, a saved song
in Edit, a failed open), and `IntegrationLastSongTests` over the real
core: a saved song read again, one whose file is gone, a changed song
with its document and one without, each from the empty song with the
session's own output fed through the launch state. `ci_screenshots.sh`'s first launch after the
install must report the quick-start song and the tour (`startup.json`).
Its relaunch check, after the other hooks: `-CNScreen draft` waits for the
launch's song, makes a new song, types a line with chords in Edit and
leaves it unsaved (`draft.json`); the script launches the Settings app, which sends
ours to the background, where the last song is written
(`draft-kept.json`); it ends the app there, as iOS or a swipe would, and
`-CNScreen restored` checks the next launch brought the song back: a draft,
untitled, modified, the typed text, in Edit (`restored.json`,
`<device>-relaunch.png`).

What CI doesn't test (device checklist below): a swipe-away from the app
switcher, iOS ending the app under memory pressure, a crash, a reboot, a
restored bookmark song outside the container (iCloud Drive, a provider), an
iCloud song that isn't downloaded at launch, a last song whose file was
deleted in Files, a song opened from Files with the app closed over a last
song with unsaved words.

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
- **In the app**: `Screens/PlayerSheets.swift` (`SheetScaffold`: a sheet's
  navigation stack with the title inline, Cancel and the confirming button
  in its bar; `ChoiceRow`, a list row with a checkmark; `CatalogSheetFrame`;
  the Voicing, Instrument, Speed with Manual…, Playback settings with its
  tempo, Insert and Examples sheets), `Tools/ToolDialogs.swift` (Transpose,
  Suggest Capo and the Insert dialogs as form sheets) and
  `Tools/ChordIdentifierView.swift` (the identifier and `PianoView`, a
  `Canvas`). `MainScreen` presents one of them at a time with
  `.sheet(item:)` from the route, the pending request and
  `CapoAdviceState.active` (`MainSheet`), so going from one to the next (Insert
  to its dialog, the dialog's Suggest to Suggest Capo) waits for the first to
  go; `AppModel.sheet(_:)` runs the reducer. The catalog can't present, so it
  draws the same view in `CatalogSheetFrame` (a sheet from the bottom, a
  form sheet in a regular-width window). The ribbon gains Insert, Transpose,
  Capo and Identify and scrolls sideways when it doesn't fit.
- **The flows**, as Android's: Voicing and Instrument apply a choice at once
  and stay open (Done closes); Instrument pushes a family's programs, Back
  (or the edge swipe) goes back. Speed sends each new 5 % stop while the finger moves; Manual… checks
  12.5–400 before OK. Playback settings shows a value a directive sets as
  "Set by `{bpm: 90}` in the song · Edit" (Edit, a button at least 44 pt
  each way, goes to Edit mode with the caret on the directive; a link inside
  the text was too small to hit); the others are dropdowns (the tempo a typed
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
  types, a candidate tap picks and plays it (long press rolled), Insert
  puts the picked chord and a space at the editor's caret and closes the
  identifier (VoiceOver also has an Insert action on each candidate).
- **Live check:** `SessionTests` drives the speed sheet (a drag, a refused
  and an accepted Manual… value, Reset), Playback settings' Edit, and from
  the ribbon Transpose, Insert › Tempo with the session's check, Suggest Capo
  and the identifier's Insert, checking the editor's text after each.
  `-CNScreen speed`, `instrument`, `insert`, `capo` and `identify` open
  each live for CI's screenshots and write `Diagnostics/tool-<name>.json`
  when ready.

Deliberate differences from Android:

- The sheets and the tools' dialogs are iOS sheets (half the window,
  draggable to full; Identify nearly full, a form sheet on an iPad), each
  with a navigation bar: Cancel on the leading side, Done, OK, Insert or
  Apply bold on the trailing one (Android: the actions at the bottom). A
  swipe down sends that sheet's own way out: Done for the player's, Cancel
  for the tools (an Insert dialog answers the session's request, Suggest
  Capo closes the session's advice). Manual… and the tempo are small sheets
  over theirs (Android: dialogs over the sheet). Identify's Insert is in its
  bar; its status line stays at the bottom.
- The lists use iOS's controls: a checkmark on the current voicing,
  instrument and capo (Android: radio buttons); pop-up menus for Playback
  settings' time and key, the Insert dialogs' pickers and Suggest Capo's
  voicing; the system's slider for the speed (VoiceOver still adjusts it in
  5 % steps); steppers for Transpose and a loop's count; plain text fields,
  the name on the left and the value typed on the right.
- A greyed value's reason in Playback settings is a banner over the sheet
  (Android: a Toast).
- The ribbon's › chevron scrolls to the end of the row (Android scrolls
  140 dp; on a phone that is the end).
- The Insert dialogs, Manual… and the tempo don't keep their fields across a
  relaunch (Android saves them for a rotation; on iOS a rotation keeps them
  anyway).

What CI doesn't test: a finger on the slider, a swipe down on a sheet, the
pop-up menus, a long press on a piano key, Play or a candidate (the session
test sends the same events the gestures send),
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
  navigation, the pages, General, Playback, the alerts), `VoicingsView.swift`
  (the list, Add voicing, the voicing's detail, the form by kind, the
  records as sections or a table through `WeightedRow`),
  `SettingsWidgets.swift` (`EchoTextField`, `NumberRow`: a name, the number
  typed and the system's stepper; `RowNote`, the error banner, `BackButton`
  and `pageBar`) and `AboutView.swift` (About, the licences, a licence's
  text), all inset grouped lists and forms of the system's controls. `AppModel` keeps the controller while Settings is open
  (`openSettings`, `settingsAct`: the commands go out, a typed number is
  saved 400 ms after the last change, the screen goes once the edit ends)
  and the parsed schema; `MainScreen` draws the page over itself, under the
  snackbar (errors and notices only: no status over a page, "The main
  screen").
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
  The user guide and Android's guide group (Sphinx, its theme, jQuery, the
  Snowball stemmers, Pygments, Font Awesome, Lato and Roboto Slab), word for
  word, since the same pinned stack builds both. The "Licences"
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
  and commit (Info.plist), the licence (the app's own text) and the source,
  then Open source licences; each opens in the browser only when tapped.
  On a phone Settings is a navigation stack bound to the kit's
  `SettingsNav` (the system's Back and edge swipe go up a level through the
  controller, which never refuses going up); Done leaves, asking first while
  something is wrong. With two panes the pages list is a sidebar beside the
  page, the voicing form pushed over the voicings list in the page's own
  stack when they don't fit side by side.
  There is no Ko-fi link, unlike Android's FOSS flavour: an App Store app
  may not link to an outside payment page.
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

- The pages are drawn by the main screen over itself, each in a navigation
  stack of its own: Settings, About and the guide have Done, the licences
  and a licence Back to where they came from (Android's ← in a top bar).
  Settings' pages on a phone are pushed, with the system's Back and edge
  swipe.
- Leaving with wrong values, removing a voicing and switching its model ask
  with the system's alerts; renaming a voicing is drawn in the alert's look
  with its field, since OK stays off while the name is blank (a system
  alert reads its buttons once). The catalog draws all four.
- The fields are iOS's: the name on the left, the value typed on the right,
  a stepper for a number, the help or the range (red) in the section's
  footer or under the row; switches, pop-up menus and the notation's
  segmented control are the system's (Android: outlined fields with their
  labels on the outline, Material switches and segmented buttons). An
  ensemble's voices are a section each, headed by the voice's number and ↑,
  ↓, copy and ✕, or a table row each on an iPad on its side.
- The dropdowns and Add voicing's menu are iOS pop-up menus with the same
  choices and group titles; the catalog draws Add voicing's menu as a
  picture of one.
- The voicing form's number fields bring up the numbers and punctuation
  keyboard (the number and decimal pads have no minus sign, and weights are
  negative); General's and Playback's take the number pad.
- The rename alert opens with the caret after the name; Android selects
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

### The user guide, Quick Start and Export PDF

The seventh slice, ported from Android's `ui/help/` (`UserGuideScreen.kt`,
`HelpLinks.kt`, `QuickStartScreen.kt`, `QuickStartModel.kt`), the startup
screen (`MainScreen.kt`, `AppGraph.reportLaunch`) and `files/PdfExporter.kt`.
The session runs each (`request_quick_start`, `set_show_quick_start_on_startup`,
`app_started` and `dismiss_startup_screen`, `export_pdf` and its
`PaintPdfRequest`); nothing in the core or the schema changed.

- **In the kit** (`Help/` and `Files/PdfExport.swift`, tested on Linux):
  `QuickStartPager`, `snippetRuns` (code points to UTF-16, the editor's
  priority, a stable sort) and `snippetStyleRuns` (the editor's
  `styleRuns`), `quickStartShowsAtStartup` (the checkbox: the user's pick
  until the settings echo it, then the setting, then the tour's own),
  `QuickStartTexts`, `LaunchKind` and `isoDay`; `HelpLinks` (the
  `cnhelp://guide/` origin, internal and external links, the file a URL
  names, never outside the guide's folder, and its MIME type); `paintPdf` on
  the `PdfCanvas` protocol, `PdfColors`, `paperFor` (the core's Letter
  countries) and `PdfExporter` (paint, write through the store, "" or the
  reason). `RequestController` paints a `PaintPdfRequest` once per request,
  off the main actor, and always answers it (Android's `paintOnce`).
  `SessionSnapshot` keeps `QuickStartContent` and `StartupState`
  (`startupDismissed()` forgets it at once, as Android's repository does).
  `MainRoute` gains `.userGuide` and `.quickStart`, both full pages.
- **In the app**: `Screens/UserGuideView.swift` (`UserGuideScreen` with
  Android's bar, `GuideWebView`, `HelpSchemeHandler`),
  `Screens/QuickStartView.swift` (the tour as Android draws it: ✕ and the
  title, the page's title, paragraphs and snippets in the editor's colours
  and monospace, the divider, the "Show at
  startup" checkbox in Material's shape, Previous, "1 of 7", Next or Done) and
  `App/PdfPainter.swift` (`UIKitPdfCanvas`: the pages collected, then
  `UIGraphicsPDFRenderer`; text drawn with Core Text on the layout's
  baselines in Menlo; `PdfReport`, what an exported PDF holds read back with
  PDFKit). `AppModel` sends `app_started` once the first song is open, opens
  the tour when the session's `StartupState` says so or from ☰, and paints
  through the request controller.
- **The guide**: `ios/tools/build_help.sh` builds `help/` with `-t ios`
  (Android's pinned Sphinx stack, `android/docs-requirements.txt`; `-W`, the
  same reproducible settings and pruning as Android's Gradle task) into
  `ios/build/help`, which the "User guide" build phase copies into
  `<app>/help` (a missing guide fails the build). The web view loads it under
  `cnhelp://guide/` through a `WKURLSchemeHandler` that serves only that
  folder (Android's `WebViewAssetLoader`), and a content rule list blocks
  every other load; JavaScript is on (the theme's menu and search), the
  website data store is non-persistent. A link to a web site opens in
  Safari, and only when tapped. The page follows the app's light or dark
  look through the view's interface style (`prefers-color-scheme`, as
  Android themes its WebView), on the app's surface colour so there is no
  white flash. The guide's licences are Android's guide group, word for word
  (`ios/Licenses/components.json`). The iOS edition itself is described in
  `docs/HELP_AUTHORING.md`.
- **Quick Start at startup**: `app_started` goes out once the session
  runs and the launch's song was asked for, with `can_ask_for_support` false (no purchase on iOS) and
  the launch kind: `document` when songs from Files were waiting for the
  session, `restore` for CI's `-CNScreen` launches, otherwise `direct`. The
  session then shows the tour when Settings' "Show quick start at startup"
  is on (the default; the tour's checkbox is the same setting). Closing the
  tour (✕, Done, a song opened from Files) dismisses the startup screen in
  the session.
- **Export PDF**: ☰ › Export PDF… sends `export_pdf` with A4 or Letter from
  the region (`Locale.current.region`, as Android's locale country). The
  pick request is answered with an export file of the store's, the session
  lays the song out, and the app paints it and writes it through the store,
  whose write offers it with the export picker after "Preparing export…",
  as for MIDI and audio ("Files"). Menlo's advance is 0.602 em where the layout counts 0.6; every
  word is a run of its own at its column, so the difference never adds up
  across a line (CI checks the advance).
- **Live check:** `SessionTests` exports the quick-start song as a PDF
  through the real store and a stand-in picker and reads it back with PDFKit
  (its pages, a line of the song, the font's advance; attached as
  `export-live.pdf`), opens the tour from ☰, toggles its checkbox (saved as
  the setting), sends a direct `app_started` (the tour opens) and closes it
  (dismissed), and loads the guide in a real `WKWebView` through the scheme
  handler (the iOS edition's first page, its stylesheet, a file outside the
  guide refused; attached as `guide-live.png`). CI's first launch after the
  install shows the tour (`startup.json`), `-CNScreen guide` the guide and
  `-CNScreen pdf` exports a PDF (`pdf.json`, `export.pdf`).

Deliberate differences from Android:

- The guide's ← leaves it, as Android's bar button does; a swipe from the
  left edge goes back through its pages (Android's system Back). There is no
  back button for the pages themselves.
- The guide is served under `cnhelp://guide/` (Android: an https origin of
  `WebViewAssetLoader`), and other loads are blocked by a content rule list.
- A launch by a song from Files counts as a document launch only when the
  song arrives before the session runs (iOS hands the URL over after the
  launch; Android knows it from the launch intent). Any other launch of a
  person's is a direct one, including the one after iOS ended the app,
  which reopens the last song ("The last song"); the tour opens over it while
  its setting is on (Android: a restore after process death shows nothing).
- Export PDF's pages are set in Menlo (Android: the system monospace, Droid
  Sans Mono); both are 0.6 em wide, as the layout counts.
- The tour's checkbox and its buttons are drawn in Material's shape, as
  Settings' switches are.

What CI doesn't test: a person reading the guide (scrolling, its search, the
theme's menu, a link to a web site opening Safari, the edge swipe back,
switching to dark mode while it is open), VoiceOver in the guide and the
tour, the tour's checkbox tapped, a PDF printed or opened in another app,
the export picker driven by a person, A4 against Letter on a device set to
another region.

### Find, the font, the pinch and the keys

The eighth slice: the editor's remaining features. The pinch, the keys and
the column's width are Android's (`ui/editor/ChordEditor.kt`'s
`pinchToZoomFont`, `ui/Shortcuts.kt`, `ui/main/UiPreferences.kt`); Find and
Replace is the Qt desktop's (`desktop/chordnotepad_desktop/find_bar.py`,
`qml/app/FindBar.qml`), because **Android has no find and replace**: nothing
in its Kotlin, the help's Find and Replace section is desktop-only, and
`text_ops.py` says Android could use the commands later. Nothing in the core
or the schema changed: the session already had `replace_match`,
`replace_all`, `step_font_size`, `reset_font_size` and the settings.

- **Own bar, not `UIFindInteraction`.** iOS 16's find bar has a field, ▲ ▼,
  match case, whole words and a replace row, but it replaces through the
  text view, so a Replace all would be the view's edits sent as `set_text`:
  not the session's one undo step, not refused while a song plays, no
  "Replaced 3 matches", and its whole-word and case rules are UIKit's, not
  `text_ops`'. The catalog couldn't draw it either. The bar is a SwiftUI
  row under the text, where the desktop has it, drawn in the app's colours
  like the sheets and dialogs.
- **Matching in Swift, exactly as the core.** The bar finds as you type, on
  the main actor, so it can't ask Python; and the session's `replace_match`
  checks the span again with `text_ops.find_all` and leaves one it doesn't
  call a match. `TextFind` (`Editor/FindReplace.swift`) is `find_all` and
  `next_match` over code points, with Python's `re` rules for a literal
  pattern: a cased character matches one whose simple lowercase is its own
  or in `re._casefix`'s extra cases (`s` and `ſ`, `σ` and `ς`, the Kelvin
  sign), an uncased one only itself, and whole words mean no `\w`
  (`str.isalnum()` or `_`) on either side. The tables come from Python
  itself (`ios/tools/gen_find_tables.py` into `Generated/PythonText.swift`),
  not Swift's Unicode properties, whose case mappings are the full ones
  (`İ` becomes two characters) and whose Unicode version on iOS is the
  device's. `FindReplaceTests` checks the Swift matching against the core's
  `find_all` on 2400 random cases and the tables against the running `re`;
  `tests/test_ios_find_tables.py` fails while the file is stale.
- **In the kit**: `FindBar` (the desktop's `FindModel`) lives in
  `EditorModel` as `find`, so its matches are searched again on every text
  change and painted with the text: `FindAction` (open with or without the
  Replace row, close, the query and the replacement, next and previous,
  Command-G's `again`, match case, whole words, Replace, Replace all, the
  notice's end) through `EditorModel.find(_:canReplace:)`, which returns
  the usual `EditorEffects` (the selection, `findMoved`, `findNotice`, the
  commands). `styleRuns` takes a `FindPaint`: every match in the desktop's
  `findMatch` tint, the current one in `findCurrent`, both under the playing
  chord. `AppShortcut` is the app's key table, `FontPinch` Android's pinch
  as steps, `UiPreferences` the column's width over a `PreferenceStore`.
- **In the app**: `Editor/FindBarView.swift` (▸ for the Replace row, the
  field, "3 of 7", ▲ ▼, Aa, W, ✕; the Replace row's field, Replace and
  Replace all; the wrap notice under the first row for 2 s);
  `EditorController.find(_:)`, which brings the match into view on both axes
  and gives the text the keys back when the bar closes in Edit;
  `App/AppShortcuts.swift` (the menu commands, `AppModel.shortcut(_:)`,
  `UserDefaultsPreferences`, `-CNScreen find`); the ribbon's Find; the pinch
  recognizer on the text view.
- **The flows**, as the desktop's: Command-F (or the ribbon's Find, which
  opens the Replace row) opens the bar, a one-line selection becomes the
  query, and the search starts from the selection or the caret; typing
  selects the first match from there (none: the caret goes back); Return and
  ▼ go to the next match, Shift-Return and ▲ to the previous one, wrapping
  with "Continued from the top" or "…from the bottom"; Aa and W search again
  from the selection's start; the count says "3 of 7", "7 matches" or "No
  matches" (red). Replace replaces the selected match (`replace_match`, the
  text sent first) and selects the next one once the session's edit is in,
  or its refusal while a song plays (`EditRefused`); a selection that isn't
  a match goes to the next match first. Replace all is `replace_all` with
  the caret: one undo step, the status (a snackbar in Edit). ✕ and Escape
  close the bar and drop the tints; the query stays, and Command-G or
  Shift-Command-G finds it again with the bar closed. Play mode opens the bar
  without its Replace row, as the desktop's Play workspace does, and the
  current match shows in its tint, since the frozen text has no selection.
- **The font settings** were already in Settings › General (the previous
  slice): the family as Monospace, Sans or Serif (Android's three kinds; the
  configured family is kept when it is already of that kind, else
  `TkFixedFont`, `Sans` or `Serif`) and the size, 6–72. The editor draws
  `EditorState`'s family and size as before: the system's monospaced design,
  the system font or New York, at the size × 4/3, scaled by Dynamic Type.
  The integration test and the session test change both from Settings and
  check what the editor draws.
- **The pinch** (both tabs): from the size when two fingers come down, each
  new whole size of `size × scale` (6–72) goes to the session as
  `step_font_size`, as Android's does, so the session keeps and saves it
  like Command-= and Settings; the model's size isn't read again until the
  pinch ends, since the `EditorState` comes back behind the fingers.
- **The keys** come from one table, `AppShortcut`, and act wherever the
  keys are (Play mode included, as Android's root key handler); the iPad
  lists them while Command is held, and iPadOS's menu bar shows them. New
  Song ⌘N, Save ⌘S, Save As… ⇧⌘S, Larger Text ⌘=, Smaller Text ⌘-, Reset
  Text Size ⌘0 and User Guide ⌘? (Android's F1) are SwiftUI menu commands.
  Open… ⌘O, Find ⌘F, Find & Replace ⌥⌘F, Find Next ⌘G and Find Previous ⇧⌘G
  are the system menu's own items, sending `open:`, `find:` and the rest up
  the responder chain: run 45493241329's log showed UIKit reporting the same
  keys as SwiftUI commands as conflicts ("undefined behavior"). The text's
  `EditorHost` (the sideways scroll view around the text view) answers
  those actions (added under their selectors at run time, since the SDK
  declares some on UIResponder and not others) and takes the keys whenever
  nothing else has them, as Android's focusable root does: in Play, in Edit
  before the text is tapped, and after a field elsewhere (rename, Insert,
  Settings) lets them go. A scroll view has no keyboard, key commands or
  undo manager, so the frozen text stays frozen; while the text has the
  keys, the actions pass through it to the host. While the find field has
  the keys, ⌘G, ⇧⌘G and ⌘F are the field's own (`onKeyPress`); ⌘O does
  nothing there. They act only on the bare main screen (Android's are
  the song screen's: a sheet, a dialog or Settings has the keys then). The
  text view keeps its own too: undo, redo, the line commands, and a hidden
  Command-+ beside the app's Command-=.
- **The column's width** (Play on its side with the chord sheet): kept in
  UserDefaults under Android's `side_fraction` when the handle is let go,
  clamped to 30–70 % on the way in and out; the privacy manifest lists
  `CA92.1`.
- **Live check:** `SessionTests` (`ChordNotepadTests/EditorFeaturesTests.swift`)
  restores a song in a real text view, opens Find and Replace through
  `AppModel.shortcut`, checks the selection and the two tints on the text
  storage, goes next and back (also with the system menu's `findNext:` and
  `findPrevious:` sent to no target, as a key press sends them: to the host
  with the keys in Edit, through the text once it has them, to the host
  again in Play, where the Replace row goes), replaces all (the text, "Replaced 3
  matches", one undo), pinches (the session's size, the settings' value,
  the view's font), runs Command-0 and the text view's own Command-+ through
  the responder chain, checks the shortcuts wait under the menu, sets the
  serif font at 16 in Settings (the view's font and the text's attribute)
  and keeps the column's width in UserDefaults. `-CNScreen find` opens the
  bar live on the quick-start song for CI's `<device>-find.png`.

Deliberate differences:

- Find and Replace exists at all (Android has none); it follows the Qt
  desktop.
- Find and Replace is Option-Command-F (Apple's key), not the desktop's
  Ctrl+H: Command-H is the iPad's Home Screen key. Find Next and Previous are
  Command-G and Shift-Command-G (Apple's), not F3, which an iPad's keyboard
  doesn't have; the desktop's Ctrl+G (Go to line) has no counterpart, and
  there is no Go to line.
- The ribbon has Find (after Redo), which Android's ribbon hasn't; it opens
  the bar with the Replace row. Play mode has no Find button: Command-F only.
- Switching to Play with the bar open keeps it, without its Replace row (the
  desktop's Play workspace); back in Edit, ▸ shows the row again.
- The menu titles of Open… and the find keys are the system's ("Find",
  "Find & Replace"), since the system menu lists them.
- The field isn't selected when the bar opens again (SwiftUI's text field
  can't select its text); a one-line selection still replaces the query.
- The current match is a stronger tint over the selection rather than the
  desktop's swapped selection colour (the text view's selection is the
  system's, and Play mode has none).
- The user guide is Command-? (Apple's Help key), not Android's F1: an
  iPad's keyboard has no F1, and SwiftUI's menu commands can't take one.
- Command-+ is listed once, as Larger Text ⌘=; Android lists both keys.

What CI doesn't test: a hardware keyboard's real key presses (the menu
commands' bindings, the HUD, Return, Shift-Return and Escape in the field;
the session test calls the commands' handler and sends the text view's key
command through the responder chain, and there is no XCUITest target), the
iPadOS menu bar, a finger pinch (the session test calls the recognizer's
handler), the software keyboard over the bar on a phone, typing into the
find field, the column's handle dragged by a finger, VoiceOver.

### Audio, multitasking and accessibility

The ninth slice: the platform glue, ported from Android's `lifecycle/`
(`PlaybackAudioPolicy.kt`, `AndroidAudioGateways.kt`, `AppLifecycleHooks.kt`,
wired in `AppGraph.install`). Nothing in the bridge schema changed: the
session's `pause`, `app_background` and `app_foreground` are all it takes.

- **In the kit** (tested on Linux): `Lifecycle/PlaybackAudioPolicy.swift`
  (which event sends which command, and the userInfo values of
  AVFoundation's notifications, decoded), `Main/AccessibilityLabels.swift`
  (the icon buttons' VoiceOver labels) and `keyboardOverlap` in
  `Main/ScreenLayout.swift`.
- **In the app:** `App/AudioSessionObserver.swift` (the notifications into
  the policy, its commands into the session; `SystemAudioFocus`, the
  category while a song plays), `AppModel.scenePhaseChanged` (the scene phase
  into the policy), `MainView.keyboardChanged` (the keyboard over the
  window, not the screen).

**Which event sends what:**

| Event | Android | iOS |
|---|---|---|
| Play starts | ask for audio focus (`AUDIOFOCUS_GAIN`); denied: `pause` | Playback without mix-with-others, `setActive(true)` (`SystemAudioFocus`); refused: `pause` |
| A resume after a pause | focus still held: nothing | the same, unless the output was reopened since (then ask again) |
| Back to idle (stop, ⏮, the end) | give focus back | Playback with mix-with-others again (the session stays active: the output is open) |
| Another app's audio, a call | focus lost: `pause` | interruption began: `app_background` |
| The interruption over | (no focus gain handled) | interruption ended: `app_foreground` on screen; never a resume, `shouldResume` or not |
| Headphones out, Bluetooth gone | "becoming noisy": `pause` while playing or paused | route change `oldDeviceUnavailable`: `pause` while playing or paused; other reasons nothing |
| The media services reset | (none) | `app_background`, then `app_foreground` on screen |
| The app leaves the screen | `onStop`: `app_background` | scene `background`: `app_background` |
| Back on screen | `onStart`: `app_foreground` | scene `active` after `background`: `app_foreground` |

- **Why `app_background` for an interruption.** The system stops the app's
  output for an interruption (and destroys it in a media services reset);
  FluidSynth's CoreAudio driver doesn't watch for that, so a chord tapped
  afterwards would be silent. The only way through the bridge to a new
  driver is `app_background` (pause, save the settings, release the output)
  then `app_foreground` (open it again). The policy sends the second only on
  screen and only once the interruption is over; if no end comes (iOS
  doesn't promise one), the next play or tap opens the output itself, as
  after the background. An interruption that only says the app was
  suspended (iOS 14.5 to 16) is ignored.
- **The category.** FluidSynth sets it each time it opens its output
  (`setupAVAudioSession` in `fluid_coreaudio_avaudiosession.m`, 2.6.1):
  Playback with mix-with-others and default-to-speaker (the simulators'
  self-test reads both back, run 45517323581), then `setActive(true)`. That happens
  at the session's start, at each `app_foreground` and when a play or tap
  reopens a released output, so whatever the app sets is overwritten then.
  **Playback, not Ambient:** Android plays music at the media volume
  whatever the ringer mode, and a music app on iOS plays through the
  Ring/Silent switch too; Ambient would mute the song with the switch and
  mix it under other apps. **Mix-with-others only while idle:** a tapped
  chord plays along with other apps' music (Android's taps take no focus),
  while a song takes the session for itself (Android's focus), which stops
  other apps' music and lets theirs interrupt ours. The policy asks again
  after every reopened output, since FluidSynth made it mixable.
- **No background playback** (no `UIBackgroundModes` audio), as on Android
  (BACKLOG, "Android background playback"): the scene in the background
  sends `app_background`, which pauses; the user taps ▶ to go on.
- **The self-test** reports the category's options (`audioOptions` in
  `selftest.json`, a row in Diagnostics), so a device shows what
  FluidSynth and the app left.
- **iPad multitasking.** Every layout rule reads the window's size, not the
  device: `ScreenLayout` (a phone below 600 pt on the smaller side,
  Android's sw600dp), the Settings panes (600 pt), the identifier's dialog
  (600 × 600). So a third or a half of an iPad in Split View, Slide Over
  and a small Stage Manager window are laid out as a phone upright, and a
  short wide Stage Manager window as a phone on its side (`MultitaskingTests`).
  The catalog draws the main screen, Settings and the identifier at about a
  third (375 × 820) and a half (585 × 820) of the iPad Air on its side. The
  keyboard's height is now how much of the window it covers
  (`keyboardOverlap`, the frame in the screen's coordinates): it was the
  screen's bottom less the keyboard's top, wrong for a window that doesn't
  reach the screen's bottom. `UIRequiresFullScreen` stays unset, so iPadOS
  offers Split View and Stage Manager.
- **One window** (`UIApplicationSupportsMultipleScenes` false): the process
  has one Python interpreter and one session, so a second window could only
  show the same song with the same playback. Android's app is one activity
  too.
- **VoiceOver labels.** Every button whose face is an icon has a label
  (`.accessibilityLabel`), and the icons themselves are hidden from
  VoiceOver. The words are Android's `contentDescription` strings in one
  table (`AccessibilityLabels`, with the Settings, identifier, tour and
  licence texts the kit already had); `AccessibilityLabelsTests` reads
  `android/app/src/main/res/values/strings*.xml` and checks each, and the
  find bar's against the Qt desktop's tooltips (`FindBar.qml`). The
  dialogs' pickers say their field and value. `AccessibilityTests` hosts
  every catalog screen in a window and walks its accessibility elements as
  VoiceOver does: a button without a label, or any element whose label is
  an image's name (`mdi_menu`, `chevron.right`), fails, and the main
  screens' known buttons must carry Android's words. Dynamic Type is the
  catalog's `accessibility2` images.
- **Play's text for VoiceOver.** In Play the frozen text view is a
  container of `PlayTextElement`s (`Editor/PlayText.swift`), built from the
  kit's `playAccessibilityItems`: each chord its own button (its label the
  chord as written; activating it does what a tap does, `tap_chord_at`; the
  marker's chord is selected), and the other text of each line, before,
  between and after its chords, as static text. The frames are the text's,
  asked for when VoiceOver needs them, so they follow scrolling and
  wrapping; the elements are made again only when the text or its spans
  change, so VoiceOver's focus stays put while a song plays. Edit keeps the
  text view's own text element. Before, UIKit made one element per line,
  and activating it hit the line's middle chord (S0 issue 8). The
  editor's session test checks the labels, the frames and an activation.
- **The export status on iOS** is the desktop's "Exported MIDI: song.mid
  (iCloud Drive)" (audio and PDF the same), said only once the export
  picker saved the file, with the place picked; a cancelled picker says
  nothing ("Files", Exports). The guide's iOS edition says so.

Deliberate differences from Android:

- Focus is the audio session's mixability: while idle the app mixes with
  other apps' audio, as Android's taps do without focus.
- An interruption releases and reopens the output (`app_background`,
  `app_foreground`), where Android's focus loss only pauses: the system
  stops an iOS app's output, Android's stays open.
- The settings are saved at each interruption too (part of `app_background`).
- A media services reset has no Android counterpart.

What CI tests: `SessionTests` (`AudioSessionTests.swift`) holds a song
playing with the FakePlayer (`CN_TEST_FAKE_PLAYER=hold`) and posts the
notifications with the system's names, object and userInfo: an interruption
pauses and its end (with `shouldResume`) reopens the output without a
resume, a plugged-in device and a category change don't pause, the old
device gone does, the background pauses, a media services reset pauses and
opens a new output, focus is asked for at each play after a reopened output
and given back at the stop; then the real `SystemAudioFocus` on the
simulator's session, reported in `audio-session.json` (not blocking).
`AccessibilityTests` walks the catalog screens; the catalog draws the split
widths. What CI doesn't test: a real call, alarm or Siri, a real route
(headphones, Bluetooth), the Ring/Silent switch, other apps' music stopping,
a real media services reset, Split View, Slide Over and Stage Manager
themselves (simulator windows can't be split from a test; the catalog draws
the widths), the keyboard over a split window, VoiceOver itself.

### Preview catalog

`PreviewCatalog.screens` lists every screen with the fixtures it is shown
with and the windows it is drawn in; adding a screen is one line there.
`#Preview`s use the same `PreviewCatalog.scene("<scene>")`. `CatalogTests`
renders each entry with `ImageRenderer` at iPhone 17 (402×874 pt, @3x) and
iPad Air 11-inch (820×1180 pt, @2x), and on their sides (874×402,
1180×820) where the layout differs, and the iPad on its side in Split View
(about a third, 375×820, and a half, 585×820), light and dark, default and
`accessibility2` text: 580 PNGs.

| Screen | Scenes | Windows |
|---|---|---|
| `edit` | `scarborough_edit`, `empty_song`, `editor_mid_edit`, `editor_european` | iPhone, iPad, iPad on its side |
| `play` | the three Scarborough Fair scenes, `play_with_chord_sheet`, `chord_sheet_staff`, `quick_start_edit` (no sheet) | all four |
| `keyboard` | `scarborough_edit` in Edit with a grey stand-in for the keyboard (the header collapses on the phone on its side) | iPhone on its side, iPhone |
| `menu` | `scarborough_edit`; `files_recent` (the recent songs) | iPhone, iPad |
| `rename` | `scarborough_edit`; `errors` for the refused rename with Save as… | iPhone, iPad |
| `discard` | `discard_question` in Edit: the unsaved-changes question | iPhone, iPad |
| `export`, `export_edit` | `export_done`: "Exported MIDI: … (iCloud Drive)" in Play's status line; in Edit as a snackbar | iPhone, iPad; iPhone |
| `export_preparing` | `export_done` with "Preparing export…" over it: an audio export at 42 % (the spinner drawn, since ImageRenderer can't draw a ProgressView; a solid colour for the material) | iPhone, iPad |
| `open_error` | `errors` in Play with the open failure as a snackbar | iPhone, iPad |
| `examples` | the Examples sheet, from the bundle's `examples/` | iPhone |
| `diagnostics` | a sample self-test report | iPhone, iPad |
| `voicing`, `instrument`, `speed`, `speed_manual`, `song_defaults` | `player_sheets` in Play: the sheet over the screen (Manual… over the speed sheet). The kit's session has the FakePlayer and no SoundFont, so the instrument families list no programs and no current instrument there; CI's `<device>-instrument.png` shows a family's programs live | iPhone, iPad |
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
| `quick_start` | `quick_start_tour`: the tour's first page | iPhone, iPad |
| `quick_start_chords` | `quick_start_tour`: the second page, its 41-column example shrunk to fit the box | iPhone |
| `help_play`, `help_play_phone`, `help_edit`, `help_voicing`, `help_rename` | the guide's scenes (`ios/tools/help_shots.json`): `grace_playing` in every window; the four views, the metronome at 125 % and the playhead on Em; `grace_edit` and `colours_edit` in Edit; the Voicing sheet over `grace_play` (My 7-String made by then); Rename over `grace_edit` | all four; iPhone; iPhone, iPad, iPhone on its side; iPhone; iPhone |
| `find`, `find_play`, `find_replaced` | `scarborough_edit` with the find bar and its Replace row (Am, match case and whole words, the second of the matches selected, Em to replace with); `scarborough_piano_roll` in Play finding "parsley" (no Replace row; beside the chord sheet on the phone on its side); `find_replaced` after Replace all, its status as a snackbar | iPhone, iPad; iPhone, iPad, iPhone on its side; iPhone, iPad |
| `split_play`, `split_edit`, `split_settings`, `split_identify` | `scarborough_piano_roll` in Play (the sheet below the text), `scarborough_edit`, `settings_open` (one pane), `identifier_cmaj7` (full screen): the iPad's Split View windows, laid out as a phone's | the iPad's third and half |

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

### App Store requirements

`ITSAppUsesNonExemptEncryption = NO` (the app uses no encryption beyond
the system's); `PrivacyInfo.xcprivacy` with no tracking and no collected
data, and the required-reason APIs the embedded CPython links: file
timestamps (`C617.1`, files in the container), system boot time (`35F9.1`,
`time.monotonic` and Swift's clocks) and disk space (`E174.1`, `statvfs` is
in the binary), plus `3B52.1` for the size of a song the user picked or
opened from Files, and user defaults (`CA92.1`: the side column's width,
read and written by the app only). `_ssl` and `_hashlib` (which
link OpenSSL, on Apple's list of SDKs that need a manifest) get one each
from `packaging/ios/privacy/`. The icon is one 1024 px PNG, flattened on the
Android icon's cream (`ios/tools/make_app_icon.py`, Inkscape and Pillow).

`ios/tools/check_app_store.py` checks the built app against these on CI (the
device build, the unsigned archive and the TestFlight archive) and fails
when one slips:

- Info.plist: bundle ID `com.tibich.chordnotepad`, the encryption flag present
  and NO, `CFBundleIcons` and `CFBundleIcons~ipad` naming AppIcon, a launch
  screen, all four iPad orientations (multitasking), numeric versions;
- the privacy manifest: present, no tracking, and a reason for every
  required-reason category whose APIs a binary in the app uses. The use is
  read from the binaries (every Mach-O is searched for the symbols and
  Foundation names Apple lists per category), so a new CPython module or
  Swift call that starts using one fails the build instead of App Store
  Connect's upload check. `_ssl`'s and `_hashlib`'s own manifests cover them;
- native code only in the executable and in frameworks, each marked for
  iPhoneOS with a MinimumOSVersion;
- the icon: Xcode 26 compiles the single 1024 px source into one 1024 px
  AppIcon rendition in Assets.car (`assetutil --info`) and writes the loose
  `AppIcon60x60@2x.png` and `AppIcon76x76@2x~ipad.png` that
  `CFBundleIconFiles` names; both must be there, and the source must be
  1024 × 1024 with no alpha channel.

The tests (`tests/test_ios_app_store_check.py`) run it on Linux over a
synthetic bundle.

## CI

`.github/workflows/ios.yml` runs on every push to main that touches `ios/`,
`core/`, `packaging/ios/`, the schema, the Python pins, the SoundFont, the
glyph export script, Android's chord sheet and voicing form fixtures, the
help screenshots' songs the scenes use (the kit's tests read them), the
examples, Android's icons the asset catalog copies (the drawables and
`SettingsIcons.kt`), the licence texts, the user guide (`help/`, its Sphinx
pins in `android/docs-requirements.txt`, Android's licence list the iOS
guide's entries must match) and `VERSION`, and by hand (workflow_dispatch). Each push gets its own run; a
newer one doesn't cancel an older one.
`build.yml` ignores pushes that touch only `ios/`, `packaging/ios/`,
`ios.yml` or this file. A push runs four jobs at once, three of them on `macos-26`
(arm64), so a run takes as long as its slowest job rather than the sum (it
was 44 minutes as one app job; the iPad's screenshots alone took 16, with
both simulators booted on one runner):

- **kit:** `swift test` on the Mac host with setup-python's 3.14 (through
  `CN_PYTHON_PKGCONFIG=python3-embed`, set only for that step), the app's
  packages from `build_python_bundle.py` as `CN_SITE_PACKAGES`, and the
  macOS app's own libfluidsynth (`packaging/macos/build_fluidsynth.sh`,
  cached) as `CHORD_NOTEPAD_LIBFLUIDSYNTH`.
- **simulator** (iPhone, iPad; a matrix, each on its own runner with only
  its simulator booted): the shared setup
  (`.github/actions/ios-app-setup`: the frameworks, cached on the scripts,
  the pins and the Xcode version; the Python bundle; the guide; XcodeGen),
  a `build-for-testing` for its simulator, `test-without-building` (the
  session test with the FakePlayer, the blocking offline render and the
  diagnostics zip; the catalog on the iPhone only, since it renders both
  sizes anyway), the real app launched for screenshots and the self-test,
  and the live CoreAudio check (non-blocking: a runner may have no audio
  device). One simulator failing doesn't cancel the other.
- **device:** the same setup, then a Release `generic/platform=iOS` build
  with `CODE_SIGNING_ALLOWED=NO`, checked for the privacy manifests, the
  compiled icon and the stdlib, then by `check_app_store.py` ("App Store
  requirements"). It packs the prebuilt inputs a session on the borrowed
  Mac builds from (`ios-build-inputs`) and rehearses that session's
  bootstrap with only the system's PATH (so the build phases use Xcode's own
  `python3`, as on her Mac): a `--dry-run` of the Xcode and runtime steps,
  which must find nothing to change, then `mac_bootstrap.sh --verify` under
  `/bin/bash` 3.2, from an SSD
  folder laid out as `prepare_ssd.sh` lays it out (a git bundle, the inputs,
  XcodeGen's zip, SHA256SUMS), cloning, generating, building and running the
  app on a simulator and listing devices (`ios-bootstrap-rehearsal`).
- **merge** (Ubuntu): joins each simulator's `ios-screenshots-<device>` and
  `ios-results-<device>` (and the device job's build log) into
  `ios-screenshots` and `ios-results`, the names below.

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
- `ios-screenshots`: `<iphone|ipad>-quickstart.png` (the first launch after
  the install: the tour over the quick-start song, `startup.json` says it
  opened and which song),
  `<iphone|ipad>-main.png` (the quick-start song in
  Play, as it opens), `<iphone|ipad>-menu.png` (`-CNScreen menu`),
  `<iphone|ipad>-selftest.png` (Diagnostics),
  `<iphone|ipad>-chordsheet.png` (Play with the chord sheet shown, its
  buffer from the live session), `<iphone|ipad>-editor.png` (Edit after the
  app typed a long chord line into the editor, the session's highlight
  painted, the keyboard up), `<iphone|ipad>-speed.png`, `-instrument.png`
  (the Guitar family's programs, Steel Guitar chosen, from the real
  SoundFont), `-insert.png`,
  `-capo.png`, `-identify.png` and `-find.png` (the speed sheet at 125 %,
  Insert › Tempo with the keyboard up, Suggest Capo scored, the identifier
  with Cmaj7 picked, Find and Replace with "the" typed; `tool-<name>.json`
  says each got there), `<iphone|ipad>-settings.png`,
  `-voicings.png` and `-about.png` (Settings › General, Settings › Voicings
  with the standard guitar's form, About),
  `<iphone|ipad>-export-preparing.png` ("Preparing export…" over the song
  during an audio export), `<iphone|ipad>-export.png` (the export picker
  after it), `<iphone|ipad>-export-saved.png` (the status "Exported audio:
  01_quick_start.wav (Chord Notepad)" after a simulated save), `<iphone|ipad>-pdf.png` (the export
  picker after a PDF export; `pdf.json` has its pages, a line of the song
  found in its text and the font's advance, and `export.pdf` is the file),
  `<iphone|ipad>-relaunch.png` (the relaunch check's song back unsaved in
  Edit after the app was ended in the background; `draft.json`,
  `draft-kept.json` and `restored.json` say each step passed, "The last
  song"),
  `-guide.png` (☰ › User guide's first page), `-families.png` (the
  Instrument sheet's families, Grand Piano the current one), `-hint.png` (a
  red `{bpm: 500}` explained in Play), `-keyboard.png` (a new song with
  "C  Am  F  G" typed and the keyboard up), `-landscape.png` (the phone on its
  side typing: the header gives way to the floating undo chip), the guide's
  live screenshots, the app's Diagnostics
  folder from each simulator (`launch.json`, `chordsheet.json`, `editor.json`,
  `export.json`, `selftest.json` with the live
  audio result, the core's log) and `<device>-app.log` (the unified log of
  the app's process).
- `ios-results`: the `.xcresult` bundles (open in Xcode, or
  `xcrun xcresulttool` on a Mac; the catalog PNGs and the test's
  `selftest.json`, `chordsheet-live.png`, `editor-live.png` and `play-live.png` are attached) and the xcodebuild logs.
- `ios-kit-tests`: the kit's `swift test` output on macOS.
- `ios-help`: the iOS edition of the guide as the app ships it.
- `ios-build-inputs` (30 days): `ios-build-inputs.tar.gz`, the frameworks,
  the Python bundle and the guide from `ios/build`, with `INPUTS_COMMIT`.
- `ios-bootstrap-rehearsal`: the rehearsal's `report.txt`, build log,
  simulator screenshot and the app's Diagnostics folder.

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

To build the same on a Mac with network access:

```sh
packaging/ios/build_fluidsynth.sh ios/build/Frameworks
packaging/ios/fetch_python.sh ios/build/Frameworks python3.14
python3.14 -I packaging/ios/build_python_bundle.py ios/build/python-bundle
xcodegen generate --spec ios/project.yml
open ios/ChordNotepad.xcodeproj
```

On the borrowed MacBook nothing is downloaded or compiled but the app:
`mac_bootstrap.sh` unpacks CI's `ios-build-inputs` into `ios/build` instead
("Device sessions"). The build phases then need only Xcode's own `python3`.

### Release lanes

Three more jobs, none of which runs on a push (`tests/test_ios_workflow_gating.py`
reads the workflow and checks which jobs each event runs):

- **release-gate** (Ubuntu, environment `ios-release`): runs on the monthly
  schedule (the 1st, 06:17 UTC) and on a dispatch with `testflight` or
  `development_ipa` ticked, from main only. With no signing secret set it
  prints a notice and every lane is skipped; with only some set it fails and
  names the missing ones. It picks the commit (a dispatch: its own; the
  schedule: the newest one whose push or dispatch run is green) and the build
  number.
- **testflight** (environment `ios-release`): after the gate, and on a
  dispatch only when this run's kit, simulator and device jobs passed. The
  shared setup, the certificates into a temporary keychain
  (`packaging/apple/import_certificates.sh`), `ios/tools/ci_archive.sh
  archive` (automatic signing, `-allowProvisioningUpdates` and the API key:
  `-authenticationKeyPath/-authenticationKeyID/-authenticationKeyIssuerID`),
  `check_app_store.py` on the archived app, the dSYMs kept
  (`ios-testflight-dsyms`, with `build-info.txt`: version, build, commit,
  UUIDs), then `-exportArchive` with `packaging/ios/ExportOptions-testflight.plist`
  (`method` app-store-connect, `destination` upload). The schedule re-uploads
  monthly because TestFlight builds expire after 90 days, so there are always
  60 or more days left.
- **development** (environment `ios-release`, dispatch only): the same
  archive exported with `ExportOptions-development.plist` (`method`
  debugging: debuggable, installs on the registered iPhones). The IPA, its
  dSYMs and `build-info.txt` go into `ios-development` as
  `ios-development.tar.enc`, encrypted with `IOS_ARTIFACT_PASSPHRASE`,
  because the profile inside lists the registered devices' UDIDs and the
  repository's artifacts are public. On Linux:
  `openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:IOS_ARTIFACT_PASSPHRASE -in ios-development.tar.enc | tar -x`.
- **archive-check** (dispatch with `unsigned_archive`, no secrets): the same
  archive unsigned, the App Store checks on it, `plutil -lint` of both
  ExportOptions plists and a check that `xcodebuild -help` knows their
  methods, and the dSYMs (`ios-unsigned-archive`). It rehearses the lanes
  before there is an account.

**Build number:** `CFBundleVersion` is the workflow's run number, the same
number the simulator and device builds of that run carry. It grows with
every ios.yml run (push, dispatch or schedule), so App Store Connect never
sees one twice for a version; a re-run of the same run adds its attempt
(`57.2`, after 57 and before 58). A timestamp would also grow, but wouldn't
match the run the dSYMs and logs belong to. `MARKETING_VERSION` is `VERSION`.

**Signing:** the archive is signed with the Apple Development certificate
from the secrets (automatic signing needs a development identity on the
machine; one Xcode makes itself on a fresh runner every time would pile up
in the account). For the TestFlight export Xcode uses a cloud-managed Apple
Distribution certificate through the Admin key. If that doesn't work on an
individual account (plan A.4), set `IOS_DISTRIBUTION_P12_BASE64` and its
password: the job imports it too, and the export uses it.

A dispatch on a commit whose push run is still going waits for it (the
`ios-<sha>` concurrency group).

| Secret (environment `ios-release`) | Lanes | What |
|---|---|---|
| `ASC_KEY_P8_BASE64` | all | base64 of the Team API key `AuthKey_<id>.p8` (Admin role); also in `release`, for notarization |
| `ASC_KEY_ID` | all | the key's ID |
| `ASC_ISSUER_ID` | all | the issuer ID (Users and Access > Integrations) |
| `APPLE_TEAM_ID` | all | the 10-character team ID (developer.apple.com > Account > Membership) |
| `IOS_DEVELOPMENT_P12_BASE64` | all | base64 of an Apple Development certificate and key (`.p12`) |
| `IOS_DEVELOPMENT_P12_PASSWORD` | all | its password |
| `IOS_ARTIFACT_PASSPHRASE` | development | encrypts the `ios-development` artifact |
| `IOS_DISTRIBUTION_P12_BASE64`, `IOS_DISTRIBUTION_P12_PASSWORD` | testflight, optional | an Apple Distribution certificate, only if cloud signing fails |

Set the environment's deployment branches to `main` (Settings >
Environments > ios-release); no required reviewers, or the monthly upload
waits for a click.

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

## Enrollment day

As late as possible: right before the first TestFlight build is wanted,
since the $99 membership runs for a year from then. Everything here is on
Linux in a browser unless it says S0. Keys, certificates and passphrases stay
outside the repository (a password manager); nothing below goes into a
commit.

**Before (any time, free):**

1. An Apple Account with two-factor authentication by SMS (account.apple.com),
   if there isn't one. It is enough to download Xcode and the simulator
   runtime for the SSD (developer.apple.com/download/all).
2. `ios/tools/prepare_ssd.sh <SSD>` fills the SSD ("Device sessions");
   `readiness.py S0` says whether S0 can go ahead.

**Enrollment:**

3. Try the web first, from Linux: developer.apple.com/account > Enroll >
   Individual. If "Continue enrollment on the web" is offered, finish it
   there (identity, then the payment).
4. If the web flow insists on the Apple Developer app, enroll in S0 under
   his own macOS user on the MacBook (iCloud signed in only there, Find My
   Mac and iCloud Keychain off). That needs the Apple Developer app from the
   Mac App Store, the one download a session can't avoid: it can't be
   fetched on Linux. Enrollment can take up to two days to be approved.

**After approval, in this order (all on the web):**

5. Team ID: developer.apple.com > Account > Membership details (10
   characters).
6. API key: App Store Connect > Users and Access > Integrations > App Store
   Connect API > Request Access (the Account Holder only), then a Team key
   with the Admin role. Download `AuthKey_<key id>.p8` (it can be downloaded
   only once) and note the key ID and the issuer ID.
7. Bundle ID: Certificates, IDs & Profiles > Identifiers > + > App IDs > App,
   explicit `com.tibich.chordnotepad`, no extra capabilities.
8. App record: App Store Connect > Apps > + > New App: iOS, Chord Notepad,
   English (U.K. or U.S.), bundle ID `com.tibich.chordnotepad`, any SKU
   (`chordnotepad-ios`), full access.
9. Certificates from Linux CSRs (`openssl req -new -newkey rsa:2048 -nodes
   -keyout <name>.key -subj "/CN=<name>" -out <name>.csr`, upload the CSR,
   download the `.cer`, then `openssl pkcs12 -export -legacy` with the
   intermediate, as `docs/RELEASE.md` shows for the Developer ID):
   - Apple Development (intermediate: Apple's WWDR G3,
     apple.com/certificateauthority) → `IOS_DEVELOPMENT_P12_BASE64`, `_PASSWORD`;
   - Developer ID Application, G2 Sub-CA (intermediate: Developer ID G2) →
     `MACOS_DEVELOPER_ID_P12_BASE64`, `_PASSWORD`;
   - Apple Distribution only if the first TestFlight run's cloud signing
     fails (plan A.4) → `IOS_DISTRIBUTION_P12_BASE64`, `_PASSWORD`.
10. His wife as an internal tester: App Store Connect > Users and Access > +,
    her own Apple Account address, role Marketing, access to Chord Notepad
    only. She accepts the e-mail on her phone. Then TestFlight > Internal
    Testing > + a group with her in it, automatic distribution on. Internal
    testing needs no Beta App Review. The fallback is an external tester,
    whose first build is reviewed.
11. The environments and secrets (`gh` from the repository):

    ```sh
    gh api -X PUT repos/{owner}/{repo}/environments/ios-release \
        -F 'deployment_branch_policy[protected_branches]=false' \
        -F 'deployment_branch_policy[custom_branch_policies]=true'
    gh api -X POST repos/{owner}/{repo}/environments/ios-release/deployment-branch-policies -f name=main
    base64 -w0 AuthKey_<key id>.p8 | gh secret set ASC_KEY_P8_BASE64 --env ios-release
    gh secret set ASC_KEY_ID --env ios-release        # and ASC_ISSUER_ID, APPLE_TEAM_ID
    base64 -w0 ios-development.p12 | gh secret set IOS_DEVELOPMENT_P12_BASE64 --env ios-release
    gh secret set IOS_DEVELOPMENT_P12_PASSWORD --env ios-release
    openssl rand -base64 32 | gh secret set IOS_ARTIFACT_PASSPHRASE --env ios-release   # keep a copy
    # release (the macOS DMG): the same three ASC_ secrets, and the Developer ID pair
    ```

    The secrets each lane needs are in "Release lanes"; `docs/RELEASE.md`
    has the `release` ones.
12. Her iPhone's UDID from S0's report: `ASC_KEY_ID=… ASC_ISSUER_ID=…
    ASC_KEY_PATH=… python3 -I ios/tools/asc_api.py register-device --udid
    <udid> --name "<a label>"`.
13. First runs: dispatch ios.yml with `unsigned_archive` if it hasn't run on
    this Xcode, then with `testflight`. Wait for processing (10–30 minutes),
    then `readiness.py T`. The notarized DMG first runs with the next weekly
    nightly; check its two macOS legs ("Check notarization").

## Device sessions

Her devices are borrowed for 2–3 hours at a time, so each session is
prepared on Linux and CI first: nothing is downloaded or built on her
machines, and every session ends with artifacts analysed offline. Each
session has a log template in `ios/tools/session_logs/` (copy it outside the
repository, with the date, and fill it in during the session).

| # | Session | Devices | When | Length |
|---|---|---|---|---|
| S0 | Bootstrap and enrollment | MacBook (iPhone for 10 min) | right before enrollment's step 5 | 2.5 h |
| U1 | Simulator runtimes and a re-verify | MacBook, overnight under his user | after S0 | – |
| T1…Tn | TestFlight smoke | iPhone only | after the first upload, then each screen milestone | 30 min |
| S1 | Layout polish (needs Metal, so not a VM) | MacBook | mid-F | 2.5 h |
| S2 | Device debugging and Instruments | MacBook and iPhone, or the VM and iPhone | late F | 3 h |
| S3 | Mac App Store sandbox for the Qt app | MacBook | later | 2 h |

With a Claude Code agent on the Mac, hand it `docs/IOS_MAC_AGENT.md`, a brief
for a session without the SSD that works from a network share and the
network.

The tools, all on Linux except `mac_bootstrap.sh`:

- `ios/tools/prepare_ssd.sh <SSD>` fills the SSD: a git bundle of main and
  the commit of the newest green run, that run's `ios-build-inputs`, the
  pinned `xcodegen.zip`, `xcode-version`, `mac_bootstrap.sh` and
  `SHA256SUMS`. It checks the two Apple downloads are there (by hand:
  `Xcode_<version>.xip`, also with a suffix like `_Universal`, and the
  matching `iOS_<version>_Simulator_Runtime.dmg`) and
  exits 1 while one is missing.
- `ios/tools/readiness.py S0|T|S1|S2 [--date …] [--issues FILE]`: the
  automated checks below, then this section's plan for the session and the
  manual checklist.
- `ios/tools/mac_bootstrap.sh` (on the MacBook, from the SSD): sets up and
  verifies the Mac ("S0" below; its header lists the steps). Every step is
  skipped when done, so it can be run again after a failure; `--dry-run`
  shows what it would change.
- `ios/tools/pull_testflight_feedback.py --out <folder>`: TestFlight's
  feedback screenshots and crash logs.
- `ios/tools/symbolicate.sh <crash.ips> <dSYMs>`: a crash report
  symbolicated with the dSYMs of the run that built it (`ios-testflight-dsyms`
  or `ios-development`); a dSYM whose UUID doesn't match is refused. Needs
  `llvm-symbolizer` (Fedora's LLVM 18 reads Xcode 26.5's dSYMs, checked on
  run 45519499248's) and, for Swift names, `swift-demangle` from the Swift
  toolchain (`SWIFT_DEMANGLE=/mnt/data_linux/Bin/swiftly/bin/swift-demangle`).
- `ios/tools/asc_api.py register-device|devices`: her iPhone's UDID for the
  development profile.

### Session plans

#### S0: bootstrap and enrollment

Before: `prepare_ssd.sh` done and `readiness.py S0` ready; her macOS
version, free disk (60 GB or more) and iPhone iOS version known. Xcode 26.5
(CI's pin) needs macOS 26.2 or later (developer.apple.com/support/xcode,
read 2026-11-25); if her Mac runs an older macOS, ask whether she would
update it, or the session can only enroll. Xcode 26.5 runs apps on iOS 15
to 26.5: a newer iOS on her iPhone needs a newer Xcode for S2 (the pin in
`ios/.xcode-version` moves with CI's image).

| Minutes | What |
|---|---|
| 0–10 | She creates his macOS user (an administrator for the session, or `--admin <her user>`). |
| 10–20 | Plug in the SSD; `/Volumes/<SSD>/mac_bootstrap.sh --ssd /Volumes/<SSD> --dry-run`, then `--only extract` in the background (`nohup … > ~/extract.log &`, 20–40 minutes). |
| 20–85 | Enrollment in the Apple Developer app, if the web flow didn't work ("Enrollment day", step 4). |
| 85–110 | `mac_bootstrap.sh --ssd /Volumes/<SSD>`: Xcode into /Applications, the licence and `-runFirstLaunch` (her password), the simulator runtime, then the repo, XcodeGen, the inputs, the project, a simulator build and run. |
| 110–135 | Her iPhone plugged in, unlocked, Trust tapped: the script's device step (or `--only device`) records UDID, model, iOS version, pairing and Developer Mode. Developer Mode only if she agrees (Settings > Privacy & Security; the phone restarts). |
| 135–150 | The session log; copy `session-reports/` off the SSD. |

Bring back: `session-reports/<date>/` (report, build log, screenshot,
devices.json), the enrollment confirmation, the UDID (a secret: not in the
repository), a photo of anything odd. Fallback: if the ID is rejected, the
bootstrap only and a support case; if Xcode won't install, enrollment only.

#### U1: simulator runtimes and a re-verify

Overnight under his user, if she agrees: another runtime from the SSD
(`xcrun simctl runtime add`) and `mac_bootstrap.sh --verify` for a fresh
report.

#### T: TestFlight smoke

Before: `readiness.py T --tester-email <her address>` ready (invite
accepted, the build processed and 30 or more days from expiry, the issue
list), the checklist printed. Agenda: install from TestFlight; under a
screen recording, the quick-start song, tap a chord and hear it, play and
pause, background and resume, the silent switch, a headphone or Bluetooth
route change, an alarm interruption (later the Files picker and a StoreKit
purchase); then Export diagnostics and TestFlight feedback (screenshot,
comment). After: `pull_testflight_feedback.py`, and `symbolicate.sh` on any
crash. Fallback: a screenshot of the install error and the self-test screen.

#### S1: layout polish

Before: the CI catalog PNGs reviewed offline into a numbered issue list,
`readiness.py S1 --issues <list>` ready, a fresh `prepare_ssd.sh` (the clone
on the Mac is left alone if it exists; `git -C ~/ChordNotepad/chord-notepad
fetch /Volumes/<SSD>/chord-notepad.bundle '+refs/*:refs/remotes/ssd/*'`
brings it up to date). Agenda: `mac_bootstrap.sh --verify` (0–15); fix
issues in Previews and the simulator, iPad split view, rotation, keyboard,
Dynamic Type, one commit per issue (15–125); push and record what snapshots
can't show (125–150). Fallback: snapshots plus the simulator if Previews
break.

#### S2: device debugging and Instruments

Before: the UDID registered, then the development IPA built (dispatch with
`development_ipa`; the profile only covers devices registered before the
run), `ios-development` decrypted onto the SSD, Developer Mode on, Xcode
matching her iOS, a repro list from TestFlight logs; `readiness.py S2
--udid <udid> --issues <list>` ready. Agenda: connect and install with
`xcrun devicectl device install app --device <udid> ChordNotepad.ipa` (0–25,
device preparation can take 10–30 min); Instruments, saving each `.trace`:
Audio System Trace with signposts for tap-to-sound latency, Time Profiler for
launch including the music21 import, Allocations during playback (25–90);
LLDB on the open issues with `log stream` on our subsystem (90–150); copy
everything off (150–170). Fallback: simulator Instruments and the TestFlight
build's timing logs.

### Readiness checklist (before each session)

`ios/tools/readiness.py <session>` checks CI is green, the artifacts the
session needs are there and won't expire before it (`ios-build-inputs`, the
catalog and screenshots, `ios-development`, `ios-testflight-dsyms`), and with
App Store Connect credentials the TestFlight build's processing state and
expiry, her tester status and the registered UDID, and that the issue list
gives each issue an expected result. Exit status 0 is ready. By hand:

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
     Then delete one of them in Files and open it from Recent: how long
     until "File not found" (the log's "A bookmark doesn't resolve after …
     s"; it took about a minute once in CI).
  4. A song in iCloud Drive removed from the device ("Remove Download"),
     then opened from Recent online and in flight mode: it downloads, or
     the "not downloaded yet" message after 20 s.
  5. Rename (tap the title) a picked song: renamed, or the Save As offer.
  6. Export MIDI and audio: "Preparing export…" (the percentage counting
     for audio, VoiceOver reads it), the export picker after it with the
     name in its "Save as" field, the file plays in Files, the status names
     the folder picked ("Exported audio: x.wav (iCloud Drive)", a provider's
     folder); cancel the picker once (nothing said); Cancel on the dialog
     during a long audio export (no picker, Export audio works again at
     once).
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

  Standing items for the guide, the tour and Export PDF:
  1. Install fresh and launch from the Home screen: the tour opens over the
     song; untick "Show at startup", close, relaunch: no tour; Settings ›
     General shows the switch off. Open a `.txt` from Files with the app
     closed: no tour.
  2. ☰ › User guide: scroll, the theme's menu, the search, a link inside the
     guide, a link to a web site (Safari opens), the edge swipe back through
     the pages, ← back to the song; the same in dark mode, and switch the
     system's look while the guide is open.
  3. ☰ › Export PDF… on a long song: the export picker, save to Files and to
     iCloud Drive, open the PDF in Files and print it; cancel the picker once.
     A4 on a device set to a European region, Letter on one set to the US.

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
     candidate (rolled), tap a candidate and Insert (inserted, closed), on the phone
     upright and on its side and on an iPad; the notes sound.
  6. The ribbon on the smallest phone: drag it sideways, tap ›.

  Standing items for Find, the font, the pinch and the keys:
  1. The ribbon's Find on a phone: type a query with the software keyboard
     up (the bar stays above it, the match scrolls into view), ▲ ▼ past the
     ends (the notice), Aa, W, Replace, Replace all, then undo once; ✕.
  2. With a song playing: Replace is refused, the next match still selected.
  3. An iPad with a keyboard: hold Command (the shortcut list shows File,
     Edit and View with the app's keys), then ⌘N, ⌘O, ⌘S, ⇧⌘S, ⌘F, ⌥⌘F,
     ⌘G, ⇧⌘G, ⌘=, ⌘-, ⌘0 and ⌘+ in Edit and in Play; Return, Shift-Return
     and Escape in the find field; the menu bar (iPadOS 26) lists them.
  4. ⌘? opens the user guide (or does the key need Shift declared?); after
     closing the rename dialog, Insert or Settings, ⌘F and ⌘O still work; in
     Play no keyboard appears and ⌘Z does nothing.
  5. Pinch the text in Edit and in Play: the size follows the fingers, stays
     after a relaunch, and Settings › General shows it.
  6. Settings › General: each font family and a typed size, in the editor.
  7. Play on a phone on its side with the chord sheet: drag the handle,
     relaunch, the column keeps its width.

  Standing items for audio, multitasking and accessibility:
  1. Play a long song, then: a call to her iPhone (decline it), an alarm or
     a timer going off, Siri ("Hey Siri" or the side button). Each time: the
     song pauses ("Paused"), doesn't resume after, ▶ goes on from there, and
     a tapped chord sounds right after it (the output was reopened).
  2. Music playing in Apple Music or Spotify, then ▶ in Chord Notepad: the
     other app stops. Pause and start the other app again: Chord Notepad is
     interrupted, and after the other app stops a tapped chord sounds. With
     the other app playing and Chord Notepad idle, tap a chord: both sound.
  3. Wired headphones (or an adapter) and AirPods or a Bluetooth speaker:
     play, unplug or switch the device off: the song pauses and doesn't
     carry on through the speaker. Plug back in: nothing starts by itself.
  4. The Ring/Silent switch (or the Action button's silent mode) on: a song
     and a tapped chord still sound; the volume buttons change it.
  5. Play, then the Home screen, the app switcher and the lock button: the
     song pauses; back in the app, ▶ goes on and a tapped chord sounds.
  6. Diagnostics › Run again: the category (Playback) and its options
     (mix with others while idle); the log's "Audio policy" lines.
  7. VoiceOver on (triple-click if set up): walk the main screen in Play and
     Edit, the ribbon, the player, the find bar, a sheet, Settings and About:
     every button says what it does in Android's words, no image names.
  8. Split View, Slide Over and Stage Manager can't be tried on her iPhone
     and there's no iPad to borrow: the catalog's `split_*` images and
     `MultitaskingTests` stand in; check on an iPad if one turns up (the
     keyboard over a split window, a resized Stage Manager window).

  Standing items for the last song (docs "The last song", what CI doesn't
  test):
  1. Type into a saved song in iCloud Drive without saving, then swipe the
     app away and reopen it: the song with the changes and its •, in the
     tab it was left in; Save writes it in place. The same after a reboot,
     and after opening many big apps until iOS ends Chord Notepad in the
     background.
  2. A saved song without changes, changed in another app (or on a Mac
     through iCloud Drive), then Chord Notepad reopened: the new text.
  3. A song with unsaved changes deleted in Files, then the app reopened:
     the words as a new song and the "Couldn't find …" snackbar. Without
     changes: "Failed to open file: … File not found" over an empty song.
  4. "Remove Download" on a saved song in iCloud Drive, flight mode on,
     reopen: the download wait, then the error after 20 s.
  5. With unsaved changes left, open a `.txt` from Files with the app
     closed: the changes come back, then the unsaved-changes question for
     the song from Files.
  6. A new song typed and the app swiped away within 2 s: the scene's
     inactive and background saves keep it.
- [ ] the checklist printed, screen recording on
- [ ] where the artifacts go
- [ ] which fallback agenda applies
- [ ] the session log template

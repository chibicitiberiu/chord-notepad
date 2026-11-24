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
CI builds the bare app shell and tests it on iPhone and iPad simulators
with no Apple account (section D, `.github/workflows/ios.yml`). The first
screen slices are the chord sheet ("The chord sheet" below) and the song
editor with the Edit ribbon ("The song editor"), both in the shell. Still to
come: enrollment, signing and TestFlight (A, E), then the other screens (F,
in `BACKLOG.md`), the Play tab and the main screen's navigation first.

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
    App/                        AppModel (the session), paths, document store,
                                diagnostics, self-test
    Screens/                    ShellScreen (pure), ShellView (live), self-test
    Editor/                     the song editor: EditorTextView, EditorController, SongEditor,
                                EditRibbon, EditorAppearance and EditorPreview, EditorScript (CI)
    ChordSheet/                 the chord sheet: CGSheetCanvas, ChordSheetSource, ChordSheetPane
    Catalog/PreviewCatalog.swift  the screens drawn from Fixtures, and the PNG renderer
    Assets.xcassets             the app icon (ios/tools/make_app_icon.py)
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
      Python/chordnotepad_ios/  the Python glue (host.py, diagnostics.py), shipped as a resource
    Tests/ChordNotepadKitTests/ XCTest; python/ holds a tiny test module
  Fixtures/                     recorded session output per scene, for the preview catalog
  tools/
    gen_swift_bridge.py         writes Generated/Bridge.swift from the schema
    install_python.sh           the app's "Install Python" build phase
    export_glyphs.sh            the "Chord sheet glyphs" build phase
    make_app_icon.py            renders the icon from resources/chord-notepad-icon.svg
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
make ios-kit-test      # swift test: 168 tests, about 12 s after the first build
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
| `SnapshotTests` | `SessionSnapshot` (code-point edits, the message cap), every fixture folding into a screen's snapshot, the chord sheet scenes' buffers (view, zoom, playhead, heights), the editor scenes folded into the editor (the selection a command made, every span kind, the notation) |
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
| `IntegrationTests` | one real session: restore a draft, code-point highlights, save through the store, a refused rename, a decoded chord sheet buffer, the eight scenes |

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

`IntegrationTests` records eight scenes into `ios/Fixtures/`: `empty_song`,
`quick_start_edit`, `play_with_chord_sheet` (the complete example with the
chord sheet shown as the piano roll and the playhead on the third chord),
`errors` (a document that can't be opened, a rename the storage refuses),
`chord_sheet_staff` (the staff, zoomed in one step, playhead on chord 24),
`chord_sheet_fret` (fret cards after `set_voicing guitar:standard`, which
makes the view available), `editor_mid_edit` (the quick-start song with a
line of an invalid and a redundant directive and an unknown chord put in by
`insert_text`, then two lines commented out by `toggle_comment`, whose
`anchor` leaves them selected: every span kind) and `editor_european` (the
quick-start song after `convert_notation european`). Each scene comes after
the ones whose states it would change, so theirs stay as they were; the
editor's come last, with the sheet hidden again. A scene starts at the mark
before its song's `restore_draft`, so it carries the `TextEdited` with the
text. The user's own typing can't be recorded (the session doesn't echo
`set_text`), so the editor scenes are made of the session's edits. Each file has the newest JSON of every state (the whole
screen) and the other outputs of the scene in order, exactly as they crossed
the bridge, sorted and indented, with the temporary files folder written
`$FILES_DIR`. A normal run checks them; `make ios-fixtures` rewrites them.
They are the same on every run.

The catalog can't call Python, so each scene with the sheet shown also keeps
its op buffers: `chord_sheet_buffers`, a list of `{height, base64}`, packed at
the content heights the catalog's iPhone and iPad ask for (102 and 355 pt:
the split's height for a 160 pt sheet in each window, less the pane's header,
progress bar, inset and the 20 pt marker lane). `CatalogTests` checks the
heights still match the catalog's devices. The theme is applied at paint
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
  SoundFont. The shell opens the quick-start song as a draft (store id
  `bundle:01_quick_start.txt`).
- **Kit headers on iOS:** `Package.swift` gives `CNBridge` `-F
  ios/build/Frameworks/Python.xcframework/ios-arm64` for iOS (both slices
  have the same headers); the app target links and embeds the framework.
  The shims include `<Python/Python.h>` only when `TARGET_OS_IOS`; a Mac
  host always uses pkg-config's `<Python.h>`, since `/Library/Frameworks`
  is on clang's default path and may hold another version's
  Python.framework. The kit imports `CNBridge` with `internal import`, so
  the app and its tests never need the C module.

### The shell and its diagnostics

Phase 1 has one screen: the song's title, the Edit ribbon, the song editor
("The song editor" below), the chord sheet while it is shown, and the
status line. `SessionSnapshot` (in the kit, tested on Linux) folds the
session's output into what a screen reads; `EditorState` carries no text,
so its `text` is rebuilt from `TextEdited`. That is the session's edits
only: the editor's own model (`EditorModel`, fed the same outputs in the
same order by `AppModel.receive`) owns the text the user sees and types.
Buttons: play the first chord, show the chord sheet, the self-test, export
diagnostics.

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
  and the run number as the build. The status line shows it.
- **Self-test** (also `-CNScreen selftest` at launch): Python boot, session
  start and first-text times; an offline render of a C major chord on a
  FluidSynth synth with no audio driver (the core's audio export renderer,
  `chordnotepad_ios.diagnostics.offline_render`), which must not be silent;
  a live audition and whether FluidSynth's CoreAudio player started; the
  AVAudioSession category, route, sample rate and buffer.

### The chord sheet

The first screen slice: the Play tab's strip, shown under the shell's text
while `ChordSheetState.visible` (the shell's header has a toggle until the
player exists). It is a port of Android's `ui/chordsheet/`.

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

The second slice: the shell's text is the song editor, a port of Android's
`ui/editor/` with the Edit ribbon (`ui/main/EditRibbon.kt`).

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
  controller as plain state, for the Play slice: the editor shows no hint).
- **In the app** (`ChordNotepad/Editor/`): `EditorTextView` (a UITextView on
  a TextKit 1 stack built by hand), `EditorController` (the main actor's
  `ObservableObject` over the model; it applies the effects to the view and
  sends the commands), `SongEditor` (the `UIViewRepresentable` and its
  delegate), `EditRibbon`, `EditorAppearance` (fonts and attributes from the
  kit's runs) and `EditorPreview` (the catalog's drawing), `EditorScript`
  (CI's typing).
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
  100 000 pt wide, the content as wide as the longest line, and the view
  scrolls sideways; UIKit follows the caret up and down,
  `TextScroll.followCursor` sideways. The sounding chord is followed on both
  axes (`TextScroll.followChord`).
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
  token, checks the unwrapped content is wider than the view, a session
  `insert_text` lands without a `set_text` going back, and undo and redo
  (the ribbon's and the undo manager's) go back as user edits; the view is
  attached as `editor-live.png`. `-CNScreen editor` does the typing at
  launch on the screen itself and writes `Diagnostics/editor.json`, which
  CI's screenshot waits for and checks.

Deliberate differences from Android:

- The ribbon has Undo, Redo, AB/Do and Convert. Insert, Transpose, Capo and
  Identify open sheets that come with later slices; until then the row fits
  every screen, so it has no chevron or fades. There is no floating undo
  chip: the header doesn't collapse, and iOS has its own undo gestures.
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
(every change repaints the whole text's attributes).

### Preview catalog

`PreviewCatalog.screens` lists every screen with the fixtures it is shown
with; adding a screen is one line there. `#Preview`s use the same
`PreviewCatalog.snapshot("<scene>")`. `CatalogTests` renders each entry with
`ImageRenderer` at iPhone 17 (402×874 pt, @3x) and iPad Air 11-inch
(820×1180 pt, @2x), light and dark, default and `accessibility2` text: 72
PNGs (the shell with eight scenes, the self-test with a sample report). The
chord sheet's strip draws there too: it is a SwiftUI `Canvas`, and only its
scroll view (live only) is UIKit. ImageRenderer can't draw a `ScrollView` (or other UIKit-backed
views), so a screen takes `scrolls: false` in the catalog and draws plain
SwiftUI. The editor's UITextView is one of those: the catalog draws
`EditorPreview`, a SwiftUI `Text` of the same `EditorModel` (folded from the
scene's outputs) with the same font and the same `styleRuns` as attributes,
word joiners keeping the chords whole when it wraps, and the selection as a
25 % tint of the primary colour. It has no caret, the live view's selection
colour is the system's, and SwiftUI's line height can differ slightly from
TextKit's; unwrapped lines run past the right edge, as the live view shows
them before it is scrolled.

### App Store requirements already in place

`ITSAppUsesNonExemptEncryption = NO` (the app uses no encryption beyond
the system's); `PrivacyInfo.xcprivacy` with no tracking and no collected
data, and the required-reason APIs the embedded CPython links: file
timestamps (`C617.1`, files in the container), system boot time (`35F9.1`,
`time.monotonic` and Swift's clocks) and disk space (`E174.1`, `statvfs` is
in the binary). Add `3B52.1` with the document picker, and the user
defaults category if the app ever uses them. `_ssl` and `_hashlib` (which
link OpenSSL, on Apple's list of SDKs that need a manifest) get one each
from `packaging/ios/privacy/`. The icon is one 1024 px PNG, flattened on the
Android icon's cream (`ios/tools/make_app_icon.py`, Inkscape and Pillow).

## CI

`.github/workflows/ios.yml` runs on every push to main that touches `ios/`,
`core/`, `packaging/ios/`, the schema, the Python pins, the SoundFont, the
glyph export script or Android's chord sheet fixtures (the kit's tests read
them), and by hand (workflow_dispatch). A newer push cancels a running build.
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
- `ios-screenshots`: `<iphone|ipad>-shell.png` (the quick-start song with
  its status line), `<iphone|ipad>-selftest.png`,
  `<iphone|ipad>-chordsheet.png` (the quick-start song with the chord sheet
  shown, its buffer from the live session), `<iphone|ipad>-editor.png` (the
  editor after the app typed a long chord line into it, the session's
  highlight painted, the keyboard up), the app's Diagnostics
  folder from each simulator (`launch.json`, `chordsheet.json`, `editor.json`, `selftest.json` with the live
  audio result, the core's log) and `<device>-app.log` (the unified log of
  the app's process).
- `ios-results`: the `.xcresult` bundles (open in Xcode, or
  `xcrun xcresulttool` on a Mac; the catalog PNGs and the test's
  `selftest.json`, `chordsheet-live.png` and `editor-live.png` are attached) and the xcodebuild logs.
- `ios-kit-tests`: the kit's `swift test` output on macOS.

`gh run download <run> -n ios-screenshots` fetches one on Linux.

What the first green run (2026-11-24, Xcode 26.5, iOS 26.5 simulators)
measured: Python boot 0.15–0.6 s, session start 3.2–4.4 s (most of it the
core's imports, music21 included), first song text about 4 s; the offline
render peaks at about 5700 of 32767; the live player started on both
simulators (route Speaker, 48 kHz, 10 ms buffer); the simulator app is
141 MB and the device build 114 MB (the SoundFont is 32 MB of it). The kit's
45 tests pass on the Mac host as on Linux, fixtures included. The first
layout issue the catalog shows (for S1's list): at accessibility text sizes
the shell's title truncates beside its three buttons.

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
  show that.
- [ ] the checklist printed, screen recording on
- [ ] where the artifacts go
- [ ] which fallback agenda applies
- [ ] the session log template

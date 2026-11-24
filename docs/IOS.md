# iOS and iPadOS build

The iOS app: a SwiftUI front end over the shared Python core and the same
JSON session bridge Android uses. One universal app for iPhone and iPad.
This file covers the rules, the Swift kit, the bridge as Swift sees it, the
development loops and the sessions on borrowed Apple devices. The Android
counterpart is `docs/ANDROID.md`; the bridge itself is specified there
("Bridge contract", "Chord sheet op buffer") and only the differences are
repeated here.

**Status (2026-11-24):** the core knows the `ios` platform (section B of the
plan) and `ios/ChordNotepadKit` is built and tested on Linux (section C).
Still to come: the CI workflow with the simulator build and the bare app
shell (D), enrollment, signing and TestFlight (A, E), then the screens (F,
in `BACKLOG.md`).

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
  ChordNotepadKit/              SwiftPM package, no UIKit or SwiftUI
    Package.swift
    .swift-version              the toolchain swiftly and the Makefile use
    Sources/CPython/            system library: Python.h, linked only for Linux/macOS hosts
    Sources/CNBridge/           C: interpreter start, the _cnbridge module, calls into Python
    Sources/ChordNotepadKit/
      PythonRuntime.swift       the interpreter and its bridge thread
      BridgeThread.swift        the one thread every Swift → Python call runs on
      Session.swift             start / submit / chordSheetBuffer / shutdown, events
      DocumentStore.swift       the store protocol and its C callbacks
      BridgeValues.swift        JSONValue, Selection, BridgeCommand
      Generated/Bridge.swift    DTOs, enums, SessionOutput, command builders (generated)
      OffsetMapper.swift        code points <-> UTF-16
      SheetBuffer.swift         op-buffer v2 decoder (values, no drawing)
      Python/chordnotepad_ios/  the Python glue (host.py), shipped as a resource
    Tests/ChordNotepadKitTests/ XCTest; python/ holds a tiny test module
  Fixtures/                     recorded session output per scene, for the preview catalog
  tools/gen_swift_bridge.py     writes Generated/Bridge.swift from the schema
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
interpreter. The system `libfluidsynth` is needed because the core imports
pyFluidSynth even with the fake player.

## Running the tests

```sh
make ios-kit-test      # swift test: 37 tests, about 5 s after the first build
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
| `IntegrationTests` | one real session: restore a draft, code-point highlights, save through the store, a refused rename, a decoded chord sheet buffer, the four scenes |

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
  `audio/fluidsynth_import.py` loads at import time), `CN_TEST_FAKE_PLAYER=1`
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

`IntegrationTests` records four scenes into `ios/Fixtures/`: `empty_song`,
`quick_start_edit`, `play_with_chord_sheet` (the complete example with the
chord sheet shown and the playhead on the third chord) and `errors` (a
document that can't be opened, a rename the storage refuses). Each file has
the newest JSON of every state (the whole screen) and the other outputs of
the scene in order, exactly as they crossed the bridge, sorted and indented,
with the temporary files folder written `$FILES_DIR`. A normal run checks
them; `make ios-fixtures` rewrites them. They are the same on every run.

## Development loops

1. **Linux, every change:** `make ios-kit-test`. Everything below the UI
   (the interpreter, the bridge, offsets, the buffer decoder, the core's
   output) is tested here against the real core.
2. **CI, every push to `ios/**`, `core/**`, `packaging/ios/**` or the
   schema** (section D, not built yet): kit tests on macOS, `xcodebuild
   test` on an iPhone and an iPad simulator with an offline synth render,
   an unsigned device build, and the preview catalog rendered to PNGs in
   phone and tablet sizes, light and dark, default and large text.
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
- [ ] a numbered issue list, each issue with its expected result
- [ ] the checklist printed, screen recording on
- [ ] where the artifacts go
- [ ] which fallback agenda applies
- [ ] the session log template

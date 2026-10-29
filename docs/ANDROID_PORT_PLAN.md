# Chord Notepad for Android: port plan (revised after review)

## Status (2026-10-29)

**Done:** M0 through M6, apart from the steps only Tibi can do. That covers the
shared session layer (desktop now runs on it), sequencer playback, natives built
from source with reproducible APKs, the Kotlin bridge, every screen in the port
checklist, About/licences, User Guide, Quick Start, CI build and release jobs,
signing plumbing, PRIVACY and RELEASE docs. An end-to-end pass on the phone and
tablet emulators passed the parity checklist after 7 fixes.

**Waiting on Tibi:**
1. Create the keys (`android/tools/make_keys.sh`), the `android-release`
   environment and the secrets (docs/RELEASE.md, Android section).
2. Test on a real phone: audible timing, pinch zoom, audio focus, real file
   providers, the soft keyboard, 16 KB pages (list in docs/ANDROID.md).
3. Run the desktop manual checks for the session migration and the audio-driver
   change (Flatpak, Snap, Windows, macOS).
4. Decide the Play account type, then do the Play setup (docs/RELEASE.md).
5. Push, then tag a release. The CI release jobs have not run on GitHub yet.
6. F-Droid: decide at release time.

**Known open items** (choices for Tibi, not defects):
- Tapping a chord in the editor also raises the soft keyboard, as any
  editable field does.
- Playback pauses when the app goes to the background (the plan's lifecycle
  rule). Continuing in the background would need a foreground media service.

Fixed after the first status note:
- the piano dropping the root over a non-root slash bass (6818c78, desktop
  too);
- a pause during rendering being lost (f439f5f);
- settings are now autosaved on Android;
- the duplicated tuning help;
- hardware shortcuts working without tapping first;
- User Guide DOM storage.

Also verified on the 16 KB-page emulator.

## Android UI redesign (agreed 2026-10-29)

The M4/M5 screens copied the desktop layout. They're being reworked into Edit /
Play modes:
- a music-player bar with a playhead;
- bottom sheets for every picker;
- a drawer instead of the ⋮ menu;
- tap the title to rename;
- landscape side by side.

The full spec is in `docs/design/android-ui-spec.md`, with an interactive mockup
in `docs/design/android-modes-mockup.html`. Fitting the UI to the platform is
part of the port (Tibi), so these are deliberate Android/desktop differences,
not scope creep. The Android help and Quick Start text need to cover them.

## Context

Chord Notepad is a desktop app: Python/Tkinter UI, FluidSynth audio, AGPL licence, and Tibi is the sole copyright holder. Tibi wants it on mobile, starting with Android, which they can test (emulator plus their Android phone). iPad comes later and will reuse the same core.

Constraints:
- **Port the app as it stands today.** Add no extra features.
- **Keep the repo well organized**, with a single shared Python core.
- **Distribution:** paid on Google Play; free as a FOSS APK on GitHub releases and, if possible, on F-Droid.
- **Layout:** phones and tablets.
- **music21 stays.**
- **Disk space:** all Android tooling and caches go under `/mnt/data_linux/Bin/` (`~` is low on space).

Three independent reviews (architecture, scope/phasing, release/licensing) and a dedicated design pass reshaped the first plan. The main change: the cross-viewmodel wiring now lives in the Tk window (`src/ui/main_window.py`). It moves into a shared, host-agnostic **AppSession** layer, which both the Tk UI and the Kotlin UI sit on. Tibi asked for this to be architected correctly and done first.

## Decisions so far

- **Test devices:** the emulator for day-to-day work, Tibi's Android phone for audio, touch and performance. The Nexus 7 is out (32-bit).
- **Distribution:** the free APK also goes on GitHub releases. IzzyOnDroid is excluded: its policy rejects AI-written code.
- **F-Droid's AI stance is in flux.** There's a Sept 2026 interim-policy proposal (fdroid/admin #699), a board member opposes AI code, and a proposed "uses AI" anti-feature (#641). **Tibi decides at release time** whether to submit. Meanwhile, keep the build F-Droid-friendly (offline wheelhouse, natives from source, reproducible where cheap), but do no recipe or Request for Packaging work before then. The GitHub APK is the FOSS channel that always works.
- **Play account type** (personal vs organization with D-U-N-S): Tibi looks into it once there's a working APK, not sooner. Nothing in M0–M5 depends on it.
- **Signing:** separate keys. Play uses Google-managed app signing with an upload key; an offline FOSS key signs the GitHub APK (and F-Droid if it's chosen and builds reproducibly).
- **music21:** ship the upstream package trimmed of data files only. `corpus/*.py` and `test/*.py` are imported, so keep them; drop the corpus and scale data. Install it with `--no-deps` plus the pure-Python dependencies it actually imports. PIL is optional (verified). Pin chardet below 7 (its licence change is disputed). Extract the parts we use only if size or startup time requires it.

## Architecture

### AppSession: the shared layer, built first

The detailed design is saved to `docs/architecture/session.md` during M1 step 0. Summary:

- **Composes the existing viewmodels.** They stay as internal components, which keeps about 15 test files valid. AppSession becomes their only observer and owns all wiring and app-level flows moved out of `main_window.py`:
  - text mirror, debounced detection and highlight spans (including `_find_comments`);
  - chord hit-testing by offset;
  - chord-sheet feed (`:886-925`) and playback-event fan-out (`:446-510`);
  - the playing/idle transitions;
  - the notation toggle with key conversion (`:318-340`);
  - transpose, capo, convert and insert flows (`:1569-1667`, `:1768-1844`);
  - settings apply (`:1468-1494`);
  - new/open/save/save-as/close/export-MIDI/recent-files flows (`:984-1105`, `:1369-1402`);
  - status text, title, multiplier parsing, voicing-menu ordering, the instrument-family table and key options.
- **Views keep only:**
  - widgets and theme;
  - pixel/cursor → offset conversion;
  - applying the undo policy carried by edit events;
  - modal presentation of requests;
  - native file pickers;
  - chord-sheet painting (replaying `DrawOps`).
- **Modules:**
  - `src/session/`:
    - `host.py`: the `Host` protocol, with `post`, `call_later`, `is_session_thread` and `monotonic`;
    - `threaded_host.py`;
    - `testing.py`: `ManualHost` with a virtual clock, `InMemoryDocumentStore`, `FakePlayer` and `EventRecorder`;
    - `errors.py`;
    - `documents.py`: `DocumentRef(id, display_name, location)`, the `DocumentStore` protocol and `FileSystemDocumentStore`;
    - `state.py`: frozen state DTOs;
    - `events.py`: one-off events and requests;
    - `formatting.py`, `highlighting.py`;
    - `flows.py`: generator-based request/response flows;
    - `workers.py`: `BackgroundWorker`;
    - `bootstrap.py`: the Tk-free service wiring;
    - `bridge.py`: DTO → `(type, json)`, plus a schema dump;
    - `session.py`.
  - Also: `src/ui/tk_host.py` and `src/utils/paths.py`.
- **Inbound:** primitive-typed commands, e.g. `set_text`, `insert_text`, `play_pause(from_offset)`, `tap_chord_at`, `transpose`, `set_notation`, `set_voicing`, `open_document`, `save_as`, `export_midi`, `request_close`, `respond(request_id, value)` and `apply_settings`.
- **Outbound:** one stream, delivered on the session thread at flush points. States are coalesced, latest value wins:
  - `DocumentState`, `EditorState`, `HighlightState`, `PlaybackState`, `ToolbarState`;
  - `StatusState`, `VoicingMenuState`, `InstrumentMenuState`, `RecentDocumentsState`, `ChordSheetState`.

  One-off events keep their order: `TextEdited` (a splice plus an undo policy of group/plain/reset), requests (`ConfirmDiscardRequest`, `PickDocumentRequest`, `CapoChoiceRequest`, `InsertDirectiveRequest`), `UserError`, `AudioUnavailable` and `UnexpectedError`. Payloads carry no live Python objects.

**Threading contract.**
- One session thread owns all state, and `queue_ui_callback` is `host.post`.
- Background threads only post: render, playback loop, chord-sheet job, `BackgroundWorker`.
- The session thread never renders. MIDI export and capo suggestion move to `BackgroundWorker`. `stop_playback` stops joining the render thread and uses a start/cancel lock instead.
- **Tk:** the main thread is the session thread.
- **Android:** a `ThreadedHost` thread. Kotlin only enqueues, from a non-Main dispatcher. The Android main thread never calls Python. Event and DocumentStore callbacks never block on the dispatcher.

**Offsets.** The session uses code points; Kotlin's `OffsetMapper` is the only place that converts to UTF-16.

**Errors.** Tk-free routing goes through `session/errors.py`, which `Observable` uses. `utils/error_reporting.py` stays the Tk presenter and registers itself, so the existing test patch points keep working. Android installs a handler that emits `UnexpectedError`.

### Android side

- **`PyHost` singleton** at Application scope:
  - starts Chaquopy;
  - calls `System.loadLibrary("fluidsynth")` (resolves liboboe and libsndfile);
  - creates the session through `bootstrap` with a SAF `DocumentStore` and an `EventSink`.
- **Flows:**
  - states map to `StateFlow`;
  - `TextEdited` goes into an unbounded `Channel`, applied inside `TextFieldState.edit {}`;
  - pending requests go into a `StateFlow`, so they survive rotation;
  - errors go into a `SharedFlow`.
- **Contract test:** a committed `bridge_schema.json`.
- **Kotlin never:**
  - re-implements wiring, formatting or highlighting;
  - holds `PyObject`s outside the bridge;
  - calls Python on Main.
- **Audio:**
  - The existing `NotePlayer` uses ctypes to load FluidSynth (allow a bare soname in `fluidsynth_import`).
  - Android driver list: `['oboe', 'opensles']`, with a NULL-driver check.
  - Device-native sample rate and dynamic sample loading.
  - **Lifecycle:** request audio focus, pause on focus loss or `AUDIO_BECOMING_NOISY`, pause and close the stream and save config on `ON_STOP`, restore a draft after process death.
  - If timing is poor, the first fallback is pyfluidsynth's `Sequencer` with sample-clock scheduling. A native `IPlayer` comes after that.
- **Chord sheet:**
  - Python packs the ops into one bytes buffer; Kotlin decodes it once, caches it and draws only the visible part.
  - One gutter variant per key signature.
  - Tk px → dp, pt → sp calibration; Tk text anchors emulated with `TextMeasurer`.
  - Pinch zoom uses `graphicsLayer`, then a single re-render.
  - The 6 base clef glyphs are drawn in Kotlin with scaling and a tint `ColorFilter`. `clef_assets.py` gets a guarded PIL import.
- **Config:** atomic writes (temp file + `os.replace`), saved on `ON_STOP`.
- **Settings visibility rule:** keep every setting whose meaning carries over to Android; hide the rest with no replacements.
  - Hidden: log level, audio driver, window geometry.
  - Soundfont path: hidden in v1.
  - Font family: Monospace, Sans or Serif, with `TkFixedFont` mapped to Monospace; editor colours unchanged.

## Repo layout

```
src/                       shared Python core
  session/                 AppSession layer (new)
  chord_sheet/             headless renderers + ops + clef data (git mv from src/ui/chord_sheet)
  ui/                      Tk only (tk_host, panel, Tk replay, dialogs)
android/                   Gradle project (Kotlin DSL, version catalog)
  app/src/main/kotlin/io/github/chibicitiberiu/chordnotepad/{bridge,ui/...,files,audio}
  app/src/main/python/chordnotepad_android/   host glue (paths, ThreadedHost wiring, loadLibrary hand-off)
  native/                  fluidsynth + deps as pinned git submodules, build.sh (16 KB pages)
  tools/                   strip_music21.py, build_wheelhouse.py (pins in android/requirements.txt, hash-checked)
fastlane/metadata/android/ repo root (F-Droid requirement)
docs/ANDROID.md, docs/architecture/session.md
```

- **Project basics:**
  - applicationId `io.github.chibicitiberiu.chordnotepad`, one build (no flavors);
  - minSdk 24, targetSdk 36, Python 3.14 (pinned micro version), ABIs arm64-v8a and x86_64.
- **Version scheme:**
  - versionName comes from `VERSION`;
  - versionCode is `(MAJ*10000+MIN*100+PATCH)*10+rebuild`, written as a literal in `build.gradle.kts`, with a test that checks it against `VERSION`;
  - no `run_number` and no wall-clock date in Android builds; use `SOURCE_DATE_EPOCH`.
- **Local environment:**
  - `ANDROID_HOME`, `ANDROID_AVD_HOME`, `ANDROID_USER_HOME`, `GRADLE_USER_HOME` and `PIP_CACHE_DIR` all under `/mnt/data_linux/Bin/android/`;
  - set through a gitignored `android/local.env` (plus a committed `.example`);
  - also add a line to `CLAUDE.md`, together with the rule "logic goes in the Python core; Kotlin is view-only".

## Milestones

### M0: desktop correctness (small, now)

1. Fix the licence notice. The About dialog says "© 2024 Chord Notepad Contributors / MIT License" (`main_window.py:1553`), and the Windows exe metadata says `LegalCopyright 'MIT License'` (`build.yml:306`). Both should say AGPL-3.0 with a link to the source.
2. A CI import-guard test: import every core module in a subprocess with tkinter, PIL and jeepney blocked.

### M1: AppSession on desktop (first major work; about 3–4 weeks; each step is one commit with `make test` green)

| # | Step | Key tests | Risk |
|---|---|---|---|
| 0 | Write `docs/architecture/session.md` (the full design) | n/a | n/a |
| 1 | `Host`, `ManualHost`, `TkHost`; `Application.queue_ui_callback` delegates to the host | host tests; retarget the queued-callback error test | Low |
| 2 | `session/errors.py`; `Observable` uses it; the Tk presenter registers itself | `test_error_reporting` unchanged; tkinter-free import test | Low–med |
| 3 | Chord-sheet debounce through `host.call_later`, marshal through `host.post` | existing tests; ManualHost debounce test | Med |
| 4 | `DocumentRef`/`DocumentStore`/FS store, `utils/paths.py`, `render_midi_bytes`; the viewmodel works on refs | adjust `test_midi_export_flow` and the file-error tests; store tests | Med |
| 5 | AppSession skeleton: emitter/flush, `set_text`, detection debounce, `HighlightState`; the editor sends text and paints spans | golden test: type → spans; paste tests unchanged | **High** |
| 6 | Chord-sheet feed moves into the session | rewrite `test_voicing_change_refresh` | Low |
| 7 | Playback commands/state/status/playhead, `AudioUnavailable` | golden test: play → progress → finished; ported dialog tests | **High** |
| 8 | Programmatic edits with an undo policy: transpose, capo, convert, insert | golden test: transpose → re-detect → key shift; manual Ctrl+Z | **High** |
| 9 | `ToolbarState`, notation/key conversion, multiplier parsing | new tests | Med |
| 10 | Settings apply, voicing and instrument menu models | port `test_settings_dialog_wiring` | Med |
| 11 | Document flows as generators plus requests; `DocumentState`/title | flow tests: unsaved → save → cancel, etc. | **High** |
| 12 | `BackgroundWorker` for export and capo; non-blocking `stop_playback` | stress test: stop during render never starts the player | Med |
| 13 | `MainWindow(session, host, resources)`; remove the shims (`current_file`, `"line.col"`) | guard test: no viewmodel references in `main_window.py` | Low |
| 14 | `ThreadedHost`, `bootstrap.build_core_services`, `bridge.encode` + schema | full flows on `ThreadedHost` with `FakePlayer`; DTO-purity test | Med |

**Also in M1, as small separate commits:**
- `git mv` of the headless renderers to `src/chord_sheet/` (7 modules, imports in `chord_sheet_viewmodel.py`, `panel.py` and 9 test files);
- guard the PIL import in `clef_assets.py`;
- mark Tk-needing tests with `pytest.mark.tk`.

**Behaviour changes to call out in commit messages:**
- inserted directives are highlighted after the debounce;
- navigation keys no longer trigger re-detection;
- `stop` no longer blocks for up to 2 s.

Keep the existing behaviour where Settings' `general_changed` is ignored; it gets filed separately.

**Manual check after every step** (`make run`): open a file with directives, type, play/loop/shift-play, transpose plus undo, toggle the strip and switch voicing, change settings, close with unsaved changes.

### M1b: desktop audio fixes (separate change, tested across all desktop packages)

- Honour `Config.audio_driver`: try it first, then the platform list. **Done.**
- Detect a NULL audio driver, so the fallback and the "audio unavailable" dialog actually happen. **Done.**
- Switch the playback loop to `perf_counter`. **Superseded:** the Python sleep loop is gone (Sequencer, below).
- Stop starting a new thread per metronome tick. **Done:** clicks are sequencer events.

Check manually on Flatpak, Snap, Windows and macOS, because this changes which audio driver users end up with.

**Added after the M2 spike (2026-10-29; details in `docs/ANDROID.md`).** These are core changes. They replace the runtime shims in `android_shim.py`.
- **Timing (done):** schedule notes on FluidSynth's `Sequencer` (sample clock) instead of the Python sleep loop. Measured on the emulator, the loop drifts +80–95 ms/min when idle, and under GIL load from one busy thread it reaches p99 49–76 ms with +5.5 s/min drift. Pause, seek and live speed changes reschedule. Desktop benefits too.
- **FluidSynth loading (done):** `fluidsynth_import` accepts a bare soname. The player has an Android driver list `['oboe', 'opensles']` and logs the driver that actually started.
- **Host-provided settings:** sample rate, Oboe performance mode (done: `AudioOptions`), and the app data directories (still to do; today `AppDataService` gets them through `XDG_*`).
- **Faster first note:** Play renders the whole song before the first note (1.4 s on the emulator), so stream the first bars or reuse the chord sheet's `RenderedSong`.

### M2: toolchain spike (can run in parallel with M1 from week 1; go/no-go)

1. Install the SDK, emulator, AVDs (phone and tablet, x86_64, KVM) and JDK 21 under `/mnt/data_linux/Bin/android`. Check that `du ~` is unchanged.
2. Build a Gradle skeleton (kept) and a throwaway Compose screen on Chaquopy 17.2.
3. Exercise the core in that screen:
   - import the core;
   - detection with highlight spans on a 300-line song while typing (IME, tap → offset, a whole-text replace as one undo step, a paste hook, read-only mode);
   - play through FluidSynth 2.6.0 prebuilt + oboe + the SF2 copied to `filesDir`;
   - replay the staff view of a 200-chord song from a packed op buffer.
4. **Measure** on the emulator and the phone, recorded in `docs/ANDROID.md`:
   - APK size;
   - cold start and music21 import time;
   - Play → first note and tap → sound;
   - jitter, measured by **recording audio output** of a 2-minute metronome (p50/p99, with and without a concurrent chord-sheet render);
   - op-buffer marshal time and scroll frame time;
   - peak RSS.
5. **Reproducibility check:** two clean builds in different paths, compared with diffoscope/apksigcopier, with `PYTHONHASHSEED=0`, `dependenciesInfo` off and no build-id.
6. 16 KB alignment check on all `.so` files.

**Exit:** sound plays, p99 jitter is acceptable (otherwise switch to the Sequencer), the editor approach works, and the reproducibility verdict is recorded.

### M3: Android plumbing

- Host glue and `PyHost`.
- The SAF `DocumentStore`: persisted URI grants, revoked grants pruned from recent files.
- `OffsetMapper` with an emoji test.
- The lifecycle handling above.
- Atomic config writes and draft restore.
- An `android` CI job from day one: assembleDebug, JVM tests, lint, the 16 KB check, and a check that the merged manifest has no INTERNET permission.

### M4: internal alpha (sideload on the phone)

Each area is built only after its logic is in the core (most of it already is, after M1), and each comes with tests: JVM/Robolectric with a fake bridge, plus 3–5 end-to-end emulator flows.

1. **Editor:** spans, tap to play, playing highlight and auto-scroll, read-only while playing, paste normalization, undo via `TextEdited` policies, pinch zoom = font zoom.
2. **Toolbar and playback:**
   - AB/Do, BPM/speed scrubbers, key, time signature, metronome;
   - Play/Pause/Stop, with long-press on Play for play-from-cursor;
   - the status line.
3. **Pickers:** voicing (menu model) and instrument (16 families).
4. **Chord sheet:** views with disabled reasons, zoom, marker lane, fixed gutter, tap to audition, playhead, show/hide, resizable split (stored in dp).
5. **Files:** new/open/save/save as, the unsaved-changes request, recent files, MIDI export, and the title as file name plus a modified marker.

**Done (2026-10-29), items 3 and 5 (M4b):** real request handling (SAF launchers on the activity, rotation-safe), the Playback menu (bottom sheets on phones, dropdown pages on tablets), View › Font… and Chord Sheet. No File › Exit: Back with unsaved changes asks first, then finishes the activity (details in `docs/ANDROID.md`). Left for M5: the Capo and Insert directive dialogs (their requests are cancelled for now), F1 once Help exists.

### M5: parity beta

- Transpose and Capo (selection vs whole song, voicing chooser, "no capo helps").
- Insert directives: BPM in 4 forms (20–300), Label with the duplicate check, Loop picking from existing labels.
- Convert notation.
- Chord Identifier: piano, typed notes, play without selecting (long-press), insert chord plus a space. **Core done (2026-10-29):** `identifier_*`, `play_note`, `play_identified_chord` and `IdentifierState` (docs/ANDROID.md, "M5 screens").
- **Done (2026-10-29), the tools above (M5b):** ⋮ › Tools with the Transpose, Suggest Capo and Insert directive dialogs, Convert notation and the Chord Identifier screen (docs/ANDROID.md, "Tools (M5)"). Directive values are checked by Python after Insert (a `UserError`), not live.
- **Settings:** General and Playback (after the visibility rule). **Core done (2026-10-29):** `SettingsState` and a settings edit (`begin_settings_edit` … `save_settings`).
- **Voicings editor**, driven by a declarative form schema that moves into the core (labels, tooltips → supporting text, parse rules, field errors; `test_voicings_page_logic.py` moves with it). **Core done (2026-10-29):** `src/settings_forms/voicing_form.py` holds the per-model schemas (sections, fields, kinds, spinner ranges, defaults, help), values ↔ voicing conversion, field and cross-field errors, record add/remove and the Load config presets, all plain JSON; the Tk page renders from it (`tests/test_voicing_form*.py`). Bridge calls done too (2026-10-29: `VoicingEditorSchema`, `VoicingEditorState` and the voicing commands inside a settings edit); still to do: the Compose renderer.
- **Quick Start:** first-run auto-show and "don't show again", with per-platform text variants in the core. **Core done (2026-10-29):** `request_quick_start` → `QuickStartContent`; the flag is in `SettingsState`; the host passes `platform="android"` at bootstrap. **Screen done (2026-10-29, M5e):** Compose pager with highlighted read-only snippets, Previous/Next/Done, "Show at startup"; opens on first run, once per process start (docs/ANDROID.md, "Help: User Guide and Quick Start").
- **Help:**
  - the same `help/*.rst` with `.. only:: desktop` / `.. only:: android` blocks;
  - a `make docs-html-android` target (`-t android`); **done (2026-10-29)**, the desktop build passes `-t desktop` (and `conf.py` defaults to it);
  - bundled in an offline WebView. **Done (2026-10-29, M5e):** Gradle `buildAndroidHelp` builds it into `assets/help/`, shown by `UserGuideScreen` (WebViewAssetLoader, no INTERNET); Help > User Guide and F1. Android wording fixes in `settings.rst`, `shortcuts.rst`, `interface.rst`.
- **About:** AGPL notice, source link, build info.
- **Open source licences screen** (compliance): AboutLibraries offline, plus manual entries for the Python packages, CPython and Chaquopy's bundled libraries, FluidSynth/libsndfile (LGPL), Oboe, the codecs, GeneralUser GS and Bravura.
- **Error dialogs** through the event stream: audio errors once per session for taps, every time for Play.

### M6: release

- **Keys** (decide before the first uploads):
  - Play uses Google-managed app signing, with the upload key in a GitHub environment `android-release` that only `v*` tags can use.
  - A separate offline **FOSS key** (RSA-4096, two encrypted backups) signs the GitHub APK and the F-Droid build when it's reproducible. Register the package name and key for developer verification as soon as they exist.
  - Play installs and FOSS installs don't update each other; document this.
- **Natives from source:** `android/native/build.sh` mirrors upstream CI (NDK 27.3, API 24, `max-page-size=16384`), with the dependencies as pinned submodules. The 2.6.0 prebuilt is for development only. **Done (2026-10-29):** FluidSynth 2.6.1 and its dependencies (plus the signalsmith libraries its CMake would otherwise clone) are shallow submodules pinned to release tags; Gradle builds them by default (`buildNatives`) and keeps the hash-pinned 2.6.0 zip behind `-PcnNatives=prebuilt`. Stripped sizes match the prebuilt within 2 % (details in `docs/ANDROID.md`).
- **Python packages offline:** `--no-index --find-links` to a wheelhouse built from pinned, hash-checked PyPI files plus the trimmed music21. No chaquo.com downloads at all. **Done (2026-10-29):** pins and hashes in `android/requirements.txt`, `tools/build_wheelhouse.py` (fetch/check/lock); a clean Gradle build inside a network namespace with `--offline` succeeds, and the two-path reproducibility check still gives byte-identical APKs.
- **CI** (desktop jobs unchanged):
  - `android-emulator`: KVM, `reactivecircus/android-emulator-runner`, and a dependency-free on-device `smoke.py` that imports everything and compares against `tests/fixtures/characterization` goldens. Gated on paths, plus nightly.
  - `android-release` on tags: an upload-key-signed AAB as a workflow artifact, **uploaded to Play by hand** (as with the MSIX); a FOSS-key-signed universal APK, checked with `apksigner verify`; a full source tarball with submodules.
  - `attach-android`: uploads the APK and source tarball to the release. An Android failure never blocks the desktop release.
  - Release tags are plain `v<VERSION>`. Nightlies are never signed with release keys.
  - setup-gradle uses `cache-provider: basic`.
- **Done (2026-10-29), waiting on Tibi's keys:** versionCode literal checked against `VERSION` (Gradle + `tests/test_android_version.py`); `-PcnSigning=debug|none|upload|foss` with keystores from env/Gradle properties; `android/tools/make_keys.sh`; `android/tools/make_source_tarball.py`; the `android-release` and `attach-android` CI jobs; Auto Backup of settings only; the PRIVACY.md and `docs/RELEASE.md` Android sections. An unsigned build plus the FOSS-signed APK's signature (apksigcopier) gives the signed APK byte for byte locally; CI-vs-local is still unchecked.
- **Play:**
  - account type per the decision below;
  - payments profile → price → promo codes → closed test (testers must otherwise pay), with the internal track for real testing;
  - Music & Audio listing with the AGPL notice and source link;
  - Data safety: no data collected;
  - privacy policy;
  - IARC rating;
  - **a business address that will be shown publicly.**
- **F-Droid (only if Tibi chooses it at release time):**
  - a Request for Packaging, with AI disclosure and a question about the GeneralUser GS licence (possible NonFreeAssets; MuseScore_General.sf3 is the fallback, licence to verify);
  - a hand-written recipe: `subdir: android/app`, submodules, `ndk:`, a cpython 3.14 srclib, a prebuild step for the wheelhouse and natives, `UpdateCheckMode: Tags ^v[\d.]+$`;
  - a local `fdroid build` before the merge request;
  - reproducible-build mode only if the M2/M6 check passes, otherwise F-Droid signs (permanently).
- **Docs:**
  - a `PRIVACY.md` Android section;
  - `docs/ANDROID.md`;
  - the Android section of `docs/RELEASE.md`;
  - CHANGELOG entries prefixed "Android:", with fastlane changelogs generated at release;
  - `dataExtractionRules` excluding the log.

## Effort (focused dev-days, solo + agents; estimates)

| Milestone | Days |
|---|---|
| M0 | 1 |
| M1 | 15–20 |
| M1b | 2–3 |
| M2 | 4–6 (parallel) |
| M3 | 5–7 |
| M4 | 18–25 |
| M5 | 18–28 |
| M6 | 8–12 |
| **Total** | **≈ 70–100** |

Add wall-clock waits: the Play closed test (14 days) and F-Droid review. The biggest risks are:
- the editor (spans, IME, undo);
- M1 steps 5, 7, 8 and 11;
- chord-sheet scroll performance;
- the voicings editor (large, but mechanical once schema-driven).

## Verification

- **Every M1 commit:** `make test` (1,644+), the new headless session tests (ManualHost, FakePlayer, InMemoryDocumentStore, EventRecorder golden flows), guard tests (no tkinter in `session`, DTO purity, no viewmodel references in `main_window.py`), and the manual `make run` checklist.
- **M2:** a measurements table and a reproducibility verdict in `docs/ANDROID.md`.
- **M3–M5:**
  - JVM UI tests against a fake bridge;
  - emulator end-to-end flows;
  - the on-device `smoke.py` against the characterization goldens;
  - manual parity checks on the phone and tablet AVDs against the checklist above.
- **M6:**
  - install the CI-signed APK;
  - `apksigner verify`, the 16 KB check, a local `fdroid build`;
  - internal-track install from Play;
  - a diffoscope comparison when claiming reproducibility.

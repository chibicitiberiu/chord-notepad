# Android build

Status: **M2 toolchain spike**, plus the M6 build groundwork: natives built
from source and Python packages installed offline (see "Natives from source and
offline packages" below, and `docs/ANDROID_PORT_PLAN.md`). The Gradle
project under `android/` is the kept skeleton; everything in the
`io.github.chibicitiberiu.chordnotepad.spike` package and
`android/app/src/main/python/chordnotepad_android/spike.py` is throwaway test
code that M4 replaces.

## Layout

```
android/
  settings.gradle.kts, build.gradle.kts, gradle.properties
  gradle/libs.versions.toml         versions (AGP, Kotlin, Chaquopy, Compose)
  gradle/wrapper/                   Gradle 9.8.2 wrapper (sha256-pinned)
  local.env.example                 toolchain paths; copy to local.env (gitignored)
  requirements.txt                  Python packages for the APK, pinned with sha256 hashes
  app/build.gradle.kts              app module: Chaquopy, natives, wheelhouse, SoundFont
  app/src/main/kotlin/io/github/chibicitiberiu/chordnotepad/
    ChordNotepadApp.kt, AppGraph.kt, MainActivity.kt
    bridge/                         PyHost, the Python contract, DTOs, codec, commands, SessionRepository
    text/                           OffsetMapper (code points <-> UTF-16), TextEdited/Span conversion
    files/                          SafDocumentStore (SAF I/O, persisted grants, recent list), picker mapping
    lifecycle/                      process start/stop hooks, audio focus + noisy, draft restore
    audio/                          SoundFont install, device sample rate
    ui/                             MainScreen (pages), MainActions, errors, shortcuts
    ui/main/                        Edit/Play screen: app bar + tabs, Edit ribbon, drawer, rename, layout rules
    ui/play/                        the player, playhead gestures
    ui/sheets/                      bottom sheets: song defaults, voicing, instrument, speed, insert
    ui/theme/                       the tonal light/dark tokens (AppColors) and ChordNotepadTheme
    ui/editor/                      the song text (editable in Edit, frozen in Play), highlighting, pinch zoom
    spike/                          M2 test screen (throwaway; `--ez spike true` or `--es spike_auto ...`)
  app/src/main/python/chordnotepad_android/
    host.py                         bridge entry point: start() -> SessionHandle (submit, shutdown)
    android_store.py                AndroidDocumentStore: session DocumentStore over Kotlin's SafDocumentStore
    android_shim.py                 runtime patches standing in for core changes
    spike.py                        M2 test glue (throwaway)
  native/                           FluidSynth + dependencies as pinned git submodules
  native/build.sh                   cross-compiles them (mirrors upstream's Android CI)
  tools/strip_music21.py            builds the data-trimmed music21 wheel
  tools/build_wheelhouse.py         fills/checks the offline wheelhouse, refreshes pins
  tools/check_16k.py                16 KB page-size check for an APK
  tools/check_manifest.py           no INTERNET, no Play services, no emoji2 font initializer in an APK
  tools/compare_apks.py             entry-by-entry APK diff (reproducibility)
  tools/export_clef_glyphs.py       the chord sheet's six base clef/glyph PNGs (Gradle: exportClefGlyphs)
  tools/mdi_icons.py                Material Design Icons -> res/drawable/mdi_*.xml (pinned @mdi/svg, sha256)
```

The Python core is not copied: Chaquopy reads `../../src` directly, minus
`ui/**` and the desktop-only modules (`main.py`, `application.py`,
`utils/display_scaling.py`, `utils/file_dialogs.py`, `utils/icon_loader.py`,
`utils/ui_helpers.py`; the same list as `tests/test_core_import_guard.py`).
The SoundFont (`resources/soundfont/GeneralUser-GS.sf2`), the spike's sample
song (`examples/02_american_complete.txt`) and the chord sheet's clef/glyph
PNGs (exported from `src/chord_sheet/clef_assets.py`) are put into the APK's
assets by Gradle tasks, not duplicated in git.

## Toolchain

| Piece | Version | Notes |
|---|---|---|
| JDK | Temurin 21.0.13 | Gradle/AGP run on it; Fedora's Java 25 is not used |
| Gradle | 9.8.2 | wrapper, distribution sha256 pinned |
| Android Gradle Plugin | 9.4.1 | newest AGP that Chaquopy 17.2 supports (7.3 to 9.4) |
| Kotlin | 2.4.21 | AGP 9 "built-in Kotlin"; the root `kotlin-android` alias only pins the compiler |
| Chaquopy | 17.2.0 | Python 3.14.8 runtime; needs a host `python3.14` as buildPython |
| Compose BOM | 2026.09.00 | Compose 1.12, Material 3 |
| compileSdk / targetSdk / minSdk | 37 / 36 / 24 | current AndroidX needs compileSdk 37; the app still targets 36 |
| NDK | 27.3.13750724 | compiles the natives (`android/native/build.sh`); `libc++_shared.so` comes from it too |
| CMake | 3.31.6 (SDK package) | used by `build.sh`, with the Ninja it bundles; not the host's CMake 4 |
| FluidSynth | 2.6.1, built from source | default; `-PcnNatives=prebuilt` uses upstream's 2.6.0 Android zip instead (sha256-pinned) |
| ABIs | arm64-v8a, x86_64 | `-PcnAbis=x86_64` builds one ABI |

Python packages (all `--no-deps`, pinned with hashes in `android/requirements.txt`,
installed offline from the wheelhouse; see below):
music21 10.3.0 (trimmed, see below), pychord 1.4.0, mido 1.3.3,
pyfluidsynth 1.4.0, packaging 26.3 (mido imports it), plus what music21 really imports: chardet 6.0.0.post1
(LGPL; below 7 on purpose), webcolors, more-itertools, requests, urllib3, idna,
certifi, charset-normalizer. numpy, matplotlib, joblib, jsonpickle and Pillow are
**not** needed: the core imports, detects and renders with them absent
(checked in a clean venv). music21 prints a one-line "optional packages" notice
to stderr at import; harmless.

## One-time setup

Everything lives under `/mnt/data_linux/Bin/android/` because `~` is small.

```bash
cp android/local.env.example android/local.env   # edit paths if needed
source android/local.env

# JDK 21 (Temurin) -> $ANDROID_ROOT/jdk, command-line tools -> $ANDROID_HOME/cmdline-tools/latest
yes | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "platforms;android-36" "platforms;android-37.0" \
  "build-tools;36.1.0" "ndk;27.3.13750724" "cmake;3.31.6" \
  "system-images;android-36;google_apis;x86_64" \
  "system-images;android-36;google_apis_ps16k;x86_64"

# AVDs (2 GB RAM, 2 cores each; edit config.ini after creating)
avdmanager create avd -n cn_phone     -k "system-images;android-36;google_apis;x86_64"       -d pixel_8
avdmanager create avd -n cn_tablet    -k "system-images;android-36;google_apis;x86_64"       -d pixel_tablet
avdmanager create avd -n cn_phone_16k -k "system-images;android-36;google_apis_ps16k;x86_64" -d pixel_8
```

`local.env` also sets `CHORD_NOTEPAD_ANDROID_BUILD_ROOT`: Gradle then writes
build outputs to `$ANDROID_ROOT/build/<checkout path>/` instead of
`android/app/build` (about 1 GB). Without it, outputs go to the usual place.
Gradle's small project cache (`android/.gradle`, ~20 MB) stays in the tree.
It also sets `SOURCE_DATE_EPOCH` and `PYTHONHASHSEED=0` for reproducible builds.

Native sources (git submodules, shallow; ~32 MB of git objects in
`.git/modules` plus a 73 MB checkout; Oboe is the largest at 19 + 30 MB). Don't use `--recursive`: FluidSynth's `test/manual` submodule is
test data the build doesn't need.

```bash
git submodule update --init --depth 1 android/native
git -C android/native/fluidsynth submodule update --init --depth 1 gcem signalsmith-audio-basics
```

Python wheelhouse (the only step that downloads Python packages; hash-checked,
pure-Python wheels only, into `$CHORD_NOTEPAD_ANDROID_CACHE/wheelhouse`):

```bash
python3.14 android/tools/build_wheelhouse.py          # fetch what's missing
python3.14 android/tools/build_wheelhouse.py check    # offline: all pins present, hashes match?
```

Gradle runs both of these steps itself when needed (`buildNatives`,
`prepareWheelhouse`), so a plain `./gradlew` works after the submodule init;
the commands above are for doing it up front or offline. `build.sh` installs
the pinned NDK and CMake through `sdkmanager` if they're missing.

## Build, install, run

```bash
source android/local.env
cd android
nice -n 10 ./gradlew :app:assembleDebug
nice -n 10 ./gradlew :app:assembleRelease               # debug-signed (-PcnSigning=none|upload|foss: docs/RELEASE.md, "Android")
nice -n 10 ./gradlew :app:assembleRelease -PcnMusic21=full   # untrimmed music21, for size comparison
nice -n 10 ./gradlew :app:assembleRelease -PcnNatives=prebuilt  # upstream 2.6.0 natives (no submodules needed)
nice -n 10 ./gradlew --offline :app:assembleRelease     # no network: the wheelhouse step only checks
nice -n 10 native/build.sh --abis x86_64                # natives by hand; same output dir Gradle uses
./gradlew --stop                                        # when done (shared machine)

# Emulator: headless. SwiftShader GLES crashes this emulator build (37.2.12);
# the ANGLE-based software renderer works.
nice -n 10 emulator -avd cn_phone -no-window -no-snapshot -no-boot-anim \
  -gpu swangle_indirect -memory 2048 -cores 2 &
adb wait-for-device
# local.env sets CHORD_NOTEPAD_ANDROID_BUILD_ROOT, so outputs land outside the repo:
OUT=$CHORD_NOTEPAD_ANDROID_BUILD_ROOT/$(pwd | sed 's|^/||; s|/|_|g')/app/outputs/apk
adb install -r $OUT/release/app-release.apk
adb shell am start -W -n io.github.chibicitiberiu.chordnotepad/.MainActivity
adb logcat -s CNSPIKE:I python.stdout:I python.stderr:W

# Scripted measurement run (60 s of the sample song, then 5 chord taps)
adb shell am start -n io.github.chibicitiberiu.chordnotepad/.MainActivity --es spike_auto play:60
adb emu kill
```

Checks:

```bash
python3 tools/check_16k.py $OUT/release/app-release.apk
python3 tools/check_manifest.py $OUT/release/app-release.apk
$ANDROID_HOME/build-tools/36.1.0/zipalign -c -P 16 -v 4 $OUT/release/app-release.apk
python3 tools/compare_apks.py a.apk b.apk          # reproducibility diff
```

Release builds, signing keys, the source tarball and how to reproduce the
GitHub APK are in `docs/RELEASE.md`, "Android". Auto Backup covers only
`files/config/` (settings); the rules are in `res/xml/backup_rules.xml`
(Android 6-11) and `res/xml/data_extraction_rules.xml` (12+).

## Bridge contract (Kotlin <-> Python)

**Status:** both halves are built (2026-10-29): the Kotlin half in M3, the
Python half in session step 14 (`session/threaded_host.py`,
`session/bootstrap.py`, `session/bridge.py`, and
`chordnotepad_android/host.py` + `android_store.py`). Kotlin's copy of it is
`bridge/BridgeContract.kt`, `bridge/SessionCommands.kt` and the DTOs in
`bridge/Session{Output,States,Events}.kt`.

### Entry point

```python
# chordnotepad_android/host.py
def start(files_dir: str, native_lib_dir: str, document_store, event_sink,
          audio_options: dict) -> SessionHandle: ...

class SessionHandle:
    def submit(self, command: str, args_json: str) -> None: ...  # enqueue only, returns at once
    def shutdown(self) -> None: ...                               # stop the session thread, release audio
```

- `start` runs once per process, on Kotlin's `python-bridge` thread, after
  `System.loadLibrary("fluidsynth")` and `Python.start`. It builds the core
  (`bootstrap.build_core_services`), starts a `ThreadedHost`, creates the
  session with an `AndroidDocumentStore` (below) and `platform="android"`
  (`session.platform`: the texts that name a gesture or a menu path get
  their Android wording, e.g. "Tapped chords won't play…", "⋮ → Playback →
  Voicing"; the desktop passes nothing and keeps its exact texts),
  subscribes a listener that
  forwards every output to `event_sink`, installs the `session.errors`
  handler (emits `UnexpectedError`, throttled) and returns. It may block for
  the imports; it must not wait for anything on the session thread that needs
  the bridge thread.
- `files_dir` replaces the `XDG_*` shim (`android_shim.py`) for config, logs
  and data. `native_lib_dir` is `ApplicationInfo.nativeLibraryDir`; the
  `.so` files stay in the APK, so FluidSynth still loads by soname.
- `audio_options`: `{"sample_rate": int, "frames_per_buffer": int,
  "soundfont_path": str}`. The SoundFont is already copied to `filesDir`.
  Python builds its `AudioOptions` from these (the Oboe settings stay in
  Python, as in `android_shim.audio_options`).
- `submit` posts to the session thread (`host.post`) and returns. Kotlin
  calls it only from the bridge thread, in order, never from Main. Commands
  submitted after `start` began wait behind it.

### Output: `event_sink.onEvent(type_name, json)`

Called on the session thread, at flush points, in delivery order (states
coalesced, events in order, the replay of every state first when the
listener subscribes). The Kotlin side never blocks in it and never throws
back.

- `type_name` is the DTO's Python class name: `HighlightState`.
- `json` is the dataclass's fields as a JSON object, with the Python field
  names: enums as their `.value`, tuples as arrays, nested dataclasses as
  objects (`DocumentRef` is `{"id", "display_name", "location"}`), None as
  `null`. `CloseApproved` is `{}`. In short,
  `json.dumps(dataclasses.asdict(dto))` with an enum-aware default.

Types Kotlin decodes (`BridgeCodec.serializers`):

| Kind | Types |
|---|---|
| States | `DocumentState`, `EditorState`, `HighlightState`, `PlaybackState`, `ToolbarState`, `StatusState`, `VoicingMenuState`, `InstrumentMenuState`, `RecentDocumentsState`, `ChordSheetState`; M5: `IdentifierState`, `SettingsState`, `VoicingEditorState`; Edit/Play: `SongDefaultsState` |
| Events | `TextEdited`, `UserError`, `AudioUnavailable`, `UnexpectedError`, `CloseApproved`; M5 replies: `VoicingEditorSchema`, `QuickStartContent`, `DirectiveCheck`; Edit/Play: `RenameFailed` |
| Requests | `ConfirmDiscardRequest`, `PickDocumentRequest`, `CapoChoiceRequest`, `InsertDirectiveRequest` |

**Step 14 added two things to the DTOs** (Kotlin already had them):
- `UnexpectedError(message: str, context: Optional[str])` in `events.py`
  (designed, not defined yet);
- `DocumentState.document_id: Optional[str]`, the open document's
  `DocumentRef.id` (None for a never-saved one). The draft restore needs it:
  Kotlin can't ask Python for it synchronously from Main.

Unknown keys are ignored by Kotlin (a newer core doesn't crash an older
view); an unknown type or a missing field is logged and shown as an
`UnexpectedError` with `context="bridge"`.

### Commands: `submit(command, args_json)`

`args_json` is always a JSON object. Offsets and selections are code points;
a selection is `[start, end]` or `null`.

**Session commands** are the public `AppSession` method names, called with
the object's keys (the method's parameter names) as keyword arguments, after
decoding `ref`/`document` objects to `DocumentRef` and `selection` arrays to
tuples. Kotlin always sends the whole ref object, so Python needn't look an id
up; `session.document_ref(id)` / `ref_for` remain available for that.
(Agreed with the coordinator for step 14, 2026-10-29: names and keys as
here, lifecycle commands host-level, `host.py`'s signature owned by the
Kotlin side, `session/bridge.py`, `bootstrap.py` and `threaded_host.py` by
step 14.)

`set_text {text, client_token}`, `insert_text {at, text}`,
`request_insert_directive {kind, at}`, `check_directive {kind, fields, request_id}`, `transpose {semitones, selection}`,
`request_suggest_capo {selection}`, `convert_notation {target}`,
`play_pause {from_offset}`, `stop {}`, `tap_chord_at {offset}`,
`set_bpm {bpm}`, `set_multiplier_pct {pct}`, `set_bpm_text {text}`,
`reset_bpm {}`, `reset_multiplier {}` (the scrubber's reset to the default),
`set_multiplier_text {text}` (typed scrubber values, parsed in Python; bad
input is ignored; the speed accepts `150`, `150%`, `1.5x`), `set_key {key}`,
`set_time_signature {beats, unit}`, `toggle_metronome {}`,
`set_voicing {voicing}`, `set_instrument {program}`,
`set_notation {notation}`, `set_font {family, size}`,
`step_font_size {delta}`, `reset_font_size {}`,
`set_chord_sheet_visible {visible}`, `set_chord_sheet_height {px}`,
`set_chord_sheet_view {view_id}`, `chord_sheet_zoom {step}`,
`audition {index}`, `new_document {}`, `open_document {ref}`,
`open_recent {ref}`, `save {}`, `save_as {}`, `export_midi {}`,
`request_close {}`, `respond {request_id, value}`.

`respond`'s `value` is decoded by the type of the pending request:
`PickDocumentRequest` → `DocumentRef` or None; `ConfirmDiscardRequest` →
`"save"`/`"discard"`/`"cancel"` or None; `CapoChoiceRequest` → the option
value or None; `InsertDirectiveRequest` → a `{field: str}` dict or None.
The M5 screens' commands are below ("M5 screens"). A parameter that has a default in
`AppSession` may be left out; any other missing, unknown or mistyped
argument is an `UnexpectedError(context="bridge")`, and a command that
raises is an `UnexpectedError` whose `context` is the command name.

**M5 screens** (Python side done 2026-10-29; Kotlin builders in
`bridge/ScreenCommands.kt`, DTOs in `bridge/ScreenOutputs.kt`, flows in
`SessionRepository`; the Compose screens are still to build):

- *Chord identifier.* `identifier_toggle_note {note, octave}` (a key tap:
  select or deselect; a newly selected key sounds), `play_note {note,
  octave}` (long-press: sound without selecting), `identifier_set_notes_text
  {text}` (the typed field: `"C E G"`, `"C4, E4, G4"`, octave 4 by default;
  silent), `identifier_clear {}` (Clear, and when the screen opens),
  `play_identified_chord {chord}` (a tapped candidate; an unplayable chord is
  a `UserError`), `insert_chord {at, chord}` (inserts `chord + " "`, says
  "Inserted chord: X"). Note names may be flats or lower case; they come back
  spelled with sharps. Audio that can't start follows the click policy
  (`AudioUnavailable` once per session). Output: `IdentifierState {notes:
  [{name, octave, midi}] lowest first, notes_text, typed_text_error,
  candidates, message}`. `notes_text` is what the typed field shows after a
  key toggle (don't overwrite the field while the user types there);
  typed notes keep their octave, which may lie outside the keys a piano
  shows; `message` replaces the candidate list when there are none.
- *Settings values.* `SettingsState {values: SettingsValues, american_keys,
  european_keys, font_size_min/max, bpm_min/max, max_recent_files_max,
  time_signature_units}` is published at subscribe and again whenever the
  config changed at the end of a command (the toolbar writes tempo, key,
  time signature and notation into it too). `values` holds exactly the
  settings Android shows (the visibility rule: no log level, audio driver,
  SoundFont path or window geometry), so visibility needs no extra flag;
  Kotlin maps the font family to Monospace/Sans/Serif. Quick Start's
  first-run flag is `values.show_quick_start_on_startup`.
  `apply_settings {changes: SettingsValues}` writes and applies them at once
  (out-of-range values: `UnexpectedError`, nothing written);
  `set_show_quick_start_on_startup {show}` is "Don't show this again".
- *Settings edit (the Settings screen, with the voicings editor).*
  `begin_settings_edit {}` opens a working copy (a `SettingsViewModel`, as
  the desktop dialog), `cancel_settings_edit {}` drops it, `save_settings
  {values: SettingsValues|null}` saves: every voicing is validated first (the
  desktop's gate: a `UserError` "Invalid Voicing" naming the first bad one,
  which gets selected, and the edit stays open), then one config write, then
  the same apply as `apply_settings` (font, Voicing menu, the voicing in use
  followed through renames or reset when removed). `null` keeps the
  General/Playback values as the config has them. The edit ends with
  `VoicingEditorState.active == false`; a config that can't be written is a
  `UserError` "Settings" and the edit stays open.
- *Voicings editor* (inside an edit; outside one these raise →
  `UnexpectedError`): `request_voicing_editor_schema {}` → `VoicingEditorSchema
  {version, schema}` (`voicing_form.editor_schema("android")`: models, list
  groups, fixed texts incl. the confirmation dialogs, header help, and per
  model the sections and fields with kinds, labels, help, ranges, defaults;
  static, keep it per `version`), `select_voicing {name}`, `add_voicing {}`
  (a guitar fretboard named "New voicing", selected), `remove_voicing
  {name}`, `rename_voicing {old, new}` (refused names: `UserError` "Rename
  Voicing"), `set_voicing_values {values}` (a JSON object of the changed
  fields, or all; merged, parsed forgivingly), `set_voicing_model {model}`
  (that model's defaults; confirm first when `dirty`), `add_voicing_record
  {field_id}` / `remove_voicing_record {index, field_id}` (`field_id`
  defaults to `voices`), `load_voicing_preset {group, label}`. Every one
  republishes `VoicingEditorState {active, revision, groups: [{model, label,
  names}], invalid, presets: [{label, group}], selected, model, values,
  field_errors, form_errors, hints, dirty}`: `values` / `field_errors` /
  `hints` are JSON objects keyed by field id (`voice:<i>:<column>` for a
  records cell), recomputed on every edit, so Kotlin never parses or
  validates. `revision` goes up on every command (also a refused rename),
  so the screen can reset its fields from the state.
- *Quick Start.* `request_quick_start {}` → `QuickStartContent {pages:
  [{title, blocks: [{kind: text|snippet|image, text, notation, spans,
  image}]}], show_on_startup}`, worded for the platform (taps, the ⋮ menu;
  no desktop screenshot). Snippet blocks carry the editor's highlight spans
  (code points), so they paint like the editor.

**Edit/Play redesign** (`docs/design/android-ui-spec.md`; Python side and
Kotlin DTOs/builders done 2026-10-29: `bridge/PlayerBridge.kt`):

- *Playhead.* `PlaybackState.playhead_offset: int|null` is the start (code
  points) of the chord ▶ plays from; `ChordSheetState.cursor_index:
  int|null` is that chord's index in the strip's rendered song (its first
  occurrence when loops repeat it), for the edge mark while nothing plays
  (null until the strip rendered the current text). Commands:
  `set_playhead {offset}` (a tap or a scrub release in Play mode: snaps to
  the chord covering `offset`, else the nearest on its line, a tie going to
  the later chord, else on the nearest line with chords, a tie going to the
  line above, at the tap's column; silent; while paused the paused song is
  dropped so ▶ starts at the new playhead; while playing, playback restarts
  there; nothing without chords), `rewind {}` (⏮: stop if playing or
  paused, playhead on the first chord), `play_pause {}` (no `from_offset`:
  from the playhead; an explicit `from_offset` still wins),
  `tap_chord_at {offset}` (on a chord: playhead there and the chord sounds;
  while playing it jumps there instead of sounding; not on a chord: nothing,
  send `set_playhead` for taps elsewhere). On Android the playhead also
  follows playback (each chord sounding), returns to the first chord at
  the end of the song, stays on ⏸ and on `stop {}` (switching to Edit),
  defaults to the first chord whenever the song has chords (an opened song
  starts there; no chords: null), and moves with edits (re-snapped to a
  chord after detection). Send scrubbing as one `set_playhead` on release,
  not per step: while playing each one restarts the render.
- *Status line.* On Android `StatusState.text` is position + activity while
  playback matters: `Bar 6/24 · Playing Em`, `Bar 6/24 · Paused`,
  `Starting…` (before the first chord sounds), and while idle the
  playhead's bar, `Bar 6/24`, or `Ready` when its bar isn't known (the strip
  hasn't rendered the text and no run played that chord). Bars count from
  the top of the song even when playback started later. Other statuses
  (`Saved: …`, `Inserted: …`, `Renamed to …`) are unchanged; Edit mode shows
  those as snackbars. The desktop wording is untouched.
- *Song defaults.* `SongDefaultsState {tempo, time, key, summary,
  locked_reason}`, each of
  the three `SongDefault {value: str, from_directive: bool,
  directive_offset: int|null}`. `value` is what the song starts with:
  `"90"`, `"3/4"`, `"G"` (`""` for the key when neither the song nor the
  toolbar sets one). `from_directive` is true when a directive before the
  song's first chord sets it (show it read-only, "Set by `{bpm: 90}` in the
  song · Edit"; Edit switches to Edit mode and puts the cursor at
  `directive_offset`, the start of the first such directive). Otherwise the
  value is the toolbar default: change it with the existing `set_bpm`,
  `set_time_signature`, `set_key` (not saved with the file).
  `summary` is the pill text, the values joined by `" · "`
  (`"90 · 3/4 · G"`, an empty key left out); Kotlin needn't format it.
  `write_song_defaults {}` (Write into song) inserts the missing directives
  as one line at the top (`{bpm: 120} {time: 4/4} {key: G}`), one `group`
  `TextEdited` followed by its `HighlightState`; refused while a song plays
  or is paused; with nothing missing the status says so. `locked_reason:
  str|null` is set while a song plays or is paused ("Stop playback to change
  the tempo or write into the song"): `set_bpm` is ignored and the write
  refused then, so the sheet turns the Tempo row and Write into song off
  and shows the reason (like `VoicingMenuState.locked_reason`).
- *Capo in Insert.* `request_insert_directive {kind: "capo", at}` →
  `InsertDirectiveRequest(kind="capo")`, answered with `{"capo": "N"}`;
  `check_directive {kind: "capo", fields: {"capo": …}, request_id}` checks
  0-12 live ("The capo must be on a fret from 0 to 12 (0 means no capo).",
  field `capo`). The dialog's Suggest button answers the insert request with
  null (`respond` cancel) and sends `request_suggest_capo {selection}`.
- *Rename.* `rename_document {name}`: `name` without the extension (the
  document's own is kept; `.txt` for an untitled one; a name already ending
  in it isn't doubled). Success: `DocumentState` (new `display_name` and
  `document_id`), `RecentDocumentsState`, `StatusState` "Renamed to X.txt".
  An untitled document just takes the name: `DocumentState.display_name`
  becomes `X.txt` (`document_id` stays null) and the first save's
  `PickDocumentRequest.suggested_name` is `X.txt`. Failure: `RenameFailed
  {name, reason, can_save_as}` (`name` as typed). `can_save_as` false: the
  name itself is invalid (empty, `/` or `\`, control characters, `.`/`..`,
  over 255 bytes): keep the dialog open with `reason`. True: the provider
  refused (it can't rename, a name in use, permissions): explain `reason`
  and offer `save_as {name}`, which suggests `name` + extension in the
  picker (`save_as {}` keeps suggesting the document's own name).

**Host commands** (the lifecycle). `pause` and `restore_draft` are
`AppSession` commands; `app_background` and `app_foreground` are run by
`session.bridge` on them, so all four are tested with the core:

| Command | Args | Does |
|---|---|---|
| `app_background` | `{}` | The app left the screen (ProcessLifecycleOwner ON_STOP; the process may die any time after). Pause playback if playing, save the config atomically (temp file + `os.replace`). Then release the audio output (`suspend_audio`: only the FluidSynth audio driver is deleted; the synth, SoundFont and sequencer stay). Refused while a song plays or renders. The next play/tap/audition reopens it lazily. |
| `app_foreground` | `{}` | ON_START. Reopen the audio output (`resume_audio`). A failure is not reported here; the next play reports `AudioUnavailable`. |
| `pause` | `{}` | Pause if a song is playing, else nothing. Sent on audio focus loss and `ACTION_AUDIO_BECOMING_NOISY`. |
| `restore_draft` | `{text, document, modified}` | After process death: replace the text as a `reset` edit (`TextEdited` + `HighlightState`), make `document` (a `DocumentRef` or null) the open document without reading it, and set the modified flag. Publishes `DocumentState`. |

An unknown command is logged and emits `UnexpectedError(context="bridge")`.

### Chord sheet: `chord_sheet_buffer(height)`

The chord sheet's drawing doesn't travel as JSON. Kotlin calls the handle
directly, on its bridge thread:

```kotlin
val bytes: ByteArray? = handle.callAttr("chord_sheet_buffer", heightDp)
    ?.toJava(ByteArray::class.java)
```

It returns the active view packed as draw ops ("Chord sheet op buffer"
below), or None without a rendered song. It packs on the calling thread
(10 to 40 ms on the emulator) from a snapshot of the last rendered song,
view and zoom that the session thread replaces whenever `ChordSheetState`
changes, so it never waits for the session thread. Refetch when
`song_revision`, `active_view`, `zoom` or the height changes. A failure is
reported as `UnexpectedError(context="chord_sheet_buffer")` and returns
None. (`AppSession.chord_sheet_buffer(height)` is the core method behind
it.)

### Documents: `document_store`

Kotlin's `SafDocumentStore` implements `DocumentStoreBridge`, called on the
session thread (blocking provider I/O is fine there):

```kotlin
fun readText(id: String): String          // raw UTF-8 text, not normalized
fun writeText(id: String, text: String)
fun writeBytes(id: String, data: ByteArray)
fun isAvailable(id: String): Boolean
fun recent(): String                      // JSON array of {"id", "display_name", "location"}, pruned
fun addRecent(id: String, displayName: String, location: String)
fun setMaxRecent(count: Int)              // max_recent_files; Kotlin defaults to 10
fun describe(id: String): String?         // ref JSON for an id, or null if unreachable (ref_for)
fun rename(id: String, displayName: String): String  // the renamed doc's ref JSON (Edit/Play)
```

`rename` calls `DocumentsContract.renameDocument` after checking the
provider's `FLAG_SUPPORTS_RENAME`; a provider that can't rename throws
`RenameUnsupportedException` (a `DocumentStoreException`, which Python maps
to `RenameNotSupported` by its class name), any other failure a
`DocumentStoreException`. The URI may change (the provider grants the new
one; Kotlin tries to persist that grant and moves the recent-list entry to
the new ref). Providers pick their own name on a clash (`song (1).txt`) rather
than overwrite, so the returned `display_name` is what the provider made.

Step 14 wraps it in an `AndroidDocumentStore` implementing
`session.documents.DocumentStore`: `read_text` applies
`normalize_song_text` (normalization stays in Python), `recent` turns the
JSON into `DocumentRef`s, `add_recent(ref)` passes the three fields,
`ref_for(id)` is `describe` (None when it returns null), and
`start` calls `setMaxRecent` with the configured value. Failures arrive as
Java `DocumentStoreException`s whose message is user-facing, worded like
`FileService` ("File not found: …", "Permission denied: …", "Cannot read
file (encoding issue): …", "Failed to write file: …"); the wrapper raises
`FileOperationError(e.getMessage())`. Ids are content URIs; the UI takes the
persistable grant when the picker returns, so the store never launches
anything.

### Schema and contract test

Step 14 commits `android/bridge_schema.json`, dumped from the dataclasses by
`session.bridge`, with a Python test that the committed file matches a fresh
dump:

```json
{"version": 1,
 "types": {"HighlightState": {"kind": "state", "fields": {"text_revision": "int", "...": "..."}},
           "DocumentRef": {"kind": "value", "fields": {"id": "str", "...": "..."}}},
 "enums": {"SpanKind": ["chord", "chord_invalid", "..."]},
 "commands": ["set_text", "...", "app_background", "restore_draft"]}
```

`kind` is `state`, `event`, `request` or `value` (nested types: `Span`,
`MenuItem`, `InstrumentFamily`, `ChordSheetView`, `DocumentRef`,
`SettingsValues`, `IdentifierNote`, `VoicingGroup`, `VoicingPreset`,
`QuickStartPage`, `QuickStartBlock`). Field types are `str`, `int`,
`float`, `bool`, an enum or DTO name, `list[X]`, `X|null` and `json` (any
JSON value, a Python field typed `Any`: the voicing form's values, errors
and hints and the editor schema; Kotlin uses `JsonObject`). Two more keys
document the inbound side: `command_params` (each command's parameters and
their types; `selection` is `[start, end]` or null, `any` is `respond`'s
value) and `answers` (what `respond` takes for each request type).
Regenerate with `cd src && python -m session.bridge --schema >
../android/bridge_schema.json`; `tests/test_session_bridge.py` fails while
the committed file is stale. The Kotlin
`BridgeSchemaContractTest` (skipped while the file is missing) checks that
every output type has exactly the same field names on both sides, that
Kotlin decodes every output the schema lists, the value types and enum
values, and that `commands` covers every command Kotlin sends;
`ScreenBridgeTest` does the same for the M5 value types and
`ScreenCommandNames`, and checks the builders' JSON. Both pass against the
committed schema (2026-10-29).

### Kotlin side

- **`PyHost`** (app-scoped, in `AppGraph`): `start()` (from `MainActivity`)
  and every `submit` run on one `python-bridge` thread; Main never calls
  Python. Status is `SessionRepository.hostStatus`.
- **`SessionRepository`**: one `StateFlow` per state (null until the first
  replay), `textEdits` (unbounded channel, one collector: the editor),
  `pendingRequest` (`StateFlow`, survives rotation, cleared by answering),
  `errors` and `closeApproved` (`SharedFlow`s; collect them in a
  ViewModel-scoped place so rotation doesn't drop one).
- **`OffsetMapper`**: the only code-point/UTF-16 conversion; identity (no
  allocation) for text without surrogate pairs.
- **Lifecycle**: `AppLifecycleHooks` on `ProcessLifecycleOwner`;
  `PlaybackAudioPolicy` follows `PlaybackState` (focus requested on entering
  PLAYING, kept while PAUSED, abandoned on IDLE; loss, denial or noisy →
  `pause`); `DraftHook` keeps `(text, document_id, modified)` in the
  activity's saved state (texts over 100,000 chars are not kept) and sends
  `restore_draft` only when the saving process is gone. The editor sets
  `AppGraph.editorText`.
- **The editor (M4a)** is app-scoped (`AppGraph.editor`, an
  `EditorController` over one `TextFieldState`), so rotation loses nothing
  and the session's edits are applied even with no activity on screen.
  - User edits (seen through `snapshotFlow`) go out as `set_text` with an
    increasing `client_token`; commands that read the text (Play, a tap,
    the file commands) send it first (`syncNow`), as the desktop does.
  - `TextEdited` is applied inside `TextFieldState.edit {}`, which records
    one never-merged undo step: right for `group`, close enough for
    `plain`; `reset` then clears the history. It isn't sent back. If the
    user typed something the session hadn't seen yet, the editor's text
    wins and is sent with a new token.
  - A `HighlightState` is painted only when it was computed for the text on
    screen: same `client_token` after a user edit, or token 0 and the
    edit's `text_revision` after a session edit (it may arrive before the
    `TextEdited`; it is re-checked once the edit is applied). Until then
    the painted spans move with the edits like Tk tags.
  - Styles are the desktop's (Tk's named colours, the tag priority, the
    playing chord on top); `OutputTransformation.addStyle` paints them.
    Font: `TkFixedFont`/monospaced names → Monospace, sans → Sans, serif →
    Serif; size in sp = pt × 4/3.
  - Edit mode is the text field: a tap only moves the cursor. Play mode
    (`ChordEditor` with `AppMode.PLAY`) is a plain `BasicText` over the same
    text and spans, so nothing focuses or opens the keyboard. A tap on a
    chord sends `tap_chord_at`; elsewhere `set_playhead` with the nearest
    chord (`ui/play/PlayheadGestures.kt`: vertical gap × 4 + horizontal gap,
    the mockup's rule); a drag that starts within 12 dp of the playhead
    marker scrubs it (drawn locally, one `set_playhead` on release; not
    while playing); other drags scroll. Both modes share one `ScrollState`.
    A pinch sends `step_font_size` in both.
  - Dark theme: the editor's colours are readable variants of the desktop
    hues (`AppColors.Dark`); light mode keeps the desktop's Tk colours.
  - Paste normalization is the one rule set duplicated in Kotlin
    (`PasteNormalization`, the cases of `test_paste_normalization.py`):
    Compose has no paste hook for `TextFieldState`, so it applies to every
    inserted text.
- **Edit / Play** (`ui/main/`, spec `docs/design/android-ui-spec.md`): the
  tab is app-scoped (`AppGraph.mode`, `ModeController`): the first document
  decides (saved → Play, untitled → Edit), then a document that arrives
  after Open/Recent opens in Play and one after New in Edit; Save/Save As
  never switch. Edit while a song plays or is paused sends `stop` first.
  `ScreenLayout` holds the layout rules (phone = smallest width < 600 dp;
  phone landscape in Edit puts the tabs and the ribbon on one line; the
  chord sheet only in Play, below the text in portrait, beside it in
  landscape) and `collapseHeader` the keyboard rule (Edit, IME up, < 170 dp
  of text: the header hides and a floating Undo/Redo chip sits above the
  keyboard). The landscape column width (30–70 %, default 50 %) is a device
  preference (`UiPreferences`, `shared_prefs/ui.xml`), not the session's
  `set_chord_sheet_height` (that stays the portrait height, shared with
  the desktop's sash).
- **Player** (`ui/play/Player.kt`): the song pill (`SongDefaultsState.summary`)
  opens Song defaults; voicing, instrument, ⏮ (`rewind`), ▶/⏸
  (`play_pause {}`: from the playhead), metronome, speed (badge when ≠ 100 %),
  ▭ (`set_chord_sheet_visible`); the status line is `StatusState.text`. In
  Edit mode each new status shows as a snackbar instead; in Play mode no
  status snackbar shows (a leftover one is dismissed) and error snackbars sit
  above the player (`snackbarClearanceDp`).
  *Starting:* from ▶ until the first chord sounds the session renders the
  whole song and reports `PlaybackState(status=playing, chord_index=None)`
  (`PlaybackState?.isStarting`, `ui/main/PlaybackUi.kt`; no extra bridge
  field). The play button shows a progress ring and ignores taps meanwhile;
  ⏮ is the way to cancel. *Voicing lock:* `VoicingMenuState.locked_reason` is
  set while a song plays (not paused); the Voicing button is greyed with that
  reason on long-press and `set_voicing` is refused by the session. A voicing
  chosen while paused makes the next ▶ render again from the paused chord.
  The instrument changes at any time. *Screen on:* the window keeps the
  screen awake only while the status is `playing` (`keepScreenOn`).
- **Sheets** (`ui/sheets/`, route in `SheetRoute`, saved across rotation):
  Song defaults (`set_bpm_text`, `set_time_signature`, `set_key` for the
  editable defaults, `write_song_defaults`, Edit → Edit mode with the cursor
  at `directive_offset`), Voicing (groups by value prefix, "Edit voicings…"
  → Settings at Voicings), Instrument (families → programs, ← back, Done
  closes), Speed (slider 12.5–400 % in 5 % steps → `set_multiplier_pct`,
  Reset, Manual… with `parseSpeedPct` 12.5–400, the session's range), Insert (the six directive
  kinds → `request_insert_directive`). Rename (the title) sends
  `rename_document {name}`; `RenameFailed` without `can_save_as` keeps the
  dialog open with the reason, with it the dialog closes and offers
  `save_as {name}`.
- **Requests (M4b)**: `ui/requests/`. `presentationOf` decides how each
  request is shown: `ConfirmDiscardRequest` as a dialog (the desktop's
  "Unsaved Changes / Do you want to save your changes?", buttons Save /
  Don't save / Cancel, dismiss = cancel), `PickDocumentRequest` as a SAF
  picker, `CapoChoiceRequest` and `InsertDirectiveRequest` as the Tools
  dialogs (M5, below; `NotYetSupported` is left for a request type a newer
  core may add: cancelled at once). `RequestController`
  (app-scoped, in `AppGraph`) remembers which pick request already got a
  picker, so a recreated activity doesn't open a second one and a result
  delivered after a rotation still answers it; a result for anything else
  (a request from before process death) is ignored. `RequestPickers`
  registers the three launchers on the activity in `onCreate` (Open:
  `text/plain`, `text/*`, `*/*`; Save As: `text/plain` with the suggested
  name; Export MIDI: `audio/midi`), follows `pendingRequest` while STARTED,
  and answers with `SafDocumentStore.adopt` (grant persisted, ref
  described) off the main thread; backing out answers null.
- **Drawer** (☰, `ui/main/AppDrawer.kt`) replaces the old ⋮ menu: New
  song, Open…, Recent (inline), Save as…, Export MIDI…, Settings, User
  guide, Quick start, About. The desktop's View menu has no Android entry:
  the font size is the pinch, the family is in Settings › General, the
  chord sheet is the player's ▭. The voicing and instrument rows come from
  `ui/menus/MenuModels.kt`.
- **Tools (M5)**: `ui/tools/`, `ui/identifier/`. The Edit ribbon has
  ＋ Insert (Tempo, Time signature, Key, Capo, Label, Loop), Transpose,
  Identify, AB/Do and Convert (to the other notation; the session switches
  AB/Do with it). Suggest Capo is the Capo dialog's Suggest (it cancels the
  insert request, then `request_suggest_capo`). The desktop's Tools ›
  Settings… is ☰ → Settings. `ToolActions` sends the commands with the editor's selection
  (`selectionOf`: UTF-16 → code points through `OffsetMapper`; an empty one
  is null, the whole song) or cursor, the text synced first.
  - *Transpose* is a local dialog (−11..+11, "Transpose selection/whole
    song" from the selection when it opened) → `transpose`.
  - *Insert* sends `request_insert_directive {kind, at}`; the
    `InsertDirectiveRequest` opens the kind's dialog with the desktop's
    title, text and fields (BPM and Label typed; Time beats 1–16 and the
    `SettingsState` units; Key from `SettingsState`'s list for the
    request's notation; Loop `@start` + the request's labels and a count
    1–100) → `respond {field: value}`. The values go as entered. As they
    change the dialog sends `check_directive {kind, fields, request_id}`
    (the request stays pending) and Python replies `DirectiveCheck {kind,
    request_id, fields, errors: {field: msg}, form_error}` from
    `session.directives.check_directive`; the dialog shows the messages
    and keeps Insert disabled until a clean reply for the current fields
    (`DirectiveVerdict`), so it stays open on a bad value like the
    desktop's. The session still checks on `respond`. Only the pickers'
    ranges and `@start` are mirrored in Kotlin (`ToolForms.kt`).
  - *Suggest Capo* sends `request_suggest_capo {selection}`; the
    `CapoChoiceRequest` opens a radio list of its options, the default
    chosen → `respond(value)`. "Finding a capo…", the result and "No capo
    makes …" are the session's status line.
  - *Identify Chord* is full screen below 600 dp, a dialog wider: the
    two-octave keyboard from C4 (`PianoKeyboard`: tap →
    `identifier_toggle_note`, long-press → `play_note`), the notes field
    (`identifier_set_notes_text`, `typed_text_error` under it; it takes
    `notes_text` only after a key tap), Clear, the candidates (tap picks and
    plays, double-tap or Insert → `insert_chord {at: cursor}`) or
    `message`, and the status line at the bottom ("Inserted chord: C").
    `identifier_clear` when it opens.
- **Close**: Android has no File › Exit. Back on the main screen is the
  desktop's window close: with unsaved changes it sends `request_close`
  (the unsaved-changes dialog, then `CloseApproved` finishes the activity);
  without, the system handles Back (predictive back works). The process
  and session live on after `finish()`, so reopening the app shows the
  same text (still marked modified after "Don't save").
- **Errors** are collected app-wide (`ErrorQueue`) so a rotation drops
  none: `UserError` and `AudioUnavailable` show as dialogs, `UnexpectedError`
  as a snackbar.
- **No Google Play services.** emoji2's `EmojiCompatInitializer` is removed
  from the manifest (it fetched a downloadable font from the Play services
## Chord sheet op buffer

**Status:** the Python half is built (`src/chord_sheet/pack.py`, format
version 1), and the bridge hands it out (`SessionHandle.chord_sheet_buffer`,
"Bridge contract" above); the Kotlin decoder, cache and painter are built
too (M4: `ui/chordsheet/ChordSheetBuffer.kt`, `ChordSheetController.kt`,
`ChordSheetPainter.kt`). A pinch sends its whole step count as one
`chord_sheet_zoom {step}`, which applies `|step|` steps and repaints once.
The zoom buttons and the pinch exist only where `ChordSheetState.zoom_supported`
(staff, fret cards and tab; not the piano roll). Fret cards only grow past the
strip height cap (230 dp x zoom), so on a short strip `+` changes nothing until
`-` has shrunk the cards. While a buffer is being fetched
(`ChordSheetController.loading`) a thin progress bar shows under the tabs.

The chord sheet's renderers (`src/chord_sheet/`) are headless: they record
draw ops (`chord_sheet/ops.py`) that the Tk panel replays onto a canvas.
Android gets the same ops as one `bytes` object per (view, zoom, height):

```python
from chord_sheet.pack import pack_view
data = pack_view(rendered_song, view_id, zoom, height, renderers=None)
```

`view_id` is `keyboard`, `staff`, `fret` or `tab`; `zoom` is the view's zoom
factor (ignored by views without zoom support); `height` is the strip's
content height in dp, the marker lane excluded. `renderers` defaults to the
standard set (`chord_sheet.registry.default_renderers()`); the session passes
the chord sheet viewmodel's own list. Packing is deterministic (same inputs,
same bytes). `chord_sheet.pack.unpack()` is the reference decoder and
`tests/test_chord_sheet_pack.py` pins the layout (`test_format_golden`) and
each view's bytes for a sample song (`test_view_golden`).

Kotlin decodes a buffer once, keeps it, and draws only the ops inside the
visible range. A new buffer is needed when the rendered song, the view, the
zoom or the strip height changes, never on scroll.

### What a buffer holds

- **Content ops**: the view's strip, in content coordinates (x from the
  strip's left edge, right of the gutter; scrolls horizontally).
- **Lane ops**: the marker lane (sections, loops, tempo, meter and key
  changes), `lane_height` tall, drawn above the content and scrolled with it.
- **Slots**: one per chord, in song order, rests included: `chord_index`
  (index into `RenderedSong.chords`, the same index `audition` and the
  playhead use), `x` and `width`. Tap hit-test: content x = scroll offset +
  tap x; the slot with `x <= cx <= x + width` is auditioned. The playhead
  highlight is a rect in the `highlight` colour over the current slot's
  `x .. x + width`, full content height, drawn *behind* the content ops.
- **Gutter variants and runs**: the frozen left gutter (piano-roll keyboard,
  staff clefs + key signature), `gutter_width` wide, drawn in gutter-local
  coordinates in a pane that does not scroll; above it, a `lane_height` corner
  filled with `background`. The staff gutter shows the key signature in
  effect at the first visible chord, so a buffer carries one pre-painted
  variant per distinct gutter and a list of runs `(start_x, variant)` sorted
  by `start_x`, the first at `-inf`. For a scroll offset `s` (content x at the
  viewport's left edge) draw the variant of the **last run with
  `start_x < s`**. A static gutter is one variant and one run; a view with no
  gutter (`fret`, `tab`) has `gutter_width = 0` and no variants.
- `background` (the strip colour, `#fbfbf8`) and `highlight` (`#ffe58a`).

### Byte layout (version 1)

Little-endian throughout, no padding or alignment (read with absolute offsets
from a `ByteBuffer` in `LITTLE_ENDIAN` order). `f32` is IEEE 754 float32;
`str` is a `u16` index into the string table, `0xFFFF` meaning "none".

Header (`header_size` bytes; 48 in version 1, a later minor addition may
append fields, so always continue at `header_size`):

| Offset | Type | Field |
|---|---|---|
| 0 | 4 bytes | magic `CNSB` |
| 4 | u16 | version (1) |
| 6 | u16 | header_size (48) |
| 8 | str | view_id |
| 10 | str | background colour |
| 12 | str | highlight colour |
| 14 | u16 | flags (0, reserved) |
| 16 | f32 | zoom |
| 20 | f32 | height (as requested) |
| 24 | f32 | content_width |
| 28 | f32 | content_height |
| 32 | f32 | gutter_width (0 = no gutter) |
| 36 | f32 | lane_height |
| 40 | u32 | string_count |
| 44 | u32 | slot_count |

Then, in order:

1. **String table**: `string_count` × (`u16` byte length, UTF-8 bytes).
   Strings are numbered from 0 in first-use order: colours, text, image
   keys and tags all share it.
2. **Slots**: `slot_count` × (`u32` chord_index, `f32` x, `f32` width).
3. **Content op list.**
4. **Lane op list.**
5. `u16` variant_count, then variant_count **gutter op lists**.
6. `u16` run_count, then run_count × (`f32` start_x, `u16` variant). The
   first run's start_x is `-inf`.

The buffer ends exactly there. An **op list** is `u32` op_count, `u32`
byte_length (of the ops that follow, so a list can be skipped), then the
ops. Each op is a `u8` opcode, its fields, then its tags (`u8` count, count ×
`str`):

| Opcode | Op | Fields after the opcode |
|---|---|---|
| 1 | rect | `f32` x, y, w, h; `str` fill; `str` outline; `f32` width |
| 2 | oval | same as rect; the ellipse inscribed in the box |
| 3 | line | `str` fill; `f32` width; `u16` n; n × (`f32` x, `f32` y) |
| 4 | polygon | `str` fill; `u8` smooth; `u16` n; n × (`f32` x, `f32` y) |
| 5 | text | `f32` x, y; `str` text; `u8` anchor; `u8` bold; `f32` size (pt); `str` fill |
| 6 | image | `f32` x, y; `str` key; `u8` anchor |

Anchors: 0 `nw`, 1 `n`, 2 `ne`, 3 `w`, 4 `center`, 5 `e`, 6 `sw`, 7 `s`,
8 `se`. An unknown opcode or version is an error (don't guess at sizes).

**Colours** are Tk colour strings; every renderer today uses `#rrggbb`.
Rect/oval fill or outline "none" (`0xFFFF`) or `""` means don't paint that
part. Line, polygon and text never come without a fill today; if one does,
Tk's default is black.

**Image keys** (staff view only): `clef_<kind>:<h>`, `glyph_<name>:<h>` and
`glyph_<name>:<h>:<rrggbb>` (`chord_sheet.clef_assets.parse_image_key`).
The part before the first `:` names one of six base PNGs that the
`exportClefGlyphs` Gradle task puts in `assets/chord_sheet/<name>.png`
(from `android/tools/export_clef_glyphs.py`, with a `glyphs.json` of base
sizes). Draw it `h` dp tall and `max(1, round(base_w * h / base_h))` wide,
anchored like text (only `nw` today). A colour tints the black ink, keeping
the alpha (`ColorFilter.tint(colour, BlendMode.SrcIn)`). Keys repeat a lot;
cache one scaled bitmap per key.

Limits: 65535 strings and 255 tags per op (`pack_view` raises `ValueError`
past them), 65535 points per line or polygon. Per-chord tags (`slot:<i>`)
use one string each, so the string table grows with the song; a 2,000-chord
song stays far below.

### Sizes and timings

`examples/02_american_complete.txt` (133 chords, 15 markers), height 130,
zoom 1. Desktop, Python 3.14.8, median of 15 runs, host load average ~13 on
24 threads. "Render" is layout + paint + lane + gutter variants
(`collect_view`); "pack" is the serialisation alone. Guitar voicing (all four
views) and, for the views that don't need fingerings, piano voicing:

| View | Voicing | Ops (content + lane + gutter) | Bytes | zlib -6 | Render | Pack |
|---|---|---|---|---|---|---|
| keyboard | guitar | 946 + 44 + 40 | 33,645 | 8,912 | 3.2 ms | 2.2 ms |
| staff | guitar | 1,078 + 44 + 15 | 25,028 | 8,366 | 11.0 ms | 2.2 ms |
| fret | guitar | 2,600 + 44 | 76,358 | 19,899 | 3.4 ms | 3.5 ms |
| tab | guitar | 1,820 + 44 | 50,542 | 9,284 | 2.8 ms | 1.8 ms |
| keyboard | piano | 883 + 44 + 50 | 33,327 | 8,759 | 2.0 ms | 1.4 ms |
| staff | piano | 1,246 + 44 + 15 | 30,724 | 10,118 | 8.3 ms | 1.5 ms |

Height and zoom barely change the size (staff at zoom 2.5: 25,030 bytes;
height 260: 25,029) since the op count stays the same. The sample has a single
key, so the staff gutter is one variant; each extra key signature adds one
gutter list of about 15 ops (~400 bytes). Expect the emulator to be ~3 to 4×
slower (the M2 render ratio). Compression isn't worth it in-process; the
`bytes` crosses Chaquopy as one `byte[]`.

### Units and calibration for Kotlin

- **Coordinates and widths** are Tk canvas pixels, designed at 96 DPI. Map
  1 px to **1 dp**. The same goes for `height` and `gutter_width`, and for
  the strip height the session stores.
- **Font sizes** are points (`size`); Tk turns them into pixels at 96 DPI,
  i.e. 4/3 px per pt. Use **sp = size × 4/3** (8 pt → 10.67 sp, 12 pt → 16
  sp). The font is `TkDefaultFont` (a sans serif on every desktop), so use
  `FontFamily.SansSerif`, bold when `bold` is set. Desktop HiDPI scaling
  enlarges Tk fonts but not canvas geometry; the 96 DPI baseline above is
  what the renderers are laid out for.
- **Text anchors** place the text's bounding box, Tk style: the box is the
  measured advance width × the font's line spacing (ascent + descent), and
  `(x, y)` is the box's anchor point (`nw` = top-left, `n` = top-centre, `w`
  = left-middle, `center`, `e` = right-middle, ...). Emulate with
  `TextMeasurer`: measure with `includeFontPadding = false`, then draw at
  `(x - fx × width, y - fy × height)` with `fx`, `fy` in {0, ½, 1} from the
  anchor. Text is single-line.
- **Strokes**: line width in dp, butt caps (Tk's default), round joins. Rect
  and oval outlines are centred on the box edge.
- **Polygon `smooth`** (unused by the renderers today) is Tk's quadratic
  B-spline: start at the midpoint of the last and first points, then
  `quadraticTo(p[i], mid(p[i], p[i+1]))` around the ring.
- **Marker lane label widths** are not measured: `marker_lane._CHAR_W = 5.5`
  px per character at 8 pt is the estimate the lane uses to keep the next
  flag clear (plus an 8 px gap). Android's sans serif measures differently
  from the desktop font, so a long label can run into the next flag. Clip
  each lane label at the next lane text op's x minus 2 dp rather than
  re-laying out the lane.
- The ops are in content dp before any pinch: during a pinch, scale with
  `graphicsLayer`, then ask for a new buffer at the new zoom (plan: one
  re-render per gesture).

  fonts provider; that is what killed the first emulator launch). The app
  has no INTERNET permission. CI checks both with `tools/check_manifest.py`.
- **Checked on the emulator** (2026-10-29, stub host): Python starts off
  Main, the stub's `StatusState` reaches the placeholder screen, and Stop,
  `app_background` and `app_foreground` reach Python on the bridge thread.
- **Checked on the emulator with the real host** (2026-10-29, step 14,
  debug APK, `cn_phone`): the session starts in about 5 s after launch
  (FluidSynth on `oboe`, the SoundFont from `filesDir`); Open through the
  SAF picker reads `Download/e2e_song.txt` through `AndroidDocumentStore`,
  and `DocumentState`, `HighlightState` (10 spans), the toolbar from the
  file's directives and the recent list come back; Play runs to the end
  with `PlaybackState`/`StatusState` updates; Home (`app_background`) writes
  `files/config/chord-notepad/settings.json`. No `UnexpectedError`.

### CI

The `android` job in `.github/workflows/build.yml` runs on pushes, pull
requests and manual dispatches, independent of the desktop jobs (nothing
needs it; it attaches nothing to releases). It checks out the native
submodules with the two-step init above, sets up Temurin 21, Python 3.14.8
(as `CHAQUOPY_BUILD_PYTHON`), Gradle (`cache-provider: basic`) and the
pinned NDK/CMake/platform/build-tools, caches the native libraries (keyed by
`build.sh` and the submodule commits) and the wheelhouse, fetches the
wheelhouse with `--require-hashes`, runs `./gradlew testDebugUnitTest lint
assembleDebug`, then `check_16k.py`, `zipalign -c -P 16` and
`check_manifest.py` on the debug APK.

## About and the licences screen

☰ → About shows the name, `versionName` (the `VERSION` file), the build type,
`versionCode`, the git commit (`BuildConfig.COMMIT`, from `git rev-parse`; set
`-PcnCommit=<id>` outside a checkout) and no date, so builds stay reproducible.
Links open only when tapped, through an `ACTION_VIEW` intent; the app has no
INTERNET permission.

**Open source licences** has three sources:

- *Maven libraries* (AndroidX, Kotlin, ...): the AboutLibraries Gradle plugin
  (`com.mikepenz.aboutlibraries.plugin.android`, build time only, no runtime
  dependency) writes `res/raw/aboutlibraries.json`. `offlineMode` is on, so it
  reads POM data only and needs no network beyond the Maven artifacts. It adds
  no permission and no Play services (`tools/check_manifest.py` passes).
- *Everything it can't see*: `app/src/main/assets/licenses/components.json`
  (Python, Chaquopy and the libraries it bundles, the audio libraries, the
  Python packages, the SoundFont, Bravura, the app itself). Each entry names
  its licence texts (`texts/<name>.txt`, verbatim upstream files) and, for
  LGPL and MPL components, where the source is.
- *Texts*: `assets/licenses/texts/`, produced by `tools/gather_licenses.py`
  (wheels from the wheelhouse, the native submodules, this repo, distribution
  licence directories; `--check` verifies). Three texts are kept by hand (see
  `ONE_OFF` in the script).

To update: bump a pinned Python package in `requirements.txt`, then change its
`version` in `components.json` (a unit test fails until they agree) and run
`gather_licenses.py`; for a native submodule or a Chaquopy bump, check the
version strings against the APK (`strings` on the `.so` files) and edit the
entry. A new bundled component needs an entry, with a text file added to the
script's table. `LicencesTest` checks that every entry parses, every named text
exists, no text is unused, the Python entries match `requirements.txt`, and
that every Maven licence id the plugin exports has a text. The Maven list
changes with dependencies; the rest only when you edit these files.

Note: pyFluidSynth's metadata says MIT but its LICENSE file and source header
are LGPL 2.1; it is listed as LGPL.

### Closing with Back

Back on the editor with unsaved changes asks (`request_close`). "Don't save"
leaves the session with the discarded text, so `CloseCoordinator` (app-scoped)
sends `stop` and `restore_draft("", null, false)` before the activity finishes,
and reopening shows a fresh Untitled document. It also turns the non-replaying
`CloseApproved` event into a `finishRequested` state, so a close approved
during a rotation still finishes the new activity once.

## Help: User Guide and Quick Start (M5)

**User Guide.** The Gradle task `buildAndroidHelp` runs
`python -m sphinx -t android -b html -W` on `help/` (the same as
`make docs-html-android`) into the generated assets, so the APK has
`assets/help/index.html` and friends (build bookkeeping and the unused
`.ttf/.eot/.svg` fonts are removed; about 6 MB unpacked). A docs warning fails the
build. The output is reproducible: the theme prints no build time and the task
pins `SOURCE_DATE_EPOCH`. The Python needs the desktop docs stack:

- locally, `CHORD_NOTEPAD_DOCS_PYTHON` in `android/local.env` points at the
  pipenv venv's python (`pipenv --venv`); without it the task uses
  `CHAQUOPY_BUILD_PYTHON`;
- CI installs `android/docs-requirements.txt` (hash-pinned from `Pipfile.lock`;
  regenerate when Sphinx or the theme changes there) into that Python before
  Gradle runs.

`UserGuideScreen` shows it in a WebView through `androidx.webkit`'s
`WebViewAssetLoader` on `https://appassets.androidplatform.net/assets/help/`.
Only that origin loads (anything else gets a 403), file and content access are
off, and there is no INTERNET permission. JavaScript is on because the
sphinx_rtd_theme menu and search need it. A tapped link to another site opens
through `ACTION_VIEW` (`HelpLinks.isExternal`). Back goes back through the
WebView history, then leaves; the page survives rotation (the history does
not). ☰ → User guide opens it, and so does F1 on a hardware keyboard.
`HelpAssetsTest` checks that the generated `help/` has `index.html` and no
`file://` links or build paths.

The Android edition has its own look and screenshots: `help/_static/android.css`
(the app's colour tokens, phone layout, dark mode through
`prefers-color-scheme`) and `help/images/android/` (optional `<name>.dark.png`
variants for dark mode). WebView sets `prefers-color-scheme` from its
context's `isLightTheme`, and the activity's theme is always light, so
`UserGuideScreen` creates the WebView with a `ContextThemeWrapper` on
`Theme.Material` or `Theme.Material.Light` to match the app (Android 10+;
older versions show the light guide). How to write for both editions:
[HELP_AUTHORING.md](HELP_AUTHORING.md).

**Quick Start.** `QuickStartRoute` sends `request_quick_start` and renders
`QuickStartContent` page by page in Compose (`QuickStartPager` holds the page;
snippets are `snippetRuns`: the session's code-point spans converted to UTF-16
and styled with the editor's `SpanStyles`, on the editor's white background in
monospace, read only). Previous/Next/Done and a "Show at startup" checkbox that
sends `set_show_quick_start_on_startup`. ☰ → Quick start opens it; it also
opens on its own when `SettingsState.values.show_quick_start_on_startup` is true
(`QuickStartLaunch.shouldAutoShow`), once per process start: the flag
`AppGraph.quickStartShown` lives in the app-scoped graph, so rotation does not
show it again.

### Screenshots for the guide

`help/images/android/` is produced by `android/tools/help_screenshots.py`
from the shot list `android/tools/help_shots.json`, on the emulator, with the
debug-only `HelpShotActivity` (`src/debug`) setting up each scene. It takes
the shared emulator lock (`$ANDROID_ROOT/emulator.lock`). How to run it, the
manifest format and which image belongs to which page:
`android/tools/HELP_SHOTS.md`. The main screen's controls carry Compose test
tags (`ui/UiTags.kt`) for it.

## Natives from source and offline packages (M6 groundwork)

**Date:** 2026-10-29. Nothing in a default build now comes from a prebuilt
binary or a package index: the natives compile from pinned submodules and
pip installs from a hash-checked local wheelhouse. (F-Droid itself isn't being
pursued yet; this only keeps the build compatible with it.)

### Native sources

All in `android/native/`, shallow submodules pinned to the release tag's
commit. `build.sh` refuses to build if a checkout isn't at its tag.

| Component | Version | Licence | Ships in the APK as |
|---|---|---|---|
| FluidSynth | 2.6.1 | LGPL-2.1-or-later | `libfluidsynth.so` |
| Oboe | 1.10.0 | Apache-2.0 | `liboboe.so` |
| libsndfile | 1.2.2 | LGPL-2.1-or-later | `libsndfile.so` |
| libogg | 1.3.6 | BSD-3-Clause | `libogg.so` |
| libvorbis | 1.3.7 | BSD-3-Clause | `libvorbis.so`, `libvorbisenc.so`, `libvorbisfile.so` |
| FLAC (libFLAC only) | 1.4.3 | BSD-3-Clause (Xiph); the GPL'd tools aren't built | `libFLAC.so` |
| Opus | 1.5.2 | BSD-3-Clause | `libopus.so` |
| gcem (FluidSynth's submodule) | 1.18.0 | Apache-2.0 | header-only, compiled in |
| signalsmith-audio-basics (FluidSynth's submodule) | 012d2be | MIT | header-only, compiled in (limiter, reverb) |
| signalsmith-linear | 0.3.1 | MIT | header-only, compiled in |
| signalsmith-dsp | 1.7.1 | MIT | header-only, compiled in |
| signalsmith-hilbert (hilbert-iir) | 1.0.0 | 0BSD | header-only, compiled in |
| libc++ (NDK 27.3) | | Apache-2.0 WITH LLVM-exception | `libc++_shared.so` |

FluidSynth's CMake git-clones the three signalsmith libraries at configure time
(`FetchContent`); `build.sh` points it at the submodules instead and sets
`FETCHCONTENT_FULLY_DISCONNECTED`, so configuring never touches the network.
Its `gcem` submodule is likewise required (it would otherwise be downloaded);
`test/manual` (test data) is not.

`build.sh` follows upstream's `.azure/azure-pipelines-android.yml` and
`cmake-android.yml` (v2.6.1): NDK 27.3.13750724, API 24, shared libraries,
`c++_shared`, `-Denable-oboe=1 -Denable-opensles=1 -Denable-floats=1`, the same
per-library options, `-Wl,-z,max-page-size=16384`, RelWithDebInfo. Deliberate
differences: SDK CMake 3.31.6 with Ninja (the host has CMake 4.3, which rejects
libvorbis's `cmake_minimum_required(2.8.12)`); `-ffile-prefix-map` for the
source, build and NDK paths and a fixed `DEFAULT_SOUNDFONT` (it defaulted to
the install prefix, i.e. the checkout path); libsndfile's MPEG support off
explicitly (upstream gets the same result by not having mpg123/lame). The
FluidSynth build summary: Oboe yes, OpenSLES yes, SF3 yes, DLS yes,
libsndfile yes, limiter yes, float samples.

Outputs go to `$CHORD_NOTEPAD_ANDROID_BUILD_ROOT/<checkout>/native/<abi>/lib`
(about 86 MB per ABI including CMake work dirs). A stamp per ABI hashes the
script, the toolchain versions and every submodule's commit and local diff;
an unchanged ABI is skipped in well under a second. A full build of one ABI
takes about 50 s with `-j4` on this machine.

### Sizes vs the upstream prebuilt

After stripping (`llvm-strip --strip-unneeded`, what AGP does), in bytes:

| Library | arm64-v8a source | arm64-v8a prebuilt | x86_64 source | x86_64 prebuilt |
|---|---|---|---|---|
| libfluidsynth.so | 594,256 | 544,536 | 668,192 | 587,152 |
| libopus.so | 398,032 | 400,048 | 477,856 | 479,936 |
| liboboe, libsndfile, libFLAC, libogg, libvorbis* | same size | same size | same size | same size |
| **Total (9 libraries)** | **2,955,168** | **2,907,464** | **3,219,816** | **3,140,856** |

Everything but FluidSynth and Opus comes out exactly the same size as
upstream's build. FluidSynth is 50 to 80 KB bigger, most likely because it's
2.6.1 against the prebuilt's 2.6.0 (not checked by building 2.6.0). Opus is
2 KB smaller. The universal release APK is 90.86 MB with source-built
natives vs 90.73 MB with the prebuilt (it was 91.0 MB in M2, before the pure
charset-normalizer wheel dropped its binary module). All `PT_LOAD` segments
are 16 KB aligned; `tools/check_16k.py` and `zipalign -c -P 16` pass.

**On the emulator** (`cn_phone`, x86_64, release build, spike auto mode):
`FluidSynth started with audio driver: oboe`, 48 kHz, the SF2 loads, song
playback starts and chord taps reach `noteon` in ~1 ms. (SF3 decoding, the
one path that exercises libsndfile and the codecs, isn't used by the app
today.)

### Python packages offline

`android/requirements.txt` pins every package with the sha256 of its
`py3-none-any` wheel on PyPI. `tools/build_wheelhouse.py` fills
`$CHORD_NOTEPAD_ANDROID_CACHE/wheelhouse` with `pip download --require-hashes
--no-deps --only-binary=:all: --platform any --abi none` (21 MB, 12 wheels),
`check` verifies it offline, and `lock` rewrites the hashes from PyPI's JSON
API after a version bump. Gradle reads the pins from the same file, so there's
one list. Chaquopy's pip runs with `--no-deps --no-index --find-links
<wheelhouse> --find-links <trimmed music21 dir>`; its log shows only
"Looking in links", no index. `strip_music21.py` now takes the upstream wheel
from the wheelhouse (its own hash pin stays as a second check).

To bump a package: edit the version in `android/requirements.txt`, run
`python3.14 android/tools/build_wheelhouse.py lock`, then
`python3.14 android/tools/build_wheelhouse.py`, then build.

**Network-free check:** reproducibility copy A (below) was built inside a
network namespace with only loopback up (`unshare -c -n --keep-caps`, then
`ip link set lo up`; a `curl https://pypi.org` in it fails) and `gradlew
--offline --no-daemon`. It built from clean, natives included, so neither
Gradle, CMake, `build.sh`, the wheelhouse step nor Chaquopy's pip needed the
network. Its log has no `chaquo.com`, `pypi.org` or `pythonhosted` URL and
pip reports only "Looking in links". (`unshare -r`, which runs the build as
uid 0, is a trap: the JVM's `user.home` becomes `/root` and the Kotlin daemon
client spun for 10+ minutes walking a directory tree. Keep your uid with `-c`.)

### Reproducibility with source-built natives

**Still byte-identical.** Same method as M2: one snapshot of commit
`4804e29` (rsync of the tree, then `git checkout -- src tests` in the copy to
drop unrelated uncommitted work), copied to
`/mnt/data_linux/Bin/android/repro/m6-a/chord-notepad` and
`.../m6-b/chord-notepad-other-name`, each built from clean with
`--no-daemon --no-build-cache --no-configuration-cache`. Copy A ran offline
in the network namespace above, copy B normally. Each checkout compiled its
own natives into its own per-checkout build directory.

- Both APKs: sha256 `6059abf8ed70c3f6…`, 90,856,460 bytes; `compare_apks.py`
  reports IDENTICAL.
- The unstripped `.so` files from both copies are identical too, so the
  prefix maps work and nothing else path- or time-dependent gets in (no
  `__DATE__`/`__TIME__` in these sources; the NDK's sha1 build-id is content
  based).
- A third build, in the main checkout with a warm Gradle daemon,
  configuration cache and a different `SOURCE_DATE_EPOCH` (the commit before),
  produced the same sha256. The epoch value doesn't reach the APK; setting
  it is what matters (hash-based pycs).

Still not covered: a different machine or user, a different host
`python3.14` micro version as buildPython, and a different host `pkg-config`.
The copies were deleted afterwards; the APK and both build logs are kept in
`$CHORD_NOTEPAD_ANDROID_CACHE` (`apks/m6-source-universal.apk`,
`m6-repro-a-offline.log`, `m6-repro-b.log`).

### What's still prebuilt

- Chaquopy's own runtime: CPython 3.14.8, its stdlib modules, OpenSSL, SQLite
  and `libchaquopy_java.so`, from Maven Central (`com.chaquo.python:target`)
  through Gradle. F-Droid would need these from source too (a cpython srclib,
  as the plan's recipe notes say).
- `libc++_shared.so`, from the NDK (as for any NDK app).
- AndroidX/Compose/Kotlin libraries from Google Maven / Maven Central.
- The FluidSynth 2.6.0 zip, only with `-PcnNatives=prebuilt`.

## Required core changes (found by the spike)

The spike ran the core unmodified; `chordnotepad_android/android_shim.py`
patched around these at runtime. Each becomes a real core change, after which
its shim goes away. Items 1 to 4, 6 and 7 landed with M1b (2026-10-29); the
shim now only sets the data directories (item 5), and the spike passes its
synth settings through `AudioOptions` (`android_shim.audio_options()`).

1. **Done (M1b).** **`audio/fluidsynth_import.py`: accept a bare soname.** On Android the
   native libraries stay inside the APK, so there is no file path; only
   `libfluidsynth.so` (resolved by the linker from the app's namespace) works.
   CPython 3.14's `ctypes.util.find_library` on Android only looks in
   `/system/lib64`, and the `CHORD_NOTEPAD_LIBFLUIDSYNTH` override requires an
   existing file. Fix: if the value has no `/`, skip the `exists` check; on
   `sys.platform == "android"` default to `libfluidsynth.so`.
2. **Done (M1b).** **`audio/player.py`: Android driver list.** `sys.platform` is `"android"`,
   which falls into the Linux branch (`pulseaudio`, `alsa`, `oss`). It must be
   `["oboe", "opensles"]`. (Also log the driver that actually started; today it
   logs the requested one.)
3. **Done (M1b).** **NULL audio driver check.** pyfluidsynth's
   `Synth.start()` returns `FLUID_OK` even when `new_fluid_audio_driver()`
   returned NULL, so the fallback and the "audio unavailable" path never run.
   Check `synth.audio_driver` after `start()`.
4. **Done (M1b):** `AudioOptions(sample_rate, period_size, settings)`, passed
   to `PlaybackService(..., audio_options=)` or `initialize_player()`.
   **Synth settings from the host.** `NotePlayer` creates `fluidsynth.Synth()`
   at pyfluidsynth's default 44.1 kHz; the device's native rate (48 kHz on the
   emulator and most phones) avoids a resampler. The host should pass the
   sample rate and extra settings (`audio.oboe.performance-mode=LowLatency`,
   later `synth.dynamic-sample-loading`).
5. **Done (session step 14):** `AppDataService(root=filesDir)`, same layout
   as the shim's (`filesDir/config/chord-notepad`, `filesDir/data/
   chord-notepad`). **App data directories from the host.** `AppDataService`
   fell into the Linux/XDG branch on Android; the shim pointed `XDG_*` at
   `filesDir` (still used by the throwaway spike).
6. **Done (M1b), by item 7:** there is no Python timing loop any more.
   **Playback loop re-anchors on every event, so lateness accumulates.**
   After each event the loop sets `_wall_anchor = time.time()`, so each event's
   lateness shifts every later event. Measured drift: +80 to +90 ms over 60 s
   when idle, **+5.65 s over 60 s** with a concurrent Python render. Schedule
   against the song start (re-anchor only on pause and multiplier changes) and
   use a monotonic clock (`perf_counter`, already planned in M1b).
7. **Done (M1b):** song notes and metronome clicks are scheduled on
   FluidSynth's sequencer at absolute ticks of its sample clock
   (`audio/sequencer.py`, `audio/song_scheduler.py`). A `PlaybackClock` thread
   only feeds it 2 s ahead and posts the UI pings; FluidSynth's audio thread
   never calls into Python. Pause, stop and live speed changes remove the
   queued events and resend from the current position. Click-to-hear
   note-offs go through the sequencer too (no timer thread per click).
   Measured below ("After the Sequencer, desktop").
   **GIL contention during playback** (see measurements): any Python work on
   another thread (a chord-sheet render, detection while typing) delays the
   player thread by tens of ms per event. Either keep the timing loop out of
   Python (pyfluidsynth's `Sequencer`, the plan's first fallback) or avoid
   Python work during playback. See the attribution runs below.
8. **Play renders the whole song before the first note.** Play to first note
   was 1.4 s for the 133-chord sample on the emulator, almost all of it
   `SongRenderer` (0.8 to 1.3 s here vs 0.32 s on the desktop). Options: render
   the first bars first and stream the rest, or reuse the `RenderedSong` that
   the chord sheet already renders after each edit.
9. Known, already planned: `utils/observable.py` imports `utils/error_reporting`
   (tkinter) at module level (M1 step 2; not hit by the spike's import path, but
   it blocks every viewmodel), and `ui/chord_sheet` must move to
   `src/chord_sheet` with a guarded PIL import before the op buffer can run on
   the device (the APK excludes `ui/**`). **Done:** the renderers are in
   `src/chord_sheet/`, `clef_assets.py` no longer imports PIL (Tk decoding is
   `ui/chord_sheet/clef_images.py`), and the op buffer is
   `chord_sheet/pack.py` (see "Chord sheet op buffer").

Build-side notes, not core changes:
- `charset-normalizer` 3.5.2 resolved to an Android binary wheel
  (`md.cpython-314-*.so`) from chaquo.com's index. **Done (M6 groundwork):**
  the wheelhouse pins its pure-Python wheel.
- Release builds are not minified yet; R8 would cut the 7.7 MB of dex
  substantially (Chaquopy ships its own keep rules).
- The SF2 is 29 MB of every APK. An SF3 (Ogg-compressed) GeneralUser GS would
  shrink it severalfold; FluidSynth 2.6 with libsndfile/vorbis loads SF3.
  Check the licence before converting.

## 16 KB page verification

**Date:** 2026-10-29. `cn_phone_16k` (16 KB page-size system image, x86_64,
headless, 2 GB), debug APK. `adb shell getconf PAGESIZE` = 16384. The app
installs and starts (cold start 5.7 s on the first start after boot), logcat
shows `FluidSynth started with audio driver: oboe`, the session starts, and
playing a typed `C Am F G C` highlights the playing chord and shows
`Bar 2/5 | 120 BPM | 4/4 | Playing: Am` with no crash (zero `FATAL EXCEPTION`).
F1 opened the User Guide with a hardware key right after dismissing the Quick
Start. Not checked on this run: the chord sheet strip (hidden by default in
the compact layout) and loading `examples/02_american_complete.txt` through
the picker. The first launch right after the install was lost while the system
was still settling after boot (the process was gone; a second start was fine).

**Second pass, 2026-10-29** (debug APK, x86_64, headless 2 GB, `cn_phone` and
`cn_phone_16k`):

- *First launch after a fresh install.* Not reproduced: `adb uninstall`,
  `install`, `am start -W` twice on `cn_phone` (TotalTime 2.7 s, 1.8 s) and
  three times on `cn_phone_16k` (including one right after `adb reboot`;
  2.2 s, 2.3 s, 4.0 s). The process was alive 25 s later every time, with no
  `FATAL EXCEPTION`, native crash, python traceback or ANR from the app. On
  the 16 KB image lmkd was busy right after the install (75 and 102 kills of
  cached system and Google apps, "min watermark is breached"; free memory
  176 MB of 2.4 GB), but the app was never among them. So the earlier loss was
  an lmkd kill under 2 GB emulator memory pressure, not an app bug. Not
  retried with `-memory 3072` since nothing failed. Logs: not kept in git.
- *Autosave.* BPM 90 and the Do notation toggled, 3 s wait, `force-stop`:
  `settings.json` held `"bpm": 90` and `"notation": "european"`, and both came
  back after relaunch.
- *Hardware keys.* With the Quick Start switched off, F1 one second after
  launch opens the User Guide; Ctrl+N (`input keycombination 113 42`) shows
  "New file created".
- *User Guide.* Renders (not blank) and links navigate (Getting Started). One
  console error: `sphinx_highlight.js` read `sessionStorage`, which is null
  with DOM storage off. Fixed by `domStorageEnabled = true` (the pages are
  local assets, nothing else changes); the error is gone. No 404s or CSP
  errors.
- *16 KB, file and chord sheet.* `02_american_complete.txt` opened through the
  system picker (Downloads); View, Chord Sheet shows the piano roll and staff;
  Play highlights the chord in the editor and the sheet ("Bar 4/125 ...
  Playing: C"). Fret cards and Tab are greyed out for the piano instrument, so
  they were not switched to. No crash. In the Do (European) notation the
  American chords are not highlighted, which is expected.

## Spike measurements (M2)

**Date:** 2026-10-29. **Device:** Android emulator `cn_phone` (Pixel 8 profile,
API 36 Google APIs x86_64, 2 vCPU, 2 GB RAM, KVM, headless,
`-gpu swangle_indirect`), emulator 37.2.12, on a shared Fedora 44 host with
a load average of 35 to 50 on 24 threads during the runs. Treat timings as
pessimistic and noisy. **Build:** release, not minified, debug-signed,
trimmed music21, unless noted. Phone numbers: still to do (see below).

### Verdicts

| Question | Verdict |
|---|---|
| Chaquopy + core works? | **Go.** Python 3.14.8 starts; music21, the core, detection, render and playback all run unmodified, with the runtime shims listed above. |
| Audio plays? | **Go (pipeline-level).** FluidSynth 2.6.0 starts on `oboe` (AAudio stream at 48 kHz, active in AudioFlinger); SF2 loads from `filesDir`. On the emulator the host audio backend didn't initialise ("Could not init `pa'"), so nothing was audible. Audible output must be checked on the phone. |
| Scheduling jitter OK? | **Go only while Python is idle; No-go under concurrent Python work.** Idle: interval error p99 0.9 to 1.4 ms. With one other Python thread busy (a render loop as a stand-in for a chord-sheet render): p50 26 ms, p99 49 to 76 ms, drift +5.5 s per minute. See below. Recommendation: move to pyfluidsynth's `Sequencer` (sample-clock timing in C) as planned, and fix the drift (core change 6). **Done in M1b**; see "After the Sequencer, desktop". |
| APK size? | **Acceptable, with easy wins left.** 91.0 MB universal, 69.8 MB arm64-v8a only (trimmed music21). The SF2 is 29 MB of that; R8 and an SF3 would cut a further ~25 to 30 MB. |
| 16 KB pages? | **Go.** All 160 ELF files (APK `lib/` plus Chaquopy's nested extension modules) have 16 KB `PT_LOAD` alignment; `zipalign -c -P 16` passes; the app runs and plays on the `google_apis_ps16k` image (`getconf PAGESIZE` = 16384). |
| Reproducible? | **Yes, on one machine.** Two clean release builds from different checkout paths are byte-identical, signature included, after two fixes (see below). Re-checked with source-built natives and the offline wheelhouse: still identical. |

### Numbers

| Metric | Value | Notes |
|---|---|---|
| APK, universal (arm64-v8a + x86_64), music21 untrimmed | 108.6 MB | |
| APK, universal, music21 trimmed | 91.0 MB | `tools/strip_music21.py`: wheel 20.1 → 2.3 MB |
| APK, arm64-v8a only, untrimmed / trimmed | 87.5 / 69.8 MB | |
| APK, x86_64 only, trimmed | 70.1 MB | |
| arm64 APK breakdown (trimmed) | SF2 29.2, libpython + OpenSSL + SQLite 12.7, dex 7.7 (no R8), stdlib 6.6, music21 + deps 5.9 (23.5 untrimmed), FluidSynth + codecs + Oboe + libc++ 4.2, other 3.3 MB | |
| Cold start → first frame (`am start -W` TotalTime) | 1.79 / 1.80 / 2.11 s | three cold starts after the first launch |
| First launch after install → first frame | 5.07 s | includes Chaquopy's first-run asset extraction |
| `System.loadLibrary("fluidsynth")` | 8 to 590 ms | |
| `Python.start()` | 1.33 to 1.84 s (first launch 1.44 s) | on the dispatcher thread, not Main |
| music21 import | 0.70 to 1.34 s (one outlier 1.90 s) | desktop: ~0.28 s |
| Core import (services, audio, models) after music21 | 59 to 95 ms | |
| Player init (Synth + Oboe + SF2 load) | 136 to 390 ms (first launch 831 ms) | |
| SF2 asset → `filesDir` copy (first launch only) | 172 ms | 32 MB |
| Process start → highlights painted (`reportFullyDrawn`) | 4.7 / 4.8 / 6.3 s | Python start + imports + first detection |
| Detection, 125-line sample (133 chords) | 85 ms (debug build 106 ms) | desktop: 28 ms |
| Render (`SongRenderer`), same sample | 0.80 to 1.28 s; `compile_events` 2 to 4 ms | desktop: 0.32 s |
| Play → first note (sample song) | 1.41 s | the whole song renders first (core change 8) |
| Play → first note (short 32-bar song) | 0.13 to 0.23 s; 0.41 to 0.44 s with a concurrent render | |
| Tap → `noteon` (chord tap, through the bridge) | 1.2 to 4.7 ms (typically 1.5 ms) | Kotlin → Python ≈ 0.6 ms; plus audio output latency |
| Emulator audio output latency (AudioFlinger) | ~181 ms | shared-mode track, 4360-frame buffer, no low-latency path on the emulator |
| Peak RSS (`VmHWM`) | 292 to 319 MB | `dumpsys meminfo`: TOTAL RSS 294 to 302 MB, PSS 193 to 202 MB, native heap 96 MB |
| 16 KB emulator, 2 GB RAM | killed once by lmkd ~30 s after boot (foreground, 351 MB RSS) while the system was still starting; a retry ran fine | the app's RSS matters on 2 GB devices; consider `synth.dynamic-sample-loading` |

### Scheduling jitter

Measured inside the player: for each NOTE_ON the player pops, the `noteon`
wall time (CLOCK_MONOTONIC) is compared with the schedule. "Interval error" is
|actual gap − scheduled gap| between consecutive chords; "drift" is the last
chord's offset from the ideal grid anchored at the first chord. **This is
scheduling jitter only**; Oboe/mixer/DAC buffering is not included and needs
the audio-recording test on the phone.

| Run (60 s) | Notes | Interval error p50 / p90 / p99 / max (ms) | Drift after 60 s |
|---|---|---|---|
| Sample song (one chord per 2 s) | 31 | 1.6 / 6.1 / 6.9 / 6.9 | +80 ms |
| Dense, 4 chords/s | 241 | 0.34 / 0.41 / 0.87 / 6.4 | +90 ms |
| Dense + metronome | 241 | 0.34 / 0.43 / 1.36 / 5.0 | +95 ms |
| Dense + concurrent Python render | 225 | 26.3 / 27.6 / 49.1 / 77.1 | **+5.52 s** |
| Dense + metronome + concurrent render | 226 | 26.2 / 27.7 / 75.7 / 94.4 | **+5.65 s** |
| Dense + concurrent render, `sys.setswitchinterval(1 ms)` | 237 | 4.9 / 6.6 / 46.6 / 63.0 | +1.32 s |
| 16 KB emulator, dense, 20 s | 81 | 0.35 / 0.51 / 0.99 / 6.3 | +37 ms |

The metronome's per-tick `threading.Timer` costs nothing measurable. The
problem is the GIL. The player loop wakes several times per event (50 ms
sleep chunks, locks, `pop_event` timeouts), and each wake waits up to one
switch interval (5 ms) for the GIL when another Python thread is busy. That
adds ~26 ms per event, and because the loop re-anchors after every event, the
delay accumulates into seconds of drift. A shorter switch interval helps the
median but not the tail. Rendering the chord sheet, detecting while typing, or
session work during playback would all trigger this. **Sequencer fallback
recommended** (timing in FluidSynth's C sequencer, Python only enqueues
ahead), plus core change 6 regardless.

### After the Sequencer, desktop (M1b)

**Date:** 2026-10-29. **Host:** the Fedora 44 desktop (24 threads, load
average ~20 from other work), Python 3.14.8, FluidSynth 2.6.1.
**Method:** `tests/perf/measure_playback_timing.py`: 60 s of woodblock notes
at 4 per second through the real `NotePlayer`, on FluidSynth's `file` audio
driver (it renders in its own thread at real-time pace and writes raw PCM),
with onsets found in the rendered audio. So unlike the spike's table this
includes everything up to the synth output; Oboe/mixer/DAC latency is a
constant offset on top. "Old" is the pre-M1b player (`git show
78a6e98:src/audio/player.py`) driven the same way. The busy thread spins pure
Python for the whole run.

| Run (60 s, 240 notes) | Interval error p50 / p90 / p99 / max (ms) | Drift after 60 s | UI ping lateness p50 / p99 / max (ms) |
|---|---|---|---|
| Old sleep loop | 0.54 / 1.22 / 1.84 / 1.84 | +39 ms | (not measured) |
| Old sleep loop + busy Python thread | 9.77 / 11.38 / 11.38 / 11.38 | **+2.47 s** | (not measured) |
| Sequencer | 0.54 / 1.07 / 1.22 / 1.22 | −1.4 ms | 1 / 2 / 2 |
| Sequencer + busy Python thread | 0.54 / 1.07 / 1.22 / 1.22 | −1.4 ms | 10 / 20 / 86 |

The sequencer's remaining error is FluidSynth's render block (64 samples,
1.45 ms at 44.1 kHz) and its whole-millisecond tick; it doesn't change under
load. GIL contention now only delays the UI pings (chord highlighting,
status), by about a switch interval per wake. Still to do on the phone: the
recorded-output metronome test from the plan.

### Op buffer (optional item)

Not run on the device: the chord-sheet renderers are still in `src/ui/`, which
the APK excludes, and `clef_assets.py` imports PIL at module level. Both are
already planned for M1. Desktop proxy (Python 3.14, this host): the staff view
of the 133-chord sample is 1,246 ops, 12.8 ms to lay out and paint, and
1.7 ms to pack into a 22.5 KB buffer (struct-packed, string table). At 266
chords it's 2,482 ops, 24.9 ms + 3.5 ms, 44 KB. Expect ~3 to 4× that on the
emulator (the render ratio above). Marshalling one `bytes` object through
Chaquopy is cheap, so the packed-buffer design looks fine. The real packer
(format version 1, with tags, the marker lane, slots and gutter variants) is
measured under "Chord sheet op buffer": 25 to 76 KB and 1.4 to 3.5 ms per view
for this sample.

### Reproducibility

Method: snapshot the repo once, copy it to `/mnt/data_linux/Bin/android/repro/a/chord-notepad`
and `.../b/chord-notepad-other-name`, and build `:app:assembleRelease` in each
from clean (`--no-build-cache --no-configuration-cache`) with
`PYTHONHASHSEED=0 SOURCE_DATE_EPOCH=<fixed>` and `dependenciesInfo` off.
Compare with `tools/compare_apks.py` (entry-by-entry sha256, recursing into
Chaquopy's `.imy` zips). diffoscope wasn't needed.

1. First pass: only two entries differed.
   `requirements-common.imy!music21-…dist-info/direct_url.json` contained
   pip's record of the local wheel's **absolute path**, and
   `assets/chaquopy/build.json` differed only because it hashes that asset.
   **Fix:** install the trimmed wheel through `--find-links` plus a version
   pin, so pip records no direct URL (now in `app/build.gradle.kts`).
2. Second pass: **byte-identical APKs** (sha256 `521cef6e…`, same v2/v3
   signature, since the same debug key was used).
3. Cross-check: a normal build without `SOURCE_DATE_EPOCH` differs from those
   in every pip-installed `.pyc` (493 files): pip compiles them with
   timestamp-based headers carrying the build time. With `SOURCE_DATE_EPOCH`
   set, `py_compile` writes checked-hash pycs instead. So `SOURCE_DATE_EPOCH`
   is **required**; `local.env` now sets it from the last commit's time.
   (PYTHONHASHSEED=0 was set in both passes; not shown to be required.)

Not covered yet, and needed before claiming reproducibility to F-Droid: a
different machine and user, and a different `python3.14` micro version as
buildPython (pyc bytecode). The natives were upstream prebuilts here; AGP
strips them (`stripReleaseDebugSymbols`), which was deterministic. **Update
(M6 groundwork):** the pip downloads are now hash-pinned and offline, the
natives build from source, and the check still gives byte-identical APKs; see
"Reproducibility with source-built natives" above.

### Needs the phone

- Audible playback; **real output latency** (tap → sound) and the 2-minute
  metronome **recorded from the audio output** (p50/p99, with and without a
  concurrent chord-sheet render).
- Cold start, `Python.start()` and music21 import on real ARM hardware (the
  emulator numbers are inflated by host load).
- Whether Oboe gets the low-latency (MMAP/exclusive) path with
  `performance-mode=LowLatency`.
- The tablet AVD (`cn_tablet`) is created but was not exercised in M2.
- Peak RSS on the actual device, and lmkd behaviour on a 16 KB device if
  available.
- Editor items from the plan that a scripted spike can't cover: IME, tap →
  offset, whole-text replace as one undo step, paste hook, read-only mode,
  scrolling a 300-line song while typing. The highlighting itself is proven:
  Python spans render through `OutputTransformation` + `addStyle` on a
  `TextFieldState` field.

### Fade-in at the start of playback (HTC 10, Android 8.0; 2026-10-29)

Reported: the first notes after Play fade in instead of starting at full
volume.

- **The synth output is clean.** The real `PlaybackService` + `NotePlayer`
  path rendered through FluidSynth's `file` driver (44.1 and 48 kHz, cold
  and warmed-up synth) gives the first chord the same RMS envelope and peak
  as later chords that also follow silence (within 0.2 dB, 50 ms windows).
  Nothing in our code ramps (no CC7/CC11 ramp, gain is set once, the click
  channel is separate).
- **The stream isn't (re)started at Play.** AudioFlinger's thread log shows
  our track added when the app comes to the foreground (`resume_audio`, or
  at session start) and removed when it leaves, so Play writes into a stream
  that has been running silence.
- **On this phone our stream is the one that goes through Dolby.** Oboe
  uses OpenSL ES below API 27; `performance-mode=LowLatency` asks for a FAST
  track, which AudioFlinger denied ("AUDIO_OUTPUT_FLAG_FAST denied by
  server; frameCount 1924"), but the track still lands on the primary output
  (I/O 13, `PRIMARY|FAST`). That output carries a global Dolby DAP effect
  (`dumpsys media.audio_policy`: "Effect 11, I/O 13, Session 0, DAP,
  Enabled"; `vendor.audio.dolby.ds2.enabled=1`). Ordinary music goes to the
  deep-buffer output (`audio.deep_buffer.media=true`, I/O 21), which has no
  effect chain. A leveler that ramps its gain up after digital silence fits
  the report; I couldn't listen or capture the device's output to confirm.
- **Tried and reverted:** asking Oboe for no performance mode below API 27
  (an ordinary deep-buffer music track) did not remove the fade on the
  HTC 10, so it was reverted; the stream is `LowLatency` everywhere again.
  The cause is still open (next suspects: the device's speaker amplifier or
  another vendor stage handling silence). Tibi chose to leave it as is.

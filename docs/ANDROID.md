# Android build

Status: **M2 toolchain spike** (see `docs/ANDROID_PORT_PLAN.md`). The Gradle
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
  app/build.gradle.kts              app module: Chaquopy, FluidSynth, SoundFont
  app/src/main/kotlin/io/github/chibicitiberiu/chordnotepad/
    ChordNotepadApp.kt, MainActivity.kt
    spike/                          M2 test screen (throwaway)
  app/src/main/python/chordnotepad_android/
    android_shim.py                 runtime patches standing in for core changes
    spike.py                        M2 test glue (throwaway)
  tools/strip_music21.py            builds the data-trimmed music21 wheel
  tools/check_16k.py                16 KB page-size check for an APK
```

The Python core is not copied: Chaquopy reads `../../src` directly, minus
`ui/**` and the desktop-only modules (`main.py`, `application.py`,
`utils/display_scaling.py`, `utils/file_dialogs.py`, `utils/icon_loader.py`,
`utils/ui_helpers.py`; the same list as `tests/test_core_import_guard.py`).
The SoundFont (`resources/soundfont/GeneralUser-GS.sf2`) and the spike's sample
song (`examples/02_american_complete.txt`) are copied into the APK's assets by
Gradle tasks, not duplicated in git.

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
| NDK | 27.3.13750724 | only for `libc++_shared.so` (the FluidSynth prebuilt needs it) |
| FluidSynth | 2.6.0 upstream Android prebuilt | dev only; M6 builds natives from source |
| ABIs | arm64-v8a, x86_64 | `-PcnAbis=x86_64` builds one ABI |

Python packages (all `--no-deps`, pinned in `app/build.gradle.kts`):
music21 10.3.0 (trimmed, see below), pychord 1.4.0, mido 1.3.3,
pyfluidsynth 1.4.0, plus what music21 really imports: chardet 6.0.0.post1
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
  "build-tools;36.1.0" "ndk;27.3.13750724" \
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

The FluidSynth prebuilt zip and the upstream music21 wheel are downloaded on
first build into `$CHORD_NOTEPAD_ANDROID_CACHE` and checked against pinned
sha256 hashes.

## Build, install, run

```bash
source android/local.env
cd android
nice -n 10 ./gradlew :app:assembleDebug
nice -n 10 ./gradlew :app:assembleRelease               # debug-signed for now (real keys: M6)
nice -n 10 ./gradlew :app:assembleRelease -PcnMusic21=full   # untrimmed music21, for size comparison
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
$ANDROID_HOME/build-tools/36.1.0/zipalign -c -P 16 -v 4 $OUT/release/app-release.apk
python3 tools/compare_apks.py a.apk b.apk          # reproducibility diff
```

## Required core changes (found by the spike)

The spike runs the core unmodified; `chordnotepad_android/android_shim.py`
patches around these at runtime. Each should become a real core change, after
which its shim goes away.

1. **`audio/fluidsynth_import.py`: accept a bare soname.** On Android the
   native libraries stay inside the APK, so there is no file path; only
   `libfluidsynth.so` (resolved by the linker from the app's namespace) works.
   CPython 3.14's `ctypes.util.find_library` on Android only looks in
   `/system/lib64`, and the `CHORD_NOTEPAD_LIBFLUIDSYNTH` override requires an
   existing file. Fix: if the value has no `/`, skip the `exists` check; on
   `sys.platform == "android"` default to `libfluidsynth.so`.
2. **`audio/player.py`: Android driver list.** `sys.platform` is `"android"`,
   which falls into the Linux branch (`pulseaudio`, `alsa`, `oss`). It must be
   `["oboe", "opensles"]`. (Also log the driver that actually started; today it
   logs the requested one.)
3. **NULL audio driver check** (already planned in M1b). pyfluidsynth's
   `Synth.start()` returns `FLUID_OK` even when `new_fluid_audio_driver()`
   returned NULL, so the fallback and the "audio unavailable" path never run.
   Check `synth.audio_driver` after `start()`.
4. **Synth settings from the host.** `NotePlayer` creates `fluidsynth.Synth()`
   at pyfluidsynth's default 44.1 kHz; the device's native rate (48 kHz on the
   emulator and most phones) avoids a resampler. The host should pass the
   sample rate and extra settings (`audio.oboe.performance-mode=LowLatency`,
   later `synth.dynamic-sample-loading`).
5. **App data directories from the host.** `AppDataService` falls into the
   Linux/XDG branch on Android; the shim points `XDG_*` at `filesDir`. The
   planned `utils/paths.py` (M1 step 4) should take the directory from the host.
6. **Playback loop re-anchors on every event, so lateness accumulates.**
   After each event the loop sets `_wall_anchor = time.time()`, so each event's
   lateness shifts every later event. Measured drift: +80 to +90 ms over 60 s
   when idle, **+5.65 s over 60 s** with a concurrent Python render. Schedule
   against the song start (re-anchor only on pause and multiplier changes) and
   use a monotonic clock (`perf_counter`, already planned in M1b).
7. **GIL contention during playback** (see measurements): any Python work on
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
   the device (the APK excludes `ui/**`).

Build-side notes, not core changes:
- `charset-normalizer` 3.5.2 resolves to an Android binary wheel
  (`md.cpython-314-*.so`); for an F-Droid build, pin its pure-Python wheel.
- Release builds are not minified yet; R8 would cut the 7.7 MB of dex
  substantially (Chaquopy ships its own keep rules).
- The SF2 is 29 MB of every APK. An SF3 (Ogg-compressed) GeneralUser GS would
  shrink it severalfold; FluidSynth 2.6 with libsndfile/vorbis loads SF3.
  Check the licence before converting.

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
| Scheduling jitter OK? | **Go only while Python is idle; No-go under concurrent Python work.** Idle: interval error p99 0.9 to 1.4 ms. With one other Python thread busy (a render loop as a stand-in for a chord-sheet render): p50 26 ms, p99 49 to 76 ms, drift +5.5 s per minute. See below. Recommendation: move to pyfluidsynth's `Sequencer` (sample-clock timing in C) as planned, and fix the drift (core change 6). |
| APK size? | **Acceptable, with easy wins left.** 91.0 MB universal, 69.8 MB arm64-v8a only (trimmed music21). The SF2 is 29 MB of that; R8 and an SF3 would cut a further ~25 to 30 MB. |
| 16 KB pages? | **Go.** All 160 ELF files (APK `lib/` plus Chaquopy's nested extension modules) have 16 KB `PT_LOAD` alignment; `zipalign -c -P 16` passes; the app runs and plays on the `google_apis_ps16k` image (`getconf PAGESIZE` = 16384). |
| Reproducible? | **Yes, on one machine.** Two clean release builds from different checkout paths are byte-identical, signature included, after two fixes (see below). |

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

### Op buffer (optional item)

Not run on the device: the chord-sheet renderers are still in `src/ui/`, which
the APK excludes, and `clef_assets.py` imports PIL at module level. Both are
already planned for M1. Desktop proxy (Python 3.14, this host): the staff view
of the 133-chord sample is 1,246 ops, 12.8 ms to lay out and paint, and
1.7 ms to pack into a 22.5 KB buffer (struct-packed, string table). At 266
chords it's 2,482 ops, 24.9 ms + 3.5 ms, 44 KB. Expect ~3 to 4× that on the
emulator (the render ratio above). Marshalling one `bytes` object through
Chaquopy is cheap, so the packed-buffer design looks fine.

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
different machine and user, a different `python3.14` micro version as
buildPython (pyc bytecode), and Chaquopy/pip downloads that aren't hash-pinned
yet (the M6 wheelhouse). The natives are upstream prebuilts and the NDK's
`libc++_shared.so`; AGP strips them (`stripReleaseDebugSymbols`), which was
deterministic here.

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

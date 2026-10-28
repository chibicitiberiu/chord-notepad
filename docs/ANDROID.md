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
    ChordNotepadApp.kt, MainActivity.kt
    spike/                          M2 test screen (throwaway)
  app/src/main/python/chordnotepad_android/
    android_shim.py                 runtime patches standing in for core changes
    spike.py                        M2 test glue (throwaway)
  native/                           FluidSynth + dependencies as pinned git submodules
  native/build.sh                   cross-compiles them (mirrors upstream's Android CI)
  tools/strip_music21.py            builds the data-trimmed music21 wheel
  tools/build_wheelhouse.py         fills/checks the offline wheelhouse, refreshes pins
  tools/check_16k.py                16 KB page-size check for an APK
  tools/compare_apks.py             entry-by-entry APK diff (reproducibility)
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
| NDK | 27.3.13750724 | compiles the natives (`android/native/build.sh`); `libc++_shared.so` comes from it too |
| CMake | 3.31.6 (SDK package) | used by `build.sh`, with the Ninja it bundles; not the host's CMake 4 |
| FluidSynth | 2.6.1, built from source | default; `-PcnNatives=prebuilt` uses upstream's 2.6.0 Android zip instead (sha256-pinned) |
| ABIs | arm64-v8a, x86_64 | `-PcnAbis=x86_64` builds one ABI |

Python packages (all `--no-deps`, pinned with hashes in `android/requirements.txt`,
installed offline from the wheelhouse; see below):
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
nice -n 10 ./gradlew :app:assembleRelease               # debug-signed for now (real keys: M6)
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
$ANDROID_HOME/build-tools/36.1.0/zipalign -c -P 16 -v 4 $OUT/release/app-release.apk
python3 tools/compare_apks.py a.apk b.apk          # reproducibility diff
```

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
5. **App data directories from the host.** `AppDataService` falls into the
   Linux/XDG branch on Android; the shim points `XDG_*` at `filesDir`. The
   planned `utils/paths.py` (M1 step 4) should take the directory from the host.
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
   the device (the APK excludes `ui/**`).

Build-side notes, not core changes:
- `charset-normalizer` 3.5.2 resolved to an Android binary wheel
  (`md.cpython-314-*.so`) from chaquo.com's index. **Done (M6 groundwork):**
  the wheelhouse pins its pure-Python wheel.
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

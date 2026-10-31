# Backlog

The one prioritised list of open work, most urgent first. Delete a line when
it's done (git history keeps it); release mechanics live in `docs/RELEASE.md`.

## Before the next release (v0.5.0)

- Bump `VERSION` to 0.5.0 and `versionCode` to 5000 (`android/app/build.gradle.kts`) in one commit; `tests/test_android_version.py` checks them.
- Tibi: approve the AGPL section 7 wording as shipped, and edit the support-prompt text (`android/.../ui/support/`).
- GitHub: create or confirm the `android-release` environment and its four secrets; tag `v0.5.0` and check that `android-release` and `attach-android` run (they never have).
- Play Console: identity verification (long lead), listing, payments profile, the `supporter` product, license testers (including pending and refund), IARC, Data safety, then the 12-tester, 14-day closed test (`docs/RELEASE.md`, "Google Play (first time)", "Developer verification").
- Microsoft Store: upload the 0.5.0 MSIX; check that every listing language has the AGPL notice and source URL (`docs/RELEASE.md`, "Licence compliance").
- Real phone: audible timing and tap-to-sound latency, the recorded-output metronome test, audio focus, SAF providers, soft keyboard and IME, Open with `.txt`, cold start and RSS, whether the stream should close in the background, a 16 KB-page device if available.
- Desktop manual checks of the session migration and the sequencer/audio-driver change on Flatpak, Snap, Windows and macOS: open a song with directives, type, play/loop/shift-play, transpose and undo, chord sheet and voicing, settings, close with unsaved changes.
- Decide F-Droid before tagging (see "Needs a decision").

## Next

- CI credentials: delete the repo-level `SNAPCRAFT_STORE_CREDENTIALS` once a dispatch shows `snapcraft upload` succeeding with the `release` environment copy (the environment policy and the `main`/`v*` rulesets are in place).
- CI signing isolation: Windows signing in its own job that alone holds `id-token: write`; Android signing in a minimal job after an unsigned build; Gradle dependency verification.
- Local signing (`docs/RELEASE.md`, "Signing locally"): read passwords in a subshell, accept them from the environment only (not `-P`), fail when `cnSigning=upload|foss` meets the configuration cache.
- Local MSIX test recipe (`docs/RELEASE.md`): import only the `.cer`, not the PFX with its private key, and clean up afterwards, as `smoke_test.ps1` does.
- Desktop file I/O: atomic save (temp file and `os.replace`) and a 5 MB cap, as on Android (`src/services/file_service.py:38,73`).
- Flatpak: serve the guide from the app's cache dir through the OpenURI portal and drop `--share=network`.
- Fast tests: Hypothesis `dev`/`ci` profiles in `tests/conftest.py` (three fuzz tests in `test_chord_pickers.py` take 99 of 184 s), patch `_create_sequencer` in `test_user_facing_errors.py::test_no_audio_driver_raises` (9.4 s), `make test-fast`, pytest-xdist with `-n 4`.
- Replace sleep-based timing tests (`test_playback_service.py`, `test_playback_stop.py`, `test_session_threaded_host.py`) with `ManualHost` or event waits.
- ruff (`check --select F,E722,B`) in dev-packages, CI and pre-commit; fix the bare `except:` in `src/chord/helper.py` and `src/application.py:373`, the duplicate `set_instrument` in `playback_service.py`, and the other pyflakes findings.
- Safe Makefile: `.DEFAULT_GOAL := help` with a `help` target (bare `make` launches the GUI today), and `make check` = lint + test + docs-check.
- pytest 7.4 to 8.x (7.4 predates Python 3.14).
- Desktop output dispatch: `MainWindow._on_session_output` (`src/ui/main_window.py:338-381`) drops unknown types silently. A type→handler dict, an explicit "ignored on desktop" set and a test that covers every bridge output.
- Limits in one place: BPM, speed, beats and transpose ranges are repeated in `main_window_viewmodel.py:586,613`, `ui/dialogs/options_dialog.py:21-22` and Kotlin (`SheetRoute.kt`, `ToolForms.kt`, `ScrubberMath.kt`, `SettingsDraft.kt`). Use `constants.py` and publish them over the bridge.
- Bridge contract test (`BridgeSchemaContractTest.kt`): fail instead of `assumeTrue` when the schema is missing; compare types, nullability and command argument shapes.
- A stress test for `AppSession.chord_sheet_buffer` packing on a second thread while the session re-feeds (renderers are assumed pure, unchecked).
- `tests/test_android_requirements.py`: compare versions with `Pipfile.lock`, not just names (allow-list chardet).
- Kotlin comments: the stale `TODO(step 14)` in `bridge/SessionOutput.kt:11`, the misplaced KDoc in `SessionRepository.kt` (~`:136`).
- `{}` (empty braces) should be marked invalid, not ignored.
- Android: the capo icon needs a better drawing.
- CONTRIBUTING.md: a Development section (setup, `make help`, `make check`, the core/desktop rule, `docs/ANDROID.md`).
- `.gitignore` backstop for `*.p12`, `*.jks`, `*.keystore`, `*.pem`, `*.env`.

## Later

- Desktop UI redesign on Android's model (2026-10-31 review, outside the repo), once the four questions under "Needs a decision" are answered:
  - first, what the session already offers: a playhead marker, ⏮ instead of ⏹, a song-defaults popover with Write into song, File › Rename, voicing and instrument buttons, startup through `StartupState`;
  - Edit/Play modes: `ModeController.kt` and a `PlayerState` move into the session; header, ribbon, player, Play-mode keys, Tools merged into Edit; help and screenshots;
  - theme and feedback: tokens shared with `AppTheme.kt`, System/Light/Dark, rasterised MDI icons, a session `Notice` event, inline validation in the Insert dialogs;
  - layout: chord sheet beside or below, per-mode visibility, settings summaries, an empty-song hint, Help › Open Example. Stay on Tk; spike PySide6 only if theming or DPI still hurt.
- Split `AppSession` (`src/session/session.py`, 2,548 lines) into per-area components, with one observer-registration helper that shutdown mirrors.
- Then move value ownership (text, document, toolbar, playback) from `MainWindowViewModel` into the session, one value at a time.
- Desktop Settings and Chord Identifier onto the session paths (`SettingsEdit`, `identifier_*`); `ConfigService` emits changed keys instead of the per-command re-read.
- Repo layout: all sources under `src/` (Tibi, 2026-10-31), split by layer rather than by store (e.g. `src/core/`, `src/desktop/`, with the Android app's sources there too if Gradle allows), desktop-only `utils/` modules into the desktop tree, the spec and `hooks/` into `packaging/pyinstaller/`. To be planned as its own step, after the reviews; one change at a time.
- Build consolidation: `scripts/make_icons.py`, `scripts/gen_build_info.py` (untracked output), `scripts/bump_version.py` shared by Make and CI; a composite setup action and venv cache; `build.yml` split into `ci.yml`, `release.yml` and reusable workflows; drop the tag-push release path and RELEASE.md's "Quick Release Guide".
- pipenv to `pyproject.toml` + uv, generating `android/docs-requirements.txt` from a dependency group.
- Type and lint more: mypy on `session` and `models`, ktlint, hints and docstrings in `ui/chord_identifier.py`, `ui/chord_sheet/panel.py`, `voicings_page.py`, `insert_directives.py`.
- Compose hygiene: `collectAsStateWithLifecycle`, the rename flow out of `SongScreen.kt` into a controller, no per-gesture `Log.i` in `ChordSheetPane.kt`.
- Android UI tests (`androidTest`, Compose) for `SongScreen`, `ChordSheetPane` and `ChordEditor`.
- Test cleanup: shared `parser()` fixture instead of five copies, no `sys.path.insert` in tests, mock-plumbing tests asserting on `EventRecorder` states.
- Small code debt: retained parameters in `audio/chord_picker.py:93-96` and `playback_service.py:385,411`, `RuntimeError` → `AudioInitializationError` in `audio/sequencer.py`, wake the Tk drain on `post` instead of the 100 ms poll.
- Song structure: reusable parts (`{part: x}` … `{endpart}` with `{call: x}`, or `{play: label}`; no `goto`) and label-less `{loop: 3}` … `{endloop}`, across parser, renderer, chord sheet, hints, help and Android.
- Faster first note: stream the first bars or reuse the chord sheet's `RenderedSong` (1.4 s on the emulator); measure on the phone first.
- APK size: R8, an SF3 GeneralUser GS (licence check), libsndfile and requests/chardet/urllib3 dropped if music21 allows; measure which chords only music21 resolves before keeping it.
- Export to WAV/MP3 through FluidSynth's `file` driver.
- Playback ideas: arpeggio and strum patterns, `{pattern: …}` per section, `{v: 80}` volume.
- Desktop ideas: audio device selection, PDF/image export of the chord sheet, multiple tabs, MIDI out.
- iOS/iPadOS port on the same core. Licensing plan (decided 2026-10-31):
  - ship FluidSynth under LGPL-2.1 as a dynamic framework with its source in the release, relying on upstream's Licensing FAQ ("iOS and the App Store": nine copyright holders, including Peter Hanappe and Tom Moebert, agreed not to object if changes stay LGPL and the app can be relinked; not a guarantee);
  - build it without libsndfile (the app plays `.sf2` only);
  - pyFluidSynth (LGPL) isn't covered: ask its maintainer or replace it with a small ctypes binding;
  - leave chardet out, as on the desktop;
  - fallback if a FluidSynth copyright holder objects: Apple's AVAudioUnitSampler (system library, loads the same SF2) or TinySoundFont (MIT);
  - App Store Connect: AGPL notice and source URL in the listing, no custom EULA.
- One `chordnotepad.` package namespace, only if a top-level name collides or the core should be installable.

## Needs a decision

- Desktop redesign: full Edit/Play modes, or editing while paused (the session freezes the text while paused today)?
- Desktop redesign: Ctrl+click to audition in Edit, or keep plain click playing?
- Desktop redesign: extend Android's dark-editor colours to the desktop, or keep the light editor inside dark chrome?
- Desktop redesign: the playhead marker drawn over the text (a 2 px overlay frame), given the editor-typography rule.
- F-Droid: submit or not (AI policy in flux). If yes: fastlane metadata, the recipe (`gradle: [foss]`), AI disclosure, the GeneralUser GS licence question, and whether the logo reserved by `ARTWORK-TERMS.txt` counts as a non-free asset.
- Metronome count-in (one bar before playback when the metronome is on)?
- Android background playback: a foreground media service, or keep pausing (documented limitation)?
- Desktop Default key = None: the toolbar shows "C" and there's no None option (Android shows None). Fix now or fold into the redesign?
- `{bpm: reset}` before the first chord resets to the toolbar tempo: intended? Then document it and close.
- Typed `{time}` accepts 1-16 beats and units 1/2/4/8/16 only (`{time: 17/8}` is red): intended? Then say so in `help/directives.rst`.

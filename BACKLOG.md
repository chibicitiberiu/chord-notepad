# Backlog

The one prioritised list of open work, most urgent first. Delete a line when
it's done (git history keeps it); release mechanics live in `docs/RELEASE.md`.

## Before the next release

- Play Console: identity verification (long lead), listing, payments profile, the `supporter` product, license testers (including pending and refund), IARC, Data safety, then the 12-tester, 14-day closed test (`docs/RELEASE.md`, "Google Play (first time)", "Developer verification").
- Microsoft Store: upload the 0.5.0 MSIX; check that every listing language has the AGPL notice and source URL (`docs/RELEASE.md`, "Licence compliance").
- Real phone: audible timing and tap-to-sound latency, the recorded-output metronome test, audio focus, SAF providers, soft keyboard and IME, Open with `.txt`, cold start and RSS, whether the stream should close in the background, a 16 KB-page device if available.
- Desktop manual checks of the session migration and the sequencer/audio-driver change on Flatpak, Snap, Windows and macOS: open a song with directives, type, play/loop/shift-play, transpose and undo, chord sheet and voicing, settings, close with unsaved changes.
- Linux ARM64 (new CI builds): after the first CI run, check the three arm64 artifacts on real ARM hardware (binary starts and plays, Flatpak installs, snap installs from the store), and that `snapcraft pack` built only arm64 on the arm runner.
- Decide F-Droid before tagging (see "Needs a decision").
- ChromeOS: after uploading the next AAB (touchscreen now optional, `check_manifest.py` enforces it), check Play Console > Reach and devices > Device catalog for Chromebooks. Mouse, keyboard and freeform window resizing were tried on the tablet emulator only, not on real ChromeOS.

## Next

- Consider `groups` in `.github/dependabot.yml` for one weekly PR (the bumps in a3c910b signed fine on v0.5.1).
- Cache the Ubuntu source packages the release's third-party source bundle downloads: "Build source bundles" takes 50-75 minutes of every release and nightly.
- macOS: try both dmgs on a real Mac (Open Anyway on first launch, sound, the Intel one on macOS 14.4); CI only smoke-tests them.
- CI signing isolation: Windows signing in its own job that alone holds `id-token: write`; Android signing in a minimal job after an unsigned build; Gradle dependency verification.
- Local signing (`docs/RELEASE.md`, "Signing locally"): read passwords in a subshell, accept them from the environment only (not `-P`), fail when `cnSigning=upload|foss` meets the configuration cache.
- Local MSIX test recipe (`docs/RELEASE.md`): import only the `.cer`, not the PFX with its private key, and clean up afterwards, as `smoke_test.ps1` does.
- Desktop file I/O: atomic save (temp file and `os.replace`) and a 5 MB cap, as on Android (`core/chordnotepad/services/file_service.py:38,73`).
- Flatpak: serve the guide from the app's cache dir through the OpenURI portal and drop `--share=network`.
- Fast tests: Hypothesis `dev`/`ci` profiles in `tests/conftest.py` (three fuzz tests in `test_chord_pickers.py` take 99 of 184 s), patch `_create_sequencer` in `test_user_facing_errors.py::test_no_audio_driver_raises` (9.4 s), `make test-fast`, pytest-xdist with `-n 4`.
- Replace sleep-based timing tests (`test_playback_service.py`, `test_playback_stop.py`, `test_session_threaded_host.py`) with `ManualHost` or event waits.
- ruff (`check --select F,E722,B`) in dev-packages, CI and pre-commit; fix the bare `except:` in `core/chordnotepad/chord/helper.py`, the duplicate `set_instrument` in `playback_service.py`, and the other pyflakes findings.
- Safe Makefile: `.DEFAULT_GOAL := help` with a `help` target (bare `make` launches the GUI today), and `make check` = lint + test + docs-check.
- pytest 7.4 to 8.x (7.4 predates Python 3.14).
- Limits in one place: BPM, speed, beats and transpose ranges are repeated in `main_window_viewmodel.py:586,613` and Kotlin (`SheetRoute.kt`, `ToolForms.kt`, `ScrubberMath.kt`, `SettingsDraft.kt`). Use `constants.py` and publish them over the bridge.
- Bridge contract test (`BridgeSchemaContractTest.kt`): fail instead of `assumeTrue` when the schema is missing; compare types, nullability and command argument shapes.
- A stress test for `AppSession.chord_sheet_buffer` packing on a second thread while the session re-feeds (renderers are assumed pure, unchecked).
- `tests/test_android_requirements.py`: compare versions with `Pipfile.lock`, not just names (allow-list chardet).
- Kotlin comments: the stale `TODO(step 14)` in `bridge/SessionOutput.kt:11`, the misplaced KDoc in `SessionRepository.kt` (~`:136`).
- `{}` (empty braces) should be marked invalid, not ignored.
- Android: the capo icon needs a better drawing.
- Android lacks these desktop features (audit 2026-11-24; the session commands exist, Kotlin never sends them; none is documented as a deliberate difference):
  - Find and replace, find next/previous, go to line, and the same-word tint on a selected word: the desktop's `find_bar.py` / `FindBar.qml` with `replace_match` and `replace_all` (`core/chordnotepad/session/text_ops.py`); the iOS slice ports the same find bar.
  - Line editing: select, duplicate, delete and move lines, toggle comment, indent/unindent (`duplicate_lines`, `delete_lines`, `move_lines`, `toggle_comment`, `indent_lines`; desktop `qml/app/EditorPane.qml:227-267`). iOS gets some as keyboard shortcuts.
  - The ▾ value picker on a directive value and tap tempo (`replace_directive_value`, `tap_tempo`; desktop `value_picker.py`). Android edits values only through ＋ Insert and the Song defaults sheet.
  - A rolled (strummed) chord on a tap: the desktop's Shift+click. `tap_chord_at` and `audition` take `rolled`, Android never sends it (only the identifier rolls).
  - Music volume, mute and metronome volume (`set_volume`, `set_muted`, `step_volume`, `set_metronome_volume`; desktop `player_bar.py:506-531`).
  - A Light / Dark / System theme setting (`set_ui_theme`); Android always follows the system (`ui/theme/AppTheme.kt:170`).
  - Hardware-keyboard shortcuts beyond files, zoom, help and undo (`ui/Shortcuts.kt`): play/pause and stop, metronome, speed, transpose, Edit/Play, the chord sheet and its views, Settings, find.
  - Strings: "Resize the chord sheet" and the voicing editor's "Move up", "Move down" and "Duplicate" labels are hard-coded in Kotlin instead of string resources (found by the iOS accessibility pass).
  - To check: whether Edit mode shows a directive's hint as the cursor enters it, as the desktop's status bar does (Android explains a red or faded directive on a long press in Play).
- CONTRIBUTING.md: a Development section (setup, `make help`, `make check`, the core/desktop rule, `docs/ANDROID.md`).
- `.gitignore` backstop for `*.p12`, `*.jks`, `*.keystore`, `*.pem`, `*.env`.

## Qt desktop

- Tk leftovers in the core, now that the window is gone: the `DESKTOP` platform texts and `tests/fixtures/quick_start_desktop.json` (`session/platform.py`, `session/quick_start.py`); the interim live paths `chord_sheet_model`, `settings_model`, `chord_identifier_model`, `has_chord_sheet`, `set_window_geometry` and `report_audio_failure` on `AppSession`; the Tk keys in `models/window_geometry.py` and the config; the Tk-only viewmodels; the Tk Quick Start picture `resources/quickstart/chord_sheet.png` (with the `DESKTOP` pages); the guard lists in `tests/test_core_import_guard.py` once nothing needs them. `build_info.py` lives in `chordnotepad_desktop`.
- Drag and drop from the Directives palette and the chord identifier: the drop caret and the word snap.
- The duration tiles and `set_chord_duration`, keeping columns aligned.
- Palette keyboard polish.
- Redraw the rail and tile icons crisp at 125% (and at 2x: offscreen at `QT_SCALE_FACTOR=2` they come out cropped, which is why the store screenshots are drawn at 1x).
- Accessibility names for the Qt controls.
- Redo the desktop screenshots (`packaging/tools/qt_help_screenshots.py`) after any window change.
- Printing (Tibi, 2026-11-16: a future update). Not wanted: a .txt file association, single-instance mode (people open songs side by side).

## Later

- Split `AppSession` (`core/chordnotepad/session/session.py`, 2,548 lines) into per-area components, with one observer-registration helper that shutdown mirrors.
- Then move value ownership (text, document, toolbar, playback) from `MainWindowViewModel` into the session, one value at a time.
- Repo layout, the rest: the spec and `hooks/` into `packaging/pyinstaller/` (the code itself is split by layer since the move to `core/chordnotepad/` and `desktop/chordnotepad_desktop/`).
- Build consolidation: `scripts/make_icons.py`, `scripts/gen_build_info.py` (untracked output), `scripts/bump_version.py` shared by Make and CI; a composite setup action and venv cache; `build.yml` split into `ci.yml`, `release.yml` and reusable workflows; drop the tag-push release path and RELEASE.md's "Quick Release Guide".
- pipenv to `pyproject.toml` + uv, generating `android/docs-requirements.txt` from a dependency group.
- Type and lint more: mypy on `session` and `models`, ktlint, hints and docstrings in the Qt models.
- Compose hygiene: `collectAsStateWithLifecycle`, the rename flow out of `SongScreen.kt` into a controller, no per-gesture `Log.i` in `ChordSheetPane.kt`.
- Android UI tests (`androidTest`, Compose) for `SongScreen`, `ChordSheetPane` and `ChordEditor`.
- Test cleanup: shared `parser()` fixture instead of five copies, no `sys.path.insert` in tests, mock-plumbing tests asserting on `EventRecorder` states.
- Small code debt: retained parameters in `audio/chord_picker.py:93-96` and `playback_service.py:385,411`, `RuntimeError` → `AudioInitializationError` in `audio/sequencer.py`.
- Song structure: reusable parts (`{part: x}` … `{endpart}` with `{call: x}`, or `{play: label}`; no `goto`) and label-less `{loop: 3}` … `{endloop}`, across parser, renderer, chord sheet, hints, help and Android.
- Faster first note: stream the first bars or reuse the chord sheet's `RenderedSong` (1.4 s on the emulator); measure on the phone first.
- APK size: an SF3 GeneralUser GS (licence check), libsndfile and requests/chardet/urllib3 dropped if music21 allows; measure which chords only music21 resolves before keeping it.
- Export to WAV/MP3 through FluidSynth's `file` driver.
- Staff view notation (Tibi, 2026-11-03; deferred until after the first official release, too much risk before it): real note values from chord lengths (stems, flags, beams, dots, ties, NC as a sized rest, time signatures, true bar lines in every allowed meter), neat triplets snapped in the renderer (lazy `*0.3 *0.6` too), anything off a 16th grid rounded with a ≈ mark, then C clefs, a clef and staff number per voice, and transposing instruments. Reviewed plan: ~/Documents/chord-notepad/staff-plan.md (rhythm about 2–2.5 weeks, clefs about 1.5 weeks).
- Playback ideas: arpeggio and strum patterns, `{pattern: …}` per section, `{v: 80}` volume.
- Desktop ideas: audio device selection, PDF/image export of the chord sheet, multiple tabs, MIDI out.
- iOS/iPadOS port: SwiftUI front end over the same core and JSON session bridge, like Android; plan and status in docs/IOS.md. Still to do after the Swift kit and the CI build:
  - SwiftUI screens ported from `android/.../ui/`, each with its catalog fixtures. Done (2026-11-24): the chord sheet, the song editor with the Edit ribbon's Undo, Redo, AB/Do and Convert, and the main screen (the app bar, Edit / Play, Play mode's frozen text with the marker, taps, scrub and the directive explanation, the player, the side-by-side layout, rename, the ☰ menu with Diagnostics; docs/IOS.md "The main screen"), and file handling (Open, New, Save, Save As with the export picker, Recent through security-scoped bookmarks, Export MIDI and audio, Examples, the unsaved-changes question, songs opened from Files; docs/IOS.md "Files", with its device checklist), and the player's sheets with the ribbon's tools (Voicing, Instrument, Playback speed with Manual…, Playback settings with Write into song, Insert and its six dialogs checked by the session, Transpose, Suggest Capo, the chord identifier; docs/IOS.md "The player's sheets and the ribbon's tools", with its device checklist), and Settings with About and the licences (General, Playback, the Voicings editor with the session's schema and its refusals, Edit voicings… from the Voicing sheet, About with the FOSS flavour's support link, the iOS app's own licence list `ios/Licenses/components.json` with its texts copied by a build phase; docs/IOS.md "Settings, About and Licences", with its device checklist). And the user guide (the Sphinx guide's iOS edition, `-t ios`, in a WKWebView limited to the bundled guide, its own screenshots in help/images/ios), the Quick Start tour (☰ and at a direct launch, through `app_started`) and Export PDF (the session's `PaintPdfRequest` painted with UIGraphicsPDFRenderer, then the export picker); docs/IOS.md "The user guide, Quick Start and Export PDF", with its device checklist. And the editor's remaining features (Find and Replace in a bar under the text, ported from the Qt desktop since Android has none, matching exactly as the core's `text_ops.find_all`; the font settings checked in the editor; the pinch on the text; the keyboard shortcuts as menu commands; the landscape column's width in UserDefaults; docs/IOS.md "Find, the font, the pinch and the keys", with its device checklist). And the platform glue (Android's `lifecycle/` audio policy: interruptions, route changes, the media services reset and the background through `pause`, `app_background` and `app_foreground`; a song takes the audio session from other apps' music while it plays; no background playback, as on Android; the layouts at iPad Split View widths; the icon buttons' VoiceOver labels in Android's words, checked by a walk of every catalog screen; the iOS export status "MIDI ready to save: x.mid"; docs/IOS.md "Audio, multitasking and accessibility", with its device checklist).
  - Platform glue still to do: the share sheet (if wanted besides the export picker); StoreKit 2 (with monetization).
  - Signposts for the note-on and the render inside Python (an `os_signpost` hook in `_cnbridge`), so S2's Audio System Trace sees the whole way from tap to sound; the app marks only the tap and the session's first output now.
  - Enrollment, as late as possible (docs/IOS.md, "Enrollment day"): the steps after it are ready and skip themselves until their secrets exist. ios.yml's TestFlight lane (monthly re-upload), development IPA and unsigned archive rehearsal ("Release lanes"); the session tools in `ios/tools/` (prepare_ssd.sh, mac_bootstrap.sh, rehearsed on CI; readiness.py, pull_testflight_feedback.py, symbolicate.sh, asc_api.py, the session log templates). Before S0: dispatch `unsigned_archive` once and check `symbolicate.sh` against its real dSYM; ask her whether her Mac runs macOS 26.2 or later (Xcode 26.5's minimum). After enrollment: the first TestFlight run (does cloud signing work on an individual account, or is the Apple Distribution fallback needed?), then T1.
  - Decide iOS monetization. About shows the FOSS flavour's Ko-fi link until then; App Review may refuse a link to an outside payment page, as Play does.
  - App Store listing: privacy labels, screenshots, the AGPL notice.
  - Licensing plan (decided 2026-10-31):
    - ship FluidSynth under LGPL-2.1 as a dynamic framework with its source in the release, relying on upstream's Licensing FAQ ("iOS and the App Store": nine copyright holders, including Peter Hanappe and Tom Moebert, agreed not to object if changes stay LGPL and the app can be relinked; not a guarantee);
    - build it without libsndfile (the app plays `.sf2` only);
    - pyFluidSynth (LGPL) isn't covered: done, replaced on every platform by the app's own ctypes binding (`core/chordnotepad/audio/fluid_ctypes.py`);
    - leave chardet out, as on the desktop;
    - fallback if a FluidSynth copyright holder objects: Apple's AVAudioUnitSampler (system library, loads the same SF2) or TinySoundFont (MIT);
    - App Store Connect: AGPL notice and source URL in the listing, no custom EULA.
- Notarized macOS DMG: build.yml signs with a Developer ID, notarizes and checks it once the `release` environment has the Developer ID and API key secrets (docs/RELEASE.md, "Notarizing the macOS app"); until then it builds ad hoc as before. After enrollment: the secrets, the next nightly's two macOS legs, then the "Open Anyway" texts swapped for the ones in docs/RELEASE.md with the first notarized release.
- Mac App Store listing of the Qt app, later: sandbox, the Qt LGPL question, and whether to do Universal Purchase.
- One `chordnotepad.` package namespace, only if a top-level name collides or the core should be installable.

## Needs a decision

- F-Droid: submit or not (AI policy in flux). If yes: fastlane metadata, the recipe (`gradle: [foss]`), AI disclosure, the GeneralUser GS licence question, and whether the logo reserved by `ARTWORK-TERMS.txt` counts as a non-free asset.
- Metronome count-in (one bar before playback when the metronome is on)?
- Android background playback: a foreground media service, or keep pausing (documented limitation)?
- Desktop Default key = None: the toolbar shows "C" and there's no None option (Android shows None). Fix now or fold into the redesign?
- `{bpm: reset}` before the first chord resets to the toolbar tempo: intended? Then document it and close.
- Typed `{time}` accepts 1-16 beats and units 1/2/4/8/16 only (`{time: 17/8}` is red): intended? Then say so in `help/directives.rst`.

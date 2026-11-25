# Brief for a Claude Code agent on the borrowed MacBook

You are working on the iOS port of Chord Notepad
(github.com/chibicitiberiu/chord-notepad, public). You run on Tibi's own
macOS user on his wife's MacBook (Apple silicon, macOS 27). Tibi is at the
keyboard. The rest of the work happens on his Linux PC, where another agent
reads what you bring back. This file is your whole brief; `docs/IOS.md` in
the repo is the reference for everything iOS (read the sections named here,
not the whole file: it is over 2000 lines).

## What exists already

- A native SwiftUI app (`ios/ChordNotepad`) over the shared Python core,
  through a JSON bridge (`ios/ChordNotepadKit`, a SwiftPM package). One
  universal iPhone and iPad app.
- CI (`.github/workflows/ios.yml`, GitHub's `macos-26` runners, Xcode 26.5)
  builds it, runs the kit tests and the app's XCTests on an iPhone and an
  iPad simulator, takes screenshots, and rehearses this Mac's bootstrap
  script. It is green. Nobody has run the app on a real Mac or iPhone yet:
  that is what this session is for.
- Tibi isn't enrolled in the Apple Developer Program yet ($99/year, on
  purpose as late as possible), so there is no team, no signing and no
  TestFlight.

## Ground rules

- **Her accounts and setup stay as they are.** Her Mac and her iPhone are
  never signed in to Tibi's Apple ID (no iCloud, no App Store sign-in on
  this Mac, nothing on her phone). Signing in to developer.apple.com or
  github.com in Safari is fine: it is a web sign-in under his macOS user.
  Signing in to Xcode's Accounts is only for phase 3, if Tibi says so.
- Don't touch her macOS user, don't run `xcode-select -s` (the script uses
  `DEVELOPER_DIR`), and don't install Homebrew or other system-wide tools
  without asking Tibi. Anything that needs an administrator password: say
  what it is for and let Tibi (or her) type it.
- Her iPhone: plug it in, unlock it and tap Trust only with her OK.
  Developer Mode restarts the phone, so ask first.
- Her iPhone's UDID is a secret: it goes in the session report, never in a
  commit.
- Commits: no `Co-authored-by` and no AI attribution of any kind. Ask Tibi
  to set `git config user.name/user.email` himself (don't write his email
  anywhere). Commit fixes in the clone; don't push unless Tibi says so.
  Hand the fixes back with `git format-patch` (phase 4).
- Never run a bare `make` in the repo: its default target launches the
  desktop app.
- Back up a generated artefact before you delete or overwrite it.
- Write plainly: short sentences, no filler words.

## Phase 1: set up the Mac (about 1.5 h, mostly waiting)

The bootstrap script `ios/tools/mac_bootstrap.sh` does the work (its header
lists the steps; every step is skipped once done, so run it again after a
failure). It was written for files carried on a USB SSD. Today there is no
SSD: you make a local folder that stands in for it and fill it from the
network.

1. **Facts first.** Record `sw_vers`, `uname -m`, `id -Gn` (is Tibi's user
   in `admin`?), `df -h ~` (60 GB free needed), and what is already in
   /Applications (`ls -d /Applications/Xcode*`; if she has an Xcode, leave
   it alone). Ask Tibi which iOS version her iPhone runs (Settings >
   General > About), and whether she agrees to plugging it in today.

2. **Pick the Xcode.** CI uses 26.5 (`ios/.xcode-version`).
   - Check developer.apple.com/support/xcode to see whether Xcode 26.5 runs
     on macOS 27 and which iOS versions it can deploy to.
   - If her iPhone runs a newer iOS than 26.5 supports and phase 3 is
     wanted, take the newest released Xcode 27.x (not a beta). Otherwise
     take 26.5. That way only one Xcode is downloaded.
   - Write the choice to the folder as `xcode-version`, and pass it as
     `--xcode-version`. The script checks that `xcodebuild -version` says
     exactly `Xcode <version>`. It warns "no known minimum macOS" for a
     27.x: that warning is expected.
   - Building with an Xcode other than CI's is new ground. If the build
     fails, phase 2 starts with fixing it.

3. **The stand-in folder.** Tibi's network share (SMB on his server; on
   Linux it is `/mnt/zizo/temp1/chord-notepad/`) already holds what
   `ios/tools/prepare_ssd.sh` writes. That is `chord-notepad.bundle` (main),
   `chord-notepad.ref` (the commit the inputs were built from),
   `ios-build-inputs.tar.gz` (CI's prebuilt FluidSynth and Python
   frameworks, the Python bundle and the user guide), `xcodegen.zip`,
   `xcode-version`, `mac_bootstrap.sh` and `SHA256SUMS`.
   - Ask Tibi where the share is mounted on the Mac (Finder > Go >
     Connect to Server, then under `/Volumes/`). Its path may have a space
     in it.
   - Copy it to a local folder and work from there: `mkdir -p
     ~/ChordNotepad/ssd && cp "<share>"/* ~/ChordNotepad/ssd/`. Don't edit
     the files: `SHA256SUMS` covers them. To use another Xcode, pass
     `--xcode-version` instead of changing `xcode-version`.
   - `Xcode_<version>.xip`: Tibi downloads it in Safari from
     developer.apple.com/download/all (signed in with his Apple ID on the
     web) straight into `~/ChordNotepad/ssd`. It is several GB, so start
     this first.
   - The share has no runtime `.dmg` (step 4.4) and no Xcode: expected.
   - If the share isn't reachable, fetch the same files from the network.
     The inputs are the `ios-build-inputs` artifact of the newest green
     ios.yml run on main (GitHub's Actions page, signed in). XcodeGen 2.46.0
     is `xcodegen.zip` from its GitHub release. The script is
     `ios/tools/mac_bootstrap.sh` at the inputs' commit, from
     raw.githubusercontent.com.

4. **Run it in stages.** `S=~/ChordNotepad/ssd`, `V=<version>`.
   1. `bash $S/mac_bootstrap.sh --ssd $S --xcode-version $V --dry-run`: read
      what it would do.
   2. `nohup bash $S/mac_bootstrap.sh --ssd $S --xcode-version $V --only
      extract > ~/ChordNotepad/extract.log 2>&1 &`. This takes 20–40 min.
   3. `--only xcode`: moves Xcode to `/Applications/Xcode_<V>.app`, accepts
      the licence and runs `-runFirstLaunch`, through sudo. If Tibi's user
      isn't an admin, add `--admin <her short user name>`, and she types her
      password.
   4. **The simulator runtime.** There is no runtime `.dmg` today:
      ```
      export DEVELOPER_DIR=/Applications/Xcode_$V.app/Contents/Developer
      xcodebuild -downloadPlatform iOS
      ```
      This needs no sign-in. The script's runtime step then finds the
      runtime installed and skips.
   5. The rest:
      `bash $S/mac_bootstrap.sh --ssd $S --xcode-version $V`. It runs
      XcodeGen, unpacks the inputs, generates the project, builds for an
      iPhone simulator, runs the app until it writes `startup.json`, takes
      a screenshot and writes the report. Its repo step clones the bundle
      at `chord-notepad.ref`, so the Swift code matches the prebuilt inputs.
      It ends with the device listing,
      which says "none connected" until phase 3.
   - The report lands in `$S/session-reports/<date-time>/` (`report.txt`,
     `build.log`, `simulator.png`, the app's Diagnostics folder).

## Phase 2: the app in the Simulator, with Tibi (the rest of the time)

Open Simulator.app (`open -a Simulator`). Tibi uses the app, and you drive
`simctl`, take the screenshots and keep the issue list. The Mac's speakers
play the simulator's sound, so audio can be checked here too.

- **Cold launches.** Quit and launch the app five times in a row. Watch for
  an abort while FluidSynth starts CoreAudio: CI's iPad simulator once
  aborted with "CoreAudio Initialize: RPC timeout. Apparently deadlocked."
  (docs/IOS.md "Readiness checklist").
- **The basics.**
  - The Quick Start song opens.
  - A tapped chord sounds.
  - Play, pause and stop work, and the playhead follows.
  - Switch between Edit and Play.
  - The chord sheet, the voicing editor, Settings, About, Licences, the
    user guide, find and replace, the font size and the pinch.
  - Export MIDI, audio and PDF.
- **Files** (docs/IOS.md "Readiness checklist", the standing file-handling
  items 1–8, as far as the simulator's Files app goes):
  - Save As into On My iPhone;
  - Open…, and change and Save in place;
  - Recent after a relaunch;
  - rename from the title;
  - delete a recent song in Files, then open it from Recent: time how long
    "File not found" takes (it took about a minute in CI).
- **Layouts.** Build and run on an iPad simulator too (`xcrun simctl list
  devices available`).
  - On the iPad: rotation, split view and Stage Manager widths.
  - Dark mode: `xcrun simctl ui <udid> appearance dark`.
  - Large text: `xcrun simctl ui <udid> content_size
    accessibility-extra-large`.
  - A hardware keyboard: the shortcuts in docs/IOS.md "Find, the font, the
    pinch and the keys".
- **Launch hooks.** `xcrun simctl launch <udid> com.tibich.chordnotepad
  -CNScreen <name>` opens a screen directly (docs/IOS.md "The main
  screen", "Launch hooks"). Use them to reach a screen quickly.
- **XCTests, once, in the background:** `xcodebuild test -project
  ios/ChordNotepad.xcodeproj -scheme ChordNotepad -destination id=<udid>
  -derivedDataPath ios/build/DerivedData`. They are green on CI. A failure
  here (another Xcode, a real Mac) is a finding, not something to fix by
  loosening the test.

**For every problem:**
- add a numbered issue: what was done, what was expected, what happened;
- take a screenshot (`xcrun simctl io <udid> screenshot <file>`), or a video
  for motion (`recordVideo`);
- add the Diagnostics folder if the app logged something.

Fix only build breaks and plain crashes yourself, one commit each. Leave UI
and behaviour changes to the Linux side: Tibi decides those, and he takes
UI specs literally.

## Phase 3 (only if Tibi and she agree): her iPhone

1. **The listing.** Plug in her iPhone, unlock it, tap Trust. Then
   `bash $S/mac_bootstrap.sh --ssd $S --xcode-version $V --only "device
   report"` records the UDID, model, iOS version, pairing and Developer
   Mode.
2. **Running the app on it before enrollment, with a free personal team.**
   This is optional and needs both of them to say yes.
   1. Tibi adds his Apple ID in Xcode > Settings > Accounts. That is his
      account in his macOS user; nothing on her phone signs in.
   2. She turns on Developer Mode (Settings > Privacy & Security; the phone
      restarts).
   3. Use another bundle ID, so the real one stays free for the paid team
      later:
      ```
      xcodebuild build -project ios/ChordNotepad.xcodeproj -scheme ChordNotepad \
        -destination id=<her udid> -derivedDataPath ios/build/DerivedData-device \
        -allowProvisioningUpdates DEVELOPMENT_TEAM=<personal team id> \
        PRODUCT_BUNDLE_IDENTIFIER=com.tibich.chordnotepad.dev
      ```
   4. Install it with `xcrun devicectl device install app --device <udid>
      <the .app>`.
   5. She trusts the developer under Settings > General > VPN & Device
      Management.
   - The free profile lasts 7 days.
   - The listing and the session log say that this was a personal-team
     build.
3. **Run the device checklist,** under a screen recording on the phone:
   - the standing items in docs/IOS.md "Readiness checklist";
   - the Files items 1–8 with iCloud Drive;
   - the silent switch;
   - headphones or Bluetooth in and out;
   - an alarm or a call as an interruption;
   - background and resume;
   - five cold launches;
   - then Export diagnostics in the app, and AirDrop it to the Mac.
4. **Afterwards:** delete the app from her phone, unless she wants to keep
   it. Developer Mode stays as she likes it.

## Phase 4: wrap up (last 15 min)

- Fill a session log from `ios/tools/session_logs/S0.md` (copy it, don't
  edit the template): what ran, timings, the issue list, decisions.
- Patches: `git -C ~/ChordNotepad/chord-notepad format-patch <the commit in chord-notepad.ref>
  -o <report>/patches`, if you committed anything.
- One zip on the Desktop, `chord-notepad-mac-<date>.zip`, with:
  - `session-reports/`;
  - the session log and the issue list with its screenshots and videos;
  - the extra XCTest result bundle, if any;
  - the patches;
  - the AirDropped diagnostics.

  Put the UDID in a separate small text file next to it, not inside the zip.
- Copy the zip and the UDID file to the share, into a new folder
  `session-<date>/`. The Linux agent reads them from there. Copy
  `session-reports/` there during the session too, after each phase, so
  nothing is lost if the session ends early. Stop the simulators (`xcrun
  simctl shutdown all`).
- Leave Xcode, the runtime and `~/ChordNotepad` in place for the next
  session (S1 picks up with `mac_bootstrap.sh --verify`), unless Tibi wants
  the disk space back.

If something here is wrong for this Mac (a path, a version, a step that
needs a download), adapt. Say what you changed in the session log, so the
next brief and `docs/IOS.md` can be fixed.

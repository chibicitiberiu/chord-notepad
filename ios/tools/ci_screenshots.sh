#!/bin/bash
# Run the app in a simulator the way a person would, and keep what it shows
# (docs/IOS.md, "CI"): the first launch after the install, where the Quick
# Start tour opens over the song (startup.json checked), a screenshot of the
# main screen with the quick-start song (in Play, as a saved song opens), one
# of the ☰ menu, one of
# Diagnostics, whose self-test also tries live CoreAudio playback, one of Play
# with the chord sheet shown (its buffer from the live session), one of
# Edit after the app typed into the editor (the session's highlight checked),
# the speed sheet, the Guitar family's programs, the ribbon's Insert › Tempo, Suggest Capo and Identify,
# the find bar with its Replace row, Settings › General, Settings › Voicings
# with a built-in's form, About, the Instrument sheet's families, the user
# guide, a directive's explanation in Play, a new song typed with the keyboard
# up, the phone on its side typing (the guide's screenshots), three of an
# audio export ("Preparing export…", the export picker after it, the status
# after a simulated save; export.json checked) and one of the picker after a
# PDF export (pdf.json checked, the PDF in the Diagnostics folder), and the
# relaunch check: a song typed, the app ended in the background, the song
# back unsaved at the next launch.
#
#   ios/tools/ci_screenshots.sh <udid> <label> <ChordNotepad.app> <out-dir>
#
# Writes <out-dir>/<label>-quickstart.png, <label>-main.png, <label>-menu.png,
# <label>-selftest.png, <label>-chordsheet.png, <label>-editor.png, <label>-speed.png,
# <label>-instrument.png, <label>-insert.png, <label>-capo.png, <label>-identify.png,
# <label>-find.png, <label>-settings.png, <label>-voicings.png, <label>-about.png,
# <label>-families.png, <label>-guide.png, <label>-hint.png, <label>-keyboard.png,
# <label>-landscape.png, <label>-export-preparing.png, <label>-export.png,
# <label>-export-saved.png, <label>-pdf.png, <label>-relaunch.png, the app's
# Diagnostics folder as <label>-diagnostics/ and the unified log of the
# app's subsystem as <label>-app.log. The live audio result is in
# <label>-diagnostics/selftest.json; ci_live_audio.py reads it.
set -euo pipefail

UDID=${1:?usage: ci_screenshots.sh <udid> <label> <app> <out-dir>}
LABEL=${2:?}
APP=${3:?}
OUT=${4:?}
BUNDLE_ID=com.tibich.chordnotepad
mkdir -p "$OUT"
# The software keyboard, not a connected Mac keyboard, for the editor's screenshot.
defaults write com.apple.iphonesimulator ConnectHardwareKeyboard -bool false || true

xcrun simctl boot "$UDID" 2>/dev/null || true
xcrun simctl bootstatus "$UDID" -b
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState charged --batteryLevel 100 || true
xcrun simctl uninstall "$UDID" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$UDID" "$APP"
DATA=$(xcrun simctl get_app_container "$UDID" "$BUNDLE_ID" data)
DIAG="$DATA/Documents/Diagnostics"

# wait_for <file> <seconds>
wait_for() {
    local file=$1 limit=$2 waited=0
    while [ ! -f "$file" ]; do
        if [ "$waited" -ge "$limit" ]; then
            echo "Timed out after ${limit}s waiting for $file" >&2
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
}

status=0
start=$(date -u +%Y-%m-%dT%H:%M:%S)
# The first launch after the install, as a person's: no last song yet, so
# the quick-start song opens, and the session opens the Quick Start tour over
# it (app_started, "Show at startup" on); the app writes startup.json once
# the tour is on screen.
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID"
if wait_for "$DIAG/startup.json" 240; then
    cat "$DIAG/startup.json"
    sleep 2
    python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/startup.json" \
        || { echo "The tour didn't open at the first launch" >&2; status=1; }
    python3 -c 'import json, sys; d = json.load(open(sys.argv[1])).get("detail", "")
sys.exit(0 if "launch quickStart" in d and "document 01_quick_start.txt" in d else 1)' "$DIAG/startup.json" \
        || { echo "The first launch didn't open the quick-start song" >&2; status=1; }
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-quickstart.png"

# The main screen: -CNScreen main is a hook that does nothing, so the launch
# isn't a direct one and nothing opens over the song.
rm -f "$DIAG/launch.json" "$DATA/Library/Application Support/Diagnostics/launch.json"
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen main
if wait_for "$DIAG/launch.json" 240; then
    cat "$DIAG/launch.json"
    # The launch state (a spinner, not the session's empty untitled song) ends with the song.
    python3 -c 'import json, sys; sys.exit(1 if json.load(open(sys.argv[1])).get("launching", True) else 0)' \
        "$DIAG/launch.json" || { echo "The launch state was still up with the song open" >&2; status=1; }
    sleep 3
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-main.png"

# The menu, opened at launch over the song. launch.json is written again when
# the song is on screen (both copies go first: the launch mirrors the other).
rm -f "$DIAG/launch.json" "$DATA/Library/Application Support/Diagnostics/launch.json"
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen menu
if wait_for "$DIAG/launch.json" 240; then
    sleep 3
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-menu.png"

rm -f "$DIAG/selftest.json"
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen selftest
if wait_for "$DIAG/selftest.json" 240; then
    cat "$DIAG/selftest.json"
    sleep 2
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-selftest.png"

# The chord sheet: the app writes chordsheet.json when its first buffer is
# drawn. One retry: the simulator's CoreAudio sometimes aborts the app while
# FluidSynth's player starts ("Initialize: RPC timeout. Apparently
# deadlocked."), before the sheet is reached.
rm -f "$DIAG/chordsheet.json"
sheet=1
for attempt in 1 2; do
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen chordsheet
    if wait_for "$DIAG/chordsheet.json" 150; then
        cat "$DIAG/chordsheet.json"
        sleep 3
        sheet=0
        break
    fi
    echo "Attempt $attempt: no chord sheet drawn" >&2
done
[ "$sheet" -eq 0 ] || status=1
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-chordsheet.png"

# The song editor: the app types a long chord line into the text view
# (EditorScript) and writes editor.json once the session's highlight of it is
# painted; the keyboard should be up. Same retry as the chord sheet.
rm -f "$DIAG/editor.json"
edited=1
for attempt in 1 2; do
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen editor
    if wait_for "$DIAG/editor.json" 150; then
        cat "$DIAG/editor.json"
        sleep 3
        if python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/editor.json"; then
            edited=0
        else
            echo "The editor check failed" >&2
        fi
        break
    fi
    echo "Attempt $attempt: no editor check" >&2
done
[ "$edited" -eq 0 ] || status=1
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-editor.png"

# The player's speed sheet and the Edit ribbon's tools, live: the app opens
# each as a person would and writes tool-<name>.json when it is ready (the
# speed at 125 %, Insert › Tempo with the session's check, Suggest Capo
# scored, the identifier with Cmaj7, Find and Replace with "the" typed,
# Settings › General, Settings › Voicings with the built-in standard guitar,
# About; for the guide: the Instrument sheet's families, the guide itself, a
# directive's explanation, a new song typed with the keyboard up and, last,
# the phone on its side typing). The identifier's keys stay lit 3 s after
# Cmaj7 sounds, so its screenshot comes sooner. Same retry as the chord sheet.
for tool in speed instrument insert capo identify find settings voicings about families guide hint keyboard landscape; do
    rm -f "$DIAG/tool-$tool.json"
    shown=1
    for attempt in 1 2; do
        xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen "$tool"
        if wait_for "$DIAG/tool-$tool.json" 150; then
            cat "$DIAG/tool-$tool.json"
            if [ "$tool" = identify ]; then sleep 0.5; else sleep 3; fi
            if python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/tool-$tool.json"; then
                shown=0
            else
                echo "The $tool screen didn't get ready" >&2
            fi
            break
        fi
        echo "Attempt $attempt: no $tool screen" >&2
    done
    [ "$shown" -eq 0 ] || status=1
    xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-$tool.png"
done

# Export audio with the real player's SoundFont, in step with the app
# (AppModel.runExportCheck): "Preparing export…" up (export-dialog.json),
# its screenshot, then export-go; the export picker up (export-picker.json),
# its screenshot, then export-save; the app saves the file as Save would and
# writes export.json (the WAV, the dialog, the picker, the "Exported audio: …"
# status), shown in the last screenshot. Same retry as the chord sheet.
exported=1
for attempt in 1 2; do
    rm -f "$DIAG/export.json" "$DIAG/export-dialog.json" "$DIAG/export-picker.json" \
        "$DIAG/export-go" "$DIAG/export-save"
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen export
    if wait_for "$DIAG/export-dialog.json" 150; then
        cat "$DIAG/export-dialog.json"
        sleep 0.5
        xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-export-preparing.png"
    fi
    touch "$DIAG/export-go"
    if wait_for "$DIAG/export-picker.json" 300; then
        sleep 4
        xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-export.png"
    fi
    touch "$DIAG/export-save"
    if wait_for "$DIAG/export.json" 120; then
        cat "$DIAG/export.json"
        sleep 2
        xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-export-saved.png"
        if python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/export.json"; then
            exported=0
        else
            echo "The audio export check failed" >&2
        fi
        break
    fi
    echo "Attempt $attempt: no audio export" >&2
done
[ "$exported" -eq 0 ] || status=1

# Export PDF: the app paints the session's pages and writes pdf.json (PDFKit's
# page count, a line of the song in its text, the font's advance) and
# export.pdf when the store has the file, then opens the export picker.
rm -f "$DIAG/pdf.json" "$DIAG/export.pdf"
pdf=1
for attempt in 1 2; do
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen pdf
    if wait_for "$DIAG/pdf.json" 150; then
        cat "$DIAG/pdf.json"
        sleep 4
        if python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/pdf.json"; then
            pdf=0
        else
            echo "The PDF export check failed" >&2
        fi
        break
    fi
    echo "Attempt $attempt: no PDF export" >&2
done
[ "$pdf" -eq 0 ] || status=1
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-pdf.png"

# A relaunch reopens the last song with its unsaved text (docs/IOS.md, "The
# last song"): -CNScreen draft types a new song in Edit and leaves it
# unsaved (draft.json); the Settings app then sends ours to the background,
# where it writes the last song (draft-kept.json); the app is ended there, as
# iOS or a swipe would, and -CNScreen restored checks the song came back
# untitled, unsaved, typed, in Edit (restored.json). The hooks before these
# never keep the last song, so their screenshots always show the quick-start song.
# ok <name>: the Diagnostics file <name>.json says ok.
ok() {
    python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$DIAG/$1.json"
}
rm -f "$DIAG/draft.json" "$DIAG/draft-kept.json" "$DIAG/restored.json"
relaunched=1
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen draft
if wait_for "$DIAG/draft.json" 150; then
    cat "$DIAG/draft.json"
    sleep 1
    xcrun simctl launch "$UDID" com.apple.Preferences >/dev/null || true
    if wait_for "$DIAG/draft-kept.json" 60; then
        cat "$DIAG/draft-kept.json"
        xcrun simctl terminate "$UDID" "$BUNDLE_ID" || true
        sleep 1
        xcrun simctl launch "$UDID" "$BUNDLE_ID" -CNScreen restored
        if wait_for "$DIAG/restored.json" 150; then
            cat "$DIAG/restored.json"
            sleep 2
            if ok draft && ok draft-kept && ok restored; then relaunched=0; fi
        fi
    fi
fi
[ "$relaunched" -eq 0 ] || { echo "A relaunch didn't reopen the last song" >&2; status=1; }
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-relaunch.png"
xcrun simctl terminate "$UDID" "$BUNDLE_ID" || true

rm -rf "$OUT/$LABEL-diagnostics"
cp -R "$DIAG" "$OUT/$LABEL-diagnostics" 2>/dev/null || true
xcrun simctl spawn "$UDID" log show --start "${start/T/ }" --style compact \
    --predicate 'subsystem == "com.tibich.chordnotepad" OR process == "ChordNotepad"' \
    > "$OUT/$LABEL-app.log" 2>&1 || true
exit $status

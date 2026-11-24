#!/bin/bash
# Run the app in a simulator the way a person would, and keep what it shows
# (docs/IOS.md, "CI"): a screenshot of the shell with the quick-start song,
# one of the self-test, which also tries live CoreAudio playback, one of the
# shell with the chord sheet shown (its buffer from the live session), and one
# of the editor after the app typed into it (the session's highlight checked).
#
#   ios/tools/ci_screenshots.sh <udid> <label> <ChordNotepad.app> <out-dir>
#
# Writes <out-dir>/<label>-shell.png, <label>-selftest.png,
# <label>-chordsheet.png, <label>-editor.png, the app's
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
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID"
if wait_for "$DIAG/launch.json" 240; then
    cat "$DIAG/launch.json"
    sleep 3
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-shell.png"

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
xcrun simctl terminate "$UDID" "$BUNDLE_ID" || true

rm -rf "$OUT/$LABEL-diagnostics"
cp -R "$DIAG" "$OUT/$LABEL-diagnostics" 2>/dev/null || true
xcrun simctl spawn "$UDID" log show --start "${start/T/ }" --style compact \
    --predicate 'subsystem == "com.tibich.chordnotepad" OR process == "ChordNotepad"' \
    > "$OUT/$LABEL-app.log" 2>&1 || true
exit $status

#!/bin/bash
# Run the app in a simulator the way a person would, and keep what it shows
# (docs/IOS.md, "CI"): a screenshot of the shell with the quick-start song,
# one of the self-test, which also tries live CoreAudio playback, and one of
# the shell with the chord sheet shown (its buffer from the live session).
#
#   ios/tools/ci_screenshots.sh <udid> <label> <ChordNotepad.app> <out-dir>
#
# Writes <out-dir>/<label>-shell.png, <label>-selftest.png,
# <label>-chordsheet.png, the app's
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

# The chord sheet: the app writes chordsheet.json when its first buffer is drawn.
rm -f "$DIAG/chordsheet.json"
xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" -CNScreen chordsheet
if wait_for "$DIAG/chordsheet.json" 240; then
    cat "$DIAG/chordsheet.json"
    sleep 3
else
    status=1
fi
xcrun simctl io "$UDID" screenshot "$OUT/$LABEL-chordsheet.png"
xcrun simctl terminate "$UDID" "$BUNDLE_ID" || true

rm -rf "$OUT/$LABEL-diagnostics"
cp -R "$DIAG" "$OUT/$LABEL-diagnostics" 2>/dev/null || true
xcrun simctl spawn "$UDID" log show --start "${start/T/ }" --style compact \
    --predicate 'subsystem == "com.tibich.chordnotepad" OR process == "ChordNotepad"' \
    > "$OUT/$LABEL-app.log" 2>&1 || true
exit $status

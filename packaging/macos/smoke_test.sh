#!/usr/bin/env bash
# Install Chord Notepad from its disk image the way a user would, and check it
# starts.
#
#   packaging/macos/smoke_test.sh dist/ChordNotepad-macos-arm64.dmg
#
# Copies the app out of the mounted image, checks its signature and that the
# bundled libfluidsynth loads, then opens it through Launch Services and passes
# when the startup banner appears in the log and the app is still running
# shortly after. A missing "Loaded soundfont" line is only a warning, because
# CI runners may have no audio device; FluidSynth not being found fails.
set -euo pipefail

DMG=${1:?usage: smoke_test.sh <dmg>}
TIMEOUT=${TIMEOUT:-60}
ALIVE=${ALIVE:-10}

WORK=$(mktemp -d)
MOUNT="$WORK/mount"
mkdir "$MOUNT"
hdiutil attach -nobrowse -readonly -mountpoint "$MOUNT" "$DMG" >/dev/null
test -L "$MOUNT/Applications" || { echo "::error::The disk image has no Applications link"; exit 1; }
ditto "$MOUNT/Chord Notepad.app" "$WORK/Chord Notepad.app"
hdiutil detach "$MOUNT" >/dev/null
APP="$WORK/Chord Notepad.app"

codesign --verify --deep --strict --verbose=2 "$APP"
/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' -c 'Print :CFBundleShortVersionString' \
    -c 'Print :LSMinimumSystemVersion' "$APP/Contents/Info.plist"

LIB=$(find "$APP/Contents" -name 'libfluidsynth.3.dylib' -type f | head -n 1)
[ -n "$LIB" ] || { echo "::error::libfluidsynth.3.dylib is not in the app"; exit 1; }
echo "Bundled FluidSynth: $LIB"
file "$LIB"
python3 -c 'import ctypes, sys; ctypes.CDLL(sys.argv[1]); print("libfluidsynth loads")' "$LIB"

LOGS="$HOME/Library/Application Support/ChordNotepad/logs"
rm -rf "$LOGS"
open -n "$APP"

log=""
for _ in $(seq 1 $((TIMEOUT / 2))); do
    sleep 2
    log=$(ls -t "$LOGS"/*.log 2>/dev/null | head -n 1 || true)
    if [ -n "$log" ] && grep -q 'Version:' "$log"; then break; fi
done

failed=0
if [ -z "$log" ] || ! grep -q 'Version:' "$log"; then
    echo "::error::No startup banner in $LOGS within ${TIMEOUT}s"
    failed=1
else
    sleep "$ALIVE"
    if ! pgrep -f "Chord Notepad.app/Contents/MacOS/" >/dev/null; then
        echo "::error::The app exited within ${ALIVE}s of starting"
        failed=1
    fi
    if grep -q "Couldn't find the FluidSynth library" "$log"; then
        echo "::error::The app didn't find its bundled FluidSynth"
        failed=1
    elif ! grep -q 'Loaded soundfont' "$log"; then
        echo "::warning::Soundfont not loaded (expected on runners without an audio device)"
    fi
    if grep -q 'Traceback' "$log"; then
        echo "::warning::Log contains a Python traceback"
    fi
    echo "--- $log"
    tail -n 60 "$log"
fi

pkill -f "Chord Notepad.app/Contents/MacOS/" || true
rm -rf "$WORK"
exit $failed

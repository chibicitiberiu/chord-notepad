#!/usr/bin/env bash
# Start the Qt window (--ui qt --smoke) from the app in a disk image.
#
#   packaging/macos/smoke_test_qt.sh dist/ChordNotepad-macos-arm64.dmg
#
# Copies the app out of the image as smoke_test.sh does, then runs its
# executable with --ui qt --smoke: the window loads, shows and quits, exit 1
# on any QML warning (chordnotepad_desktop/main.py). The Qt Quick scene graph
# may not get a GPU on a CI runner: if the plain run fails, it runs again
# with QT_QUICK_BACKEND=software and only warns when that one passes.
set -euo pipefail

DMG=${1:?usage: smoke_test_qt.sh <dmg>}
TIMEOUT=${TIMEOUT:-120}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
MOUNT="$WORK/mount"
mkdir "$MOUNT"
hdiutil attach -nobrowse -readonly -mountpoint "$MOUNT" "$DMG" >/dev/null
ditto "$MOUNT/Chord Notepad.app" "$WORK/Chord Notepad.app"
hdiutil detach "$MOUNT" >/dev/null
EXE="$WORK/Chord Notepad.app/Contents/MacOS/ChordNotepad"

smoke() {
    # macOS has no timeout(1); perl's alarm kills a run that hangs.
    perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" "$EXE" --ui qt --smoke
}

if smoke; then
    echo "The Qt window started and quit cleanly"
    exit 0
fi
echo "::warning::--ui qt --smoke failed with the default scene graph; trying QT_QUICK_BACKEND=software"
if QT_QUICK_BACKEND=software smoke; then
    echo "::warning::The Qt window only starts with software rendering on this runner"
    exit 0
fi
echo "::error::The Qt window (--ui qt --smoke) didn't start from $DMG"
exit 1

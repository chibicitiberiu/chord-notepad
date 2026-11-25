#!/usr/bin/env bash
# Gatekeeper's view of the notarized disk image and the app in it, as a
# downloaded copy would get it (build.yml, after the smoke tests, only for the
# Developer ID build).
#
#   packaging/macos/check_notarized.sh dist/ChordNotepad-macos-arm64.dmg
#
# Fails unless spctl accepts both with "source=Notarized Developer ID" and
# the image carries a stapled ticket.
set -euo pipefail

DMG=${1:?usage: check_notarized.sh <dmg>}
WORK=$(mktemp -d)
trap 'hdiutil detach "$WORK/mount" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature -vv "$DMG" 2>&1 | tee "$WORK/dmg.txt"

mkdir "$WORK/mount"
hdiutil attach -nobrowse -readonly -mountpoint "$WORK/mount" "$DMG" >/dev/null
ditto "$WORK/mount/Chord Notepad.app" "$WORK/Chord Notepad.app"
hdiutil detach "$WORK/mount" >/dev/null
spctl --assess --type execute -vv "$WORK/Chord Notepad.app" 2>&1 | tee "$WORK/app.txt"

failed=0
for report in dmg app; do
    if ! grep -q 'source=Notarized Developer ID' "$WORK/$report.txt"; then
        echo "::error::Gatekeeper doesn't see the $report as notarized"
        failed=1
    fi
done
exit $failed

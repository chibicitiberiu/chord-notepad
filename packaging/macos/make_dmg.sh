#!/usr/bin/env bash
# Package the PyInstaller app bundle as a drag-to-Applications disk image.
#
#   packaging/macos/make_dmg.sh "dist/Chord Notepad.app" dist/ChordNotepad-macos-arm64.dmg
#
# The app is signed ad hoc (no Apple Developer ID), which Apple silicon needs to
# run it at all; Gatekeeper still asks the user to allow it once (see
# help/introduction.rst).
set -euo pipefail

APP=${1:?usage: make_dmg.sh <app> <dmg>}
DMG=${2:?usage: make_dmg.sh <app> <dmg>}

# Re-sign the whole bundle, so the signature covers everything PyInstaller
# put in it, then check it the way Gatekeeper will.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
# ditto keeps the bundle's symlinks and extended attributes
ditto "$APP" "$STAGE/$(basename "$APP")"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create -volname "Chord Notepad" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
hdiutil verify "$DMG"
echo "Disk image: $DMG"

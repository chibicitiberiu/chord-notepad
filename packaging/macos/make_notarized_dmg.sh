#!/usr/bin/env bash
# The Developer ID build of the disk image: sign the app inside out, build the
# image as make_dmg.sh does, sign it, notarize it and staple the ticket
# (docs/RELEASE.md, "Notarizing the macOS app"). build.yml runs this instead
# of make_dmg.sh only when the Developer ID secrets are set.
#
#   CODESIGN_IDENTITY=<identity SHA-1> ASC_KEY_PATH=<AuthKey .p8> ASC_KEY_ID=<id> ASC_ISSUER_ID=<id> \
#       packaging/macos/make_notarized_dmg.sh "dist/Chord Notepad.app" dist/ChordNotepad-macos-arm64.dmg
set -euo pipefail

APP=${1:?usage: make_notarized_dmg.sh <app> <dmg>}
DMG=${2:?usage: make_notarized_dmg.sh <app> <dmg>}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${CODESIGN_IDENTITY:?set CODESIGN_IDENTITY}
: "${ASC_KEY_PATH:?}" "${ASC_KEY_ID:?}" "${ASC_ISSUER_ID:?}"

"$HERE/sign_app.sh" "$APP"

STAGE=$(mktemp -d)
WORK=$(mktemp -d)
trap 'rm -rf "$STAGE" "$WORK"' EXIT
# ditto keeps the bundle's symlinks, extended attributes and signatures
ditto "$APP" "$STAGE/$(basename "$APP")"
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create -volname "Chord Notepad" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
codesign --force --timestamp --sign "$IDENTITY" "$DMG"

echo "Notarizing $DMG (usually a few minutes)"
xcrun notarytool submit "$DMG" --key "$ASC_KEY_PATH" --key-id "$ASC_KEY_ID" --issuer "$ASC_ISSUER_ID" \
    --wait --timeout 60m --output-format json > "$WORK/submit.json" || true
cat "$WORK/submit.json"
read -r id status < <(python3 -I -c 'import json, sys; r = json.load(open(sys.argv[1])); print(r.get("id", "-"), r.get("status", "-"))' "$WORK/submit.json")
if [ "$status" != Accepted ]; then
    echo "::error::Notarization of $(basename "$DMG") ended as $status"
    if [ "$id" != - ]; then
        xcrun notarytool log "$id" --key "$ASC_KEY_PATH" --key-id "$ASC_KEY_ID" --issuer "$ASC_ISSUER_ID" || true
    fi
    exit 1
fi

xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
hdiutil verify "$DMG"
echo "Notarized disk image: $DMG"

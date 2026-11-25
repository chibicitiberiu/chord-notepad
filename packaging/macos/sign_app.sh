#!/usr/bin/env bash
# Sign the PyInstaller app with a Developer ID, inside out, for notarization
# (docs/RELEASE.md, "Notarizing the macOS app"). make_notarized_dmg.sh runs it;
# the ad hoc build (make_dmg.sh) doesn't.
#
#   CODESIGN_IDENTITY=<SHA-1 of the Developer ID Application identity> \
#       packaging/macos/sign_app.sh "dist/Chord Notepad.app" [--dry-run]
#
# Every Mach-O file and nested bundle on its own, deepest first
# (sign_order.py), then the app: hardened runtime and a secure timestamp on
# each, the entitlements (entitlements.plist: Python's ctypes and the
# libraries it loads need unsigned executable memory and no library
# validation) on executables and the app. --dry-run prints the codesign
# commands instead (the tests run it on Linux).
set -euo pipefail

APP=${1:?usage: sign_app.sh <app> [--dry-run]}
DRY_RUN=0
if [ "${2:-}" = --dry-run ]; then DRY_RUN=1; fi
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IDENTITY=${CODESIGN_IDENTITY:?set CODESIGN_IDENTITY to the Developer ID identity}
ENTITLEMENTS="$HERE/entitlements.plist"
PYTHON=${PYTHON:-python3}

sign() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "codesign $*"
    else
        codesign "$@"
    fi
}

count=0
while IFS=$'\t' read -r kind path; do
    case "$kind" in
        exe|app)
            sign --force --timestamp --options runtime --entitlements "$ENTITLEMENTS" --sign "$IDENTITY" "$path" ;;
        lib|bundle)
            sign --force --timestamp --options runtime --sign "$IDENTITY" "$path" ;;
        *) echo "error: unknown kind $kind for $path" >&2; exit 1 ;;
    esac
    count=$((count + 1))
done < <("$PYTHON" -I "$HERE/sign_order.py" "$APP")
echo "Signed $count items in $APP"

if [ "$DRY_RUN" = 0 ]; then
    codesign --verify --deep --strict --verbose=2 "$APP"
    codesign --display --verbose=2 "$APP" 2>&1 | grep -E '^(Identifier|Format|TeamIdentifier|Timestamp|Runtime)'
fi

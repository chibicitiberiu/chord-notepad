#!/usr/bin/env bash
# Fill the USB SSD for a session on the borrowed Mac, on Linux (docs/IOS.md,
# "Device sessions"): everything mac_bootstrap.sh needs, so nothing is
# downloaded or built there.
#
#   ios/tools/prepare_ssd.sh /run/media/$USER/<SSD> [--run <ios.yml run id>] [--repo <checkout>]
#
# Writes to the SSD:
#   chord-notepad.bundle   a git bundle of origin/main (git fetch first)
#   chord-notepad.ref      the commit to check out: the CI run's, so the
#                          code matches the prebuilt inputs
#   ios-build-inputs.tar.gz  the run's ios-build-inputs artifact (gh run download)
#   xcodegen.zip           the release ios.yml pins, its SHA-256 checked
#   xcode-version          ios/.xcode-version
#   mac_bootstrap.sh       this folder's
#   SHA256SUMS             of the files above (mac_bootstrap.sh checks them)
# and checks that the two Apple downloads are there (by hand, with a free
# Apple Account, from developer.apple.com/download/all): Xcode_<version>.xip
# and the matching iOS simulator runtime (*Simulator_Runtime*.dmg).
#
# --run: the ios.yml run to take the inputs from; default the newest
# successful push run on main that has them.
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
SSD=""
RUN=""
REF=origin/main

while [ $# -gt 0 ]; do
    case "$1" in
        --run) RUN=${2:?}; shift 2 ;;
        --repo) REPO=${2:?}; shift 2 ;;
        --ref) REF=${2:?}; shift 2 ;;
        -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
        *) if [ -z "$SSD" ]; then SSD=$1; shift; else echo "unknown argument: $1" >&2; exit 2; fi ;;
    esac
done
[ -n "$SSD" ] || { echo "usage: prepare_ssd.sh <ssd folder> [--run <id>]" >&2; exit 2; }
[ -d "$SSD" ] || { echo "error: $SSD isn't a folder" >&2; exit 1; }

XCODE_VERSION=$(tr -d '[:space:]' < "$REPO/ios/.xcode-version")
ACTION="$REPO/.github/actions/ios-app-setup/action.yml"
pin() { sed -n "s/^ *$1: '\{0,1\}\([0-9A-Za-z.]*\)'\{0,1\}$/\1/p" "$ACTION" | head -n 1; }
XCODEGEN_VERSION=$(pin XCODEGEN_VERSION)
XCODEGEN_SHA256=$(pin XCODEGEN_SHA256)
problems=0

if [ -z "$RUN" ]; then
    for candidate in $(gh run list --workflow ios.yml --branch main --event push --status success --limit 10 \
            --json databaseId -q '.[].databaseId'); do
        if gh api "repos/{owner}/{repo}/actions/runs/$candidate/artifacts" \
                -q '.artifacts[] | select(.name == "ios-build-inputs" and (.expired | not)) | .name' | grep -q .; then
            RUN=$candidate
            break
        fi
    done
    [ -n "$RUN" ] || { echo "error: no green ios.yml push run with ios-build-inputs; push or dispatch one" >&2; exit 1; }
fi
COMMIT=$(gh run view "$RUN" --json headSha -q .headSha)
echo "Inputs from run $RUN (commit ${COMMIT:0:7})"

echo "Bundling $REF"
git -C "$REPO" merge-base --is-ancestor "$COMMIT" "$REF" \
    || { echo "error: $REF doesn't contain ${COMMIT:0:7}; git fetch first" >&2; exit 1; }
rm -f "$SSD/chord-notepad.bundle"
git -C "$REPO" bundle create "$SSD/chord-notepad.bundle" "$REF"
echo "$COMMIT" > "$SSD/chord-notepad.ref"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
gh run download "$RUN" -n ios-build-inputs -D "$TMP/inputs"
mv -f "$TMP/inputs/ios-build-inputs.tar.gz" "$SSD/ios-build-inputs.tar.gz"

if [ -f "$SSD/xcodegen.zip" ] && [ "$(sha256sum "$SSD/xcodegen.zip" | cut -d' ' -f1)" = "$XCODEGEN_SHA256" ]; then
    echo "xcodegen.zip $XCODEGEN_VERSION is already there"
else
    curl -fsSL --retry 3 -o "$TMP/xcodegen.zip" \
        "https://github.com/yonaskolb/XcodeGen/releases/download/$XCODEGEN_VERSION/xcodegen.zip"
    echo "$XCODEGEN_SHA256  $TMP/xcodegen.zip" | sha256sum -c - >/dev/null \
        || { echo "error: the downloaded xcodegen.zip doesn't match the pin" >&2; exit 1; }
    mv -f "$TMP/xcodegen.zip" "$SSD/xcodegen.zip"
fi

echo "$XCODE_VERSION" > "$SSD/xcode-version"
cp "$HERE/mac_bootstrap.sh" "$SSD/mac_bootstrap.sh"
chmod +x "$SSD/mac_bootstrap.sh"

(cd "$SSD" && sha256sum chord-notepad.bundle chord-notepad.ref ios-build-inputs.tar.gz xcodegen.zip \
    xcode-version mac_bootstrap.sh > SHA256SUMS)

for wanted in "Xcode_$XCODE_VERSION.xip" "*Simulator_Runtime*.dmg"; do
    found=""
    for match in "$SSD"/$wanted; do
        if [ -e "$match" ]; then found=$match; fi
    done
    if [ -n "$found" ]; then
        echo "found $(basename "$found") ($(du -h "$found" | cut -f1))"
    else
        echo "MISSING: $wanted (developer.apple.com/download/all, signed in with a free Apple Account;" \
             "the runtime must be the one for Xcode $XCODE_VERSION)"
        problems=1
    fi
done
echo "Free on the SSD: $(df -h "$SSD" | awk 'NR == 2 { print $4 }')"
ls -la "$SSD"
exit $problems

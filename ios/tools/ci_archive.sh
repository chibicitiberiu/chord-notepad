#!/bin/bash
# Archive and export the iOS app on CI (ios.yml's release lanes and the
# unsigned archive rehearsal; docs/IOS.md, "Release lanes").
#
#   ios/tools/ci_archive.sh archive <ChordNotepad.xcarchive> [--unsigned]
#   ios/tools/ci_archive.sh export <ChordNotepad.xcarchive> testflight|development <export-dir>
#   ios/tools/ci_archive.sh dsyms <ChordNotepad.xcarchive> <out-dir>
#
# archive: a Release build for generic/platform=iOS with automatic signing,
#   -allowProvisioningUpdates and the App Store Connect API key, so Xcode
#   fetches or makes the provisioning profile itself. --unsigned builds the
#   same archive with CODE_SIGNING_ALLOWED=NO and needs no secret.
# export: xcodebuild -exportArchive with packaging/ios/ExportOptions-<lane>.plist
#   (teamID filled in): testflight uploads to App Store Connect, development
#   writes the development-signed IPA.
# dsyms: the archive's dSYMs and a build-info.txt (version, build number,
#   commit, each dSYM's UUID) into <out-dir>, for ios/tools/symbolicate.sh.
#
# Environment: CN_BUILD_NUMBER (CFBundleVersion), and for signing
# ASC_KEY_PATH, ASC_KEY_ID, ASC_ISSUER_ID, APPLE_TEAM_ID.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MODE=${1:?usage: ci_archive.sh archive|export|dsyms <archive> ...}
ARCHIVE=${2:?usage: ci_archive.sh $MODE <archive> ...}
LOGS=${RUNNER_TEMP:-/tmp}

# add_auth: append the API key options to args (the caller's array).
add_auth() {
    : "${ASC_KEY_PATH:?}" "${ASC_KEY_ID:?}" "${ASC_ISSUER_ID:?}"
    args+=(-allowProvisioningUpdates -authenticationKeyPath "$ASC_KEY_PATH"
           -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID")
}

case "$MODE" in
    archive)
        build=${CN_BUILD_NUMBER:?set CN_BUILD_NUMBER}
        args=(-project "$ROOT/ios/ChordNotepad.xcodeproj" -scheme ChordNotepad -configuration Release
              -destination 'generic/platform=iOS' -archivePath "$ARCHIVE"
              -derivedDataPath "$ROOT/ios/build/DerivedData"
              MARKETING_VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")" CURRENT_PROJECT_VERSION="$build"
              CN_GIT_COMMIT="$(git -C "$ROOT" rev-parse --short HEAD)" CN_BUILD_DATE="$(date -u +%Y-%m-%d)")
        if [ "${3:-}" = --unsigned ]; then
            args+=(CODE_SIGNING_ALLOWED=NO)
        else
            : "${APPLE_TEAM_ID:?}"
            add_auth
            args+=(CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM="$APPLE_TEAM_ID")
        fi
        log="$LOGS/archive.log"
        set -o pipefail
        xcodebuild archive "${args[@]}" | tee "$log" | grep -E 'error:|warning: .*(sign|provision)|\*\* ' || true
        grep -q '\*\* ARCHIVE SUCCEEDED \*\*' "$log" || { tail -n 80 "$log"; exit 1; }
        app="$ARCHIVE/Products/Applications/ChordNotepad.app"
        plutil -p "$app/Info.plist" | grep -E 'CFBundle(Short)?Version|CFBundleIdentifier|CNGitCommit'
        if [ "${3:-}" != --unsigned ]; then
            codesign --display --verbose=2 "$app" 2>&1 | grep -E '^(Identifier|TeamIdentifier|Authority)=' || true
        fi
        ;;
    export)
        lane=${3:?testflight or development}
        out=${4:?export directory}
        : "${APPLE_TEAM_ID:?}"
        template="$ROOT/packaging/ios/ExportOptions-$lane.plist"
        [ -f "$template" ] || { echo "error: no $template" >&2; exit 2; }
        options="$LOGS/ExportOptions-$lane.plist"
        cp "$template" "$options"
        plutil -replace teamID -string "$APPLE_TEAM_ID" "$options"
        plutil -lint "$options"
        args=(-exportArchive -archivePath "$ARCHIVE" -exportOptionsPlist "$options" -exportPath "$out")
        add_auth
        log="$LOGS/export-$lane.log"
        set -o pipefail
        xcodebuild "${args[@]}" | tee "$log" | grep -E 'error:|Upload|EXPORT|\*\* ' || true
        grep -q '\*\* EXPORT SUCCEEDED \*\*' "$log" || { tail -n 80 "$log"; exit 1; }
        ls -la "$out"
        ;;
    dsyms)
        out=${3:?output directory}
        mkdir -p "$out/dSYMs"
        if [ -d "$ARCHIVE/dSYMs" ]; then
            ditto "$ARCHIVE/dSYMs" "$out/dSYMs"
        fi
        app="$ARCHIVE/Products/Applications/ChordNotepad.app"
        {
            echo "version: $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Info.plist")"
            echo "build: $(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app/Info.plist")"
            echo "commit: $(git -C "$ROOT" rev-parse HEAD)"
            echo "run: ${GITHUB_RUN_ID:-local} (attempt ${GITHUB_RUN_ATTEMPT:-1})"
            for dsym in "$out"/dSYMs/*.dSYM; do
                [ -e "$dsym" ] || continue
                dwarfdump --uuid "$dsym" | sed 's/^/dsym: /'
            done
            dwarfdump --uuid "$app/ChordNotepad" | sed 's/^/binary: /'
        } > "$out/build-info.txt"
        cat "$out/build-info.txt"
        ;;
    *)
        echo "unknown mode $MODE" >&2
        exit 2
        ;;
esac

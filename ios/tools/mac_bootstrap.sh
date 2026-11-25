#!/bin/bash
# Set up the borrowed MacBook for the iOS app in session S0 (docs/IOS.md,
# "Device sessions"), from files on a USB SSD only: nothing is downloaded,
# nothing signs in to anything.
#
#   /Volumes/<SSD>/mac_bootstrap.sh --ssd /Volumes/<SSD>             everything
#   /Volumes/<SSD>/mac_bootstrap.sh --ssd /Volumes/<SSD> --only extract   start xip early
#   /Volumes/<SSD>/mac_bootstrap.sh --ssd /Volumes/<SSD> --verify    build and run only
#   ... --dry-run                       print what would change, change nothing
#
# The SSD is filled on Linux by ios/tools/prepare_ssd.sh:
#   Xcode_<version>.xip                 from developer.apple.com/download/all
#   <iOS simulator runtime>.dmg         the same page, the runtime matching Xcode
#   xcodegen.zip                        the release ios.yml pins (checked here)
#   chord-notepad.bundle, chord-notepad.ref   a git bundle of main and its commit
#   ios-build-inputs.tar.gz             CI's prebuilt frameworks, Python bundle, guide
#   xcode-version, SHA256SUMS, mac_bootstrap.sh
#
# Steps, each skipped when already done (run it again after a failure):
#   preflight  macOS version (Xcode's minimum), Apple silicon, free disk, the SSD's files
#   extract    xip --expand the Xcode .xip into the work folder (20-40 min)
#   xcode      move it to /Applications/Xcode_<version>.app, accept the licence,
#              -runFirstLaunch (her admin password, through sudo)
#   runtime    simctl runtime add the .dmg unless that iOS runtime is there
#   repo       clone the bundle into the work folder (an existing clone is left alone)
#   xcodegen   unzip the pinned XcodeGen after checking its SHA-256
#   inputs     unpack ios-build-inputs.tar.gz into <repo>/ios/build
#   project    xcodegen generate
#   build      xcodebuild for an iPhone simulator
#   run        install, launch, wait for the app's startup.json, screenshot
#   device     devicectl list devices: her iPhone's UDID, model, iOS version
#   report     <report-dir>/report.txt (and devices.json, the build log, the
#              screenshot, the app's Diagnostics folder)
# --verify runs repo..report and only checks that Xcode and the runtime are
# installed.
#
# Xcode is used through DEVELOPER_DIR (also added to ~/.zprofile), never
# xcode-select, so her own setup doesn't change. Privileged steps use sudo; if
# this user isn't an administrator, --admin <her short user name> runs them
# through su (she types her password). Bash 3.2 (macOS's /bin/bash) and the
# BSD tools; ios.yml rehearses --verify on every run.
# The steps are called as step_<name> from the loop at the end.
# shellcheck disable=SC2329
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUNDLE_ID=com.tibich.chordnotepad
STEPS="preflight extract xcode runtime repo xcodegen inputs project build run device report"
VERIFY_STEPS="preflight repo xcodegen inputs project build run device report"

SSD=""
WORK="$HOME/ChordNotepad"
REPORT_DIR=""
DRY_RUN=0
VERIFY=0
ONLY=""
ADMIN_USER=""
XCODE_VERSION=""
LAUNCH_WAIT=${LAUNCH_WAIT:-240}

usage() {
    sed -n '2,44p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --ssd) SSD=${2:?--ssd needs a folder}; shift 2 ;;
        --workdir) WORK=${2:?}; shift 2 ;;
        --report-dir) REPORT_DIR=${2:?}; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --verify) VERIFY=1; shift ;;
        --only) ONLY=${2:?}; shift 2 ;;
        --admin) ADMIN_USER=${2:?}; shift 2 ;;
        --xcode-version) XCODE_VERSION=${2:?}; shift 2 ;;
        -h|--help) usage ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done
[ -n "$SSD" ] || { echo "error: --ssd <folder> is required" >&2; usage; }
[ -d "$SSD" ] || { echo "error: $SSD isn't a folder" >&2; exit 1; }

if [ -z "$XCODE_VERSION" ]; then
    if [ -f "$SSD/xcode-version" ]; then
        XCODE_VERSION=$(tr -d '[:space:]' < "$SSD/xcode-version")
    elif [ -f "$SCRIPT_DIR/../.xcode-version" ]; then
        XCODE_VERSION=$(tr -d '[:space:]' < "$SCRIPT_DIR/../.xcode-version")
    else
        echo "error: no xcode-version on the SSD; pass --xcode-version" >&2
        exit 1
    fi
fi
# CN_XCODE_APP: another place for Xcode (the tests use it).
XCODE_APP=${CN_XCODE_APP:-/Applications/Xcode_$XCODE_VERSION.app}
REPO="$WORK/chord-notepad"
XCODEGEN="$WORK/tools/xcodegen/bin/xcodegen"
if [ -z "$REPORT_DIR" ]; then
    REPORT_DIR="$SSD/session-reports/$(date +%Y%m%d-%H%M%S)"
fi
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/report.txt"
: > "$REPORT"
FAILED=0
UDID=""
SIM_APP=""

log() { echo "== $*"; }
warn() { echo "warning: $*" >&2; record warning "$*"; }
die() { echo "error: $*" >&2; record error "$*"; exit 1; }
# fail <message>: stop, or in a dry run note it, go on, and exit 1 at the end,
# so one dry run lists every problem.
fail() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "error: $*" >&2
        record error "$*"
        FAILED=1
    else
        die "$*"
    fi
}
record() { echo "$1: $2" >> "$REPORT"; }

# run <command...>: a command that changes something; printed, and not run
# in a dry run.
run() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "DRY: $*"
    else
        echo "+ $*"
        "$@"
    fi
}

is_admin() { id -Gn 2>/dev/null | tr ' ' '\n' | grep -qx admin; }

# as_admin <command...>: sudo, or su to her account when this one isn't an admin.
as_admin() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "DRY (admin): $*"
        return 0
    fi
    if is_admin || [ -z "$ADMIN_USER" ]; then
        echo "+ sudo $*"
        sudo "$@"
    else
        echo "+ su $ADMIN_USER -c sudo $*"
        su "$ADMIN_USER" -c "sudo $(printf '%q ' "$@")"
    fi
}

# version_ge <a> <b>: a >= b, numerically by dotted parts (bash 3.2).
version_ge() {
    local a=$1 b=$2 i x y
    for i in 1 2 3; do
        x=$(echo "$a" | cut -d. -f"$i"); y=$(echo "$b" | cut -d. -f"$i")
        x=${x:-0}; y=${y:-0}
        if [ "$x" -gt "$y" ]; then return 0; fi
        if [ "$x" -lt "$y" ]; then return 1; fi
    done
    return 0
}

# The oldest macOS each Xcode runs on (developer.apple.com/support/xcode,
# checked 2026-11-25). Add a line when ios/.xcode-version moves.
min_macos_for_xcode() {
    case "$1" in
        26.5|26.5.*) echo 26.2 ;;
        *) echo "" ;;
    esac
}

sha256_of() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        sha256sum "$1" | cut -d' ' -f1
    fi
}

ssd_file() {  # ssd_file <glob>: the first match on the SSD, or nothing
    local match
    for match in "$SSD"/$1; do
        if [ -e "$match" ]; then echo "$match"; return 0; fi
    done
    return 0
}

developer_dir() {
    if [ -d "$XCODE_APP/Contents/Developer" ]; then
        export DEVELOPER_DIR="$XCODE_APP/Contents/Developer"
    fi
}

xcode_installed() {
    local version
    [ -x "$XCODE_APP/Contents/Developer/usr/bin/xcodebuild" ] || return 1
    # Read it whole: with pipefail, `| head -n 1` would fail the check when
    # xcodebuild gets SIGPIPE (ios.yml's first rehearsal did).
    version=$("$XCODE_APP/Contents/Developer/usr/bin/xcodebuild" -version 2>/dev/null || true)
    [ "${version%%$'\n'*}" = "Xcode $XCODE_VERSION" ]
}

sdk_version() { xcrun --sdk iphonesimulator --show-sdk-version 2>/dev/null || true; }

runtime_installed() {
    local sdk
    sdk=$(sdk_version)
    [ -n "$sdk" ] && xcrun simctl list runtimes 2>/dev/null | grep -E "^iOS $sdk " | grep -vq unavailable
}

# The XcodeGen version and SHA-256 ios.yml pins, from the repo (or this script's own).
xcodegen_pin() {
    local action
    for action in "$REPO/.github/actions/ios-app-setup/action.yml" \
                  "$SCRIPT_DIR/../../.github/actions/ios-app-setup/action.yml"; do
        if [ -f "$action" ]; then
            sed -n "s/^ *$1: '\{0,1\}\([0-9A-Za-z.]*\)'\{0,1\}$/\1/p" "$action" | head -n 1
            return 0
        fi
    done
}

step_preflight() {
    local os arch macos minimum free need name file
    os=$(uname -s)
    record date "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    record xcode_wanted "$XCODE_VERSION"
    if [ "$os" != Darwin ]; then
        [ "$DRY_RUN" = 1 ] || die "this is $os, not macOS"
        warn "not macOS ($os): a dry run with whatever tools are on PATH"
    fi
    macos=$(sw_vers -productVersion)
    arch=$(uname -m)
    record macos "$macos"
    record cpu "$arch"
    [ "$arch" = arm64 ] || warn "not Apple silicon ($arch)"
    minimum=$(min_macos_for_xcode "$XCODE_VERSION")
    if [ -z "$minimum" ]; then
        warn "no known minimum macOS for Xcode $XCODE_VERSION: check developer.apple.com/support/xcode"
    elif ! version_ge "$macos" "$minimum"; then
        fail "Xcode $XCODE_VERSION needs macOS $minimum or later; this Mac has $macos"
    fi
    free=$(df -k "$HOME" | awk 'NR == 2 { print int($4 / 1048576) }')
    record free_disk_gb "$free"
    need=60
    if [ "$VERIFY" = 1 ]; then need=15; fi
    if [ "$free" -lt "$need" ]; then
        fail "only $free GB free, $need GB needed"
    fi
    for name in "Xcode_$XCODE_VERSION.xip" "*Simulator_Runtime*.dmg" xcodegen.zip chord-notepad.bundle \
            ios-build-inputs.tar.gz; do
        file=$(ssd_file "$name")
        if [ -n "$file" ]; then
            record ssd "$(basename "$file") $(du -h "$file" | cut -f1)"
        else
            case "$name" in
                *.xip|*.dmg) if [ "$VERIFY" = 1 ]; then continue; fi ;;
            esac
            warn "missing from the SSD: $name"
        fi
    done
    # --verify checks the installed Xcode and runtime instead of installing them.
    if [ "$VERIFY" = 1 ]; then
        developer_dir
        if ! xcode_installed; then
            fail "Xcode $XCODE_VERSION isn't in $XCODE_APP: run without --verify first"
        elif ! runtime_installed; then
            fail "no iOS $(sdk_version) simulator runtime: run without --verify first"
        else
            record xcode "$(xcodebuild -version | tr '\n' ' ')"
        fi
    fi
    if [ -f "$SSD/SHA256SUMS" ]; then
        if (cd "$SSD" && { if command -v shasum >/dev/null 2>&1; then shasum -a 256 -c SHA256SUMS;
                           else sha256sum -c SHA256SUMS; fi; }) > "$REPORT_DIR/sha256.log" 2>&1; then
            record ssd_checksums ok
        else
            cat "$REPORT_DIR/sha256.log" >&2
            fail "the SSD's files don't match SHA256SUMS (see $REPORT_DIR/sha256.log)"
        fi
    else
        warn "no SHA256SUMS on the SSD (ios/tools/prepare_ssd.sh writes one)"
    fi
}

step_extract() {
    local xip
    if xcode_installed; then log "Xcode $XCODE_VERSION is already in $XCODE_APP"; return; fi
    if [ -f "$WORK/xcode/.extracted" ]; then log "Xcode is already extracted in $WORK/xcode"; return; fi
    xip=$(ssd_file "Xcode_$XCODE_VERSION.xip")
    if [ -z "$xip" ]; then fail "no Xcode_$XCODE_VERSION.xip on the SSD"; return; fi
    run mkdir -p "$WORK/xcode"
    log "Expanding $xip (20-40 minutes; xip checks Apple's signature)"
    if [ "$DRY_RUN" = 1 ]; then
        echo "DRY: (cd $WORK/xcode && xip --expand $xip)"
    else
        (cd "$WORK/xcode" && xip --expand "$xip")
    fi
    run touch "$WORK/xcode/.extracted"
}

step_xcode() {
    if xcode_installed; then
        log "Xcode $XCODE_VERSION is in $XCODE_APP"
    elif [ "$VERIFY" = 1 ]; then
        fail "Xcode $XCODE_VERSION isn't in $XCODE_APP: run without --verify first"
        return
    else
        [ -d "$WORK/xcode/Xcode.app" ] || [ "$DRY_RUN" = 1 ] || die "extract first (--only extract)"
        as_admin mv "$WORK/xcode/Xcode.app" "$XCODE_APP"
        run rm -rf "$WORK/xcode"
    fi
    developer_dir
    local xcodebuild="$XCODE_APP/Contents/Developer/usr/bin/xcodebuild"
    if [ "$DRY_RUN" = 1 ] && [ ! -x "$xcodebuild" ]; then
        echo "DRY (admin): $xcodebuild -license accept; $xcodebuild -runFirstLaunch"
    else
        if "$xcodebuild" -license check >/dev/null 2>&1; then
            log "The Xcode licence is accepted"
        else
            as_admin "$xcodebuild" -license accept
        fi
        if "$xcodebuild" -checkFirstLaunchStatus >/dev/null 2>&1; then
            log "Xcode's first launch tasks are done"
        else
            as_admin "$xcodebuild" -runFirstLaunch
        fi
        record xcode "$("$xcodebuild" -version | tr '\n' ' ')"
    fi
    if ! grep -qs "DEVELOPER_DIR=$XCODE_APP" "$HOME/.zprofile"; then
        if [ "$DRY_RUN" = 1 ]; then
            echo "DRY: echo 'export DEVELOPER_DIR=$XCODE_APP/Contents/Developer' >> ~/.zprofile"
        else
            echo "export DEVELOPER_DIR=$XCODE_APP/Contents/Developer" >> "$HOME/.zprofile"
        fi
    fi
}

step_runtime() {
    local dmg
    developer_dir
    if runtime_installed; then
        log "The iOS $(sdk_version) simulator runtime is installed"
    elif [ "$VERIFY" = 1 ]; then
        fail "no iOS $(sdk_version) simulator runtime: run without --verify first"
    else
        dmg=$(ssd_file "*Simulator_Runtime*.dmg")
        if [ -n "$dmg" ]; then
            run xcrun simctl runtime add "$dmg"
        else
            fail "no simulator runtime .dmg on the SSD"
        fi
    fi
    xcrun simctl list runtimes > "$REPORT_DIR/runtimes.txt" 2>&1 || true
    record runtimes "$(grep -c '^iOS' "$REPORT_DIR/runtimes.txt" || true) iOS"
}

step_repo() {
    local commit
    developer_dir
    if [ -d "$REPO/.git" ]; then
        log "$REPO exists; left as it is"
        record repo "$(xcrun git -C "$REPO" rev-parse --short HEAD) $(xcrun git -C "$REPO" status --porcelain | wc -l | tr -d ' ') changed files"
        return
    fi
    commit=""
    if [ -f "$SSD/chord-notepad.ref" ]; then commit=$(tr -d '[:space:]' < "$SSD/chord-notepad.ref"); fi
    if [ ! -f "$SSD/chord-notepad.bundle" ]; then fail "no chord-notepad.bundle on the SSD"; return; fi
    if [ -z "$commit" ]; then
        commit=$(xcrun git bundle list-heads "$SSD/chord-notepad.bundle" 2>/dev/null | head -n 1 | cut -d' ' -f1 || true)
        if [ -z "$commit" ]; then fail "chord-notepad.bundle has no commit to check out"; return; fi
    fi
    # init and fetch rather than clone: the bundle's ref is origin/main,
    # which a clone wouldn't take.
    run mkdir -p "$WORK"
    run xcrun git init -q "$REPO"
    run xcrun git -C "$REPO" fetch -q "$SSD/chord-notepad.bundle" "+refs/*:refs/remotes/ssd/*"
    if [ "$DRY_RUN" = 0 ] && ! xcrun git -C "$REPO" cat-file -e "$commit^{commit}" 2>/dev/null; then
        rm -rf "$REPO"
        fail "chord-notepad.bundle has no branch holding $commit (bundle a ref, as prepare_ssd.sh does)"
        return
    fi
    run xcrun git -C "$REPO" checkout -q -B main "$commit"
    if [ "$DRY_RUN" = 0 ]; then
        record repo "$(xcrun git -C "$REPO" rev-parse --short HEAD) (cloned from the SSD)"
    fi
}

step_xcodegen() {
    local version sha zip got
    version=$(xcodegen_pin XCODEGEN_VERSION)
    sha=$(xcodegen_pin XCODEGEN_SHA256)
    if [ -z "$version" ] || [ -z "$sha" ]; then
        if [ "$DRY_RUN" = 1 ]; then warn "no repo yet to read XcodeGen's pin from"; return; fi
        die "can't read XcodeGen's pin from .github/actions/ios-app-setup/action.yml"
    fi
    if [ -x "$XCODEGEN" ] && "$XCODEGEN" version 2>/dev/null | grep -q "$version"; then
        log "XcodeGen $version is in $XCODEGEN"
    else
        zip="$SSD/xcodegen.zip"
        if [ ! -f "$zip" ]; then fail "no xcodegen.zip on the SSD"; return; fi
        got=$(sha256_of "$zip")
        if [ "$got" != "$sha" ]; then fail "xcodegen.zip's SHA-256 is $got, ios.yml pins $sha"; return; fi
        run mkdir -p "$WORK/tools"
        run unzip -q -o "$zip" -d "$WORK/tools"
    fi
    record xcodegen "$version"
}

step_inputs() {
    local tarball marker built head
    tarball="$SSD/ios-build-inputs.tar.gz"
    if [ ! -f "$tarball" ]; then fail "no ios-build-inputs.tar.gz on the SSD"; return; fi
    marker="$REPO/ios/build/.inputs-$(sha256_of "$tarball" | cut -c1-16)"
    if [ -f "$marker" ]; then
        log "The build inputs are unpacked"
    else
        run mkdir -p "$REPO/ios/build"
        run rm -rf "$REPO/ios/build/Frameworks" "$REPO/ios/build/python-bundle" "$REPO/ios/build/help"
        run tar -xzf "$tarball" -C "$REPO/ios/build"
        run touch "$marker"
    fi
    if [ "$DRY_RUN" = 0 ]; then
        built=unknown
        if [ -f "$REPO/ios/build/INPUTS_COMMIT" ]; then built=$(tr -d '[:space:]' < "$REPO/ios/build/INPUTS_COMMIT"); fi
        head=$(xcrun git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)
        record inputs_commit "$built"
        if [ "$built" != "$head" ]; then
            warn "the build inputs are from $built, the repo is at $head: the app bundles that commit's core"
        fi
    fi
}

step_project() {
    local python
    developer_dir
    # The build phases run python3 (Xcode's own on a Mac without other Pythons).
    python=$(command -v python3.14 || xcrun --find python3 2>/dev/null || true)
    record python3 "${python:-missing}; Xcode's: $(xcrun --find python3 2>/dev/null || echo none)"
    [ -n "$python" ] || fail "no python3 for the build phases (Xcode's is xcrun --find python3)"
    run "$XCODEGEN" generate --spec "$REPO/ios/project.yml"
}

pick_simulator() {
    local runtime sdk
    UDID=$(xcrun python3 "$REPO/ios/tools/ci_simulators.py" 2>/dev/null | sed -n 's/^IPHONE_UDID=//p' | head -n 1 || true)
    if [ -z "$UDID" ]; then
        sdk=$(sdk_version)
        runtime="com.apple.CoreSimulator.SimRuntime.iOS-${sdk//./-}"
        if [ "$DRY_RUN" = 1 ]; then
            echo "DRY: xcrun simctl create 'iPhone 17' com.apple.CoreSimulator.SimDeviceType.iPhone-17 $runtime"
            UDID=dry-run-udid
        else
            UDID=$(xcrun simctl create "iPhone 17" com.apple.CoreSimulator.SimDeviceType.iPhone-17 "$runtime")
        fi
    fi
    record simulator "$UDID"
}

step_build() {
    local log_file="$REPORT_DIR/build.log" commit
    developer_dir
    pick_simulator
    if [ "$DRY_RUN" = 1 ]; then
        echo "DRY: xcodebuild build -project $REPO/ios/ChordNotepad.xcodeproj -scheme ChordNotepad -destination id=$UDID"
        return
    fi
    commit=$(xcrun git -C "$REPO" rev-parse --short HEAD)
    log "Building for the simulator (log: $log_file)"
    xcodebuild build -project "$REPO/ios/ChordNotepad.xcodeproj" -scheme ChordNotepad \
        -destination "id=$UDID" -derivedDataPath "$REPO/ios/build/DerivedData" \
        MARKETING_VERSION="$(cat "$REPO/VERSION")" CN_GIT_COMMIT="$commit" CN_BUILD_DATE="$(date -u +%Y-%m-%d)" \
        > "$log_file" 2>&1 || true
    if grep -q '\*\* BUILD SUCCEEDED \*\*' "$log_file"; then
        record build ok
    else
        grep -E 'error:' "$log_file" | head -n 20 >&2 || true
        tail -n 40 "$log_file" >&2
        die "the simulator build failed (see $log_file)"
    fi
    SIM_APP="$REPO/ios/build/DerivedData/Build/Products/Debug-iphonesimulator/ChordNotepad.app"
}

step_run() {
    local data waited=0
    if [ "$DRY_RUN" = 1 ]; then
        echo "DRY: xcrun simctl boot/install/launch $BUNDLE_ID on ${UDID:-the simulator}; screenshot"
        return
    fi
    [ -n "$UDID" ] || pick_simulator
    [ -n "$SIM_APP" ] || SIM_APP="$REPO/ios/build/DerivedData/Build/Products/Debug-iphonesimulator/ChordNotepad.app"
    xcrun simctl boot "$UDID" 2>/dev/null || true
    xcrun simctl bootstatus "$UDID" -b > /dev/null
    xcrun simctl uninstall "$UDID" "$BUNDLE_ID" 2>/dev/null || true
    xcrun simctl install "$UDID" "$SIM_APP"
    data=$(xcrun simctl get_app_container "$UDID" "$BUNDLE_ID" data)
    xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID"
    while [ ! -f "$data/Documents/Diagnostics/startup.json" ] && [ "$waited" -lt "$LAUNCH_WAIT" ]; do
        sleep 2
        waited=$((waited + 2))
    done
    sleep 2
    xcrun simctl io "$UDID" screenshot "$REPORT_DIR/simulator.png" >/dev/null 2>&1 || warn "no screenshot"
    if [ -f "$data/Documents/Diagnostics/startup.json" ]; then
        record launch "ok after ${waited}s: $(tr -d '\n' < "$data/Documents/Diagnostics/startup.json")"
    else
        FAILED=1
        record launch "no startup.json after ${LAUNCH_WAIT}s"
        echo "error: the app didn't write startup.json within ${LAUNCH_WAIT}s" >&2
    fi
    rm -rf "$REPORT_DIR/diagnostics"
    cp -R "$data/Documents/Diagnostics" "$REPORT_DIR/diagnostics" 2>/dev/null || true
    xcrun simctl terminate "$UDID" "$BUNDLE_ID" 2>/dev/null || true
}

step_device() {
    developer_dir
    if [ "$DRY_RUN" = 1 ] && ! command -v xcrun >/dev/null 2>&1; then
        echo "DRY: xcrun devicectl list devices"
        return
    fi
    if ! xcrun devicectl list devices --json-output "$REPORT_DIR/devices.json" > "$REPORT_DIR/devices.txt" 2>&1; then
        warn "devicectl list devices failed (see devices.txt)"
        return
    fi
    # One line per iPhone or iPad: its UDID (a secret: keep it off the repo),
    # model, iOS version, pairing and Developer Mode.
    xcrun python3 - "$REPORT_DIR/devices.json" <<'PY' >> "$REPORT" || warn "couldn't read devices.json"
import json, sys
devices = json.load(open(sys.argv[1])).get("result", {}).get("devices", [])
shown = 0
for d in devices:
    hw, props, conn = d.get("hardwareProperties", {}), d.get("deviceProperties", {}), d.get("connectionProperties", {})
    if hw.get("platform") not in ("iOS", "iPadOS"):
        continue
    shown += 1
    print("device: udid %s; %s (%s); iOS %s; pairing %s; transport %s; developer mode %s" % (
        hw.get("udid"), hw.get("marketingName"), hw.get("productType"), props.get("osVersionNumber"),
        conn.get("pairingState"), conn.get("transportType"), props.get("developerModeStatus")))
if not shown:
    print("device: none connected (plug in the iPhone, unlock it, tap Trust)")
PY
}

step_report() {
    log "Report: $REPORT"
    cat "$REPORT"
}

wanted() {  # wanted <step>: in this run's list
    local list=$STEPS
    if [ "$VERIFY" = 1 ]; then list=$VERIFY_STEPS; fi
    if [ -n "$ONLY" ]; then list=$ONLY; fi
    case " $list " in *" $1 "*) return 0 ;; esac
    return 1
}

for step in $STEPS; do
    if wanted "$step"; then
        log "$step"
        "step_$step"
    fi
done
exit $FAILED

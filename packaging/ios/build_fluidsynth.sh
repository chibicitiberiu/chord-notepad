#!/usr/bin/env bash
# Build FluidSynth.xcframework for the iOS app (docs/IOS.md, "CI"), from the
# same pinned source as the macOS build (packaging/macos/build_fluidsynth.sh).
#
#   packaging/ios/build_fluidsynth.sh <out-dir>
#
# Writes <out-dir>/FluidSynth.xcframework with two slices, device arm64 and
# simulator arm64. Each holds a dynamic FluidSynth.framework: the library is
# shipped under the LGPL as a framework the app loads at run time (BACKLOG.md,
# iOS licensing), and pyFluidSynth dlopens it by path (CHORD_NOTEPAD_LIBFLUIDSYNTH).
#
# Audio goes through FluidSynth's iOS CoreAudio driver (RemoteIO, with its own
# AVAudioSession setup in fluid_coreaudio_avaudiosession.m); the macOS HAL
# path must not be picked, and the build fails if it is. No CoreMIDI, no
# libsndfile, no GLib (C++11 threads), no network shell, no signalsmith: the
# framework links only the system's libraries.
set -euo pipefail

OUT=${1:?usage: build_fluidsynth.sh <out-dir>}
# Keep in step with IPHONEOS_DEPLOYMENT_TARGET in ios/project.yml.
MIN_IOS=${MIN_IOS:-17.0}
BUNDLE_ID=org.fluidsynth.FluidSynth

FLUIDSYNTH_VERSION=2.6.1
FLUIDSYNTH_URL=https://github.com/FluidSynth/fluidsynth/archive/refs/tags/v$FLUIDSYNTH_VERSION.tar.gz
FLUIDSYNTH_SHA256=3d258a3bf97cc20c59eeebfe62c2432fae88adda74d3ad098681c76e0ebf446b
# Git submodule the release tarball leaves out (pinned at v2.6.1)
GCEM_URL=https://github.com/kthohr/gcem/archive/012ae73c6d0a2cb09ffe86475f5c6fba3926e200.tar.gz
GCEM_SHA256=34ab0ee87a9eb26d3087fa9b49c2572ea8ee03db0c9705b83648301a3a3fc172

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

fetch() {
    curl -fsSL --retry 3 -o "$2" "$1"
    echo "$3  $2" | shasum -a 256 -c -
}

fetch "$FLUIDSYNTH_URL" "$WORK/fluidsynth.tar.gz" "$FLUIDSYNTH_SHA256"
fetch "$GCEM_URL" "$WORK/gcem.tar.gz" "$GCEM_SHA256"
mkdir -p "$WORK/src/gcem"
tar -xzf "$WORK/fluidsynth.tar.gz" -C "$WORK/src" --strip-components=1
tar -xzf "$WORK/gcem.tar.gz" -C "$WORK/src/gcem" --strip-components=1

# build_slice <sdk> <platform name for CFBundleSupportedPlatforms>
build_slice() {
    local sdk=$1 platform=$2
    local build="$WORK/build-$sdk"
    # CMAKE_TRY_COMPILE_TARGET_TYPE: the feature checks build static
    # libraries, since an iOS executable can't be linked unsigned here.
    # CMAKE_MACOSX_BUNDLE: CMake makes every iOS executable an app bundle,
    # and FluidSynth's install rule for its command-line program has no
    # bundle destination (only the library is built anyway).
    cmake -S "$WORK/src" -B "$build" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_SYSTEM_NAME=iOS \
        -DCMAKE_OSX_SYSROOT="$sdk" \
        -DCMAKE_OSX_ARCHITECTURES=arm64 \
        -DCMAKE_OSX_DEPLOYMENT_TARGET="$MIN_IOS" \
        -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
        -DCMAKE_MACOSX_BUNDLE=OFF \
        -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-headerpad_max_install_names" \
        -DCMAKE_FIND_FRAMEWORK=LAST \
        -DBUILD_SHARED_LIBS=ON \
        -Dosal=cpp11 \
        -Denable-framework=OFF \
        -Denable-coreaudio=ON \
        -Denable-coremidi=OFF \
        -Denable-alsa=OFF \
        -Denable-dbus=OFF \
        -Denable-jack=OFF \
        -Denable-ladspa=OFF \
        -Denable-libinstpatch=OFF \
        -Denable-libsndfile=OFF \
        -Denable-midishare=OFF \
        -Denable-network=OFF \
        -Denable-ipv6=OFF \
        -Denable-openmp=OFF \
        -Denable-oss=OFF \
        -Denable-pipewire=OFF \
        -Denable-portaudio=OFF \
        -Denable-pulseaudio=OFF \
        -Denable-readline=OFF \
        -Denable-sdl3=OFF \
        -Denable-signalsmith=OFF
    cmake --build "$build" --target libfluidsynth --parallel "$(sysctl -n hw.ncpu)"

    # The iOS driver, not the macOS one.
    grep -q '^#define COREAUDIO_SUPPORT 1' "$build/config.h" || {
        echo "FluidSynth ($sdk) was configured without CoreAudio:" >&2
        grep -n COREAUDIO "$build/config.h" >&2 || true
        exit 1
    }
    if grep -q '^#define COREAUDIO_SUPPORT_HAL' "$build/config.h"; then
        echo "FluidSynth ($sdk) took the macOS CoreAudio HAL path; iOS needs RemoteIO" >&2
        exit 1
    fi

    local dylib
    dylib=$(find "$build/src" -name 'libfluidsynth*.dylib' -type f | head -n 1)
    test -n "$dylib"
    local framework="$WORK/slices/$sdk/FluidSynth.framework"
    mkdir -p "$framework"
    cp "$dylib" "$framework/FluidSynth"
    install_name_tool -id @rpath/FluidSynth.framework/FluidSynth "$framework/FluidSynth"
    cat > "$framework/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>en</string>
	<key>CFBundleExecutable</key>
	<string>FluidSynth</string>
	<key>CFBundleIdentifier</key>
	<string>$BUNDLE_ID</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>FluidSynth</string>
	<key>CFBundlePackageType</key>
	<string>FMWK</string>
	<key>CFBundleShortVersionString</key>
	<string>$FLUIDSYNTH_VERSION</string>
	<key>CFBundleVersion</key>
	<string>$FLUIDSYNTH_VERSION</string>
	<key>CFBundleSupportedPlatforms</key>
	<array>
		<string>$platform</string>
	</array>
	<key>MinimumOSVersion</key>
	<string>$MIN_IOS</string>
</dict>
</plist>
PLIST
    plutil -lint "$framework/Info.plist"

    echo "Built $framework:"
    file "$framework/FluidSynth"
    otool -L "$framework/FluidSynth"
    # The first line is the binary's name, the second its own install name;
    # every dependency after them must come with iOS.
    local foreign
    foreign=$(otool -L "$framework/FluidSynth" | tail -n +3 | awk '{print $1}' \
        | grep -v -E '^(/usr/lib/|/System/Library/)' || true)
    if [ -n "$foreign" ]; then
        echo "FluidSynth links libraries iOS doesn't ship:" >&2
        echo "$foreign" >&2
        exit 1
    fi
    otool -L "$framework/FluidSynth" | grep -q '/AVFoundation.framework/' || {
        echo "FluidSynth doesn't link AVFoundation: the iOS audio session code is missing" >&2
        exit 1
    }
    # The deployment target and platform the binary was built for.
    otool -l "$framework/FluidSynth" | grep -A4 LC_BUILD_VERSION | grep -E 'platform|minos'
}

build_slice iphoneos iPhoneOS
build_slice iphonesimulator iPhoneSimulator

mkdir -p "$OUT"
rm -rf "$OUT/FluidSynth.xcframework"
xcodebuild -create-xcframework \
    -framework "$WORK/slices/iphoneos/FluidSynth.framework" \
    -framework "$WORK/slices/iphonesimulator/FluidSynth.framework" \
    -output "$OUT/FluidSynth.xcframework"
echo "Wrote $OUT/FluidSynth.xcframework"

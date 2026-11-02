#!/usr/bin/env bash
# Build libfluidsynth for the macOS app bundle, from the same pinned source as
# the Flatpak (packaging/flatpak/*.yml, resources/licenses/components.json).
#
#   packaging/macos/build_fluidsynth.sh <prefix>
#
# Installs <prefix>/lib/libfluidsynth.3.dylib. FluidSynth 2.6 uses C++11
# threads instead of GLib, and every optional backend but CoreAudio and
# CoreMIDI is off, so the library links only the system's own libraries and
# frameworks: the app needs nothing from Homebrew. The build fails if it links
# anything else. Builds for the runner's CPU (arm64 or x86_64).
set -euo pipefail

PREFIX=${1:?usage: build_fluidsynth.sh <prefix>}
# Keep in step with LSMinimumSystemVersion in chord-notepad.spec.
export MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-11.0}

FLUIDSYNTH_URL=https://github.com/FluidSynth/fluidsynth/archive/refs/tags/v2.6.1.tar.gz
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

# Off: every backend that could pick up a Homebrew library on the runner, the
# sound-file writer's libsndfile (the app never renders to a file), and the
# optional limiter/reverb engine (its CMake fetches more repos; the Windows
# build has none of it either).
cmake -S "$WORK/src" -B "$WORK/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_FIND_FRAMEWORK=LAST \
    -Dosal=cpp11 \
    -Denable-framework=OFF \
    -Denable-coreaudio=ON \
    -Denable-coremidi=ON \
    -Denable-dbus=OFF \
    -Denable-jack=OFF \
    -Denable-ladspa=OFF \
    -Denable-libinstpatch=OFF \
    -Denable-libsndfile=OFF \
    -Denable-midishare=OFF \
    -Denable-openmp=OFF \
    -Denable-pipewire=OFF \
    -Denable-portaudio=OFF \
    -Denable-pulseaudio=OFF \
    -Denable-readline=OFF \
    -Denable-sdl3=OFF \
    -Denable-signalsmith=OFF
cmake --build "$WORK/build" --parallel "$(sysctl -n hw.ncpu)"
cmake --install "$WORK/build"

LIB="$PREFIX/lib/libfluidsynth.3.dylib"
test -f "$LIB"
echo "Built $LIB:"
file "$LIB"
otool -L "$LIB"
# The first line is the library's own install name; every dependency after it
# must come with macOS.
foreign=$(otool -L "$LIB" | tail -n +3 | awk '{print $1}' | grep -v -E '^(/usr/lib/|/System/Library/)' || true)
if [ -n "$foreign" ]; then
    echo "libfluidsynth links libraries macOS doesn't ship:" >&2
    echo "$foreign" >&2
    exit 1
fi

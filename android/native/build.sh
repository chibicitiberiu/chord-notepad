#!/usr/bin/env bash
# Cross-compile FluidSynth and its dependencies for Android from the pinned
# submodules in this directory.
#
# Mirrors upstream FluidSynth's Android CI (.azure/azure-pipelines-android.yml
# and cmake-android.yml at v2.6.1): NDK 27.3.13750724, API 24, shared libs,
# c++_shared STL, -Denable-oboe=1 -Denable-opensles=1, 16 KB max page size.
# Differences, all for reproducibility or offline builds:
#   - CMake comes from the SDK (pinned version below), not the host, and uses Ninja;
#   - the signalsmith reverb/limiter dependencies come from submodules
#     (FETCHCONTENT_FULLY_DISCONNECTED) instead of a configure-time git clone;
#   - source and build paths are mapped out of the binaries (-ffile-prefix-map)
#     and DEFAULT_SOUNDFONT is fixed, so the output doesn't depend on where the
#     checkout lives;
#   - git is hidden from FLAC's and opus's CMake (they stamp `git describe` into
#     the library), so shallow CI clones and full local clones build the same bytes;
#   - libsndfile's MPEG support is off explicitly (upstream has no mpg123/lame,
#     so it's off there too, but by not finding them).
#
# Usage:
#   android/native/build.sh [--abis arm64-v8a,x86_64] [--out DIR] [--jobs N] [--force]
#
# Output: DIR/<abi>/lib/*.so (the libraries the APK ships, unstripped; AGP
# strips them). DIR defaults to $CHORD_NOTEPAD_ANDROID_BUILD_ROOT/<checkout>/native,
# the same per-checkout directory scheme Gradle uses (android/settings.gradle.kts),
# or android/build/native when that variable is unset.
#
# A stamp per ABI records the inputs (this script, toolchain versions, every
# submodule's commit and local diff); when it matches, the ABI is skipped.
#
# Needs: ANDROID_HOME (source android/local.env), the submodules checked out
# (see docs/ANDROID.md), host make/pkg-config. Installs the pinned NDK and CMake
# through sdkmanager when missing.
set -euo pipefail

NDK_VERSION=27.3.13750724
CMAKE_VERSION=3.31.6
ANDROID_API=24
OBOE_VERSION=1.10.0
# Keep in step with the opus submodule's tag: CI's shallow submodule clones have
# no tags, so opus's CMake can't ask git for it (see the cmi opus call below).
OPUS_VERSION=1.5.2

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(dirname "$HERE")"

ABIS="arm64-v8a,x86_64"
OUT=""
JOBS=4
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --abis) ABIS="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --jobs) JOBS="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$OUT" ]; then
    if [ -n "${CHORD_NOTEPAD_ANDROID_BUILD_ROOT:-}" ]; then
        checkout="${ANDROID_DIR#/}"
        OUT="$CHORD_NOTEPAD_ANDROID_BUILD_ROOT/${checkout//\//_}/native"
    else
        OUT="$ANDROID_DIR/build/native"
    fi
fi

: "${ANDROID_HOME:?set ANDROID_HOME (source android/local.env)}"
NDK="$ANDROID_HOME/ndk/$NDK_VERSION"
CMAKE_DIR="$ANDROID_HOME/cmake/$CMAKE_VERSION"

sdk_install() {
    local sdkmanager="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
    [ -x "$sdkmanager" ] || { echo "sdkmanager not found at $sdkmanager" >&2; exit 1; }
    echo ">> sdkmanager --install $1"
    "$sdkmanager" --install "$1" >/dev/null
}
[ -f "$NDK/build/cmake/android.toolchain.cmake" ] || sdk_install "ndk;$NDK_VERSION"
[ -x "$CMAKE_DIR/bin/cmake" ] || sdk_install "cmake;$CMAKE_VERSION"
CMAKE="$CMAKE_DIR/bin/cmake"
NINJA="$CMAKE_DIR/bin/ninja"

# Sources: name, path, expected tag (checked so a stray checkout can't slip in).
SOURCES=(
    "ogg ogg v1.3.6"
    "vorbis vorbis v1.3.7"
    "flac flac 1.4.3"
    "opus opus v1.5.2"
    "libsndfile libsndfile 1.2.2"
    "oboe oboe $OBOE_VERSION"
    "fluidsynth fluidsynth v2.6.1"
    "signalsmith-linear signalsmith-linear 0.3.1"
    "signalsmith-dsp signalsmith-dsp v1.7.1"
    "signalsmith-hilbert signalsmith-hilbert 1.0.0"
)
# FluidSynth's own submodules that the build needs (not test/manual, the
# test data). Without gcem its CMake would download it at configure time.
FS_SUBMODULES=(gcem signalsmith-audio-basics)

missing=0
for entry in "${SOURCES[@]}"; do
    read -r _ path tag <<<"$entry"
    if [ ! -e "$HERE/$path/CMakeLists.txt" ]; then
        echo "missing source: android/native/$path" >&2; missing=1; continue
    fi
    if ! git -C "$HERE/$path" describe --tags --exact-match HEAD 2>/dev/null | grep -qx "$tag"; then
        # A shallow clone without the tag ref still has the pinned commit; fall back
        # to comparing with the superproject's gitlink.
        want="$(git -C "$ANDROID_DIR/.." ls-tree HEAD "android/native/$path" | awk '{print $3}')"
        have="$(git -C "$HERE/$path" rev-parse HEAD)"
        if [ -n "$want" ] && [ "$want" != "$have" ]; then
            echo "android/native/$path is at $have, expected $tag ($want)" >&2; missing=1
        fi
    fi
done
for sub in "${FS_SUBMODULES[@]}"; do
    [ -n "$(ls -A "$HERE/fluidsynth/$sub" 2>/dev/null)" ] || { echo "missing source: android/native/fluidsynth/$sub" >&2; missing=1; }
done
if [ "$missing" = 1 ]; then
    cat >&2 <<EOF

Check out the native sources first (shallow, ~35 MB of git objects):
  git submodule update --init --depth 1 android/native
  git -C android/native/fluidsynth submodule update --init --depth 1 ${FS_SUBMODULES[*]}
EOF
    exit 1
fi

fingerprint() {
    {
        sha256sum "$HERE/build.sh"
        echo "ndk=$NDK_VERSION cmake=$CMAKE_VERSION api=$ANDROID_API"
        for entry in "${SOURCES[@]}"; do
            read -r _ path _ <<<"$entry"
            echo "$path $(git -C "$HERE/$path" rev-parse HEAD) $(git -C "$HERE/$path" diff HEAD | sha256sum)"
        done
        for sub in "${FS_SUBMODULES[@]}"; do
            echo "fluidsynth/$sub $(git -C "$HERE/fluidsynth/$sub" rev-parse HEAD)"
        done
    } | sha256sum | cut -d' ' -f1
}
FP="$(fingerprint)"

# Keep the caller's environment out of the build.
unset CFLAGS CXXFLAGS CPPFLAGS LDFLAGS CC CXX AR LD PKG_CONFIG_PATH PKG_CONFIG_SYSROOT_DIR

LIBS=(libfluidsynth.so liboboe.so libsndfile.so libFLAC.so libogg.so libopus.so
      libvorbis.so libvorbisenc.so libvorbisfile.so)

build_abi() {
    local abi="$1"
    local root="$OUT/$abi"
    local prefix="$root/prefix"
    local work="$root/work"
    local stamp="$root/stamp"

    if [ "$FORCE" = 0 ] && [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$FP" ]; then
        echo ">> $abi: up to date ($root/lib)"
        return
    fi
    echo ">> $abi: building into $root"
    rm -rf "$root"
    mkdir -p "$prefix/lib/pkgconfig" "$work"

    # Upstream's flags (cmake-android.yml), minus the explicit sysroot paths the
    # NDK toolchain file already sets. The prefix maps make the output
    # independent of the checkout and build locations; the NDK map makes it
    # independent of where the SDK lives.
    local cflags="-fPIE -fPIC -I$prefix/include -Werror=implicit-function-declaration"
    cflags+=" -ffile-prefix-map=$HERE=/native-src -ffile-prefix-map=$root=/native-build"
    cflags+=" -ffile-prefix-map=$NDK=/ndk"
    local ldflags="-Wl,-z,max-page-size=16384 -L$prefix/lib"

    export PKG_CONFIG_LIBDIR="$prefix/lib/pkgconfig"
    export PKG_CONFIG_PATH="$PKG_CONFIG_LIBDIR"

    cm() {  # cm <source dir> <build name> [extra cmake args...]
        local src="$1" name="$2"; shift 2
        echo ">> $abi: $name"
        "$CMAKE" -S "$src" -B "$work/$name" -G Ninja \
            -DCMAKE_MAKE_PROGRAM="$NINJA" \
            -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
            -DCMAKE_BUILD_TYPE=RelWithDebInfo \
            -DANDROID_ABI="$abi" \
            -DANDROID_PLATFORM="android-$ANDROID_API" \
            -DANDROID_STL=c++_shared \
            -DCMAKE_C_FLAGS="$cflags" \
            -DCMAKE_CXX_FLAGS="$cflags" \
            -DCMAKE_SHARED_LINKER_FLAGS="$ldflags" \
            -DCMAKE_MODULE_LINKER_FLAGS="$ldflags" \
            -DCMAKE_REQUIRED_FLAGS="$cflags" \
            -DCMAKE_INSTALL_PREFIX="$prefix" \
            -DCMAKE_STAGING_PREFIX="$prefix" \
            -DCMAKE_INSTALL_LIBDIR=lib \
            -DBUILD_SHARED_LIBS=1 \
            -DBUILD_TESTING=0 \
            -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
            "$@" >"$work/$name.configure.log" 2>&1 \
            || { tail -40 "$work/$name.configure.log" >&2; return 1; }
        "$CMAKE" --build "$work/$name" -j "$JOBS" >"$work/$name.build.log" 2>&1 \
            || { tail -40 "$work/$name.build.log" >&2; return 1; }
    }
    cmi() { cm "$@" && "$CMAKE" --install "$work/$2" >"$work/$2.install.log" 2>&1; }

    cmi "$HERE/ogg" ogg -DINSTALL_DOCS=0
    cmi "$HERE/vorbis" vorbis
    cmi "$HERE/flac" flac -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=1 -DWITH_ASM=0 \
        -DHAVE_GIT=OFF \
        -DBUILD_CXXLIBS=0 -DBUILD_PROGRAMS=0 -DBUILD_EXAMPLES=0 -DBUILD_DOCS=0 \
        -DINSTALL_MANPAGES=0
    cmi "$HERE/opus" opus -DCMAKE_DISABLE_FIND_PACKAGE_Git=ON -DOPUS_PACKAGE_VERSION="$OPUS_VERSION" \
        -DBUILD_PROGRAMS=0 -DOPUS_MAY_HAVE_NEON=1 \
        -DCMAKE_C_STANDARD=99 -DCMAKE_C_STANDARD_REQUIRED=1
    cmi "$HERE/libsndfile" libsndfile -DBUILD_PROGRAMS=0 -DBUILD_EXAMPLES=0 \
        -DENABLE_MPEG=0 -DENABLE_CPACK=0 -DENABLE_EXTERNAL_LIBS=1

    # Oboe has no install rule upstream uses; copy the library and headers.
    cm "$HERE/oboe" oboe
    cp "$work/oboe/liboboe.so" "$prefix/lib/"
    cp -r "$HERE/oboe/include/oboe" "$prefix/include/"
    cat >"$prefix/lib/pkgconfig/oboe-1.0.pc" <<EOF
prefix=$prefix
exec_prefix=\${prefix}
libdir=\${prefix}/lib
includedir=\${prefix}/include

Name: Oboe
Description: Oboe library
Version: $OBOE_VERSION
Libs: -L\${libdir} -loboe -landroid -llog
Cflags: -I\${includedir}
EOF

    cmi "$HERE/fluidsynth" fluidsynth \
        -Denable-opensles=1 -Denable-floats=1 -Denable-oboe=1 -Denable-dbus=0 \
        -Denable-oss=0 -Denable-openmp=0 \
        -DDEFAULT_SOUNDFONT=/opt/android/share/soundfonts/default.sf2 \
        -DFETCHCONTENT_SOURCE_DIR_SIGNALSMITH-LINEAR="$HERE/signalsmith-linear" \
        -DFETCHCONTENT_SOURCE_DIR_SIGNALSMITH-DSP="$HERE/signalsmith-dsp" \
        -DFETCHCONTENT_SOURCE_DIR_SIGNALSMITH-HILBERT="$HERE/signalsmith-hilbert"

    mkdir -p "$root/lib"
    for lib in "${LIBS[@]}"; do
        cp -L "$prefix/lib/$lib" "$root/lib/$lib"
    done
    echo "$FP" >"$stamp"
    echo ">> $abi: done"
}

IFS=',' read -r -a abi_list <<<"$ABIS"
for abi in "${abi_list[@]}"; do
    case "$abi" in
        arm64-v8a|x86_64|armeabi-v7a|x86) build_abi "$abi" ;;
        *) echo "unsupported ABI: $abi" >&2; exit 2 ;;
    esac
done

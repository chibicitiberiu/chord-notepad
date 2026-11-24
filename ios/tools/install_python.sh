#!/bin/bash
# Xcode build phase of the ChordNotepad app target (ios/project.yml): put
# Python into the app bundle (docs/IOS.md, "The app bundle").
#
#   <app>/python/lib/python3.14/   the standard library from Python.xcframework
#                                  (shared part plus the slice's own part)
#   <app>/python/app/              the core and chordnotepad_ios
#   <app>/python/app_packages/     the core's packages
#   <app>/Frameworks/<module>.framework   one per binary module
#
# This is CPython's "Process Python libraries" step (Doc/using/ios.rst; the
# utils.sh shipped in Python.xcframework/build): iOS loads native code only
# from signed frameworks, so every .so becomes Frameworks/<dotted
# name>.framework/<dotted name>, with a .fwork file where the .so was (the
# binary's path, read by Python's AppleFrameworkLoader) and a .origin file in
# the framework pointing back. A <module>.xcprivacy next to a .so becomes the
# framework's PrivacyInfo.xcprivacy.
#
# Differences from utils.sh: a framework is signed only when the build signs
# (an unsigned device build has no identity), and it fails with a hint when
# the inputs from packaging/ios/ are missing.
#
# Inputs (made by packaging/ios/fetch_python.sh and build_python_bundle.py):
#   $PROJECT_DIR/build/Frameworks/Python.xcframework
#   $PROJECT_DIR/build/python-bundle/{app,app_packages}
set -euo pipefail

XCFRAMEWORK="$PROJECT_DIR/build/Frameworks/Python.xcframework"
BUNDLE="$PROJECT_DIR/build/python-bundle"
APP="$CODESIGNING_FOLDER_PATH"
DEST="$APP/python"

for input in "$XCFRAMEWORK/lib" "$BUNDLE/app" "$BUNDLE/app_packages"; do
    if [ ! -d "$input" ]; then
        echo "error: $input is missing. Run packaging/ios/fetch_python.sh ios/build/Frameworks and" \
             "python3.14 packaging/ios/build_python_bundle.py ios/build/python-bundle first (docs/IOS.md)."
        exit 1
    fi
done

case "$EFFECTIVE_PLATFORM_NAME" in
    -iphonesimulator)
        if [ -d "$XCFRAMEWORK/ios-arm64-simulator" ]; then
            SLICE=ios-arm64-simulator
        else
            SLICE=ios-arm64_x86_64-simulator
        fi
        ;;
    -iphoneos) SLICE=ios-arm64 ;;
    *) echo "error: unsupported platform $EFFECTIVE_PLATFORM_NAME"; exit 1 ;;
esac
# One architecture per build (EXCLUDED_ARCHS drops the simulator's x86_64).
ARCH=$ARCHS
if [ "${ARCH// /}" != "$ARCH" ]; then
    echo "error: building for several architectures ($ARCHS); the stdlib is per architecture"
    exit 1
fi

echo "Installing Python ($SLICE, $ARCH) into $DEST"
mkdir -p "$DEST/lib"
rsync -a --delete --exclude 'libpython*.dylib' "$XCFRAMEWORK/lib/" "$DEST/lib/"
rsync -a --exclude 'libpython*.dylib' "$XCFRAMEWORK/$SLICE/lib-$ARCH/" "$DEST/lib/"
rsync -a --delete "$BUNDLE/app/" "$DEST/app/"
rsync -a --delete "$BUNDLE/app_packages/" "$DEST/app_packages/"

SIGN_IDENTITY=""
if [ "${CODE_SIGNING_ALLOWED:-YES}" != "NO" ]; then
    SIGN_IDENTITY="${EXPANDED_CODE_SIGN_IDENTITY:-}"
fi

# install_framework <install base, relative to the app> <the .so's full path>
install_framework() {
    local base=$1 ext=$2
    local relative=${ext#"$APP"/}
    local module_path module_name dotted framework bundle_id
    module_path=$(dirname "$ext")
    module_name=$(basename "$ext" | cut -d . -f 1)
    dotted=$(echo "${relative#"$base"/}" | cut -d . -f 1 | tr / .)
    framework="Frameworks/$dotted.framework"
    bundle_id=$(echo "$PRODUCT_BUNDLE_IDENTIFIER.$dotted" | tr _ -)

    mkdir -p "$APP/$framework"
    cp "$XCFRAMEWORK/build/$PLATFORM_FAMILY_NAME-dylib-Info-template.plist" "$APP/$framework/Info.plist"
    plutil -replace CFBundleExecutable -string "$dotted" "$APP/$framework/Info.plist"
    plutil -replace CFBundleIdentifier -string "$bundle_id" "$APP/$framework/Info.plist"
    plutil -replace MinimumOSVersion -string "$IPHONEOS_DEPLOYMENT_TARGET" "$APP/$framework/Info.plist"
    if [ "$EFFECTIVE_PLATFORM_NAME" = "-iphonesimulator" ]; then
        plutil -replace CFBundleSupportedPlatforms -json '["iPhoneSimulator"]' "$APP/$framework/Info.plist"
    fi
    mv "$ext" "$APP/$framework/$dotted"
    echo "$framework/$dotted" > "${ext%.so}.fwork"
    echo "${relative%.so}.fwork" > "$APP/$framework/$dotted.origin"
    if [ -e "$module_path/$module_name.xcprivacy" ]; then
        mv "$module_path/$module_name.xcprivacy" "$APP/$framework/PrivacyInfo.xcprivacy"
    fi
    if [ -n "$SIGN_IDENTITY" ]; then
        /usr/bin/codesign --force --sign "$SIGN_IDENTITY" ${OTHER_CODE_SIGN_FLAGS:-} -o runtime \
            --timestamp=none --preserve-metadata=identifier,entitlements,flags \
            --generate-entitlement-der "$APP/$framework"
    fi
}

count=0
for base in "python/lib/python3.14/lib-dynload" "python/app_packages" "python/app"; do
    while IFS= read -r -d '' ext; do
        install_framework "$base" "$ext"
        count=$((count + 1))
    done < <(find "$APP/$base" -name '*.so' -print0)
done
# Manifests for modules this slice doesn't have.
find "$DEST/lib" -name '*.xcprivacy' -delete
echo "Made $count binary modules into frameworks${SIGN_IDENTITY:+, signed as $SIGN_IDENTITY}"

#!/usr/bin/env bash
# Fetch the iOS Python.xcframework the app embeds (docs/IOS.md, "CI"), trim
# it and precompile its standard library.
#
#   packaging/ios/fetch_python.sh <out-dir> [host-python]
#
# Writes <out-dir>/Python.xcframework. python.org publishes iOS builds only
# from 3.15 on, so this is BeeWare's support package for 3.14: CPython's own
# iOS framework build (Apple/ in the CPython tree) with its dependencies
# (OpenSSL, libFFI, XZ, BZip2, mpdecimal, Zstandard) built in, and the
# App Store compliance patch applied.
#
# The framework holds the interpreter and headers; the standard library sits
# next to it (lib/ for every slice, <slice>/lib-<arch>/ for the per-slice
# parts) and ios/tools/install_python.sh copies it into the app at build
# time. Here it loses what the app never imports (the test suite, IDLE,
# Tkinter, ensurepip, the test extension modules), each binary module gets
# the privacy manifest packaging/ios/privacy/ has for it, and every .py is
# compiled with the host's 3.14 into unchecked-hash .pyc files: the app
# bundle is read-only, and timestamp-checked ones would go stale as soon as
# a copy changes the files' times, so Python would recompile on every start.
set -euo pipefail

OUT=${1:?usage: fetch_python.sh <out-dir> [host-python]}
HOST_PYTHON=${2:-python3.14}
HERE=$(cd "$(dirname "$0")" && pwd)

PYTHON_MINOR=3.14
SUPPORT_RELEASE=3.14-b14
SUPPORT_URL=https://github.com/beeware/Python-Apple-support/releases/download/$SUPPORT_RELEASE/Python-3.14-iOS-support.b14.tar.gz
SUPPORT_SHA256=703ff822529f46edcbcd8b88096b2544f6990f3109ad38b4b4b61bb489a7c1ee

host_minor=$("$HOST_PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
if [ "$host_minor" != "$PYTHON_MINOR" ]; then
    echo "The host Python ($HOST_PYTHON) is $host_minor; the .pyc files need $PYTHON_MINOR" >&2
    exit 1
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
curl -fsSL --retry 3 -o "$WORK/support.tar.gz" "$SUPPORT_URL"
echo "$SUPPORT_SHA256  $WORK/support.tar.gz" | shasum -a 256 -c -
mkdir -p "$WORK/x"
tar -xzf "$WORK/support.tar.gz" -C "$WORK/x"
cat "$WORK/x/VERSIONS"

FRAMEWORK="$WORK/x/Python.xcframework"
STDLIB="$FRAMEWORK/lib/python$PYTHON_MINOR"
test -d "$STDLIB"

# What the app never imports.
for unused in test idlelib tkinter turtledemo turtle.py ensurepip pydoc_data; do
    rm -rf "${STDLIB:?}/$unused"
done
find "$FRAMEWORK" -path '*/lib-dynload/*' \( -name '_test*.so' -o -name '_ctypes_test*.so' \
    -o -name 'xxlimited*.so' -o -name 'xxsubtype*.so' -o -name '_xxtestfuzz*.so' \) -delete

# Privacy manifests for the binary modules that link a library Apple lists
# (OpenSSL in _ssl and _hashlib). install_python.sh moves <module>.xcprivacy
# into the module's framework.
for dynload in "$FRAMEWORK"/*/lib-*/python$PYTHON_MINOR/lib-dynload; do
    for manifest in "$HERE"/privacy/*.xcprivacy; do
        cp "$manifest" "$dynload/"
    done
done

# Precompile every .py, the per-slice sysconfig data too. A file that
# doesn't compile (none should be left) fails the step.
"$HOST_PYTHON" -I "$HERE/compile_pyc.py" "$FRAMEWORK/lib" "$FRAMEWORK"/*/lib-*

mkdir -p "$OUT"
rm -rf "$OUT/Python.xcframework"
mv "$FRAMEWORK" "$OUT/Python.xcframework"
cp "$WORK/x/VERSIONS" "$OUT/Python.xcframework/VERSIONS"
echo "Wrote $OUT/Python.xcframework ($(du -sh "$OUT/Python.xcframework" | cut -f1))"

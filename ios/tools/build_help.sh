#!/bin/bash
# Build the iOS edition of the user guide (help/*.rst with `-t ios`, the same
# Sphinx stack as Android's: android/docs-requirements.txt) into <out>, which
# the app's "User guide" build phase copies into <app>/help (docs/IOS.md,
# "The user guide"). As Android's Gradle task: a warning fails the build, the
# HTML is reproducible, and the build's bookkeeping and the font formats
# WebKit never asks for are left out.
#
#   ios/tools/build_help.sh <out-dir>            (PYTHON: a Python with Sphinx; default python3)
set -euo pipefail

OUT=${1:?usage: build_help.sh <out-dir>}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PYTHON=${PYTHON:-python3}
SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT

rm -rf "$OUT"
# CN_HELP_DRAFT=1 lets warnings through (a figure without its iOS screenshot yet).
STRICT=(-W --keep-going)
[ "${CN_HELP_DRAFT:-0}" = 1 ] && STRICT=()
SOURCE_DATE_EPOCH=1700000000 PYTHONHASHSEED=0 \
    "$PYTHON" -m sphinx -t ios -b html -q ${STRICT[@]+"${STRICT[@]}"} -d "$SCRATCH/doctrees" "$ROOT/help" "$OUT"

rm -f "$OUT/.buildinfo" "$OUT/objects.inv"
find "$OUT" -type f \( -name '*.ttf' -o -name '*.eot' -o -name '*.otf' \) -delete
rm -f "$OUT"/_static/css/fonts/*.svg
echo "User guide (iOS edition): $(find "$OUT" -name '*.html' | wc -l | tr -d ' ') pages," \
    "$(du -sh "$OUT" | cut -f1) in $OUT"

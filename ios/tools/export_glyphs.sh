#!/bin/bash
# Xcode build phase of the ChordNotepad app target (ios/project.yml): the
# chord sheet's seven base clef and glyph PNGs and their glyphs.json into
# <app>/chord_sheet/ (docs/IOS.md, "Chord sheet"). The staff view's image ops
# name them; android/tools/export_clef_glyphs.py writes them from the PNGs
# embedded in core/chordnotepad/chord_sheet/clef_assets.py, as Android's
# exportClefGlyphs Gradle task does, so no binary is committed.
#
# The script needs only the standard library (Python 3.9 or later): the
# setup-python 3.14 on CI, the system python3 on a Mac.
set -euo pipefail

REPO="$PROJECT_DIR/.."
OUT="$CODESIGNING_FOLDER_PATH/chord_sheet"
PYTHON=$(command -v python3.14 || command -v python3 || true)
if [ -z "$PYTHON" ]; then
    echo "error: no python3 on PATH; the chord sheet's glyphs can't be exported (docs/IOS.md)."
    exit 1
fi
rm -rf "$OUT"
"$PYTHON" -I "$REPO/android/tools/export_clef_glyphs.py" --core "$REPO/core" --out-dir "$OUT"

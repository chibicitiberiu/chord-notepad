#!/usr/bin/env bash
# Thin the universal2 (arm64 + x86_64) binaries of the build venv to this
# Mac's CPU, before PyInstaller collects them.
#
#   packaging/macos/thin_wheels.sh "$(pipenv run python -c 'import sysconfig; print(sysconfig.get_paths()["platlib"])')"
#
# PySide6's macOS wheel is universal2 only. PyInstaller thins the binaries it
# collects as binaries, but not Mach-O files that reach the bundle as data,
# and each dmg is for one CPU anyway. Every fat Mach-O file under the folder
# is cut down to `uname -m` with lipo and signed again ad hoc (lipo breaks the
# signature, and Apple silicon refuses unsigned code). smoke_test.sh checks
# that the app has no fat binary left.
set -euo pipefail

SITE=${1:?usage: thin_wheels.sh <site-packages>}
ARCH=$(uname -m)
count=0
while IFS= read -r -d '' file; do
    archs=$(lipo -archs "$file" 2>/dev/null || true)
    case " $archs " in
        *" $ARCH "*) ;;
        *) continue ;;
    esac
    [ "$(wc -w <<<"$archs")" -gt 1 ] || continue
    lipo -thin "$ARCH" -output "$file.thin" "$file"
    chmod "$(stat -f '%Lp' "$file")" "$file.thin"
    mv "$file.thin" "$file"
    codesign --force --sign - "$file"
    count=$((count + 1))
done < <(find "$SITE" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -u+x -o -path '*.framework/Versions/*' \) -print0)
echo "Thinned $count universal binaries in $SITE to $ARCH"

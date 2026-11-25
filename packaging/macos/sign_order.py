#!/usr/bin/env python3
"""The order to sign a macOS app bundle in, inside out (sign_app.sh reads it).

    python3 -I packaging/macos/sign_order.py "dist/Chord Notepad.app"

Prints one ``<kind>\\t<path>`` line per item, deepest first, the app last:

- ``exe``: a Mach-O executable (MH_EXECUTE), signed with the entitlements;
- ``lib``: any other Mach-O file (dylib, Python extension module);
- ``bundle``: a nested bundle (.framework, .app, .appex, .bundle, .xpc),
  signed after everything inside it;
- ``app``: the app itself, last, with the entitlements.

Symbolic links are skipped (PyInstaller links Contents/Resources to
Contents/Frameworks; the link's target is signed once). Signing each item
on its own instead of ``codesign --deep`` is what Apple asks for: --deep
gives every nested file the outer item's options and entitlements.
"""

import os
import pathlib
import plistlib
import struct
import sys

THIN = {b"\xcf\xfa\xed\xfe": "<", b"\xce\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">", b"\xfe\xed\xfa\xce": ">"}
FAT = {b"\xca\xfe\xba\xbe": 20, b"\xca\xfe\xba\xbf": 32}
MH_EXECUTE = 2
BUNDLE_SUFFIXES = {".framework", ".app", ".appex", ".bundle", ".xpc"}


def macho_kind(path: pathlib.Path):
    """"exe", "lib" or None (not Mach-O)."""
    try:
        with path.open("rb") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    magic = head[:4]
    if magic in THIN:
        filetype = struct.unpack_from(THIN[magic] + "I", head, 12)[0]
        return "exe" if filetype == MH_EXECUTE else "lib"
    if magic in FAT and len(head) >= 8:
        count = struct.unpack_from(">I", head, 4)[0]
        if not 0 < count < 30:  # Java class files share the magic; their "count" is a version
            return None
        offset = struct.unpack_from(">I" if FAT[magic] == 20 else ">Q", head, 16)[0]
        with path.open("rb") as handle:
            handle.seek(offset)
            slice_head = handle.read(16)
        if slice_head[:4] in THIN:
            filetype = struct.unpack_from(THIN[slice_head[:4]] + "I", slice_head, 12)[0]
            return "exe" if filetype == MH_EXECUTE else "lib"
        return "lib"
    return None


def signing_order(app: pathlib.Path) -> list:
    """(kind, path) for everything to sign, deepest first; the app last."""
    items = []
    # os.walk doesn't descend into linked folders; linked files are skipped below.
    for folder, dirs, files in os.walk(app, followlinks=False):
        base = pathlib.Path(folder)
        for name in dirs:
            path = base / name
            if not path.is_symlink() and path.suffix in BUNDLE_SUFFIXES:
                items.append(("bundle", path))
        for name in files:
            path = base / name
            if path.is_symlink():
                continue
            kind = macho_kind(path)
            if kind:
                items.append((kind, path))
    items.sort(key=lambda item: (-len(item[1].relative_to(app).parts), str(item[1])))
    main_executable = None
    info = app / "Contents" / "Info.plist"
    if info.is_file():
        name = plistlib.loads(info.read_bytes()).get("CFBundleExecutable")
        if name:
            main_executable = app / "Contents" / "MacOS" / name
    # The main executable is signed with the app (codesign signs it as part of
    # the bundle), so it isn't listed on its own.
    items = [item for item in items if item[1] != main_executable]
    items.append(("app", app))
    return items


def main(argv: list) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    app = pathlib.Path(argv[1])
    for kind, path in signing_order(app):
        print(f"{kind}\t{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

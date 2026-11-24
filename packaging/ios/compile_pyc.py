#!/usr/bin/env python3
"""Precompile the iOS app's Python files into unchecked-hash .pyc files.

    python3.14 -I packaging/ios/compile_pyc.py DIR [DIR ...]

The app bundle is read-only and the interpreter runs with write_bytecode off,
so Python only ever uses the .pyc files shipped next to the sources.
Timestamp-checked ones would go stale as soon as a copy changes the files'
times (and Python would then compile every module on each start without a
word), so these are checked by nothing: they are rebuilt with every app build.

Run it with the same minor version as the app's interpreter (3.14). Exits 1
if any file fails to compile.
"""

import compileall
import py_compile
import sys

EXPECTED = (3, 14)


def main(argv: list) -> int:
    if sys.version_info[:2] != EXPECTED:
        print(f"compile_pyc.py needs Python {EXPECTED[0]}.{EXPECTED[1]}, not {sys.version.split()[0]}",
              file=sys.stderr)
        return 1
    ok = True
    for directory in argv:
        ok = compileall.compile_dir(
            directory, quiet=1, workers=0,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

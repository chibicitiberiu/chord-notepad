#!/usr/bin/env python3
"""Check an APK's merged manifest for things a FOSS, offline build must not have.

- no ``android.permission.INTERNET`` (the app works fully offline);
- nothing from Google Play services (``com.google.android.gms``): the app must
  run on de-Googled devices;
- no emoji2 ``EmojiCompatInitializer``: it fetches a downloadable font from the
  Play services fonts provider (the manifest removes it; this keeps it removed).

Reads the compiled manifest with ``aapt2`` from the SDK's newest build-tools
(``$ANDROID_HOME``), or the one given with ``--aapt2``.

Usage: python3 check_manifest.py [--aapt2 PATH] app.apk [more.apk ...]
(exit code 1 on failure)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PERMISSIONS = ("android.permission.INTERNET",)
FORBIDDEN_TEXT = (
    "com.google.android.gms",
    "androidx.emoji2.text.EmojiCompatInitializer",
)


def find_aapt2() -> str:
    """The aapt2 of the newest installed build-tools."""
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        sys.exit("set ANDROID_HOME (source android/local.env) or pass --aapt2")
    tools = sorted(
        (p for p in Path(sdk, "build-tools").glob("*/aapt2") if p.is_file()),
        key=lambda p: [int(x) if x.isdigit() else 0 for x in p.parent.name.replace("-", ".").split(".")],
    )
    if not tools:
        sys.exit(f"no build-tools/*/aapt2 under {sdk}")
    return str(tools[-1])


def aapt2(tool: str, *args: str) -> str:
    return subprocess.run([tool, *args], check=True, capture_output=True, text=True).stdout


def check_apk(tool: str, apk: str) -> list:
    """Return the problems found in ``apk``."""
    problems = []
    permissions = aapt2(tool, "dump", "permissions", apk)
    for perm in FORBIDDEN_PERMISSIONS:
        if perm in permissions:
            problems.append(f"uses {perm}")
    manifest = aapt2(tool, "dump", "xmltree", "--file", "AndroidManifest.xml", apk)
    for text in FORBIDDEN_TEXT:
        if text in manifest:
            problems.append(f"manifest mentions {text}")
    return problems


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aapt2")
    parser.add_argument("apks", nargs="+")
    args = parser.parse_args(argv[1:])
    tool = args.aapt2 or find_aapt2()
    failed = False
    for apk in args.apks:
        problems = check_apk(tool, apk)
        for p in problems:
            print(f"FAIL {apk}: {p}")
        if not problems:
            print(f"OK   {apk}: no INTERNET permission, no Play services, no emoji2 initializer")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Check an APK's merged manifest against what its flavour may contain.

Both flavours (a hard check):

- no ``android.permission.INTERNET`` and no ``ACCESS_NETWORK_STATE``: the app
  works fully offline;
- no emoji2 ``EmojiCompatInitializer``: it fetches a downloadable font from the
  Play services fonts provider (the manifest removes it; this keeps it removed).

``--flavor foss`` (GitHub APK, F-Droid): nothing from Google Play services
(``com.google.android.gms``), Play Billing or the Play Store app: the app must
run on de-Googled devices.

``--flavor play`` (Google Play): exactly what Play Billing adds, and nothing
else of Google's: the BILLING permission, the two ``<queries>`` intents, the
billing proxy activities and version meta-data, and from Play services
``GoogleApiActivity`` and the ``com.google.android.gms.version`` meta-data.
Google's datatransport telemetry components are removed in
``src/play/AndroidManifest.xml`` and must stay removed. A new billing release
that adds something fails here until the list below is updated on purpose.

Reads the compiled manifest with ``aapt2`` from the SDK's newest build-tools
(``$ANDROID_HOME``), or the one given with ``--aapt2``. aapt2 can't read an
AAB: check the play flavour through its APK (``assemblePlayRelease``).

Usage: python3 check_manifest.py --flavor foss|play [--aapt2 PATH] app.apk [more.apk ...]
(exit code 1 on failure)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PERMISSIONS = (
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
)
FORBIDDEN_TEXT = ("androidx.emoji2.text.EmojiCompatInitializer",)

# Names from Google's Play libraries: Play services, Play Billing, the Play
# Store app, datatransport and Firebase.
GOOGLE_NAME = re.compile(
    r'"((?:com\.google\.|com\.android\.billingclient\.|com\.android\.vending\b)[^"]*)"'
)

# What billing-ktx 9.1 (billing, play-services-base) adds to the play manifest.
PLAY_ALLOWED = frozenset({
    "com.android.vending.BILLING",
    "com.android.vending.billing.InAppBillingService.BIND",
    "com.google.android.apps.play.billingtestcompanion.BillingOverrideService.BIND",
    "com.google.android.play.billingclient.version",
    "com.android.billingclient.api.ProxyBillingActivity",
    "com.android.billingclient.api.ProxyBillingActivityV2",
    "com.google.android.gms.common.api.GoogleApiActivity",
    "com.google.android.gms.version",
})
ALLOWED = {"foss": frozenset(), "play": PLAY_ALLOWED}


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


def check_manifest_text(flavor: str, permissions: str, manifest: str) -> list:
    """Return the problems, given aapt2's ``dump permissions`` and ``dump xmltree`` output."""
    problems = []
    declared = set(re.findall(r"name='([^']+)'", permissions))
    for perm in FORBIDDEN_PERMISSIONS:
        if perm in declared or perm in permissions:
            problems.append(f"uses {perm}")
    for text in FORBIDDEN_TEXT:
        if text in manifest:
            problems.append(f"manifest mentions {text}")
    google = set(GOOGLE_NAME.findall(manifest)) | {p for p in declared if GOOGLE_NAME.search(f'"{p}"')}
    for name in sorted(google - ALLOWED[flavor]):
        problems.append(f"manifest mentions {name} (not allowed in {flavor})")
    return problems


def check_apk(tool: str, flavor: str, apk: str) -> list:
    """Return the problems found in ``apk``."""
    permissions = aapt2(tool, "dump", "permissions", apk)
    manifest = aapt2(tool, "dump", "xmltree", "--file", "AndroidManifest.xml", apk)
    return check_manifest_text(flavor, permissions, manifest)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--flavor", required=True, choices=sorted(ALLOWED), help="the APK's product flavour")
    parser.add_argument("--aapt2")
    parser.add_argument("apks", nargs="+")
    args = parser.parse_args(argv[1:])
    tool = args.aapt2 or find_aapt2()
    summary = {
        "foss": "no network permissions, no Play services or billing, no emoji2 initializer",
        "play": "no network permissions, only Play Billing's own entries, no emoji2 initializer",
    }[args.flavor]
    failed = False
    for apk in args.apks:
        problems = check_apk(tool, args.flavor, apk)
        for p in problems:
            print(f"FAIL {apk}: {p}")
        if not problems:
            print(f"OK   {apk} ({args.flavor}): {summary}")
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

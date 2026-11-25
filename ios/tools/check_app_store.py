#!/usr/bin/env python3
"""Check a built ChordNotepad.app against what App Store validation looks for.

    python3 -I ios/tools/check_app_store.py <ChordNotepad.app> \\
        [--assetutil-json assets.json] [--icon-source AppIcon-1024.png]

ios.yml runs it on the device build and on the TestFlight archive (docs/IOS.md,
"App Store requirements"). Standard library only; the tests run it on Linux
over a synthetic bundle. It fails (exit 1) when:

- Info.plist: the bundle ID isn't com.tibich.chordnotepad;
  ITSAppUsesNonExemptEncryption isn't present and false; CFBundleIcons or
  CFBundleIcons~ipad doesn't name AppIcon; there is no UILaunchScreen; the
  iPad doesn't allow all four orientations (iPad multitasking needs them);
  the version strings aren't numbers.
- PrivacyInfo.xcprivacy is missing, tracks, or doesn't declare a reason for a
  required-reason API category the app's binaries use. The use is read from
  the binaries themselves: every Mach-O in the bundle is searched for the
  symbols and names Apple lists per category (NSPrivacyAccessedAPIType,
  developer.apple.com/documentation/bundleresources/app-privacy-configuration/
  nsprivacyaccessedapitypes/nsprivacyaccessedapitype, read 2026-11-25), so a
  new CPython module or Swift call that starts using one fails the build. A
  framework's own PrivacyInfo.xcprivacy covers that framework.
- A Mach-O sits outside a framework (iOS loads native code only from the app's
  executable and its frameworks), or a framework's Info.plist doesn't say
  iPhoneOS or has no MinimumOSVersion.
- The icon: no Assets.car; with --assetutil-json (``xcrun --sdk iphoneos
  assetutil --info Assets.car``), no 1024 px AppIcon rendition; a loose icon
  file Info.plist's CFBundleIconFiles names (iPhone or iPad) is missing; with
  --icon-source, the 1024 px source isn't 1024 x 1024 or has an
  alpha channel (App Store Connect refuses those).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import plistlib
import re
import struct
import sys
from typing import Optional

BUNDLE_ID = "com.tibich.chordnotepad"
ICON_NAME = "AppIcon"
# From a single-size (1024 px) icon, Xcode 26 compiles one 1024 px AppIcon
# rendition into Assets.car (the system scales it) and writes the loose
# AppIcon60x60@2x.png / AppIcon76x76@2x~ipad.png files Info.plist's
# CFBundleIconFiles name (seen in ios.yml's device build, run 45518102280).
REQUIRED_ICON_PIXELS = {1024}
IPAD_ORIENTATIONS = {"UIInterfaceOrientationPortrait", "UIInterfaceOrientationPortraitUpsideDown",
                     "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"}

# Apple's required-reason API list: per category, the C functions (as Mach-O
# symbols) and the Foundation names (constants and selectors) that count.
REQUIRED_REASON_APIS = {
    "NSPrivacyAccessedAPICategoryFileTimestamp": {
        "symbols": ["_stat", "_fstat", "_fstatat", "_lstat", "_getattrlist", "_getattrlistbulk",
                    "_fgetattrlist", "_getattrlistat"],
        "names": ["NSFileCreationDate", "NSFileModificationDate", "NSURLContentModificationDateKey",
                  "NSURLCreationDateKey", "creationDate", "modificationDate", "fileModificationDate"],
    },
    "NSPrivacyAccessedAPICategorySystemBootTime": {
        "symbols": ["_mach_absolute_time"],
        "names": ["systemUptime"],
    },
    "NSPrivacyAccessedAPICategoryDiskSpace": {
        "symbols": ["_statfs", "_statvfs", "_fstatfs", "_fstatvfs", "_getattrlist", "_fgetattrlist",
                    "_getattrlistat"],
        "names": ["NSURLVolumeAvailableCapacityKey", "NSURLVolumeAvailableCapacityForImportantUsageKey",
                  "NSURLVolumeAvailableCapacityForOpportunisticUsageKey", "NSURLVolumeTotalCapacityKey",
                  "NSFileSystemFreeSize", "NSFileSystemSize"],
    },
    "NSPrivacyAccessedAPICategoryActiveKeyboards": {
        "symbols": [],
        "names": ["activeInputModes"],
    },
    "NSPrivacyAccessedAPICategoryUserDefaults": {
        "symbols": ["_OBJC_CLASS_$_NSUserDefaults"],
        "names": [],
    },
}
# The short names (creationDate, modificationDate) are Swift property names
# of FileAttributeKey/URLResourceValues; as plain strings they match far too
# much, so only the exact Foundation constants above are searched for.
NAME_ONLY_IN_SWIFT = {"creationDate", "modificationDate", "fileModificationDate"}

MACHO_MAGICS = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}


class Result:
    def __init__(self) -> None:
        self.errors: list = []
        self.notes: list = []

    def error(self, text: str) -> None:
        self.errors.append(text)

    def note(self, text: str) -> None:
        self.notes.append(text)


def is_macho(path: pathlib.Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGICS
    except OSError:
        return False


def machos(app: pathlib.Path) -> list:
    return sorted(p for p in app.rglob("*") if p.is_file() and not p.is_symlink() and is_macho(p))


def owning_framework(app: pathlib.Path, path: pathlib.Path) -> Optional[pathlib.Path]:
    for parent in path.relative_to(app).parents:
        if parent.suffix == ".framework":
            return app / parent
    return None


def api_use(data: bytes) -> dict:
    """category -> the matching symbols and names found in a binary's bytes."""
    found = {}
    for category, apis in REQUIRED_REASON_APIS.items():
        hits = [s for s in apis["symbols"] if b"\x00" + s.encode() + b"\x00" in data]
        hits += [n for n in apis["names"] if n not in NAME_ONLY_IN_SWIFT
                 and re.search(rb"(?<![A-Za-z0-9_])_?" + re.escape(n.encode()) + rb"(?![A-Za-z0-9_])", data)]
        if hits:
            found[category] = hits
    return found


def declared(manifest: pathlib.Path) -> Optional[dict]:
    """category -> reasons from a privacy manifest, or None when it's missing."""
    if not manifest.is_file():
        return None
    data = plistlib.loads(manifest.read_bytes())
    return {entry.get("NSPrivacyAccessedAPIType"): list(entry.get("NSPrivacyAccessedAPITypeReasons") or [])
            for entry in data.get("NSPrivacyAccessedAPITypes") or []}


def check_info(app: pathlib.Path, result: Result) -> None:
    info_path = app / "Info.plist"
    if not info_path.is_file():
        result.error("no Info.plist")
        return
    info = plistlib.loads(info_path.read_bytes())
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        result.error(f"CFBundleIdentifier is {info.get('CFBundleIdentifier')!r}, not {BUNDLE_ID}")
    if info.get("ITSAppUsesNonExemptEncryption") is not False:
        result.error("ITSAppUsesNonExemptEncryption isn't set to NO (App Store Connect asks for export compliance)")
    for key in ("CFBundleIcons", "CFBundleIcons~ipad"):
        name = ((info.get(key) or {}).get("CFBundlePrimaryIcon") or {}).get("CFBundleIconName")
        if name != ICON_NAME:
            result.error(f"{key} doesn't name {ICON_NAME} (got {name!r})")
    if "UILaunchScreen" not in info and "UILaunchStoryboardName" not in info:
        result.error("no UILaunchScreen")
    ipad = set(info.get("UISupportedInterfaceOrientations~ipad") or [])
    if not info.get("UIRequiresFullScreen") and ipad != IPAD_ORIENTATIONS:
        result.error(f"the iPad orientations are {sorted(ipad)}; multitasking needs all four")
    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        if not re.fullmatch(r"\d+(\.\d+){0,2}", str(info.get(key, ""))):
            result.error(f"{key} is {info.get(key)!r}, not one to three numbers")
    result.note(f"{info.get('CFBundleIdentifier')} {info.get('CFBundleShortVersionString')}"
                f" ({info.get('CFBundleVersion')}), iOS {info.get('MinimumOSVersion')}+")


def check_privacy(app: pathlib.Path, binaries: list, result: Result) -> None:
    app_manifest = declared(app / "PrivacyInfo.xcprivacy")
    if app_manifest is None:
        result.error("no PrivacyInfo.xcprivacy in the app")
        return
    raw = plistlib.loads((app / "PrivacyInfo.xcprivacy").read_bytes())
    if raw.get("NSPrivacyTracking") is not False:
        result.error("PrivacyInfo.xcprivacy: NSPrivacyTracking isn't false")
    used: dict = {}
    for binary in binaries:
        framework = owning_framework(app, binary)
        own = declared(framework / "PrivacyInfo.xcprivacy") if framework else None
        for category, hits in api_use(binary.read_bytes()).items():
            if own and own.get(category):
                continue
            used.setdefault(category, []).append(f"{binary.relative_to(app)} ({', '.join(hits)})")
    for category, places in sorted(used.items()):
        reasons = app_manifest.get(category)
        if not reasons:
            result.error(f"{category} is used but PrivacyInfo.xcprivacy gives no reason: {'; '.join(places[:5])}"
                         + (f" and {len(places) - 5} more" if len(places) > 5 else ""))
        else:
            result.note(f"{category} ({', '.join(reasons)}): used by {len(places)} binaries, e.g. {places[0]}")
    for category in sorted(set(app_manifest) - set(used)):
        result.note(f"{category} is declared but no binary uses it")


def check_binaries(app: pathlib.Path, binaries: list, result: Result) -> None:
    info = plistlib.loads((app / "Info.plist").read_bytes()) if (app / "Info.plist").is_file() else {}
    executable = app / info.get("CFBundleExecutable", "ChordNotepad")
    for binary in binaries:
        if binary != executable and owning_framework(app, binary) is None:
            result.error(f"native code outside a framework: {binary.relative_to(app)}")
    frameworks = sorted((app / "Frameworks").glob("*.framework")) if (app / "Frameworks").is_dir() else []
    for framework in frameworks:
        plist = framework / "Info.plist"
        if not plist.is_file():
            result.error(f"{framework.name} has no Info.plist")
            continue
        data = plistlib.loads(plist.read_bytes())
        if "iPhoneOS" not in (data.get("CFBundleSupportedPlatforms") or []):
            result.error(f"{framework.name} isn't marked for iPhoneOS")
        if not data.get("MinimumOSVersion"):
            result.error(f"{framework.name} has no MinimumOSVersion")
    result.note(f"{len(binaries)} Mach-O files, {len(frameworks)} frameworks")


def png_header(path: pathlib.Path) -> tuple:
    data = path.read_bytes()[:33]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} isn't a PNG")
    width, height, _depth, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, colour


def check_icons(app: pathlib.Path, assetutil: Optional[pathlib.Path], source: Optional[pathlib.Path],
                result: Result) -> None:
    if not (app / "Assets.car").is_file():
        result.error("no Assets.car (the compiled asset catalog with the icon)")
    if assetutil:
        entries = json.loads(assetutil.read_text(encoding="utf-8"))
        sizes = sorted({int(e.get("PixelWidth", 0)) for e in entries
                        if isinstance(e, dict) and e.get("Name") == ICON_NAME and e.get("PixelWidth")})
        missing = REQUIRED_ICON_PIXELS - set(sizes)
        if missing:
            result.error(f"the compiled {ICON_NAME} has {sizes} px, missing {sorted(missing)}")
        else:
            result.note(f"{ICON_NAME} sizes: {sizes} px")
    info = plistlib.loads((app / "Info.plist").read_bytes()) if (app / "Info.plist").is_file() else {}
    for key, suffix in (("CFBundleIcons", ""), ("CFBundleIcons~ipad", "~ipad")):
        for name in ((info.get(key) or {}).get("CFBundlePrimaryIcon") or {}).get("CFBundleIconFiles") or []:
            # An iPad looks for <name>@2x~ipad.png, then <name>@2x.png.
            if not list(app.glob(f"{name}@*x{suffix}.png")) and not list(app.glob(f"{name}@*x.png")):
                result.error(f"{key} names {name}, but there is no {name}@2x{suffix}.png in the app")
    if source:
        width, height, colour = png_header(source)
        if (width, height) != (1024, 1024):
            result.error(f"{source.name} is {width} x {height}, not 1024 x 1024")
        if colour in (4, 6):
            result.error(f"{source.name} has an alpha channel; App Store icons must be opaque")


def check(app: pathlib.Path, assetutil: Optional[pathlib.Path] = None,
          icon_source: Optional[pathlib.Path] = None) -> Result:
    result = Result()
    binaries = machos(app)
    check_info(app, result)
    check_privacy(app, binaries, result)
    check_binaries(app, binaries, result)
    check_icons(app, assetutil, icon_source, result)
    return result


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Check an iOS app bundle for App Store validation's rules.")
    parser.add_argument("app", type=pathlib.Path)
    parser.add_argument("--assetutil-json", type=pathlib.Path)
    parser.add_argument("--icon-source", type=pathlib.Path)
    args = parser.parse_args(argv)
    if not args.app.is_dir():
        print(f"error: {args.app} isn't an app bundle", file=sys.stderr)
        return 2
    result = check(args.app, args.assetutil_json, args.icon_source)
    for note in result.notes:
        print(f"  {note}")
    for error in result.errors:
        print(f"error: {error}")
    print(f"{'App Store checks passed' if not result.errors else f'{len(result.errors)} App Store problem(s)'}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())

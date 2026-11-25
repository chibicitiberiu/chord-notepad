"""ios/tools/check_app_store.py over a synthetic app bundle (no Mac needed).

The binaries are stand-ins: a Mach-O header followed by a string table that
names the symbols a real one imports. ios.yml runs the check on the real
device build and the TestFlight archive.
"""

import json
import plistlib
import shutil
import struct
import zlib

import pytest

from tests.ios_tools_support import ROOT, load_tool

check = load_tool("check_app_store")

MANIFEST = ROOT / "ios/ChordNotepad/PrivacyInfo.xcprivacy"
ICON = ROOT / "ios/ChordNotepad/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
ORIENTATIONS = sorted(check.IPAD_ORIENTATIONS)


def macho(*symbols):
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 0, 0, 0, 0)
    return header + b"\x00" + b"\x00".join(s.encode() for s in symbols) + b"\x00"


def framework(app, name, *symbols, platforms=("iPhoneOS",), manifest=None):
    folder = app / "Frameworks" / f"{name}.framework"
    folder.mkdir(parents=True)
    (folder / name).write_bytes(macho(*symbols))
    (folder / "Info.plist").write_bytes(plistlib.dumps(
        {"CFBundleExecutable": name, "CFBundleSupportedPlatforms": list(platforms), "MinimumOSVersion": "17.0"},
        fmt=plistlib.FMT_BINARY))
    if manifest:
        (folder / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps(manifest))
    return folder


@pytest.fixture
def app(tmp_path):
    bundle = tmp_path / "ChordNotepad.app"
    bundle.mkdir()
    info = {
        "CFBundleIdentifier": "com.tibich.chordnotepad", "CFBundleExecutable": "ChordNotepad",
        "CFBundleShortVersionString": "0.6.2", "CFBundleVersion": "57", "MinimumOSVersion": "17.0",
        "ITSAppUsesNonExemptEncryption": False, "UILaunchScreen": {},
        # As Xcode 26 writes them for a single-size icon (ios.yml's device build).
        "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon",
                                                  "CFBundleIconFiles": ["AppIcon60x60"]}},
        "CFBundleIcons~ipad": {"CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon",
                                                       "CFBundleIconFiles": ["AppIcon60x60", "AppIcon76x76"]}},
        "UISupportedInterfaceOrientations~ipad": ORIENTATIONS,
    }
    (bundle / "Info.plist").write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    shutil.copy(MANIFEST, bundle / "PrivacyInfo.xcprivacy")
    (bundle / "Assets.car").write_bytes(b"car")
    for name in ("AppIcon60x60@2x.png", "AppIcon60x60@2x~ipad.png", "AppIcon76x76@2x~ipad.png"):
        (bundle / name).write_bytes(b"png")
    # The executable: Swift's clocks and UserDefaults; Python's file and disk calls.
    (bundle / "ChordNotepad").write_bytes(macho("_mach_absolute_time", "_OBJC_CLASS_$_NSUserDefaults"))
    framework(bundle, "Python", "_stat", "_fstat", "_lstat", "_statvfs", "_fstatvfs", "_mach_absolute_time")
    framework(bundle, "_ssl", "_stat", manifest={"NSPrivacyAccessedAPITypes": [
        {"NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryFileTimestamp",
         "NSPrivacyAccessedAPITypeReasons": ["C617.1"]}]})
    (bundle / "python/lib/python3.14").mkdir(parents=True)
    (bundle / "python/lib/python3.14/os.py").write_text("stat = None\n")
    return bundle


def errors(bundle, **kwargs):
    return check.check(bundle, **kwargs).errors


def test_a_complete_bundle_passes(app):
    assert errors(app) == []
    notes = "\n".join(check.check(app).notes)
    assert "NSPrivacyAccessedAPICategoryDiskSpace (E174.1): used by 1 binaries, e.g. Frameworks/Python.framework" in notes


def test_the_repo_manifest_declares_every_category_cpython_and_the_app_use():
    declared = check.declared(MANIFEST)
    for category in ("FileTimestamp", "SystemBootTime", "DiskSpace", "UserDefaults"):
        assert declared[f"NSPrivacyAccessedAPICategory{category}"], category


@pytest.mark.parametrize("key, value, message", [
    ("CFBundleIdentifier", "com.example.other", "CFBundleIdentifier"),
    ("ITSAppUsesNonExemptEncryption", None, "ITSAppUsesNonExemptEncryption"),
    ("CFBundleIcons~ipad", None, "CFBundleIcons~ipad doesn't name AppIcon"),
    ("UILaunchScreen", None, "no UILaunchScreen"),
    ("UISupportedInterfaceOrientations~ipad", ORIENTATIONS[:2], "multitasking needs all four"),
    ("CFBundleVersion", "57-dev", "CFBundleVersion"),
])
def test_info_plist_problems(app, key, value, message):
    info = plistlib.loads((app / "Info.plist").read_bytes())
    if value is None:
        info.pop(key)
    else:
        info[key] = value
    (app / "Info.plist").write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    assert any(message in e for e in errors(app)), errors(app)


def test_an_undeclared_category_fails(app):
    (app / "Frameworks/Python.framework/Python").write_bytes(macho("_stat", "activeInputModes"))
    found = errors(app)
    assert len(found) == 1 and "NSPrivacyAccessedAPICategoryActiveKeyboards is used" in found[0]
    assert "Frameworks/Python.framework/Python (activeInputModes)" in found[0]


def test_a_framework_manifest_covers_its_own_binary(app):
    manifest = plistlib.loads(MANIFEST.read_bytes())
    manifest["NSPrivacyAccessedAPITypes"] = [e for e in manifest["NSPrivacyAccessedAPITypes"]
                                             if e["NSPrivacyAccessedAPIType"] != "NSPrivacyAccessedAPICategoryFileTimestamp"]
    (app / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps(manifest))
    found = errors(app)
    # Python's stat calls aren't covered any more; _ssl's are, by its own manifest.
    assert len(found) == 1 and "FileTimestamp is used" in found[0]
    assert "Python.framework" in found[0] and "_ssl" not in found[0]


def test_symbols_match_whole_names_only(app):
    (app / "Frameworks/Python.framework/Python").write_bytes(macho("_statx_helper", "_mystat"))
    (app / "ChordNotepad").write_bytes(macho("_OBJC_CLASS_$_NSUserDefaults"))
    notes = "\n".join(check.check(app).notes)
    assert "NSPrivacyAccessedAPICategoryDiskSpace is declared but no binary uses it" in notes
    assert errors(app) == []


def test_missing_manifest_and_tracking(app):
    manifest = plistlib.loads(MANIFEST.read_bytes())
    manifest["NSPrivacyTracking"] = True
    (app / "PrivacyInfo.xcprivacy").write_bytes(plistlib.dumps(manifest))
    assert any("NSPrivacyTracking" in e for e in errors(app))
    (app / "PrivacyInfo.xcprivacy").unlink()
    assert "no PrivacyInfo.xcprivacy in the app" in errors(app)


def test_native_code_outside_a_framework(app):
    (app / "python/lib/python3.14/lib-dynload").mkdir(parents=True)
    (app / "python/lib/python3.14/lib-dynload/_ctypes.so").write_bytes(macho("_stat"))
    assert any("native code outside a framework: python/lib/python3.14/lib-dynload/_ctypes.so" in e
               for e in errors(app))


def test_framework_not_for_iphoneos(app):
    framework(app, "_hashlib", platforms=("iPhoneSimulator",))
    assert any("_hashlib.framework isn't marked for iPhoneOS" in e for e in errors(app))


def test_icon_rendition_from_assetutil(app, tmp_path):
    # assetutil's listing of the device build's Assets.car: one 1024 px AppIcon.
    listing = [{"AssetStorageVersion": "x"}, {"AssetType": "Icon Image", "Name": "AppIcon", "PixelWidth": 1024},
               {"AssetType": "Image", "Name": "mdi_play", "PixelWidth": 72}]
    path = tmp_path / "assets.json"
    path.write_text(json.dumps(listing))
    assert errors(app, assetutil=path) == []
    path.write_text(json.dumps(listing[:1] + listing[2:]))
    assert any("missing [1024]" in e for e in errors(app, assetutil=path))


def test_loose_icon_files(app):
    (app / "AppIcon76x76@2x~ipad.png").unlink()
    assert errors(app) == ["CFBundleIcons~ipad names AppIcon76x76, but there is no AppIcon76x76@2x~ipad.png in the app"]


def png(width, height, colour):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0))


def test_icon_source(app, tmp_path):
    assert errors(app, icon_source=ICON) == []
    path = tmp_path / "icon.png"
    path.write_bytes(png(1024, 1024, 6))
    assert any("alpha channel" in e for e in errors(app, icon_source=path))
    path.write_bytes(png(512, 512, 2))
    assert any("not 1024 x 1024" in e for e in errors(app, icon_source=path))


def test_cli(app, capsys):
    assert check.main([str(app)]) == 0
    assert "App Store checks passed" in capsys.readouterr().out
    (app / "Assets.car").unlink()
    assert check.main([str(app)]) == 1

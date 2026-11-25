"""The Developer ID signing order (packaging/macos/sign_order.py, sign_app.sh).

A synthetic app shaped like PyInstaller's (Contents/MacOS, Frameworks with
Python's extension modules and a Qt framework, Resources linking into
Frameworks), with stand-in Mach-O headers; sign_app.sh --dry-run prints the
codesign commands, so this runs on Linux. The real signing only runs on
build.yml's macOS legs once the Developer ID secrets exist.
"""

import plistlib
import shutil
import struct
import subprocess

import pytest

from tests.ios_tools_support import ROOT

PACKAGING = ROOT / "packaging" / "macos"


def load_order():
    import importlib.util
    spec = importlib.util.spec_from_file_location("sign_order", PACKAGING / "sign_order.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sign_order = load_order()


def thin(filetype):
    return struct.pack("<IiiIIIII", 0xFEEDFACF, 0x0100000C, 0, filetype, 0, 0, 0, 0)


def fat(filetype):
    header = struct.pack(">II", 0xCAFEBABE, 2) + struct.pack(">iiIII", 0x0100000C, 0, 64, 32, 0) \
        + struct.pack(">iiIII", 0x01000007, 3, 96, 32, 0)
    return header.ljust(64, b"\x00") + thin(filetype) + thin(filetype)


@pytest.fixture
def app(tmp_path):
    bundle = tmp_path / "Chord Notepad.app"
    contents = bundle / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "ChordNotepad"}))
    (contents / "MacOS/ChordNotepad").write_bytes(thin(2))
    frameworks = contents / "Frameworks"
    (frameworks / "lib-dynload").mkdir(parents=True)
    (frameworks / "lib-dynload/_ctypes.cpython-314-darwin.so").write_bytes(thin(8))   # MH_BUNDLE
    (frameworks / "libfluidsynth.3.dylib").write_bytes(thin(6))                        # MH_DYLIB
    (frameworks / "Python").write_bytes(fat(6))
    qt = frameworks / "PySide6/Qt/lib/QtCore.framework"
    (qt / "Versions/A").mkdir(parents=True)
    (qt / "Versions/A/QtCore").write_bytes(thin(6))
    (qt / "Versions/Current").symlink_to("A")
    (qt / "QtCore").symlink_to("Versions/Current/QtCore")
    (frameworks / "helper").write_bytes(thin(2))                                       # another executable
    (frameworks / "base_library.zip").write_bytes(b"PK\x03\x04")
    (frameworks / "Example.class").write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x3d")    # Java's magic
    resources = contents / "Resources"
    resources.mkdir()
    (resources / "Python").symlink_to("../Frameworks/Python")
    (resources / "PySide6").symlink_to("../Frameworks/PySide6")
    return bundle


def test_inside_out(app):
    order = [(kind, str(path.relative_to(app.parent))) for kind, path in sign_order.signing_order(app)]
    names = [path for _, path in order]
    assert order[-1] == ("app", "Chord Notepad.app")
    # Each item once; links, the main executable and non-Mach-O files not at all.
    assert len(names) == len(set(names))
    assert not any("Resources" in n or n.endswith(("ChordNotepad", ".zip", ".class")) for n in names[:-1])
    qt_binary = names.index("Chord Notepad.app/Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore")
    qt_bundle = names.index("Chord Notepad.app/Contents/Frameworks/PySide6/Qt/lib/QtCore.framework")
    assert qt_binary < qt_bundle
    kinds = dict((path, kind) for kind, path in order)
    assert kinds["Chord Notepad.app/Contents/Frameworks/helper"] == "exe"
    assert kinds["Chord Notepad.app/Contents/Frameworks/Python"] == "lib"
    assert kinds["Chord Notepad.app/Contents/Frameworks/lib-dynload/_ctypes.cpython-314-darwin.so"] == "lib"


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_sign_app_dry_run(app):
    result = subprocess.run(["bash", str(PACKAGING / "sign_app.sh"), str(app), "--dry-run"],
                            capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "CODESIGN_IDENTITY": "ABCDEF0123456789",
                                 "PYTHON": shutil.which("python3")})
    assert result.returncode == 0, result.stderr
    lines = [l for l in result.stdout.splitlines() if l.startswith("codesign ")]
    assert all("--timestamp --options runtime" in l and "--sign ABCDEF0123456789" in l for l in lines)
    assert "--deep" not in result.stdout
    entitled = [l for l in lines if "--entitlements" in l]
    assert len(entitled) == 2  # the helper executable and the app
    assert lines[-1].endswith("/Chord Notepad.app") and "--entitlements" in lines[-1]
    assert f"Signed {len(lines)} items" in result.stdout


def test_entitlements_are_the_two_the_plan_names():
    data = plistlib.loads((PACKAGING / "entitlements.plist").read_bytes())
    assert data == {"com.apple.security.cs.allow-unsigned-executable-memory": True,
                    "com.apple.security.cs.disable-library-validation": True}


def test_the_ad_hoc_path_is_untouched():
    """Without the Developer ID secrets build.yml still runs make_dmg.sh, which signs ad hoc."""
    script = (PACKAGING / "make_dmg.sh").read_text()
    assert 'codesign --force --deep --sign - "$APP"' in script
    workflow = (ROOT / ".github/workflows/build.yml").read_text()
    assert 'run: packaging/macos/make_dmg.sh "dist/Chord Notepad.app" "dist/${{ matrix.asset_name }}"' in workflow


def test_shellcheck_clean():
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        pytest.skip("shellcheck not installed")
    scripts = [PACKAGING / name for name in ("sign_app.sh", "make_notarized_dmg.sh", "check_notarized.sh")]
    scripts.append(ROOT / "packaging/apple/import_certificates.sh")
    result = subprocess.run([shellcheck, *map(str, scripts)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout

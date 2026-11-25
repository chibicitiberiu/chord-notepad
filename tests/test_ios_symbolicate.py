"""ios/tools/symbolicate.sh and symbolicate_ips.py on Linux.

The crash reports are synthetic, in the .ips layout iOS writes (a JSON
header line, then the body with usedImages and threads). The end-to-end
test builds a real arm64 iOS Mach-O and its dSYM with clang, ld64.lld and
dsymutil, and skips when those LLVM tools aren't installed.
"""

import json
import shutil
import subprocess

import pytest

from tests.ios_tools_support import TOOLS, load_tool

ips = load_tool("symbolicate_ips")

APP_PATH = "/private/var/containers/Bundle/Application/0000/ChordNotepad.app/Frameworks/Demo.framework/Demo"


def _tool(*names):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


CLANG = _tool("clang-18", "clang")
LD64 = _tool("ld64.lld-18", "ld64.lld")
DSYMUTIL = _tool("dsymutil-18", "dsymutil")
SYMBOLIZER = _tool("llvm-symbolizer", "llvm-symbolizer-18")
NM = _tool("llvm-nm-18", "llvm-nm")


def make_ips(uuid, offsets, system_symbol="__pthread_kill"):
    header = {"app_name": "ChordNotepad", "app_version": "0.6.2", "build_version": "57", "bug_type": "309",
              "os_version": "iPhone OS 26.1 (23B85)", "timestamp": "2026-12-03 18:10:00.00 +0000",
              "incident_id": "00000000-0000-4000-8000-000000000000", "bundleID": "com.tibich.chordnotepad"}
    body = {
        "usedImages": [
            {"source": "P", "arch": "arm64", "base": 4_310_000_000, "size": 32768, "uuid": uuid.lower(),
             "path": APP_PATH, "name": "Demo"},
            {"source": "P", "arch": "arm64e", "base": 7_000_000_000, "size": 4096,
             "uuid": "11111111-2222-3333-4444-555555555555", "path": "/usr/lib/system/libsystem_kernel.dylib",
             "name": "libsystem_kernel.dylib"},
        ],
        "exception": {"type": "EXC_BAD_ACCESS", "signal": "SIGSEGV", "codes": "0x0000000000000001, 0x0"},
        "faultingThread": 0,
        "threads": [
            {"triggered": True, "id": 1, "queue": "com.apple.main-thread", "frames": [
                {"imageOffset": offsets[0], "imageIndex": 0},
                {"imageOffset": offsets[1], "imageIndex": 0},
            ]},
            {"id": 2, "name": "python-session", "frames": [
                {"imageOffset": 120, "imageIndex": 1, "symbol": system_symbol, "symbolLocation": 8},
            ]},
        ],
    }
    return json.dumps(header) + "\n" + json.dumps(body, indent=2) + "\n"


def test_parse_ips_reads_images_and_threads():
    report = ips.parse(make_ips("4C4C446D-5555-3144-A118-CB15D4629C5C", [16424, 16476]))
    assert [i.name for i in report.images] == ["Demo", "libsystem_kernel.dylib"]
    assert report.images[0].uuid == "4C4C446D-5555-3144-A118-CB15D4629C5C"
    assert ips.is_app_image(report.images[0]) and not ips.is_app_image(report.images[1])
    assert report.threads[0].triggered and report.threads[0].frames[0].first
    assert not report.threads[0].frames[1].first
    assert report.threads[1].title == "Thread 1 python-session"


def test_parse_text_format():
    text = """Incident Identifier: 0000
Exception Type:  EXC_CRASH (SIGABRT)

Thread 0 Crashed:
0   libsystem_kernel.dylib        0x00000001d8a2a1d4 __pthread_kill + 8
1   ChordNotepad                  0x0000000100a04028 0x100a00000 + 16424

Binary Images:
       0x100a00000 -        0x100a07fff ChordNotepad arm64  <4c4c446d55553144a118cb15d4629c5c> /private/var/containers/Bundle/Application/X/ChordNotepad.app/ChordNotepad
       0x1d8a20000 -        0x1d8a5ffff libsystem_kernel.dylib arm64e  <11111111222233334444555555555555> /usr/lib/system/libsystem_kernel.dylib
"""
    report = ips.parse(text)
    assert report.images[0].uuid == "4C4C446D-5555-3144-A118-CB15D4629C5C"
    thread = report.threads[0]
    assert thread.triggered
    assert thread.frames[1].image == 0 and thread.frames[1].offset == 16424
    assert thread.frames[0].symbol == "__pthread_kill + 8"


def test_a_dsym_from_another_build_is_refused():
    report = ips.parse(make_ips("4C4C446D-5555-3144-A118-CB15D4629C5C", [16424, 16476]))
    other = {"AAAAAAAA-5555-3144-A118-CB15D4629C5C": ips.Slice(None, "arm64", "AAAAAAAA-…", 0)}
    missing = ips.symbolicate(report, other, "llvm-symbolizer-never-called")
    assert [image.name for image in missing] == ["Demo"]


def test_shellcheck_clean():
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        pytest.skip("shellcheck not installed")
    result = subprocess.run([shellcheck, str(TOOLS / "symbolicate.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


@pytest.mark.skipif(not all([CLANG, LD64, DSYMUTIL, SYMBOLIZER, NM]),
                    reason="needs clang, ld64.lld, dsymutil, llvm-symbolizer and llvm-nm")
def test_symbolicates_a_real_dsym(tmp_path):
    source = tmp_path / "demo.c"
    source.write_text("int helper(int x) { return x * 3 + 1; }\n"
                      "__attribute__((noinline)) int crash_here(int *p) { return *p + helper(2); }\n"
                      "int entry(void) { return crash_here(0); }\n")
    obj, binary, dsym = tmp_path / "demo.o", tmp_path / "Demo", tmp_path / "Demo.framework.dSYM"
    subprocess.run([CLANG, "-target", "arm64-apple-ios17.0", "-g", "-O0", "-c", str(source), "-o", str(obj)],
                   check=True)
    subprocess.run([LD64, "-arch", "arm64", "-platform_version", "ios", "17.0", "17.0", "-dylib",
                    "-install_name", "@rpath/Demo.framework/Demo", "-o", str(binary), str(obj)], check=True)
    subprocess.run([DSYMUTIL, str(binary), "-o", str(dsym)], check=True)
    [slice_] = ips.macho_slices(dsym / "Contents/Resources/DWARF/Demo")
    assert slice_.arch == "arm64"

    symbols = {}
    for line in subprocess.run([NM, str(binary)], capture_output=True, text=True, check=True).stdout.splitlines():
        address, _, name = line.split()
        symbols[name] = int(address, 16)
    # Frame 0: the faulting load inside crash_here; frame 1: the return address in entry.
    crash = symbols["_crash_here"] + 8 - slice_.text_vmaddr
    caller = symbols["_entry"] + 12 - slice_.text_vmaddr
    report = tmp_path / "crash.ips"
    report.write_text(make_ips(slice_.uuid, [crash, caller]))

    env = {"PATH": "/usr/bin:/bin", "LLVM_SYMBOLIZER": SYMBOLIZER}
    result = subprocess.run(["bash", str(TOOLS / "symbolicate.sh"), str(report), str(tmp_path)],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "EXC_BAD_ACCESS SIGSEGV" in out
    assert "Thread 0 (com.apple.main-thread) (crashed)" in out
    assert "crash_here (demo.c:2)" in out
    assert "entry (demo.c:3)" in out
    assert "__pthread_kill" in out  # the system frame keeps the device's own symbol

    # The wrong dSYM: same name, another UUID.
    wrong = make_ips("AAAAAAAA-0000-0000-0000-000000000000", [crash, caller])
    report.write_text(wrong)
    result = subprocess.run(["bash", str(TOOLS / "symbolicate.sh"), str(report), str(tmp_path)],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 1 and "no dSYM with the UUID of Demo" in result.stderr

"""The Android versionCode literal matches VERSION.

android/app/build.gradle.kts writes versionCode as a plain number so F-Droid's
tooling can read it; this checks it the way F-Droid does (same regex as
fdroidserver's ``vcsearch_g``) and against the scheme
``(MAJ*10000 + MIN*100 + PATCH)*10 + rebuild`` (docs/RELEASE.md, "Android").
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GRADLE = REPO / "android" / "app" / "build.gradle.kts"

# fdroidserver/common.py: vcsearch_g
FDROID_VERSION_CODE = re.compile(r'''\b[Vv]ersionCode\s*=?\s*["'(]*([0-9][0-9_]*)["')]*''')


def _version() -> tuple:
    text = (REPO / "VERSION").read_text().strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text)
    assert match, f"VERSION must be MAJOR.MINOR.PATCH, got {text!r}"
    return tuple(int(x) for x in match.groups())


def _version_codes() -> list:
    codes = []
    for line in GRADLE.read_text().splitlines():
        match = FDROID_VERSION_CODE.search(line)
        if match:
            codes.append(int(match.group(1).replace("_", "")))
    return codes


def test_fdroid_finds_one_version_code():
    codes = _version_codes()
    assert codes, "F-Droid's regex finds no versionCode literal in build.gradle.kts"
    assert len(set(codes)) == 1, f"F-Droid's regex finds conflicting versionCodes: {codes}"


def test_version_code_matches_version_file():
    major, minor, patch = _version()
    assert minor < 100 and patch < 100
    code = _version_codes()[0]
    expected_base = major * 10000 + minor * 100 + patch
    assert code // 10 == expected_base, (
        f"versionCode {code} doesn't match VERSION {major}.{minor}.{patch}; "
        f"set it to {expected_base * 10} in {GRADLE.relative_to(REPO)}")

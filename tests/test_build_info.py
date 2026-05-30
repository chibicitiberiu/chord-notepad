"""Tests for build_info VERSION-file fallback and exposed fields."""

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_version_file_exists_and_is_simple():
    """The VERSION file must exist and contain a single non-empty token."""
    version_path = REPO_ROOT / "VERSION"
    assert version_path.is_file(), "VERSION file is missing at repo root"
    contents = version_path.read_text(encoding="utf-8").strip()
    assert contents, "VERSION file is empty"
    # Should be something like "0.1" or "1.2.3" - no spaces, no commentary.
    assert " " not in contents, f"VERSION file has unexpected whitespace: {contents!r}"
    assert all(c.isdigit() or c == "." for c in contents), (
        f"VERSION file should contain only digits and dots, got: {contents!r}"
    )


def test_build_info_reads_version_file():
    """In a fresh import, BASE_VERSION should match the VERSION file."""
    import build_info
    importlib.reload(build_info)

    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert build_info.BASE_VERSION == expected


def test_build_info_exposes_required_fields():
    """All consumers (application.py, main_window.py) rely on these attributes."""
    import build_info
    importlib.reload(build_info)

    required = [
        "BASE_VERSION",
        "BUILD_NUMBER",
        "VERSION",
        "BUILD_TYPE",
        "COMMIT_HASH",
        "COMMIT_SHORT",
        "BUILD_DATE",
    ]
    for name in required:
        assert hasattr(build_info, name), f"build_info missing required attribute: {name}"
        assert isinstance(getattr(build_info, name), str), f"{name} must be a string"


def test_build_info_dev_version_includes_base_version():
    """Local-dev VERSION string should embed the base version from the file."""
    import build_info
    importlib.reload(build_info)

    assert build_info.BASE_VERSION in build_info.VERSION, (
        f"VERSION {build_info.VERSION!r} should embed BASE_VERSION {build_info.BASE_VERSION!r}"
    )


def test_build_info_fallback_when_version_file_missing(tmp_path, monkeypatch):
    """If the VERSION file cannot be located, base version falls back to '0.0'."""
    import build_info

    # Point the module's resolution at a directory with no VERSION file.
    fake_module_path = tmp_path / "src" / "build_info.py"
    fake_module_path.parent.mkdir(parents=True)
    fake_module_path.write_text("# stub", encoding="utf-8")

    monkeypatch.setattr(build_info, "__file__", str(fake_module_path))
    assert build_info._read_version_file() == "0.0"


def test_package_version_matches_version_file():
    """src/__init__.py __version__ should agree with the VERSION file."""
    import importlib as _importlib
    import src as src_pkg  # type: ignore[import-not-found]

    _importlib.reload(src_pkg)
    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert src_pkg.__version__ == expected

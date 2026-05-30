"""
Auto-generated build information.

In CI builds, this file is overwritten with concrete values for the build.
For local development, values are computed from the VERSION file at repo root
plus a "dev-local" marker.
"""

from pathlib import Path


def _read_version_file() -> str:
    """Read the base version (e.g. '0.1') from the VERSION file at the repo root.

    Falls back to '0.0' if the file cannot be read.
    """
    try:
        version_path = Path(__file__).resolve().parent.parent / "VERSION"
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0"


BASE_VERSION = _read_version_file()
BUILD_NUMBER = "0"
COMMIT_HASH = "unknown"
COMMIT_SHORT = "unknown"
BUILD_DATE = "unknown"
BUILD_TYPE = "development"
VERSION = f"v{BASE_VERSION} (dev-local)"

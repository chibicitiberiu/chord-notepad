"""
Auto-generated build information.

In CI builds, this file is overwritten with concrete values for the build.
For local development, values are computed from the VERSION file at the app
root (found by chordnotepad_tk.desktop_paths) plus a "dev-local" marker.
"""

from chordnotepad_tk.desktop_paths import resolve_desktop_paths


def _read_version_file() -> str:
    """Read the base version (e.g. '0.1') from the VERSION file.

    Falls back to '0.0' if the file cannot be read.
    """
    return resolve_desktop_paths().read_version()


BASE_VERSION = _read_version_file()
BUILD_NUMBER = "0"
COMMIT_HASH = "unknown"
COMMIT_SHORT = "unknown"
BUILD_DATE = "unknown"
BUILD_TYPE = "development"
VERSION = f"v{BASE_VERSION} (dev-local)"

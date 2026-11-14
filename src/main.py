#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application.
"""

import os
import sys

from ui.desktop_paths import resolve_desktop_paths

# Where VERSION, resources/ and the help are (a checkout, a bundle, the
# Flatpak or the snap); handed down to everything that needs them.
APP_PATHS = resolve_desktop_paths()

# Set up FluidSynth DLL path for local development on Windows
# This must run BEFORE pyfluidsynth is imported (it has hardcoded paths that fail)
if sys.platform == 'win32' and not getattr(sys, 'frozen', False):
    # Monkeypatch os.add_dll_directory to not fail on missing directories
    # (pyfluidsynth unconditionally tries to add C:\tools\fluidsynth\bin)
    _original_add_dll_directory = os.add_dll_directory

    def _safe_add_dll_directory(path):
        try:
            return _original_add_dll_directory(path)
        except (FileNotFoundError, OSError):
            pass  # Ignore missing directories

    os.add_dll_directory = _safe_add_dll_directory

    # Add our local .tools directory
    if APP_PATHS.dev_dll_dir is not None and APP_PATHS.dev_dll_dir.is_dir():
        path = str(APP_PATHS.dev_dll_dir)
        _original_add_dll_directory(path)
        os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')

from utils.std_streams import ensure_std_streams

# Before anything else is imported: see utils/std_streams.py.
ensure_std_streams()

from application import Application


def main():
    """Thin wrapper that delegates to Application.main()"""
    exit_code = Application.main(APP_PATHS)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

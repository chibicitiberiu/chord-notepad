#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application.
"""

import os
import sys

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
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(src_dir)
    tools_paths = [
        os.path.join(project_dir, '.tools', 'bin'),
    ]
    for path in tools_paths:
        if os.path.isdir(path):
            _original_add_dll_directory(path)
            os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')
            break

from application import Application


def main():
    """Thin wrapper that delegates to Application.main()"""
    exit_code = Application.main()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

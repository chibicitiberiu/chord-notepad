#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application, for both desktop front ends:
``--ui tk`` (the default, the Tk window in this package) or ``--ui qt``
(the Qt Quick window in ``chordnotepad_desktop``, while it is being built).

The front end is chosen here, in the entry point every build already runs
(the PyInstaller spec, ``make run``, the Flatpak and snap launchers), so the
packaging stays as it is until the switch. The setup above the choice (the
resolved paths, the Windows FluidSynth DLL folder, the std streams) is the
same for both. When the Tk front end goes, this file and ``desktop_paths``
move into ``chordnotepad_desktop``.
"""

import argparse
import importlib.util
import os
import sys

from chordnotepad_tk.desktop_paths import resolve_desktop_paths

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

from chordnotepad.utils.std_streams import ensure_std_streams

# Before anything else is imported: see utils/std_streams.py.
ensure_std_streams()

#: The front ends ``--ui`` chooses from; the first is the default.
FRONT_ENDS = ("tk", "qt")


def parse_ui(argv):
    """Split ``--ui tk|qt`` off the command line.

    Returns:
        ``(front end, the other arguments)``. The rest is left alone (Qt
        reads options such as ``-platform`` itself).
    """
    parser = argparse.ArgumentParser(prog="chord-notepad", add_help=False)
    parser.add_argument("--ui", choices=FRONT_ENDS, default=FRONT_ENDS[0],
                        help="the desktop front end (default: %(default)s)")
    known, rest = parser.parse_known_args(argv)
    return known.ui, rest


def run_qt(argv) -> int:
    """Start the Qt Quick front end, or say why it can't start."""
    if importlib.util.find_spec("PySide6") is None:
        # A build that bundles only Tk (every build until the switch), or a
        # venv without the dev packages.
        print("chord-notepad: --ui qt needs PySide6, which this build doesn't include "
              "(run from source after `pipenv install --dev`).", file=sys.stderr)
        return 2
    from chordnotepad_desktop.main import run
    return run(APP_PATHS, argv)


def main(argv=None):
    """Start the front end ``--ui`` names (Tk by default) and exit with its code."""
    ui, rest = parse_ui(sys.argv[1:] if argv is None else argv)
    if ui == "qt":
        exit_code = run_qt(rest)
    else:
        # Imported here: it loads tkinter, which --ui qt never needs.
        from chordnotepad_tk.application import Application
        exit_code = Application.main(APP_PATHS)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

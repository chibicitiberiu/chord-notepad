"""The desktop app's entry point: ``python -m chordnotepad_desktop``.

Every build starts here (the PyInstaller spec runs ``__main__.py``, the
Flatpak and snap launchers and ``make run`` use ``-m chordnotepad_desktop``).
Before the Qt window is imported it resolves where the app's files are, sets
up the Windows FluidSynth DLL folder (before ``audio/fluid_ctypes.py`` loads
libfluidsynth) and the std streams, and reads CI's ``build_info``.

``--ui qt`` is still accepted and ignored: older scripts and the session's
own relaunch (``rendering.relaunch_command``) may pass it. ``--ui tk`` says
the Tk window is gone (it was removed in 0.6.0). Everything else on the
command line goes to the Qt window (``main.run``), which hands what it
doesn't know to QGuiApplication.
"""

import argparse
import importlib.util
import os
import sys

from chordnotepad_desktop.desktop_paths import resolve_desktop_paths

# Where VERSION, resources/ and the help are (a checkout, a bundle, the
# Flatpak or the snap); handed down to everything that needs them.
APP_PATHS = resolve_desktop_paths()

# Set up FluidSynth DLL path for local development on Windows. This must run
# before audio/fluid_ctypes.py is imported: it looks for libfluidsynth-3.dll on
# PATH when the module loads.
if sys.platform == 'win32' and not getattr(sys, 'frozen', False):
    # os.add_dll_directory that ignores missing directories
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

#: What ``--ui`` takes: ``qt`` (ignored) and ``tk`` (refused).
UI_CHOICES = ("qt", "tk")

#: What ``--ui tk`` prints before the app exits with code 2.
TK_REMOVED = ("chord-notepad: the Tk window was removed in 0.6.0; "
              "start chord-notepad without --ui tk.")


def parse_ui(argv):
    """Split ``--ui qt|tk`` off the command line.

    Returns:
        ``(the --ui value or None, the other arguments)``. The rest is left
        alone (Qt reads options such as ``-platform`` itself).
    """
    parser = argparse.ArgumentParser(prog="chord-notepad", add_help=False)
    parser.add_argument("--ui", choices=UI_CHOICES, default=None)
    known, rest = parser.parse_known_args(argv)
    return known.ui, rest


#: The build_info fields About and the start-up log show (CI writes build_info.py).
BUILD_INFO_FIELDS = ("VERSION", "BUILD_TYPE", "BUILD_NUMBER", "COMMIT_SHORT", "BUILD_DATE")


def read_build_info() -> dict:
    """``build_info``'s values for About and the start-up log."""
    from chordnotepad_desktop import build_info

    return {name: str(getattr(build_info, name)) for name in BUILD_INFO_FIELDS}


def run_qt(argv) -> int:
    """Start the Qt Quick window, or say why it can't start."""
    if importlib.util.find_spec("PySide6") is None:
        # A venv without the packages (every build bundles PySide6).
        print("chord-notepad: PySide6 is missing (run `pipenv install` first).", file=sys.stderr)
        return 2
    # Before PySide6 loads: Qt's plugins must find the Qt DLLs, also in the MSIX.
    from chordnotepad_desktop.windows_dlls import use_bundled_dll_dirs
    use_bundled_dll_dirs()
    from chordnotepad_desktop.main import run
    return run(APP_PATHS, argv, build_info=read_build_info())


def main(argv=None):
    """Start the Qt window and exit with its code."""
    ui, rest = parse_ui(sys.argv[1:] if argv is None else argv)
    if ui == "tk":
        print(TK_REMOVED, file=sys.stderr)
        sys.exit(2)
    sys.exit(run_qt(rest))

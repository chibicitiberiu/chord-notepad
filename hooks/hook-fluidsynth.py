"""
PyInstaller runtime hook for loading the bundled FluidSynth.

This hook runs before any modules are imported. On Windows it:
1. Monkeypatches os.add_dll_directory to not fail on missing directories
2. Adds the bundled FluidSynth DLL path to the search path

On macOS it points CHORD_NOTEPAD_LIBFLUIDSYNTH (src/audio/fluidsynth_import.py)
at the bundled libfluidsynth: ctypes' find_library doesn't search the app
bundle, and would otherwise find a Homebrew copy or nothing.
"""

import os
import sys

if sys.platform == 'win32':
    # Wrap os.add_dll_directory to handle missing directories gracefully
    _original_add_dll_directory = os.add_dll_directory

    def _safe_add_dll_directory(path):
        """Add DLL directory, ignoring FileNotFoundError for missing paths."""
        try:
            return _original_add_dll_directory(path)
        except FileNotFoundError:
            # Directory doesn't exist, skip silently
            pass
        except OSError:
            # Other OS errors, skip silently
            pass

    os.add_dll_directory = _safe_add_dll_directory

    # When running from PyInstaller bundle, add our bundled DLLs
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        dll_path = os.path.join(sys._MEIPASS, 'fluidsynth')
        if os.path.isdir(dll_path):
            _original_add_dll_directory(dll_path)
            # Also add to PATH as fallback for ctypes.util.find_library
            os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')

if sys.platform == 'darwin' and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    _library = os.path.join(sys._MEIPASS, 'fluidsynth', 'libfluidsynth.3.dylib')
    if os.path.isfile(_library):
        os.environ.setdefault('CHORD_NOTEPAD_LIBFLUIDSYNTH', _library)

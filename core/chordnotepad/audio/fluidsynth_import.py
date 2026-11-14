"""Import pyfluidsynth, optionally pointing it at a specific libfluidsynth.

pyfluidsynth finds the library with ctypes.util.find_library, which on Linux
only searches the system linker cache. Libraries bundled inside a snap aren't
in that cache, so the snap sets CHORD_NOTEPAD_LIBFLUIDSYNTH to the library's
path. Without the variable this is a plain ``import fluidsynth``.

The variable can also hold a bare soname such as ``libfluidsynth.so``: the
dynamic linker resolves it itself, so no file has to exist at that name. On
Android the native libraries stay inside the APK (there is no file path at
all) and CPython's find_library only looks in ``/system/lib64``, so there the
soname is the default.
"""

import ctypes.util
import logging
import os
import sys

logger = logging.getLogger(__name__)

LIBRARY_ENV = "CHORD_NOTEPAD_LIBFLUIDSYNTH"
ANDROID_SONAME = "libfluidsynth.so"


def _is_bare_soname(library: str) -> bool:
    """Whether ``library`` is a name for the linker rather than a path."""
    return os.sep not in library and "/" not in library


def _requested_library() -> str:
    """The library pyfluidsynth should load, or "" for its own lookup."""
    library = os.environ.get(LIBRARY_ENV, "")
    if not library and sys.platform == "android":
        return ANDROID_SONAME
    return library


def _import_fluidsynth():
    """Import and return the pyfluidsynth module."""
    library = _requested_library()
    if not library:
        import fluidsynth
        return fluidsynth
    if not _is_bare_soname(library) and not os.path.exists(library):
        logger.warning("%s points at a missing file: %s", LIBRARY_ENV, library)
        import fluidsynth
        return fluidsynth

    original = ctypes.util.find_library

    def find_library(name):
        if "fluidsynth" in name:
            return library
        return original(name)

    # pyfluidsynth looks the library up once, at import time
    ctypes.util.find_library = find_library
    try:
        import fluidsynth
    finally:
        ctypes.util.find_library = original
    logger.debug("Loaded FluidSynth from %s", library)
    return fluidsynth


fluidsynth = _import_fluidsynth()

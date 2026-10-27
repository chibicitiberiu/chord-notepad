"""Import pyfluidsynth, optionally pointing it at a specific libfluidsynth.

pyfluidsynth finds the library with ctypes.util.find_library, which on Linux
only searches the system linker cache. Libraries bundled inside a snap aren't
in that cache, so the snap sets CHORD_NOTEPAD_LIBFLUIDSYNTH to the library's
path. Without the variable this is a plain ``import fluidsynth``.
"""

import ctypes.util
import logging
import os

logger = logging.getLogger(__name__)

LIBRARY_ENV = "CHORD_NOTEPAD_LIBFLUIDSYNTH"


def _import_fluidsynth():
    """Import and return the pyfluidsynth module."""
    library = os.environ.get(LIBRARY_ENV, "")
    if not library:
        import fluidsynth
        return fluidsynth
    if not os.path.exists(library):
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

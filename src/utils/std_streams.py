"""Standard streams for windowed builds.

A windowed Windows build (PyInstaller ``console=False``) starts with
``sys.stdout`` and ``sys.stderr`` set to ``None``. Libraries that write to them
then crash the app: music21 warns on stderr at import time that numpy and
matplotlib (which the builds leave out) aren't installed.
"""

import os
import sys


def ensure_std_streams() -> None:
    """Point a missing ``sys.stdout``/``sys.stderr`` at the null device."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))

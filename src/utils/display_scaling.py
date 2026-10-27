"""Make Tk 8.6 on X11 honor the desktop's font DPI (Xft.dpi).

Tk 9 sizes fonts and widgets from the Xft.dpi X resource that KDE and GNOME
set when display scaling is above 100%. Tk 8.6 ignores it and uses the
screen's physical size, so on a scaled desktop everything comes out smaller
than in other apps. The snap ships Tk 8.6, which is where this shows up.
"""

import ctypes
import logging
import sys
import tkinter as tk
from typing import Optional

logger = logging.getLogger(__name__)

#: Tk measures fonts in points, 72 to the inch
_POINTS_PER_INCH = 72.0


def _read_xft_dpi() -> Optional[float]:
    """Return the Xft.dpi resource of the current X display, or None."""
    try:
        xlib = ctypes.CDLL("libX11.so.6")
    except OSError:
        return None
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XGetDefault.restype = ctypes.c_char_p
    xlib.XGetDefault.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]

    display = xlib.XOpenDisplay(None)
    if not display:
        return None
    try:
        value = xlib.XGetDefault(display, b"Xft", b"dpi")
    finally:
        xlib.XCloseDisplay(display)
    if not value:
        return None
    try:
        dpi = float(value.decode("ascii", "replace"))
    except ValueError:
        return None
    return dpi if dpi > 0 else None


def apply_xft_dpi(root: tk.Tk) -> None:
    """Set Tk's scaling from Xft.dpi on Linux/X11 when Tk is older than 9.

    Does nothing on other platforms, on Tk 9 (which already does this) or
    when the resource isn't set.
    """
    if not sys.platform.startswith("linux") or tk.TkVersion >= 9.0:
        return
    try:
        if root.tk.call("tk", "windowingsystem") != "x11":
            return
        dpi = _read_xft_dpi()
        if dpi is None:
            return
        root.tk.call("tk", "scaling", dpi / _POINTS_PER_INCH)
        logger.info("Applied Xft.dpi %s to Tk scaling", dpi)
    except (tk.TclError, OSError, AttributeError) as e:
        logger.warning("Could not apply Xft.dpi: %s", e)

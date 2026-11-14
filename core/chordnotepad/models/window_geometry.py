"""The main window's size and place, and the chord sheet's height, in a form
both desktop front ends can keep.

The Tk window saves Tk's geometry string, ``"WxH+X+Y"`` (config
``window_geometry``), and the sheet's height (``chord_sheet_height``), in
Tk's pixels: physical pixels on X11 and Windows. Qt works in logical
pixels (physical ones divided by the screen's scale). So the Qt window keeps
its own, neutral form:

- ``window_bounds``: ``{"width", "height", "x", "y"}`` in logical pixels
  (``x``/``y`` null when the window was never placed), plus
  ``window_maximized``, which Tk never used. The bounds are the window's
  normal geometry: a maximized window keeps the size it goes back to.
- ``chord_sheet_logical_height``: the Edit sheet's height in logical pixels.

Both front ends stay readable by the other while ``--ui tk`` is the 0.6.0
fallback:

- Qt writes its neutral values *and* Tk's (converted with the scale it
  passes in), so Tk opens where Qt closed. When the Tk value still converts
  to what Qt is saving, it is left as it was, so switching back and forth
  never moves a window by a pixel.
- Tk writes only its own keys and drops the neutral ones (``window_bounds``
  and ``chord_sheet_logical_height`` go to null, ``window_maximized`` to
  false: Tk never restores maximized), so Qt migrates from what Tk wrote.
- With no neutral value (a config from before Qt, or after Tk wrote), Qt
  reads Tk's value divided by the scale: what Tk showed, in logical pixels.
- A config with neither (a first start) has the neutral defaults
  (:data:`DEFAULT_BOUNDS`, ``DEFAULT_CHORD_SHEET_HEIGHT``), so a new user
  gets 900x600 logical at any scale (``Config.from_dict`` tells a key that
  is missing from one Tk set to null).

The scale is the front end's to give: how many Tk pixels make one logical
pixel. That is the screen's device pixel ratio on X11 and Windows, but 1.0
on macOS (Tk already works in points there).

Nothing here knows about Qt or Tk widgets; the config stores plain JSON.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from chordnotepad.constants import DEFAULT_CHORD_SHEET_HEIGHT

#: Tk's default geometry: the config's default, and what Tk opens at.
TK_DEFAULT_GEOMETRY = "900x600"
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 600
#: The neutral bounds of a first start (config ``window_bounds``).
DEFAULT_BOUNDS = {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT, "x": None, "y": None}

#: Tk's geometry: "WxH" or "WxH+X+Y" ("+-8" for a place left of or above the
#: primary screen). A "-X" offset counts from the right edge, which can't be
#: placed without the screen: such a geometry keeps only its size.
_TK_GEOMETRY = re.compile(r"^=?(\d+)x(\d+)(?:([+-])(-?\d+)([+-])(-?\d+))?$")


@dataclass(frozen=True)
class WindowGeometry:
    """A window's normal geometry (its size and place when not maximized).

    Attributes:
        width: Its width, at least 1.
        height: Its height, at least 1.
        x: Its left edge, or None when it has no saved place (the window
            manager places it).
        y: Its top edge, or None with ``x``.
        maximized: Whether it was maximized.
    """

    width: int
    height: int
    x: Optional[int] = None
    y: Optional[int] = None
    maximized: bool = False

    @property
    def has_position(self) -> bool:
        """Whether it has a saved place."""
        return self.x is not None and self.y is not None


def check_scale(scale: Any) -> float:
    """``scale`` as a float, if it is a finite number above 0.

    Raises:
        ValueError: For anything else.
    """
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        raise ValueError(f"scale must be a number, not {scale!r}")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError(f"scale must be above 0, not {scale!r}")
    return float(scale)


def _round(value: float) -> int:
    """Half up, the same way for both signs of a place (not Python's
    round-half-even)."""
    return int(math.floor(value + 0.5))


def to_logical(length: int, scale: float) -> int:
    """A length or place in Tk's pixels as logical pixels."""
    return _round(length / check_scale(scale))


def to_physical(length: int, scale: float) -> int:
    """A logical length or place in Tk's pixels."""
    return _round(length * check_scale(scale))


def parse_tk_geometry(text: Any) -> Optional[WindowGeometry]:
    """Tk's geometry string as a :class:`WindowGeometry` (Tk's pixels, not
    maximized); None if it isn't one or a side is 0."""
    if not isinstance(text, str):
        return None
    match = _TK_GEOMETRY.match(text.strip())
    if match is None:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    if match.group(3) == "+" and match.group(5) == "+":
        return WindowGeometry(width, height, int(match.group(4)), int(match.group(6)))
    return WindowGeometry(width, height)


def format_tk_geometry(geometry: WindowGeometry) -> str:
    """``geometry`` the way Tk writes it: ``"WxH+X+Y"``, or ``"WxH"`` with no place."""
    size = f"{geometry.width}x{geometry.height}"
    return f"{size}+{geometry.x}+{geometry.y}" if geometry.has_position else size


def _scaled(geometry: WindowGeometry, convert) -> WindowGeometry:
    return WindowGeometry(
        max(1, convert(geometry.width)), max(1, convert(geometry.height)),
        None if geometry.x is None else convert(geometry.x),
        None if geometry.y is None else convert(geometry.y),
        geometry.maximized)


def logical_geometry(geometry: WindowGeometry, scale: float) -> WindowGeometry:
    """A geometry in Tk's pixels in logical pixels."""
    check_scale(scale)
    return _scaled(geometry, lambda n: to_logical(n, scale))


def physical_geometry(geometry: WindowGeometry, scale: float) -> WindowGeometry:
    """A logical geometry in Tk's pixels."""
    check_scale(scale)
    return _scaled(geometry, lambda n: to_physical(n, scale))


def _int(value: Any) -> Optional[int]:
    """``value`` if it is a whole number (a bool is not), else None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def bounds_from_config(raw: Any) -> Optional[WindowGeometry]:
    """The config's ``window_bounds`` (not maximized), or None if it isn't a
    usable one (missing, junk, a side below 1, half a place)."""
    if not isinstance(raw, dict):
        return None
    width, height = _int(raw.get("width")), _int(raw.get("height"))
    if width is None or height is None or width < 1 or height < 1:
        return None
    x, y = _int(raw.get("x")), _int(raw.get("y"))
    if x is None or y is None:
        x = y = None
    return WindowGeometry(width, height, x, y)


def bounds_to_config(geometry: WindowGeometry) -> Dict[str, Optional[int]]:
    """``geometry`` as the config's ``window_bounds`` (without ``maximized``)."""
    return {"width": int(geometry.width), "height": int(geometry.height),
            "x": None if geometry.x is None else int(geometry.x),
            "y": None if geometry.y is None else int(geometry.y)}


def saved_geometry(bounds: Any, tk_geometry: Any, maximized: Any, scale: float) -> WindowGeometry:
    """The logical geometry to open the Qt window at.

    Args:
        bounds: The config's ``window_bounds``.
        tk_geometry: The config's ``window_geometry`` (Tk's string).
        maximized: The config's ``window_maximized``.
        scale: Tk pixels per logical pixel.

    The neutral bounds when there are some; otherwise Tk's geometry divided
    by ``scale``. A string that isn't a geometry gives the default 900x600
    logical, unplaced.
    """
    check_scale(scale)
    maximized = maximized is True
    neutral = bounds_from_config(bounds)
    if neutral is not None:
        return WindowGeometry(neutral.width, neutral.height, neutral.x, neutral.y, maximized)
    tk = parse_tk_geometry(tk_geometry)
    if tk is None:
        return WindowGeometry(DEFAULT_WIDTH, DEFAULT_HEIGHT, maximized=maximized)
    logical = logical_geometry(tk, scale)
    return WindowGeometry(logical.width, logical.height, logical.x, logical.y, maximized)


def tk_geometry_for(geometry: WindowGeometry, scale: float, current: Any) -> str:
    """Tk's geometry string for the logical ``geometry``: ``current`` when it
    already converts to it (so a round trip changes nothing), else
    ``geometry`` in Tk's pixels."""
    check_scale(scale)
    tk = parse_tk_geometry(current)
    if tk is not None and logical_geometry(tk, scale) == WindowGeometry(
            geometry.width, geometry.height, geometry.x, geometry.y):
        return current.strip()
    return format_tk_geometry(physical_geometry(geometry, scale))


def height_from_config(raw: Any) -> Optional[int]:
    """The config's ``chord_sheet_logical_height``, or None if it isn't a
    whole number of at least 1."""
    value = _int(raw)
    return value if value is not None and value >= 1 else None


def saved_sheet_height(logical: Any, tk_height: Any, scale: float) -> int:
    """The Edit sheet's logical height: the neutral one, else Tk's divided
    by ``scale`` (at least 1); junk gives the default."""
    check_scale(scale)
    neutral = height_from_config(logical)
    if neutral is not None:
        return neutral
    tk = _int(tk_height)
    if tk is None or tk < 1:
        return DEFAULT_CHORD_SHEET_HEIGHT
    return max(1, to_logical(tk, scale))


def tk_sheet_height_for(height: int, scale: float, current: Any) -> int:
    """Tk's sheet height for the logical ``height``: ``current`` when it
    already converts to it, else ``height`` in Tk's pixels."""
    check_scale(scale)
    tk = _int(current)
    if tk is not None and tk >= 1 and max(1, to_logical(tk, scale)) == height:
        return tk
    return max(1, to_physical(height, scale))

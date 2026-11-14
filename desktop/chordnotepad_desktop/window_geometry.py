"""The main window's size and place, kept between runs (today's config keys).

For now the Qt window reads and writes the keys the Tk window uses:
``window_geometry``, Tk's ``"WxH+X+Y"`` string, through the session's
``window_geometry`` / ``set_window_geometry``, and ``window_maximized``
(which Tk never wrote) in the config. Plan step B3 replaces both with a
neutral form and converts Tk's physical pixels to logical ones; until then
the numbers are taken as they are (the same at 100%), and this module is
the only place that knows the format.

What is saved is the window's **normal** geometry: a maximized or
full-screen window saves the size it had before, plus the flag, so
un-maximizing after a restart goes back to it. QWindow has no
``normalGeometry``, so :class:`GeometryKeeper` follows the window while it
is in the normal state.

On Wayland a client can't place its window: the position is ignored there
(Qt only applies the size).
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QGuiApplication, QWindow

logger = logging.getLogger(__name__)

#: Tk's geometry: "WxH", "WxH+X+Y" (also "+-X" for a position left of or
#: above the primary screen). Tk's "-X" (from the right edge) keeps the size only.
_TK_GEOMETRY = re.compile(r"^=?(\d+)x(\d+)(?:([+-])(-?\d+)([+-])(-?\d+))?$")
#: Tk's own default, the config's too.
DEFAULT_SIZE = (900, 600)
#: How much of the title bar must be on a screen for a saved place to be used.
_VISIBLE_MARGIN = 48


@dataclass(frozen=True)
class Geometry:
    """A window's normal geometry, in the config's pixels."""

    width: int
    height: int
    x: Optional[int] = None
    y: Optional[int] = None
    maximized: bool = False

    @property
    def has_position(self) -> bool:
        return self.x is not None and self.y is not None


def parse(text: str, maximized: bool = False) -> Optional[Geometry]:
    """Tk's geometry string as a :class:`Geometry`; None if it isn't one."""
    match = _TK_GEOMETRY.match((text or "").strip())
    if match is None:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    x = y = None
    if match.group(3) == "+" and match.group(5) == "+":
        x, y = int(match.group(4)), int(match.group(6))
    return Geometry(width, height, x, y, bool(maximized))


def format_geometry(geometry: Geometry) -> str:
    """``geometry`` as Tk writes it (``"WxH+X+Y"``, or ``"WxH"`` without a place)."""
    size = f"{geometry.width}x{geometry.height}"
    if not geometry.has_position:
        return size
    return f"{size}+{geometry.x}+{geometry.y}"


def placed_on_screens(geometry: Geometry, screens: Iterable[QRect]) -> Geometry:
    """``geometry`` without its place if its title bar wouldn't be on any screen
    (a monitor that is gone); the window manager then places it."""
    if not geometry.has_position:
        return geometry
    title_bar = QRect(geometry.x, geometry.y, geometry.width, _VISIBLE_MARGIN)
    for screen in screens:
        overlap = title_bar.intersected(screen)
        if overlap.width() >= _VISIBLE_MARGIN and overlap.height() > 0:
            return geometry
    logger.info("Saved window place %s,%s is off every screen; not used", geometry.x, geometry.y)
    return Geometry(geometry.width, geometry.height, None, None, geometry.maximized)


def load(session: Any, config: Any) -> Geometry:
    """The saved geometry (Tk's default size when there is none or it's unreadable)."""
    text = session.window_geometry
    maximized = bool(config.get("window_maximized", False))
    geometry = parse(text, maximized)
    if geometry is None:
        logger.info("Window geometry %r not understood; using the default size", text)
        geometry = Geometry(*DEFAULT_SIZE, maximized=maximized)
    return geometry


def available_screens() -> list:
    """The screens' available areas (without panels and docks)."""
    return [screen.availableGeometry() for screen in QGuiApplication.screens()]


def apply(window: QWindow, geometry: Geometry) -> None:
    """Size and place ``window`` before it is shown; show it with :func:`show`."""
    geometry = placed_on_screens(geometry, available_screens())
    window.resize(max(geometry.width, window.minimumWidth()),
                  max(geometry.height, window.minimumHeight()))
    if geometry.has_position:
        window.setPosition(geometry.x, geometry.y)


def show(window: QWindow, geometry: Geometry) -> None:
    """Show ``window``, maximized if it was."""
    if geometry.maximized:
        window.showMaximized()
    else:
        window.show()


def save(session: Any, config: Any, geometry: Geometry) -> None:
    """Remember ``geometry`` (on an approved close)."""
    session.set_window_geometry(format_geometry(geometry))
    config.set("window_maximized", bool(geometry.maximized))


class GeometryKeeper(QObject):
    """Follows the window's normal geometry, for :meth:`current`.

    Args:
        window: The main window (already sized by :func:`apply`).
        initial: What :func:`apply` was given: its place is kept until the
            window moves (its size is the window's).
    """

    def __init__(self, window: QWindow, initial: Geometry, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._window = window
        # The size apply() gave it (never below the window's minimum).
        self._normal = QRect(initial.x if initial.x is not None else 0,
                             initial.y if initial.y is not None else 0,
                             window.width(), window.height())
        self._has_position = initial.has_position
        for signal in (window.xChanged, window.yChanged, window.widthChanged, window.heightChanged):
            signal.connect(self._moved)
        window.windowStateChanged.connect(self._moved)

    def _is_normal(self) -> bool:
        state = self._window.windowStates()
        return not (state & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen
                             | Qt.WindowState.WindowMinimized))

    def _moved(self, *_args) -> None:
        if self._is_normal() and self._window.isVisible():
            self._normal = QRect(self._window.position(), self._window.size())
            self._has_position = True

    def current(self) -> Geometry:
        """The normal geometry now, and whether the window is maximized."""
        self._moved()
        state = self._window.windowStates()
        maximized = bool(state & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen))
        rect = self._normal
        if not self._has_position:
            return Geometry(rect.width(), rect.height(), None, None, maximized)
        return Geometry(rect.width(), rect.height(), rect.x(), rect.y(), maximized)

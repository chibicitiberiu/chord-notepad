"""The main window's size and place, kept between runs.

The core keeps the geometry in a neutral form, in logical pixels
(``chordnotepad.models.window_geometry``, plan step B3): the Qt window reads
it with the session's ``logical_window_geometry(scale)`` and saves it with
``set_logical_window_geometry(geometry, scale)``. The core also writes Tk's
``"WxH+X+Y"`` string from it, and migrates from that string when Tk saved
last, so ``--ui tk`` and ``--ui qt`` open in the same place. The scale it
needs is how many Tk pixels make one logical pixel: the window's device
pixel ratio on X11, Wayland (through XWayland) and Windows, 1.0 on macOS,
where Tk already works in points. This module is the only place that calls
those two session methods (``tests/qt/test_qt_session_store.py``).

What is saved is the window's **normal** geometry: a maximized or
full-screen window saves the size it had before, plus the flag, so
un-maximizing after a restart goes back to it. QWindow has no
``normalGeometry``, so :class:`GeometryKeeper` follows the window while it
is in the normal state.

On Wayland a client can't place its window: the position is ignored there
(Qt only applies the size).
"""

import logging
import sys
from typing import Any, Iterable, Optional

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QGuiApplication, QWindow

from chordnotepad.models.window_geometry import WindowGeometry

logger = logging.getLogger(__name__)

#: How much of the title bar must be on a screen for a saved place to be used.
_VISIBLE_MARGIN = 48


def tk_scale(window: QWindow) -> float:
    """Tk pixels per logical pixel for ``window``'s screen.

    The window's own ratio, not the screen's (pitfall 9: on KDE Wayland the
    Screen reports the integer output scale). Before the window is shown it
    is the ratio of the screen it will open on.
    """
    if sys.platform == "darwin":
        return 1.0
    ratio = window.devicePixelRatio()
    return ratio if ratio > 0 else 1.0


def placed_on_screens(geometry: WindowGeometry, screens: Iterable[QRect]) -> WindowGeometry:
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
    return WindowGeometry(geometry.width, geometry.height, None, None, geometry.maximized)


def load(session: Any, window: QWindow) -> WindowGeometry:
    """The saved geometry in logical pixels (the core's default size when
    there is none or it's unreadable)."""
    return session.logical_window_geometry(tk_scale(window))


def available_screens() -> list:
    """The screens' available areas (without panels and docks)."""
    return [screen.availableGeometry() for screen in QGuiApplication.screens()]


def apply(window: QWindow, geometry: WindowGeometry) -> WindowGeometry:
    """Size and place ``window`` before it is shown; show it with :func:`show`.

    Returns the geometry as applied (without a place that is on no screen).
    """
    geometry = placed_on_screens(geometry, available_screens())
    window.resize(max(geometry.width, window.minimumWidth()),
                  max(geometry.height, window.minimumHeight()))
    if geometry.has_position:
        window.setPosition(geometry.x, geometry.y)
    return geometry


def show(window: QWindow, geometry: WindowGeometry) -> None:
    """Show ``window``, maximized if it was."""
    if geometry.maximized:
        window.showMaximized()
    else:
        window.show()


def save(session: Any, window: QWindow, geometry: WindowGeometry) -> None:
    """Remember ``geometry`` (on an approved close)."""
    session.set_logical_window_geometry(geometry, tk_scale(window))


class GeometryKeeper(QObject):
    """Follows the window's normal geometry, for :meth:`current`.

    Args:
        window: The main window (already sized by :func:`apply`).
        initial: What :func:`apply` returned: its place is kept until the
            window moves (its size is the window's).
    """

    def __init__(self, window: QWindow, initial: WindowGeometry,
                 parent: Optional[QObject] = None) -> None:
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

    def current(self) -> WindowGeometry:
        """The normal geometry now, and whether the window is maximized."""
        self._moved()
        state = self._window.windowStates()
        maximized = bool(state & (Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen))
        rect = self._normal
        if not self._has_position:
            return WindowGeometry(rect.width(), rect.height(), None, None, maximized)
        return WindowGeometry(rect.width(), rect.height(), rect.x(), rect.y(), maximized)

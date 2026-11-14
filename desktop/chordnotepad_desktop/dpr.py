"""The window's real device pixel ratio for QML, and the deferred first show.

On KDE Wayland at 125% the screen reports 2.0 (the integer ``wl_output``
scale) while the window renders at 1.25 (fractional-scale-v1). QML's
``Screen.devicePixelRatio`` and the window's own QML ``devicePixelRatio``
both said 2.0 there, so icons were rasterised for 2.0 and shrunk (Qt Quick
pitfall 9). :class:`DprWatcher` reads ``QWindow.devicePixelRatio()`` from
Python once the window is exposed, and again on every
``DevicePixelRatioChange``, ``Expose`` and screen change (moving between a
1.25 and a 1.0 monitor re-rasterises). It writes it to the window's
``windowDpr`` property, which Main.qml binds to ``Theme.dpr``.

When the ratio changes after the first reading, text laid out at the old
ratio keeps its glyph positions (pitfall 10): the watcher bumps the window's
``fontRevision`` (Theme makes every font a new instance from it, so every
Text lays out again) and calls ``releaseResources`` to drop glyph caches.

The deferred show: the window's root item stays transparent (only the
window colour shows) until the ratio has been stable for ``settle_ms``, so
the first frames at a provisional ratio (2.0 before Wayland's fractional
scale arrives) are never seen; then ``contentReady`` turns true. It is shown
after ``reveal_by_ms`` whatever happens. The root item, not
ApplicationWindow's ``contentItem``: that one is only the area between the
header and the footer, so the toolbar and the menu bar would show early.
The watcher has to be made before the event loop runs the first frame.
"""

import logging
import time
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtGui import QWindow

logger = logging.getLogger(__name__)

#: How long the ratio must stay put before the content is shown.
SETTLE_MS = 350
#: The content is shown by then even if the ratio keeps changing.
REVEAL_BY_MS = 1500

#: Events after which the ratio is read again (after the event is handled).
WATCHED_EVENTS = {
    QEvent.Type.DevicePixelRatioChange: "DevicePixelRatioChange",
    QEvent.Type.Expose: "Expose",
    QEvent.Type.ScreenChangeInternal: "ScreenChangeInternal",
}


class DprWatcher(QObject):
    """Feeds ``window``'s device pixel ratio to QML and reveals its content.

    The window must have the QML properties ``windowDpr`` (real),
    ``fontRevision`` (int) and ``contentReady`` (bool), as Main.qml does.

    Args:
        window: The main window.
        ratio: Reads the ratio; ``window.devicePixelRatio`` by default (tests
            pass their own).
        settle_ms, reveal_by_ms: See the module docstring.
    """

    #: The ratio changed (the new value).
    dprChanged = Signal(float)
    #: The content was shown (``contentReady`` became true).
    revealed = Signal()

    def __init__(self, window: QWindow, ratio: Optional[Callable[[], float]] = None,
                 settle_ms: int = SETTLE_MS, reveal_by_ms: int = REVEAL_BY_MS, parent=None):
        super().__init__(parent)
        self._window = window
        self._ratio = ratio or window.devicePixelRatio
        self._t0 = time.monotonic()
        self.current: Optional[float] = None
        self._settle = QTimer(self, singleShot=True, interval=settle_ms)
        self._settle.timeout.connect(self.reveal)
        if not window.property("contentReady"):
            window.contentItem().setOpacity(0)
        window.installEventFilter(self)
        window.screenChanged.connect(lambda _screen: self.update("screen changed"))
        self.update("start")
        QTimer.singleShot(reveal_by_ms, self, self.reveal)

    def reveal(self):
        """Show the content now (once)."""
        if not self._window.property("contentReady"):
            self._window.contentItem().setOpacity(1)
            self._window.setProperty("contentReady", True)
            logger.debug("Content shown at ratio %s after %.0f ms",
                         self.current, 1000 * (time.monotonic() - self._t0))
            self.revealed.emit()

    def update(self, why: str = ""):
        """Read the ratio; on a change, push it to QML and relayout the text."""
        dpr = float(self._ratio())
        if dpr == self.current:
            return
        first = self.current is None
        self.current = dpr
        self._window.setProperty("windowDpr", dpr)
        if not first:
            self._window.setProperty("fontRevision", int(self._window.property("fontRevision")) + 1)
            QTimer.singleShot(0, self._window, self._window.releaseResources)
        self._settle.start()
        screen = self._window.screen()
        logger.debug("Device pixel ratio %s (%s; screen %s says %s)", dpr, why,
                     screen.name() if screen else "?", screen.devicePixelRatio() if screen else "?")
        self.dprChanged.emit(dpr)

    def eventFilter(self, obj, event):  # noqa: N802 (Qt)
        if obj is self._window:
            name = WATCHED_EVENTS.get(event.type())
            if name:
                # The ratio is only updated once the event has been handled.
                QTimer.singleShot(0, self, lambda: self.update(name))
        return False

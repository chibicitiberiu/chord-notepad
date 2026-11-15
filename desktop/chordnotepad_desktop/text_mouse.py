"""The editor's mouse selection, fixed where Qt Quick's TextArea falls short.

Pitfall 29: Qt Quick Controls' TextArea holds a left-button press back
(``QQuickPressHandler``, for its press-and-hold signal). The text only gets
it once the pointer has moved more than the drag distance *sideways*, or on
the release, and the moves before that are dropped. So a drag that went
mostly up or down (selecting a few lines) selected nothing and only put the
caret where it started on release, and a press held still for the
press-and-hold time lost the press altogether. The press it hands on late is
a copy without a timestamp, which the text's triple-click test reads as
"just now": after a double-click, a later click near the same place selected
the whole line.

:class:`TextMouse` is an event filter on the TextArea:

* It hands the TextArea each left-button press from a mouse or touchpad with
  the left button left out of ``buttons()``. The TextArea then starts no hold
  timer and passes the press, with its real timestamp, straight to the text
  (which also keeps the grab, so the ScrollView can't take the drag). The
  moves and the release that follow are the real ones. Touch keeps Qt's
  behaviour.
* While a drag-select is held outside the visible part of the text, it sends
  the TextArea the last move again every :data:`AUTOSCROLL_MS`: the selection
  reaches a line past the edge and the TextArea scrolls to it, as Tk's text
  scrolls on its own while the pointer is held below or above it. A
  TextArea only scrolls when the pointer moves.
"""

from typing import Optional

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QInputDevice, QMouseEvent
from PySide6.QtQuick import QQuickItem

#: How often a drag held past the edge scrolls a line (Tk's text: 50 ms).
AUTOSCROLL_MS = 50

_POINTERS = (QInputDevice.DeviceType.Mouse, QInputDevice.DeviceType.TouchPad)
_LEFT = Qt.MouseButton.LeftButton


def _from_pointer(event) -> bool:
    device = event.pointingDevice()
    return device is not None and device.type() in _POINTERS


def _viewport(item: QQuickItem) -> Optional[QQuickItem]:
    """The Flickable the TextArea scrolls in (a ScrollView's), or None."""
    parent = item.parentItem()
    while parent is not None and not parent.inherits("QQuickFlickable"):
        parent = parent.parentItem()
    return parent


class TextMouse(QObject):
    """Event filter for the editor's TextArea (``area.installEventFilter``)."""

    def __init__(self, area: QQuickItem) -> None:
        super().__init__(area)
        self._area = area
        self._sending = False
        self._held = False
        self._last: Optional[QMouseEvent] = None
        self._timer = QTimer(self)
        self._timer.setInterval(AUTOSCROLL_MS)
        self._timer.timeout.connect(self._autoscroll)

    def eventFilter(self, obj, event):  # noqa: N802 (Qt)
        if self._sending:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == _LEFT and _from_pointer(event):
            self._held = True
            self._last = None
            others = Qt.MouseButton(event.buttons().value & ~_LEFT.value)
            press = QMouseEvent(QEvent.Type.MouseButtonPress, event.position(), event.scenePosition(),
                                event.globalPosition(), _LEFT, others, event.modifiers(),
                                event.pointingDevice())
            press.setTimestamp(event.timestamp())
            self._send(obj, press)
            event.setAccepted(press.isAccepted())
            return True
        if kind == QEvent.Type.MouseMove and self._held:
            if event.buttons() & _LEFT:
                self._last = QMouseEvent(QEvent.Type.MouseMove, event.position(), event.scenePosition(),
                                         event.globalPosition(), Qt.MouseButton.NoButton,
                                         event.buttons(), event.modifiers(), event.pointingDevice())
                if self._outside(event.scenePosition()):
                    if not self._timer.isActive():
                        self._timer.start()
                else:
                    self._timer.stop()
            else:
                self._release()
        elif kind in (QEvent.Type.MouseButtonRelease, QEvent.Type.UngrabMouse) and self._held:
            if kind == QEvent.Type.UngrabMouse or event.button() == _LEFT:
                self._release()
        return False

    def _release(self) -> None:
        self._held = False
        self._last = None
        self._timer.stop()

    def _outside(self, scene: QPointF) -> bool:
        """Whether ``scene`` is past the visible part of the text (above or
        below it; left or right of it when the text is wider)."""
        view = _viewport(self._area)
        if view is None:
            return False
        rect = view.mapRectToScene(QRectF(0, 0, view.width(), view.height()))
        if scene.y() < rect.top() or scene.y() > rect.bottom():
            return True
        wider = view.property("contentWidth") > view.width() + 0.5
        return wider and (scene.x() < rect.left() or scene.x() > rect.right())

    def _autoscroll(self) -> None:
        last = self._last
        if not self._held or last is None or not self._outside(last.scenePosition()):
            self._timer.stop()
            return
        # The same pointer, where it now is over the scrolled text.
        local = self._area.mapFromScene(last.scenePosition())
        move = QMouseEvent(QEvent.Type.MouseMove, local, last.scenePosition(), last.globalPosition(),
                           Qt.MouseButton.NoButton, last.buttons(), last.modifiers(),
                           last.pointingDevice())
        self._send(self._area, move)

    def _send(self, obj, event) -> None:
        self._sending = True
        try:
            QCoreApplication.sendEvent(obj, event)
        finally:
            self._sending = False

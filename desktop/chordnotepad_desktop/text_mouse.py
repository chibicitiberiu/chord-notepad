"""The editor's mouse: selection where Qt Quick's TextArea falls short, chords as links.

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
* A valid chord in the text is a link (Tibi, 2026-11-15): a left press on
  one never reaches the TextArea, so no click on a chord selects anything
  (a double-click no word, a triple-click no line, a drag from it nothing).
  The press puts the caret where it is and drops the selection, as a plain
  click would; with Shift held it leaves both alone. The release plays the
  chord, every time (rolled with Shift), unless the pointer was dragged off
  first. With Alt held a chord is plain text, as Alt+click on a link in a
  browser: the press goes to the TextArea and nothing plays.
"""

from typing import Callable, Optional

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QInputDevice, QMouseEvent
from PySide6.QtQuick import QQuickItem

#: How often a drag held past the edge scrolls a line (Tk's text: 50 ms).
AUTOSCROLL_MS = 50

_POINTERS = (QInputDevice.DeviceType.Mouse, QInputDevice.DeviceType.TouchPad)
_LEFT = Qt.MouseButton.LeftButton
_ALT = Qt.KeyboardModifier.AltModifier
_SHIFT = Qt.KeyboardModifier.ShiftModifier


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

    def __init__(self, area: QQuickItem,
                 chord_at: Optional[Callable[[QPointF], int]] = None,
                 tap: Optional[Callable[[int, bool], None]] = None,
                 place_caret: Optional[Callable[[QPointF], None]] = None) -> None:
        """``chord_at(point)`` is the position of the valid chord under
        ``point`` (the TextArea's coordinates), or -1; ``tap(position,
        rolled)`` plays it; ``place_caret(point)`` moves the caret there and
        drops the selection. Without ``chord_at`` chords are plain text."""
        super().__init__(area)
        self._area = area
        self._chord_at = chord_at
        self._tap = tap
        self._place_caret = place_caret
        self._sending = False
        self._held = False
        self._last: Optional[QMouseEvent] = None
        self._timer = QTimer(self)
        self._timer.setInterval(AUTOSCROLL_MS)
        self._timer.timeout.connect(self._autoscroll)
        #: The chord press under way: (position, scene point, rolled), or None.
        self._chord: Optional[tuple] = None
        self._dragged = False
        #: Whether the current press, and the one before it, were on a chord.
        self._was_chord = False
        self._after_chord = False

    def eventFilter(self, obj, event):  # noqa: N802 (Qt)
        if self._sending:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == _LEFT:
            self._after_chord = self._was_chord
            self._was_chord = self._chord_press(event)
            if self._was_chord:
                event.setAccepted(True)
                return True
        elif kind == QEvent.Type.MouseButtonDblClick and event.button() == _LEFT:
            # The text would select the word: not on a chord, nor when the
            # first click of the two was on one.
            if self._was_chord or self._after_chord:
                event.setAccepted(True)
                return True
            return False
        if self._chord is not None:
            return self._chord_event(kind, event)
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

    def _chord_press(self, event) -> bool:
        """Start a chord press if ``event`` (a left press) is on a valid
        chord without Alt; whether it did."""
        if self._chord_at is None or event.modifiers() & _ALT:
            return False
        position = self._chord_at(event.position())
        if position < 0:
            return False
        self._release()
        rolled = bool(event.modifiers() & _SHIFT)
        self._chord = (position, QPointF(event.scenePosition()), rolled)
        self._dragged = False
        # The ScrollView's Flickable mustn't take a drag that starts here.
        self._area.setKeepMouseGrab(True)
        if self._area.property("activeFocusOnPress") and not self._area.hasActiveFocus():
            self._area.forceActiveFocus(Qt.FocusReason.MouseFocusReason)
        if not rolled and self._place_caret is not None:
            self._place_caret(event.position())
        return True

    def _chord_event(self, kind, event) -> bool:
        """The moves and the release of a chord press: none reach the text."""
        if kind == QEvent.Type.MouseMove:
            if not event.buttons() & _LEFT:
                self._end_chord()
                return True
            start = self._chord[1]
            moved = event.scenePosition() - start
            if moved.manhattanLength() > QGuiApplication.styleHints().startDragDistance():
                self._dragged = True
            return True
        if kind == QEvent.Type.MouseButtonRelease and event.button() == _LEFT:
            position, _, rolled = self._chord
            dragged = self._dragged
            self._end_chord()
            if not dragged and self._tap is not None:
                self._tap(position, rolled)
            return True
        if kind == QEvent.Type.UngrabMouse:
            self._end_chord()
        return False

    def _end_chord(self) -> None:
        self._chord = None
        self._dragged = False
        self._area.setKeepMouseGrab(False)

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

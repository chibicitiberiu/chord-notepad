"""The wheel as Wayland delivers it.

On Wayland (KWin, Qt 6.12) Qt tags every pointer event with the seat's
primary pointing device, and the seat's only pointing device is the one
Qt Wayland registers for touchpad gestures, named "touchpad". So a plain
mouse wheel arrives with a TouchPad device, and a WheelHandler, which by
default takes only ``PointerDevice.Mouse``, never sees it: Ctrl+wheel didn't
zoom anywhere, and neither the sheet's wheel nor Shift+wheel scrolled.
Seen live on a virtual KWin with fake input (the ``touchpad`` device on
``seat0``; the "core pointer" mouse has no seat). The tests here send the
events with such a device; the other wheel tests use the mouse.
"""

import re

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(QT_PROBLEM, allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QInputDevice, QPointingDevice, QWheelEvent  # noqa: E402

from chordnotepad_desktop.main import QML_DIR  # noqa: E402
from tests.qt.test_qt_chord_sheet import finish, make_sheet  # noqa: E402
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, song  # noqa: E402

SHIFT = Qt.KeyboardModifier.ShiftModifier
NOT_SYNTHESIZED = Qt.MouseEventSource.MouseEventNotSynthesized
BY_SYSTEM = Qt.MouseEventSource.MouseEventSynthesizedBySystem

_TOUCHPAD = []


def wayland_pointer():
    """A device like Qt Wayland's: type TouchPad, named "touchpad", on seat0."""
    if not _TOUCHPAD:
        _TOUCHPAD.append(QPointingDevice(
            "touchpad", 0, QInputDevice.DeviceType.TouchPad, QPointingDevice.PointerType.Finger,
            QInputDevice.Capability.Position, 5, 0, "seat0"))
    return _TOUCHPAD[0]


def send(window, point, angle, pixel=QPoint(0, 0), modifiers=NO_MODIFIER,
         phase=Qt.ScrollPhase.NoScrollPhase, source=NOT_SYNTHESIZED):
    pos = QPointF(point)
    event = QWheelEvent(pos, QPointF(window.mapToGlobal(pos)), pixel, angle, Qt.MouseButton.NoButton,
                        modifiers, phase, False, source, wayland_pointer())
    QGuiApplication.sendEvent(window, event)


def mouse_notch(window, point, notches, modifiers):
    """A mouse wheel on KWin: 120 per notch (axis_value120) and 15 px a notch."""
    send(window, point, QPoint(0, 120 * notches), QPoint(0, 15 * notches), modifiers)


def text_point(ed, host="editHost"):
    item = ed.item(host)
    return item.mapToScene(QPointF(item.width() / 3, item.height() / 2))


@pytest.fixture
def sh(qapp, qtbot, tmp_path):
    sh = make_sheet(qapp, qtbot, tmp_path)
    yield sh
    finish(sh)


def test_every_wheel_handler_takes_the_touchpad_device():
    """A new WheelHandler without the touchpad would be dead on Wayland."""
    found = 0
    for path in sorted(QML_DIR.rglob("*.qml")):
        text = path.read_text()
        for match in re.finditer(r"\bWheelHandler\s*\{", text):
            depth, end = 0, match.end() - 1
            for end in range(match.end() - 1, len(text)):
                depth += {"{": 1, "}": -1}.get(text[end], 0)
                if depth == 0:
                    break
            block = text[match.start():end]
            found += 1
            assert "PointerDevice.TouchPad" in block, f"{path.name}: {block.splitlines()[1].strip()}"
    assert found >= 5


def test_ctrl_wheel_from_a_wayland_mouse_zooms_the_text_in_edit_and_play(sh):
    song(sh, "C G Am F\n" * 3)
    sh.set_cursor(0)
    size = sh.bridge.fontSize
    mouse_notch(sh.window, text_point(sh), 1, CTRL)
    sh.qtbot.waitUntil(lambda: sh.bridge.fontSize == size + 1, timeout=1000)
    sh.window.setProperty("mode", "play")
    sh.qtbot.waitUntil(lambda: sh.area.property("readOnly") is True, timeout=1000)
    sh.run()
    mouse_notch(sh.window, text_point(sh, "playTextHost"), -1, CTRL)
    sh.qtbot.waitUntil(lambda: sh.bridge.fontSize == size, timeout=1000)


def test_ctrl_and_a_touchpad_scroll_zoom_the_text_once_a_notchs_worth_has_come(sh):
    song(sh, "C G Am F\n")
    size = sh.bridge.fontSize
    point = text_point(sh)
    # Two fingers: Qt Wayland sends a begin, updates whose angle is 12 x the
    # pixels, and an end.
    send(sh.window, point, QPoint(0, 0), modifiers=CTRL, phase=Qt.ScrollPhase.ScrollBegin, source=BY_SYSTEM)
    for _ in range(3):
        send(sh.window, point, QPoint(0, 36), QPoint(0, 3), CTRL, Qt.ScrollPhase.ScrollUpdate, BY_SYSTEM)
    sh.run(50)
    assert sh.bridge.fontSize == size                    # 108 of 120
    send(sh.window, point, QPoint(0, 36), QPoint(0, 3), CTRL, Qt.ScrollPhase.ScrollUpdate, BY_SYSTEM)
    send(sh.window, point, QPoint(0, 0), modifiers=CTRL, phase=Qt.ScrollPhase.ScrollEnd, source=BY_SYSTEM)
    sh.qtbot.waitUntil(lambda: sh.bridge.fontSize == size + 1, timeout=1000)


def test_shift_wheel_from_a_wayland_mouse_scrolls_the_text_sideways(sh):
    song(sh, "C" + " " * 400 + "G\n")                    # wrap is off by default
    flick = sh.item("editorScroll").property("contentItem")
    sh.set_cursor(0)
    mouse_notch(sh.window, text_point(sh), -1, SHIFT)
    sh.qtbot.waitUntil(lambda: flick.property("contentX") > 0, timeout=1000)


def test_the_sheet_zooms_and_scrolls_with_a_wayland_mouse(sh):
    sh.to_play(700)
    sh.wait_sheet("keyboard")
    view = sh.view
    centre = sh.at(view.width() / 2, view.height() / 2)
    mouse_notch(sh.window, centre, -1, NO_MODIFIER)
    sh.qtbot.waitUntil(lambda: view.property("scrollX") > 0, timeout=1000)
    mouse_notch(sh.window, centre, 1, CTRL)
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.2), timeout=2000)

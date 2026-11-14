"""The main window's plumbing: the ratio from Python, the deferred show, snapping.

DprWatcher is driven with a fake ratio (offscreen windows report 1.0); the
QML side is checked through Theme and the snapped items. The snapping and
the dark switch are checked on C2's sample controls (``sample_window``,
tests/qt/qml/ThemeSample.qml), as the shell has no caret or heading yet;
the ratio and the deferred show on the real main window.
"""

import math

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtQml import qmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad_desktop.dpr import DprWatcher  # noqa: E402


def theme(main):
    """The CNTheme Theme singleton the window binds to."""
    return qmlEngine(main.window).singletonInstance("CNTheme", "Theme")


class FakeRatio:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def item(main, name):
    found = main.window.findChild(QQuickItem, name)
    assert found is not None, name
    return found


def scene_x(quick_item):
    return quick_item.mapToScene(QPointF(0, 0)).x()


def descendant_with(quick_item, prop):
    """The first item under quick_item that has QML property prop (e.g. PixelIcon's devicePx)."""
    for child in quick_item.childItems():
        if child.property(prop) is not None:
            return child
        found = descendant_with(child, prop)
        if found is not None:
            return found
    return None


def click(main, quick_item):
    centre = quick_item.mapToScene(QPointF(quick_item.width() / 2, quick_item.height() / 2))
    QTest.mouseClick(main.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     centre.toPoint())


def test_the_content_is_shown_once_the_ratio_settles(main_window, qtbot):
    window = main_window.window
    assert window.property("windowDpr") == window.devicePixelRatio() == 1.0
    assert window.contentItem().opacity() == 0           # hidden at first
    qtbot.waitUntil(lambda: window.property("contentReady"), timeout=3000)
    assert window.contentItem().opacity() == 1


def test_a_ratio_change_reaches_qml_and_relays_out_the_text(main_window, qtbot):
    window = main_window.window
    ratio = FakeRatio(2.0)
    watcher = DprWatcher(window, ratio=ratio, settle_ms=50, reveal_by_ms=5000, parent=window)
    assert window.property("windowDpr") == 2.0
    revision = window.property("fontRevision")
    ratio.value = 1.25
    with qtbot.waitSignal(watcher.dprChanged, timeout=1000) as changed:
        watcher.update("test")
    assert changed.args == [1.25]
    assert window.property("windowDpr") == 1.25
    assert window.property("fontRevision") == revision + 1
    qtbot.waitUntil(lambda: theme(main_window).property("dpr") == 1.25, timeout=1000)
    assert theme(main_window).property("fontRevision") == revision + 1
    assert theme(main_window).property("hairline") == 0.8
    watcher.update("same ratio")
    assert window.property("fontRevision") == revision + 1   # no change, no relayout


def test_the_content_is_shown_by_the_deadline_even_if_the_ratio_keeps_moving(main_window, qtbot):
    window = main_window.window
    window.setProperty("contentReady", False)
    ratio = FakeRatio(1.0)
    watcher = DprWatcher(window, ratio=ratio, settle_ms=10_000, reveal_by_ms=100, parent=window)
    with qtbot.waitSignal(watcher.revealed, timeout=2000):
        pass
    assert window.property("contentReady") is True


def test_icons_lines_and_text_land_on_device_pixels_at_125(sample_window, qtbot):
    main_window = sample_window
    window = main_window.window
    watcher = DprWatcher(window, ratio=FakeRatio(1.25), settle_ms=10, parent=window)
    qtbot.waitUntil(lambda: window.property("contentReady"), timeout=3000)
    caret = item(main_window, "caret")
    qtbot.waitUntil(lambda: theme(main_window).property("dpr") == 1.25, timeout=1000)
    qtbot.wait(50)        # Theme.bumpLayout's frame debounce, then the re-snap

    # The caret: a whole number of device pixels wide, on the device grid.
    rect = next(c for c in caret.childItems() if c.objectName() == "snapLineRect")
    assert math.isclose(rect.width() * 1.25, round(rect.width() * 1.25), abs_tol=1e-6)
    assert math.isclose(scene_x(rect) * 1.25, round(scene_x(rect) * 1.25), abs_tol=1e-3)

    # The icon: whole device pixels (devicePx / dpr logical).
    icon = descendant_with(item(main_window, "undoButton"), "devicePx")
    device_px = icon.property("devicePx")
    assert device_px == round(device_px) and math.isclose(icon.width() * 1.25, device_px)

    # The heading's snapped origin (SText).
    heading = item(main_window, "heading")
    snapped = heading.mapToScene(QPointF(0, 0))
    assert math.isclose(snapped.x() * 1.25, round(snapped.x() * 1.25), abs_tol=1e-3)
    assert math.isclose(snapped.y() * 1.25, round(snapped.y() * 1.25), abs_tol=1e-3)
    assert watcher.current == 1.25


def test_the_dark_switch_turns_the_theme_dark(sample_window, qtbot):
    main_window = sample_window
    window = main_window.window
    qtbot.waitUntil(lambda: window.property("contentReady"), timeout=3000)
    switch = item(main_window, "darkSwitch")
    assert window.color().name() == "#ffffff"
    click(main_window, switch)
    qtbot.waitUntil(lambda: theme(main_window).property("dark") is True, timeout=1000)
    assert window.color().name() == "#1e1f22"
    click(main_window, switch)
    qtbot.waitUntil(lambda: window.color().name() == "#ffffff", timeout=1000)


def test_a_screenshot_renders(main_window, qtbot):
    window = main_window.window
    qtbot.waitUntil(lambda: window.property("contentReady"), timeout=3000)
    image = window.grabWindow()
    assert not image.isNull() and image.width() > 100
    colours = {image.pixelColor(x, y).name() for x in range(0, image.width(), 7)
               for y in range(0, image.height(), 7)}
    assert len(colours) > 5            # more than a blank window

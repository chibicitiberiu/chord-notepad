"""The hidden menu bar's keys (alt_watcher.py): Alt tap, Alt+letter, click, Escape.

Events go straight to the filter with a window as the target, the way the
application delivers them first (an event the window passes on to an item
reaches the filter again with the item as target, and must be ignored).
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QEvent, QObject, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWindow  # noqa: E402

from chordnotepad_desktop.alt_watcher import MENU_LETTERS, AltWatcher  # noqa: E402

ALT = Qt.KeyboardModifier.AltModifier
NONE = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def window(qapp):
    win = QWindow()
    yield win
    win.destroy()


@pytest.fixture
def watcher(qapp):
    return AltWatcher()


@pytest.fixture
def seen(watcher):
    log = []
    watcher.altTapped.connect(lambda: log.append("tap"))
    watcher.altLetter.connect(lambda letter: log.append(letter))
    watcher.pointerPressed.connect(lambda y: log.append(("press", y)))
    watcher.escapePressed.connect(lambda: log.append("escape"))
    return log


def key(kind, code, mods=NONE, text="", repeat=False):
    return QKeyEvent(kind, code, mods, text, repeat)


def press(watcher, target, code, mods=NONE, text="", repeat=False):
    return watcher.eventFilter(target, key(QEvent.Type.KeyPress, code, mods, text, repeat))


def release(watcher, target, code, mods=NONE):
    return watcher.eventFilter(target, key(QEvent.Type.KeyRelease, code, mods))


def mouse_press(watcher, target, y):
    event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, y), QPointF(5, y),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, NONE)
    return watcher.eventFilter(target, event)


def test_the_menu_letters_are_the_menu_bars():
    assert MENU_LETTERS == "FEVPTH"


def test_an_alt_tap_is_reported(watcher, window, seen):
    assert press(watcher, window, Qt.Key.Key_Alt, ALT) is False
    assert release(watcher, window, Qt.Key.Key_Alt) is False
    assert seen == ["tap"]


def test_alt_with_another_key_is_not_a_tap(watcher, window, seen):
    press(watcher, window, Qt.Key.Key_Alt, ALT)
    press(watcher, window, Qt.Key.Key_Left, ALT)
    release(watcher, window, Qt.Key.Key_Alt)
    assert seen == []


def test_a_click_while_alt_is_down_cancels_the_tap(watcher, window, seen):
    press(watcher, window, Qt.Key.Key_Alt, ALT)
    mouse_press(watcher, window, 40)
    release(watcher, window, Qt.Key.Key_Alt)
    assert seen == [("press", 40.0)]


def test_auto_repeat_doesnt_start_a_tap(watcher, window, seen):
    press(watcher, window, Qt.Key.Key_Alt, ALT, repeat=True)
    release(watcher, window, Qt.Key.Key_Alt)
    assert seen == []


@pytest.mark.parametrize("text", ["f", ""])      # with and without the event's text
def test_alt_letter_opens_that_menu_while_the_bar_is_hidden(watcher, window, seen, text):
    press(watcher, window, Qt.Key.Key_Alt, ALT)
    assert press(watcher, window, Qt.Key.Key_F, ALT, text) is True     # consumed
    release(watcher, window, Qt.Key.Key_Alt)
    assert seen == ["F"]


def test_letters_that_name_no_menu_pass_through(watcher, window, seen):
    assert press(watcher, window, Qt.Key.Key_Q, ALT, "q") is False
    assert seen == []


def test_a_shown_bar_takes_its_own_mnemonics(watcher, window, seen):
    watcher.setMenuHidden(False)
    assert press(watcher, window, Qt.Key.Key_F, ALT, "f") is False
    assert seen == []


def test_ctrl_alt_letter_is_not_a_menu(watcher, window, seen):
    mods = ALT | Qt.KeyboardModifier.ControlModifier
    assert press(watcher, window, Qt.Key.Key_F, mods, "f") is False
    assert seen == []


def test_escape_and_clicks_are_reported_for_hiding_the_bar(watcher, window, seen):
    press(watcher, window, Qt.Key.Key_Escape)
    mouse_press(watcher, window, 123)
    assert seen == ["escape", ("press", 123.0)]


def test_events_to_items_are_ignored(watcher, seen):
    """Each key reaches the filter again for the item it is delivered to."""
    item = QObject()
    press(watcher, item, Qt.Key.Key_Alt, ALT)
    release(watcher, item, Qt.Key.Key_Alt)
    assert press(watcher, item, Qt.Key.Key_F, ALT, "f") is False
    assert seen == []


def test_the_installed_filter_sees_real_window_events(qapp, watcher, window, seen):
    qapp.installEventFilter(watcher)
    try:
        qapp.sendEvent(window, key(QEvent.Type.KeyPress, Qt.Key.Key_Alt, ALT))
        qapp.sendEvent(window, key(QEvent.Type.KeyRelease, Qt.Key.Key_Alt))
    finally:
        qapp.removeEventFilter(watcher)
    assert seen == ["tap"]

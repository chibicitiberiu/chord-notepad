"""The keyboard focus and the modal dialogs: whichever way a dialog is
opened (the ☰ menu and its submenus, the hidden menu bar, a shortcut, the
toolbar), it has the keys, and nothing puts them back in the editor behind it.

The manual pass found Help › Quick start from the ☰ menu typing into the song
behind the dialog: the menu's ``onClosed`` ran after the dialog had opened and
gave the editor the focus back.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from tests.qt.test_qt_chrome import (  # noqa: E402
    ALT, CTRL, NO_MODIFIER, Chrome, alt_tap, menu_item_at, plain_text,
)
from tests.qt.test_qt_editor import start  # noqa: E402

SONG = "{key: G}\nG   D   Em  C\nAmazing grace\n"


class Focus(Chrome):
    """The chrome harness plus clicks inside just-opened popups."""

    def drawn(self):
        # A popup's rows have their places after its first polish (H1's note).
        with self.qtbot.waitSignal(self.window.frameSwapped, timeout=1000):
            self.window.update()

    def click_at(self, it):
        self.drawn()
        centre = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, NO_MODIFIER, centre)

    def hover(self, it):
        self.drawn()
        QTest.mouseMove(self.window, it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint())

    def row(self, menu, label):
        for i in range(menu.property("count")):
            item = menu_item_at(menu, i)
            text = item.property("text")
            if text and plain_text(text) == label:
                return item
        raise AssertionError(f"no {label!r} in {menu.objectName()}")

    def submenu(self, menu, title):
        # PySide can't convert a MenuItem's subMenu (QQuickMenu*).
        for child in menu.findChildren(QObject):
            if (child.inherits("QQuickMenu")
                    and plain_text(child.property("title") or "") == title):
                return child
        raise AssertionError(f"no submenu {title!r} in {menu.objectName()}")

    def wait_open(self, menu):
        self.qtbot.waitUntil(lambda: menu.property("opened") is True, timeout=1000)

    def choose(self, menu, *path):
        """Click through ``path`` in an opened menu: submenus by hovering
        their row (as a person does), the last row by a click."""
        self.wait_open(menu)
        for label in path[:-1]:
            row = self.row(menu, label)
            self.hover(row)
            menu = self.submenu(menu, label)
            self.wait_open(menu)
        self.click_at(self.row(menu, path[-1]))

    def open_burger(self):
        menu = self.obj("appMenu")
        self.click_at(self.it("appMenuButton"))
        self.wait_open(menu)
        return menu

    def focus_in(self, dialog_name):
        """Whether the window's focus item is inside the popup ``dialog_name``."""
        dialog = self.obj(dialog_name)
        popup_item = dialog.property("contentItem").parentItem()
        focus = self.window.activeFocusItem()
        while focus is not None:
            if focus is popup_item:
                return True
            focus = focus.parentItem()
        return False


@pytest.fixture
def app(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    ed = Focus(harness, qtbot)
    qtbot.waitUntil(lambda: ed.area.hasActiveFocus(), timeout=1000)
    ed.song(SONG)
    yield ed
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def assert_has_the_keys(app, name, text=SONG):
    """The dialog ``name`` is open with the focus, also a while later (after
    every menu has closed and every deferred call has run), and a typed key
    doesn't reach the song."""
    modified = app.store.state("DocumentState").value("is_modified")
    dialog = app.obj(name)
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    app.run(300)
    assert dialog.property("visible") is True
    assert app.focus_in(name), app.window.activeFocusItem()
    assert not app.area.hasActiveFocus()
    QTest.keyClick(app.window, "x")
    app.run()
    assert app.text() == text
    assert app.store.state("DocumentState").value("is_modified") is modified


# -- Quick Start: the reported case ----------------------------------------------------------


def test_quick_start_from_the_burger_menus_help_has_the_keys(app):
    app.choose(app.open_burger(), "Help", "Quick start")
    assert_has_the_keys(app, "quickStartDialog")
    # Right pages it.
    indicator = app.it("quickStartPageIndicator")
    app.qtbot.waitUntil(lambda: indicator.property("text").startswith("1 /"), timeout=2000)
    QTest.keyClick(app.window, Qt.Key.Key_Right)
    app.qtbot.waitUntil(lambda: indicator.property("text").startswith("2 /"), timeout=1000)



# -- Every dialog, every way in ----------------------------------------------------------------

def burger(*path):
    return lambda app: app.choose(app.open_burger(), *path)


def menu_bar(letter, menu_name, *path):
    # Alt+letter opens that menu, the bar hidden (F1); then a click.
    def go(app):
        app.key(getattr(Qt.Key, f"Key_{letter}"), ALT)
        app.choose(app.obj(menu_name), *path)
    return go


def keys(key, modifier=NO_MODIFIER):
    return lambda app: app.key(key, modifier)


def toolbar(name):
    return lambda app: app.click_at(app.it(name))


WAYS_IN = {
    "burger-quick-start": (burger("Help", "Quick start"), "quickStartDialog"),
    "burger-licences": (burger("Help", "Open source licences"), "licencesDialog"),
    "burger-about": (burger("Help", "About Chord Notepad"), "aboutDialog"),
    "burger-user-guide": (burger("Help", "User guide"), "errorDialog"),   # no help built here
    "bar-quick-start": (menu_bar("H", "helpMenu", "Quick start"), "quickStartDialog"),
    "bar-licences": (menu_bar("H", "helpMenu", "Open source licences"), "licencesDialog"),
    "bar-about": (menu_bar("H", "helpMenu", "About Chord Notepad"), "aboutDialog"),
    "bar-user-guide": (menu_bar("H", "helpMenu", "User guide"), "errorDialog"),
    "bar-transpose": (menu_bar("T", "toolsMenu", "Transpose…"), "transposeDialog"),
    "bar-suggest-capo": (menu_bar("T", "toolsMenu", "Suggest capo…"), "capoDialog"),
    "ctrl-t": (keys(Qt.Key.Key_T, CTRL), "transposeDialog"),
    "f1": (keys(Qt.Key.Key_F1), "errorDialog"),
    "toolbar-transpose": (toolbar("transposeButton"), "transposeDialog"),
    "toolbar-capo": (toolbar("capoButton"), "capoDialog"),
}


@pytest.mark.parametrize("way", sorted(WAYS_IN))
def test_a_dialog_has_the_keys_whichever_way_it_was_opened(app, way):
    go, name = WAYS_IN[way]
    go(app)
    assert_has_the_keys(app, name)
    # Escape closes it and the editor has the keys back.
    QTest.keyClick(app.window, Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: app.obj(name).property("visible") is False, timeout=2000)
    app.qtbot.waitUntil(lambda: app.area.hasActiveFocus(), timeout=1000)


def test_licences_from_about_has_the_keys_and_gives_them_back_to_about(app):
    app.choose(app.open_burger(), "Help", "About Chord Notepad")
    assert_has_the_keys(app, "aboutDialog")
    app.click_at(app.it("aboutLicences"))
    assert_has_the_keys(app, "licencesDialog")
    QTest.keyClick(app.window, Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: app.obj("licencesDialog").property("visible") is False, timeout=2000)
    app.run(100)
    assert app.focus_in("aboutDialog")


@pytest.mark.parametrize("way", ["burger", "bar"])
def test_the_unsaved_changes_question_has_the_keys(app, way):
    QTest.keyClick(app.window, "z")
    app.qtbot.waitUntil(lambda: app.store.state("DocumentState").value("is_modified") is True,
                        timeout=2000)
    typed = app.text()
    if way == "burger":
        app.choose(app.open_burger(), "New")
    else:
        menu_bar("F", "fileMenu", "New")(app)
    assert_has_the_keys(app, "unsavedDialog", text=typed)


def test_a_deferred_focus_call_doesnt_take_the_keys_from_a_dialog(app):
    QMetaObject.invokeMethod(app.obj("appDialogs"), "openAbout")
    assert_has_the_keys(app, "aboutDialog")
    # What the menus, the workspace switch and the sidebars call.
    QMetaObject.invokeMethod(app.obj("editorPane"), "focusEditor")
    app.run()
    assert app.focus_in("aboutDialog")


@pytest.mark.parametrize("way", ["burger", "bar", "ctrl-comma"])
def test_the_settings_window_has_the_keys(app, way):
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow
    if way == "burger":
        app.choose(app.open_burger(), "Settings…")
    elif way == "bar":
        menu_bar("T", "toolsMenu", "Settings…")(app)
    else:
        app.key(Qt.Key.Key_Comma, CTRL)
    settings = app.window.findChild(QQuickWindow, "settingsWindow")
    app.qtbot.waitUntil(lambda: settings.isVisible(), timeout=2000)
    app.qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is settings, timeout=2000)
    app.run(300)
    assert QGuiApplication.focusWindow() is settings
    assert settings.activeFocusItem() is not None
    settings.close()
    app.qtbot.waitUntil(lambda: not settings.isVisible(), timeout=2000)


def test_the_open_picker_has_the_keys(app):
    from PySide6.QtGui import QGuiApplication
    app.choose(app.open_burger(), "Open…")
    picker = app.obj("filePicker")
    app.qtbot.waitUntil(lambda: picker.property("visible") is True, timeout=2000)
    app.run(300)
    # Qt Quick's own dialog is a window of its own: the keys go there.
    assert QGuiApplication.focusWindow() is not app.window
    assert QGuiApplication.focusWindow() is not None
    QMetaObject.invokeMethod(picker, "reject")
    app.qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is app.window, timeout=2000)
    app.qtbot.waitUntil(lambda: app.area.hasActiveFocus(), timeout=1000)

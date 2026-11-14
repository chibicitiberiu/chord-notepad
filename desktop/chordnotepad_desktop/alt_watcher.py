"""The hidden menu bar's keyboard: an Alt tap shows it, Alt+letter opens a menu.

Firefox-style: the menu bar is hidden by default. An Alt tap (press and
release with no other key or click between) toggles it; Alt plus a menu's
letter while it is hidden opens that menu; a click below the bar or Escape
hides it again (the window decides, from :attr:`AltWatcher.pointerPressed`
and :attr:`AltWatcher.escapePressed`).

Qt Quick has no Alt-only shortcut, and a hidden MenuBar registers no
mnemonics (Qt Quick pitfall 18), so this is an application event filter. It
looks only at events sent to a window: each key event is delivered again to
the items inside, and counting those would see every key twice. On macOS the
menu bar is the native global one and this has nothing to do.
"""

from PySide6.QtCore import QEvent, QObject, Qt, Signal, Slot
from PySide6.QtGui import QWindow

#: The top menus' letters, in menu bar order (File, Edit, View, Playback,
#: Tools, Help).
MENU_LETTERS = "FEVPTH"


class AltWatcher(QObject):
    """Install with ``app.installEventFilter(watcher)``; QML listens to the signals."""

    #: Alt was pressed and released on its own.
    altTapped = Signal()
    #: Alt+letter while the menu bar is hidden (the letter, upper case).
    altLetter = Signal(str)
    #: A mouse button went down in a window (its y, in window coordinates).
    pointerPressed = Signal(float)
    #: Escape went down in a window.
    escapePressed = Signal()

    def __init__(self, letters: str = MENU_LETTERS, parent=None):
        super().__init__(parent)
        self._alone = False
        self.letters = letters
        #: Letters are only taken while the bar is hidden (set from QML).
        self.menuHidden = True

    @Slot(bool)
    def setMenuHidden(self, hidden: bool):  # noqa: N802 (called from QML)
        self.menuHidden = hidden

    def eventFilter(self, obj, event):  # noqa: N802 (Qt)
        if not isinstance(obj, QWindow):
            return False
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Alt:
                if not event.isAutoRepeat():
                    self._alone = True
                return False
            self._alone = False
            if event.key() == Qt.Key.Key_Escape:
                self.escapePressed.emit()
            mods = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
            if self.menuHidden and mods == Qt.KeyboardModifier.AltModifier:
                letter = event.text().upper() if event.text() else ""
                key = int(event.key())
                if not letter and int(Qt.Key.Key_A) <= key <= int(Qt.Key.Key_Z):
                    letter = chr(key)
                if letter and letter in self.letters:
                    self.altLetter.emit(letter)
                    return True
        elif kind == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Alt:
            if self._alone:
                self.altTapped.emit()
            self._alone = False
        elif kind == QEvent.Type.MouseButtonPress:
            self._alone = False
            self.pointerPressed.emit(event.position().y())
        return False

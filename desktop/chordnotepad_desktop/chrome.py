"""The window's chrome that the session keeps: the whole-window zoom and the
menu bar (plan step F1), plus the File menu's documents (``files.py``).

:class:`ChromeModel` reads what was kept at start (the session's
``ui_scale`` and ``menu_bar_shown``, direct calls like the volume) and sends
the changes back as bridge commands (``set_ui_scale``,
``set_menu_bar_shown``). The colours (Dark theme) go through
``set_ui_theme``, straight from QML, since ``SettingsState`` carries them.

The menu bar: hidden by default, an Alt tap shows it (``alt_watcher.py``),
"Show menu bar" keeps it. On macOS the menu bar is the native global one and
always there; elsewhere Qt is told not to use a platform menu bar
(:func:`configure_menu_bar`), or a desktop with a global menu (KDE's, Unity's
D-Bus menus) would take the bar out of the window.
"""

import os
import sys
from typing import Any, Optional

from PySide6.QtCore import Property, QCoreApplication, QObject, Qt, Signal, Slot

from chordnotepad.constants import DEFAULT_UI_SCALE, UI_SCALE_MAX, UI_SCALE_MIN, UI_SCALE_STEP
from chordnotepad.session import toolbar_texts
from chordnotepad_desktop.files import FilesModel

#: The Edit toolbar's tooltips that come from the core (Tk's AB | Do, Stop).
TEXTS = {
    "american": toolbar_texts.AMERICAN_TOOLTIP,
    "european": toolbar_texts.EUROPEAN_TOOLTIP,
    "toEuropean": toolbar_texts.convert_tooltip("european"),
    "toAmerican": toolbar_texts.convert_tooltip("american"),
    "stop": toolbar_texts.STOP_TOOLTIP,
}


def is_mac() -> bool:
    """Whether the menu bar is the native global one (macOS)."""
    return sys.platform == "darwin"


def configure_menu_bar(mac: Optional[bool] = None) -> None:
    """The Qt Quick MenuBar is native on macOS only (before any QML loads)."""
    mac = is_mac() if mac is None else mac
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, not mac)


#: The switch Tk's file dialogs had (``CHORD_NOTEPAD_FILE_DIALOG``): "tk"
#: there, "qt" here, keeps the toolkit's own dialog.
FILE_DIALOG_ENV = "CHORD_NOTEPAD_FILE_DIALOG"
PORTAL_THEME = "xdgdesktopportal"


def prefer_portal_file_dialogs(environ, platform: str = sys.platform) -> bool:
    """On Linux, ask Qt for the desktop portal's file dialogs, as Tk does.

    Inside a Flatpak or a Snap Qt picks the ``xdgdesktopportal`` platform
    theme by itself. Outside, Tk's file dialogs try the portal first (KDE's
    or GNOME's own dialog), so the Qt window does too: the theme wraps the
    desktop's own one and adds only the portal's dialogs and colour scheme;
    without a portal its dialogs are Qt Quick's own. Left alone when
    ``QT_QPA_PLATFORMTHEME`` is set already, ``CHORD_NOTEPAD_FILE_DIALOG``
    asks for the toolkit's dialog (``tk`` or ``qt``), or there is no session
    bus (the theme would then guess the colour scheme, and guessed dark on a
    bare X server). Call before the QGuiApplication exists.

    Returns:
        Whether it set ``QT_QPA_PLATFORMTHEME``.
    """
    if not platform.startswith("linux") or environ.get("QT_QPA_PLATFORMTHEME"):
        return False
    if environ.get(FILE_DIALOG_ENV, "").strip().lower() in ("tk", "qt"):
        return False
    if not session_bus_reachable(environ):
        # No portal to ask; the theme would only guess the colour scheme.
        return False
    environ["QT_QPA_PLATFORMTHEME"] = PORTAL_THEME
    return True


def session_bus_reachable(environ) -> bool:
    """Whether there is a session bus to find a portal on: an address, and
    for a ``unix:path=`` one, its socket."""
    address = environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    if not address:
        return False
    for part in address.split(";")[0].split(":", 1)[-1].split(","):
        if part.startswith("path="):
            return os.path.exists(part[len("path="):])
    return True


def stepped_scale(scale: float, steps: int) -> float:
    """``scale`` moved by ``steps`` of UI_SCALE_STEP, kept in range, to whole percent."""
    target = round(float(scale) + int(steps) * UI_SCALE_STEP, 2)
    return min(UI_SCALE_MAX, max(UI_SCALE_MIN, target))


class ChromeModel(QObject):
    """The zoom and menu bar the session keeps, and the File menu's documents.

    Args:
        store: The window's SessionStore.
        mac: Whether the menu bar is the native global one (macOS); detected
            by default.
    """

    uiScaleChanged = Signal()
    menuBarShownChanged = Signal()

    def __init__(self, store: Any, mac: Optional[bool] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._mac = is_mac() if mac is None else bool(mac)
        self._scale = float(store.direct("ui_scale"))
        self._menu_bar = bool(store.direct("menu_bar_shown"))
        self._files = FilesModel(store, parent=self)

    def _get_files(self) -> QObject:
        return self._files

    #: The recent list and the file pickers (files.py).
    files = Property(QObject, _get_files, constant=True)

    def _get_texts(self) -> dict:
        return dict(TEXTS)

    #: The toolbar's tooltips (:data:`TEXTS`).
    texts = Property("QVariantMap", _get_texts, constant=True)

    def _get_mac(self) -> bool:
        return self._mac

    #: The menu bar is the native global one (always there).
    mac = Property(bool, _get_mac, constant=True)

    def _get_scale(self) -> float:
        return self._scale

    #: The whole-window zoom (Theme.scale), 0.7-2.0.
    uiScale = Property(float, _get_scale, notify=uiScaleChanged)

    def _get_scale_min(self) -> float:
        return UI_SCALE_MIN

    uiScaleMin = Property(float, _get_scale_min, constant=True)

    def _get_scale_max(self) -> float:
        return UI_SCALE_MAX

    uiScaleMax = Property(float, _get_scale_max, constant=True)

    @Slot(int)
    def stepUiScale(self, steps: int) -> None:  # noqa: N802 (Qt)
        """Zoom the whole window in (+1) or out (-1) by 10%."""
        self._set_scale(stepped_scale(self._scale, steps))

    @Slot()
    def resetUiScale(self) -> None:  # noqa: N802 (Qt)
        """Back to 100%."""
        self._set_scale(DEFAULT_UI_SCALE)

    def _set_scale(self, scale: float) -> None:
        if scale == self._scale:
            return
        self._scale = scale
        self.uiScaleChanged.emit()
        self._store.submit("set_ui_scale", {"scale": scale})

    def _get_menu_bar(self) -> bool:
        return self._menu_bar

    def _set_menu_bar(self, shown: bool) -> None:
        shown = bool(shown)
        if shown == self._menu_bar:
            return
        self._menu_bar = shown
        self.menuBarShownChanged.emit()
        self._store.submit("set_menu_bar_shown", {"shown": shown})

    #: "Show menu bar": the bar stays shown (else an Alt tap shows it).
    menuBarShown = Property(bool, _get_menu_bar, _set_menu_bar, notify=menuBarShownChanged)

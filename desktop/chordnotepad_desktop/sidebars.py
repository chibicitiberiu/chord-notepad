"""The Edit workspace's rail and sidebars (plan step F5): the Python side.

The rail, the Directives palette and the chord identifier are QML
(``IconRail.qml``, ``DirectivePalette.qml``, ``IdentifierPanel.qml``; the
identifier's model is :mod:`chordnotepad_desktop.identifier`). This holds
what they share with the session:

* **Which sidebar is open** (:attr:`SidebarModel.current`: ``directives``,
  ``identifier`` or "" when collapsed) and **its width** in layout units
  (``Theme.px``), kept in the config through the bridge commands
  ``set_sidebar`` / ``set_sidebar_width`` and read back at start with the
  direct calls ``sidebar`` / ``sidebar_width``. A first start has the
  palette open at 76 units (the mockup's).
* **The palette's tiles**, from the core's ``session.snippets.PALETTE``
  (B4): :attr:`SidebarModel.paletteGroups`. A click inserts the tile's text
  with ``insert_snippet`` at the caret; the session fills the template for
  the song and selects its value (``TextEdited.anchor``).
* **Why the tiles are disabled** while the editor is read-only (playing or
  paused): :attr:`SidebarModel.lockedReason`.
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from chordnotepad.constants import SIDEBAR_WIDTH_MAX, SIDEBAR_WIDTH_MIN, SIDEBARS
from chordnotepad.session.snippets import PALETTE
from chordnotepad_desktop.status_bar import READ_ONLY_NOTICE

logger = logging.getLogger(__name__)

#: Why the palette is disabled while a song plays or is paused: the status
#: bar's read-only notice (the mockup's line), one text for both.
LOCKED_REASON = READ_ONLY_NOTICE
#: The tooltip's last line for a tile that can be used (the mockup's).
TILE_ACTION = "Click to insert · drag to place"


def palette_groups() -> list:
    """The palette as plain data for QML: ``[{title, tiles: [{id, icon,
    caption, text, name, hint}]}]``."""
    return [{"title": group.title,
             "tiles": [{"id": t.id, "icon": t.icon, "caption": t.caption, "text": t.text,
                        "name": t.name, "hint": t.hint} for t in group.snippets]}
            for group in PALETTE]


class SidebarModel(QObject):
    """The open sidebar and its width, and the palette's data.

    Args:
        store: The window's :class:`~chordnotepad_desktop.session_store.SessionStore`.
    """

    changed = Signal()

    def __init__(self, store: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        current = store.direct("sidebar")
        self._current = current if current in SIDEBARS else ""
        self._width = float(store.direct("sidebar_width"))
        self._groups = palette_groups()

    def _get_current(self) -> str:
        return self._current

    #: ``directives``, ``identifier``, or "" (collapsed).
    current = Property(str, _get_current, notify=changed)

    def _get_width(self) -> float:
        return self._width

    #: The sidebar's width in layout units (SIDEBAR_WIDTH_MIN-SIDEBAR_WIDTH_MAX).
    width = Property(float, _get_width, notify=changed)

    def _get_min(self) -> float:
        return float(SIDEBAR_WIDTH_MIN)

    minWidth = Property(float, _get_min, constant=True)

    def _get_max(self) -> float:
        return float(SIDEBAR_WIDTH_MAX)

    maxWidth = Property(float, _get_max, constant=True)

    def _get_groups(self) -> list:
        return self._groups

    #: The palette's groups and tiles (:func:`palette_groups`).
    paletteGroups = Property("QVariantList", _get_groups, constant=True)

    def _get_locked_reason(self) -> str:
        return LOCKED_REASON

    lockedReason = Property(str, _get_locked_reason, constant=True)

    def _get_tile_action(self) -> str:
        return TILE_ACTION

    tileAction = Property(str, _get_tile_action, constant=True)

    @Slot(str)
    def show(self, sidebar: str) -> None:
        """Open ``sidebar`` ("" collapses)."""
        sidebar = sidebar if sidebar in SIDEBARS else ""
        if sidebar != self._current:
            self._current = sidebar
            self.changed.emit()
            self._store.submit("set_sidebar", {"sidebar": sidebar})

    @Slot(str)
    def toggle(self, sidebar: str) -> None:
        """A rail icon: open ``sidebar``, or collapse it when it is the open one."""
        self.show("" if sidebar == self._current else sidebar)

    @Slot(float)
    def setWidth(self, units: float) -> None:  # noqa: N802 (Qt)
        """The splitter was let go at ``units`` wide: keep it (clamped)."""
        value = round(min(max(float(units), SIDEBAR_WIDTH_MIN), SIDEBAR_WIDTH_MAX), 1)
        if value != self._width:
            self._width = value
            self.changed.emit()
            self._store.submit("set_sidebar_width", {"width": value})

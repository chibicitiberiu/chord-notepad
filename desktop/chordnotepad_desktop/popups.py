"""Which popups a Qt Quick window has open.

Qt Quick has no "is a modal popup open" in QML: a Popup's item sits under the
window's Overlay while it is open (Qt unparents it once it has closed), and
only its QObject parent, the Popup itself, knows whether it is modal. Python
can follow that link; QML can't.
"""

from typing import Optional

from PySide6.QtQuick import QQuickItem, QQuickWindow


def _overlay(window: QQuickWindow) -> Optional[QQuickItem]:
    for child in window.contentItem().childItems():
        if child.inherits("QQuickOverlay"):
            return child
    return None


def modal_popup_open(window: Optional[QQuickWindow]) -> bool:
    """Whether ``window`` shows a modal popup (a dialog), opening or open.

    A popup that is closing still counts until it has closed (its ``closed``
    handler runs after it has left the overlay)."""
    if window is None:
        return False
    overlay = _overlay(window)
    if overlay is None:
        return False
    for item in overlay.childItems():
        popup = item.parent()
        if item.isVisible() and popup is not None and popup.property("modal") is True:
            return True
    return False

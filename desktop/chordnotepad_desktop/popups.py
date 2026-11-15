"""Which popups a Qt Quick window has open.

Qt Quick has no "is a modal popup open" in QML: a Popup's item sits under the
window's Overlay while it is open (Qt unparents it once it has closed), and
only its QObject parent, the Popup itself, knows whether it is modal. Python
can follow that link; QML can't, so QML hands over ``Overlay.overlay``.

Not the window itself: a Python wrapper of the QML main window (from
``QQuickItem.window()``) made the interpreter crash on exit, after every test
had passed.
"""

from typing import Optional

from PySide6.QtQuick import QQuickItem


def modal_popup_open(overlay: Optional[QQuickItem]) -> bool:
    """Whether the window of ``overlay`` (its ``Overlay.overlay``) shows a
    modal popup (a dialog), opening or open.

    A popup that is closing still counts until it has closed (its ``closed``
    handler runs after it has left the overlay)."""
    if overlay is None:
        return False
    for item in overlay.childItems():
        popup = item.parent()
        if item.isVisible() and popup is not None and popup.property("modal") is True:
            return True
    return False

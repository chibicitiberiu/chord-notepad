import QtQuick
import QtQuick.Controls
import CNTheme

// The one dialog template: title header (from the style), a body, and a
// DialogFooter (destructive alone on the left, primary last on the right).
// It takes the keyboard focus when it opens, so Escape closes it.
Dialog {
    modal: true
    focus: true
    width: Theme.px(118)
    anchors.centerIn: Overlay.overlay
}

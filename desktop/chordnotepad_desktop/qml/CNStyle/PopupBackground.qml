import QtQuick
import CNTheme

// Menu / popover / dialog surface: hairline border and a soft offset shadow.
// The software backend (the GPU fallback) has no MultiEffect, so the shadow
// is two translucent rectangles, not a blur (pitfall 15). They come before the
// surface instead of taking a negative z: that would also put them below the
// parent for input (pitfall 4).
Item {
    id: root
    property color color: Theme.popup
    property real radius: Theme.radiusPopup
    Rectangle {
        x: -Theme.hairline; y: Theme.px(0.75)
        width: parent.width + 2 * Theme.hairline; height: parent.height + Theme.px(0.75)
        radius: root.radius + Theme.hairline
        color: Theme.shadow; opacity: 0.5
    }
    Rectangle {
        y: Theme.px(1.5)
        width: parent.width; height: parent.height
        radius: root.radius
        color: Theme.shadow; opacity: 0.35
    }
    Rectangle {
        anchors.fill: parent
        radius: root.radius
        color: root.color
        border.color: Theme.border
        border.width: Theme.hairline
    }
}

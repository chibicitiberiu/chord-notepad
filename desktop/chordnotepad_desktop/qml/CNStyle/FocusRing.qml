import QtQuick
import CNTheme

// Keyboard focus: a soft accent ring just outside the control.
Rectangle {
    property real ringRadius: Theme.radius
    anchors.fill: parent
    anchors.margins: -Theme.focusWidth
    radius: ringRadius + Theme.focusWidth
    color: "transparent"
    border.width: Theme.focusWidth
    border.color: Theme.focusRing
}

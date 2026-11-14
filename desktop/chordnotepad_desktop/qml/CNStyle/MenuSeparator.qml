import QtQuick
import QtQuick.Templates as T
import CNTheme

// A hairline in the border colour, 1u of air above and below, inset to the
// menu items' text margin. (v3 had no implicit size: zero height, invisible.)
T.MenuSeparator {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    topPadding: Theme.gap1; bottomPadding: Theme.gap1
    leftPadding: Theme.gap2; rightPadding: Theme.gap2
    contentItem: Rectangle {
        implicitWidth: Theme.px(45)
        implicitHeight: Theme.hairline
        color: Theme.border
    }
}

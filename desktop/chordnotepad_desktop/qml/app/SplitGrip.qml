import QtQuick
import QtQuick.Controls
import CNTheme

// A SplitView handle (the mockup's SplitHandle): a hairline, tinted while
// hovered or dragged. `vertical`: the views are stacked (a horizontal line).
Rectangle {
    id: grip
    property bool vertical: true
    implicitWidth: Theme.splitHandle; implicitHeight: Theme.splitHandle
    color: SplitHandle.pressed ? Theme.accentFill : SplitHandle.hovered ? Theme.borderStrong : "transparent"
    Rectangle {
        anchors.centerIn: parent
        width: grip.vertical ? parent.width : Theme.hairline
        height: grip.vertical ? Theme.hairline : parent.height
        color: Theme.border
    }
}

import QtQuick
import QtQuick.Templates as T
import CNTheme

// Thin track, accent progress, a small round handle with a hairline border.
T.Slider {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitHandleWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitHandleHeight + topPadding + bottomPadding)
    padding: Theme.gap1
    hoverEnabled: true
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: Theme.px(3.5); implicitHeight: implicitWidth
        radius: width / 2
        color: control.pressed ? Theme.controlPressed : Theme.control
        border.width: Theme.hairline
        border.color: control.hovered || control.pressed ? Theme.accent : Theme.borderStrong
        FocusRing { visible: control.visualFocus; ringRadius: parent.radius }
    }
    background: Item {
        implicitWidth: Theme.px(30); implicitHeight: Theme.px(5)
        x: control.leftPadding; y: control.topPadding + (control.availableHeight - height) / 2
        width: control.availableWidth; height: Theme.px(1)
        Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.borderStrong }
        Rectangle {
            width: control.visualPosition * parent.width; height: parent.height
            radius: height / 2; color: Theme.accentFill
        }
    }
}

import QtQuick
import QtQuick.Templates as T
import CNTheme

// Thin overlay scrollbar that thickens on hover.
T.ScrollBar {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    padding: Theme.px(0.5)
    hoverEnabled: true
    minimumSize: 0.06
    visible: policy !== T.ScrollBar.AlwaysOff && size < 1.0
    contentItem: Rectangle {
        readonly property int thick: control.hovered || control.pressed ? Theme.px(2) : Theme.px(1.25)
        implicitWidth: thick
        implicitHeight: thick
        radius: thick / 2
        color: control.pressed ? Theme.muted : control.hovered ? Theme.alpha(Theme.muted, 0.8) : Theme.alpha(Theme.muted, 0.45)
        opacity: control.policy === T.ScrollBar.AlwaysOn || control.active || control.hovered ? 1.0 : 0.6
    }
}

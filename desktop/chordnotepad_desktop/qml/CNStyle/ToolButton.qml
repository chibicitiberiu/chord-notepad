import QtQuick
import QtQuick.Templates as T
import CNTheme

// Toolbar button: flat, square for icons, icon + label when `display` says
// so; checked = a neutral pressed-in background, accent icon.
T.ToolButton {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    padding: Theme.px(1.25)
    leftPadding: display === T.AbstractButton.IconOnly ? Theme.px(1.25) : Theme.gap2
    rightPadding: display === T.AbstractButton.IconOnly ? Theme.px(1.25) : Theme.px(2.5)
    spacing: Theme.px(1.5)
    hoverEnabled: true
    display: T.AbstractButton.IconOnly
    font: Theme.font
    icon.width: Theme.iconSize; icon.height: Theme.iconSize
    icon.color: !enabled ? Theme.disabled : checked ? Theme.accent : Theme.icon
    property color textColor: !enabled ? Theme.disabled : Theme.text
    contentItem: IconText {
        spacing: control.spacing
        display: control.display
        iconSource: control.icon.source
        iconColor: control.icon.color
        iconSize: control.icon.width
        text: control.text
        font: control.font
        color: control.textColor
    }
    background: Rectangle {
        implicitWidth: Theme.toolButton
        implicitHeight: Theme.toolButton
        radius: Theme.radius
        color: control.down ? Theme.pressed : control.checked ? Theme.checkedBg
               : control.hovered ? Theme.hover : "transparent"
        FocusRing { visible: control.visualFocus }
    }
}

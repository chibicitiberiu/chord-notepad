import QtQuick
import QtQuick.Templates as T
import CNTheme

// Compact desktop toggle (VS Code / Figma size): track 9u x 5u.
T.Switch {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding,
                            implicitIndicatorWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitContentHeight, implicitIndicatorHeight) + topPadding + bottomPadding
    padding: Theme.gap1
    spacing: Theme.gap3
    hoverEnabled: true
    font: Theme.font
    indicator: Rectangle {
        implicitWidth: Theme.px(9); implicitHeight: Theme.px(5)
        x: control.text ? control.width - width - control.rightPadding : control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: height / 2
        color: control.checked ? (control.hovered ? Theme.accentHover : Theme.accentFill)
                               : (control.hovered ? Theme.controlPressed : Theme.controlHover)
        border.width: control.checked ? 0 : Theme.hairline
        border.color: Theme.borderStrong
        Rectangle {
            width: parent.height - 2 * Theme.px(0.75); height: width; radius: width / 2
            x: control.checked ? parent.width - width - Theme.px(0.75) : Theme.px(0.75)
            y: Theme.px(0.75)
            color: control.checked ? Theme.textOnAccent : Theme.icon
            Behavior on x { NumberAnimation { duration: Theme.fast } }
        }
        FocusRing { visible: control.visualFocus; ringRadius: parent.radius }
    }
    contentItem: SText {
        rightPadding: control.text ? control.indicator.width + control.spacing : 0
        text: control.text
        font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}

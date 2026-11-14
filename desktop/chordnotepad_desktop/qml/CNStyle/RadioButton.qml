import QtQuick
import QtQuick.Templates as T
import CNTheme

T.RadioButton {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitContentHeight, implicitIndicatorHeight) + topPadding + bottomPadding
    padding: Theme.gap1; spacing: Theme.gap2
    hoverEnabled: true
    font: Theme.font
    indicator: Rectangle {
        implicitWidth: Theme.iconSmall; implicitHeight: Theme.iconSmall
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: width / 2
        color: control.checked ? Theme.accentFill : Theme.input
        border.width: control.checked ? 0 : Theme.hairline
        border.color: control.hovered ? Theme.muted : Theme.borderStrong
        Rectangle {
            anchors.centerIn: parent; width: Theme.px(1.5); height: width; radius: width / 2
            color: Theme.textOnAccent; visible: control.checked
        }
        FocusRing { visible: control.visualFocus; ringRadius: parent.radius }
    }
    contentItem: SText {
        leftPadding: control.indicator.width + control.spacing
        text: control.text; font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
        verticalAlignment: Text.AlignVCenter
    }
}

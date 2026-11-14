import QtQuick
import QtQuick.Templates as T
import CNTheme

T.ItemDelegate {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(Theme.listRowHeight, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.padX; rightPadding: Theme.padX
    topPadding: Theme.gap1; bottomPadding: Theme.gap1
    spacing: Theme.gap2
    hoverEnabled: true
    font: Theme.font
    icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
    icon.color: Theme.icon
    contentItem: IconText {
        spacing: control.spacing
        display: control.display
        alignLeft: true
        iconSource: control.icon.source
        iconColor: control.icon.color
        iconSize: control.icon.width
        text: control.text
        font: control.font
        color: control.enabled ? Theme.text : Theme.disabled
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        color: control.down ? Theme.pressed : control.highlighted ? Theme.selectedRow
               : control.hovered ? Theme.hover : "transparent"
    }
}

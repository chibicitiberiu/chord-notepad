import QtQuick
import QtQuick.Templates as T
import CNTheme

// Flat text tab with a thin accent underline when active (MuseScore 4's
// Home | Score | Publish). Used for the Edit | Play workspaces and the
// chord-sheet views.
T.TabButton {
    id: control
    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.gap3; rightPadding: Theme.gap3
    hoverEnabled: true
    font: checked ? Theme.fontStrong : Theme.fontMedium
    contentItem: SText {
        text: control.text
        font: control.font
        color: !control.enabled ? Theme.disabled : control.checked ? Theme.text
               : control.hovered ? Theme.text : Theme.muted
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
    }
    background: Item {
        implicitHeight: Theme.panelHeader
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - 2 * Theme.gap2
            height: Theme.px(0.5)
            radius: height / 2
            color: control.checked ? Theme.accent : control.hovered ? Theme.border : "transparent"
        }
        Rectangle {
            visible: control.visualFocus
            anchors.fill: parent; anchors.margins: Theme.gap1
            radius: Theme.radiusSmall; color: "transparent"
            border.width: Theme.focusWidth; border.color: Theme.focusRing
        }
    }
}

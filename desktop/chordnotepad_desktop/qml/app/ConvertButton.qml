import QtQuick
import QtQuick.Controls
import CNTheme

// Convert (plan step F2, the mockup's ConvertButton): the two-colour C ↔ Do
// mark plus a label when the toolbar is wide. It converts the song's chords
// to the notation it isn't in (AppActions' convertAction); the tooltip
// names that one.
ToolButton {
    id: control
    objectName: "convertButton"
    property string tip: ""
    property bool showLabel: true
    text: "Convert"
    focusPolicy: Qt.TabFocus
    leftPadding: Theme.gap2; rightPadding: showLabel ? Theme.px(2.5) : Theme.gap2
    ToolTip.visible: hovered && control.tip !== ""
    ToolTip.delay: 600
    ToolTip.text: control.tip
    contentItem: Row {
        spacing: Theme.px(1.5)
        opacity: control.enabled ? 1 : 0.45
        Item {
            width: Theme.iconSize; height: Theme.iconSize
            anchors.verticalCenter: parent.verticalCenter
            SText { x: 0; y: -Theme.px(0.5); text: "C"; color: Theme.markAmerican; font: Theme.fontMarkC }
            SText {
                anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.bottomMargin: -Theme.px(0.5)
                text: "Do"; color: Theme.markEuropean; font: Theme.fontMarkDo
            }
        }
        SText {
            visible: control.showLabel
            text: control.text
            font: control.font
            color: control.enabled ? Theme.text : Theme.disabled
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}

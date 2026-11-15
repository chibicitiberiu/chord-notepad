import QtQuick
import QtQuick.Controls
import CNTheme

// The zoom control: [ - 110% + ] in a small framed pill. Used by the text pane's
// corner chip (ZoomChip) and the chord sheet's header. It only shows a
// percentage and says what was clicked; the owner does the zooming.
// Children go after the three parts, inside the frame (the chip's pencil).
Rectangle {
    id: pill
    property int percent: 100
    property bool canIn: true
    property bool canOut: true
    // Full tooltip texts (rich text allowed, the owner adds its shortcut hint).
    property string outTip: "Zoom out"
    property string inTip: "Zoom in"
    property string resetTip: "Reset to 100%"
    // The names the three parts are found by; percentName is the text itself.
    property string outName: "zoomOutButton"
    property string inName: "zoomInButton"
    property string resetName: "zoomResetButton"
    property string percentName: "zoomPercent"
    signal zoomIn()
    signal zoomOut()
    signal reset()
    default property alias extras: allParts.data

    width: allParts.implicitWidth + 2 * Theme.gap1
    height: allParts.implicitHeight + 2 * Theme.px(0.5)
    radius: Theme.radius
    color: Theme.popup
    border.width: Theme.hairline; border.color: Theme.border

    Row {
        id: allParts
        anchors.centerIn: parent
        spacing: Theme.gap1
        Row {
            id: zoomParts
            spacing: 0
            ToolButton {
                objectName: pill.outName
                icon.source: Theme.iconUrl("minus")
                icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
                implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
                padding: 0
                focusPolicy: Qt.NoFocus
                enabled: pill.canOut
                onClicked: pill.zoomOut()
                ToolTip.visible: hovered; ToolTip.delay: 600
                ToolTip.text: pill.outTip
            }
            AbstractButton {
                id: pct
                objectName: pill.resetName
                hoverEnabled: true
                focusPolicy: Qt.NoFocus
                implicitHeight: Theme.controlSmall
                implicitWidth: Theme.px(10)
                onClicked: pill.reset()
                ToolTip.visible: hovered; ToolTip.delay: 600
                ToolTip.text: pill.resetTip
                background: Rectangle { radius: Theme.radiusSmall; color: pct.hovered ? Theme.hover : "transparent" }
                contentItem: SText {
                    objectName: pill.percentName
                    text: pill.percent + "%"
                    font: Theme.fontS; color: Theme.muted
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
            }
            ToolButton {
                objectName: pill.inName
                icon.source: Theme.iconUrl("plus")
                icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
                implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
                padding: 0
                focusPolicy: Qt.NoFocus
                enabled: pill.canIn
                onClicked: pill.zoomIn()
                ToolTip.visible: hovered; ToolTip.delay: 600
                ToolTip.text: pill.inTip
            }
        }
    }
}

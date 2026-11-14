import QtQuick
import QtQuick.Controls
import CNTheme

// − 110% + : the editor's text zoom (Ctrl+= / Ctrl+-); click the value to reset.
// The percentage is of the default 11 pt, in 10% steps (plan resolution 3);
// the size itself is the session's font_size (EditorBridge.zoomPercent).
Row {
    id: zoom
    required property var editor
    spacing: 0
    ToolButton {
        objectName: "zoomOutButton"
        icon.source: Theme.iconUrl("minus")
        icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
        implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
        padding: 0
        focusPolicy: Qt.NoFocus
        onClicked: zoom.editor.zoomOut()
        ToolTip.visible: hovered; ToolTip.delay: 600
        ToolTip.text: "Smaller text  <font color='" + Theme.muted + "'>Ctrl+-</font>"
    }
    AbstractButton {
        id: pct
        objectName: "zoomResetButton"
        hoverEnabled: true
        focusPolicy: Qt.NoFocus
        implicitHeight: Theme.controlSmall
        implicitWidth: Theme.px(10)
        onClicked: zoom.editor.zoomReset()
        ToolTip.visible: hovered; ToolTip.delay: 600
        ToolTip.text: "Text zoom; click to reset  <font color='" + Theme.muted + "'>Ctrl+0</font>"
        background: Rectangle { radius: Theme.radiusSmall; color: pct.hovered ? Theme.hover : "transparent" }
        contentItem: SText {
            objectName: "zoomPercent"
            text: zoom.editor.zoomPercent + "%"
            font: Theme.fontS; color: Theme.muted
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }
    ToolButton {
        objectName: "zoomInButton"
        icon.source: Theme.iconUrl("plus")
        icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
        implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
        padding: 0
        focusPolicy: Qt.NoFocus
        onClicked: zoom.editor.zoomIn()
        ToolTip.visible: hovered; ToolTip.delay: 600
        ToolTip.text: "Larger text  <font color='" + Theme.muted + "'>Ctrl+=</font>"
    }
}

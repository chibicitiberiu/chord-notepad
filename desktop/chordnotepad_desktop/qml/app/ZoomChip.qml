import QtQuick
import CNTheme

// The text pane's corner chip: − 100% + text zoom, and in Play a pencil back to
// Edit. It floats over the pane's top-right corner and stays put while the
// text scrolls under it (song lines are short, so that corner is usually empty).
ZoomPill {
    id: chip
    required property var editor
    property bool showEdit: false
    signal editRequested()
    z: 3
    anchors.top: parent.top; anchors.right: parent.right
    anchors.margins: Theme.gap2
    percent: editor.zoomPercent
    outTip: "Smaller text  <font color='" + Theme.muted + "'>Ctrl+-</font>"
    inTip: "Larger text  <font color='" + Theme.muted + "'>Ctrl+=</font>"
    resetTip: "Text zoom; click to reset  <font color='" + Theme.muted + "'>Ctrl+0</font>"
    onZoomOut: editor.zoomOut()
    onZoomIn: editor.zoomIn()
    onReset: editor.zoomReset()
    Rectangle { visible: chip.showEdit; width: Theme.hairline; height: Theme.px(4); color: Theme.border; anchors.verticalCenter: parent.verticalCenter }
    IconButton {
        objectName: "editPencil"
        visible: chip.showEdit
        iconName: "pencil"; tip: "Edit the text"; shortcutHint: "Ctrl+1"
        implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
        onClicked: chip.editRequested()
    }
}

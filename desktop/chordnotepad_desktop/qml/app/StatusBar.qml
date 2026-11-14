import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit workspace's status line (the mockup's StatusBar.qml). Plan step
// D4 has the message: the session's status, or the hint of the directive at
// the caret (its reason in red, or muted when it has no effect, then its
// syntax). What shows when is StatusBarModel's (status_bar.py), not this
// file's. F4 adds the rest of the mockup's bar: the playing dot, "Read-only
// while playing", Ln/Col and the notation.
Rectangle {
    id: bar
    objectName: "statusBar"
    required property var model
    implicitHeight: Theme.statusHeight
    color: Theme.chrome
    Rectangle { width: parent.width; height: Theme.hairline; color: Theme.border }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.gap3; anchors.rightMargin: Theme.gap3
        spacing: Theme.gap3
        Label {
            objectName: "statusText"
            visible: !bar.model.showHint
            text: bar.model.statusText
            color: bar.model.playing ? Theme.text : Theme.muted
            font: Theme.fontS
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Label {
            objectName: "hintMessage"
            visible: bar.model.showHint && text !== ""
            text: bar.model.hintMessage
            color: bar.model.hintRedundant ? Theme.muted : Theme.error
            font: Theme.fontStrongS
        }
        Label {
            objectName: "hintSyntax"
            visible: bar.model.showHint
            text: bar.model.hintSyntax
            color: Theme.directive
            font: Theme.fontMonoS
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}

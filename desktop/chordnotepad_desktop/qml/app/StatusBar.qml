import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit workspace's status line (the mockup's StatusBar.qml): on the left
// the message (D4): the session's status, or the hint of the directive at
// the caret (its reason in red, or muted when it has no effect, then its
// syntax), with the accent dot while a song plays; on the right (F4) the
// read-only notice while playing ("Read-only while playing · Shift+F5
// stops", or a refused edit in the error colour, Q9), else Ln/Col, then the
// song's notation. What shows when is StatusBarModel's (status_bar.py),
// not this file's. No timeouts: a message stays until the next.
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
        Rectangle {
            objectName: "playingDot"
            visible: bar.model.playing
            width: Theme.px(1.5); height: width; radius: width / 2
            color: Theme.accent
        }
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
        Label {
            objectName: "readOnlyNotice"
            visible: text !== ""
            text: bar.model.readOnlyNotice
            color: bar.model.noticeWarning ? Theme.error : Theme.muted
            font: bar.model.noticeWarning ? Theme.fontStrongS : Theme.fontS
        }
        Label {
            objectName: "caretPosition"
            visible: !bar.model.playing
            text: "Ln " + bar.model.caretLine + ", Col " + bar.model.caretColumn
            color: Theme.muted
            font: Theme.fontS
        }
        Label {
            objectName: "notationName"
            visible: text !== ""
            text: bar.model.notation
            color: Theme.muted
            font: Theme.fontS
        }
    }
}

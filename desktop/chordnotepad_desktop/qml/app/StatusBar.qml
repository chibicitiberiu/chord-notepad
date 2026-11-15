import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit workspace's status line. On the left: while a song plays or is
// paused, the accent dot (playing only), "Playing" or "Paused" and the chord
// in strong text, then quiet segments (Bar 2 / 125, 120 bpm, 4/4, Key G) with
// a muted "·" between, their numbers in tabular figures. Idle, the session's
// message (Saved, an error, "Stopped playback"; never "Ready") and the song's
// starting tempo, time and key. With the caret in a directive its hint takes
// the whole left side (its reason in red, or muted when it has no effect, then
// its syntax). On the right: the read-only notice as a small badge (amber; red
// for a refused edit, Q9), else Ln/Col, then a hairline and the notation.
// What shows when is StatusBarModel's (status_bar.py), not this file's. No
// timeouts: a message stays until the next.
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
        spacing: Theme.gap2
        Rectangle {
            objectName: "playingDot"
            visible: bar.model.running
            width: Theme.px(1.5); height: width; radius: width / 2
            color: Theme.accent
        }
        Label {
            objectName: "activityLabel"
            visible: text !== ""
            text: bar.model.activity
            color: Theme.muted
            font: Theme.fontS
        }
        Label {
            objectName: "chordName"
            visible: text !== ""
            text: bar.model.chordName
            color: Theme.text
            font: Theme.fontStrongS
        }
        Label {
            objectName: "statusText"
            visible: !bar.model.showHint && text !== ""
            text: bar.model.statusText
            color: Theme.muted
            font: Theme.fontS
            elide: Text.ElideRight
            Layout.maximumWidth: bar.width / 2
        }
        Repeater {
            model: bar.model.showHint ? [] : bar.model.segments
            delegate: RowLayout {
                id: seg
                required property var modelData
                required property int index
                spacing: Theme.gap2
                // A "·" after whatever came before: the activity, the chord, the message.
                readonly property bool lead: index > 0 || bar.model.activity !== "" || bar.model.statusText !== ""
                Label {
                    objectName: "segmentDot"
                    visible: seg.lead
                    text: "·"
                    color: Theme.disabled
                    font: Theme.fontS
                    Layout.rightMargin: Theme.gap1
                }
                Label {
                    objectName: "segment"
                    text: seg.modelData.text
                    color: seg.modelData.warning ? Theme.warning : Theme.muted
                    font: seg.modelData.warning ? Theme.fontTabularStrong : Theme.fontTabular
                    HoverHandler { id: segHover }
                    ToolTip.visible: segHover.hovered && seg.modelData.tip !== ""
                    ToolTip.delay: 400
                    ToolTip.text: seg.modelData.tip
                }
            }
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
        Item { Layout.fillWidth: true; visible: !bar.model.showHint }
        Rectangle {
            id: badge
            objectName: "readOnlyBadge"
            visible: notice.text !== ""
            implicitWidth: notice.implicitWidth + 2 * Theme.gap2
            implicitHeight: notice.implicitHeight + Theme.px(1)
            radius: height / 2
            color: bar.model.noticeWarning ? Theme.errorBg : Theme.warningBg
            Label {
                id: notice
                objectName: "readOnlyNotice"
                anchors.centerIn: parent
                text: bar.model.readOnlyNotice
                color: bar.model.noticeWarning ? Theme.error : Theme.warning
                font: Theme.fontStrongS
            }
        }
        Label {
            objectName: "caretPosition"
            visible: !bar.model.playing
            text: "Ln " + bar.model.caretLine + ", Col " + bar.model.caretColumn
            color: Theme.muted
            font: Theme.fontTabular
        }
        Rectangle {   // hairline between the caret and the notation
            visible: notation.visible
            Layout.preferredWidth: Theme.hairline; Layout.preferredHeight: Theme.px(3)
            Layout.leftMargin: Theme.gap1; Layout.rightMargin: Theme.gap1
            color: Theme.border
        }
        Label {
            id: notation
            objectName: "notationName"
            visible: text !== ""
            text: bar.model.notation
            color: Theme.muted
            font: Theme.fontS
        }
    }
}

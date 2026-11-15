pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit workspace's status line. On the left: while a song plays or is
// paused, the accent dot (playing only), "Playing" or "Paused" and the chord
// in strong text, then quiet segments (Bar 2 / 125, 120 bpm, 4/4, Key G),
// their numbers in tabular figures. Idle, the session's message (Saved, an
// error, "Stopped playback"; never "Ready") and the song's starting tempo,
// time and key. With the caret in a directive its hint takes the whole left
// side (its reason in red, or muted when it has no effect, then its syntax).
// On the right: an edit refused while playing as a small red badge (Q9),
// else Ln/Col, then the notation. Vertical separators part the cells, and
// each cell is as wide as the widest text it is meant for (model.widest), so
// nothing moves as the values change.
// What shows when is StatusBarModel's (status_bar.py), not this file's. No
// timeouts: a message stays until the next.
Rectangle {
    id: bar
    objectName: "statusBar"
    required property var model
    implicitHeight: Theme.statusHeight
    color: Theme.chrome

    // A classic status bar separator: a hairline most of the bar's height.
    component Separator: Rectangle {
        objectName: "statusSeparator"
        Layout.preferredWidth: Theme.hairline
        Layout.preferredHeight: Theme.statusHeight - 2 * Theme.gap1
        Layout.leftMargin: Theme.gap1; Layout.rightMargin: Theme.gap1
        color: Theme.border
    }
    // A label sized for the widest text of its kind (it still grows past it).
    component Cell: Label {
        id: cell
        property string kind
        Layout.preferredWidth: Math.ceil(Math.max(implicitWidth,
            ...(bar.model.widest[cell.kind] || []).map(t => cellMetrics.advanceWidth(t))))
        FontMetrics { id: cellMetrics; font: cell.font }
    }

    Rectangle { width: parent.width; height: Theme.hairline; color: Theme.border }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.gap3; anchors.rightMargin: Theme.gap3
        spacing: Theme.gap2
        Rectangle {
            objectName: "playingDot"
            // Paused keeps the dot's room, so "Paused" sits where "Playing" did.
            visible: bar.model.activity !== ""
            opacity: bar.model.running ? 1 : 0
            width: Theme.px(1.5); height: width; radius: width / 2
            color: Theme.accent
        }
        Cell {
            objectName: "activityLabel"
            kind: "activity"
            visible: text !== ""
            text: bar.model.activity
            color: Theme.muted
            font: Theme.fontS
        }
        Cell {
            objectName: "chordName"
            kind: "chord"
            visible: bar.model.activity !== ""
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
                // A separator after whatever came before: the activity, the chord, the message.
                Separator {
                    visible: seg.index > 0 || bar.model.activity !== "" || bar.model.statusText !== ""
                }
                Cell {
                    objectName: "segment"
                    kind: seg.modelData.kind
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
            color: Theme.errorBg
            Label {
                id: notice
                objectName: "readOnlyNotice"
                anchors.centerIn: parent
                text: bar.model.readOnlyNotice
                color: Theme.error
                font: Theme.fontStrongS
            }
        }
        Cell {
            objectName: "caretPosition"
            kind: "caret"
            visible: !bar.model.playing
            text: "Ln " + bar.model.caretLine + ", Col " + bar.model.caretColumn
            color: Theme.muted
            font: Theme.fontTabular
        }
        Separator { visible: notation.visible }
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

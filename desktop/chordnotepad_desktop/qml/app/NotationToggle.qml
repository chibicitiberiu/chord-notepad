pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import CNTheme

// AB | Do (plan step F2, the mockup's NotationToggle): how chords are
// detected, a two-segment toggle in the squared desktop shape. `value` is
// the session's notation (EditorState); a click on the other half asks for
// it with picked(). The tooltips are Tk's (toolbar_texts).
Rectangle {
    id: root
    objectName: "notationToggle"
    property string value: "american"
    property string americanTip: ""
    property string europeanTip: ""
    signal picked(string value)
    implicitWidth: row.implicitWidth + 2 * Theme.hairline
    implicitHeight: Theme.controlHeight
    radius: Theme.radius
    color: Theme.control
    border.width: Theme.hairline
    border.color: Theme.borderStrong
    opacity: enabled ? 1 : 0.5
    Row {
        id: row
        anchors.centerIn: parent
        Repeater {
            model: [["AB", "american"], ["Do", "european"]]
            delegate: AbstractButton {
                id: seg
                required property var modelData
                objectName: "notation:" + modelData[1]
                implicitWidth: Theme.px(9); height: root.height - 2 * Theme.hairline
                hoverEnabled: true
                focusPolicy: Qt.TabFocus
                checked: root.value === seg.modelData[1]
                onClicked: if (root.value !== seg.modelData[1]) root.picked(seg.modelData[1])
                ToolTip.visible: hovered
                ToolTip.delay: 600
                ToolTip.text: seg.modelData[1] === "american" ? root.americanTip : root.europeanTip
                background: Rectangle {
                    radius: Theme.radius - Theme.hairline
                    color: seg.checked ? Theme.checkedBg : seg.hovered ? Theme.hover : "transparent"
                }
                contentItem: SText {
                    text: seg.modelData[0]
                    font: Theme.fontStrong
                    color: seg.checked ? Theme.accent : Theme.muted
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}

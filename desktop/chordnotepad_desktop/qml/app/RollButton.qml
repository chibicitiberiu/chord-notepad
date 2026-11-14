import QtQuick
import QtQuick.Controls
import CNTheme
import CNStyle      // PixelIcon: qmllint misses it through QtQuick.Controls here

// A ▶ that plays something now or rolled (the chord identifier's Play and
// its candidates' ▶, resolution 1): a click plays it, Shift+click or a
// right click plays it rolled, one note at a time from the lowest (Tk's
// Play button). Space or Enter on a focused one too, Shift for rolled.
// A MouseArea, since a button's clicked carries no modifiers.
Item {
    id: rb
    property string iconName: "play"
    property string tip
    property int iconSize: Theme.iconSmall
    signal play(bool rolled)
    implicitWidth: Theme.controlSmall
    implicitHeight: Theme.controlSmall
    activeFocusOnTab: true
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
            if (!e.isAutoRepeat) rb.play((e.modifiers & Qt.ShiftModifier) !== 0)
            e.accepted = true
        }
    }
    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: area.pressed ? Theme.pressed : area.containsMouse ? Theme.hover : "transparent"
        border.width: rb.activeFocus ? Theme.hairline : 0
        border.color: Theme.accent
    }
    PixelIcon {
        anchors.centerIn: parent
        name: rb.iconName
        size: rb.iconSize
        color: rb.enabled ? Theme.icon : Theme.disabled
    }
    MouseArea {
        id: area
        objectName: "rollArea"
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: (m) => rb.play(m.button === Qt.RightButton || (m.modifiers & Qt.ShiftModifier) !== 0)
    }
    ToolTip.visible: area.containsMouse && rb.tip !== ""
    ToolTip.delay: 600
    ToolTip.text: rb.tip
}

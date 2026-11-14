import QtQuick
import QtQuick.Controls
import CNTheme
import CNStyle      // PixelIcon: qmllint misses it through QtQuick.Controls in this file

// The compact dropdown button of the player bar and the chord-sheet header:
// flat until hovered, [icon] value ⌄, the value elided. The tooltip hangs
// off a HoverHandler, so a disabled one (the voicing, while playing) still
// says why (pitfall 16): put it in an enabled parent and give that `tip`.
AbstractButton {
    id: pd
    property string iconName
    property color valueColor: Theme.text
    property string tip
    property int maxTextWidth: Theme.px(40)
    property bool showText: true
    property int iconSize: Theme.playerIcon
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    implicitHeight: Theme.playerControl
    implicitWidth: pdRow.implicitWidth + 2 * Theme.gap2
    HoverHandler { id: tipHover }
    // Not over its own open dropdown.
    ToolTip.visible: tipHover.hovered && !down && !checked && tip !== ""
    ToolTip.delay: 600
    ToolTip.text: tip
    background: Rectangle {
        radius: Theme.radius
        color: pd.down || pd.checked ? Theme.pressed : pd.hovered ? Theme.hover : "transparent"
    }
    contentItem: Item {
        opacity: pd.enabled ? 1 : 0.45
        Row {
            id: pdRow
            anchors.centerIn: parent
            spacing: Theme.gap1
            PixelIcon {
                name: pd.iconName
                size: pd.iconSize
                color: Theme.icon
                anchors.verticalCenter: parent.verticalCenter
            }
            SText {
                visible: pd.text !== "" && pd.showText
                text: pd.text
                font: Theme.fontMedium; color: pd.valueColor
                width: Math.min(implicitWidth, pd.maxTextWidth)
                elide: Text.ElideRight
                anchors.verticalCenter: parent.verticalCenter
            }
            PixelIcon {
                name: "chevron-down"
                size: Theme.iconSmall
                color: Theme.muted
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}

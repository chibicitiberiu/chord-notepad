import QtQuick
import QtQuick.Controls
import CNTheme
import CNStyle      // PixelIcon: qmllint misses it through QtQuick.Controls here

// A palette tile (MuseScore palette style, the mockup's): a square with an
// icon and at most a tiny caption; the explanation is in a rich tooltip.
// A click, Enter or Space inserts the snippet at the caret with its value
// selected; dragging it into the text drops it there (DragSource, the
// mockup's: the chip, the drop caret, snapped off the middle of a word). The
// arrow keys move through the palette (DirectivePalette's `navigate`).
//
// While the editor is read-only (playing or paused) the button is disabled
// and the tooltip says why. A disabled control gets no hover, so the tooltip
// hangs off the enabled Item around it (pitfall 16).
Item {
    id: tile
    property string tileId
    property string iconName
    property string caption
    property string name
    property string snippet
    property string hint
    property string action
    property bool locked: false
    property string lockedReason
    required property var dnd
    readonly property alias button: btn
    signal insert(string snippet)
    // An arrow key: the palette moves the focus (key: Qt.Key_Left ...).
    signal navigate(int key)
    objectName: "tile:" + tileId
    implicitWidth: Theme.tileSize
    implicitHeight: Theme.tileSize

    function escaped(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
    readonly property string tip: "<b>" + escaped(name) + "</b><br><font face='" + Theme.monoFont
        + "' color='" + Theme.directive + "'>" + escaped(snippet) + "</font><br>" + escaped(hint)
        + "<br><font color='" + Theme.muted + "'>" + escaped(locked ? lockedReason : action) + "</font>"

    HoverHandler { id: hover; cursorShape: tile.locked ? Qt.ArrowCursor : Qt.PointingHandCursor }
    ToolTip.visible: (hover.hovered || btn.visualFocus) && !drag.dragging
    ToolTip.delay: 400
    ToolTip.text: tile.tip

    AbstractButton {
        id: btn
        objectName: "tileButton:" + tile.tileId
        anchors.fill: parent
        enabled: !tile.locked
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: tile.name
        onClicked: tile.insert(tile.snippet)
        Keys.onReturnPressed: tile.insert(tile.snippet)
        Keys.onEnterPressed: tile.insert(tile.snippet)
        Keys.onSpacePressed: tile.insert(tile.snippet)
        Keys.onLeftPressed: tile.navigate(Qt.Key_Left)
        Keys.onRightPressed: tile.navigate(Qt.Key_Right)
        Keys.onUpPressed: tile.navigate(Qt.Key_Up)
        Keys.onDownPressed: tile.navigate(Qt.Key_Down)
        // The DragSource on top takes the pointer: its press and hover.
        background: Rectangle {
            radius: Theme.radiusSmall
            color: drag.pressed && !drag.dragging ? Theme.controlPressed
                 : drag.containsMouse ? Theme.controlHover : "transparent"
            border.width: drag.containsMouse || btn.activeFocus ? Theme.hairline : 0
            border.color: btn.activeFocus ? Theme.accent : Theme.border
        }
        contentItem: Item {
            PixelIcon {
                anchors.horizontalCenter: parent.horizontalCenter
                y: tile.caption ? Theme.px(1) : (parent.height - height) / 2
                name: "pal-" + tile.iconName
                size: Theme.tileIcon
                color: btn.enabled ? Theme.icon : Theme.disabled
            }
            SText {
                visible: tile.caption !== ""
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Theme.px(0.5)
                width: parent.width - Theme.px(1)
                horizontalAlignment: Text.AlignHCenter
                text: tile.caption
                font: Theme.fontC
                color: btn.enabled ? Theme.muted : Theme.disabled
                elide: Text.ElideRight
            }
        }
    }
    // Click or drag (pitfall 5); off while locked, as the button.
    DragSource {
        id: drag
        objectName: "tileDrag:" + tile.tileId
        dnd: tile.dnd
        snippet: tile.snippet
        enabled: !tile.locked
        onTapped: { btn.forceActiveFocus(Qt.MouseFocusReason); tile.insert(tile.snippet) }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit sidebar's Directives palette (the mockup's): every directive form
// and text helper as a compact icon tile, grouped, from the core's
// session.snippets.PALETTE (SidebarModel.paletteGroups). No dialogs: a click
// inserts the default with its value selected, and the value is picked
// later in the text (the ▾ after a directive). The duration tiles come
// after the switch.
//
// Keys: Left/Right move one tile (across groups), Up/Down one row (to the
// nearest tile in the row above or below), Enter/Space insert, Escape goes
// back to the editor (Main.qml). Disabled while the editor is read-only.
Rectangle {
    id: panel
    objectName: "directivePalette"
    required property var sidebars
    property bool locked: false
    signal insert(string snippet)
    color: Theme.panel

    // Every tile in order, for the arrow keys (Repeater delegates aren't in
    // the QObject tree, pitfall 25).
    property var tiles: []
    function register(t, flat) { var a = panel.tiles.slice(); a[flat] = t; panel.tiles = a }
    function offsetOf(group) {
        var n = 0
        for (var g = 0; g < group; ++g) n += panel.sidebars.paletteGroups[g].tiles.length
        return n
    }
    // The first tile the keyboard can reach (Ctrl+Shift+D gives it the focus).
    function focusFirst() {
        for (var i = 0; i < panel.tiles.length; ++i)
            if (panel.tiles[i] && panel.tiles[i].button.enabled) {
                panel.tiles[i].button.forceActiveFocus(Qt.TabFocusReason)
                return true
            }
        return false
    }
    function centre(t) { return t.mapToItem(panel, t.width / 2, t.height / 2) }
    function navigate(from, key) {
        var i = panel.tiles.indexOf(from)
        if (i < 0) return
        var to = null
        if (key === Qt.Key_Left || key === Qt.Key_Right) {
            to = panel.tiles[i + (key === Qt.Key_Right ? 1 : -1)] || null
        } else {
            var c = panel.centre(from), down = key === Qt.Key_Down, best = -1
            var slack = from.height / 2
            for (var j = 0; j < panel.tiles.length; ++j) {
                var t = panel.tiles[j]
                if (!t || t === from) continue
                var p = panel.centre(t), dy = down ? p.y - c.y : c.y - p.y
                if (dy < slack) continue
                // The nearest row first, then the nearest tile in it.
                var score = Math.round(dy / slack) * 100000 + Math.abs(p.x - c.x)
                if (best < 0 || score < best) { best = score; to = t }
            }
        }
        if (to) {
            to.button.forceActiveFocus(Qt.TabFocusReason)
            panel.reveal(to)
        }
    }
    function reveal(t) {
        var flick = scroll.contentItem as Flickable
        if (!flick) return
        var top = t.mapToItem(flick.contentItem, 0, 0).y
        if (top < flick.contentY) flick.contentY = Math.max(0, top - Theme.gap2)
        else if (top + t.height > flick.contentY + flick.height)
            flick.contentY = top + t.height - flick.height + Theme.gap2
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.panelHeader
            Label { anchors.verticalCenter: parent.verticalCenter; x: Theme.gap3; text: "Directives"; font: Theme.fontStrong }
        }
        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            ColumnLayout {
                x: Theme.gap2
                width: scroll.availableWidth - 2 * Theme.gap2
                spacing: 0
                Repeater {
                    model: panel.sidebars.paletteGroups
                    delegate: ColumnLayout {
                        id: grp
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: Theme.px(0.5)
                        Label {
                            objectName: "paletteGroup:" + grp.modelData.title
                            text: grp.modelData.title
                            font: Theme.fontC
                            color: Theme.muted
                            Layout.leftMargin: Theme.gap1
                            Layout.topMargin: grp.index ? Theme.gap2 : 0
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: Theme.gap1
                            Repeater {
                                model: grp.modelData.tiles
                                delegate: SnippetTile {
                                    id: tileItem
                                    required property var modelData
                                    required property int index
                                    tileId: modelData.id
                                    iconName: modelData.icon
                                    caption: modelData.caption
                                    snippet: modelData.text
                                    name: modelData.name
                                    hint: modelData.hint
                                    action: panel.sidebars.tileAction
                                    locked: panel.locked
                                    lockedReason: panel.sidebars.lockedReason
                                    onInsert: (s) => panel.insert(s)
                                    onNavigate: (key) => panel.navigate(tileItem, key)
                                    Component.onCompleted: panel.register(tileItem, panel.offsetOf(grp.index) + index)
                                }
                            }
                        }
                    }
                }
                Item { Layout.preferredHeight: Theme.gap3 }
            }
        }
    }
}

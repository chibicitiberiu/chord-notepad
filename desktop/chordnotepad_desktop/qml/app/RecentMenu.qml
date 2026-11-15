import QtQuick
import QtQuick.Controls
import CNTheme

// File › Open recent (plan step F3), for the menu bar and the ☰ menu: one
// row per file of RecentDocumentsState, newest first, a same-named file
// with its folder ("song.txt — Band", Q11), or "(No recent files)",
// disabled. Built with createObject, parented to the menu's contentItem
// (Menu has no Repeater, pitfall 7), and rebuilt when the list changes; a
// pick sends open_recent (files.py).
Menu {
    id: menu
    title: "Open &recent"
    required property var files
    property Component itemComp: Component { MenuItem { } }

    function rebuild() {
        while (menu.count > 0) {
            var old = menu.takeItem(0)
            if (old) old.destroy()
        }
        var labels = menu.files.recentLabels
        if (labels.length === 0) {
            menu.addItem(menu.itemComp.createObject(menu.contentItem, { text: menu.files.noRecentText,
                                                            enabled: false,
                                                            objectName: "noRecentFiles" }))
            return
        }
        for (var i = 0; i < labels.length; ++i) {
            // A "&" in a name is a "&", not a mnemonic.
            var item = menu.itemComp.createObject(menu.contentItem, { text: labels[i].replace(/&/g, "&&"),
                                                          objectName: "recent:" + i }) as MenuItem
            item.triggered.connect(menu.opener(i))
            menu.addItem(item)
        }
    }
    function opener(index) { return function () { menu.files.openRecent(index) } }

    Component.onCompleted: menu.rebuild()
    Connections {
        target: menu.files
        function onRecentChanged() { menu.rebuild() }
    }
}

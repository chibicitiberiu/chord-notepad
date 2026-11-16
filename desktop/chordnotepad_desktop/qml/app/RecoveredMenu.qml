import QtQuick
import QtQuick.Controls
import CNTheme

// File › Backups, right after Open recent, in the menu bar and the ☰
// menu: the copies of unsaved songs that crashed or killed instances left
// (recovery.py), newest first ("song.txt, today at 14:32"), then "Clear
// backups". Disabled while there are none.
// Built like RecentMenu (createObject under contentItem, pitfall 7) and
// rebuilt when the list changes; the parent menu asks for a fresh list as it
// opens (refresh). `recovery` is null when the app has no recovery folder.
Menu {
    id: menu
    title: "&Backups"
    property var recovery: null
    readonly property int entryCount: menu.recovery ? menu.recovery.labels.length : 0
    enabled: menu.entryCount > 0
    property Component itemComp: Component { MenuItem { } }
    property Component separatorComp: Component { MenuSeparator { } }

    function refresh() { if (menu.recovery) menu.recovery.refresh() }

    function rebuild() {
        while (menu.count > 0) {
            var old = menu.takeItem(0)
            if (old) old.destroy()
        }
        if (menu.entryCount === 0) return
        var labels = menu.recovery.labels
        for (var i = 0; i < labels.length; ++i) {
            // A "&" in a name is a "&", not a mnemonic.
            var item = menu.itemComp.createObject(menu.contentItem, { text: labels[i].replace(/&/g, "&&"),
                                                          objectName: "recovered:" + i }) as MenuItem
            item.triggered.connect(menu.opener(i))
            menu.addItem(item)
        }
        menu.addItem(menu.separatorComp.createObject(menu.contentItem))
        var clear = menu.itemComp.createObject(menu.contentItem, { text: menu.recovery.clearText,
                                                       objectName: "clearRecovered" }) as MenuItem
        clear.triggered.connect(function () { menu.recovery.clearAll() })
        menu.addItem(clear)
    }
    function opener(index) { return function () { menu.recovery.openEntry(index) } }

    Component.onCompleted: menu.rebuild()
    Connections {
        target: menu.recovery
        ignoreUnknownSignals: true
        function onEntriesChanged() { menu.rebuild() }
    }
}

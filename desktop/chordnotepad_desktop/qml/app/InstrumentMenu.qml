import QtQuick
import QtQuick.Controls
import CNTheme

// Playback › Instrument as a popup menu (plan step E3): the 16 General MIDI
// families of InstrumentMenuState, each a submenu of its (up to 8)
// programs, the family in use marked with a dot (Tk's menu, Android's
// two-level sheet). Built with createObject (pitfall 7), rebuilt when the
// soundfont's programs change; a pick sends set_instrument.
Menu {
    id: menu
    objectName: "instrumentMenu"
    title: "I&nstrument"
    required property var store
    readonly property var istate: menu.store.states.InstrumentMenuState
    property string builtFor: ""
    property Component subComp: Component { Menu { } }
    property Component itemComp: Component { MenuItem { checkable: true } }

    function check(item, program) {
        item.checked = Qt.binding(function () { return menu.istate.current === program })
    }
    function rebuild() {
        var families = menu.istate.families || []
        var key = JSON.stringify(families.map(function (f) { return [f.name, f.items] }))
        if (key === menu.builtFor) return
        menu.builtFor = key
        while (menu.count > 0) {
            var old = menu.takeMenu(0) || menu.takeItem(0)
            if (old) old.destroy()
        }
        for (var f = 0; f < families.length; ++f) {
            var fam = families[f]
            var sub = menu.subComp.createObject(menu, { title: fam.name, objectName: "family:" + fam.name }) as Menu
            sub.icon.source = Qt.binding(function (i) { return function () {
                var fs = menu.istate.families || []
                return fs[i] && fs[i].is_current ? Theme.iconUrl("circle") : ""
            } }(f))
            sub.icon.color = Theme.accent
            for (var i = 0; i < fam.items.length; ++i) {
                var program = parseInt(fam.items[i].value)
                var item = menu.itemComp.createObject(sub.contentItem, { text: fam.items[i].label,
                                                               objectName: "program:" + program }) as MenuItem
                menu.check(item, program)
                item.triggered.connect(function (it, p) { return function () {
                    menu.check(it, p)
                    menu.store.submit("set_instrument", { program: p })
                } }(item, program))
                sub.addItem(item)
            }
            sub.enabled = fam.items.length > 0
            menu.addMenu(sub)
        }
    }
    Connections {
        target: menu.store
        function onStateChanged(name) { if (name === "InstrumentMenuState") menu.rebuild() }
    }
    Component.onCompleted: menu.rebuild()
}

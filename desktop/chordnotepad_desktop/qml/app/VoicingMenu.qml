import QtQuick
import QtQuick.Controls
import CNTheme

// Playback › Voicing as a popup menu (plan step E3): the session's
// VoicingMenuState groups (piano; the built-in fretboards; the built-in
// ensembles; the user's voicings), separated, the one in use checked, then
// "Edit voicings…". Built with createObject (Menu has no Repeater,
// pitfall 7) and rebuilt when the choices change. A pick sends
// set_voicing; the opener keeps the menu shut while the voicing is locked
// (a song plays), and the core refuses set_voicing then anyway.
Menu {
    id: menu
    objectName: "voicingMenu"
    title: "&Voicing"
    required property var store
    signal editVoicings()
    readonly property var vstate: menu.store.states.VoicingMenuState
    property string builtFor: ""
    property Component itemComp: Component { MenuItem { checkable: true } }
    property Component sepComp: Component { MenuSeparator { } }

    function check(item, value) {
        // A checkable item flips itself when triggered: bind it to the state again.
        item.checked = Qt.binding(function () { return menu.vstate.selected === value })
    }
    function rebuild() {
        var groups = menu.vstate.groups || []
        var key = JSON.stringify(groups)
        if (key === menu.builtFor) return
        menu.builtFor = key
        while (menu.count > 0) {
            var old = menu.takeItem(0)
            if (old) old.destroy()
        }
        for (var g = 0; g < groups.length; ++g) {
            if (g > 0) menu.addItem(menu.sepComp.createObject(null))
            for (var i = 0; i < groups[g].length; ++i) {
                var choice = groups[g][i]
                var item = menu.itemComp.createObject(null, { text: choice.label, objectName: "voicing:" + choice.value }) as MenuItem
                menu.check(item, choice.value)
                item.triggered.connect(function (it, v) { return function () {
                    menu.check(it, v)
                    menu.store.submit("set_voicing", { voicing: v })
                } }(item, choice.value))
                menu.addItem(item)
            }
        }
        menu.addItem(menu.sepComp.createObject(null))
        var edit = menu.itemComp.createObject(null, { text: "Edit voicings…", checkable: false,
                                                       objectName: "editVoicings" }) as MenuItem
        edit.triggered.connect(menu.editVoicings)
        menu.addItem(edit)
    }
    Connections {
        target: menu.store
        function onStateChanged(name) { if (name === "VoicingMenuState") menu.rebuild() }
    }
    Component.onCompleted: menu.rebuild()
}

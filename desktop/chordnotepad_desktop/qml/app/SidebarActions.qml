import QtQuick
import QtQuick.Controls

// The sidebars' shortcuts (plan step F5), as Actions with window shortcuts,
// like PlaybackActions.qml. F1 puts them in View
// (`MenuItem { action: sidebarActions.directivesAction }`): never declare
// these sequences again, or both go dead as ambiguous.
//
//   Ctrl+Shift+D   the Directives palette
//   Ctrl+Shift+I   the Chord identifier
//
// In Edit, each opens its sidebar and gives it the keyboard focus, or
// collapses it when it is the open one (as its rail icon does); in Play it
// switches to Edit with that sidebar open.
Item {
    id: acts
    objectName: "sidebarActions"
    required property var sidebars
    property bool editMode: true
    // The workspace has to be Edit first (Main.qml switches it).
    signal editRequested()
    // The sidebar was opened from the keyboard: Main.qml focuses it.
    signal opened(string sidebar)
    // It was collapsed: the editor gets the focus back.
    signal collapsed()

    function trigger(name) {
        if (!acts.editMode) {
            acts.editRequested()
            acts.sidebars.show(name)
            acts.opened(name)
        } else if (acts.sidebars.current === name) {
            acts.sidebars.show("")
            acts.collapsed()
        } else {
            acts.sidebars.show(name)
            acts.opened(name)
        }
    }

    readonly property Action directivesAction: Action {
        id: directives
        objectName: "directivesAction"
        text: "&Directives"
        shortcut: "Ctrl+Shift+D"
        checkable: true
        checked: acts.sidebars.current === "directives"
        onTriggered: {
            // A checkable Action flips itself: follow the model again.
            directives.checked = Qt.binding(function () { return acts.sidebars.current === "directives" })
            acts.trigger("directives")
        }
    }
    readonly property Action identifierAction: Action {
        id: identifier
        objectName: "identifierAction"
        text: "Chord &identifier"
        shortcut: "Ctrl+Shift+I"
        checkable: true
        checked: acts.sidebars.current === "identifier"
        onTriggered: {
            identifier.checked = Qt.binding(function () { return acts.sidebars.current === "identifier" })
            acts.trigger("identifier")
        }
    }
}

import QtQuick
import QtQuick.Controls

// The chord sheet's shortcuts (plan step E4), as Actions with window
// shortcuts, like PlaybackActions.qml. F1 puts them in View › Chord sheet
// (`MenuItem { action: sheetActions.panelAction }`): never declare these
// sequences again, or both go dead as ambiguous.
//
//   F9         the chord sheet under the text (Edit only; Play always shows it)
//   Alt+1..4   Piano roll, Staff, Fret cards, Tab (a view the song can't show is off)
Item {
    id: acts
    objectName: "sheetActions"
    required property var store
    property bool editMode: true
    readonly property var st: acts.store.states.ChordSheetState
    readonly property var views: acts.st.views || []

    function available(i) { return i < acts.views.length && acts.views[i].available === true }
    function show(i) {
        if (acts.available(i) && acts.views[i].view_id !== acts.st.active_view)
            acts.store.submit("set_chord_sheet_view", { view_id: acts.views[i].view_id })
    }

    readonly property Action panelAction: Action {
        id: panel
        objectName: "sheetPanelAction"
        text: "Chord &sheet under the text"
        shortcut: "F9"
        checkable: true
        enabled: acts.editMode
        checked: acts.st.visible === true
        onTriggered: {
            // A checkable Action flips itself: follow the session's state again.
            panel.checked = Qt.binding(function () { return acts.st.visible === true })
            acts.store.submit("set_chord_sheet_visible", { visible: acts.st.visible !== true })
        }
    }
    readonly property Action view1Action: Action {
        objectName: "sheetView1Action"
        text: acts.views.length > 0 ? acts.views[0].label : ""
        shortcut: "Alt+1"
        enabled: acts.available(0)
        onTriggered: acts.show(0)
    }
    readonly property Action view2Action: Action {
        objectName: "sheetView2Action"
        text: acts.views.length > 1 ? acts.views[1].label : ""
        shortcut: "Alt+2"
        enabled: acts.available(1)
        onTriggered: acts.show(1)
    }
    readonly property Action view3Action: Action {
        objectName: "sheetView3Action"
        text: acts.views.length > 2 ? acts.views[2].label : ""
        shortcut: "Alt+3"
        enabled: acts.available(2)
        onTriggered: acts.show(2)
    }
    readonly property Action view4Action: Action {
        objectName: "sheetView4Action"
        text: acts.views.length > 3 ? acts.views[3].label : ""
        shortcut: "Alt+4"
        enabled: acts.available(3)
        onTriggered: acts.show(3)
    }
}

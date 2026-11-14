import QtQuick
import QtQuick.Layouts
import CNTheme

// The Edit workspace's toolbar (plan step F2, the mockup's EditToolbar),
// grouped with hairline separators:
//   Undo, Redo | Transpose, Convert, AB|Do | … | Chord sheet | Play, Stop
// Labels show when the bar is wider than 200 u (Play always has its label).
// Inserting lives in the Directives sidebar (F5).
//
// Every button runs an Action someone else declares (EditorPane's Undo and
// Redo, disabled on an empty stack, Q3; AppActions' Transpose and Convert;
// PlaybackActions' Play; E4's chord-sheet toggle), so a shortcut is never
// declared twice. Enabled as the menus are: Transpose and Convert stay on
// while a song plays, and the session's refusal shows in the status bar (Q9).
Rectangle {
    id: bar
    objectName: "editToolbar"
    required property var store
    required property var chrome
    required property var actions      // AppActions
    required property var pane         // EditorPane
    required property var playback     // PlaybackActions
    required property var player       // PlayerBarModel (the Play tooltip)
    // SheetActions (E4): the chord-sheet toggle; null until then.
    property var sheetActions: null
    readonly property bool roomy: width > Theme.px(200)
    readonly property var tb: bar.store.states.ToolbarState
    readonly property string notation: bar.store.states.EditorState.notation || "american"
    readonly property bool playing: bar.tb.play_action === "pause"
    implicitHeight: Theme.toolbarHeight
    color: Theme.chrome
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.hairline; color: Theme.border }

    component Sep: Rectangle {
        Layout.preferredWidth: Theme.hairline
        Layout.preferredHeight: Theme.px(5)
        Layout.leftMargin: Theme.gap2; Layout.rightMargin: Theme.gap2
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.gap2; anchors.rightMargin: Theme.gap2
        spacing: Theme.gap1
        IconButton {
            objectName: "undoButton"
            iconName: "undo"; tip: "Undo"; shortcutHint: "Ctrl+Z"
            enabled: bar.pane.undoAction.enabled
            onClicked: bar.pane.undoAction.trigger()
        }
        IconButton {
            objectName: "redoButton"
            iconName: "redo"; tip: "Redo"; shortcutHint: "Ctrl+Y"
            enabled: bar.pane.redoAction.enabled
            onClicked: bar.pane.redoAction.trigger()
        }
        Sep { objectName: "toolbarSep1" }
        IconButton {
            objectName: "transposeButton"
            iconName: "transpose"; text: "Transpose"; showLabel: bar.roomy
            icon.width: Theme.px(6)
            tip: "Transpose…"; shortcutHint: "Ctrl+T"
            onClicked: bar.actions.transposeAction.trigger()
        }
        ConvertButton {
            showLabel: bar.roomy
            tip: bar.notation === "american" ? bar.chrome.texts.toEuropean : bar.chrome.texts.toAmerican
            onClicked: bar.actions.convertAction.trigger()
        }
        NotationToggle {
            value: bar.notation
            americanTip: bar.chrome.texts.american
            europeanTip: bar.chrome.texts.european
            onPicked: (v) => bar.store.submit("set_notation", { notation: v })
        }
        Item { Layout.fillWidth: true }
        IconButton {
            objectName: "sheetToggle"
            visible: bar.sheetActions !== null
            iconName: "dock-bottom"; text: "Chord sheet"; showLabel: bar.roomy
            checkable: true
            checked: bar.sheetActions !== null && bar.sheetActions.panelAction.checked
            enabled: bar.sheetActions !== null && bar.sheetActions.panelAction.enabled
            // The action decides; the button shows the session's state again.
            onClicked: {
                bar.sheetActions.panelAction.trigger()
                checked = Qt.binding(function () {
                    return bar.sheetActions !== null && bar.sheetActions.panelAction.checked
                })
            }
            tip: "Show the chord sheet under the text"; shortcutHint: "F9"
        }
        Sep { objectName: "toolbarSep2"; visible: bar.sheetActions !== null }
        IconButton {
            id: playBtn
            objectName: "toolbarPlay"
            iconName: bar.playing ? "pause" : "play"
            text: bar.playing ? "Pause" : "Play"; showLabel: true
            tip: bar.player.playTooltip(bar.tb.play_action || "play"); shortcutHint: "F5"
            // Shift+click plays from the cursor, as the player bar's ▶.
            property bool fromCursor: false
            onClicked: bar.player.playPause(playBtn.fromCursor)
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                // Only notes Shift; the press goes on to the button.
                onPressed: (m) => {
                    playBtn.fromCursor = (m.modifiers & Qt.ShiftModifier) !== 0
                    m.accepted = false
                }
            }
        }
        IconButton {
            objectName: "toolbarStop"
            iconName: "stop"; tip: bar.chrome.texts.stop
            // Not disabled when idle: Stop also silences a chord still ringing
            // from a click (as the player bar's ⏹ and Tk's Stop).
            onClicked: bar.store.submit("stop")
        }
    }
}

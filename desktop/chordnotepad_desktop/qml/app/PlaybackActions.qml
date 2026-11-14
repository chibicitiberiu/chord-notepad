import QtQuick
import QtQuick.Controls

// The playback shortcuts, all in one place (plan steps E1-E3), as Actions
// with window shortcuts (scoped to the main window; a modal dialog blocks
// them; Qt matches them with Caps Lock on and uses Cmd on macOS). The player
// bar's buttons call the same things. F1 puts these Actions in the menus
// (`MenuItem { action: playbackActions.playAction }`): never declare a
// second Action or Shortcut with one of these sequences, or both go dead as
// ambiguous.
//
//   F5         play / pause / resume (from the playhead)
//   Shift+F5   stop and rewind (to the first chord)
//   Ctrl+M     the metronome (off at every start: the session doesn't keep it)
//   Ctrl+]     speed +5%      Ctrl+[  speed −5%      Ctrl+\  speed 100%
Item {
    id: acts
    objectName: "playbackActions"
    required property var store
    required property var player
    readonly property var tb: acts.store.states.ToolbarState

    readonly property Action playAction: Action {
        objectName: "playAction"
        text: acts.tb.play_action === "pause" ? "&Pause" : "&Play"
        shortcut: "F5"
        onTriggered: acts.player.playPause(false)
    }
    readonly property Action rewindAction: Action {
        objectName: "rewindAction"
        text: "&Stop and rewind"
        shortcut: "Shift+F5"
        onTriggered: acts.store.submit("rewind")
    }
    readonly property Action metronomeAction: Action {
        id: metronome
        objectName: "metronomeAction"
        text: "&Metronome"
        shortcut: "Ctrl+M"
        checkable: true
        checked: acts.tb.metronome === true
        onTriggered: {
            // A checkable Action flips itself: follow the session's state again.
            metronome.checked = Qt.binding(function () { return acts.tb.metronome === true })
            acts.store.submit("toggle_metronome")
        }
    }
    readonly property Action fasterAction: Action {
        objectName: "fasterAction"
        text: "&Faster"
        shortcut: "Ctrl+]"
        onTriggered: acts.player.stepSpeed(1)
    }
    readonly property Action slowerAction: Action {
        objectName: "slowerAction"
        text: "&Slower"
        shortcut: "Ctrl+["
        onTriggered: acts.player.stepSpeed(-1)
    }
    readonly property Action speedResetAction: Action {
        objectName: "speedResetAction"
        text: "&Normal speed (100%)"
        shortcut: "Ctrl+\\"
        onTriggered: acts.store.submit("reset_multiplier")
    }
}

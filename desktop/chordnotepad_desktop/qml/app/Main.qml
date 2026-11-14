import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Qt front end's main window: the shell (plan step C4). The tab strip
// with Edit | Play, the two workspaces with the editor (D; the player and
// chord sheet, E, and the toolbar, rail and status bar, F, come next), the
// close flow with the Unsaved changes dialog, the error dialog and Quick
// Start at startup.
//
// Everything shown comes from the session through `store`
// (session_store.py): `store.states.<Type>.<field>` for the states,
// store.event / store.request / store.closeApproved for the rest, and
// store.submit(command, args) for the commands. `errors` is the error
// presenter (error_presenter.py); `editor` the editor's EditorBridge
// (editor_bridge.py), which EditorPane attaches to its TextArea.
//
// The plumbing every main window keeps:
// - windowDpr, fontRevision and contentReady are written by DprWatcher
//   (dpr.py): the window's real device pixel ratio, a counter that makes
//   every Theme font a new instance after a ratio change, and the deferred
//   first show (DprWatcher keeps the whole window transparent until the
//   ratio has settled, then sets contentReady).
// - Resizing and Theme.scale changes bump Theme.layoutRevision, so the
//   snapped text (SnapTranslate) re-snaps.
// - altWatcher (alt_watcher.py) is the hidden menu bar's Alt handling; the
//   menus (F1) connect to its signals.
// - Python sizes and shows the window (window_geometry.py), so it starts
//   hidden.
ApplicationWindow {
    id: win
    objectName: "mainWindow"

    required property QtObject altWatcher
    required property var store
    required property var errors
    required property var editor
    property real windowDpr: 1.0
    property int fontRevision: 0
    property bool contentReady: false
    Binding { target: Theme; property: "dpr"; value: win.windowDpr }
    Binding { target: Theme; property: "fontRevision"; value: win.fontRevision }
    onWidthChanged: Theme.bumpLayout()
    onHeightChanged: Theme.bumpLayout()
    Connections {
        target: Theme
        function onScaleChanged() { Theme.bumpLayout() }
    }

    // "song.txt* - Chord Notepad", the session's (DocumentState.title).
    title: win.store.states.DocumentState.title || win.store.texts.appName
    visible: false
    minimumWidth: Theme.px(225)
    minimumHeight: Theme.px(140)

    // The workspace: "edit" or "play" (not kept between runs, as in the mockup).
    property string mode: "edit"
    onModeChanged: { Theme.bumpLayout(); editorPane.focusEditor() }
    Shortcut { sequence: "Ctrl+1"; context: Qt.WindowShortcut; onActivated: win.mode = "edit" }
    Shortcut { sequence: "Ctrl+2"; context: Qt.WindowShortcut; onActivated: win.mode = "play" }

    // --- Closing -------------------------------------------------------------------
    // The close button (and Quit, ☰, File once F1 adds them) only ask the
    // session; it answers with CloseApproved, after the Unsaved changes
    // dialog if needed, and Python (application.py) saves the geometry, sets
    // closeApproved and closes the window for real.
    property bool closeApproved: false
    function requestClose() { win.store.submit("request_close") }
    onClosing: (close) => {
        if (win.closeApproved) return
        close.accepted = false
        win.requestClose()
    }

    // --- Body ------------------------------------------------------------------------
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        TabStrip {
            id: tabStrip
            document: win.store.states.DocumentState
            mode: win.mode
            Layout.fillWidth: true
            onModeRequested: (m) => win.mode = m
        }
        StackLayout {
            objectName: "workspaces"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.mode === "play" ? 1 : 0
            // Edit: the toolbar, the rail and sidebars (F), the editor, the
            // chord sheet (E4), the status bar (F4).
            ColumnLayout {
                objectName: "editWorkspace"
                spacing: 0
                Item {
                    id: editHost
                    objectName: "editHost"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                    onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                    // The text's zoom, on the text pane (not the status bar under the sheet).
                    ZoomChip { objectName: "editZoomChip"; editor: win.editor }
                }
            }
            // Play: the player bar (E1), the text and the chord-sheet strip (E4).
            ColumnLayout {
                objectName: "playWorkspace"
                spacing: 0
                Item {
                    id: playTextHost
                    objectName: "playTextHost"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                    onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                    // The text pane's corner: text zoom and back to Edit.
                    ZoomChip {
                        objectName: "playZoomChip"
                        editor: win.editor
                        showEdit: true
                        onEditRequested: win.mode = "edit"
                    }
                }
            }
        }
    }

    // One editor, moved between the workspaces (as in the mockup); read-only in Play.
    EditorPane {
        id: editorPane
        editor: win.editor
        placeholder: win.store.texts.editorPlaceholder
        playMode: win.mode === "play"
        parent: win.mode === "play" ? playTextHost : editHost
        anchors.fill: parent
    }
    // The editor has the keyboard focus from the start (Q10) and gets it back
    // when a dialog closes or the workspace changes.
    onContentReadyChanged: if (win.contentReady) editorPane.focusEditor()

    // --- The session's requests and the presenter's dialogs ----------------------------
    UnsavedDialog {
        id: unsavedDlg
        texts: win.store.texts
        onChoiceMade: (id, choice) => win.store.submit("respond", { request_id: id, value: choice })
    }
    ErrorDialog {
        id: errorDlg
        onDismissed: win.errors.dismissed()
        onClosed: editorPane.focusEditor()
    }
    QuickStartDialog {
        id: quickStartDlg
        onOpened: win.store.submit("request_quick_start")
        onFinished: (dontShow) => {
            if (dontShow) win.store.submit("set_show_quick_start_on_startup", { show: false })
            win.store.submit("dismiss_startup_screen")
        }
        onClosed: editorPane.focusEditor()
    }
    Connections {
        target: win.store
        function onRequest(typeName, data) {
            if (typeName === "ConfirmDiscardRequest") unsavedDlg.ask(data.request_id)
        }
        function onEvent(typeName, data) {
            if (typeName === "QuickStartContent") quickStartDlg.setContent(data)
        }
    }
    Connections {
        target: win.errors
        function onShown(title, message) { errorDlg.show(title, message) }
    }

    // Quick Start: 100 ms after the window shows, when the session says so
    // (StartupState, decided by app_started from the setting).
    readonly property string startupScreen: win.store.states.StartupState.screen || "none"
    readonly property bool quickStartDue: win.contentReady && win.startupScreen === "quick_start"
    onQuickStartDueChanged: if (win.quickStartDue) quickStartTimer.start()
    Timer {
        id: quickStartTimer
        interval: 100
        onTriggered: if (win.quickStartDue && !quickStartDlg.opened) quickStartDlg.open()
    }
}

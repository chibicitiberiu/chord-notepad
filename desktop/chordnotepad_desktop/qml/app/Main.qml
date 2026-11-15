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
// (editor_bridge.py), which EditorPane attaches to its TextArea; `status`
// the status bar's StatusBarModel (status_bar.py), `pickers` the ▾ value
// pickers' ValuePickerModel (value_picker.py), `dialogs` the Settings
// window's and the small dialogs' DialogsModel (dialogs.py), for AppDialogs,
// `player` the player bar's PlayerBarModel (player_bar.py), `chrome` the
// kept zoom and menu bar plus the File menu's documents (chrome.py,
// files.py), `sheet` the chord sheet's ChordSheetModel (chord_sheet.py),
// `sidebars` the rail's SidebarModel (sidebars.py: the open sidebar, its
// width, the palette) and `identifier` the chord identifier's
// IdentifierModel (identifier.py). The shortcuts are Actions: the window's
// in AppActions.qml, the editor's in EditorPane.qml, playback's in
// PlaybackActions.qml, the chord sheet's in SheetActions.qml, the sidebars'
// in SidebarActions.qml; the menu bar (AppMenuBar.qml), the ☰ menu
// (AppMenu.qml) and the Edit toolbar (EditToolbar.qml) reuse them.
//
// The plumbing every main window keeps:
// - windowDpr, fontRevision and contentReady are written by DprWatcher
//   (dpr.py): the window's real device pixel ratio, a counter that makes
//   every Theme font a new instance after a ratio change, and the deferred
//   first show (DprWatcher keeps the whole window transparent until the
//   ratio has settled, then sets contentReady).
// - Resizing and Theme.scale changes bump Theme.layoutRevision, so the
//   snapped text (SnapTranslate) re-snaps.
// - altWatcher (alt_watcher.py) is the hidden menu bar's Alt handling
//   (AppMenuBar.qml listens to it).
// - Python sizes and shows the window (window_geometry.py), so it starts
//   hidden.
ApplicationWindow {
    id: win
    objectName: "mainWindow"

    required property QtObject altWatcher
    required property var store
    required property var errors
    required property var editor
    required property var status
    required property var pickers
    required property var dialogs
    required property var player
    required property var chrome
    required property var sheet
    required property var sidebars
    required property var identifier
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
    // The Play workspace shows the chord sheet, so it renders and the
    // timeline gets its sections (B3); in Edit, F9's setting decides; a
    // minimized window shows nothing.
    readonly property bool minimized: win.visibility === Window.Minimized
    function sheetOnScreen() {
        win.store.submit("set_chord_sheet_on_screen",
                         { on_screen: win.minimized ? false : win.mode === "play" ? true : null })
    }
    onModeChanged: {
        Theme.bumpLayout()
        editorPane.moveTo(win.mode === "play" ? playTextHost : editHost)
        editorPane.focusEditor()
        win.sheetOnScreen()
    }
    onMinimizedChanged: win.sheetOnScreen()
    // Ctrl+1 / Ctrl+2 are AppActions' editModeAction / playModeAction.

    // --- The menus (F1) ----------------------------------------------------------------
    menuBar: AppMenuBar {
        id: appMenuBar
        actions: appActions
        pane: editorPane
        playback: playbackActions
        store: win.store
        chrome: win.chrome
        altWatcher: win.altWatcher
        sheetActions: windowSheetActions
        sidebarActions: windowSidebarActions
        onEditVoicings: appDialogs.openSettings("voicings")
    }
    // F10: the first menu.
    function openMenuBar() { appMenuBar.openMenu(0) }
    AppActions {
        id: appActions
        store: win.store
        chrome: win.chrome
        editor: win.editor
        pane: editorPane
        dialogs: appDialogs
        window: win
    }
    AppMenu {
        id: appMenu
        actions: appActions
        files: win.chrome.files
        onClosed: editorPane.focusEditor()
    }
    function toggleAppMenu(anchor) {
        if (appMenu.visible) appMenu.close()
        else appMenu.popup(anchor, anchor.width - appMenu.width, anchor.height)
    }
    // The session's file requests (F3). The picker is a window of its own:
    // the keys come back to this one when it closes.
    FileDialogs {
        files: win.chrome.files
        onFinished: { win.requestActivate(); editorPane.focusEditor() }
    }

    // --- Closing -------------------------------------------------------------------
    // The close button, Quit (Ctrl+Q, File, ☰) only ask the
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
            appMenuOpen: appMenu.visible
            Layout.fillWidth: true
            onModeRequested: (m) => win.mode = m
            onOpenAppMenu: (anchor) => win.toggleAppMenu(anchor)
        }
        StackLayout {
            objectName: "workspaces"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.mode === "play" ? 1 : 0
            // Edit: the toolbar, the rail and sidebars (F), the editor, the
            // chord sheet panel (E4, F9), the status bar (F4).
            ColumnLayout {
                objectName: "editWorkspace"
                spacing: 0
                EditToolbar {
                    store: win.store
                    chrome: win.chrome
                    actions: appActions
                    pane: editorPane
                    playback: playbackActions
                    player: win.player
                    sheetActions: windowSheetActions
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 0
                    // The rail and the sidebars (F5).
                    IconRail {
                        sidebars: win.sidebars
                        Layout.fillHeight: true
                        onOpenSettings: appDialogs.openSettings()
                    }
                    SplitView {
                        id: sideSplit
                        objectName: "sideSplit"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        orientation: Qt.Horizontal
                        handle: SplitGrip { vertical: false }
                        // The sidebar's width is kept after a drag (layout units, F5).
                        onResizingChanged: if (!resizing && sidebarBox.visible)
                            win.sidebars.setWidth(sidebarBox.width / Theme.u)
                        Rectangle {
                            id: sidebarBox
                            objectName: "sidebarBox"
                            visible: win.sidebars.current !== ""
                            color: Theme.panel
                            SplitView.preferredWidth: Theme.px(win.sidebars.width)
                            SplitView.minimumWidth: Theme.sidebarMin
                            SplitView.maximumWidth: Theme.sidebarMax
                            onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                            onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                            onVisibleChanged: Theme.bumpLayout()
                            // Escape in a sidebar goes back to the text.
                            Keys.onEscapePressed: editorPane.focusEditor()
                            StackLayout {
                                anchors.fill: parent
                                currentIndex: win.sidebars.current === "identifier" ? 1 : 0
                                DirectivePalette {
                                    id: directivePalette
                                    dnd: sidebarDrag
                                    sidebars: win.sidebars
                                    locked: win.editor.readOnly
                                    onInsert: (s) => win.insertSnippet(s)
                                }
                                IdentifierPanel {
                                    id: identifierPanel
                                    dnd: sidebarDrag
                                    model: win.identifier
                                    locked: win.editor.readOnly
                                    lockedReason: win.sidebars.lockedReason
                                    onInsert: (c) => win.insertChord(c)
                                }
                            }
                        }
                        SplitView {
                            id: editSplit
                            objectName: "editSplit"
                            SplitView.fillWidth: true
                            orientation: Qt.Vertical
                            handle: SplitGrip { vertical: true }
                            // The panel's height is kept after a drag (logical px, B3).
                            onResizingChanged: if (!resizing && editSheetHost.visible)
                                win.sheet.saveHeight(Math.round(editSheetHost.height), Theme.dpr)
                            Item {
                                id: editHost
                                objectName: "editHost"
                                SplitView.fillHeight: true
                                SplitView.minimumHeight: Theme.px(30)
                                onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                                onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                                // The text's zoom, on the text pane (not the status bar under the sheet).
                                ZoomChip { objectName: "editZoomChip"; editor: win.editor }
                            }
                            Item {
                                id: editSheetHost
                                objectName: "editSheetHost"
                                visible: win.store.states.ChordSheetState.visible === true
                                SplitView.preferredHeight: Theme.sheetPanelHeight
                                SplitView.minimumHeight: Theme.px(40)
                                onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                                onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                            }
                        }
                    }
                }
                // The message (D4), the read-only notice, Ln/Col, the notation (F4).
                StatusBar { model: win.status; overwrite: editorPane.area.overwriteMode; Layout.fillWidth: true }
            }
            // Play: the player bar (E1), the text and the chord-sheet strip (E4).
            ColumnLayout {
                objectName: "playWorkspace"
                spacing: 0
                PlayerBar {
                    store: win.store
                    player: win.player
                    pickers: win.pickers
                    actions: playbackActions
                    Layout.fillWidth: true
                    onGoToDirective: (v) => win.goToDirective(v)
                    onEditVoicings: appDialogs.openSettings("voicings")
                }
                SplitView {
                    objectName: "playSplit"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    orientation: Qt.Vertical
                    handle: SplitGrip { vertical: true }
                    Item {
                        id: playTextHost
                        objectName: "playTextHost"
                        SplitView.fillHeight: true
                        SplitView.minimumHeight: Theme.px(30)
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
                    // The chord-sheet strip, always on screen in Play.
                    Item {
                        id: playSheetHost
                        objectName: "playSheetHost"
                        SplitView.preferredHeight: Theme.playSheetHeight
                        SplitView.minimumHeight: Theme.px(45)
                        onXChanged: Theme.bumpLayout(); onYChanged: Theme.bumpLayout()
                        onWidthChanged: Theme.bumpLayout(); onHeightChanged: Theme.bumpLayout()
                    }
                }
            }
        }
    }

    // One editor, moved between the workspaces (as in the mockup); read-only in Play.
    EditorPane {
        id: editorPane
        editor: win.editor
        status: win.status
        pickers: win.pickers
        dnd: sidebarDrag
        placeholder: win.store.texts.editorPlaceholder
        playMode: win.mode === "play"
        // Moved by onModeChanged (moveTo keeps the view where it was).
        parent: editHost
        anchors.fill: parent
    }
    // One chord sheet, moved between the Edit panel and the Play strip (the mockup's).
    ChordSheetPane {
        id: sheetPane
        store: win.store
        model: win.sheet
        editor: win.editor
        parent: win.mode === "play" ? playSheetHost : editSheetHost
        anchors.fill: parent
        closable: win.mode === "edit"
        showVoicing: win.mode === "edit"
        active: win.contentReady && !win.minimized && sheetPane.parent !== null && sheetPane.parent.visible
        onCloseRequested: win.store.submit("set_chord_sheet_visible", { visible: false })
        onEditVoicings: appDialogs.openSettings("voicings")
    }

    // The playback shortcuts (F5, Shift+F5, Ctrl+M, Ctrl+] / Ctrl+[ / Ctrl+\).
    PlaybackActions { id: playbackActions; store: win.store; player: win.player }
    // The chord sheet's (F9 in Edit, Alt+1..4 for the views).
    SheetActions { id: windowSheetActions; store: win.store; editMode: win.mode === "edit" }
    // The sidebars' (Ctrl+Shift+D, Ctrl+Shift+I): from the keyboard the
    // opened sidebar gets the focus, a collapsed one gives it back.
    SidebarActions {
        id: windowSidebarActions
        sidebars: win.sidebars
        editMode: win.mode === "edit"
        onEditRequested: win.mode = "edit"
        onOpened: (name) => Qt.callLater(function () {
            if (!(name === "identifier" ? identifierPanel.focusFirst() : directivePalette.focusFirst()))
                editorPane.focusEditor()
        })
        onCollapsed: editorPane.focusEditor()
    }

    // --- Drag from the sidebar into the text (internal drag, the mockup's) -------------
    // A zero-size item carries Drag (hot spot = the pointer); the chip it shows
    // sits beside the pointer. The editor's DropArea sets `accepting` (false
    // over anything else, and while the editor is read-only); the pointer is
    // the closed hand where a drop goes in, the no-drop sign elsewhere.
    QtObject {
        id: sidebarDrag
        objectName: "sidebarDrag"
        property bool accepting: false
        readonly property bool active: dragChip.Drag.active
        readonly property string snippet: dragChip.snippet       // what is being dragged
        function begin(snippet, p, kind) {
            dragChip.snippet = snippet
            dragChip.kind = kind || "snippet"
            sidebarDrag.accepting = false
            sidebarDrag.move(p)
            dragChip.Drag.active = true
        }
        function move(p) {
            dragChip.x = p.x; dragChip.y = p.y
            win.editor.setDragCursor(sidebarDrag.accepting)
        }
        function finish(drop) {
            if (dragChip.Drag.active) {
                if (drop) dragChip.Drag.drop(); else dragChip.Drag.cancel()
            }
            dragChip.Drag.active = false
            dragChip.snippet = ""
            sidebarDrag.accepting = false
            win.editor.clearDragCursor()
        }
        function end() { sidebarDrag.finish(true) }
        function cancel() { sidebarDrag.finish(false) }
    }
    Item {
        id: dragChip
        objectName: "dragChip"
        parent: Overlay.overlay
        z: 1000
        property string snippet
        property string kind: "snippet"
        Drag.keys: [kind]
        Drag.hotSpot.x: 0; Drag.hotSpot.y: 0
        visible: snippet !== ""
        Rectangle {
            x: Theme.gap3; y: Theme.gap2
            width: chipText.implicitWidth + 2 * Theme.gap2
            height: chipText.implicitHeight + Theme.gap2
            radius: Theme.radiusSmall
            color: Theme.popup
            border.width: Theme.hairline
            border.color: sidebarDrag.accepting ? Theme.accent : Theme.borderStrong
            opacity: 0.95
            SText {
                id: chipText
                objectName: "dragChipText"
                anchors.centerIn: parent
                text: dragChip.snippet
                font: Theme.fontMonoS
                color: Theme.directive
            }
        }
    }

    // A palette tile: its snippet at the caret, the value selected (B4's
    // insert_snippet and TextEdited.anchor), the editor focused again.
    function insertSnippet(text) {
        win.store.submit("insert_snippet", { offset: win.editor.codePointAt(editorPane.area.cursorPosition),
                                             text: text, snap: false })
        editorPane.focusEditor()
    }
    // An identifier candidate: the chord and a space at the caret
    // (insert_chord: "Inserted chord: X"), the editor focused again.
    function insertChord(chord) {
        win.identifier.insert(chord)
        editorPane.focusEditor()
    }

    // A song value's link: Edit, the cursor just inside the directive that
    // sets it (looked up in the live text), the editor focused.
    function goToDirective(value) {
        var pos = win.player.directivePosition(value)
        win.mode = "edit"
        // After the workspace switch: the editor unlocks then, and keeps its caret.
        Qt.callLater(function () {
            if (pos >= 0) editorPane.area.cursorPosition = pos
            editorPane.focusEditor()
        })
    }

    // The editor has the keyboard focus from the start (Q10) and gets it back
    // when a dialog closes or the workspace changes.
    onContentReadyChanged: if (win.contentReady) {
        editorPane.focusEditor()
        // The Edit panel's saved height, now that the ratio is known (B3: Tk's
        // pixels are migrated with it).
        editSheetHost.SplitView.preferredHeight = win.sheet.savedHeight(Theme.dpr)
    }

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
    Connections {
        target: win.store
        function onRequest(typeName, data) {
            if (typeName === "ConfirmDiscardRequest") unsavedDlg.ask(data.request_id)
        }
    }
    Connections {
        target: win.errors
        function onShown(title, message) {
            if (!appDialogs.showError(title, message)) errorDlg.show(title, message)
        }
    }

    // Settings, Transpose, Suggest Capo, Quick Start (at startup too),
    // Licences, About and Help (G1, G2; AppDialogs lists the ways in).
    AppDialogs {
        id: appDialogs
        store: win.store
        dialogs: win.dialogs
        errors: win.errors
        editor: win.editor
        pane: editorPane
        mainWindow: win
    }
}

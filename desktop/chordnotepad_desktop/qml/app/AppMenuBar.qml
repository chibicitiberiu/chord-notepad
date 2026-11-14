import QtQuick
import QtQuick.Controls
import CNTheme

// The menu bar (plan step F1): every command, File Edit View Playback Tools
// Help. Hidden by default (Firefox's way): an Alt tap shows it until a click
// below it, Escape or the next Alt tap; Alt+letter opens that menu (F10 the
// first) even while hidden; "Show menu bar" keeps it. On macOS it is the
// native global menu bar, always there (configure_menu_bar in chrome.py
// keeps every other platform's in the window).
//
// The Alt keys come from the AltWatcher (alt_watcher.py), an application
// event filter: Qt Quick has no Alt-only shortcut and a hidden MenuBar has
// no mnemonics (pitfall 18). While the bar shows, its own mnemonics (&File)
// work.
//
// The items are the Actions of AppActions, EditorPane, PlaybackActions and
// (once E4 is in) SheetActions, never new ones: a second Action with the
// same shortcut would make both dead.
MenuBar {
    id: bar
    objectName: "appMenuBar"
    required property var actions          // AppActions
    required property var pane             // EditorPane (the editor's actions)
    required property var playback         // PlaybackActions
    required property var store
    required property var chrome
    required property var altWatcher
    // SheetActions (E4): View › Chord sheet and its views; null until then.
    property var sheetActions: null
    signal editVoicings()

    // Shown: always on macOS, kept shown, or revealed by Alt (peek).
    property bool peek: false
    readonly property bool shown: bar.chrome.mac || bar.chrome.menuBarShown || bar.peek
    visible: bar.shown
    height: bar.shown ? implicitHeight : 0
    onShownChanged: {
        bar.altWatcher.setMenuHidden(!bar.shown)
        Theme.bumpLayout()
    }
    Component.onCompleted: bar.altWatcher.setMenuHidden(!bar.shown)

    readonly property var topMenus: [fileMenu, editMenu, viewMenu, playbackMenu, toolsMenu, helpMenu]
    function anyMenuOpen() { return bar.topMenus.some(function (m) { return m.visible }) }
    // A menu closed: a revealed bar hides again unless another menu opened.
    function menuClosed() {
        Qt.callLater(function () { if (bar.peek && !bar.anyMenuOpen()) bar.peek = false })
    }
    // Open the menu of a letter of MENU_LETTERS ("FEVPTH"), showing the bar.
    function openMenuLetter(letter) {
        var i = "FEVPTH".indexOf(letter)
        if (i < 0) return
        bar.openMenu(i)
    }
    function openMenu(i) {
        if (!bar.shown) bar.peek = true
        Qt.callLater(function () {
            var item = bar.itemAt(i)
            if (item) bar.topMenus[i].popup(item, 0, item.height)
        })
    }
    Connections {
        target: bar.altWatcher
        function onAltTapped() {
            if (bar.chrome.mac || bar.chrome.menuBarShown) return
            bar.peek = !bar.peek
        }
        function onAltLetter(letter) { bar.openMenuLetter(letter) }
        function onPointerPressed(y) {
            if (bar.peek && y > bar.height && !bar.anyMenuOpen()) bar.peek = false
        }
        function onEscapePressed() { if (bar.peek && !bar.anyMenuOpen()) bar.peek = false }
    }
    // "Show menu bar" turned off while revealed: it goes at once.
    Connections {
        target: bar.chrome
        function onMenuBarShownChanged() { bar.peek = false }
    }

    Menu {
        id: fileMenu
        objectName: "fileMenu"
        title: "&File"
        onClosed: bar.menuClosed()
        MenuItem { action: bar.actions.newAction }
        MenuItem { action: bar.actions.openAction }
        RecentMenu { objectName: "menuBarRecent"; files: bar.chrome.files }
        MenuSeparator { }
        MenuItem { action: bar.actions.saveAction }
        MenuItem { action: bar.actions.saveAsAction }
        MenuItem { action: bar.actions.exportMidiAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.quitAction }
    }
    Menu {
        id: editMenu
        objectName: "editMenu"
        title: "&Edit"
        onClosed: bar.menuClosed()
        MenuItem { objectName: "barUndo"; action: bar.pane.undoAction }
        MenuItem { objectName: "barRedo"; action: bar.pane.redoAction }
        MenuSeparator { }
        MenuItem { action: bar.pane.cutAction }
        MenuItem { action: bar.pane.copyAction }
        MenuItem { action: bar.pane.pasteAction }
        MenuSeparator { }
        MenuItem { action: bar.pane.selectAllAction }
    }
    Menu {
        id: viewMenu
        objectName: "viewMenu"
        title: "&View"
        onClosed: bar.menuClosed()
        MenuItem { action: bar.actions.editModeAction }
        MenuItem { action: bar.actions.playModeAction }
        MenuSeparator { }
        // The sidebars (Ctrl+Shift+D / Ctrl+Shift+I) come with F5. The chord
        // sheet and its views are E4's SheetActions.
        MenuItem {
            objectName: "barSheetPanel"
            action: bar.sheetActions ? bar.sheetActions.panelAction : null
            visible: bar.sheetActions !== null
            height: visible ? implicitHeight : 0
        }
        Menu {
            id: sheetViews
            title: "Chord sheet &view"
            enabled: bar.sheetActions !== null
            MenuItem { action: bar.sheetActions ? bar.sheetActions.view1Action : null }
            MenuItem { action: bar.sheetActions ? bar.sheetActions.view2Action : null }
            MenuItem { action: bar.sheetActions ? bar.sheetActions.view3Action : null }
            MenuItem { action: bar.sheetActions ? bar.sheetActions.view4Action : null }
        }
        MenuSeparator { }
        MenuItem { action: bar.actions.wordWrapAction }
        MenuItem { action: bar.pane.zoomInAction }
        MenuItem { action: bar.pane.zoomOutAction }
        MenuItem { action: bar.pane.zoomResetAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.scaleUpAction }
        MenuItem { action: bar.actions.scaleDownAction }
        MenuItem { action: bar.actions.scaleResetAction }
        MenuItem { action: bar.actions.fullScreenAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.menuBarAction }
        MenuItem { action: bar.actions.darkAction }
    }
    Menu {
        id: playbackMenu
        objectName: "playbackMenu"
        title: "&Playback"
        onClosed: bar.menuClosed()
        MenuItem { action: bar.playback.playAction }
        MenuItem { action: bar.playback.rewindAction }
        MenuSeparator { }
        MenuItem { action: bar.playback.metronomeAction }
        MenuItem { action: bar.playback.fasterAction }
        MenuItem { action: bar.playback.slowerAction }
        MenuItem { action: bar.playback.speedResetAction }
        MenuSeparator { }
        // Disabled while a song plays (the player bar's button says why, Q11).
        VoicingMenu {
            objectName: "barVoicingMenu"
            store: bar.store
            enabled: !(bar.store.states.VoicingMenuState.locked_reason)
            onEditVoicings: bar.editVoicings()
        }
        InstrumentMenu { objectName: "barInstrumentMenu"; store: bar.store }
    }
    Menu {
        id: toolsMenu
        objectName: "toolsMenu"
        title: "&Tools"
        onClosed: bar.menuClosed()
        MenuItem { action: bar.actions.transposeAction }
        MenuItem { action: bar.actions.suggestCapoAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.toAmericanAction }
        MenuItem { action: bar.actions.toEuropeanAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.settingsAction }
    }
    Menu {
        id: helpMenu
        objectName: "helpMenu"
        title: "&Help"
        onClosed: bar.menuClosed()
        MenuItem { action: bar.actions.helpAction }
        MenuItem { action: bar.actions.quickStartAction }
        MenuItem { action: bar.actions.shortcutsAction }
        MenuSeparator { }
        MenuItem { action: bar.actions.licencesAction }
        MenuItem { action: bar.actions.aboutAction }
    }
}

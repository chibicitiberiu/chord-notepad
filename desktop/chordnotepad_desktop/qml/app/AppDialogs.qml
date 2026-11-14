import QtQuick
import CNTheme

// The Settings window and the small dialogs (plan steps G1, G2), in one
// place so Main.qml only holds this item. Each dialog is an AppDialog with a
// DialogFooter (a destructive button alone on the left, the primary last)
// and closes on Escape (Q12).
//
// The ways in, for F1's menus and shortcuts (none has a shortcut yet but
// Help's F1, as in Tk; Tk has no Settings shortcut):
//   openSettings(page)  Settings… ("general", "playback" or "voicings")
//   openTranspose()     Tools › Transpose…
//   openSuggestCapo()   Tools › Suggest capo… (and the Capo picker's link)
//   openQuickStart()    Help › Quick start
//   openHelp()          Help › Help (F1)
//   openLicences()      Help › Open source licences
//   openAbout()         Help › About
// The session's requests and events it answers: CapoChoiceRequest (Suggest
// Capo), QuickStartContent (Quick Start's pages). It also follows the
// theme setting (ui_theme: the system's, light or dark), live.
Item {
    id: hub
    objectName: "appDialogs"
    required property var store
    required property var dialogs
    required property var errors
    required property var editor
    // The editor pane (EditorPane.qml): the selection and the colours.
    required property var pane
    // The main window (its contentReady starts Quick Start).
    required property var mainWindow

    // --- The theme (B3's ui_theme) ------------------------------------------------------
    readonly property var settingsValues: hub.store.states.SettingsState.values || ({})
    readonly property string uiTheme: hub.settingsValues.ui_theme || "system"
    Binding {
        target: Theme
        property: "dark"
        value: hub.uiTheme === "dark"
               || (hub.uiTheme === "system" && hub.dialogs.systemDark)
    }

    // --- The ways in --------------------------------------------------------------------
    function openSettings(page) { settingsWin.showPage(page || "") }
    function openTranspose() {
        var a = hub.pane.area
        transposeDlg.ask(a.selectionEnd > a.selectionStart)
    }
    function openSuggestCapo() { hub.store.submit("request_suggest_capo", { selection: hub.selection() }) }
    function openQuickStart() { if (!quickStartDlg.opened) quickStartDlg.open() }
    function openHelp() { hub.dialogs.openHelp() }
    function openLicences() { licencesDlg.load() }
    function openAbout() { aboutDlg.open() }

    // The editor's selection as the session's [start, end], or null.
    function selection() {
        var a = hub.pane.area
        if (a.selectionEnd <= a.selectionStart) return null
        return [hub.editor.codePointAt(a.selectionStart), hub.editor.codePointAt(a.selectionEnd)]
    }

    // An error over the Settings window while it is the one in use; false
    // leaves it to the main window's dialog.
    function showError(title, message) {
        if (settingsWin.visible && (settingsWin.active || !hub.mainWindow.active)) {
            settingsWin.showError(title, message)
            return true
        }
        return false
    }

    // Help: F1, as in Tk (F1's menus must not add a second F1 shortcut).
    Shortcut { sequence: "F1"; context: Qt.WindowShortcut; onActivated: hub.openHelp() }

    // --- The dialogs --------------------------------------------------------------------
    SettingsWindow {
        id: settingsWin
        settings: hub.dialogs.settings
        errors: hub.errors
        transientParent: hub.mainWindow
    }
    TransposeDialog {
        id: transposeDlg
        onTranspose: (n) => {
            var a = hub.pane.area
            hub.store.submit("transpose", { semitones: n, selection: hub.selection(),
                                            cursor: hub.editor.codePointAt(a.cursorPosition) })
        }
        onClosed: hub.pane.focusEditor()
    }
    CapoDialog {
        id: capoDlg
        onAnswered: (id, value) => hub.store.submit("respond", { request_id: id, value: value })
        onClosed: hub.pane.focusEditor()
    }
    QuickStartDialog {
        id: quickStartDlg
        dialogs: hub.dialogs
        editor: hub.editor
        onAboutToShow: quickStartDlg.editorColours = hub.pane.palette()
        onOpened: hub.store.submit("request_quick_start")
        onFinished: (dontShow) => {
            if (dontShow) hub.store.submit("set_show_quick_start_on_startup", { show: false })
            hub.store.submit("dismiss_startup_screen")
        }
        onClosed: hub.pane.focusEditor()
    }
    AboutDialog {
        id: aboutDlg
        dialogs: hub.dialogs
        onLicencesRequested: licencesDlg.load()
        onClosed: hub.pane.focusEditor()
    }
    LicencesDialog {
        id: licencesDlg
        dialogs: hub.dialogs
        onClosed: if (!aboutDlg.visible) hub.pane.focusEditor()
    }

    Connections {
        target: hub.store
        // The main window is closing: the Settings window goes with it (it
        // would keep the app running otherwise).
        function onCloseApproved() {
            if (!settingsWin.visible) return
            hub.dialogs.settings.close()
            settingsWin.hide()
        }
        function onRequest(typeName, data) {
            if (typeName === "CapoChoiceRequest") capoDlg.ask(data)
        }
        function onEvent(typeName, data) {
            if (typeName === "QuickStartContent") quickStartDlg.setContent(data)
        }
    }

    // Quick Start: 100 ms after the window shows, when the session says so
    // (StartupState, decided by app_started from the setting).
    readonly property string startupScreen: hub.store.states.StartupState.screen || "none"
    readonly property bool quickStartDue: hub.mainWindow.contentReady && hub.startupScreen === "quick_start"
    onQuickStartDueChanged: if (hub.quickStartDue) quickStartTimer.start()
    Timer {
        id: quickStartTimer
        interval: 100
        onTriggered: if (hub.quickStartDue && !quickStartDlg.opened) quickStartDlg.open()
    }
}

import QtQuick
import QtQuick.Controls
import CNTheme

// The window's own commands (plan step F1), as Actions with window
// shortcuts: the menu bar, the ☰ menu and the Edit toolbar all use these,
// so each key sequence is declared once (a second Action or Shortcut with
// the same sequence makes both ambiguous, and neither fires). The editor's
// commands (Undo … Select all, the text zoom) are EditorPane's actions, the
// playback ones PlaybackActions', the chord sheet's (F9, Alt+1..4) E4's
// SheetActions: the menus reuse those.
//
// Shortcuts are explicit sequences; Qt maps Ctrl to Cmd on macOS and
// matches them with Caps Lock on. They are scoped to the main window, and a
// modal dialog blocks them (Q5).
//
//   Ctrl+N New            Ctrl+O Open…          Ctrl+S Save
//   Ctrl+Shift+S Save as… Ctrl+Q Quit           Ctrl+1 / Ctrl+2 Edit / Play
//   Ctrl+Alt+= / Ctrl+Alt+- / Ctrl+Alt+0 the whole window's zoom
//   F11 Full screen       Ctrl+Shift+L Dark theme   F10 the menu bar
//   Ctrl+T Transpose…     Ctrl+, Settings…      F1 User guide
//
// Enabled as Tk's menus are: everything always, except what the editor's
// actions disable (Undo/Redo on an empty stack, Q3). Transpose, Suggest
// capo and Convert stay enabled while a song plays; the session refuses the
// edit then and the status bar says so (Q9).
Item {
    id: acts
    objectName: "appActions"
    required property var store
    required property var chrome
    required property var editor
    // EditorPane (the caret, the selection, the focus).
    required property var pane
    // AppDialogs (Settings, Transpose, Help, …).
    required property var dialogs
    // The main window (the workspace, full screen, closing).
    required property var window

    readonly property string notation: acts.store.states.EditorState.notation || "american"

    function cursor() { return acts.editor.codePointAt(acts.pane.area.cursorPosition) }
    function convert(target) {
        acts.store.submit("convert_notation", { target: target, cursor: acts.cursor() })
    }

    // --- File ---------------------------------------------------------------------------
    // The editor sends every change at once (set_text), so the session has
    // the text before any of these runs (Tk's _send_text).
    readonly property Action newAction: Action {
        objectName: "newAction"
        text: "&New"; shortcut: "Ctrl+N"
        onTriggered: acts.store.submit("new_document")
    }
    readonly property Action openAction: Action {
        objectName: "openAction"
        text: "&Open…"; shortcut: "Ctrl+O"
        onTriggered: acts.store.submit("open_document", { ref: null, read_only: false })
    }
    readonly property Action saveAction: Action {
        objectName: "saveAction"
        text: "&Save"; shortcut: "Ctrl+S"
        onTriggered: acts.store.submit("save")
    }
    readonly property Action saveAsAction: Action {
        objectName: "saveAsAction"
        text: "Save &as…"; shortcut: "Ctrl+Shift+S"
        onTriggered: acts.store.submit("save_as", { name: null })
    }
    readonly property Action exportMidiAction: Action {
        objectName: "exportMidiAction"
        text: "&Export MIDI…"
        onTriggered: acts.store.submit("export_midi")
    }
    readonly property Action exportAudioAction: Action {
        objectName: "exportAudioAction"
        text: "Export a&udio…"
        onTriggered: acts.store.submit("export_audio")
    }
    readonly property Action exportPdfAction: Action {
        objectName: "exportPdfAction"
        text: "Export &PDF…"
        // On the locale's paper (Letter or A4).
        onTriggered: acts.chrome.files.exportPdf()
    }
    readonly property Action quitAction: Action {
        objectName: "quitAction"
        text: "&Quit"; shortcut: "Ctrl+Q"
        onTriggered: acts.window.requestClose()
    }

    // --- View ---------------------------------------------------------------------------
    readonly property ActionGroup modeGroup: ActionGroup { exclusive: true }
    readonly property Action editModeAction: Action {
        id: editMode
        objectName: "editModeAction"
        text: "&Edit"; shortcut: "Ctrl+1"
        checkable: true
        ActionGroup.group: acts.modeGroup
        checked: acts.window.mode === "edit"
        onTriggered: {
            acts.window.mode = "edit"
            editMode.checked = Qt.binding(function () { return acts.window.mode === "edit" })
        }
    }
    readonly property Action playModeAction: Action {
        id: playMode
        objectName: "playModeAction"
        text: "&Play"; shortcut: "Ctrl+2"
        checkable: true
        ActionGroup.group: acts.modeGroup
        checked: acts.window.mode === "play"
        onTriggered: {
            acts.window.mode = "play"
            playMode.checked = Qt.binding(function () { return acts.window.mode === "play" })
        }
    }
    readonly property Action wordWrapAction: Action {
        id: wrap
        objectName: "wordWrapAction"
        text: "&Word wrap"
        checkable: true
        checked: acts.store.states.EditorState.word_wrap === true
        onTriggered: {
            var on = acts.store.states.EditorState.word_wrap !== true
            wrap.checked = Qt.binding(function () { return acts.store.states.EditorState.word_wrap === true })
            acts.store.submit("set_word_wrap", { on: on })
        }
    }
    readonly property Action scaleUpAction: Action {
        objectName: "scaleUpAction"
        text: "Zoom &in (whole window)"; shortcut: "Ctrl+Alt+="
        enabled: acts.chrome.uiScale < acts.chrome.uiScaleMax
        onTriggered: acts.chrome.stepUiScale(1)
    }
    readonly property Action scaleDownAction: Action {
        objectName: "scaleDownAction"
        text: "Zoom &out (whole window)"; shortcut: "Ctrl+Alt+-"
        enabled: acts.chrome.uiScale > acts.chrome.uiScaleMin
        onTriggered: acts.chrome.stepUiScale(-1)
    }
    readonly property Action scaleResetAction: Action {
        objectName: "scaleResetAction"
        text: "Reset &zoom (100%)"; shortcut: "Ctrl+Alt+0"
        onTriggered: acts.chrome.resetUiScale()
    }
    readonly property Action fullScreenAction: Action {
        id: full
        objectName: "fullScreenAction"
        text: "&Full screen"; shortcut: "F11"
        checkable: true
        checked: acts.window.visibility === Window.FullScreen
        onTriggered: {
            acts.window.visibility = acts.window.visibility === Window.FullScreen
                ? Window.Windowed : Window.FullScreen
            full.checked = Qt.binding(function () { return acts.window.visibility === Window.FullScreen })
        }
    }
    readonly property Action menuBarAction: Action {
        id: menuBarShown
        objectName: "menuBarAction"
        text: "Show &menu bar"
        checkable: true
        // macOS always has its global menu bar.
        enabled: !acts.chrome.mac
        checked: acts.chrome.mac || acts.chrome.menuBarShown
        onTriggered: {
            acts.chrome.menuBarShown = !acts.chrome.menuBarShown
            menuBarShown.checked = Qt.binding(function () { return acts.chrome.mac || acts.chrome.menuBarShown })
        }
    }
    // F10: the menu bar's first menu (showing the bar if hidden), as on
    // Windows and KDE. Not on macOS (the global menu bar has its own keys).
    readonly property Action menuKeysAction: Action {
        objectName: "menuKeysAction"
        text: "Menu bar"; shortcut: "F10"
        enabled: !acts.chrome.mac
        onTriggered: acts.window.openMenuBar()
    }
    readonly property Action darkAction: Action {
        id: dark
        objectName: "darkAction"
        text: "&Dark theme"; shortcut: "Ctrl+Shift+L"
        checkable: true
        checked: Theme.dark
        onTriggered: {
            var theme = Theme.dark ? "light" : "dark"
            dark.checked = Qt.binding(function () { return Theme.dark })
            acts.store.submit("set_ui_theme", { theme: theme })
        }
    }

    // --- Tools --------------------------------------------------------------------------
    readonly property Action transposeAction: Action {
        objectName: "transposeAction"
        text: "&Transpose…"; shortcut: "Ctrl+T"
        onTriggered: acts.dialogs.openTranspose()
    }
    readonly property Action suggestCapoAction: Action {
        objectName: "suggestCapoAction"
        text: "Suggest &capo…"
        onTriggered: acts.dialogs.openSuggestCapo()
    }
    readonly property Action toAmericanAction: Action {
        objectName: "toAmericanAction"
        text: "Convert to &American notation"
        onTriggered: acts.convert("american")
    }
    readonly property Action toEuropeanAction: Action {
        objectName: "toEuropeanAction"
        text: "Convert to &European notation"
        onTriggered: acts.convert("european")
    }
    // The toolbar's one Convert button: to the notation the song isn't in.
    readonly property Action convertAction: Action {
        objectName: "convertAction"
        text: "Convert"
        onTriggered: acts.convert(acts.notation === "american" ? "european" : "american")
    }
    readonly property Action settingsAction: Action {
        objectName: "settingsAction"
        text: "&Settings…"; shortcut: "Ctrl+,"
        onTriggered: acts.dialogs.openSettings("general")
    }

    // --- Help ---------------------------------------------------------------------------
    readonly property Action helpAction: Action {
        objectName: "helpAction"
        text: "&User guide"; shortcut: "F1"
        onTriggered: acts.dialogs.openHelp()
    }
    readonly property Action quickStartAction: Action {
        objectName: "quickStartAction"
        text: "&Quick start"
        onTriggered: acts.dialogs.openQuickStart()
    }
    readonly property Action shortcutsAction: Action {
        objectName: "shortcutsAction"
        text: "&Keyboard shortcuts"
        onTriggered: acts.dialogs.openHelpPage("shortcuts.html")
    }
    readonly property Action licencesAction: Action {
        objectName: "licencesAction"
        text: "Open source &licences"
        onTriggered: acts.dialogs.openLicences()
    }
    readonly property Action aboutAction: Action {
        objectName: "aboutAction"
        text: "&About Chord Notepad"
        onTriggered: acts.dialogs.openAbout()
    }

    // Theme.scale follows the kept zoom (0.7-2.0, ChromeModel).
    Binding { target: Theme; property: "scale"; value: acts.chrome.uiScale }
}

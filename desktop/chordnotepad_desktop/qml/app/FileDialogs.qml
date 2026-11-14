import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import CNTheme

// The file pickers (plan step F3): the session's PickDocumentRequest, shown
// as a Qt FileDialog with Tk's titles, filters and suggested names
// (FilesModel in files.py says which). Open, Save As (also for Save on a
// song never saved, and Save before closing one) and Export MIDI. The
// FileDialog is the platform's: the xdg-desktop-portal's inside a Flatpak or
// a Snap (Qt's xdgdesktopportal theme), else Qt Quick's own on Linux, the
// native one on Windows and macOS.
//
// Save As takes the suggested name with its extension ("song.txt"): under the
// portal the sandbox may write only the exact name chosen. A name typed
// without an extension gets the picker's (as in Tk); if that file exists,
// "Confirm Save As" asks first (the picker only asked about the name as
// typed). No initial folder, as in Tk. One picker at a time: FilesModel
// cancels a request that comes while one is open.
Item {
    id: hub
    objectName: "fileDialogs"
    required property var files          // FilesModel
    signal finished()

    property int requestId: -1
    property bool choosing: false

    // Qt Quick's own dialog (no platform dialog, no portal) paints with the
    // application palette: give it the window's colours.
    function useColours() {
        hub.files.useColours({
            window: Theme.panel, windowText: Theme.text, base: Theme.base, alternateBase: Theme.panel,
            text: Theme.text, button: Theme.chrome, buttonText: Theme.text, brightText: Theme.text,
            light: Theme.base, midlight: Theme.controlHover, mid: Theme.border, dark: Theme.border,
            shadow: Theme.shadow, highlight: Theme.accentFill, highlightedText: Theme.textOnAccent,
            placeholderText: Theme.muted, toolTipBase: Theme.popup, toolTipText: Theme.text,
            link: Theme.accent
        })
    }
    Component.onCompleted: hub.useColours()
    Connections {
        target: Theme
        function onDarkChanged() { hub.useColours() }
    }

    // What the picker's Accepted does, for a file chosen without its own
    // file list (the tests: Qt Quick's dialog can't be driven offscreen).
    function choose(url) {
        if (!picker.visible) return
        hub.choosing = true
        picker.close()
        hub.choosing = false
        hub.files.accept(hub.requestId, url)
    }

    FileDialog {
        id: picker
        objectName: "filePicker"
        onAccepted: hub.files.accept(hub.requestId, picker.selectedFile.toString())
        onRejected: if (!hub.choosing) hub.files.cancel(hub.requestId)
        onVisibleChanged: if (!visible && !replaceDlg.visible) hub.finished()
    }

    Connections {
        target: hub.files
        function onPickRequested(spec) {
            hub.requestId = spec.requestId
            picker.title = spec.title
            picker.nameFilters = spec.nameFilters
            picker.fileMode = spec.save ? FileDialog.SaveFile : FileDialog.OpenFile
            // The name in the folder the dialog is in (no folder of our own:
            // it starts where the platform's dialog starts, then stays in the
            // last one used).
            if (spec.suggestedName !== "")
                picker.selectedFile = hub.files.fileUrl(picker.currentFolder, spec.suggestedName)
            picker.open()
            if (spec.suggestedName !== "")
                Qt.callLater(hub.files.prefillQuickDialog, hub.Window.window, spec.suggestedName)
        }
        function onConfirmReplace(id, title, message) { replaceDlg.ask(id, title, message) }
    }

    // "Confirm Save As": the file the added extension names exists already.
    AppDialog {
        id: replaceDlg
        objectName: "confirmReplaceDialog"
        property int requestId: -1
        property bool pending: false
        property string message: ""
        function ask(id, t, m) {
            replaceDlg.requestId = id
            replaceDlg.title = t
            replaceDlg.message = m
            replaceDlg.pending = true
            replaceDlg.open()
        }
        function answer(replace) {
            if (!replaceDlg.pending) return
            replaceDlg.pending = false
            replaceDlg.close()
            hub.files.replaceAnswered(replaceDlg.requestId, replace)
        }
        closePolicy: Popup.CloseOnEscape
        onClosed: { replaceDlg.answer(false); hub.finished() }
        contentItem: Label {
            objectName: "confirmReplaceText"
            text: replaceDlg.message
            color: Theme.muted; wrapMode: Text.Wrap
        }
        footer: DialogFooter {
            Button { objectName: "replaceNo"; text: "No"; onClicked: replaceDlg.answer(false) }
            Button { objectName: "replaceYes"; text: "Replace"; highlighted: true; onClicked: replaceDlg.answer(true) }
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Suggest Capo (plan step G2): the session's CapoChoiceRequest asks which
// fretboard voicing to optimize the capo for. Tk's texts
// (dialogs/capo_dialog.py) in the mockup's dialog style: what it does, the
// scope line (the selection or the whole song), the voicing. Enter or
// Suggest answers with the voicing; Escape or Cancel answers null. The
// session then scores the song ("Finding a capo…" in the status line) and
// inserts {capo: N} as one undo step, or says that no capo helps.
AppDialog {
    id: dlg
    objectName: "capoDialog"
    property int requestId: -1
    property bool pending: false
    property var options: []
    property string scope: ""
    signal answered(int requestId, var value)

    function ask(request) {
        dlg.requestId = request.request_id
        dlg.options = request.options || []
        dlg.scope = request.scope || ""
        var i = dlg.options.findIndex((o) => o.value === request["default"])
        voicing.currentIndex = i >= 0 ? i : 0
        dlg.pending = true
        dlg.open()
    }
    function answer(value) {
        if (!dlg.pending) return
        dlg.pending = false
        dlg.close()
        dlg.answered(dlg.requestId, value)
    }

    title: "Suggest Capo"
    width: Theme.px(118)
    closePolicy: Popup.CloseOnEscape
    onOpened: voicing.forceActiveFocus()
    onClosed: dlg.answer(null)
    contentItem: ColumnLayout {
        spacing: Theme.gap3
        Label {
            text: "Suggest a capo position for this song.\n\nChoose the fretboard voicing the suggestion should optimize for; the recommended capo makes those shapes easiest to play."
            color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Label {
            objectName: "capoScope"
            visible: text !== ""
            text: dlg.scope
            font: Theme.fontMedium; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        RowLayout {
            spacing: Theme.gap3
            Label { text: "Voicing"; font: Theme.fontMedium; Layout.fillWidth: true }
            ComboBox {
                id: voicing
                objectName: "capoVoicing"
                model: dlg.options.map((o) => o.label)
                Layout.preferredWidth: Theme.px(62)
                Keys.onReturnPressed: dlg.answer(dlg.options[voicing.currentIndex].value)
                Keys.onEnterPressed: dlg.answer(dlg.options[voicing.currentIndex].value)
            }
        }
    }
    footer: DialogFooter {
        Button { objectName: "capoCancel"; text: "Cancel"; onClicked: dlg.answer(null) }
        Button {
            objectName: "capoOk"
            text: "Suggest"
            highlighted: true
            enabled: dlg.options.length > 0
            onClicked: dlg.answer(dlg.options[voicing.currentIndex].value)
        }
    }
}

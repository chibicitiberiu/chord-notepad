import QtQuick
import QtQuick.Controls
import CNTheme

// Unsaved changes: the session's ConfirmDiscardRequest (before closing the
// window, New and Open). Don't save alone on the left, Save last; Escape or
// closing it any other way is Cancel. The texts are the session's
// (formatting.CONFIRM_DISCARD_*), the button labels the parity checklist's.
//
// choiceMade(requestId, choice) gives the session's DiscardChoice value:
// "save", "discard" or "cancel", once per request. A new request while one is
// open takes its place (the session has dropped the old one).
AppDialog {
    id: dlg
    objectName: "unsavedDialog"
    required property var texts
    property int requestId: -1
    property bool pending: false
    signal choiceMade(int requestId, string choice)

    function ask(id) {
        dlg.requestId = id
        dlg.pending = true
        dlg.open()
    }
    function answer(choice) {
        if (!dlg.pending) return
        dlg.pending = false
        dlg.close()
        dlg.choiceMade(dlg.requestId, choice)
    }

    title: dlg.texts.confirmDiscardTitle
    width: Theme.px(120)
    closePolicy: Popup.CloseOnEscape
    onClosed: dlg.answer("cancel")
    contentItem: Label {
        text: dlg.texts.confirmDiscardMessage
        color: Theme.muted; wrapMode: Text.Wrap
    }
    footer: DialogFooter {
        leading: Button {
            objectName: "unsavedDiscard"
            text: "Don't save"; flat: true
            contentItem: SText {
                text: "Don't save"; color: Theme.error; font: Theme.fontMedium
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            onClicked: dlg.answer("discard")
        }
        Button { objectName: "unsavedCancel"; text: "Cancel"; onClicked: dlg.answer("cancel") }
        Button { objectName: "unsavedSave"; text: "Save"; highlighted: true; onClicked: dlg.answer("save") }
    }
}

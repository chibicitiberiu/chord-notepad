import QtQuick
import QtQuick.Controls
import CNTheme

// Errors and the session's messages, as the error presenter (error_presenter.py)
// hands them over: one at a time, `show(title, message)`; `dismissed()` when it
// closes (OK, Escape), so the presenter can show the next one.
AppDialog {
    id: dlg
    objectName: "errorDialog"
    property string message: ""
    signal dismissed()

    function show(title, message) {
        dlg.title = title
        dlg.message = message
        dlg.open()
    }

    width: Theme.px(150)
    closePolicy: Popup.CloseOnEscape
    onClosed: dlg.dismissed()
    contentItem: Label {
        objectName: "errorMessage"
        text: dlg.message
        textFormat: Text.PlainText
        color: Theme.text
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
    }
    footer: DialogFooter {
        Button { objectName: "errorOk"; text: "OK"; highlighted: true; onClicked: dlg.close() }
    }
}

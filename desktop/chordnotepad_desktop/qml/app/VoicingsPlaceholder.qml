import QtQuick
import QtQuick.Controls
import CNTheme

// "Edit voicings…" until the Settings window comes (plan step G1, which
// replaces this with the Voicings page).
AppDialog {
    id: dlg
    objectName: "voicingsPlaceholder"
    title: "Voicings"
    closePolicy: Popup.CloseOnEscape
    contentItem: Label {
        text: "The voicings editor comes with the Settings window, which the Qt version doesn't have yet."
        color: Theme.muted; wrapMode: Text.Wrap
    }
    footer: DialogFooter {
        Button { objectName: "voicingsClose"; text: "Close"; highlighted: true; onClicked: dlg.close() }
    }
}

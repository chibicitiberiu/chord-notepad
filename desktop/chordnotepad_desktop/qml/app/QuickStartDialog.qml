import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Quick Start, for now a plain stand-in (plan step G2 builds the real one):
// the session's QuickStartContent pages as text, n / N, Previous and Next,
// "Don't show this again on startup" and Close. The texts are Tk's
// (chordnotepad_tk/dialogs/quick_start.py).
//
// Opened by the window when the session's StartupState says "quick_start";
// it asks for the pages itself (request_quick_start). finished(dontShow)
// when it closes.
AppDialog {
    id: dlg
    objectName: "quickStartDialog"
    property var pages: []
    property int page: 0
    readonly property var current: dlg.pages.length > dlg.page ? dlg.pages[dlg.page] : null
    signal finished(bool dontShow)

    function setContent(content) {
        dlg.pages = content.pages
        dlg.page = 0
    }
    function pageText(p) {
        if (!p) return ""
        var parts = []
        for (var i = 0; i < p.blocks.length; i++) {
            var b = p.blocks[i]
            if (b.kind !== "image") parts.push(b.text)
        }
        return parts.join("\n\n")
    }

    title: "Quick Start"
    width: Theme.px(150)
    closePolicy: Popup.CloseOnEscape
    onClosed: dlg.finished(dontShow.checked)
    contentItem: ColumnLayout {
        spacing: Theme.gap3
        RowLayout {
            Layout.fillWidth: true
            SText {
                objectName: "quickStartPageTitle"
                text: dlg.current ? dlg.current.title : ""
                font: Theme.fontStrong
                color: Theme.text
                Layout.fillWidth: true
            }
            SText {
                objectName: "quickStartPageIndicator"
                text: dlg.pages.length ? (dlg.page + 1) + " / " + dlg.pages.length : ""
                font: Theme.fontS
                color: Theme.muted
            }
        }
        Label {
            objectName: "quickStartPageText"
            text: dlg.pageText(dlg.current)
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            color: Theme.text
            Layout.fillWidth: true
        }
        CheckBox {
            id: dontShow
            objectName: "quickStartDontShow"
            text: "Don't show this again on startup"
        }
    }
    footer: DialogFooter {
        leading: Button {
            objectName: "quickStartClose"
            text: "Close"; flat: true
            onClicked: dlg.close()
        }
        Button {
            objectName: "quickStartPrevious"
            text: "← Previous"
            enabled: dlg.page > 0
            onClicked: dlg.page -= 1
        }
        Button {
            objectName: "quickStartNext"
            text: "Next →"
            highlighted: true
            enabled: dlg.page + 1 < dlg.pages.length
            onClicked: dlg.page += 1
        }
    }
}

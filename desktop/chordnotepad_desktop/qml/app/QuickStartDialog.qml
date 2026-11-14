pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Quick Start (plan step G2): the session's QuickStartContent for the Qt
// desktop (session/quick_start.py, DESKTOP_QT texts) in the mockup's dialog
// style. Tk's dialog (dialogs/quick_start.py) is the model: the page title
// with "n / N" at the right, the page's paragraphs, examples and pictures,
// "Don't show this again on startup", Previous / Next (off at the ends) and
// Close. Left and Right page through when that button is on; Escape closes.
// The examples are the editor's: its font and size (so chords line up over
// their lyrics) and its colours, from the spans the session sent.
//
// Opened by the window at startup when StartupState says so, or from Help
// (F1's menu: AppDialogs.openQuickStart). It asks for the pages itself
// (`opened` → request_quick_start). finished(dontShow) when it closes:
// "Don't show again" only ever turns the setting off.
AppDialog {
    id: dlg
    objectName: "quickStartDialog"
    required property var dialogs
    required property var editor
    // The editor's colours (EditorPane.palette()).
    property var editorColours: ({})
    property var pages: []
    property int page: 0
    readonly property var current: dlg.pages.length > dlg.page ? dlg.pages[dlg.page] : null
    readonly property bool canGoBack: dlg.page > 0
    readonly property bool canGoOn: dlg.page + 1 < dlg.pages.length
    signal finished(bool dontShow)

    function setContent(content) {
        dlg.pages = content.pages
        dlg.page = 0
    }
    function back() { if (dlg.canGoBack) dlg.page -= 1 }
    function next() { if (dlg.canGoOn) dlg.page += 1 }

    title: "Quick Start"
    width: Math.min(Theme.px(190), Overlay.overlay ? Overlay.overlay.width - Theme.px(8) : Theme.px(190))
    height: Math.min(implicitHeight, Overlay.overlay ? Overlay.overlay.height - Theme.px(8) : implicitHeight)
    closePolicy: Popup.CloseOnEscape
    onAboutToShow: dontShow.checked = false
    onClosed: dlg.finished(dontShow.checked)

    contentItem: ColumnLayout {
        spacing: Theme.gap3
        focus: true
        Keys.onLeftPressed: dlg.back()
        Keys.onRightPressed: dlg.next()
        RowLayout {
            Layout.fillWidth: true
            SText {
                objectName: "quickStartPageTitle"
                text: dlg.current ? dlg.current.title : ""
                font: Theme.fontHeadF
                color: Theme.text
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            SText {
                objectName: "quickStartPageIndicator"
                text: dlg.pages.length ? (dlg.page + 1) + " / " + dlg.pages.length : ""
                font: Theme.fontS
                color: Theme.muted
            }
        }
        ScrollView {
            id: bodyScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: body.implicitHeight
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                id: body
                objectName: "quickStartBody"
                width: bodyScroll.availableWidth
                spacing: Theme.gap3
                Repeater {
                    model: dlg.current ? dlg.current.blocks : []
                    delegate: Loader {
                        id: block
                        required property var modelData
                        Layout.fillWidth: true
                        sourceComponent: block.modelData.kind === "snippet" ? snippet
                                         : block.modelData.kind === "image" ? picture : paragraph
                        Component {
                            id: paragraph
                            Label {
                                objectName: "quickStartText"
                                text: block.modelData.text
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                color: Theme.text
                            }
                        }
                        Component {
                            id: snippet
                            Rectangle {
                                objectName: "quickStartSnippet"
                                implicitHeight: snippetText.implicitHeight + 2 * Theme.gap2
                                color: Theme.editorBg
                                radius: Theme.radius
                                border.width: Theme.hairline
                                border.color: Theme.border
                                clip: true
                                TextEdit {
                                    id: snippetText
                                    objectName: "quickStartSnippetText"
                                    x: Theme.gap3; y: Theme.gap2
                                    width: parent.width - 2 * Theme.gap3
                                    readOnly: true
                                    selectByMouse: false
                                    activeFocusOnPress: false
                                    wrapMode: TextEdit.NoWrap
                                    textFormat: TextEdit.PlainText
                                    text: block.modelData.text
                                    color: Theme.editorText
                                    font: Theme.editorFont(dlg.editor.fontFamily, dlg.editor.fontSize)
                                    Component.onCompleted: dlg.dialogs.paintSnippet(snippetText.textDocument,
                                                                                    block.modelData.spans, dlg.editorColours)
                                }
                            }
                        }
                        Component {
                            id: picture
                            Item {
                                readonly property string source: dlg.dialogs.resourceUrl(block.modelData.image || "")
                                visible: source !== ""
                                implicitHeight: source !== "" ? img.height + 2 * Theme.hairline : 0
                                Rectangle {
                                    width: img.width + 2 * Theme.hairline
                                    height: img.height + 2 * Theme.hairline
                                    color: "transparent"
                                    border.width: Theme.hairline
                                    border.color: Theme.border
                                }
                                Image {
                                    id: img
                                    objectName: "quickStartImage"
                                    x: Theme.hairline; y: Theme.hairline
                                    source: parent.source
                                    width: Math.min(sourceSize.width, parent.width - 2 * Theme.hairline)
                                    height: sourceSize.width > 0 ? width * sourceSize.height / sourceSize.width : 0
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    footer: DialogFooter {
        leading: CheckBox {
            id: dontShow
            objectName: "quickStartDontShow"
            Keys.onLeftPressed: dlg.back()
            Keys.onRightPressed: dlg.next()
            text: "Don't show this again on startup"
        }
        Button {
            objectName: "quickStartPrevious"
            Keys.onLeftPressed: dlg.back()
            Keys.onRightPressed: dlg.next()
            text: "← Previous"
            enabled: dlg.canGoBack
            onClicked: dlg.back()
        }
        Button {
            objectName: "quickStartNext"
            Keys.onLeftPressed: dlg.back()
            Keys.onRightPressed: dlg.next()
            text: "Next →"
            highlighted: dlg.canGoOn
            enabled: dlg.canGoOn
            onClicked: dlg.next()
        }
        Button {
            objectName: "quickStartClose"
            Keys.onLeftPressed: dlg.back()
            Keys.onRightPressed: dlg.next()
            text: "Close"
            highlighted: !dlg.canGoOn
            onClicked: dlg.close()
        }
    }
}

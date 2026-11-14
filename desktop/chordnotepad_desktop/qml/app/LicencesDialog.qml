pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Open Source Licences (plan step G2): every component of this build and
// its licence, from the session's licence catalog (DialogsModel.licences).
// Tk's window (dialogs/licences_dialog.py) in the mockup's dialog style: the
// list on the left (Component | Licence, grouped, "Source code" first and
// selected), the selected one's details on the right (licence, copyright,
// note, source, the link) over its full text in a fixed-width font,
// scrolled to the top. Escape closes it and gives the keys back to the
// dialog underneath (About), as every popup here does.
AppDialog {
    id: dlg
    objectName: "licencesDialog"
    required property var dialogs
    property var rows: []
    property string intro: ""
    property string selectedId: ""
    property var detail: ({})

    // Fill from the catalog and open; false if it couldn't be read (the
    // presenter shows "Licences Unavailable").
    function load() {
        var data = dlg.dialogs.licences()
        if (!data.ok) return false
        dlg.rows = data.rows
        dlg.intro = data.intro
        dlg.select(data.rows.length ? data.rows[0].id : "")
        dlg.open()
        return true
    }
    function select(id) {
        dlg.selectedId = id
        dlg.detail = id ? dlg.dialogs.licenceDetail(id) : ({})
        textArea.cursorPosition = 0
        textScroll.ScrollBar.vertical.position = 0
        var i = dlg.rows.findIndex((r) => r.id === id)
        if (i >= 0) list.currentIndex = i
    }
    function step(delta) {
        var i = list.currentIndex
        do { i += delta } while (i >= 0 && i < dlg.rows.length && dlg.rows[i].group)
        if (i >= 0 && i < dlg.rows.length) dlg.select(dlg.rows[i].id)
    }

    title: "Open Source Licences"
    width: Math.min(Theme.px(220), Overlay.overlay ? Overlay.overlay.width - Theme.px(8) : Theme.px(220))
    height: Math.min(Theme.px(150), Overlay.overlay ? Overlay.overlay.height - Theme.px(8) : Theme.px(150))
    closePolicy: Popup.CloseOnEscape
    onOpened: list.forceActiveFocus()

    contentItem: ColumnLayout {
        spacing: Theme.gap3
        Label { text: dlg.intro; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.gap4
            // The list.
            Rectangle {
                Layout.preferredWidth: Theme.px(88)
                Layout.fillHeight: true
                radius: Theme.radius
                color: Theme.panel
                border.width: Theme.hairline; border.color: Theme.border
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.hairline
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
                        Layout.topMargin: Theme.gap1; Layout.bottomMargin: Theme.gap1
                        Label { text: "Component"; font: Theme.fontStrongS; color: Theme.muted; Layout.fillWidth: true }
                        Label { text: "Licence"; font: Theme.fontStrongS; color: Theme.muted; Layout.preferredWidth: Theme.px(30) }
                    }
                    Rectangle { Layout.fillWidth: true; implicitHeight: Theme.hairline; color: Theme.border }
                    ListView {
                        id: list
                        objectName: "licencesList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: dlg.rows
                        highlightMoveDuration: 0
                        keyNavigationEnabled: false
                        Keys.onUpPressed: dlg.step(-1)
                        Keys.onDownPressed: dlg.step(1)
                        ScrollBar.vertical: ScrollBar { }
                        delegate: ItemDelegate {
                            id: rowItem
                            required property var modelData
                            required property int index
                            width: ListView.view.width
                            enabled: !modelData.group
                            highlighted: modelData.id === dlg.selectedId
                            focusPolicy: Qt.NoFocus
                            onClicked: { dlg.select(modelData.id); list.forceActiveFocus() }
                            contentItem: RowLayout {
                                spacing: Theme.gap2
                                Label {
                                    text: rowItem.modelData.label
                                    font: rowItem.modelData.group ? Theme.fontStrong : Theme.font
                                    color: Theme.text
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    Layout.leftMargin: rowItem.modelData.group || rowItem.index === 0 ? 0 : Theme.gap3
                                }
                                Label {
                                    text: rowItem.modelData.licence
                                    color: Theme.muted; font: Theme.fontS
                                    elide: Text.ElideRight
                                    Layout.preferredWidth: Theme.px(30)
                                }
                            }
                        }
                    }
                }
            }
            // The details.
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Theme.gap1
                Label {
                    objectName: "licenceTitle"
                    text: dlg.detail.title || ""
                    font: Theme.fontTitleF
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "licenceDetails"
                    visible: text !== ""
                    text: dlg.detail.details || ""
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: Theme.muted
                    Layout.fillWidth: true
                }
                Label {
                    objectName: "licenceLink"
                    visible: text !== ""
                    text: dlg.detail.url || ""
                    color: Theme.accent
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    HoverHandler { id: linkHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: dlg.dialogs.openUrl(dlg.detail.url) }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.topMargin: Theme.gap2
                    radius: Theme.radius
                    color: Theme.input
                    border.width: Theme.hairline; border.color: Theme.border
                    ScrollView {
                        id: textScroll
                        anchors.fill: parent
                        anchors.margins: Theme.hairline
                        TextArea {
                            id: textArea
                            objectName: "licenceText"
                            readOnly: true
                            wrapMode: TextEdit.Wrap
                            textFormat: TextEdit.PlainText
                            text: dlg.detail.text || ""
                            font: Theme.fontMonoS
                            color: Theme.text
                            selectByMouse: true
                            leftPadding: Theme.gap3; rightPadding: Theme.gap3
                            topPadding: Theme.gap2; bottomPadding: Theme.gap2
                            background: null
                        }
                    }
                }
            }
        }
    }
    footer: DialogFooter {
        Button { objectName: "licencesClose"; text: "Close"; highlighted: true; onClicked: dlg.close() }
    }
}

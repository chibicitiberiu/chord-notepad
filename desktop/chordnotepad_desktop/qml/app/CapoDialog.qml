pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// Suggest Capo: one dialog over the session's CapoAdviceState. It opens
// when the state goes active (capo_advice_open) and closes when it goes
// inactive (Apply, Cancel, or the document replaced). At the top, the scope
// line and the voicing (choosing another scores again); a spinner while the
// capos are scored; then the ranked rows in words, the recommended one
// first and chosen, tagged Recommended and Current. Up/Down choose a row,
// Enter or Apply puts its capo in the song as one undo step
// (capo_advice_apply), Escape or Cancel closes without a change
// (capo_advice_close). Apply waits while a song plays, with a hint.
AppDialog {
    id: dlg
    objectName: "capoDialog"
    required property var store
    readonly property var advice: dlg.store.states.CapoAdviceState
    readonly property bool active: !!dlg.advice.active
    readonly property var rows: dlg.advice.rows || []
    readonly property var voicings: dlg.advice.voicings || []
    readonly property bool computing: dlg.advice.status === "computing"
    readonly property bool playing: !!dlg.advice.playing
    // The chosen row's capo (-1: none).
    property int chosen: -1
    readonly property int chosenIndex: dlg.rows.findIndex((r) => r.capo === dlg.chosen)
    readonly property bool canApply: dlg.advice.status === "ready" && !dlg.playing && dlg.chosenIndex >= 0

    // Open at once: a close and a reopen can reach the store as one state
    // that never stops being active, so the active change alone can't be relied on.
    function begin(selection) {
        dlg.store.submit("capo_advice_open", { selection: selection })
        if (!dlg.opened) dlg.open()
    }
    function choose(index) {
        if (index < 0 || index >= dlg.rows.length) return
        dlg.chosen = dlg.rows[index].capo
        list.currentIndex = index
    }
    function apply() { if (dlg.canApply) dlg.store.submit("capo_advice_apply", { capo: dlg.chosen }) }

    onActiveChanged: {
        if (dlg.active && !dlg.opened) dlg.open()
        else if (!dlg.active && dlg.opened) dlg.close()
    }
    // New rows (a voicing switch, a rescore): the recommended one is chosen.
    onRowsChanged: {
        dlg.chosen = dlg.rows.length ? dlg.rows[0].capo : -1
        list.currentIndex = dlg.rows.length ? 0 : -1
    }

    title: "Suggest Capo"
    width: Math.min(Theme.px(140), Overlay.overlay ? Overlay.overlay.width - Theme.px(8) : Theme.px(140))
    closePolicy: Popup.CloseOnEscape
    onOpened: list.forceActiveFocus()
    // Escape (or the window closing it) while the session still has it open: Cancel.
    onClosed: if (dlg.active) dlg.store.submit("capo_advice_close")

    contentItem: ColumnLayout {
        spacing: Theme.gap3
        Label {
            text: "Each row is a capo position, the chord shapes you play with it, and how easy they are next to no capo. The recommended one comes first."
            color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Label {
            objectName: "capoScope"
            visible: text !== ""
            text: dlg.advice.scope || ""
            font: Theme.fontMedium; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        RowLayout {
            spacing: Theme.gap3
            Label { text: "Voicing"; font: Theme.fontMedium; Layout.fillWidth: true }
            ComboBox {
                id: voicing
                objectName: "capoVoicing"
                model: dlg.voicings.map((o) => o.label)
                currentIndex: dlg.voicings.findIndex((o) => o.value === dlg.advice.voicing)
                Layout.preferredWidth: Theme.px(62)
                onActivated: (i) => dlg.store.submit("capo_advice_voicing", { voicing: dlg.voicings[i].value })
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.px(62)
            radius: Theme.radius
            color: Theme.panel
            border.width: Theme.hairline; border.color: Theme.border
            RowLayout {
                objectName: "capoComputing"
                anchors.centerIn: parent
                visible: dlg.computing
                spacing: Theme.gap3
                BusyIndicator { objectName: "capoSpinner"; running: dlg.computing }
                Label { text: dlg.store.texts.capoFinding; color: Theme.muted }
            }
            ListView {
                id: list
                objectName: "capoRows"
                anchors.fill: parent
                anchors.margins: Theme.hairline
                clip: true
                visible: !dlg.computing
                model: dlg.rows
                highlightMoveDuration: 0
                keyNavigationEnabled: false
                Keys.onUpPressed: dlg.choose(dlg.chosenIndex - 1)
                Keys.onDownPressed: dlg.choose(dlg.chosenIndex + 1)
                Keys.onReturnPressed: dlg.apply()
                Keys.onEnterPressed: dlg.apply()
                ScrollBar.vertical: ScrollBar { }
                delegate: ItemDelegate {
                    id: rowItem
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    highlighted: rowItem.modelData.capo === dlg.chosen
                    focusPolicy: Qt.NoFocus
                    onClicked: { dlg.choose(rowItem.index); list.forceActiveFocus() }
                    onDoubleClicked: { dlg.choose(rowItem.index); dlg.apply() }
                    contentItem: RowLayout {
                        spacing: Theme.gap2
                        Label {
                            text: rowItem.modelData.label
                            color: Theme.text
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Tag { visible: rowItem.modelData.recommended; text: "Recommended"; strong: true }
                        Tag { visible: rowItem.modelData.current; text: "Current" }
                    }
                }
            }
        }
        Label {
            objectName: "capoMessage"
            visible: text !== ""
            text: dlg.advice.message || ""
            color: dlg.advice.status === "error" ? Theme.error : Theme.muted
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Label {
            objectName: "capoStopHint"
            visible: dlg.playing
            text: dlg.store.texts.capoStopToApply
            color: Theme.muted; font: Theme.fontS
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }
    }
    footer: DialogFooter {
        Button { objectName: "capoCancel"; text: "Cancel"; onClicked: dlg.close() }
        Button {
            objectName: "capoApply"
            text: "Apply"
            highlighted: true
            enabled: dlg.canApply
            onClicked: dlg.apply()
        }
    }

    // A row's small tag: Recommended (in the accent) or Current.
    component Tag: Rectangle {
        property alias text: tagLabel.text
        property bool strong: false
        implicitWidth: tagLabel.implicitWidth + 2 * Theme.gap2
        implicitHeight: tagLabel.implicitHeight + Theme.gap1
        radius: height / 2
        color: strong ? Theme.selectedRow : Theme.checkedBg
        Label {
            id: tagLabel
            anchors.centerIn: parent
            font: Theme.fontC
            color: parent.strong ? Theme.accent : Theme.muted
        }
    }
}

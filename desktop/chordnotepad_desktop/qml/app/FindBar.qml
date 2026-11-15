import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The find bar under the text (Kate's and Firefox's place; Tibi's choice).
// Find: the field, "3 of 7", previous / next, match case (Aa) and whole
// word (W), the wrap-around notice, close. Replace (Ctrl+H, or the ▸ at
// the left): a second row with the replacement, Replace and Replace all.
// Go to line (Ctrl+G): the bar's other mode, one row.
// What it finds and does is FindModel's (find_bar.py); this file lays it out
// and routes the keys: Enter next, Shift+Enter previous, Escape closes and
// gives the text the keys back.
Rectangle {
    id: bar
    objectName: "findBar"
    required property var finder
    // No Replace row in the Play workspace (the text is only read there).
    property bool canReplace: true
    // "find" or "line" (Go to line).
    property string mode: "find"
    property bool replacing: false
    property bool shown: false
    signal closed()
    visible: bar.shown
    implicitHeight: bar.shown ? rows.implicitHeight + 2 * Theme.gap2 : 0
    color: Theme.chrome

    function open(replace) {
        bar.mode = "find"
        bar.replacing = replace && bar.canReplace
        bar.shown = true
        var prefill = bar.finder.begin()
        if (prefill !== "") findField.text = prefill
        else bar.finder.setQuery(findField.text)
        findField.selectAll()
        findField.forceActiveFocus()
    }
    function openGoToLine() {
        if (bar.shown && bar.mode === "find") bar.finder.end()
        bar.mode = "line"
        bar.shown = true
        lineField.text = ""
        lineField.forceActiveFocus()
    }
    function close() {
        if (!bar.shown) return
        bar.shown = false
        bar.finder.end()
        bar.closed()
    }
    function goToLine() {
        if (bar.finder.goToLine(lineField.text)) bar.close()
    }
    onCanReplaceChanged: if (!bar.canReplace) bar.replacing = false
    onShownChanged: Theme.bumpLayout()

    Rectangle { width: parent.width; height: Theme.hairline; color: Theme.border }

    component BarField: TextField {
        Layout.preferredWidth: Theme.px(62)
        Layout.preferredHeight: Theme.controlSmall
    }
    component Toggle: ToolButton {
        id: toggle
        property string tip
        checkable: true
        focusPolicy: Qt.TabFocus
        display: AbstractButton.TextOnly
        implicitWidth: Theme.controlSmall + Theme.px(1); implicitHeight: Theme.controlSmall
        leftPadding: 0; rightPadding: 0
        font: Theme.fontStrongS
        contentItem: SText {
            text: toggle.text
            font: toggle.font
            color: !toggle.enabled ? Theme.disabled : toggle.checked ? Theme.accent : Theme.muted
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        ToolTip.visible: hovered
        ToolTip.delay: 600
        ToolTip.text: toggle.tip
    }
    component SmallIcon: IconButton {
        implicitWidth: Theme.controlSmall; implicitHeight: Theme.controlSmall
        icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
    }

    ColumnLayout {
        id: rows
        anchors.fill: parent
        anchors.leftMargin: Theme.gap2; anchors.rightMargin: Theme.gap2
        anchors.topMargin: Theme.gap2; anchors.bottomMargin: Theme.gap2
        spacing: Theme.gap1

        // --- Find ---------------------------------------------------------------------
        RowLayout {
            visible: bar.mode === "find"
            spacing: Theme.gap1
            SmallIcon {
                objectName: "replaceToggle"
                iconName: bar.replacing ? "chevron-down" : "chevron-right"
                tip: bar.replacing ? "Hide Replace" : "Replace"
                shortcutHint: bar.replacing ? "" : "Ctrl+H"
                enabled: bar.canReplace
                onClicked: bar.replacing = !bar.replacing
            }
            BarField {
                id: findField
                objectName: "findField"
                placeholderText: "Find"
                Keys.onEscapePressed: bar.close()
                // Tab goes to the replacement (then on through the buttons).
                KeyNavigation.tab: bar.replacing ? replaceField : null
                onTextChanged: if (bar.shown && bar.mode === "find") bar.finder.setQuery(text)
                Keys.onReturnPressed: (event) => event.modifiers & Qt.ShiftModifier
                                      ? bar.finder.findPrevious() : bar.finder.findNext()
                Keys.onEnterPressed: (event) => event.modifiers & Qt.ShiftModifier
                                     ? bar.finder.findPrevious() : bar.finder.findNext()
            }
            Label {
                objectName: "findCount"
                text: bar.finder.countText
                color: bar.finder.noMatch ? Theme.error : Theme.muted
                font: bar.finder.noMatch ? Theme.fontStrongS : Theme.fontTabular
                // Room for "No matches" and "88 of 88", so the buttons stay put.
                Layout.preferredWidth: Math.max(implicitWidth, Theme.px(20))
                Layout.leftMargin: Theme.gap1
            }
            SmallIcon {
                objectName: "findPrevious"
                iconName: "chevron-up"; tip: "Previous match"; shortcutHint: "Shift+F3"
                enabled: bar.finder.count > 0
                onClicked: bar.finder.findPrevious()
            }
            SmallIcon {
                objectName: "findNext"
                iconName: "chevron-down"; tip: "Next match"; shortcutHint: "F3"
                enabled: bar.finder.count > 0
                onClicked: bar.finder.findNext()
            }
            Toggle {
                objectName: "matchCase"
                text: "Aa"; tip: "Match case"
                checked: bar.finder.matchCase
                onToggled: bar.finder.matchCase = checked
            }
            Toggle {
                objectName: "wholeWord"
                text: "W"; tip: "Whole words only"
                checked: bar.finder.wholeWord
                onToggled: bar.finder.wholeWord = checked
            }
            Label {
                objectName: "findNotice"
                text: bar.finder.notice
                color: Theme.muted
                font: Theme.fontS
                Layout.leftMargin: Theme.gap2
            }
            Item { Layout.fillWidth: true }
            SmallIcon {
                objectName: "findClose"
                iconName: "close"; tip: "Close"; shortcutHint: "Esc"
                onClicked: bar.close()
            }
        }
        // --- Replace ------------------------------------------------------------------
        RowLayout {
            visible: bar.mode === "find" && bar.replacing
            spacing: Theme.gap1
            Item { implicitWidth: Theme.controlSmall; implicitHeight: 1 }
            BarField {
                id: replaceField
                objectName: "replaceField"
                placeholderText: "Replace with"
                Keys.onEscapePressed: bar.close()
                KeyNavigation.backtab: findField
                Keys.onReturnPressed: bar.finder.replaceCurrent(replaceField.text)
                Keys.onEnterPressed: bar.finder.replaceCurrent(replaceField.text)
            }
            Button {
                objectName: "replaceOne"
                text: "Replace"
                implicitHeight: Theme.controlSmall
                font: Theme.fontS
                enabled: bar.finder.count > 0
                onClicked: bar.finder.replaceCurrent(replaceField.text)
            }
            Button {
                objectName: "replaceAll"
                text: "Replace all"
                implicitHeight: Theme.controlSmall
                font: Theme.fontS
                enabled: bar.finder.count > 0
                onClicked: bar.finder.replaceAll(replaceField.text)
            }
            Item { Layout.fillWidth: true }
        }
        // --- Go to line ---------------------------------------------------------------
        RowLayout {
            visible: bar.mode === "line"
            spacing: Theme.gap1
            Label {
                text: "Go to line"
                font: Theme.fontS
                color: Theme.muted
                Layout.leftMargin: Theme.gap1
                Layout.rightMargin: Theme.gap1
            }
            BarField {
                id: lineField
                objectName: "goToLineField"
                Layout.preferredWidth: Theme.px(20)
                Keys.onEscapePressed: bar.close()
                validator: IntValidator { bottom: 1 }
                Keys.onReturnPressed: bar.goToLine()
                Keys.onEnterPressed: bar.goToLine()
            }
            Label {
                objectName: "lineCountLabel"
                text: "of " + bar.finder.lineCount
                font: Theme.fontTabular
                color: Theme.muted
            }
            Button {
                objectName: "goToLineButton"
                text: "Go"
                implicitHeight: Theme.controlSmall
                font: Theme.fontS
                enabled: lineField.text !== ""
                onClicked: bar.goToLine()
            }
            Item { Layout.fillWidth: true }
            SmallIcon {
                objectName: "goToLineClose"
                iconName: "close"; tip: "Close"; shortcutHint: "Esc"
                onClicked: bar.close()
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Edit sidebar's chord identifier (the mockup's), through the session's
// IdentifierState (identifier.py, `model`): two octaves of piano scaled to
// the sidebar's width, the typed notes, the candidates.
//
// - A click on a key selects or deselects it (a key that became selected
//   sounds); right-click or Shift+click only plays it. One MouseArea for the
//   whole keyboard: Python hit-tests black keys first (pitfall 6).
// - Selected keys: a white key is lit (the accent at 42% over its white), a
//   black key goes deep accent, so neighbours never read as one block. The
//   edges between white keys are drawn over the fills, black keys over both.
//   The lowest selected note has the bass dot. Keys a chord sounded are amber
//   for the state's 3 s, with "◂ C3" / "D6 ▸" for notes off the keyboard.
// - The notes field takes either notation and commas, re-parsed on every
//   keystroke; a key click rewrites it.
// - Candidates (resolution 1): a click inserts the chord at the caret (the
//   editor gets the focus back), ▶ auditions it, Shift+▶ (or a right click)
//   plays it rolled. From the keyboard: Up/Down, Enter inserts, Space plays.
//   Inserting is off while the editor is read-only; ▶ still plays.
Rectangle {
    id: panel
    objectName: "identifierPanel"
    required property var model
    property bool locked: false
    property string lockedReason
    signal insert(string chord)
    color: Theme.panel

    // The notes field first (Ctrl+Shift+I gives it the focus).
    function focusFirst() { notesField.forceActiveFocus(Qt.TabFocusReason); return true }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.gap2
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.panelHeader
            Label { anchors.verticalCenter: parent.verticalCenter; x: Theme.gap3; text: "Chord identifier"; font: Theme.fontStrong }
        }
        Label {
            objectName: "identifierInstructions"
            Layout.fillWidth: true
            Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
            Layout.topMargin: -Theme.gap2
            text: panel.model.instructions
            wrapMode: Text.Wrap
            font: Theme.fontC
            color: Theme.muted
        }
        Rectangle {
            id: keybed
            Layout.fillWidth: true
            Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
            Layout.preferredHeight: Theme.px(24)
            radius: Theme.radiusSmall
            color: Theme.border
            Item {
                id: piano
                objectName: "piano"
                anchors.fill: parent
                anchors.margins: Theme.hairline
                readonly property var keys: panel.model.keys
                readonly property real ww: width / panel.model.whiteCount
                readonly property real bh: height * panel.model.blackHeight
                readonly property bool roomy: ww > Theme.px(panel.model.notation === "european" ? 6.5 : 5)
                readonly property var selected: panel.model.selected
                readonly property var sounding: panel.model.sounding
                readonly property int bass: panel.model.bass
                readonly property color whiteKey: Theme.dark ? "#e4e6eb" : "#ffffff"
                readonly property color whiteHover: Theme.dark ? "#d8dbe2" : "#eef0f5"
                readonly property color whiteOn: Qt.tint(whiteKey, Theme.alpha(Theme.accentFill, 0.42))
                readonly property color blackKey: "#1a1c21"
                readonly property color blackHover: "#3b4250"
                readonly property color blackOn: Qt.darker(Theme.accentFill, Theme.dark ? 1.05 : 1.25)
                readonly property color keyEdge: Theme.dark ? "#5b5f69" : "#9aa0ad"
                // The keys a chord sounds (Tk's and Android's amber).
                readonly property color soundingFill: "#f5a623"
                readonly property color dotFill: "#ffb74d"
                readonly property color dotEdge: "#9a6200"
                function isOn(midi) { return piano.selected.indexOf(midi) >= 0 }
                function isSounding(midi) { return piano.sounding.indexOf(midi) >= 0 }

                component BassDot: Rectangle {
                    width: Theme.px(1.5); height: width; radius: width / 2
                    color: piano.dotFill
                    border.width: Theme.hairline; border.color: piano.dotEdge
                }

                Repeater {   // the white keys
                    model: piano.keys
                    delegate: Rectangle {
                        id: wk
                        required property var modelData
                        readonly property int midi: modelData.midi
                        readonly property bool on: piano.isOn(midi)
                        readonly property bool sounds: piano.isSounding(midi)
                        objectName: modelData.black ? "" : "key:" + midi
                        visible: !modelData.black
                        x: modelData.left * piano.ww; width: piano.ww - Theme.hairline; height: piano.height
                        radius: Theme.radiusSmall
                        color: wk.sounds ? piano.soundingFill : wk.on ? piano.whiteOn
                             : keys.hoverNote === wk.midi ? piano.whiteHover : piano.whiteKey
                        BassDot {
                            visible: wk.midi === piano.bass
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.px(4.5)
                        }
                        SText {
                            visible: piano.roomy || wk.modelData.isC
                            text: wk.modelData.label
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.px(0.75)
                            font: wk.on ? Theme.fontKeyStrong : Theme.fontKey
                            color: wk.on && !wk.sounds ? "#1d2350" : "#3a3d47"
                        }
                    }
                }
                Repeater {   // the edges between white keys, drawn over the fills
                    model: panel.model.whiteCount - 1
                    delegate: Rectangle {
                        required property int index
                        x: (index + 1) * piano.ww - Theme.hairline; width: Theme.hairline
                        height: piano.height
                        color: piano.keyEdge
                    }
                }
                Repeater {   // the black keys, over both
                    model: piano.keys
                    delegate: Rectangle {
                        id: bk
                        required property var modelData
                        readonly property int midi: modelData.midi
                        readonly property bool on: piano.isOn(midi)
                        readonly property bool sounds: piano.isSounding(midi)
                        objectName: modelData.black ? "key:" + midi : ""
                        visible: modelData.black
                        x: modelData.left * piano.ww; width: modelData.width * piano.ww; height: piano.bh
                        radius: Theme.radiusSmall
                        color: bk.sounds ? piano.soundingFill : bk.on ? piano.blackOn
                             : keys.hoverNote === bk.midi ? piano.blackHover : piano.blackKey
                        border.width: Theme.hairline
                        border.color: bk.sounds ? piano.dotEdge : bk.on ? Qt.lighter(piano.blackOn, 1.5) : "#000000"
                        BassDot {
                            visible: bk.midi === piano.bass
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.px(1)
                        }
                    }
                }
                MouseArea {
                    id: keys
                    objectName: "pianoKeys"
                    property int hoverNote: -1
                    anchors.fill: parent
                    z: 10
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    function noteAt(x, y) { return panel.model.keyAt(x / piano.ww, y / piano.height) }
                    onPositionChanged: (m) => keys.hoverNote = keys.noteAt(m.x, m.y)
                    onExited: keys.hoverNote = -1
                    onClicked: (m) => {
                        var n = keys.noteAt(m.x, m.y)
                        if (n < 0) return
                        if (m.button === Qt.RightButton || (m.modifiers & Qt.ShiftModifier)) panel.model.playKey(n)   // hear it, don't select
                        else panel.model.toggleKey(n)
                    }
                }
            }
        }
        // Sounding notes the piano doesn't show.
        Item {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
            Layout.topMargin: -Theme.gap1
            // One caption line, kept while empty, so the field doesn't jump.
            Layout.preferredHeight: markLine.height
            FontMetrics { id: markLine; font: Theme.fontC }
            Label { objectName: "soundingBelow"; text: panel.model.soundingBelow; font: Theme.fontC; color: Theme.muted }
            Label { objectName: "soundingAbove"; anchors.right: parent.right; text: panel.model.soundingAbove; font: Theme.fontC; color: Theme.muted }
        }
        RowLayout {
            Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
            spacing: Theme.gap1
            TextField {
                id: notesField
                objectName: "notesField"
                Layout.fillWidth: true
                font: Theme.fontMono
                placeholderText: panel.model.placeholder
                Component.onCompleted: text = panel.model.typed
                onTextEdited: panel.model.type(text)
                Keys.onDownPressed: if (list.count > 0) { list.currentIndex = Math.max(0, list.currentIndex); list.forceActiveFocus() }
            }
            IconButton {
                objectName: "identifierClear"
                iconName: "close"; tip: "Clear"
                onClicked: panel.model.clear()
            }
            RollButton {
                objectName: "identifierPlay"
                enabled: panel.model.canPlay
                tip: "Plays the selected keys. Shift+click or right-click plays them rolled, one at a time from the lowest."
                onPlay: (rolled) => panel.model.play(rolled)
            }
        }
        Connections {
            target: panel.model
            function onTypedChanged() { if (notesField.text !== panel.model.typed) notesField.text = panel.model.typed }
        }
        Label {
            objectName: "typedError"
            visible: text !== ""
            Layout.fillWidth: true
            Layout.leftMargin: Theme.gap3; Layout.rightMargin: Theme.gap3
            Layout.topMargin: -Theme.gap1
            text: panel.model.typedError
            wrapMode: Text.Wrap
            font: Theme.fontC
            color: Theme.error
        }
        Label {
            text: "CANDIDATES"
            Layout.leftMargin: Theme.gap3
            Layout.topMargin: Theme.gap1
            font: Theme.fontCaps
            color: Theme.muted
        }
        ListView {
            id: list
            objectName: "candidates"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.gap1; Layout.rightMargin: Theme.gap1
            clip: true
            model: panel.model.candidates
            currentIndex: -1
            keyNavigationEnabled: true
            boundsBehavior: Flickable.StopAtBounds
            onCountChanged: if (list.currentIndex >= list.count) list.currentIndex = list.count - 1
            Keys.onReturnPressed: list.chooseCurrent()
            Keys.onEnterPressed: list.chooseCurrent()
            Keys.onSpacePressed: (e) => { list.hearCurrent((e.modifiers & Qt.ShiftModifier) !== 0) }
            Keys.onUpPressed: { if (list.currentIndex <= 0) notesField.forceActiveFocus(); else list.decrementCurrentIndex() }
            function chooseCurrent() {
                if (list.currentIndex >= 0 && !panel.locked) panel.insert(panel.model.candidates[list.currentIndex])
            }
            function hearCurrent(rolled) {
                if (list.currentIndex >= 0) panel.model.audition(panel.model.candidates[list.currentIndex], rolled)
            }
            delegate: Rectangle {
                id: row
                required property string modelData
                required property int index
                readonly property bool current: ListView.isCurrentItem && list.activeFocus
                objectName: "candidate:" + modelData
                width: ListView.view.width
                height: Theme.listRowHeight
                radius: Theme.radiusSmall
                color: rowArea.pressed && !panel.locked ? Theme.pressed
                     : row.current ? Theme.selectedRow : rowArea.containsMouse ? Theme.hover : "transparent"
                MouseArea {
                    id: rowArea
                    objectName: "candidateArea"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: panel.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
                    onClicked: { list.currentIndex = row.index; if (!panel.locked) panel.insert(row.modelData) }
                }
                ToolTip.visible: rowArea.containsMouse && !hear.hovered
                ToolTip.delay: 900
                ToolTip.text: panel.locked ? panel.lockedReason : "Click to insert at the caret"
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.gap2; anchors.rightMargin: Theme.gap1
                    spacing: Theme.gap2
                    Label {
                        text: row.modelData
                        font: Theme.fontMono
                        color: Theme.chord
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    Label {
                        visible: row.index === 0 && !rowArea.containsMouse && !hear.hovered && !row.current
                        text: "best"; color: Theme.muted; font: Theme.fontS
                    }
                    RollButton {
                        id: hear
                        objectName: "hear:" + row.modelData
                        readonly property bool hovered: hearHover.hovered
                        visible: rowArea.containsMouse || hearHover.hovered || row.current
                        activeFocusOnTab: false
                        tip: "Hear " + row.modelData + ". Shift+click plays it rolled."
                        onPlay: (rolled) => panel.model.audition(row.modelData, rolled)
                        HoverHandler { id: hearHover }
                    }
                }
            }
            Label {
                objectName: "identifierMessage"
                anchors.centerIn: parent
                width: parent.width - 2 * Theme.gap3
                horizontalAlignment: Text.AlignHCenter
                visible: list.count === 0
                text: panel.model.message
                wrapMode: Text.Wrap
                color: Theme.muted; font: Theme.fontS
            }
        }
    }
}

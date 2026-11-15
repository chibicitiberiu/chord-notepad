pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The value picker the ▾ after a directive opens (the mockup's
// ValuePicker.qml, plan step D5). What it offers is the session's
// (`picker` is ValuePickerModel's answer: the kind, `options` from the
// core's pickers.picker_options, `initial` for the boxes), so every value it
// gives is one the Tk Insert dialogs would have taken:
//   key    the 30 keys, majors then minors, in pitch order with twins side by side
//   time   the presets, and beats 1-16 over a unit (the Tk dialog's choices)
//   tempo  the form (120 · +10 · −10 · 50% · 2x · reset) and a box + slider for its number
//          and Tap: tap the beat, the box shows its tempo (ValuePickerModel.tap)
//   capo   box + slider, 0-12
//   loop   the labels above the loop and @start, and a count box (1-16)
// A chip that is a whole value (a key, a time, reset) applies at once;
// numbers apply on Enter or Apply. Escape or a click outside cancels. The
// value is composed in Python (ValuePickerModel.valueFor) and sent as one
// replace_directive_value: one undo step per pick.
//
// Keys: Enter picks the focused chip, Left/Right move between chips, Enter
// in a box applies, Escape closes. The focus starts on the current value's
// chip, else on the box (pitfall 23: only in onOpened).
Popup {
    id: pop
    objectName: "valuePicker"
    required property var model
    property var picker: ({})
    readonly property string kind: picker.kind || ""
    readonly property var options: picker.options || ({})
    readonly property var initial: picker.initial || ({})
    readonly property string current: options.current || ""
    signal picked(string value)
    padding: Theme.gap3
    margins: Theme.gap2          // stay inside the window
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    // Opens for `p` (a fresh body, so the boxes start from its value).
    function openFor(p) {
        picker = ({})
        picker = p
        open()
    }
    function apply(parts) {
        var v = pop.model.valueFor(pop.kind, parts)
        if (v === "") return
        close()
        picked(v)
    }

    contentItem: Loader {
        id: body
        focus: true
        sourceComponent: ({ key: keyBox, time: timeBox, tempo: tempoBox, capo: capoBox,
                            loop: loopBox })[pop.kind] || null
    }

    // --- Shared bits -----------------------------------------------------------------
    component Caption: Label { font: Theme.fontC; color: Theme.muted }
    component Chip: AbstractButton {
        id: chip
        property bool current: false
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        implicitHeight: Theme.controlSmall
        implicitWidth: Math.max(Theme.px(9), lbl.implicitWidth + 2 * Theme.gap2)
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        Keys.onRightPressed: nextItemInFocusChain(true).forceActiveFocus()
        Keys.onLeftPressed: nextItemInFocusChain(false).forceActiveFocus()
        background: Rectangle {
            radius: Theme.radiusSmall
            color: chip.down ? Theme.pressed : chip.current ? Theme.selectedRow
                   : chip.hovered || chip.activeFocus ? Theme.hover : "transparent"
            border.width: chip.activeFocus ? Theme.hairline : 0
            border.color: Theme.accent
        }
        contentItem: SText {
            id: lbl
            text: chip.text
            font: chip.current ? Theme.fontStrong : Theme.font
            color: chip.current ? Theme.accent : Theme.text
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }
    // A chip that takes the focus when the picker opens (the current value's, by default).
    component FocusChip: Chip {
        id: fchip
        property bool focusOnOpen: current
        Connections { target: pop; function onOpened() { if (fchip.focusOnOpen) fchip.forceActiveFocus() } }
    }
    // A number box (`field`: a NumberField) with a slider under it; Enter or Apply applies.
    component NumberRow: ColumnLayout {
        id: nr
        property alias box: sb
        property var field: ({})
        property real value: 0
        property bool takesFocus: true
        property bool canApply: true
        readonly property real from: field.minimum || 0
        readonly property real to: field.maximum === undefined ? 100 : field.maximum
        readonly property real stepSize: field.step || 1
        signal accepted()
        spacing: Theme.gap1
        readonly property real k: 1 / stepSize          // SpinBox is integer: scale by the step (pitfall 20)
        // Set from outside (a chip, Tap) after the box or slider was used:
        // their own value bindings are gone by then, so bind them again.
        onValueChanged: {
            sb.value = Qt.binding(() => Math.round(nr.value * nr.k))
            sl.value = Qt.binding(() => nr.value)
        }
        Connections {
            target: pop
            function onOpened() { if (nr.visible && nr.takesFocus) sb.forceActiveFocus() }
        }
        RowLayout {
            spacing: Theme.gap2
            SpinBox {
                id: sb
                objectName: "pickerBox"
                Layout.preferredWidth: Theme.px(26)
                from: Math.round(nr.from * nr.k); to: Math.round(nr.to * nr.k)
                value: Math.round(nr.value * nr.k)
                validator: RegularExpressionValidator { regularExpression: /[+-]?\d{0,3}([.,]\d{0,2})?/ }
                textFromValue: (v) => String(Math.round(v / nr.k * 100) / 100)
                valueFromText: (t) => Math.round(parseFloat(String(t).replace(",", ".")) * nr.k)
                onValueModified: nr.value = value / nr.k
                // Commit what was typed (clamped), then apply.
                function commit() {
                    var typed = sb.valueFromText((sb.contentItem as TextInput).text, sb.locale)
                    if (!isNaN(typed)) nr.value = Math.max(sb.from, Math.min(sb.to, typed)) / nr.k
                    if (nr.canApply) nr.accepted()
                }
                Keys.onReturnPressed: commit()
                Keys.onEnterPressed: commit()
            }
            Caption { text: nr.field.suffix || ""; visible: text !== "" }
            Item { Layout.fillWidth: true }
            Button {
                objectName: "pickerApply"
                text: "Apply"; highlighted: true; enabled: nr.canApply
                implicitHeight: Theme.controlSmall
                onClicked: nr.accepted()
            }
        }
        Slider {
            id: sl
            Layout.fillWidth: true
            from: nr.from; to: nr.to; stepSize: nr.stepSize; snapMode: Slider.SnapAlways
            value: nr.value
            onMoved: nr.value = value
            Keys.onReturnPressed: if (nr.canApply) nr.accepted()
        }
    }

    // --- Key: compact chips in pitch order from C, enharmonic twins side by
    // side (D♭ then C♯). Arrows follow that order.
    Component {
        id: keyBox
        Column {
            id: kb
            objectName: "keyPicker"
            spacing: Theme.px(0.5)
            readonly property bool anyCurrent: {
                for (var g of pop.options.groups || [])
                    for (var c of g.choices) if (c.value === pop.current) return true
                return false
            }
            Repeater {
                model: pop.options.groups || []
                delegate: Column {
                    id: kg
                    required property var modelData
                    required property int index
                    spacing: Theme.px(0.5)
                    topPadding: kg.index ? Theme.gap1 : 0
                    Caption { text: kg.modelData.title }
                    Flow {
                        width: Theme.px(62)          // rows of about seven
                        spacing: Theme.px(0.5)
                        Repeater {
                            model: kg.modelData.choices
                            delegate: FocusChip {
                                id: keyChip
                                required property var modelData
                                required property int index
                                objectName: "key:" + modelData.value
                                text: modelData.label
                                current: modelData.value === pop.current
                                onClicked: pop.apply({ value: modelData.value })
                                Connections {
                                    target: pop
                                    function onOpened() {
                                        if (!kb.anyCurrent && kg.index === 0 && keyChip.index === 0)
                                            keyChip.forceActiveFocus()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // --- Time: the presets, then beats over a unit -------------------------------------
    Component {
        id: timeBox
        ColumnLayout {
            id: tm
            objectName: "timePicker"
            implicitWidth: Theme.px(62)
            spacing: Theme.gap2
            property int beats: pop.initial.beats || 4
            property int unit: pop.initial.unit || 4
            readonly property var presets: (pop.options.groups || [{ choices: [] }])[0].choices
            readonly property bool presetCurrent: presets.some((c) => c.value === pop.current)
            readonly property var beatsField: (pop.options.numbers || [{}])[0]
            Flow {
                Layout.fillWidth: true
                spacing: Theme.px(0.5)
                Repeater {
                    model: tm.presets
                    delegate: FocusChip {
                        required property var modelData
                        objectName: "time:" + modelData.value
                        text: modelData.label
                        current: modelData.value === pop.current
                        onClicked: pop.apply({ value: modelData.value })
                    }
                }
            }
            Caption { text: tm.beatsField.caption || "" }
            RowLayout {
                spacing: Theme.gap2
                SpinBox {
                    id: beatsBox
                    objectName: "pickerBox"
                    Layout.preferredWidth: Theme.px(20)
                    from: tm.beatsField.minimum || 1; to: tm.beatsField.maximum || 16
                    value: tm.beats
                    onValueModified: tm.beats = value
                    function commit() {
                        var typed = parseInt((beatsBox.contentItem as TextInput).text)
                        if (!isNaN(typed)) tm.beats = Math.max(from, Math.min(to, typed))
                        pop.apply({ beats: tm.beats, unit: tm.unit })
                    }
                    Keys.onReturnPressed: commit()
                    Keys.onEnterPressed: commit()
                    Connections {
                        target: pop
                        function onOpened() { if (!tm.presetCurrent) beatsBox.forceActiveFocus() }
                    }
                }
                Caption { text: "/" }
                Repeater {
                    model: pop.options.units || []
                    delegate: Chip {
                        required property int modelData
                        objectName: "unit:" + modelData
                        implicitWidth: Math.max(Theme.px(6), implicitContentWidth + 2 * Theme.gap1)
                        text: String(modelData)
                        current: modelData === tm.unit
                        onClicked: tm.unit = modelData
                    }
                }
                Item { Layout.fillWidth: true }
                Button {
                    objectName: "pickerApply"
                    text: "Apply"; highlighted: true
                    implicitHeight: Theme.controlSmall
                    onClicked: pop.apply({ beats: tm.beats, unit: tm.unit })
                }
            }
        }
    }

    // --- Tempo: the form, and a number for it -----------------------------------------
    Component {
        id: tempoBox
        ColumnLayout {
            id: tb
            objectName: "tempoPicker"
            spacing: Theme.gap2
            implicitWidth: Theme.px(64)
            property string form: pop.initial.form || "abs"
            property real number: pop.initial.number || 0
            readonly property var group: (pop.options.groups || [{ title: "", choices: [] }])[0]
            readonly property var field: {
                for (var f of pop.options.forms || []) if (f.form === tb.form) return f.number
                return null
            }
            function setForm(choice) {
                if (choice.form === "reset") { pop.apply({ form: "reset" }); return }
                form = choice.form
                number = parseFloat(choice.value.replace(/[x%+]/g, ""))
            }
            // A press of Tap: from the second tap on, the box shows the tempo
            // tapped (an absolute bpm); Apply or Enter writes it.
            function tap() {
                var bpm = pop.model.tap()
                if (bpm <= 0) return
                form = "abs"
                number = bpm
            }
            onNumberChanged: if (tempoRow.value !== number) tempoRow.value = number
            Connections { target: pop; function onOpened() { pop.model.resetTaps() } }
            function chipIsCurrent(choice) {
                if (choice.form !== tb.form) return false
                if (choice.form === "rel") return (choice.value[0] === "-") === (tb.number < 0)
                return true
            }
            Caption { text: tb.group.title }
            Flow {
                Layout.fillWidth: true
                spacing: Theme.px(0.5)
                Repeater {
                    model: tb.group.choices
                    delegate: FocusChip {
                        required property var modelData
                        objectName: "tempo:" + modelData.value
                        text: modelData.label
                        current: tb.chipIsCurrent(modelData)
                        // The box has the focus, unless the value is reset (no box).
                        focusOnOpen: current && modelData.form === "reset"
                        onClicked: tb.setForm(modelData)
                    }
                }
            }
            Caption {
                text: tb.field ? tb.field.caption : ""
                visible: tb.field !== null
            }
            NumberRow {
                id: tempoRow
                Layout.fillWidth: true
                visible: tb.field !== null
                field: tb.field || ({})
                value: tb.number
                onValueChanged: tb.number = value
                onAccepted: pop.apply({ form: tb.form, number: tb.number })
            }
            // Tap: on the press (the beat is when the finger lands), and
            // without taking the focus, so Enter in the box still applies.
            RowLayout {
                spacing: Theme.gap2
                Button {
                    objectName: "pickerTap"
                    Layout.fillWidth: true
                    implicitHeight: Theme.controlHeight
                    text: "Tap"
                    focusPolicy: Qt.NoFocus
                    onPressed: tb.tap()
                }
                Caption {
                    objectName: "pickerTapCount"
                    Layout.preferredWidth: Theme.px(20)
                    readonly property int taps: pop.model.tapCount
                    text: taps === 0 ? "tap the beat" : taps === 1 ? "1 tap" : taps + " taps"
                }
            }
        }
    }

    // --- Capo ------------------------------------------------------------------------------
    Component {
        id: capoBox
        ColumnLayout {
            id: cb
            objectName: "capoPicker"
            implicitWidth: Theme.px(56)
            readonly property var field: (pop.options.numbers || [{}])[0]
            property real fret: pop.initial.fret || 0
            Caption { text: cb.field.caption || "" }
            NumberRow {
                Layout.fillWidth: true
                field: cb.field
                value: cb.fret
                onValueChanged: cb.fret = value
                onAccepted: pop.apply({ fret: Math.round(cb.fret) })
            }
        }
    }

    // --- Loop: the section and the count ------------------------------------------------
    Component {
        id: loopBox
        ColumnLayout {
            id: lb
            objectName: "loopPicker"
            implicitWidth: Theme.px(60)
            spacing: Theme.gap2
            property string label: pop.initial.label || ""
            property int count: pop.initial.count || 2
            readonly property var group: (pop.options.groups || [{ title: "", choices: [] }])[0]
            readonly property var countField: (pop.options.numbers || [{}])[0]
            Caption { text: lb.group.title }
            Flow {
                Layout.fillWidth: true
                spacing: Theme.px(0.5)
                Repeater {
                    model: lb.group.choices
                    delegate: Chip {
                        required property var modelData
                        objectName: "loop:" + modelData.value
                        text: modelData.label
                        current: modelData.value === lb.label
                        onClicked: lb.label = modelData.value
                    }
                }
            }
            Caption { text: lb.countField.caption || "" }
            NumberRow {
                Layout.fillWidth: true
                field: lb.countField
                value: lb.count
                canApply: lb.label !== ""
                onValueChanged: lb.count = Math.round(value)
                onAccepted: pop.apply({ label: lb.label, count: lb.count })
            }
        }
    }
}

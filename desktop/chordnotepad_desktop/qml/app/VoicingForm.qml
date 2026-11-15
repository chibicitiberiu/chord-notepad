pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme
import "FormTips.js" as FormTips

// The parameters of the voicing in the Settings window's form (plan step
// G1), drawn from the core's form schema (settings_forms/voicing_form.py,
// SettingsModel.schema): every section kind, `stack` (fields one under
// another), `grid` (number fields two by two, with a title, a blurb and
// titled sub-grids), `table` (a records field: the ensemble's voices),
// `range_table` (the piano's low/high rows) and `groups` (titled grids side
// by side). Values, marks, hints and messages are the session's
// (VoicingEditorState); edits go to SettingsModel (setField / setCell) and
// the window's Save writes them. The help of each field is
// its tooltip, shared with its caption; a wrong field's tooltip ends with
// "⚠ message" (Tk's voicings page).
//
// A switch (`bool`) is a row of the number grid: its caption in the label
// column and the switch alone at the right, where the number fields end, so
// captions and fields line up down the form. The grid's fields are all one
// width, the ensemble's Voice movement too.
ColumnLayout {
    id: vform
    objectName: "voicingForm"
    required property var settings
    // forms[model] of the schema.
    required property var schemaForm
    property int formWidth: Theme.px(160)
    readonly property var editor: vform.settings.editor
    readonly property var values: vform.editor.values || ({})
    readonly property var errors: vform.editor.field_errors || ({})
    readonly property var hints: vform.editor.hints || ({})
    spacing: Theme.gap1

    function err(id) { return vform.errors[id] || "" }
    // A choice's value as the schema has it (Python's None arrives as null or undefined).
    function choiceIndex(choices, value) {
        var v = value === undefined ? null : value
        return choices.findIndex((c) => (c.value === undefined ? null : c.value) === v)
    }
    function cellPath(field, index, column) {
        return String(field.error_path).replace("{index}", index).replace("{column}", column)
    }

    // --- Pieces ---------------------------------------------------------------------------
    component Caption: Label {
        property string tip: ""
        HoverHandler { id: capHover }
        ToolTip.visible: capHover.hovered && tip !== ""
        ToolTip.delay: 600
        ToolTip.text: FormTips.tip(tip, "")
    }
    component Hint: Label {
        color: Theme.muted; font: Theme.fontS
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.maximumWidth: vform.formWidth
        visible: text !== ""
    }
    component SectionTitle: Label { font: Theme.fontTitleF; Layout.topMargin: Theme.gap4 }

    // One field of a grid, a stack or a range row: the right control for its kind.
    component FieldInput: Item {
        id: fi
        required property var field
        readonly property string kind: fi.field.kind
        implicitWidth: loader.implicitWidth
        implicitHeight: loader.implicitHeight
        Loader {
            id: loader
            // A switch keeps its own width, at the right (where fields end).
            anchors.left: fi.kind === "bool" ? undefined : parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            sourceComponent: fi.kind === "bool" ? boolInput
                             : fi.kind === "choice" ? choiceInput
                             : (fi.kind === "int" || fi.kind === "float") ? numberInput : textInput
        }
        Component {
            id: numberInput
            FormSpin {
                objectName: "field:" + fi.field.id
                shown: vform.values[fi.field.id]
                error: vform.err(fi.field.id)
                tip: fi.field.help || ""
                from: fi.field.min !== undefined ? fi.field.min : -1000000
                to: fi.field.max !== undefined ? fi.field.max : 1000000
                stepSize: fi.field.step || 1
                onEdited: (t) => vform.settings.setField(fi.field.id, t, false)
            }
        }
        Component {
            id: textInput
            FormField {
                objectName: "field:" + fi.field.id
                shown: vform.values[fi.field.id]
                error: vform.err(fi.field.id)
                tip: fi.field.help || ""
                font: fi.kind === "pitch_list" || fi.kind === "pitch" ? Theme.fontMonoS : Theme.font
                onEdited: (t) => vform.settings.setField(fi.field.id, t, false)
            }
        }
        Component {
            id: boolInput
            Switch {
                objectName: "field:" + fi.field.id
                padding: 0
                Accessible.name: fi.field.label
                checked: !!vform.values[fi.field.id]
                onToggled: vform.settings.setField(fi.field.id, checked, true)
                HoverHandler { id: swHover }
                ToolTip.visible: swHover.hovered && fi.field.help
                ToolTip.delay: 600
                ToolTip.text: FormTips.tip(fi.field.help, "")
            }
        }
        Component {
            id: choiceInput
            ComboBox {
                objectName: "field:" + fi.field.id
                model: fi.field.choices.map((c) => c.label)
                currentIndex: vform.choiceIndex(fi.field.choices, vform.values[fi.field.id])
                implicitWidth: Theme.px(56)
                onActivated: (i) => vform.settings.setField(fi.field.id, fi.field.choices[i].value, true)
                HoverHandler { id: cbHover }
                ToolTip.visible: cbHover.hovered && ToolTip.text !== ""
                ToolTip.delay: 600
                ToolTip.text: FormTips.tip(fi.field.help, vform.err(fi.field.id))
            }
        }
    }

    // Fields one under another (a caption beside text and choice fields, the
    // hint under a text field).
    component StackSection: ColumnLayout {
        id: stack
        required property var section
        spacing: Theme.gap1
        Layout.fillWidth: true
        Repeater {
            model: stack.section.fields
            delegate: Loader {
                id: row
                required property var modelData
                Layout.fillWidth: true
                Layout.maximumWidth: vform.formWidth
                Layout.topMargin: Theme.gap2
                sourceComponent: row.modelData.kind === "bool" ? boolRow : fieldRow
                Component {
                    id: fieldRow
                    ColumnLayout {
                        spacing: Theme.px(0.5)
                        Caption {
                            objectName: "caption:" + row.modelData.id
                            text: row.modelData.label
                            tip: row.modelData.help || ""
                            font: Theme.fontMedium
                        }
                        FieldInput {
                            field: row.modelData
                            Layout.fillWidth: row.modelData.kind !== "choice"
                        }
                        Hint { text: vform.hints[row.modelData.id] || "" }
                    }
                }
                Component {
                    id: boolRow
                    FieldGrid { fields: [row.modelData] }
                }
            }
        }
    }

    // Number fields two by two: caption, then the field (a switch too, at
    // the right). An odd last cell keeps its column's width.
    component FieldGrid: GridLayout {
        id: grid
        required property var fields
        columns: 2
        columnSpacing: Theme.gap6
        rowSpacing: Theme.gap1
        uniformCellWidths: true
        Layout.fillWidth: true
        Layout.maximumWidth: vform.formWidth
        Repeater {
            model: grid.fields
            delegate: RowLayout {
                id: cell
                required property var modelData
                spacing: Theme.gap2
                Layout.fillWidth: true
                Layout.minimumHeight: Theme.controlHeight
                Caption {
                    objectName: "caption:" + cell.modelData.id
                    text: cell.modelData.label
                    tip: cell.modelData.help || ""
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                FieldInput {
                    field: cell.modelData
                    Layout.preferredWidth: cell.modelData.kind === "bool" ? implicitWidth : Theme.px(22)
                }
            }
        }
        Repeater {
            model: grid.fields.length % 2
            delegate: Item { Layout.fillWidth: true }
        }
    }

    component GridSection: ColumnLayout {
        id: gs
        required property var section
        spacing: Theme.gap1
        Layout.fillWidth: true
        Layout.topMargin: Theme.gap2
        SectionTitle { text: gs.section.title || ""; visible: !!gs.section.title }
        Hint { text: gs.section.blurb || "" }
        FieldGrid { fields: gs.section.fields || []; Layout.topMargin: Theme.gap1 }
        Repeater {
            model: gs.section.groups || []
            delegate: ColumnLayout {
                id: sub
                required property var modelData
                Layout.fillWidth: true
                Layout.topMargin: Theme.gap2
                Label { text: sub.modelData.title; font: Theme.fontStrong }
                FieldGrid { fields: sub.modelData.fields }
            }
        }
    }

    // Titled grids side by side (the ensemble's doubling, omission, inversion).
    component GroupsSection: GridLayout {
        id: gr
        required property var section
        columns: 2
        columnSpacing: Theme.gap6
        rowSpacing: Theme.gap3
        uniformCellWidths: true
        Repeater {
            model: gr.section.groups
            delegate: ColumnLayout {
                id: group
                required property var modelData
                spacing: Theme.gap1
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Label { text: group.modelData.title; font: Theme.fontStrong }
                Repeater {
                    model: group.modelData.fields
                    delegate: RowLayout {
                        id: gcell
                        required property var modelData
                        Layout.fillWidth: true
                        Caption { text: gcell.modelData.label; tip: gcell.modelData.help || ""; Layout.fillWidth: true; elide: Text.ElideRight }
                        FieldInput { field: gcell.modelData; Layout.preferredWidth: Theme.px(22) }
                    }
                }
            }
        }
    }

    // The piano's rows of (low, high) pitches.
    component RangeTableSection: ColumnLayout {
        id: rt
        required property var section
        spacing: Theme.gap1
        Layout.fillWidth: true
        SectionTitle { text: rt.section.title || ""; visible: !!rt.section.title }
        GridLayout {
            columns: 3
            columnSpacing: Theme.gap3
            rowSpacing: Theme.gap1
            Layout.maximumWidth: vform.formWidth
            Item { implicitWidth: 1; implicitHeight: 1 }
            Repeater {
                model: rt.section.columns
                delegate: Label { required property string modelData; text: modelData; font: Theme.fontStrongS; color: Theme.muted }
            }
            Repeater {
                model: rt.section.rows
                delegate: Caption {
                    required property var modelData
                    required property int index
                    text: modelData.label
                    tip: modelData.help || ""
                    Layout.row: index + 1
                    Layout.column: 0
                    Layout.preferredWidth: Theme.px(44)
                }
            }
            Repeater {
                model: rt.section.rows.length * 2
                delegate: FieldInput {
                    required property int index
                    field: rt.section.rows[Math.floor(index / 2)].fields[index % 2]
                    Layout.row: Math.floor(index / 2) + 1
                    Layout.column: index % 2 + 1
                    Layout.preferredWidth: Theme.px(26)
                }
            }
        }
    }

    // A records field as a table (the ensemble's voices): ↑ ↓ ✕ per row and
    // Add voice; a column with disabled_in_last_row (the gap to the next
    // voice) is off in the last row.
    component TableSection: ColumnLayout {
        id: table
        required property var section
        readonly property var field: table.section.fields[0]
        readonly property var rows: vform.values[table.field.id] || []
        spacing: Theme.gap1
        Layout.fillWidth: true
        SectionTitle { text: table.section.title || "" }
        GridLayout {
            id: cells
            objectName: "recordsTable"
            columns: table.field.columns.length + 3
            columnSpacing: Theme.gap2
            rowSpacing: Theme.gap1
            Repeater {
                model: table.field.columns
                delegate: Caption {
                    required property var modelData
                    required property int index
                    text: modelData.label
                    tip: modelData.help || ""
                    font: Theme.fontStrongS
                    color: Theme.muted
                    wrapMode: Text.Wrap
                    Layout.maximumWidth: Theme.px(2 * (modelData.width || 8) + 4)
                    Layout.alignment: Qt.AlignBottom
                    Layout.row: 0
                    Layout.column: index
                }
            }
            Repeater {
                model: table.rows.length * table.field.columns.length
                delegate: Item {
                    id: tc
                    required property int index
                    readonly property int row: Math.floor(index / table.field.columns.length)
                    readonly property var column: table.field.columns[index % table.field.columns.length]
                    readonly property bool off: tc.column.disabled_in_last_row === true && tc.row === table.rows.length - 1
                    readonly property var record: table.rows[tc.row] || ({})
                    readonly property string path: vform.cellPath(table.field, tc.row, tc.column.id)
                    Layout.row: tc.row + 1
                    Layout.column: index % table.field.columns.length
                    Layout.preferredWidth: Theme.px(2 * (tc.column.width || 8) + 4)
                    implicitHeight: Theme.controlHeight
                    Loader {
                        anchors.fill: parent
                        sourceComponent: tc.column.kind === "choice" ? cellChoice
                                         : tc.column.kind === "int" ? cellNumber : cellText
                    }
                    Component {
                        id: cellText
                        FormField {
                            objectName: "cell:" + tc.path
                            shown: tc.record[tc.column.id]
                            error: tc.column.kind === "text" ? "" : vform.err(tc.path)
                            tip: tc.column.help || ""
                            font: tc.column.kind === "pitch" ? Theme.fontMonoS : Theme.font
                            onEdited: (t) => vform.settings.setCell(table.field.id, tc.row, tc.column.id, t, false)
                        }
                    }
                    Component {
                        id: cellNumber
                        FormSpin {
                            objectName: "cell:" + tc.path
                            enabled: !tc.off
                            shown: tc.off ? "" : tc.record[tc.column.id]
                            error: tc.off ? "" : vform.err(tc.path)
                            tip: tc.column.help || ""
                            from: tc.column.min; to: tc.column.max; stepSize: tc.column.step || 1
                            onEdited: (t) => vform.settings.setCell(table.field.id, tc.row, tc.column.id, t, false)
                        }
                    }
                    Component {
                        id: cellChoice
                        ComboBox {
                            objectName: "cell:" + tc.path
                            model: tc.column.choices.map((c) => c.label)
                            currentIndex: vform.choiceIndex(tc.column.choices, tc.record[tc.column.id])
                            onActivated: (i) => vform.settings.setCell(table.field.id, tc.row, tc.column.id, tc.column.choices[i].value, true)
                            HoverHandler { id: chHover }
                            ToolTip.visible: chHover.hovered && ToolTip.text !== ""
                            ToolTip.delay: 600
                            ToolTip.text: FormTips.tip(tc.column.help, vform.err(tc.path))
                        }
                    }
                }
            }
            // ↑ ↓ ✕ of each row.
            Repeater {
                model: table.rows.length * 3
                delegate: IconButton {
                    required property int index
                    readonly property int row: Math.floor(index / 3)
                    readonly property int which: index % 3
                    objectName: ["moveUp", "moveDown", "removeRow"][which] + ":" + row
                    Layout.row: row + 1
                    Layout.column: table.field.columns.length + which
                    iconName: ["chevron-up", "chevron-down", "close"][which]
                    text: [table.field.move_up_label, table.field.move_down_label, table.field.remove_label][which]
                    tip: [table.field.move_up_help, table.field.move_down_help, table.field.remove_help][which]
                    Accessible.name: tip
                    enabled: which === 0 ? row > 0 : which === 1 ? row < table.rows.length - 1 : true
                    onClicked: {
                        if (which === 2) vform.settings.removeRecord(row, table.field.id)
                        else vform.settings.moveRecord(row, which === 0 ? -1 : 1, table.field.id)
                    }
                }
            }
        }
        Button {
            objectName: "addRecord"
            text: table.field.add_label
            icon.source: Theme.iconUrl("plus")
            Layout.topMargin: Theme.gap1
            onClicked: vform.settings.addRecord(table.field.id)
            HoverHandler { id: addHover }
            ToolTip.visible: addHover.hovered
            ToolTip.delay: 600
            ToolTip.text: FormTips.tip(table.field.add_help, "")
        }
    }

    // --- The sections, in the schema's order --------------------------------------------
    Repeater {
        model: vform.schemaForm ? vform.schemaForm.sections : []
        delegate: ColumnLayout {
            id: sec
            required property var modelData
            Layout.fillWidth: true
            spacing: 0
            Loader {
                Layout.fillWidth: true
                active: sec.modelData.kind === "stack"
                visible: active
                sourceComponent: StackSection { section: sec.modelData }
            }
            Loader {
                Layout.fillWidth: true
                active: sec.modelData.kind === "grid"
                visible: active
                sourceComponent: GridSection { section: sec.modelData }
            }
            Loader {
                Layout.fillWidth: true
                // On the Loader: a margin or a width limit set inside its item is lost.
                Layout.maximumWidth: vform.formWidth
                Layout.topMargin: Theme.gap3
                active: sec.modelData.kind === "groups"
                visible: active
                sourceComponent: GroupsSection { section: sec.modelData }
            }
            Loader {
                Layout.fillWidth: true
                active: sec.modelData.kind === "range_table"
                visible: active
                sourceComponent: RangeTableSection { section: sec.modelData }
            }
            Loader {
                Layout.fillWidth: true
                active: sec.modelData.kind === "table"
                visible: active
                sourceComponent: TableSection { section: sec.modelData }
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme
import "FormTips.js" as FormTips

// Settings › Voicings (plan step G1), the mockup's layout: the voicings by
// model on the left (Fretboard, Piano, Ensemble, sorted; the session's
// VoicingEditorState.groups) under [+ Add voicing | 🗑], the selected one's
// form on the right: name and model, the error banner and the parameters
// (VoicingForm). With nothing selected, the placeholder. Texts and help come
// from the schema (voicing_texts.py).
//
// Add voicing opens a menu of what the new voicing starts as: the built-in
// presets and the user's voicings (Tibi, 2026-11-15: the copy is wanted
// right after adding, so Android's separate Copy from existing went into
// it). The trash button removes the selected voicing.
//
// It asks before removing a voicing and before switching the model of an
// edited one (`confirm`, the window's ConfirmDialog); a refused name comes
// back as the session's UserError ("Rename Voicing"), shown over the
// Settings window.
RowLayout {
    id: page
    objectName: "voicingsPage"
    required property var settings
    // confirm(title, message, actionText, onYes): the window's question.
    required property var confirm
    property int formWidth: Theme.px(160)
    readonly property var editor: page.settings.editor
    readonly property var schema: page.settings.schema
    readonly property var texts: page.schema ? page.schema.texts : ({})
    readonly property var help: page.schema ? page.schema.help : ({})
    readonly property string selected: page.editor.selected || ""
    readonly property var models: page.schema ? page.schema.models : []
    spacing: 0

    component GroupLabel: Label { font: Theme.fontS; color: Theme.muted; Layout.topMargin: Theme.gap3; Layout.leftMargin: Theme.gap2 }
    component FieldLabel: Label {
        property string tip: ""
        font: Theme.fontMedium
        Layout.topMargin: Theme.gap2
        HoverHandler { id: flHover }
        ToolTip.visible: flHover.hovered && tip !== ""
        ToolTip.delay: 600
        ToolTip.text: FormTips.tip(tip, "")
    }

    function askRemove(name) {
        page.confirm(page.texts.remove_confirm_title,
                     String(page.texts.remove_confirm).replace("{name}", name), "Remove",
                     () => page.settings.removeVoicing(name))
    }
    function askModel(model) {
        if (model === page.editor.model) return
        if (page.editor.dirty)
            page.confirm(page.texts.model_confirm_title, page.texts.model_confirm, "Switch model",
                         () => page.settings.setModel(model))
        else
            page.settings.setModel(model)
    }
    // Every edit command moves the revision, a refused rename too: the name
    // field goes back to the voicing's name then. The new name too: the
    // revision can arrive before it, and leaving the field would then rename
    // the voicing back.
    readonly property int revision: page.editor.revision || 0
    function resetName() { nameField.text = page.selected; nameField.tried = null }
    onRevisionChanged: page.resetName()
    onSelectedChanged: page.resetName()

    // Add voicing's menu: the presets, a separator between groups. Built on
    // each opening; a Menu has no Repeater (pitfall 7). `const`, not `var`:
    // each row's handler keeps its own preset.
    Component { id: presetItem; MenuItem { property string group } }
    Component { id: presetSeparator; MenuSeparator { } }
    function fillAddMenu() {
        while (addMenu.count > 0) addMenu.takeItem(0).destroy()
        var last = null
        for (const p of page.settings.addPresets()) {
            if (last !== null && p.group !== last) addMenu.addItem(presetSeparator.createObject(addMenu.contentItem))
            last = p.group
            const item = presetItem.createObject(addMenu.contentItem, { text: p.label, group: p.group })
            item.triggered.connect(() => page.settings.addVoicingFrom(item.group, item.text))
            addMenu.addItem(item)
        }
    }

    // --- The voicings ------------------------------------------------------------------
    Rectangle {
        Layout.fillHeight: true
        Layout.preferredWidth: Theme.px(56)
        color: Theme.base
        Rectangle { anchors.right: parent.right; width: Theme.hairline; height: parent.height; color: Theme.border }
        ScrollView {
            anchors.fill: parent
            anchors.rightMargin: Theme.hairline
            contentWidth: availableWidth
            ColumnLayout {
                x: Theme.gap3
                width: parent.width - 2 * Theme.gap3
                spacing: Theme.px(0.5)
                RowLayout {
                    Layout.topMargin: Theme.gap3
                    Layout.fillWidth: true
                    spacing: Theme.px(0.5)
                    Button {
                        id: addButton
                        objectName: "addVoicing"
                        text: "Add voicing"
                        icon.source: Theme.iconUrl("plus")
                        Layout.fillWidth: true
                        onClicked: { page.fillAddMenu(); addMenu.popup(addButton, 0, addButton.height) }
                        HoverHandler { id: addHover }
                        ToolTip.visible: addHover.hovered && !addMenu.visible
                        ToolTip.delay: 600
                        ToolTip.text: FormTips.tip(page.help.tree_add, "")
                        Menu {
                            id: addMenu
                            objectName: "addVoicingMenu"
                        }
                    }
                    Button {
                        objectName: "removeVoicing"
                        icon.source: Theme.iconUrl("trash-can-outline")
                        display: AbstractButton.IconOnly
                        leftPadding: 0; rightPadding: 0
                        Layout.preferredWidth: Theme.controlHeight
                        enabled: page.selected !== ""
                        onClicked: page.askRemove(page.selected)
                        HoverHandler { id: removeHover }
                        ToolTip.visible: removeHover.hovered
                        ToolTip.delay: 600
                        ToolTip.text: FormTips.tip(page.help.tree_remove, "")
                    }
                }
                Repeater {
                    model: page.editor.groups || []
                    delegate: ColumnLayout {
                        id: group
                        required property var modelData
                        spacing: Theme.px(0.5)
                        Layout.fillWidth: true
                        GroupLabel { text: group.modelData.label; font: Theme.fontStrongS }
                        Label {
                            visible: group.modelData.names.length === 0
                            text: "No voicings"
                            color: Theme.disabled; font: Theme.fontS
                            Layout.leftMargin: Theme.gap3
                        }
                        Repeater {
                            model: group.modelData.names
                            delegate: ItemDelegate {
                                id: entry
                                required property string modelData
                                objectName: "voicing:" + modelData
                                text: modelData
                                highlighted: modelData === page.selected
                                Layout.fillWidth: true
                                // A voicing with a wrong value shows it (VoicingEditorState.invalid).
                                contentItem: Label {
                                    text: entry.text
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                    color: (page.editor.invalid || []).indexOf(entry.modelData) >= 0 ? Theme.error : Theme.text
                                    font: entry.highlighted ? Theme.fontMedium : Theme.font
                                }
                                onClicked: page.settings.selectVoicing(modelData)
                            }
                        }
                    }
                }
                Item { implicitHeight: Theme.gap3 }
            }
        }
    }

    // --- The selected voicing -------------------------------------------------------------
    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Label {
            objectName: "voicingPlaceholder"
            visible: page.selected === ""
            x: Theme.gap6; y: Theme.gap6
            width: parent.width - 2 * Theme.gap6
            text: page.texts.placeholder || ""
            color: Theme.muted
            wrapMode: Text.Wrap
        }
        ScrollView {
            id: formScroll
            anchors.fill: parent
            visible: page.selected !== ""
            contentWidth: availableWidth
            ColumnLayout {
                x: Theme.gap6
                width: parent.width - 2 * Theme.gap6
                spacing: Theme.gap1
                Item { implicitHeight: Theme.gap3 }
                RowLayout {
                    spacing: Theme.gap4
                    Layout.maximumWidth: page.formWidth
                    ColumnLayout {
                        Layout.fillWidth: true
                        FieldLabel { text: "Name"; tip: page.help.name || "" }
                        FormField {
                            id: nameField
                            objectName: "voicingName"
                            shown: page.selected
                            tip: page.help.name || ""
                            Layout.fillWidth: true
                            // Enter, then leaving the field for the error dialog,
                            // would send the same refused name twice.
                            property var tried: null
                            onCommitted: {
                                if (nameField.text === page.selected || nameField.text === nameField.tried) return
                                nameField.tried = nameField.text
                                page.settings.renameVoicing(page.selected, nameField.text)
                            }
                        }
                    }
                    ColumnLayout {
                        FieldLabel { text: "Model"; tip: page.help.model || "" }
                        ComboBox {
                            id: modelBox
                            objectName: "voicingModel"
                            model: page.models.map((m) => m.label)
                            currentIndex: page.models.findIndex((m) => m.value === page.editor.model)
                            Layout.preferredWidth: Theme.px(36)
                            onActivated: (i) => {
                                // Back to the voicing's model until the session says otherwise.
                                modelBox.currentIndex = Qt.binding(() => page.models.findIndex((m) => m.value === page.editor.model))
                                page.askModel(page.models[i].value)
                            }
                            HoverHandler { id: modelHover }
                            ToolTip.visible: modelHover.hovered
                            ToolTip.delay: 600
                            ToolTip.text: FormTips.tip(page.help.model, "")
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.maximumWidth: page.formWidth
                    implicitHeight: Theme.hairline; color: Theme.border
                    Layout.topMargin: Theme.gap3; Layout.bottomMargin: Theme.gap1
                }
                // The banner: the voicing has something wrong (a field, or the
                // spec's message when no field is to blame).
                Rectangle {
                    objectName: "voicingErrors"
                    readonly property var formErrors: page.editor.form_errors || []
                    readonly property bool shown: Object.keys(page.editor.field_errors || {}).length > 0
                                                  || formErrors.length > 0
                    visible: shown
                    Layout.fillWidth: true; Layout.maximumWidth: page.formWidth
                    implicitHeight: bannerText.implicitHeight + 2 * Theme.gap2
                    radius: Theme.radius
                    color: Theme.alpha(Theme.error, Theme.dark ? 0.16 : 0.09)
                    border.width: Theme.hairline
                    border.color: Theme.alpha(Theme.error, 0.5)
                    Label {
                        id: bannerText
                        objectName: "voicingErrorsText"
                        x: Theme.gap3; y: Theme.gap2
                        width: parent.width - 2 * Theme.gap3
                        text: [page.texts.errors_banner].concat(parent.formErrors).join("\n")
                        color: Theme.error
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                    }
                }
                VoicingForm {
                    settings: page.settings
                    schemaForm: page.schema && page.editor.model ? page.schema.forms[page.editor.model] : null
                    formWidth: page.formWidth
                    Layout.fillWidth: true
                }
                Item { implicitHeight: Theme.gap6 }
            }
        }
    }
}

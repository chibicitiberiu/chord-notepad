pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import CNTheme
import "FormTips.js" as FormTips

// The Settings window (plan step G1), the mockup's: its own window with a
// page list on the left (General, Playback & audio, Voicings). It saves as
// you go (parity checklist resolution 6): no Save or Cancel, a wrong value
// is marked and the saved one stays in use (Q8). `settings` is the
// SettingsModel (settings_window.py): show() opens the session's settings
// edit, closing it (Close, Escape, the title bar) saves what waits and ends
// it, after asking when something wrong isn't saved.
//
// What applies at once (font, word wrap, the notation of a song still on the
// defaults, the Voicing menus, the active voicing) is the session's
// apply_settings; the defaults (tempo, key, time, audio, log level) count
// from the next New or Open, or the next start, as the hints say.
ApplicationWindow {
    id: win
    objectName: "settingsWindow"
    required property var settings
    // The error presenter: errors raised from here (a refused name) show over this window.
    required property var errors
    property string page: "general"
    readonly property var values: win.settings.values
    readonly property var limits: win.settings.limits
    readonly property var numberTexts: win.settings.numberTexts
    readonly property var numberErrors: win.settings.numberErrors
    readonly property int formWidth: Theme.px(160)
    // Tk's restart hint (options_dialog.py RESTART_HINT).
    readonly property string restartHint: "Takes effect after restart."

    title: "Settings - Chord Notepad"
    width: Theme.px(275); height: Theme.px(185)
    minimumWidth: Theme.px(200); minimumHeight: Theme.px(130)
    color: Theme.base
    visible: false
    onVisibleChanged: if (visible) Theme.bumpLayout()
    onWidthChanged: Theme.bumpLayout()
    onHeightChanged: Theme.bumpLayout()

    function showPage(p) {
        if (p) win.page = p
        var wasShown = win.visible
        win.settings.open()
        win.show()
        // Already open behind the main window: bring it up (the offscreen
        // platform of the tests can't, and says so).
        if (wasShown && Qt.platform.pluginName !== "offscreen") win.raise()
        win.requestActivate()
    }
    // Close: ask first while something wrong isn't saved (Android's
    // "Some values aren't saved"), else save what waits and end the edit.
    function requestClose() {
        if (win.settings.hasProblems) problemsDlg.open()
        else win.finish()
    }
    function finish() {
        win.settings.close()
        win.hide()
    }
    onClosing: (close) => { close.accepted = false; win.requestClose() }
    // Edit (the problems dialog): go to the first wrong value.
    function editProblems() {
        var numbers = Object.keys(win.numberErrors)
        if (numbers.length > 0) {
            win.page = (numbers[0] === "bpm" || numbers[0] === "time_signature_beats") ? "playback" : "general"
            return
        }
        var problems = win.settings.editor.problems || []
        if (problems.length > 0) {
            win.page = "voicings"
            if (problems[0].voicing !== win.settings.editor.selected) win.settings.selectVoicing(problems[0].voicing)
        }
    }

    // An error to show over this window (AppDialogs routes them here while it's in use).
    function showError(title, message) { errorDlg.show(title, message) }

    // A question before a change: confirm(title, message, actionText, onYes).
    function confirm(title, message, actionText, onYes) {
        confirmDlg.title = title
        confirmDlg.message = message
        confirmDlg.actionText = actionText
        confirmDlg.yes = onYes
        confirmDlg.open()
    }

    component FieldLabel: Label {
        property string tip: ""
        font: Theme.fontMedium
        Layout.topMargin: Theme.gap2
        HoverHandler { id: flHover }
        ToolTip.visible: flHover.hovered && tip !== ""
        ToolTip.delay: 600
        ToolTip.text: FormTips.tip(tip, "")
    }
    component Help: Label {
        color: Theme.muted; font: Theme.fontS
        wrapMode: Text.Wrap
        Layout.fillWidth: true
        Layout.maximumWidth: win.formWidth
    }
    component ErrorText: Label {
        color: Theme.error; font: Theme.fontS
        wrapMode: Text.Wrap
        visible: text !== ""
        Layout.fillWidth: true
        Layout.maximumWidth: win.formWidth
    }
    component SwitchRow: RowLayout {
        id: sr
        property alias title: t.text
        property alias help: h.text
        property alias checked: sw.checked
        property alias control: sw
        signal toggled(bool checked)
        Layout.preferredWidth: win.formWidth
        Layout.maximumWidth: win.formWidth
        Layout.topMargin: Theme.gap2
        spacing: Theme.gap4
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 0
            spacing: Theme.px(0.5)
            Label { id: t; font: Theme.fontMedium; Layout.fillWidth: true; wrapMode: Text.Wrap }
            Help { id: h; visible: text !== "" }
            // The title and help switch it too, like a label.
            TapHandler { onTapped: { sw.toggle(); sr.toggled(sw.checked) } }
        }
        Switch { id: sw; onToggled: sr.toggled(sw.checked) }
    }
    component SectionTitle: Label { font: Theme.fontTitleF; Layout.topMargin: Theme.gap4 }
    component PageTitle: Label { font: Theme.fontHeadF; Layout.topMargin: Theme.gap6; Layout.bottomMargin: Theme.gap1 }
    // A whole-number setting: kept as typed; a wrong one is marked and not saved.
    component NumberSetting: FormSpin {
        id: ns
        required property string setting
        objectName: "setting:" + setting
        shown: win.numberTexts[ns.setting] !== undefined ? win.numberTexts[ns.setting] : win.values[ns.setting]
        error: win.numberErrors[ns.setting] || ""
        from: (win.limits[ns.setting] || [0, 0])[0]
        to: (win.limits[ns.setting] || [0, 0])[1]
        onEdited: (t) => win.settings.setNumber(ns.setting, t, false)
        onCommitted: win.settings.setNumber(ns.setting, ns.text, true)
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        // Escape closes the window, like every dialog (Q12). Here, so an open
        // popup (a combo box's list, a question) takes it first.
        focus: true
        Keys.onEscapePressed: win.requestClose()

        // --- Page list ----------------------------------------------------------
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: Theme.px(58)
            color: Theme.panel
            Rectangle { anchors.right: parent.right; width: Theme.hairline; height: parent.height; color: Theme.border }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.gap2
                anchors.rightMargin: Theme.gap2 + Theme.hairline
                spacing: Theme.px(0.5)
                Label { text: "Settings"; font: Theme.fontTitleF; Layout.margins: Theme.gap2; Layout.bottomMargin: Theme.gap3 }
                Repeater {
                    model: [["general", "General", "Font, wrap, notation, key, theme"],
                            ["playback", "Playback & audio", "Default tempo, soundfont, driver"],
                            ["voicings", "Voicings", "Your fretboard, piano and ensemble voicings"]]
                    delegate: ItemDelegate {
                        id: navItem
                        required property var modelData
                        objectName: "page:" + modelData[0]
                        Layout.fillWidth: true
                        highlighted: win.page === modelData[0]
                        onClicked: win.page = modelData[0]
                        topPadding: Theme.gap2; bottomPadding: Theme.gap2
                        contentItem: ColumnLayout {
                            spacing: Theme.px(0.25)
                            Label { text: navItem.modelData[1]; font: Theme.fontMedium; Layout.fillWidth: true }
                            Label { text: navItem.modelData[2]; color: Theme.muted; font: Theme.fontS
                                    wrapMode: Text.Wrap; Layout.fillWidth: true }
                        }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            // Wrong values kept from last time (the app went away before they
            // were fixed): Android's banner, with Discard.
            Rectangle {
                objectName: "restoredBanner"
                visible: win.settings.editor.restored === true
                Layout.fillWidth: true
                implicitHeight: restoredRow.implicitHeight + 2 * Theme.gap2
                color: Theme.alpha(Theme.error, Theme.dark ? 0.16 : 0.09)
                RowLayout {
                    id: restoredRow
                    anchors.fill: parent
                    anchors.leftMargin: Theme.gap4; anchors.rightMargin: Theme.gap4
                    Label {
                        text: "Some values you typed last time have mistakes and weren't saved. They're back in their fields: fix them, or discard them."
                        color: Theme.text; wrapMode: Text.Wrap; Layout.fillWidth: true
                    }
                    Button { text: "Discard"; onClicked: win.settings.discardProblems() }
                }
            }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: ["general", "playback", "voicings"].indexOf(win.page)

                // General ------------------------------------------------------
                ScrollView {
                    objectName: "generalPage"
                    contentWidth: availableWidth
                    ColumnLayout {
                        x: Theme.gap6; width: parent.width - 2 * Theme.gap6
                        spacing: Theme.gap1
                        PageTitle { text: "General" }
                        SectionTitle { text: "Editor" }
                        RowLayout {
                            spacing: Theme.gap4
                            ColumnLayout {
                                FieldLabel { text: "Font" }
                                ComboBox {
                                    objectName: "setting:font_family"
                                    model: win.settings.fontFamilies
                                    currentIndex: win.settings.fontFamilies.indexOf(win.settings.fontFamily)
                                    Layout.preferredWidth: Theme.px(60)
                                    onActivated: (i) => win.settings.setValue("font_family", win.settings.fontFamilies[i])
                                }
                            }
                            ColumnLayout {
                                FieldLabel { text: "Size (pt)" }
                                NumberSetting { setting: "font_size"; Layout.preferredWidth: Theme.px(22) }
                            }
                        }
                        ErrorText { text: win.numberErrors.font_size || "" }
                        Help { text: "A monospace font keeps chords over their lyrics. Ctrl+= and Ctrl+- change the size too." }
                        SwitchRow {
                            objectName: "setting:word_wrap"
                            title: "Word wrap"
                            help: "Off: long lines scroll sideways, so chords stay over their lyrics."
                            checked: !!win.values.word_wrap
                            onToggled: (on) => win.settings.setValue("word_wrap", on)
                        }
                        SectionTitle { text: "Chords" }
                        FieldLabel { text: "Chord notation" }
                        RowLayout {
                            spacing: Theme.gap4
                            RadioButton {
                                objectName: "setting:notation:american"
                                text: "American (C, D, E…)"
                                checked: win.values.notation !== "european"
                                onToggled: if (checked) win.settings.setValue("notation", "american")
                            }
                            RadioButton {
                                objectName: "setting:notation:european"
                                text: "European (Do, Re, Mi…)"
                                checked: win.values.notation === "european"
                                onToggled: if (checked) win.settings.setValue("notation", "european")
                            }
                        }
                        Help { text: "How new songs are read. An opened song starts in the notation its chords use; AB | Do in the toolbar switches only that song." }
                        FieldLabel { text: "Default key" }
                        ComboBox {
                            objectName: "setting:key"
                            model: win.settings.keyChoices.map((k) => k.label)
                            currentIndex: win.settings.keyChoices.findIndex((k) => k.value === (win.values.key || ""))
                            Layout.preferredWidth: Theme.px(26)
                            onActivated: (i) => win.settings.setValue("key", win.settings.keyChoices[i].value)
                        }
                        Help { text: "The key a new song starts in." }
                        SectionTitle { text: "Appearance and startup" }
                        FieldLabel { text: "Theme" }
                        ComboBox {
                            objectName: "setting:ui_theme"
                            model: win.settings.choices.themes.map((t) => t.label)
                            currentIndex: win.settings.choices.themes.findIndex((t) => t.value === win.values.ui_theme)
                            Layout.preferredWidth: Theme.px(45)
                            onActivated: (i) => win.settings.setValue("ui_theme", win.settings.choices.themes[i].value)
                        }
                        Help { text: "Desktop only; Android follows the system." }
                        SwitchRow {
                            objectName: "setting:show_quick_start_on_startup"
                            title: "Show quick start at startup"
                            help: "Whether the quick-start tour (also in Help › Quick start) opens when Chord Notepad starts."
                            checked: !!win.values.show_quick_start_on_startup
                            onToggled: (on) => win.settings.setValue("show_quick_start_on_startup", on)
                        }
                        FieldLabel { text: "Recent files" }
                        NumberSetting { setting: "max_recent_files"; Layout.preferredWidth: Theme.px(22) }
                        ErrorText { text: win.numberErrors.max_recent_files || "" }
                        Help { text: "How many songs File › Open recent remembers." }
                        FieldLabel { text: "Log level" }
                        ComboBox {
                            objectName: "setting:log_level"
                            model: win.settings.choices.logLevels
                            currentIndex: win.settings.choices.logLevels.indexOf(win.values.log_level)
                            Layout.preferredWidth: Theme.px(30)
                            onActivated: (i) => win.settings.setValue("log_level", win.settings.choices.logLevels[i])
                        }
                        Help { text: win.restartHint }
                        Item { implicitHeight: Theme.gap6 }
                    }
                }

                // Playback & audio -------------------------------------------------
                ScrollView {
                    objectName: "playbackPage"
                    contentWidth: availableWidth
                    ColumnLayout {
                        x: Theme.gap6; width: parent.width - 2 * Theme.gap6
                        spacing: Theme.gap1
                        PageTitle { text: "Playback & audio" }
                        FieldLabel { text: "Default tempo (bpm)" }
                        NumberSetting { setting: "bpm"; Layout.preferredWidth: Theme.px(24) }
                        ErrorText { text: win.numberErrors.bpm || "" }
                        Help { text: "For songs without a {bpm} directive." }
                        FieldLabel { text: "Default time signature" }
                        RowLayout {
                            NumberSetting { setting: "time_signature_beats"; Layout.preferredWidth: Theme.px(18) }
                            Label { text: "/"; color: Theme.muted }
                            ComboBox {
                                objectName: "setting:time_signature_unit"
                                readonly property var units: {
                                    var u = win.settings.choices.timeUnits.slice()
                                    var current = win.values.time_signature_unit
                                    if (current !== undefined && u.indexOf(current) < 0) u.unshift(current)
                                    return u
                                }
                                model: units.map((n) => String(n))
                                currentIndex: units.indexOf(win.values.time_signature_unit)
                                Layout.preferredWidth: Theme.px(18)
                                onActivated: (i) => win.settings.setValue("time_signature_unit", units[i])
                            }
                        }
                        ErrorText { text: win.numberErrors.time_signature_beats || "" }
                        FieldLabel { text: "Soundfont" }
                        RowLayout {
                            Layout.maximumWidth: win.formWidth
                            FormField {
                                id: soundfontField
                                objectName: "setting:soundfont_path"
                                Layout.fillWidth: true
                                placeholderText: "Bundled default soundfont"
                                shown: win.values.soundfont_path || ""
                                onCommitted: win.settings.setValue("soundfont_path", soundfontField.text)
                            }
                            Button {
                                objectName: "browseSoundfont"
                                text: "Browse…"
                                onClicked: soundfontDialog.open()
                            }
                        }
                        Help { text: "Leave empty to use the bundled default soundfont. " + win.restartHint }
                        FieldLabel { text: "Audio driver" }
                        ComboBox {
                            id: driverBox
                            objectName: "setting:audio_driver"
                            editable: true
                            model: win.settings.choices.audioDrivers
                            Layout.preferredWidth: Theme.px(40)
                            // The saved driver, whether or not it is one of the suggestions.
                            readonly property string saved: win.values.audio_driver || ""
                            Component.onCompleted: driverBox.editText = driverBox.saved
                            onSavedChanged: if (!driverBox.activeFocus) driverBox.editText = driverBox.saved
                            onActivated: (i) => win.settings.setValue("audio_driver", win.settings.choices.audioDrivers[i])
                            onAccepted: win.settings.setValue("audio_driver", driverBox.editText)
                            onActiveFocusChanged: if (!activeFocus) win.settings.setValue("audio_driver", driverBox.editText)
                        }
                        Help { text: "Empty means auto-detect. " + win.restartHint }
                        Item { implicitHeight: Theme.gap6 }
                    }
                }

                // Voicings ---------------------------------------------------------
                VoicingsPage {
                    settings: win.settings
                    confirm: win.confirm
                    formWidth: win.formWidth
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.px(12)
                color: Theme.chrome
                Rectangle { width: parent.width; height: Theme.hairline; color: Theme.border }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.gap4; anchors.rightMargin: Theme.gap4
                    Label { text: "Changes are saved as you make them."; color: Theme.muted; font: Theme.fontS; Layout.fillWidth: true }
                    Button { objectName: "settingsClose"; text: "Close"; onClicked: win.requestClose() }
                }
            }
        }
    }

    // "Select SoundFont", *.sf2 (Tk's Browse).
    FileDialog {
        id: soundfontDialog
        title: "Select SoundFont"
        nameFilters: ["SoundFont files (*.sf2)", "All files (*)"]
        onAccepted: {
            var path = win.settings.localFile(soundfontDialog.selectedFile)
            soundfontField.text = path
            win.settings.setValue("soundfont_path", path)
        }
    }

    // Remove voicing / Copy from existing / Change model: the question.
    AppDialog {
        id: confirmDlg
        objectName: "settingsConfirm"
        property string message: ""
        property string actionText: "OK"
        property var yes: null
        closePolicy: Popup.CloseOnEscape
        contentItem: Label { text: confirmDlg.message; color: Theme.muted; wrapMode: Text.Wrap }
        footer: DialogFooter {
            Button { objectName: "settingsConfirmCancel"; text: "Cancel"; onClicked: confirmDlg.close() }
            Button {
                objectName: "settingsConfirmYes"
                text: confirmDlg.actionText
                highlighted: true
                onClicked: { var f = confirmDlg.yes; confirmDlg.close(); if (f) f() }
            }
        }
    }

    // Closing with wrong values (Android's Problems dialog): Edit stays, Discard drops them.
    AppDialog {
        id: problemsDlg
        objectName: "settingsProblems"
        title: "Some values aren't saved"
        width: Theme.px(140)
        closePolicy: Popup.CloseOnEscape
        contentItem: ColumnLayout {
            spacing: Theme.gap2
            Label { text: "These have mistakes, so they aren't saved:"; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Label {
                objectName: "settingsProblemsList"
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
                text: {
                    var lines = []
                    for (const name in win.numberErrors) lines.push("• " + win.numberErrors[name] + " (" + win.numberTexts[name] + ")")
                    for (const p of (win.settings.editor.problems || [])) lines.push("• " + p.text)
                    return lines.join("\n")
                }
            }
        }
        footer: DialogFooter {
            leading: Button {
                objectName: "settingsProblemsDiscard"
                text: "Discard"; flat: true
                contentItem: SText {
                    text: "Discard"; color: Theme.error; font: Theme.fontMedium
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                onClicked: { problemsDlg.close(); win.finish() }
            }
            Button { objectName: "settingsProblemsEdit"; text: "Edit"; highlighted: true; onClicked: { problemsDlg.close(); win.editProblems() } }
        }
    }

    ErrorDialog {
        id: errorDlg
        objectName: "settingsErrorDialog"
        onDismissed: win.errors.dismissed()
    }
}

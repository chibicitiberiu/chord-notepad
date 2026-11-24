import ChordNotepadKit
import SwiftUI

/// What the Settings screen does with a tap: a change to the kit's
/// ``SettingsController`` (the app sends what it queues). Nil in the catalog.
typealias SettingsAct = ((inout SettingsController) -> Void) -> Void

/// ☰ › Settings (Android's `SettingsScreen`): General, Playback and the
/// Voicings editor over a settings edit (`begin_settings_edit` when it opens;
/// every change is saved as it is made with `commit_settings`; leaving sends
/// `cancel_settings_edit`, asking first while a value is wrong). Full screen:
/// on a phone the pages list, a page, the voicing form; from 600 pt wide the
/// pages list stays on the left; the voicings list and form side by side
/// when there is room for both. Drawn from the controller's value, so the
/// catalog draws it from a recorded scene.
struct SettingsScreen: View {
    let controller: SettingsController
    let schema: EditorSchema?
    var live = true
    var act: SettingsAct?
    /// The catalog's stand-in for the Add voicing menu (live, it is iOS's menu).
    var addMenuShown = false
    /// The catalog's stand-in for the rename dialog's field.
    var renameText: String?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    private func change(_ body: @escaping (inout SettingsController) -> Void) {
        act?(body)
    }

    var body: some View {
        GeometryReader { window in
            let width = Double(window.size.width)
            let twoPane = settingsTwoPane(width: width)
            let split = splitsVoicings(width: width)
            VStack(spacing: 0) {
                PageBar(title: settingsTitle(controller.ui, editor: controller.editor, twoPane: twoPane, split: split),
                        colors: colors) {
                    change { $0.back(twoPane: twoPane, split: split) }
                }
                if settingsShowsRestoredBanner(controller.ui, editor: controller.editor) {
                    restoredBanner
                }
                content(twoPane: twoPane, split: split)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
            .background(colors.surface.swiftUI.ignoresSafeArea())
            .overlay { dialogs }
            .task(id: twoPane) { if live { change { $0.settleNav(twoPane: twoPane) } } }
        }
        .accessibilityIdentifier("settings-screen")
    }

    @ViewBuilder
    private func content(twoPane: Bool, split: Bool) -> some View {
        let ui = controller.ui
        if let draft = ui.draft, let limits = controller.limits, ui.phase != .new, ui.phase != .opening {
            let shown = ui.nav.shown(twoPane: twoPane)
            if twoPane {
                HStack(spacing: 0) {
                    pagesList(selected: shown)
                        .frame(width: CGFloat(settingsPagesPaneWidth))
                        .frame(maxHeight: .infinity, alignment: .top)
                    Rule(colors: colors, vertical: true)
                    page(shown ?? .general, draft: draft, limits: limits, split: split)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                }
            } else if let shown {
                page(shown, draft: draft, limits: limits, split: split)
            } else {
                pagesList(selected: nil)
            }
        } else {
            Spinner(color: colors.primary.swiftUI, animated: live)
                .frame(width: 40, height: 40)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder
    private func page(_ page: SettingsPage, draft: SettingsDraft, limits: SettingsState, split: Bool) -> some View {
        switch page {
        case .general:
            GeneralPage(draft: draft, limits: limits, numbers: controller.ui.numberTexts,
                        focus: controller.ui.focus, colors: colors, live: live, act: change)
        case .playback:
            PlaybackPage(draft: draft, limits: limits, numbers: controller.ui.numberTexts,
                         focus: controller.ui.focus, colors: colors, live: live, act: change)
        case .voicings:
            VoicingsPage(schema: schema, view: controller.editor, detail: controller.ui.nav.voicingDetail,
                         split: split, colors: colors, live: live, addMenuShown: addMenuShown, act: change)
        }
    }

    /// The pages: General, Playback, Voicings (the shown one tinted with two
    /// panes). The FOSS flavour's support card has nothing to show, so none.
    private func pagesList(selected: SettingsPage?) -> some View {
        VStack(spacing: 0) {
            ForEach(SettingsPage.allCases, id: \.self) { page in
                ListRow(headline: page.title, supporting: page.summary, selected: page == selected, colors: colors,
                        identifier: "settings-page-\(page.rawValue)") {
                    change { $0.openPage(page) }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.top, 8)
    }

    /// Wrong values kept from last time: Edit goes to the first, Discard drops them.
    private var restoredBanner: some View {
        VStack(alignment: .trailing, spacing: 0) {
            Text(SettingsTexts.restored)
                .font(.subheadline)
                .foregroundColor(colors.onErrorContainer.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.trailing, 8)
            HStack(spacing: 0) {
                DialogButton(label: SettingsTexts.problemsDiscard, colors: colors) {
                    change { $0.discardProblems() }
                }
                DialogButton(label: SettingsTexts.problemsEdit, colors: colors) {
                    change { $0.editProblems() }
                }
            }
        }
        .padding(.leading, 16)
        .padding(.top, 12)
        .padding(.trailing, 8)
        .background(colors.errorContainer.swiftUI, in: RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .accessibilityIdentifier("settings-restored")
    }

    // MARK: - Dialogs

    @ViewBuilder
    private var dialogs: some View {
        switch controller.ui.dialog {
        case .problems?:
            problemsDialog
        case .removeVoicing(let name)?:
            confirmDialog(title: schema?.text("remove_confirm_title") ?? "",
                          message: (schema?.text("remove_confirm") ?? "").replacingOccurrences(of: "{name}", with: name))
        case .changeModel?:
            confirmDialog(title: schema?.text("model_confirm_title") ?? "", message: schema?.text("model_confirm") ?? "")
        case .rename(let name)?:
            RenameVoicingDialog(name: name, schema: schema, colors: colors, live: live, typed: renameText,
                                confirm: { new in change { $0.confirmDialog(newName: new) } },
                                dismiss: { change { $0.dismissDialog() } })
        case nil:
            EmptyView()
        }
    }

    /// Leaving with wrong values: each listed (numbers worded here, voicing
    /// values as Python words them), Edit goes to the first, Discard drops
    /// them and leaves.
    private var problemsDialog: some View {
        let lines = settingsProblemLines(controller.ui, editor: controller.editor, limits: controller.limits)
        return ToolDialog(title: SettingsTexts.problemsTitle, colors: colors, live: live, identifier: "settings-problems",
                          dismiss: { change { $0.dismissDialog() } }) {
            VStack(alignment: .leading, spacing: 8) {
                Text(SettingsTexts.problemsIntro)
                ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                    Text("• \(line)").font(.subheadline)
                }
            }
            .foregroundColor(colors.text.swiftUI)
            .fixedSize(horizontal: false, vertical: true)
        } buttons: {
            DialogButton(label: SettingsTexts.problemsDiscard, colors: colors) { change { $0.confirmDialog() } }
            DialogButton(label: SettingsTexts.problemsEdit, colors: colors) { change { $0.editProblems() } }
        }
    }

    private func confirmDialog(title: String, message: String) -> some View {
        ToolDialog(title: title, colors: colors, live: live, identifier: "settings-confirm",
                   dismiss: { change { $0.dismissDialog() } }) {
            Text(message)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
        } buttons: {
            DialogButton(label: SettingsTexts.cancel, colors: colors) { change { $0.dismissDialog() } }
            DialogButton(label: SettingsTexts.ok, colors: colors) { change { $0.confirmDialog() } }
        }
    }
}

/// Rename a voicing (the name selected, ready to type over); a refused name
/// comes back as the session's "Rename Voicing" error.
struct RenameVoicingDialog: View {
    let name: String
    let schema: EditorSchema?
    let colors: AppColors
    var live = true
    /// The catalog's text in the field.
    var typed: String?
    var confirm: (String) -> Void = { _ in }
    var dismiss: () -> Void = {}

    @State private var text: String?
    @FocusState private var focused: Bool

    var body: some View {
        let current = text ?? typed ?? name
        ToolDialog(title: SettingsTexts.voicingsRename, colors: colors, live: live, identifier: "voicing-rename",
                   dismiss: dismiss) {
            OutlinedBox(label: schema?.text("name_label", fallback: "Name") ?? "Name", colors: colors,
                        supporting: schema?.help["name"], focused: true, background: colors.surfaceHigh.swiftUI) {
                Group {
                    if live {
                        TextField("", text: Binding(get: { current }, set: { text = $0 }))
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.done)
                            .focused($focused)
                            .onSubmit { if !blank(current) { confirm(current) } }
                            .onAppear { focused = true }
                            .accessibilityIdentifier("voicing-rename-field")
                    } else {
                        Text(current)
                    }
                }
                .font(.body)
                .foregroundColor(colors.text.swiftUI)
                .padding(.horizontal, 16)
            }
        } buttons: {
            DialogButton(label: SettingsTexts.cancel, colors: colors, action: dismiss)
            DialogButton(label: SettingsTexts.ok, colors: colors, enabled: !blank(current)) { confirm(current) }
        }
    }

    private func blank(_ text: String) -> Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
}

// MARK: - General and Playback

/// Settings › General: font, word wrap, chord notation, default key, quick start, recent files.
struct GeneralPage: View {
    let draft: SettingsDraft
    let limits: SettingsState
    let numbers: [NumberSetting: String]
    let focus: NumberSetting?
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        PageColumn(live: live) {
            DropdownField(label: SettingsTexts.fontFamily, selected: draft.fontKind, options: EditorFontKind.allCases,
                          optionLabel: { $0.map(fontKindLabel) ?? "" }, colors: colors, live: live,
                          supporting: SettingsTexts.fontFamilyHelp, identifier: "settings-font-family") { kind in
                act { $0.updateDraft { $0.fontKind = kind } }
            }
            NumberSettingField(setting: .fontSize, draft: draft, limits: limits, numbers: numbers, focus: focus,
                               colors: colors, live: live, act: act)
            SwitchRow(label: SettingsTexts.wordWrap, checked: draft.wordWrap, colors: colors,
                      supporting: SettingsTexts.wordWrapHelp, identifier: "settings-word-wrap") { on in
                act { $0.updateDraft { $0.wordWrap = on } }
            }
            Text(SettingsTexts.notation)
                .font(.body)
                .foregroundColor(colors.text.swiftUI)
            SegmentedRow(options: [(Notation.american, SettingsTexts.notationAmerican),
                                   (Notation.european, SettingsTexts.notationEuropean)],
                         selected: draft.notation, colors: colors, identifier: "settings-notation") { notation in
                act { $0.setNotation(notation) }
            }
            HelpText(text: SettingsTexts.notationHelp, colors: colors)
            DropdownField(label: SettingsTexts.defaultKey, selected: draft.key, options: [""] + limits.americanKeys,
                          optionLabel: { key in
                              guard let key, !key.isEmpty else { return SettingsTexts.keyNone }
                              return shownKey(key, notation: draft.notation, limits: limits)
                          },
                          colors: colors, live: live, supporting: SettingsTexts.defaultKeyHelp,
                          identifier: "settings-default-key") { key in
                act { $0.updateDraft { $0.key = key } }
            }
            SwitchRow(label: SettingsTexts.quickStart, checked: draft.showQuickStartOnStartup, colors: colors,
                      supporting: SettingsTexts.quickStartHelp, identifier: "settings-quick-start") { show in
                act { $0.updateDraft { $0.showQuickStartOnStartup = show } }
            }
            NumberSettingField(setting: .maxRecentFiles, draft: draft, limits: limits, numbers: numbers, focus: focus,
                               colors: colors, live: live, act: act)
        }
    }
}

/// Settings › Playback: default BPM and time signature, how a tapped chord sounds.
struct PlaybackPage: View {
    let draft: SettingsDraft
    let limits: SettingsState
    let numbers: [NumberSetting: String]
    let focus: NumberSetting?
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        PageColumn(live: live) {
            NumberSettingField(setting: .bpm, draft: draft, limits: limits, numbers: numbers, focus: focus,
                               colors: colors, live: live, act: act)
            Text(SettingsTexts.timeSignature)
                .font(.body)
                .foregroundColor(colors.text.swiftUI)
            HStack(alignment: .top, spacing: 12) {
                NumberSettingField(setting: .timeSignatureBeats, draft: draft, limits: limits, numbers: numbers,
                                   focus: focus, colors: colors, live: live, act: act)
                    .frame(maxWidth: .infinity)
                DropdownField(label: SettingsTexts.beatUnit, selected: draft.timeSignatureUnit,
                              options: limits.timeSignatureUnits, optionLabel: { $0.map(String.init) ?? "" },
                              colors: colors, live: live, identifier: "settings-beat-unit") { unit in
                    act { $0.updateDraft { $0.timeSignatureUnit = unit } }
                }
                .frame(maxWidth: .infinity)
            }
            HelpText(text: SettingsTexts.timeSignatureHelp, colors: colors)
            SwitchRow(label: SettingsTexts.clickChartVoicing, checked: draft.clickPlaysChartVoicing, colors: colors,
                      supporting: SettingsTexts.clickChartVoicingHelp, identifier: "settings-click-voicing") { on in
                act { $0.updateDraft { $0.clickPlaysChartVoicing = on } }
            }
        }
    }
}

/// A whole-number setting with − and +; text out of range shows its range
/// in red and isn't saved.
struct NumberSettingField: View {
    let setting: NumberSetting
    let draft: SettingsDraft
    let limits: SettingsState
    let numbers: [NumberSetting: String]
    let focus: NumberSetting?
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let range = setting.range(limits)
        let value = setting.get(draft)
        let wrong = numbers[setting]
        FormField(label: setting.label, value: wrong ?? String(value), colors: colors, live: live,
                  supporting: wrong != nil ? setting.rangeText(limits) : setting.help, error: wrong != nil,
                  keyboard: .numberPad, focusNow: focus == setting, focusShown: { act { $0.focusShown() } },
                  identifier: "settings-\(setting.key)", change: { text in act { $0.setNumber(setting, text) } }) {
            StepperButtons(label: setting.label, canDown: range.contains(value - 1), canUp: range.contains(value + 1),
                           colors: colors, identifier: "settings-\(setting.key)") { delta in
                act { $0.stepNumber(setting, delta) }
            }
        }
    }
}

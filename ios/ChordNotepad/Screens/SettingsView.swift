import ChordNotepadKit
import SwiftUI

/// What the Settings screen does with a tap: a change to the kit's
/// ``SettingsController`` (the app sends what it queues). Nil in the catalog.
typealias SettingsAct = ((inout SettingsController) -> Void) -> Void

/// A level of Settings' navigation on a phone.
enum SettingsStep: Hashable {
    case page(SettingsPage)
    case voicingDetail
}

/// ☰ › Settings (Android's `SettingsScreen`): General, Playback and the
/// Voicings editor over a settings edit (`begin_settings_edit` when it opens;
/// every change is saved as it is made with `commit_settings`; leaving sends
/// `cancel_settings_edit`, asking first while a value is wrong). Drawn as
/// iOS's Settings: on a phone a navigation stack (the pages list, a page,
/// the voicing form, with the system's Back and its swipe), from 600 pt wide
/// the pages list beside the page, the voicings list and form side by side
/// when there is room for both. Done leaves. The stack follows the kit's
/// ``SettingsNav``, so the catalog draws it from a recorded scene.
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
            Group {
                if twoPane {
                    HStack(spacing: 0) {
                        NavigationStack {
                            pagesList(selected: controller.ui.nav.shown(twoPane: true))
                                .navigationTitle(SettingsTexts.title)
                                .toolbar { doneItem(twoPane: true, split: split) }
                        }
                        .frame(width: CGFloat(settingsPagesPaneWidth) + 40)
                        colors.separator.frame(width: 0.5)
                        NavigationStack(path: detailPath(split: split)) {
                            pageView(controller.ui.nav.shown(twoPane: true) ?? .general, split: split)
                                .navigationDestination(for: SettingsStep.self) { _ in voicingDetail(wide: false) }
                        }
                    }
                } else {
                    NavigationStack(path: phonePath(split: split)) {
                        pagesList(selected: nil)
                            .navigationTitle(SettingsTexts.title)
                            .toolbar { doneItem(twoPane: false, split: split) }
                            .navigationDestination(for: SettingsStep.self) { step in
                                switch step {
                                case .page(let page): pageView(page, split: split)
                                case .voicingDetail: voicingDetail(wide: false)
                                }
                            }
                    }
                }
            }
            .background(colors.groupedBackground.ignoresSafeArea())
            .overlay { drawnDialogs }
            .task(id: twoPane) { if live { change { $0.settleNav(twoPane: twoPane) } } }
        }
        .modifier(SettingsAlerts(controller: controller, schema: schema, live: live, change: change))
        .accessibilityIdentifier("settings-screen")
    }

    /// Done: leave Settings (asking first while a value is wrong).
    private func doneItem(twoPane: Bool, split: Bool) -> some ToolbarContent {
        ToolbarItem(placement: .confirmationAction) {
            Button(sheetDone) { change { $0.requestClose() } }
                .fontWeight(.semibold)
                .accessibilityIdentifier("page-back")
        }
    }

    /// A phone's stack: the page, then the voicing form. Back (the button or
    /// the swipe) goes up a level through the controller.
    private func phonePath(split: Bool) -> Binding<[SettingsStep]> {
        let nav = controller.ui.nav
        var path: [SettingsStep] = []
        if let page = nav.page {
            path.append(.page(page))
            if page == .voicings && nav.voicingDetail && !split && controller.editor?.state.selected != nil {
                path.append(.voicingDetail)
            }
        }
        return Binding(get: { path }, set: { new in
            guard new.count < path.count else { return }
            for _ in new.count..<path.count { change { $0.back(twoPane: false, split: split) } }
        })
    }

    /// The right pane's stack with two panes: the voicing form over the
    /// voicings list when they don't fit side by side.
    private func detailPath(split: Bool) -> Binding<[SettingsStep]> {
        let nav = controller.ui.nav
        let path: [SettingsStep] = nav.page == .voicings && nav.voicingDetail && !split
            && controller.editor?.state.selected != nil ? [.voicingDetail] : []
        return Binding(get: { path }, set: { new in
            if new.isEmpty && !path.isEmpty { change { $0.back(twoPane: true, split: split) } }
        })
    }

    private var ready: Bool {
        let ui = controller.ui
        return ui.draft != nil && controller.limits != nil && ui.phase != .new && ui.phase != .opening
    }

    @ViewBuilder
    private func pageView(_ page: SettingsPage, split: Bool) -> some View {
        Group {
            if let draft = controller.ui.draft, let limits = controller.limits, ready {
                switch page {
                case .general:
                    GeneralPage(draft: draft, limits: limits, numbers: controller.ui.numberTexts,
                                focus: controller.ui.focus, colors: colors, live: live, act: change)
                case .playback:
                    PlaybackPage(draft: draft, limits: limits, numbers: controller.ui.numberTexts,
                                 focus: controller.ui.focus, colors: colors, live: live, act: change)
                case .voicings:
                    VoicingsPage(schema: schema, view: controller.editor, split: split, colors: colors, live: live,
                                 addMenuShown: addMenuShown, act: change)
                }
            } else {
                loading
            }
        }
        .navigationTitle(page.title)
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .top) { restoredBanner }
    }

    private func voicingDetail(wide: Bool) -> some View {
        Group {
            if let schema, let view = controller.editor {
                VoicingDetail(schema: schema, view: view, wide: wide, colors: colors, live: live, act: change)
            } else {
                loading
            }
        }
        .navigationTitle(controller.editor?.state.selected ?? SettingsTexts.pageVoicings)
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .top) { restoredBanner }
    }

    private var loading: some View {
        ProgressView()
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    /// The pages: General, Playback, Voicings, each with what it holds; with
    /// two panes the shown one is selected as a sidebar's row. The FOSS
    /// flavour's support card has nothing to show, so none.
    private func pagesList(selected: SettingsPage?) -> some View {
        List {
            Section {
                ForEach(SettingsPage.allCases, id: \.self) { page in
                    let on = page == selected
                    Button { change { $0.openPage(page) } } label: {
                        HStack(spacing: 8) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(page.title)
                                    .foregroundColor(on ? .white : colors.label)
                                Text(page.summary)
                                    .font(.footnote)
                                    .foregroundColor(on ? .white.opacity(0.85) : colors.secondaryLabel)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            if selected == nil {
                                Image(systemName: AppSymbols.chevronRight)
                                    .font(.footnote.weight(.semibold))
                                    .foregroundColor(colors.tertiaryLabel)
                                    .accessibilityHidden(true)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .listRowBackground(on ? Color.accentColor : colors.cell)
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityIdentifier("settings-page-\(page.rawValue)")
                }
            }
        }
        .listStyle(.insetGrouped)
        .safeAreaInset(edge: .top) { restoredBanner }
    }

    /// Wrong values kept from last time: Edit goes to the first, Discard drops them.
    @ViewBuilder
    private var restoredBanner: some View {
        if settingsShowsRestoredBanner(controller.ui, editor: controller.editor) {
            VStack(alignment: .leading, spacing: 4) {
                Label {
                    Text(SettingsTexts.restored)
                        .fixedSize(horizontal: false, vertical: true)
                } icon: {
                    Image(systemName: AppSymbols.error).foregroundStyle(colors.red)
                }
                .font(.subheadline)
                HStack(spacing: 20) {
                    Spacer(minLength: 0)
                    Button(SettingsTexts.problemsDiscard) { change { $0.discardProblems() } }
                    Button(SettingsTexts.problemsEdit) { change { $0.editProblems() } }
                        .fontWeight(.semibold)
                }
                .buttonStyle(.borderless)
                .frame(minHeight: 36)
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 6)
            .background(colors.cell, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .accessibilityIdentifier("settings-restored")
        }
    }

    // MARK: - Dialogs

    /// Rename (a field, so drawn in the system's alert look, live and in the
    /// catalog) and the catalog's pictures of the system's alerts.
    @ViewBuilder
    private var drawnDialogs: some View {
        switch controller.ui.dialog {
        case .rename(let name)?:
            RenameVoicingDialog(name: name, schema: schema, colors: colors, live: live, typed: renameText,
                                confirm: { new in change { $0.confirmDialog(newName: new) } },
                                dismiss: { change { $0.dismissDialog() } })
        case .problems?:
            if !live {
                AlertCard(title: SettingsTexts.problemsTitle, message: SettingsAlerts.problemsMessage(controller),
                          actions: [AlertAction(title: SettingsTexts.problemsDiscard, role: .destructive) {},
                                    AlertAction(title: SettingsTexts.problemsEdit, role: .preferred) {}],
                          live: false, identifier: "settings-problems")
            }
        case .removeVoicing(let name)?:
            if !live {
                AlertCard(title: schema?.text("remove_confirm_title") ?? "",
                          message: SettingsAlerts.removeMessage(schema, name),
                          actions: [AlertAction(title: SettingsTexts.cancel, role: .cancel) {},
                                    AlertAction(title: SettingsTexts.ok, role: .destructive) {}],
                          live: false, identifier: "settings-confirm")
            }
        case .changeModel?:
            if !live {
                AlertCard(title: schema?.text("model_confirm_title") ?? "",
                          message: schema?.text("model_confirm") ?? "",
                          actions: [AlertAction(title: SettingsTexts.cancel, role: .cancel) {},
                                    AlertAction(title: SettingsTexts.ok, role: .preferred) {}],
                          live: false, identifier: "settings-confirm")
            }
        case nil:
            EmptyView()
        }
    }
}

/// Settings' questions as the system's alerts (live): leaving with wrong
/// values (Discard, or Edit to go to the first), removing a voicing,
/// switching a voicing's model.
private struct SettingsAlerts: ViewModifier {
    let controller: SettingsController
    let schema: EditorSchema?
    let live: Bool
    let change: (@escaping (inout SettingsController) -> Void) -> Void

    static func problemsMessage(_ controller: SettingsController) -> String {
        let lines = settingsProblemLines(controller.ui, editor: controller.editor, limits: controller.limits)
        return ([SettingsTexts.problemsIntro] + lines.map { "• \($0)" }).joined(separator: "\n")
    }

    static func removeMessage(_ schema: EditorSchema?, _ name: String) -> String {
        (schema?.text("remove_confirm") ?? "").replacingOccurrences(of: "{name}", with: name)
    }

    /// Shown while the controller asks; the buttons answer it (a system
    /// alert has no other way out).
    private func shown(_ matches: @escaping (SettingsDialog?) -> Bool) -> Binding<Bool> {
        Binding(get: { live && matches(controller.ui.dialog) }, set: { _ in })
    }

    private var removing: String? {
        if case .removeVoicing(let name)? = controller.ui.dialog { return name }
        return nil
    }

    func body(content: Content) -> some View {
        content
            .alert(SettingsTexts.problemsTitle, isPresented: shown { $0 == .problems }) {
                Button(SettingsTexts.problemsDiscard, role: .destructive) { change { $0.confirmDialog() } }
                Button(SettingsTexts.problemsEdit) { change { $0.editProblems() } }
            } message: {
                Text(Self.problemsMessage(controller))
            }
            .alert(schema?.text("remove_confirm_title") ?? "", isPresented: shown { dialog in
                if case .removeVoicing? = dialog { return true }
                return false
            }) {
                Button(SettingsTexts.cancel, role: .cancel) { change { $0.dismissDialog() } }
                Button(SettingsTexts.ok, role: .destructive) { change { $0.confirmDialog() } }
            } message: {
                Text(Self.removeMessage(schema, removing ?? ""))
            }
            .alert(schema?.text("model_confirm_title") ?? "", isPresented: shown { dialog in
                if case .changeModel? = dialog { return true }
                return false
            }) {
                Button(SettingsTexts.cancel, role: .cancel) { change { $0.dismissDialog() } }
                Button(SettingsTexts.ok) { change { $0.confirmDialog() } }
            } message: {
                Text(schema?.text("model_confirm") ?? "")
            }
    }
}

/// Rename a voicing, as an alert with a field; OK stays off while the name is
/// blank (drawn: a system alert reads its buttons once). A refused name comes
/// back as the session's "Rename Voicing" error.
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

    var body: some View {
        let current = text ?? typed ?? name
        AlertCard(title: SettingsTexts.voicingsRename, message: schema?.help["name"],
                  actions: [AlertAction(title: SettingsTexts.cancel, role: .cancel, action: dismiss),
                            AlertAction(title: SettingsTexts.ok, role: .preferred, enabled: !blank(current),
                                        identifier: "voicing-rename-ok") { confirm(current) }],
                  live: live, identifier: "voicing-rename") {
            AlertTextField(placeholder: schema?.text("name_label", fallback: "Name") ?? "Name",
                           text: Binding(get: { current }, set: { text = $0 }), live: live,
                           identifier: "voicing-rename-field") {
                if !blank(current) { confirm(current) }
            }
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
        Form {
            Section {
                Picker(SettingsTexts.fontFamily, selection: Binding(get: { draft.fontKind }, set: { kind in
                    act { $0.updateDraft { $0.fontKind = kind } }
                })) {
                    ForEach(EditorFontKind.allCases, id: \.self) { kind in
                        Text(fontKindLabel(kind)).tag(kind)
                    }
                }
                .pickerStyle(.menu)
                .accessibilityIdentifier("settings-font-family")
            } footer: {
                Text(SettingsTexts.fontFamilyHelp)
            }
            NumberSettingSection(setting: .fontSize, draft: draft, limits: limits, numbers: numbers, focus: focus,
                                 colors: colors, live: live, act: act)
            Section {
                Toggle(SettingsTexts.wordWrap, isOn: Binding(get: { draft.wordWrap }, set: { on in
                    act { $0.updateDraft { $0.wordWrap = on } }
                }))
                .accessibilityIdentifier("settings-word-wrap")
            } footer: {
                Text(SettingsTexts.wordWrapHelp)
            }
            Section {
                Picker(SettingsTexts.notation, selection: Binding(get: { draft.notation }, set: { notation in
                    act { $0.setNotation(notation) }
                })) {
                    Text(SettingsTexts.notationAmerican).tag(Notation.american)
                    Text(SettingsTexts.notationEuropean).tag(Notation.european)
                }
                .pickerStyle(.segmented)
                .accessibilityIdentifier("settings-notation")
            } header: {
                Text(SettingsTexts.notation)
            } footer: {
                Text(SettingsTexts.notationHelp)
            }
            Section {
                Picker(SettingsTexts.defaultKey, selection: Binding(get: { draft.key }, set: { key in
                    act { $0.updateDraft { $0.key = key } }
                })) {
                    ForEach([""] + limits.americanKeys, id: \.self) { key in
                        Text(key.isEmpty ? SettingsTexts.keyNone : shownKey(key, notation: draft.notation, limits: limits))
                            .tag(key)
                    }
                }
                .pickerStyle(.menu)
                .accessibilityIdentifier("settings-default-key")
            } footer: {
                Text(SettingsTexts.defaultKeyHelp)
            }
            Section {
                Toggle(SettingsTexts.quickStart, isOn: Binding(get: { draft.showQuickStartOnStartup }, set: { show in
                    act { $0.updateDraft { $0.showQuickStartOnStartup = show } }
                }))
                .accessibilityIdentifier("settings-quick-start")
            } footer: {
                Text(SettingsTexts.quickStartHelp)
            }
            NumberSettingSection(setting: .maxRecentFiles, draft: draft, limits: limits, numbers: numbers,
                                 focus: focus, colors: colors, live: live, act: act)
        }
        .scrollDismissesKeyboard(.interactively)
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
        Form {
            NumberSettingSection(setting: .bpm, draft: draft, limits: limits, numbers: numbers, focus: focus,
                                 colors: colors, live: live, act: act)
            Section {
                NumberSettingRow(setting: .timeSignatureBeats, draft: draft, limits: limits, numbers: numbers,
                                 focus: focus, colors: colors, live: live, act: act)
                Picker(SettingsTexts.beatUnit, selection: Binding(get: { draft.timeSignatureUnit }, set: { unit in
                    act { $0.updateDraft { $0.timeSignatureUnit = unit } }
                })) {
                    ForEach(limits.timeSignatureUnits, id: \.self) { unit in
                        Text(String(unit)).tag(unit)
                    }
                }
                .pickerStyle(.menu)
                .accessibilityIdentifier("settings-beat-unit")
            } header: {
                Text(SettingsTexts.timeSignature)
            } footer: {
                let wrong = numbers[.timeSignatureBeats] != nil
                Text(wrong ? NumberSetting.timeSignatureBeats.rangeText(limits) : SettingsTexts.timeSignatureHelp)
                    .foregroundColor(wrong ? colors.red : nil)
            }
            Section {
                Toggle(SettingsTexts.clickChartVoicing, isOn: Binding(get: { draft.clickPlaysChartVoicing }, set: { on in
                    act { $0.updateDraft { $0.clickPlaysChartVoicing = on } }
                }))
                .accessibilityIdentifier("settings-click-voicing")
            } footer: {
                Text(SettingsTexts.clickChartVoicingHelp)
            }
        }
        .scrollDismissesKeyboard(.interactively)
    }
}

/// A whole-number setting in a section of its own: the row, and its help
/// under it (its range in red while the text is out of range, not saved).
struct NumberSettingSection: View {
    let setting: NumberSetting
    let draft: SettingsDraft
    let limits: SettingsState
    let numbers: [NumberSetting: String]
    let focus: NumberSetting?
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let wrong = numbers[setting] != nil
        Section {
            NumberSettingRow(setting: setting, draft: draft, limits: limits, numbers: numbers, focus: focus,
                             colors: colors, live: live, act: act)
        } footer: {
            if let help = wrong ? setting.rangeText(limits) : setting.help {
                Text(help)
                    .foregroundColor(wrong ? colors.red : nil)
            }
        }
    }
}

/// A whole-number setting's row: its name, the number typed, and − / +.
struct NumberSettingRow: View {
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
        NumberRow(label: setting.label, value: wrong ?? String(value), error: wrong != nil, live: live,
                  keyboard: .numberPad, canDown: range.contains(value - 1), canUp: range.contains(value + 1),
                  focusNow: focus == setting, focusShown: { act { $0.focusShown() } },
                  identifier: "settings-\(setting.key)",
                  change: { text in act { $0.setNumber(setting, text) } },
                  step: { delta in act { $0.stepNumber(setting, delta) } })
    }
}

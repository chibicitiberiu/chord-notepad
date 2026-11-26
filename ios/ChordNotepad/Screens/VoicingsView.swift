import ChordNotepadKit
import SwiftUI

/// Settings › Voicings (Android's `VoicingsPage`): the voicings grouped by
/// model, each group's built-ins first (with a lock), and the selected one's
/// form. Side by side when `split`; else the list, and the form pushed on it
/// once a voicing is picked (`SettingsScreen`'s navigation).
struct VoicingsPage: View {
    let schema: EditorSchema?
    let view: EditorView?
    let split: Bool
    let colors: AppColors
    var live = true
    var addMenuShown = false
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        if let schema, let view {
            if split {
                HStack(spacing: 0) {
                    VoicingList(schema: schema, state: view.state, split: true, colors: colors, live: live,
                                addMenuShown: addMenuShown, act: act)
                        .frame(width: CGFloat(voicingsListWidth) + 40)
                    colors.separator.frame(width: 0.5)
                    VoicingDetail(schema: schema, view: view, wide: true, colors: colors, live: live, act: act)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            } else {
                VoicingList(schema: schema, state: view.state, split: false, colors: colors, live: live,
                            addMenuShown: addMenuShown, act: act)
            }
        } else {
            ProgressView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

/// The voicings grouped by model, each group's built-ins first (tapping one
/// shows it read-only), invalid ones marked; Add voicing opens a menu of what
/// the new one starts as.
struct VoicingList: View {
    let schema: EditorSchema
    let state: VoicingEditorState
    let split: Bool
    let colors: AppColors
    var live = true
    var addMenuShown = false
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let builtin = state.showsBuiltin
        List {
            Section {
                AddVoicingButton(schema: schema, presets: state.addPresets(), live: live) { preset in
                    act { $0.addVoicingFrom(preset) }
                }
            } footer: {
                if let help = schema.help["tree_add"] { Text(help) }
            }
            if !state.invalid.isEmpty {
                Section {
                    ErrorBanner(messages: [SettingsTexts.voicingsInvalidBanner], colors: colors)
                }
            }
            ForEach(state.groups, id: \.model) { group in
                Section(group.label) {
                    if group.names.isEmpty && group.builtins.isEmpty {
                        Text(SettingsTexts.voicingsEmptyGroup)
                            .foregroundColor(colors.secondaryLabel)
                    }
                    ForEach(group.builtins, id: \.self) { label in
                        row(label, selected: builtin && state.model == group.model && label == state.selected,
                            identifier: "builtin-\(label)") {
                            Text(label)
                                .foregroundColor(colors.secondaryLabel)
                            Spacer(minLength: 8)
                            Image(systemName: AppSymbols.lock)
                                .font(.footnote)
                                .foregroundColor(colors.tertiaryLabel)
                                .accessibilityLabel(SettingsTexts.voicingsBuiltin)
                        } action: {
                            act { $0.selectBuiltin(model: group.model, label: label) }
                        }
                    }
                    ForEach(group.names, id: \.self) { name in
                        let invalid = state.invalid.contains(name)
                        row(name, selected: !builtin && name == state.selected, identifier: "voicing-\(name)") {
                            if invalid {
                                Image(systemName: AppSymbols.error)
                                    .foregroundStyle(colors.red)
                                    .accessibilityHidden(true)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text(name)
                                    .foregroundColor(colors.label)
                                if invalid {
                                    Text(SettingsTexts.voicingsInvalid)
                                        .font(.footnote)
                                        .foregroundColor(colors.red)
                                }
                            }
                            Spacer(minLength: 8)
                        } action: {
                            act { $0.selectVoicing(name) }
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .overlay(alignment: .topLeading) {
            if !live && addMenuShown {
                AddVoicingMenuPicture(sections: addVoicingSections(state.addPresets(), schema: schema))
                    .padding(.leading, 32)
                    .padding(.top, 76)
            }
        }
    }

    /// A voicing's row: a chevron when the form opens over the list, the
    /// selected one tinted when both show.
    private func row<Content: View>(_ label: String, selected: Bool, identifier: String,
                                    @ViewBuilder content: () -> Content,
                                    action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                content()
                if !split {
                    Image(systemName: AppSymbols.chevronRight)
                        .font(.footnote.weight(.semibold))
                        .foregroundColor(colors.tertiaryLabel)
                        .accessibilityHidden(true)
                }
            }
            .contentShape(Rectangle())
        }
        .listRowBackground(selected && split ? Color.accentColor.opacity(0.18) : colors.cell)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityIdentifier(identifier)
    }
}

/// Add voicing: iOS's menu of what the new voicing starts as (the blanks,
/// then the built-ins by model and the user's own voicings, each group under
/// its title).
struct AddVoicingButton: View {
    let schema: EditorSchema
    let presets: [VoicingPreset]
    var live = true
    var pick: (VoicingPreset) -> Void = { _ in }

    var body: some View {
        Menu {
            ForEach(Array(addVoicingSections(presets, schema: schema).enumerated()), id: \.offset) { _, section in
                Section(section.title ?? "") {
                    ForEach(section.presets, id: \.label) { preset in
                        Button(preset.label) { pick(preset) }
                    }
                }
            }
        } label: {
            Label(SettingsTexts.voicingsAdd, systemImage: AppSymbols.add)
        }
        .accessibilityIdentifier("voicings-add")
    }
}

/// The catalog's picture of the open Add voicing menu, as iOS draws a menu.
private struct AddVoicingMenuPicture: View {
    let sections: [(title: String?, presets: [VoicingPreset])]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(sections.enumerated()), id: \.offset) { index, section in
                if index > 0 { Color(uiColor: .separator).frame(height: 6).opacity(0.3) }
                if let title = section.title {
                    Text(title)
                        .font(.footnote)
                        .foregroundColor(Color(uiColor: .secondaryLabel))
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 4)
                }
                ForEach(Array(section.presets.enumerated()), id: \.offset) { row, preset in
                    if row > 0 { Color(uiColor: .separator).frame(height: 0.5) }
                    Text(preset.label)
                        .lineLimit(1)
                        .padding(.horizontal, 16)
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                }
            }
        }
        .frame(width: 260, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 13, style: .continuous))
        .shadow(color: .black.opacity(0.2), radius: 20, y: 6)
        .fixedSize(horizontal: false, vertical: true)
    }
}

/// The selected voicing: its name (tap to rename), model, Remove, then the
/// form under the errors banner. A built-in shows read-only: its name with a
/// lock and Copy to a new voicing, the model and the form greyed, no Remove.
struct VoicingDetail: View {
    let schema: EditorSchema
    let view: EditorView
    let wide: Bool
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    @State private var banner = ErrorsBanner()

    var body: some View {
        let state = view.state
        if let name = state.selected {
            if let form = schema.form(state.model) {
                detail(name: name, form: form)
            } else if state.readOnly {
                // A voicing of a model a newer version added: read-only, no
                // form; the session's note says so. It can be renamed or removed.
                newerVersion(name: name)
            }
        } else {
            Text(schema.text("placeholder"))
                .foregroundColor(colors.secondaryLabel)
                .multilineTextAlignment(.center)
                .padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(colors.groupedBackground)
        }
    }

    private func detail(name: String, form: FormSpec) -> some View {
        let state = view.state
        let builtin = state.showsBuiltin
        let items = buildForm(form, values: view.values, errors: state.fieldErrors, hints: state.hints,
                              enabled: !builtin)
        let bannerKey = "\(name):\(state.model ?? "")"
        return Form {
            if live ? banner.visible && state.hasErrors : state.hasErrors {
                Section {
                    ErrorBanner(messages: state.formErrors,
                                title: schema.text("errors_banner", fallback: "Fix these errors to apply changes"),
                                colors: colors)
                        .accessibilityIdentifier("voicing-errors")
                }
            }
            if builtin {
                builtinName(name)
            } else {
                nameRow(name)
            }
            Section {
                Picker(schema.text("model_label"), selection: Binding(get: { state.model ?? "" }, set: { model in
                    act { $0.askModel(model) }
                })) {
                    ForEach(schema.models, id: \.model) { option in
                        Text(option.label).tag(option.model)
                    }
                }
                .pickerStyle(.menu)
                .disabled(builtin)
                .accessibilityIdentifier("voicing-model")
            } footer: {
                if let help = schema.help["model"] { Text(help) }
            }
            if !builtin {
                Section {
                    Button(role: .destructive) { act { $0.askRemove(name) } } label: {
                        Label(SettingsTexts.voicingsRemove, systemImage: AppSymbols.delete)
                    }
                    .accessibilityIdentifier("voicing-remove")
                }
            }
            VoicingFormItems(items: items, formKey: "\(name):\(state.model ?? ""):\(builtin)", wide: wide,
                             colors: colors, live: live, act: act)
        }
        .scrollDismissesKeyboard(.interactively)
        .task(id: "\(bannerKey):\(state.hasErrors)") {
            guard live else { return }
            if banner.update(key: bannerKey, hasErrors: state.hasErrors) {
                try? await Task.sleep(for: .milliseconds(Int(draftSaveDelay * 1000)))
                if !Task.isCancelled { banner.delayElapsed(key: bannerKey) }
            }
        }
    }

    /// The voicing's name; tapping the row opens the rename dialog.
    private func nameRow(_ name: String) -> some View {
        Section {
            Button { act { $0.askRename(name) } } label: {
                HStack(spacing: 8) {
                    Text(schema.text("name_label"))
                        .foregroundColor(colors.label)
                    Spacer(minLength: 8)
                    Text(name)
                        .foregroundColor(colors.secondaryLabel)
                        .lineLimit(2)
                        .multilineTextAlignment(.trailing)
                    Image(systemName: AppSymbols.rename)
                        .font(.footnote)
                        .accessibilityHidden(true)
                }
                .contentShape(Rectangle())
            }
            .accessibilityLabel("\(schema.text("name_label")): \(name)")
            .accessibilityHint(SettingsTexts.voicingsRename)
            .accessibilityIdentifier("voicing-rename")
        } footer: {
            if let help = schema.help["name"] { Text(help) }
        }
    }

    /// A built-in's name, with a lock, and Copy to a new voicing.
    private func builtinName(_ name: String) -> some View {
        Section {
            HStack(spacing: 8) {
                Image(systemName: AppSymbols.lock)
                    .foregroundColor(colors.secondaryLabel)
                    .accessibilityLabel(SettingsTexts.voicingsBuiltin)
                Text(name)
                    .font(.headline)
                    .lineLimit(2)
            }
            Button {
                act { $0.addVoicingFrom(VoicingPreset(group: view.state.model ?? "", label: name)) }
            } label: {
                Label(SettingsTexts.voicingsCopyBuiltin, systemImage: AppSymbols.copy)
            }
            .accessibilityIdentifier("voicing-copy")
        } header: {
            Text(schema.text("name_label"))
        }
    }

    private func newerVersion(name: String) -> some View {
        Form {
            nameRow(name)
            Section {
                ForEach(Array(view.state.formErrors.enumerated()), id: \.offset) { _, note in
                    Text(note).foregroundColor(colors.secondaryLabel)
                }
                Button(role: .destructive) { act { $0.askRemove(name) } } label: {
                    Label(SettingsTexts.voicingsRemove, systemImage: AppSymbols.delete)
                }
                .accessibilityIdentifier("voicing-remove")
            }
        }
    }
}

/// The voicing form: every ``FormItem`` drawn by kind, a section from each
/// header to the next; a records field's rows each a section of their own (a
/// table row each when `wide`). `formKey` names the voicing and model (the
/// fields start afresh when it changes); `wide` puts grids in two columns.
struct VoicingFormItems: View {
    let items: [FormItem]
    let formKey: String
    let wide: Bool
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    /// A run of items under one header, or a records field (with its header).
    private enum FormGroup {
        case fields(title: String?, blurb: String?, items: [FormItem])
        case records(title: String?, blurb: String?, item: RecordsItem)
    }

    private var groups: [FormGroup] {
        var groups: [FormGroup] = []
        var title: String?
        var blurb: String?
        var run: [FormItem] = []
        func flush() {
            if !run.isEmpty || title != nil { groups.append(.fields(title: title, blurb: blurb, items: run)) }
            run = []
            title = nil
            blurb = nil
        }
        for item in items {
            switch item {
            case .header(_, let headerTitle, let headerBlurb, _):
                flush()
                title = headerTitle
                blurb = headerBlurb
            case .records(let records):
                groups.append(.records(title: title, blurb: blurb, item: records))
                if !run.isEmpty { groups.insert(.fields(title: nil, blurb: nil, items: run), at: groups.count - 1) }
                run = []
                title = nil
                blurb = nil
            default:
                run.append(item)
            }
        }
        flush()
        return groups
    }

    var body: some View {
        ForEach(Array(groups.enumerated()), id: \.offset) { _, group in
            switch group {
            case .fields(let title, let blurb, let items):
                Section {
                    ForEach(items, id: \.key) { item in rows(item) }
                } header: {
                    if let title { Text(title) }
                } footer: {
                    if let blurb { Text(blurb) }
                }
            case .records(let title, let blurb, let item):
                RecordsInput(item: item, title: title, blurb: blurb, formKey: formKey, wide: wide, colors: colors,
                             live: live, act: act)
            }
        }
    }

    @ViewBuilder
    private func rows(_ item: FormItem) -> some View {
        switch item {
        case .stack(_, let fields):
            ForEach(fields, id: \.spec.id) { field in input(field) }
        case .grid(_, let fields):
            if wide {
                let pairs = stride(from: 0, to: fields.count, by: 2).map { Array(fields[$0..<min($0 + 2, fields.count)]) }
                ForEach(Array(pairs.enumerated()), id: \.offset) { _, pair in
                    HStack(alignment: .top, spacing: 16) {
                        ForEach(pair, id: \.spec.id) { field in input(field, cell: true).frame(maxWidth: .infinity) }
                        if pair.count == 1 { Spacer().frame(maxWidth: .infinity) }
                    }
                }
            } else {
                ForEach(fields, id: \.spec.id) { field in input(field) }
            }
        case .range(_, let label, let help, let low, let high):
            VStack(alignment: .leading, spacing: 6) {
                Text(label)
                if !help.trimmingCharacters(in: .whitespaces).isEmpty {
                    RowNote(text: help)
                }
                HStack(alignment: .top, spacing: 12) {
                    input(low, withHelp: false, cell: true).frame(maxWidth: .infinity)
                    input(high, withHelp: false, cell: true).frame(maxWidth: .infinity)
                }
            }
            .padding(.vertical, 2)
        case .header, .records:
            EmptyView()
        }
    }

    private func input(_ field: FieldItem, withHelp: Bool = true, cell: Bool = false) -> some View {
        FieldInput(field: field, colors: colors, live: live, withHelp: withHelp, cell: cell) { value in
            act { $0.edit(.object([field.spec.id: value])) }
        }
        .id("\(formKey):\(field.spec.id)")
    }
}

/// One field of the form by kind, as a form row: a switch, a pop-up menu, a
/// number with − / +, a text field; its help or error under it. A `cell` (a
/// table's, a grid's) is compact: the name small above a bordered field, no
/// stepper.
struct FieldInput: View {
    let field: FieldItem
    let colors: AppColors
    var live = true
    var withHelp = true
    var cell = false
    var send: (JSONValue) -> Void = { _ in }

    var body: some View {
        let spec = field.spec
        let supporting = field.supporting(withHelp: withHelp)
        let error = field.error != nil
        VStack(alignment: .leading, spacing: 4) {
            if cell {
                Text(spec.label)
                    .font(.caption)
                    .foregroundColor(colors.secondaryLabel)
                    .lineLimit(1)
            }
            control(spec, error: error)
            if let supporting, !cell || error {
                RowNote(text: supporting, error: error)
            }
        }
    }

    @ViewBuilder
    private func control(_ spec: FieldSpec, error: Bool) -> some View {
        switch spec.kind {
        case .bool:
            Toggle(cell ? "" : spec.label, isOn: Binding(get: { field.checked }, set: { send(.bool($0)) }))
                .disabled(!field.enabled)
                .accessibilityLabel(spec.label)
                .accessibilityIdentifier("field-\(spec.id)")
        case .choice:
            Picker(cell ? "" : spec.label, selection: Binding(get: { field.choice?.label ?? "" }, set: { label in
                if let option = spec.choices.first(where: { $0.label == label }) { send(option.value) }
            })) {
                ForEach(spec.choices, id: \.label) { option in
                    Text(option.label).tag(option.label)
                }
            }
            .pickerStyle(.menu)
            .disabled(!field.enabled)
            .accessibilityLabel(spec.label)
            .accessibilityIdentifier("field-\(spec.id)")
        case .int, .float:
            if cell {
                EchoTextField(label: spec.label, value: field.text, error: error, enabled: field.enabled,
                              keyboard: .numbersAndPunctuation, alignment: .leading, bordered: true, live: live,
                              identifier: "field-\(spec.id)", change: { send(.string($0)) })
            } else {
                // Negative weights need the minus sign, which the number and decimal pads lack.
                NumberRow(label: spec.label, value: field.text, error: error, enabled: field.enabled, live: live,
                          keyboard: .numbersAndPunctuation, canDown: canStep(spec, field.text, -1),
                          canUp: canStep(spec, field.text, 1), identifier: "field-\(spec.id)",
                          change: { send(.string($0)) },
                          step: { delta in if let next = stepNumber(spec, field.text, delta) { send(.string(next)) } })
            }
        default:
            if cell {
                EchoTextField(label: spec.label, value: field.text, error: error, enabled: field.enabled,
                              keyboard: .asciiCapable, alignment: .leading, bordered: true, live: live,
                              identifier: "field-\(spec.id)", change: { send(.string($0)) })
            } else {
                HStack(spacing: 12) {
                    Text(spec.label)
                    EchoTextField(label: spec.label, value: field.text, error: error, enabled: field.enabled,
                                  keyboard: .asciiCapable, live: live, identifier: "field-\(spec.id)",
                                  change: { send(.string($0)) })
                }
            }
        }
    }
}

/// A records field (an ensemble's voices): each column's help once, then the
/// rows, each a section headed by its number and ↑, ↓, copy and ✕ (a table
/// row each when wide), and the add button.
struct RecordsInput: View {
    let item: RecordsItem
    var title: String?
    var blurb: String?
    let formKey: String
    let wide: Bool
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let spec = item.spec
        let columnHelp = spec.columns.filter { !$0.help.trimmingCharacters(in: .whitespaces).isEmpty }
        Section {
            ForEach(columnHelp, id: \.id) { column in
                RowNote(text: "\(column.label): \(column.help)")
            }
            if let error = item.error {
                RowNote(text: error, error: true)
            }
            if wide {
                ForEach(item.rows, id: \.index) { row in tableRow(row) }
            }
        } header: {
            if let title { Text(title) }
        } footer: {
            if let blurb { Text(blurb) }
        }
        if !wide {
            ForEach(item.rows, id: \.index) { row in
                Section {
                    ForEach(row.cells, id: \.spec.id) { field in cell(field, row, compact: false) }
                } header: {
                    HStack(spacing: 0) {
                        Text("\(row.index + 1)")
                        Spacer(minLength: 8)
                        buttons(row)
                    }
                    .textCase(nil)
                }
            }
        }
        Section {
            Button { act { $0.addRecord(spec.id) } } label: {
                Label(spec.addLabel ?? spec.label, systemImage: AppSymbols.add)
            }
            .disabled(!item.canAdd)
            .accessibilityIdentifier("records-add-\(spec.id)")
        } footer: {
            if let help = spec.addHelp { Text(help) }
        }
    }

    private func cell(_ field: FieldItem, _ row: RecordRow, compact: Bool) -> some View {
        FieldInput(field: field, colors: colors, live: live, withHelp: false, cell: compact) { value in
            act { $0.editCell(item.spec.id, index: row.index, column: field.spec.id, value: value) }
        }
        .id("\(formKey):\(item.spec.id):\(row.index):\(field.spec.id)")
    }

    private func buttons(_ row: RecordRow) -> some View {
        let spec = item.spec
        return HStack(spacing: 4) {
            iconButton(AppSymbols.moveUp, spec.moveUpHelp ?? "Move up", enabled: row.canMoveUp,
                       identifier: "row-\(row.index)-up") { act { $0.moveRecord(row.index, -1, spec.id) } }
            iconButton(AppSymbols.moveDown, spec.moveDownHelp ?? "Move down", enabled: row.canMoveDown,
                       identifier: "row-\(row.index)-down") { act { $0.moveRecord(row.index, 1, spec.id) } }
            iconButton(AppSymbols.copy, spec.duplicateHelp ?? "Duplicate", enabled: item.canAdd,
                       identifier: "row-\(row.index)-copy") { act { $0.duplicateRecord(row.index, spec.id) } }
            iconButton(AppSymbols.close, spec.removeHelp ?? spec.removeLabel ?? "Remove", enabled: item.canRemove,
                       identifier: "row-\(row.index)-remove") { act { $0.removeRecord(row.index, spec.id) } }
        }
    }

    private func iconButton(_ symbol: String, _ label: String, enabled: Bool, identifier: String,
                            action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.body)
                .frame(width: 40, height: 36)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(identifier)
    }

    /// A row as one line of a table: the columns side by side, weighted by
    /// width (the name 2, numbers 1.5, the rest 1), then the row's buttons.
    private func tableRow(_ row: RecordRow) -> some View {
        HStack(alignment: .center, spacing: 8) {
            WeightedRow(weights: row.cells.map { field in
                field.spec.id == "name" ? 2 : field.spec.kind.numeric ? 1.5 : 1
            }) {
                ForEach(row.cells, id: \.spec.id) { field in cell(field, row, compact: true) }
            }
            buttons(row)
        }
        .padding(.vertical, 2)
    }
}

/// Lays its subviews out side by side, each as wide as its share of the
/// weights (Compose's `Modifier.weight`).
struct WeightedRow: Layout {
    let weights: [Double]
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 600
        let widths = columnWidths(width, count: subviews.count)
        let height = zip(subviews, widths).map { $0.sizeThatFits(ProposedViewSize(width: $1, height: nil)).height }
            .max() ?? 0
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let widths = columnWidths(bounds.width, count: subviews.count)
        var x = bounds.minX
        for (subview, width) in zip(subviews, widths) {
            subview.place(at: CGPoint(x: x, y: bounds.minY), proposal: ProposedViewSize(width: width, height: nil))
            x += width + spacing
        }
    }

    private func columnWidths(_ width: CGFloat, count: Int) -> [CGFloat] {
        let used = (0..<count).map { $0 < weights.count ? weights[$0] : 1 }
        let total = used.reduce(0, +)
        let room = max(0, width - spacing * CGFloat(max(0, count - 1)))
        return used.map { room * CGFloat($0 / max(total, 0.0001)) }
    }
}

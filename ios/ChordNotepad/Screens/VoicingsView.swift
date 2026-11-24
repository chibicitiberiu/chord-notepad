import ChordNotepadKit
import SwiftUI

/// Settings › Voicings (Android's `VoicingsPage`): the voicings grouped by
/// model, each group's built-ins first (muted, with a lock), and the selected
/// one's form; both side by side when `split`, else the list, then the form
/// once a voicing is picked.
struct VoicingsPage: View {
    let schema: EditorSchema?
    let view: EditorView?
    let detail: Bool
    let split: Bool
    let colors: AppColors
    var live = true
    var addMenuShown = false
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        if let schema, let view {
            if split {
                HStack(spacing: 0) {
                    VoicingList(schema: schema, state: view.state, colors: colors, live: live,
                                addMenuShown: addMenuShown, act: act)
                        .frame(width: CGFloat(voicingsListWidth))
                        .frame(maxHeight: .infinity, alignment: .top)
                    Rule(colors: colors, vertical: true)
                    VoicingDetail(schema: schema, view: view, wide: true, colors: colors, live: live, act: act)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                }
            } else if detail && view.state.selected != nil {
                VoicingDetail(schema: schema, view: view, wide: false, colors: colors, live: live, act: act)
            } else {
                VoicingList(schema: schema, state: view.state, colors: colors, live: live, addMenuShown: addMenuShown,
                            act: act)
            }
        } else {
            Spinner(color: colors.primary.swiftUI, animated: live)
                .frame(width: 40, height: 40)
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
    let colors: AppColors
    var live = true
    var addMenuShown = false
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let list = VStack(alignment: .leading, spacing: 0) {
            AddVoicingButton(schema: schema, presets: state.addPresets(), colors: colors, live: live,
                             shown: addMenuShown) { preset in
                act { $0.addVoicingFrom(preset) }
            }
            .padding(.horizontal, 16)
            .zIndex(1)
            if let help = schema.help["tree_add"] {
                HelpText(text: help, colors: colors, indent: 0)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 4)
            }
            if !state.invalid.isEmpty {
                ErrorBanner(messages: [SettingsTexts.voicingsInvalidBanner], colors: colors)
                    .padding(16)
            }
            let builtin = state.showsBuiltin
            ForEach(state.groups, id: \.model) { group in
                SectionTitle(title: group.label, level: 1, colors: colors)
                    .padding(.horizontal, 16)
                if group.names.isEmpty && group.builtins.isEmpty {
                    HelpText(text: SettingsTexts.voicingsEmptyGroup, colors: colors, indent: 0)
                        .padding(.horizontal, 16)
                }
                ForEach(group.builtins, id: \.self) { label in
                    ListRow(headline: label, headlineColor: colors.muted.swiftUI,
                            selected: builtin && state.model == group.model && label == state.selected, colors: colors,
                            identifier: "builtin-\(label)",
                            action: { act { $0.selectBuiltin(model: group.model, label: label) } },
                            leading: { EmptyView() },
                            trailing: {
                                MdiIcon("settings_lock", tint: colors.muted.swiftUI, size: 18)
                                    .accessibilityLabel(SettingsTexts.voicingsBuiltin)
                            })
                }
                ForEach(group.names, id: \.self) { name in
                    let invalid = state.invalid.contains(name)
                    ListRow(headline: name, supporting: invalid ? SettingsTexts.voicingsInvalid : nil,
                            supportingColor: colors.error.swiftUI, selected: !builtin && name == state.selected,
                            colors: colors, identifier: "voicing-\(name)",
                            action: { act { $0.selectVoicing(name) } },
                            leading: {
                                if invalid { MdiIcon("settings_error", tint: colors.error.swiftUI) }
                            },
                            trailing: { EmptyView() })
                }
            }
        }
        .padding(.vertical, 8)
        if live {
            ScrollView { list }
        } else {
            list
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .clipped()
        }
    }
}

/// Add voicing: a menu of what the new voicing starts as (the blanks, then
/// the built-ins by model and the user's own voicings, each group under its
/// title). Live, iOS's menu; the catalog draws the open menu as a card.
struct AddVoicingButton: View {
    let schema: EditorSchema
    let presets: [VoicingPreset]
    let colors: AppColors
    var live = true
    var shown = false
    var pick: (VoicingPreset) -> Void = { _ in }

    var body: some View {
        let sections = addVoicingSections(presets, schema: schema)
        let button = IconTextLabel(icon: "settings_add", label: SettingsTexts.voicingsAdd, colors: colors,
                                   style: .tonal)
        if live {
            Menu {
                ForEach(Array(sections.enumerated()), id: \.offset) { _, section in
                    Section(section.title ?? "") {
                        ForEach(section.presets, id: \.label) { preset in
                            Button(preset.label) { pick(preset) }
                        }
                    }
                }
            } label: {
                button
            }
            .accessibilityIdentifier("voicings-add")
        } else {
            button
                .overlay(alignment: .topLeading) {
                    if shown { menuCard(sections).offset(y: 44) }
                }
        }
    }

    /// The open menu as Android draws it, for the catalog.
    private func menuCard(_ sections: [(title: String?, presets: [VoicingPreset])]) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(sections.enumerated()), id: \.offset) { index, section in
                if index > 0 { Rule(colors: colors).padding(.vertical, 4) }
                if let title = section.title {
                    Text(title)
                        .font(.caption.weight(.medium))
                        .foregroundColor(colors.primary.swiftUI)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                }
                ForEach(section.presets, id: \.label) { preset in
                    Text(preset.label)
                        .font(.body)
                        .foregroundColor(colors.text.swiftUI)
                        .lineLimit(1)
                        .padding(.horizontal, 12)
                        .frame(minHeight: 44, alignment: .leading)
                }
            }
        }
        .padding(.vertical, 8)
        .frame(width: 280, alignment: .leading)
        .background(colors.surfaceHigh.swiftUI, in: RoundedRectangle(cornerRadius: 4))
        .shadow(color: .black.opacity(0.2), radius: 6, y: 2)
        .fixedSize(horizontal: false, vertical: true)
    }
}

/// The selected voicing: name, model, remove, then the form under the
/// errors banner. A built-in shows read-only: its name as text with a lock
/// and Copy to a new voicing, the model and the form greyed, no remove.
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
                .foregroundColor(colors.muted.swiftUI)
                .multilineTextAlignment(.center)
                .padding(24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func detail(name: String, form: FormSpec) -> some View {
        let state = view.state
        let builtin = state.showsBuiltin
        let items = buildForm(form, values: view.values, errors: state.fieldErrors, hints: state.hints,
                              enabled: !builtin)
        let bannerKey = "\(name):\(state.model ?? "")"
        return VStack(spacing: 0) {
            if live ? banner.visible && state.hasErrors : state.hasErrors {
                ErrorBanner(messages: state.formErrors,
                            title: schema.text("errors_banner", fallback: "Fix these errors to apply changes"),
                            colors: colors)
                    .frame(maxWidth: 900)
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .accessibilityIdentifier("voicing-errors")
            }
            PageColumn(live: live, spacing: 8, maxWidth: 900) {
                if builtin {
                    builtinName(name)
                } else {
                    nameField(name)
                }
                DropdownField(label: schema.text("model_label"),
                              selected: schema.models.first { $0.model == state.model },
                              options: schema.models, optionLabel: { $0?.label ?? "" }, colors: colors, live: live,
                              supporting: schema.help["model"], enabled: !builtin, identifier: "voicing-model") { option in
                    act { $0.askModel(option.model) }
                }
                if !builtin {
                    IconTextButton(icon: "settings_delete", label: SettingsTexts.voicingsRemove, colors: colors,
                                   identifier: "voicing-remove") {
                        act { $0.askRemove(name) }
                    }
                }
                Rule(colors: colors).padding(.top, 8)
                VoicingFormItems(items: items, formKey: "\(name):\(state.model ?? ""):\(builtin)", wide: wide,
                                 colors: colors, live: live, act: act)
            }
        }
        .task(id: "\(bannerKey):\(state.hasErrors)") {
            guard live else { return }
            if banner.update(key: bannerKey, hasErrors: state.hasErrors) {
                try? await Task.sleep(for: .milliseconds(Int(draftSaveDelay * 1000)))
                if !Task.isCancelled { banner.delayElapsed(key: bannerKey) }
            }
        }
    }

    /// The voicing's name; tapping it (or the pencil) opens the rename dialog.
    private func nameField(_ name: String) -> some View {
        OutlinedBox(label: schema.text("name_label"), colors: colors, supporting: schema.help["name"],
                    background: colors.surface.swiftUI) {
            HStack(spacing: 0) {
                Text(name)
                    .font(.body)
                    .foregroundColor(colors.text.swiftUI)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 16)
                IconButton(icon: "settings_edit", label: SettingsTexts.voicingsRename, colors: colors,
                           identifier: "voicing-rename") {
                    act { $0.askRename(name) }
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { act { $0.askRename(name) } }
        }
    }

    /// A built-in's name, as text with a lock, and Copy to a new voicing;
    /// beside it when wide, under it on a phone.
    @ViewBuilder
    private func builtinName(_ name: String) -> some View {
        let title = VStack(alignment: .leading, spacing: 2) {
            Text(schema.text("name_label"))
                .font(.caption.weight(.medium))
                .foregroundColor(colors.muted.swiftUI)
            HStack(spacing: 8) {
                MdiIcon("settings_lock", tint: colors.muted.swiftUI, size: 18)
                    .accessibilityLabel(SettingsTexts.voicingsBuiltin)
                Text(name)
                    .font(.headline)
                    .foregroundColor(colors.text.swiftUI)
                    .lineLimit(2)
            }
        }
        let copy = IconTextButton(icon: "settings_content_copy", label: SettingsTexts.voicingsCopyBuiltin,
                                  colors: colors, style: .tonal, identifier: "voicing-copy") {
            act { $0.addVoicingFrom(VoicingPreset(group: view.state.model ?? "", label: name)) }
        }
        if wide {
            HStack(spacing: 16) {
                title.frame(maxWidth: .infinity, alignment: .leading)
                copy
            }
            .padding(.vertical, 4)
        } else {
            VStack(alignment: .leading, spacing: 8) {
                title
                copy
            }
            .padding(.vertical, 4)
        }
    }

    private func newerVersion(name: String) -> some View {
        PageColumn(live: live, spacing: 8, maxWidth: 900) {
            nameField(name)
            ForEach(Array(view.state.formErrors.enumerated()), id: \.offset) { _, note in
                Text(note).foregroundColor(colors.muted.swiftUI)
            }
            IconTextButton(icon: "settings_delete", label: SettingsTexts.voicingsRemove, colors: colors,
                           identifier: "voicing-remove") {
                act { $0.askRemove(name) }
            }
        }
    }
}

/// The voicing form: every ``FormItem`` drawn by kind. `formKey` names the
/// voicing and model (the fields start afresh when it changes); `wide` puts
/// grids in two columns and records in a table.
struct VoicingFormItems: View {
    let items: [FormItem]
    let formKey: String
    let wide: Bool
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(items, id: \.key) { item in
                switch item {
                case .header(_, let title, let blurb, let level):
                    SectionTitle(title: title, blurb: blurb, level: level, colors: colors)
                case .stack(_, let fields):
                    ForEach(fields, id: \.spec.id) { field in input(field) }
                case .grid(_, let fields):
                    grid(fields)
                case .range(_, let label, let help, let low, let high):
                    VStack(alignment: .leading, spacing: 2) {
                        Text(label).font(.body).foregroundColor(colors.text.swiftUI)
                        if !help.trimmingCharacters(in: .whitespaces).isEmpty {
                            Text(help).font(.caption).foregroundColor(colors.muted.swiftUI)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        HStack(alignment: .top, spacing: 12) {
                            input(low, withHelp: false).frame(maxWidth: .infinity)
                            input(high, withHelp: false).frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.top, 4)
                case .records(let records):
                    RecordsInput(item: records, formKey: formKey, wide: wide, colors: colors, live: live, act: act)
                }
            }
        }
    }

    @ViewBuilder
    private func grid(_ fields: [FieldItem]) -> some View {
        if wide {
            let pairs = stride(from: 0, to: fields.count, by: 2).map { Array(fields[$0..<min($0 + 2, fields.count)]) }
            ForEach(Array(pairs.enumerated()), id: \.offset) { _, pair in
                HStack(alignment: .top, spacing: 12) {
                    ForEach(pair, id: \.spec.id) { field in input(field).frame(maxWidth: .infinity) }
                    if pair.count == 1 { Spacer().frame(maxWidth: .infinity) }
                }
            }
        } else {
            ForEach(fields, id: \.spec.id) { field in input(field) }
        }
    }

    private func input(_ field: FieldItem, withHelp: Bool = true) -> some View {
        FieldInput(field: field, colors: colors, live: live, withHelp: withHelp) { value in
            act { $0.edit(.object([field.spec.id: value])) }
        }
        .id("\(formKey):\(field.spec.id)")
    }
}

/// One field of the form by kind. A `cell` (of a records row) is narrow: a
/// number has no − and + (it is typed) and the label stays on one line.
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
        switch spec.kind {
        case .bool:
            SwitchRow(label: spec.label, checked: field.checked, colors: colors, supporting: supporting,
                      enabled: field.enabled, identifier: "field-\(spec.id)") { send(.bool($0)) }
        case .choice:
            DropdownField(label: spec.label, selected: field.choice, options: spec.choices,
                          optionLabel: { $0?.label ?? "" }, colors: colors, live: live, supporting: supporting,
                          error: field.error != nil, enabled: field.enabled, identifier: "field-\(spec.id)") {
                send($0.value)
            }
        case .int, .float:
            FormField(label: spec.label, value: field.text, colors: colors, live: live, supporting: supporting,
                      error: field.error != nil, enabled: field.enabled,
                      // Negative weights need the minus sign, which the number and decimal pads lack.
                      keyboard: .numbersAndPunctuation, labelLines: cell ? 1 : nil,
                      identifier: "field-\(spec.id)", change: { send(.string($0)) }) {
                if !cell {
                    StepperButtons(label: spec.label, canDown: field.enabled && canStep(spec, field.text, -1),
                                   canUp: field.enabled && canStep(spec, field.text, 1), colors: colors,
                                   identifier: "field-\(spec.id)") { delta in
                        if let next = stepNumber(spec, field.text, delta) { send(.string(next)) }
                    }
                }
            }
        default:
            FormField(label: spec.label, value: field.text, colors: colors, live: live, supporting: supporting,
                      error: field.error != nil, enabled: field.enabled, keyboard: .asciiCapable,
                      labelLines: cell ? 1 : nil, identifier: "field-\(spec.id)", change: { send(.string($0)) })
        }
    }
}

/// A records field (an ensemble's voices): each column's help once, the
/// rows (a card each on a phone, a table row when wide) with ↑, ↓, copy and
/// ✕, and the add button.
struct RecordsInput: View {
    let item: RecordsItem
    let formKey: String
    let wide: Bool
    let colors: AppColors
    var live = true
    var act: (@escaping (inout SettingsController) -> Void) -> Void = { _ in }

    var body: some View {
        let spec = item.spec
        VStack(alignment: .leading, spacing: 8) {
            ForEach(spec.columns.filter { !$0.help.trimmingCharacters(in: .whitespaces).isEmpty }, id: \.id) { column in
                Text("\(column.label): \(column.help)")
                    .font(.caption)
                    .foregroundColor(colors.muted.swiftUI)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let error = item.error {
                Text(error).font(.caption).foregroundColor(colors.error.swiftUI)
            }
            ForEach(item.rows, id: \.index) { row in
                if wide { tableRow(row) } else { card(row) }
            }
            IconTextButton(icon: "settings_add", label: spec.addLabel ?? spec.label, colors: colors, style: .outlined,
                           enabled: item.canAdd, identifier: "records-add-\(spec.id)") {
                act { $0.addRecord(spec.id) }
            }
            if let help = spec.addHelp {
                HelpText(text: help, colors: colors, indent: 0)
            }
        }
    }

    private func cell(_ field: FieldItem, _ row: RecordRow) -> some View {
        FieldInput(field: field, colors: colors, live: live, withHelp: false, cell: true) { value in
            act { $0.editCell(item.spec.id, index: row.index, column: field.spec.id, value: value) }
        }
        .id("\(formKey):\(item.spec.id):\(row.index):\(field.spec.id)")
    }

    private func buttons(_ row: RecordRow) -> some View {
        let spec = item.spec
        return HStack(spacing: 0) {
            IconButton(icon: "settings_arrow_upward", label: spec.moveUpHelp ?? "Move up", colors: colors,
                       enabled: row.canMoveUp, identifier: "row-\(row.index)-up") {
                act { $0.moveRecord(row.index, -1, spec.id) }
            }
            IconButton(icon: "settings_arrow_downward", label: spec.moveDownHelp ?? "Move down", colors: colors,
                       enabled: row.canMoveDown, identifier: "row-\(row.index)-down") {
                act { $0.moveRecord(row.index, 1, spec.id) }
            }
            IconButton(icon: "settings_content_copy", label: spec.duplicateHelp ?? "Duplicate", colors: colors,
                       enabled: item.canAdd, identifier: "row-\(row.index)-copy") {
                act { $0.duplicateRecord(row.index, spec.id) }
            }
            IconButton(icon: "settings_close", label: spec.removeHelp ?? spec.removeLabel ?? "Remove", colors: colors,
                       enabled: item.canRemove, identifier: "row-\(row.index)-remove") {
                act { $0.removeRecord(row.index, spec.id) }
            }
        }
    }

    /// A row as one line of a table: the columns side by side, weighted by
    /// width (the name 2, numbers 1.5, the rest 1), then the row's buttons.
    private func tableRow(_ row: RecordRow) -> some View {
        HStack(alignment: .center, spacing: 8) {
            WeightedRow(weights: row.cells.map { field in
                field.spec.id == "name" ? 2 : field.spec.kind.numeric ? 1.5 : 1
            }) {
                ForEach(row.cells, id: \.spec.id) { field in cell(field, row) }
            }
            buttons(row)
        }
    }

    /// A row as a card: its number and buttons, the name, then the other
    /// text columns two per line and each number on a line of its own.
    private func card(_ row: RecordRow) -> some View {
        let first = row.cells.first
        let rest = Array(row.cells.dropFirst())
        let texts = rest.filter { !$0.spec.kind.numeric }
        let numbers = rest.filter { $0.spec.kind.numeric }
        let pairs = stride(from: 0, to: texts.count, by: 2).map { Array(texts[$0..<min($0 + 2, texts.count)]) }
        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 0) {
                Text("\(row.index + 1)")
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(colors.text.swiftUI)
                    .frame(maxWidth: .infinity, alignment: .leading)
                buttons(row)
            }
            VStack(alignment: .leading, spacing: 4) {
                if let first { cell(first, row) }
                ForEach(Array(pairs.enumerated()), id: \.offset) { _, pair in
                    HStack(alignment: .top, spacing: 8) {
                        ForEach(pair, id: \.spec.id) { field in cell(field, row).frame(maxWidth: .infinity) }
                        if pair.count == 1 { Spacer().frame(maxWidth: .infinity) }
                    }
                }
                ForEach(numbers, id: \.spec.id) { field in cell(field, row) }
            }
            .padding(.trailing, 8)
        }
        .padding(.leading, 12)
        .padding(.trailing, 4)
        .padding(.bottom, 12)
        .background(colors.surfaceLow.swiftUI, in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .contain)
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

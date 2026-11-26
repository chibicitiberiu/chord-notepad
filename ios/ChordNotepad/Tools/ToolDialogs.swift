import ChordNotepadKit
import SwiftUI
import UIKit

// The Edit ribbon's dialogs, ported from Android's ui/tools/ToolDialogs.kt:
// Transpose, Suggest Capo and the six Insert directive dialogs. Each is an
// iOS form sheet: the title and Cancel / the confirming button in a
// navigation bar, the fields in an inset grouped form. The main screen
// presents them; the catalog draws them in a sheet's frame. What they hold
// lives in the kit (`ToolsUiState`).

// MARK: - Transpose

/// Transpose: −11..+11 semitones for the selection or, with none, the whole
/// song (the desktop's dialog).
struct TransposeDialog: View {
    let hasSelection: Bool
    let form: TransposeForm
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: TransposeTexts.title,
                      cancel: BarButton(title: "Cancel") { event(.dismiss) },
                      confirm: BarButton(title: "OK", identifier: "transpose-ok") { event(.transposeOK) }) {
            Form {
                Section {
                    Text(hasSelection ? TransposeTexts.selection : TransposeTexts.wholeSong)
                    Stepper(onIncrement: form.canUp ? { event(.transposeUp) } : nil,
                            onDecrement: form.canDown ? { event(.transposeDown) } : nil) {
                        HStack {
                            Text(TransposeTexts.semitones)
                            Spacer(minLength: 8)
                            Text(form.display)
                                .font(.body.monospacedDigit())
                                .foregroundColor(colors.secondaryLabel)
                                .accessibilityIdentifier("transpose-value")
                        }
                    }
                    .accessibilityValue(form.display)
                    .accessibilityIdentifier("transpose")
                } footer: {
                    Text(TransposeTexts.hint)
                }
            }
        }
        .accessibilityIdentifier("transpose-dialog")
    }
}

// MARK: - Suggest Capo

/// Suggest Capo: the session's `CapoAdviceState`. The voicing at the top (a
/// new one scores again), a spinner while the capos are scored, then the
/// ranked rows, the recommended one first and checked. Apply waits while a
/// song plays, with a hint, since the session refuses the edit then.
struct CapoDialog: View {
    let state: CapoAdviceState
    let chosen: Int?
    let canApply: Bool
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: CapoTexts.title,
                      cancel: BarButton(title: "Cancel") { event(.capoCancel) },
                      confirm: BarButton(title: CapoTexts.apply, enabled: canApply, identifier: "capo-apply") {
                          event(.capoApply)
                      }) {
            Form {
                Section {
                    Picker(CapoTexts.voicing, selection: Binding(get: { state.voicing }, set: { value in
                        if value != state.voicing { event(.capoVoicing(value)) }
                    })) {
                        ForEach(state.voicings, id: \.value) { voicing in
                            Text(voicing.label).tag(voicing.value)
                        }
                    }
                    .pickerStyle(.menu)
                    .accessibilityIdentifier("capo-voicing")
                } header: {
                    if !state.scope.isEmpty {
                        Text(state.scope)
                            .textCase(nil)
                    }
                } footer: {
                    Text(CapoTexts.hint)
                }
                Section {
                    if state.computing {
                        HStack(spacing: 12) {
                            ProgressView()
                            Text(CapoTexts.finding)
                                .foregroundColor(colors.secondaryLabel)
                        }
                    }
                    ForEach(state.rows, id: \.capo) { row in
                        capoRow(row, selected: row.capo == chosen)
                    }
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        if !state.message.isEmpty {
                            Text(state.message)
                                .foregroundColor(state.status == CapoAdviceState.errorStatus ? colors.red : nil)
                        }
                        if state.playing {
                            Text(CapoTexts.stopToApply)
                        }
                    }
                }
            }
        }
        .accessibilityIdentifier("capo-dialog")
    }

    /// One capo position: the capo as the headline with its ease at the
    /// right, the shapes below, then the tags; a checkmark on the chosen one.
    private func capoRow(_ row: CapoRow, selected: Bool) -> some View {
        Button { event(.capoPick(row.capo)) } label: {
            HStack(alignment: .center, spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(row.headline)
                            .font(.body.weight(.semibold))
                        Spacer(minLength: 8)
                        if row.capo > 0 {
                            Text(row.ease)
                                .font(.footnote)
                                .foregroundColor(colors.secondaryLabel)
                        }
                    }
                    Text(row.shapes)
                        .fixedSize(horizontal: false, vertical: true)
                    if let tags = row.tags {
                        Text(tags)
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(.tint)
                    }
                }
                .foregroundColor(colors.label)
                Image(systemName: AppSymbols.checkmark)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.tint)
                    .opacity(selected ? 1 : 0)
                    .accessibilityHidden(true)
            }
            .padding(.vertical, 2)
            .contentShape(Rectangle())
        }
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
        .accessibilityIdentifier("capo-row-\(row.capo)")
    }
}

// MARK: - Insert

/// ＋ Insert › a directive: its fields, as the desktop's dialogs have them.
/// The session checks the fields as they change; what's wrong shows under
/// them in red and Insert stays off until a clean reply for exactly these
/// fields. Insert Capo has Suggest, which opens Suggest Capo instead.
struct InsertDirectiveDialog: View {
    let request: InsertDirectiveRequest
    let state: DirectiveFormState
    let verdict: DirectiveVerdict
    let keys: [String]
    let units: [Int]
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    @FocusState private var focused: Bool

    var body: some View {
        let kind = state.form.kind
        SheetScaffold(title: kind.title,
                      cancel: BarButton(title: InsertTexts.cancel) { event(.directiveCancel) },
                      confirm: BarButton(title: InsertTexts.insert, enabled: verdict.canInsert,
                                         identifier: "insert-ok") { event(.directiveInsert) }) {
            Form {
                Section {
                    fields(state.form)
                } footer: {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(verdict.messages, id: \.self) { message in
                            Text(message)
                                .foregroundColor(colors.red)
                        }
                        Text(kind.hint)
                    }
                }
                if kind == .capo {
                    Section {
                        Button(InsertTexts.suggest) { event(.directiveSuggest) }
                            .accessibilityIdentifier("insert-suggest")
                    }
                }
            }
        }
        .task {
            guard live else { return }
            focused = true
        }
        .accessibilityIdentifier("insert-dialog-\(kind.wire)")
    }

    @ViewBuilder
    private func fields(_ form: DirectiveForm) -> some View {
        switch form.kind {
        case .bpm:
            textField(InsertTexts.bpmField, form.bpm, keyboard: .numberPad) { text in
                var next = form
                next.bpm = text
                return next
            }
        case .time:
            picker(InsertTexts.beats, String(form.beats), DirectiveForm.beatsRange.map(String.init)) { value in
                var next = form
                next.beats = Int(value) ?? form.beats
                return next
            }
            picker(InsertTexts.unit, String(form.unit), units.map(String.init)) { value in
                var next = form
                next.unit = Int(value) ?? form.unit
                return next
            }
        case .key:
            picker(InsertTexts.keyField, form.key, keys) { value in
                var next = form
                next.key = value
                return next
            }
        case .label:
            textField(InsertTexts.labelField, form.label, keyboard: .default) { text in
                var next = form
                next.label = text
                return next
            }
        case .capo:
            textField(InsertTexts.capoField, form.capo, keyboard: .numberPad) { text in
                var next = form
                next.capo = text
                return next
            }
        case .loop:
            picker(InsertTexts.loopLabel, form.loopLabel, loopChoices(request)) { value in
                var next = form
                next.loopLabel = value
                return next
            }
            Stepper(onIncrement: form.count < DirectiveForm.countRange.upperBound
                        ? { event(.directiveChanged(form.moreRepeats())) } : nil,
                    onDecrement: form.count > DirectiveForm.countRange.lowerBound
                        ? { event(.directiveChanged(form.fewerRepeats())) } : nil) {
                HStack {
                    Text(InsertTexts.loopCount)
                    Spacer(minLength: 8)
                    Text(String(form.count))
                        .font(.body.monospacedDigit())
                        .foregroundColor(colors.secondaryLabel)
                        .accessibilityIdentifier("loop-count-value")
                }
            }
            .accessibilityValue(String(form.count))
            .accessibilityIdentifier("loop-count")
        }
    }

    /// A typed field in a form row: its name on the left, the value typed on
    /// the right; it takes the keyboard when the sheet opens.
    private func textField(_ label: String, _ text: String, keyboard: UIKeyboardType,
                           change: @escaping (String) -> DirectiveForm) -> some View {
        LabeledContent(label) {
            TextField("", text: Binding(get: { text }, set: { event(.directiveChanged(change($0))) }))
                .multilineTextAlignment(.trailing)
                .keyboardType(keyboard)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .focused($focused)
                .onSubmit { event(.directiveInsert) }
                .foregroundColor(verdict.messages.isEmpty ? nil : colors.red)
                .accessibilityIdentifier("insert-field")
        }
    }

    /// A choice in a form row: the system's pop-up menu.
    private func picker(_ label: String, _ value: String, _ options: [String],
                        change: @escaping (String) -> DirectiveForm) -> some View {
        Picker(label, selection: Binding(get: { value }, set: { event(.directiveChanged(change($0))) })) {
            ForEach(options, id: \.self) { option in
                Text(option).tag(option)
            }
        }
        .pickerStyle(.menu)
        .accessibilityIdentifier("picker-\(label)")
    }
}

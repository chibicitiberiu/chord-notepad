import ChordNotepadKit
import SwiftUI
import UIKit

// The Edit ribbon's dialogs and the sheets' small dialogs, ported from
// Android's ui/tools/ToolDialogs.kt and the speed and tempo dialogs of
// ui/sheets/: Transpose, Suggest Capo, the six Insert directive dialogs,
// Manual… speed and the tempo default. Cards in the app's colours over a
// dimmed screen, like the rename dialog, so they stack over a sheet and the
// catalog draws them. What they hold lives in the kit (`ToolsUiState`).

/// A dialog card whose content scrolls when it doesn't fit (live), or is cut
/// at the window's height (the catalog). A tap on the dimmed screen dismisses.
struct ToolDialog<Content: View, Buttons: View>: View {
    let title: String
    let colors: AppColors
    var live = true
    var identifier: String?
    var dismiss: () -> Void = {}
    @ViewBuilder let content: () -> Content
    @ViewBuilder let buttons: () -> Buttons

    @State private var contentHeight: CGFloat = 0

    var body: some View {
        GeometryReader { geometry in
            let room = max(geometry.size.height - 48, 160)
            ZStack {
                Color.black.opacity(0.32)
                    .ignoresSafeArea()
                    .onTapGesture { dismiss() }
                VStack(alignment: .leading, spacing: 14) {
                    Text(title)
                        .font(.title3)
                        .foregroundColor(colors.text.swiftUI)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                    contentArea(room: room)
                    HStack(spacing: 8) {
                        Spacer(minLength: 0)
                        buttons()
                    }
                }
                .padding(22)
                .frame(maxWidth: 360)
                .background(colors.surfaceHigh.swiftUI, in: RoundedRectangle(cornerRadius: 24))
                .frame(maxHeight: room)
                .padding(24)
                .accessibilityIdentifier(identifier ?? "dialog")
            }
            .frame(width: geometry.size.width, height: geometry.size.height)
        }
        .dynamicTypeSize(...DynamicTypeSize.accessibility2)
    }

    @ViewBuilder
    private func contentArea(room: CGFloat) -> some View {
        let column = VStack(alignment: .leading, spacing: 0, content: content)
            .frame(maxWidth: .infinity, alignment: .leading)
        if live {
            ScrollView {
                column.onGeometryChange(for: CGFloat.self, of: { $0.size.height }) { contentHeight = $0 }
            }
            .scrollBounceBehavior(.basedOnSize)
            .frame(maxHeight: contentHeight > 0 ? contentHeight : nil)
        } else {
            // The content whole when it fits, else cut at the room left.
            ViewThatFits(in: .vertical) {
                column.fixedSize(horizontal: false, vertical: true)
                column.fixedSize(horizontal: false, vertical: true)
                    .frame(maxHeight: max(room - 150, 60), alignment: .top).clipped()
            }
        }
    }
}

/// A one-line field with its label on the outline (Android's
/// `OutlinedTextField`): a live TextField that takes the keyboard at once, or
/// its text drawn in the catalog.
struct OutlinedField: View {
    let label: String
    let text: String
    let colors: AppColors
    var live = true
    var suffix: String?
    var error = false
    var keyboard: UIKeyboardType = .asciiCapable
    /// Takes the keyboard when it appears (the Insert dialogs, Manual…, the
    /// tempo); the identifier's field waits for a tap, so the piano stays in view.
    var autofocus = true
    var identifier: String?
    var change: (String) -> Void = { _ in }
    var submit: () -> Void = {}

    @FocusState private var focused: Bool

    var body: some View {
        let accent = (error ? colors.error : colors.primary).swiftUI
        HStack(spacing: 4) {
            if live {
                TextField("", text: Binding(get: { text }, set: { change($0) }))
                    .keyboardType(keyboard)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .focused($focused)
                    .onSubmit(submit)
                    .onAppear { if autofocus { focused = true } }
                    .accessibilityLabel(label)
                    .accessibilityIdentifier(identifier ?? "field-\(label)")
            } else {
                Text(text.isEmpty ? " " : text)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            if let suffix {
                Text(suffix).foregroundColor(colors.muted.swiftUI)
            }
        }
        .font(.body)
        .foregroundColor(colors.text.swiftUI)
        .padding(.horizontal, 14)
        .frame(minHeight: 52)
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(accent, lineWidth: 2))
        .overlay(alignment: .topLeading) {
            if !label.isEmpty {
                Text(label)
                    .font(.caption)
                    .foregroundColor(accent)
                    .padding(.horizontal, 4)
                    .background(colors.surfaceHigh.swiftUI)
                    .offset(x: 10, y: -8)
            }
        }
        .padding(.top, 6)
    }
}

/// A labelled dropdown (the desktop's read-only comboboxes): the label, then
/// an outlined capsule with the value and ▾; live, a menu of the options.
struct DialogPicker: View {
    let label: String
    let value: String
    let options: [String]
    let colors: AppColors
    var live = true
    var identifier: String?
    var pick: (String) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.subheadline.weight(.medium))
                .foregroundColor(colors.text.swiftUI)
            if live && !options.isEmpty {
                Menu {
                    ForEach(options, id: \.self) { option in
                        Button(option) { pick(option) }
                    }
                } label: { capsule }
                .accessibilityLabel(label)
                .accessibilityValue(value)
                .accessibilityIdentifier(identifier ?? "picker-\(label)")
            } else {
                capsule
            }
        }
    }

    private var capsule: some View {
        HStack(spacing: 6) {
            Text(value)
                .font(.subheadline.weight(.medium))
                .foregroundColor(colors.text.swiftUI)
                .lineLimit(1)
            Image(systemName: "arrowtriangle.down.fill")
                .font(.system(size: 8))
                .foregroundColor(colors.text.swiftUI)
                .accessibilityHidden(true)
        }
        .padding(.horizontal, 24)
        .frame(minHeight: 40)
        .overlay(Capsule().stroke(colors.line.swiftUI, lineWidth: 1))
        .contentShape(Capsule())
    }
}

/// −/+ around a value.
struct ValueStepper: View {
    let value: String
    let colors: AppColors
    var canDown = true
    var canUp = true
    let downLabel: String
    let upLabel: String
    var identifier = "stepper"
    var down: () -> Void = {}
    var up: () -> Void = {}

    var body: some View {
        HStack(spacing: 0) {
            button("−", enabled: canDown, label: downLabel, id: "\(identifier)-down", action: down)
            Text(value)
                .font(.headline)
                .foregroundColor(colors.text.swiftUI)
                .frame(width: 40)
                .accessibilityIdentifier("\(identifier)-value")
            button("+", enabled: canUp, label: upLabel, id: "\(identifier)-up", action: up)
        }
    }

    private func button(_ text: String, enabled: Bool, label: String, id: String,
                        action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text)
                .font(.title2)
                .foregroundColor(colors.text.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }
}

// MARK: - The sheets' dialogs

/// The small dialog Manual… opens: a number field, 12.5–400, checked before OK.
struct SpeedDialog: View {
    let entry: SpeedEntry
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        ToolDialog(title: SpeedTexts.title, colors: colors, live: live, identifier: "speed-dialog",
                   dismiss: { event(.back) }) {
            OutlinedField(label: "", text: entry.text, colors: colors, live: live, suffix: "%",
                          error: entry.showError, keyboard: .decimalPad, identifier: "speed-field",
                          change: { event(.speedTyped($0)) }, submit: { event(.speedOK) })
                .frame(width: 160)
            Text(entry.supportingText)
                .font(.caption)
                .foregroundColor((entry.showError ? colors.error : colors.muted).swiftUI)
                .padding(.leading, 16)
                .padding(.top, 4)
        } buttons: {
            DialogButton(label: "Cancel", colors: colors) { event(.back) }
            DialogButton(label: "OK", colors: colors) { event(.speedOK) }
                .accessibilityIdentifier("speed-ok")
        }
    }
}

/// The tempo default, typed (the session parses and clamps it).
struct TempoDialog: View {
    let text: String
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        ToolDialog(title: "Tempo", colors: colors, live: live, identifier: "tempo-dialog",
                   dismiss: { event(.tempoCancel) }) {
            OutlinedField(label: "", text: text, colors: colors, live: live, suffix: "bpm", keyboard: .numberPad,
                          identifier: "tempo-field", change: { event(.tempoTyped($0)) }, submit: { event(.tempoOK) })
                .frame(width: 160)
        } buttons: {
            DialogButton(label: "Cancel", colors: colors) { event(.tempoCancel) }
            DialogButton(label: "OK", colors: colors,
                         enabled: !text.trimmingCharacters(in: .whitespaces).isEmpty) { event(.tempoOK) }
        }
    }
}

// MARK: - The ribbon's dialogs

/// Transpose: −11..+11 semitones for the selection or, with none, the whole
/// song (the desktop's dialog).
struct TransposeDialog: View {
    let hasSelection: Bool
    let form: TransposeForm
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        ToolDialog(title: TransposeTexts.title, colors: colors, live: live, identifier: "transpose-dialog",
                   dismiss: { event(.dismiss) }) {
            Text(hasSelection ? TransposeTexts.selection : TransposeTexts.wholeSong)
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
            Text(TransposeTexts.hint)
                .font(.subheadline)
                .foregroundColor(colors.muted.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)
                .padding(.bottom, 12)
            HStack {
                Text(TransposeTexts.semitones)
                    .font(.subheadline)
                    .foregroundColor(colors.text.swiftUI)
                Spacer(minLength: 8)
                ValueStepper(value: form.display, colors: colors, canDown: form.canDown, canUp: form.canUp,
                             downLabel: TransposeTexts.down, upLabel: TransposeTexts.up, identifier: "transpose",
                             down: { event(.transposeDown) }, up: { event(.transposeUp) })
            }
        } buttons: {
            DialogButton(label: "Cancel", colors: colors) { event(.dismiss) }
            DialogButton(label: "OK", colors: colors) { event(.transposeOK) }
                .accessibilityIdentifier("transpose-ok")
        }
    }
}

/// Suggest Capo: the session's `CapoAdviceState`. The voicing at the top (a
/// new one scores again), a spinner while the capos are scored, then the
/// ranked rows, the recommended one first and chosen. Apply waits while a
/// song plays, with a hint, since the session refuses the edit then.
struct CapoDialog: View {
    let state: CapoAdviceState
    let chosen: Int?
    let canApply: Bool
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        ToolDialog(title: CapoTexts.title, colors: colors, live: live, identifier: "capo-dialog",
                   dismiss: { event(.capoCancel) }) {
            Text(CapoTexts.hint)
                .font(.subheadline)
                .foregroundColor(colors.muted.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, 12)
            if !state.scope.isEmpty {
                Text(state.scope)
                    .font(.subheadline.weight(.bold))
                    .foregroundColor(colors.muted.swiftUI)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 12)
            }
            DialogPicker(label: CapoTexts.voicing, value: state.voicingLabel, options: state.voicings.map(\.label),
                         colors: colors, live: live, identifier: "capo-voicing") { label in
                if let value = state.voicings.first(where: { $0.label == label })?.value {
                    event(.capoVoicing(value))
                }
            }
            .padding(.bottom, 12)
            if state.computing {
                HStack(spacing: 12) {
                    Spinner(color: colors.primary.swiftUI, animated: live)
                        .frame(width: 24, height: 24)
                    Text(CapoTexts.finding)
                        .font(.subheadline)
                        .foregroundColor(colors.text.swiftUI)
                }
                .padding(.vertical, 12)
            }
            ForEach(state.rows, id: \.capo) { row in
                capoRow(row, selected: row.capo == chosen)
            }
            if !state.message.isEmpty {
                Text(state.message)
                    .font(.subheadline)
                    .foregroundColor((state.status == CapoAdviceState.errorStatus ? colors.error : colors.muted).swiftUI)
                    .padding(.top, 8)
            }
            if state.playing {
                Text(CapoTexts.stopToApply)
                    .font(.caption)
                    .foregroundColor(colors.muted.swiftUI)
                    .padding(.top, 8)
            }
        } buttons: {
            DialogButton(label: "Cancel", colors: colors) { event(.capoCancel) }
            DialogButton(label: CapoTexts.apply, colors: colors, enabled: canApply) { event(.capoApply) }
                .accessibilityIdentifier("capo-apply")
        }
    }

    /// One capo position: a radio, the capo as the headline with its ease at
    /// the right, the shapes as the main line below, then the tags.
    private func capoRow(_ row: CapoRow, selected: Bool) -> some View {
        Button { event(.capoPick(row.capo)) } label: {
            HStack(alignment: .center, spacing: 12) {
                RadioMark(on: selected, colors: colors)
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(row.headline)
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(colors.text.swiftUI)
                        Spacer(minLength: 8)
                        if row.capo > 0 {
                            Text(row.ease)
                                .font(.caption)
                                .foregroundColor(colors.muted.swiftUI)
                        }
                    }
                    Text(row.shapes)
                        .font(.body)
                        .foregroundColor(colors.text.swiftUI)
                        .fixedSize(horizontal: false, vertical: true)
                    if let tags = row.tags {
                        Text(tags)
                            .font(.caption.weight(.medium))
                            .foregroundColor(colors.primary.swiftUI)
                    }
                }
            }
            .padding(.vertical, 10)
            .frame(minHeight: 56)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
        .accessibilityIdentifier("capo-row-\(row.capo)")
    }
}

/// A spinning arc (Android's indeterminate progress), drawn so the catalog shows it.
struct Spinner: View {
    let color: Color
    var animated = true
    @State private var turning = false

    var body: some View {
        Circle()
            .trim(from: 0, to: 0.7)
            .stroke(color, style: StrokeStyle(lineWidth: 3, lineCap: .round))
            .rotationEffect(.degrees(turning ? 360 : 0))
            .onAppear {
                guard animated else { return }
                withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) { turning = true }
            }
    }
}

/// ＋ Insert › a directive: its fields, as the desktop's dialogs have them.
/// The session checks the fields as they change; what's wrong shows under
/// them and Insert stays off until a clean reply for exactly these fields.
struct InsertDirectiveDialog: View {
    let request: InsertDirectiveRequest
    let state: DirectiveFormState
    let verdict: DirectiveVerdict
    let keys: [String]
    let units: [Int]
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let kind = state.form.kind
        ToolDialog(title: kind.title, colors: colors, live: live, identifier: "insert-dialog-\(kind.wire)",
                   dismiss: { event(.directiveCancel) }) {
            Text(kind.hint)
                .font(.subheadline)
                .foregroundColor(colors.muted.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, 12)
            fields(state.form)
            ForEach(verdict.messages, id: \.self) { message in
                Text(message)
                    .font(.caption)
                    .foregroundColor(colors.error.swiftUI)
                    .padding(.top, 8)
            }
        } buttons: {
            if kind == .capo {
                DialogButton(label: InsertTexts.suggest, colors: colors) { event(.directiveSuggest) }
            }
            DialogButton(label: InsertTexts.cancel, colors: colors) { event(.directiveCancel) }
            DialogButton(label: InsertTexts.insert, colors: colors, enabled: verdict.canInsert) {
                event(.directiveInsert)
            }
            .accessibilityIdentifier("insert-ok")
        }
    }

    @ViewBuilder
    private func fields(_ form: DirectiveForm) -> some View {
        let submit = { event(.directiveInsert) }
        switch form.kind {
        case .bpm:
            OutlinedField(label: InsertTexts.bpmField, text: form.bpm, colors: colors, live: live,
                          error: !verdict.messages.isEmpty, identifier: "insert-field") { text in
                var next = form
                next.bpm = text
                event(.directiveChanged(next))
            } submit: { submit() }
        case .time:
            HStack(alignment: .bottom, spacing: 12) {
                DialogPicker(label: InsertTexts.beats, value: String(form.beats),
                             options: DirectiveForm.beatsRange.map(String.init), colors: colors, live: live) {
                    var next = form
                    next.beats = Int($0) ?? form.beats
                    event(.directiveChanged(next))
                }
                Text("/")
                    .font(.title2)
                    .foregroundColor(colors.text.swiftUI)
                    .padding(.bottom, 6)
                DialogPicker(label: InsertTexts.unit, value: String(form.unit), options: units.map(String.init),
                             colors: colors, live: live) {
                    var next = form
                    next.unit = Int($0) ?? form.unit
                    event(.directiveChanged(next))
                }
            }
        case .key:
            DialogPicker(label: InsertTexts.keyField, value: form.key, options: keys, colors: colors, live: live) {
                var next = form
                next.key = $0
                event(.directiveChanged(next))
            }
        case .label:
            OutlinedField(label: InsertTexts.labelField, text: form.label, colors: colors, live: live,
                          error: !verdict.messages.isEmpty, identifier: "insert-field") { text in
                var next = form
                next.label = text
                event(.directiveChanged(next))
            } submit: { submit() }
        case .capo:
            OutlinedField(label: InsertTexts.capoField, text: form.capo, colors: colors, live: live,
                          error: !verdict.messages.isEmpty, keyboard: .numberPad, identifier: "insert-field") { text in
                var next = form
                next.capo = text
                event(.directiveChanged(next))
            } submit: { submit() }
        case .loop:
            VStack(alignment: .leading, spacing: 8) {
                DialogPicker(label: InsertTexts.loopLabel, value: form.loopLabel, options: loopChoices(request),
                             colors: colors, live: live) {
                    var next = form
                    next.loopLabel = $0
                    event(.directiveChanged(next))
                }
                HStack {
                    Text(InsertTexts.loopCount)
                        .font(.subheadline)
                        .foregroundColor(colors.text.swiftUI)
                    Spacer(minLength: 8)
                    ValueStepper(value: String(form.count), colors: colors,
                                 canDown: form.count > DirectiveForm.countRange.lowerBound,
                                 canUp: form.count < DirectiveForm.countRange.upperBound,
                                 downLabel: InsertTexts.fewer, upLabel: InsertTexts.more, identifier: "loop-count",
                                 down: { event(.directiveChanged(form.fewerRepeats())) },
                                 up: { event(.directiveChanged(form.moreRepeats())) })
                }
            }
        }
    }
}

import ChordNotepadKit
import SwiftUI
import UIKit

// The rows Settings' forms share, in iOS's look: a name on the left and its
// value typed on the right, a stepper for numbers, help under the row in the
// secondary colour (red when the value is wrong). The forms themselves are
// the system's grouped lists.

/// A text field over a value that lives elsewhere (Android's
/// `StateTextField`): what the user types stays as typed; the value replaces
/// it only when it becomes something this field didn't send (the kit's
/// ``FieldEcho``). `id` it by what it edits, so another voicing starts afresh.
struct EchoTextField: View {
    let label: String
    let value: String
    var error = false
    var enabled = true
    var keyboard: UIKeyboardType = .default
    var alignment: TextAlignment = .trailing
    var bordered = false
    /// Put the cursor here once (Edit in the problems dialog: Android's P8).
    var focusNow = false
    var focusShown: () -> Void = {}
    var live = true
    var identifier: String?
    var change: (String) -> Void = { _ in }

    @State private var echo: FieldEcho
    @FocusState private var focused: Bool

    init(label: String, value: String, error: Bool = false, enabled: Bool = true,
         keyboard: UIKeyboardType = .default, alignment: TextAlignment = .trailing, bordered: Bool = false,
         focusNow: Bool = false, focusShown: @escaping () -> Void = {}, live: Bool = true,
         identifier: String? = nil, change: @escaping (String) -> Void = { _ in }) {
        self.label = label
        self.value = value
        self.error = error
        self.enabled = enabled
        self.keyboard = keyboard
        self.alignment = alignment
        self.bordered = bordered
        self.focusNow = focusNow
        self.focusShown = focusShown
        self.live = live
        self.identifier = identifier
        self.change = change
        _echo = State(initialValue: FieldEcho(value))
    }

    var body: some View {
        TextField(label, text: Binding(get: { echo.text }, set: { text in
            echo.typed(text)
            change(text)
        }))
        .multilineTextAlignment(alignment)
        .keyboardType(keyboard)
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .submitLabel(.done)
        .focused($focused)
        .disabled(!enabled)
        .foregroundColor(error ? Color(uiColor: .systemRed) : enabled ? nil : Color(uiColor: .tertiaryLabel))
        .modifier(RoundedFieldStyle(on: bordered))
        .accessibilityLabel(label)
        .modifier(AlertIdentifier(id: identifier ?? "field-\(label)"))
        .onChange(of: value) { _, new in echo.valueChanged(new) }
        .onAppear { if focusNow { requestFocus() } }
        .onChange(of: focusNow) { _, now in if now { requestFocus() } }
    }

    private func requestFocus() {
        guard live else { return }
        focused = true
        focusShown()
    }
}

/// The system's rounded border, when asked for (a field in a table's cell).
private struct RoundedFieldStyle: ViewModifier {
    let on: Bool

    func body(content: Content) -> some View {
        if on {
            content.textFieldStyle(.roundedBorder)
        } else {
            content
        }
    }
}

/// A number's row: its name, the number typed (right-aligned), and the
/// system's − / + stepper, each half off at a bound; at the accessibility
/// text sizes the field and stepper go under the name.
struct NumberRow: View {
    let label: String
    let value: String
    var error = false
    var enabled = true
    var live = true
    var keyboard: UIKeyboardType = .numberPad
    var canDown = true
    var canUp = true
    var showsStepper = true
    var focusNow = false
    var focusShown: () -> Void = {}
    var identifier: String?
    var change: (String) -> Void = { _ in }
    var step: (Int) -> Void = { _ in }

    @Environment(\.dynamicTypeSize) private var textSize

    var body: some View {
        let field = EchoTextField(label: label, value: value, error: error, enabled: enabled, keyboard: keyboard,
                                  alignment: textSize.isAccessibilitySize ? .leading : .trailing,
                                  focusNow: focusNow, focusShown: focusShown, live: live, identifier: identifier,
                                  change: change)
        if textSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: 6) {
                Text(label)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    field
                    stepper
                }
            }
        } else {
            HStack(spacing: 12) {
                Text(label)
                    .fixedSize(horizontal: false, vertical: true)
                field
                    .frame(minWidth: 60)
                stepper
            }
        }
    }

    @ViewBuilder
    private var stepper: some View {
        if showsStepper {
            Stepper(label, onIncrement: enabled && canUp ? { step(1) } : nil,
                    onDecrement: enabled && canDown ? { step(-1) } : nil)
                .labelsHidden()
                .fixedSize()
                .accessibilityIdentifier("\(identifier ?? label)-stepper")
        }
    }
}

/// Help or an error under a row, inside its cell (a form with several
/// fields to a section).
struct RowNote: View {
    let text: String
    var error = false

    var body: some View {
        Text(text)
            .font(.footnote)
            .foregroundColor(error ? Color(uiColor: .systemRed) : Color(uiColor: .secondaryLabel))
            .fixedSize(horizontal: false, vertical: true)
    }
}

/// An error card in a form: the error mark, `title` (if any) over `messages`.
struct ErrorBanner: View {
    let messages: [String]
    var title: String?
    let colors: AppColors

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: AppSymbols.error)
                .foregroundStyle(colors.red)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                if let title {
                    Text(title).font(.subheadline.weight(.semibold))
                }
                ForEach(Array(messages.enumerated()), id: \.offset) { _, message in
                    Text(message).font(.subheadline)
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityElement(children: .combine)
    }
}

/// A page's back button in its navigation bar, to `title` (a page drawn by
/// the main screen, not pushed: the system's Back isn't there). iOS 26's is
/// the chevron alone; before it, the chevron and the title.
struct BackButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            if glassAlerts {
                Image(systemName: AppSymbols.back)
                    .fontWeight(.semibold)
            } else {
                HStack(spacing: 4) {
                    Image(systemName: AppSymbols.back)
                        .fontWeight(.semibold)
                    Text(title)
                }
            }
        }
        .accessibilityLabel(title)
        .accessibilityIdentifier("page-back")
    }
}

extension View {
    /// A full page's navigation bar: its title inline, Back to `back` (or
    /// Done when `back` is nil), as a pushed page or a presented one has it.
    func pageBar(title: String, back: String?, action: @escaping () -> Void) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let back {
                    ToolbarItem(placement: .topBarLeading) { BackButton(title: back, action: action) }
                } else {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(sheetDone, action: action)
                            .fontWeight(.semibold)
                            .accessibilityIdentifier("page-back")
                    }
                }
            }
    }
}

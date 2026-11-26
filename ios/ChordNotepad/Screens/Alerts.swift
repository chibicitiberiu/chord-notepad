import ChordNotepadKit
import SwiftUI

// Alerts drawn by the screen in the system's alert look (`UIAlertController`
// up to iOS 18, iOS 26's rounder card with capsule buttons): the title, the
// message, an optional text field, the buttons. The app presents the
// system's own `.alert` where it can; these are for
// - a dialog with a field whose state must stay in it (Rename keeps the
//   session's refusal under the field; a voicing's rename keeps OK off while
//   the name is blank), which a system alert can't (it reads its buttons and
//   message once, and any button closes it);
// - the unsaved-changes question, which can arrive while a sheet is up or
//   going away, when a system alert can't be presented;
// - the catalog's pictures of the system alerts (it draws, it can't present).
// "Preparing export…" (`ExportProgressDialog`) is drawn the same way.

/// One of an alert's buttons.
struct AlertAction {
    enum Role { case normal, cancel, destructive, preferred }

    let title: String
    var role = Role.normal
    var enabled = true
    var identifier: String?
    let action: () -> Void
}

/// Whether the system draws iOS 26's alerts (rounder, capsule buttons).
var glassAlerts: Bool {
    if #available(iOS 26, *) { return true }
    return false
}

/// An alert over a dimmed screen, as the system draws one.
struct AlertCard<Field: View>: View {
    let title: String
    var message: String?
    let actions: [AlertAction]
    /// False in the catalog: no material (a solid colour), no focus.
    var live = true
    var identifier: String?
    @ViewBuilder var field: () -> Field

    @Environment(\.colorScheme) private var scheme
    /// The title, message and field's height, for the scroll view around them.
    @State private var textHeight: CGFloat = 0
    @Environment(\.dynamicTypeSize) private var textSize

    /// Two buttons side by side, as the system lays them out; stacked at the
    /// accessibility text sizes, as the system does there.
    private var sideBySide: Bool { actions.count == 2 && !textSize.isAccessibilitySize }

    var body: some View {
        GeometryReader { window in
            ZStack {
                Color.black.opacity(0.2).ignoresSafeArea()
                card(maxHeight: max(window.size.height - 48, 160))
            }
            .frame(width: window.size.width, height: window.size.height)
        }
    }

    private func card(maxHeight: CGFloat) -> some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                    if let message, !message.isEmpty {
                        Text(message)
                            .font(.footnote)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    field()
                        .padding(.top, 10)
                }
                .foregroundColor(Color(uiColor: .label))
                .padding(.horizontal, 16)
                .padding(.top, 20)
                .padding(.bottom, glassAlerts ? 14 : 16)
                .onGeometryChange(for: CGFloat.self, of: { $0.size.height }) { textHeight = $0 }
            }
            .scrollBounceBehavior(.basedOnSize)
            // As tall as the text, up to most of the window (the largest text sizes scroll).
            .frame(height: min(textHeight > 0 ? textHeight : 120, maxHeight * 0.6))
            buttons
        }
        .frame(width: glassAlerts ? 300 : 270)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: glassAlerts ? 34 : 14, style: .continuous))
        .frame(maxHeight: maxHeight)
        .accessibilityElement(children: .contain)
        .modifier(AlertIdentifier(id: identifier))
    }

    @ViewBuilder
    private var buttons: some View {
        if glassAlerts {
            // iOS 26: capsules inside the card, side by side for two, else stacked.
            let stacked = !sideBySide
            let layout = stacked ? AnyLayout(VStackLayout(spacing: 8)) : AnyLayout(HStackLayout(spacing: 8))
            layout {
                ForEach(Array(ordered.enumerated()), id: \.offset) { _, action in
                    Button(action: action.action) {
                        Text(action.title)
                            .font(.body.weight(action.role == .preferred ? .semibold : .medium))
                            .lineLimit(2)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity, minHeight: 34)
                    }
                    .buttonStyle(.bordered)
                    .buttonBorderShape(.capsule)
                    .controlSize(.large)
                    .tint(tint(action))
                    .disabled(!action.enabled)
                    .modifier(AlertIdentifier(id: action.identifier))
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
        } else {
            // Up to iOS 18: full-width text buttons under hairlines, two side by side.
            VStack(spacing: 0) {
                Divider()
                if sideBySide {
                    HStack(spacing: 0) {
                        textButton(ordered[0])
                        Divider().frame(height: 44)
                        textButton(ordered[1])
                    }
                } else {
                    ForEach(Array(ordered.enumerated()), id: \.offset) { index, action in
                        if index > 0 { Divider() }
                        textButton(action)
                    }
                }
            }
        }
    }

    /// The system's order: Cancel on the left of two side by side, else last.
    private var ordered: [AlertAction] {
        let cancel = actions.filter { $0.role == .cancel }
        let others = actions.filter { $0.role != .cancel }
        return sideBySide ? cancel + others : others + cancel
    }

    private func tint(_ action: AlertAction) -> Color {
        switch action.role {
        case .destructive: return .red
        case .preferred: return .accentColor
        default: return Color(uiColor: .label)
        }
    }

    private func textButton(_ action: AlertAction) -> some View {
        Button(action: action.action) {
            Text(action.title)
                .font(action.role == .cancel || action.role == .preferred ? .body.weight(.semibold) : .body)
                .foregroundColor(action.role == .destructive ? .red : nil)
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity, minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .disabled(!action.enabled)
        .modifier(AlertIdentifier(id: action.identifier))
    }

    @ViewBuilder
    private var background: some View {
        if live {
            Rectangle().fill(.regularMaterial)
        } else {
            // The material over a dimmed screen, as UIKit's alert shows it.
            Color(white: scheme == .dark ? 0.17 : 0.95)
        }
    }
}

extension AlertCard where Field == EmptyView {
    init(title: String, message: String? = nil, actions: [AlertAction], live: Bool = true,
         identifier: String? = nil) {
        self.init(title: title, message: message, actions: actions, live: live, identifier: identifier,
                  field: { EmptyView() })
    }
}

/// An alert's text field, as UIAlertController draws one: a thin border
/// around the system's background, the placeholder in grey.
struct AlertTextField: View {
    let placeholder: String
    @Binding var text: String
    var live = true
    var keyboard: UIKeyboardType = .default
    var identifier: String?
    var submit: () -> Void = {}

    @FocusState private var focused: Bool

    var body: some View {
        TextField(placeholder, text: $text)
            .font(.subheadline)
            .keyboardType(keyboard)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .submitLabel(.done)
            .focused($focused)
            .onSubmit(submit)
            .padding(.horizontal, 7)
            .frame(minHeight: 30)
            .background(Color(uiColor: .systemBackground), in: RoundedRectangle(cornerRadius: glassAlerts ? 10 : 6))
            .overlay(RoundedRectangle(cornerRadius: glassAlerts ? 10 : 6)
                .stroke(Color(uiColor: .separator), lineWidth: 0.5))
            .task {
                guard live else { return }
                focused = true
            }
            .modifier(AlertIdentifier(id: identifier))
    }
}

/// An accessibility identifier when there is one.
struct AlertIdentifier: ViewModifier {
    let id: String?

    func body(content: Content) -> some View {
        if let id {
            content.accessibilityIdentifier(id)
        } else {
            content
        }
    }
}

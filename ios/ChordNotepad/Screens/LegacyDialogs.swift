import ChordNotepadKit
import SwiftUI

// The old dialog card and its buttons, for the Settings pages until they are
// redrawn as iOS lists (the next step of the iOS look). Not for new code.

struct ToolDialog<Content: View, Buttons: View>: View {
    let title: String
    let colors: AppColors
    var live = true
    var identifier: String?
    var dismiss: () -> Void = {}
    @ViewBuilder let content: () -> Content
    @ViewBuilder let buttons: () -> Buttons

    var body: some View {
        ZStack {
            Color.black.opacity(0.2).ignoresSafeArea()
                .onTapGesture { dismiss() }
            VStack(alignment: .leading, spacing: 14) {
                Text(title)
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
                VStack(alignment: .leading, spacing: 0, content: content)
                HStack(spacing: 8) {
                    Spacer(minLength: 0)
                    buttons()
                }
            }
            .padding(20)
            .frame(maxWidth: 340)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .padding(24)
            .accessibilityIdentifier(identifier ?? "dialog")
        }
    }
}

struct DialogButton: View {
    let label: String
    let colors: AppColors
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(label, action: action)
            .buttonStyle(.borderless)
            .disabled(!enabled)
            .frame(minHeight: 44)
    }
}

struct Spinner: View {
    let color: Color
    var animated = true

    var body: some View {
        ProgressView()
    }
}

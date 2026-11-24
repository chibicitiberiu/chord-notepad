import ChordNotepadKit
import SwiftUI

/// The ☰ menu: a panel from the leading edge over a dimmed screen (Android's
/// drawer, without its edge swipe), with Android's entries (``AppMenu``).
/// Entries the iOS app can't do yet are greyed with "Coming soon".
struct AppMenuPanel: View {
    let recent: [DocumentRef]
    let colors: AppColors
    /// False in the catalog: no ScrollView (ImageRenderer can't draw one).
    var scrolls = true
    var choose: (MenuAction) -> Void = { _ in }
    var close: () -> Void = {}

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Color.black.opacity(0.32)
                    .ignoresSafeArea()
                    .onTapGesture { close() }
                    .accessibilityLabel("Close the menu")
                    .accessibilityAddTraits(.isButton)
                Group {
                    if scrolls {
                        ScrollView { content }
                    } else {
                        content.frame(maxHeight: .infinity, alignment: .top).clipped()
                    }
                }
                .frame(width: min(300, geometry.size.width * 0.85))
                .frame(maxHeight: .infinity)
                // The panel runs the screen's whole height, under the status
                // bar and the home indicator, as Android's drawer does; its
                // entries stay inside the safe area.
                .background(alignment: .leading) {
                    UnevenRoundedRectangle(bottomTrailingRadius: 16, topTrailingRadius: 16)
                        .fill(colors.surfaceLow.swiftUI)
                        .ignoresSafeArea()
                }
                .accessibilityIdentifier("app-menu")
            }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Chord Notepad")
                .font(.title3.weight(.medium))
                .foregroundColor(colors.text.swiftUI)
                .padding(.horizontal, 14)
                .padding(.top, 4)
                .padding(.bottom, 10)
            ForEach(Array(AppMenu.sections(recent: recent).enumerated()), id: \.offset) { pair in
                switch pair.element {
                case .entries(let entries):
                    ForEach(entries, id: \.self) { item($0) }
                case .recent(let entries):
                    Text("Recent".uppercased())
                        .font(.caption.weight(.medium))
                        .foregroundColor(colors.muted.swiftUI)
                        .padding(.horizontal, 14)
                        .padding(.top, 12)
                        .padding(.bottom, 4)
                    if entries.isEmpty {
                        Text("No recent songs")
                            .font(.footnote)
                            .foregroundColor(colors.muted.swiftUI)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                    }
                    ForEach(entries, id: \.self) { item($0) }
                case .separator:
                    colors.line.swiftUI
                        .frame(height: 1)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.top, 24)
        .padding(.bottom, 10)
    }

    private func item(_ entry: MenuEntry) -> some View {
        Button {
            close()
            choose(entry.action)
        } label: {
            HStack(spacing: 14) {
                MdiIcon(entry.icon, tint: entry.tint.swiftUI)
                VStack(alignment: .leading, spacing: 1) {
                    Text(entry.label)
                        .font(.subheadline)
                        .foregroundColor(colors.text.swiftUI)
                        .lineLimit(1)
                    if !entry.enabled {
                        Text("Coming soon")
                            .font(.caption2)
                            .foregroundColor(colors.muted.swiftUI)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 46)
            .contentShape(Capsule())
            .opacity(entry.enabled ? 1 : 0.45)
        }
        .buttonStyle(.plain)
        .disabled(!entry.enabled)
        .accessibilityLabel(entry.enabled ? entry.label : "\(entry.label), coming soon")
        .accessibilityIdentifier("menu-\(entry.label)")
    }
}

/// A small dialog over a dimmed screen, in the app's colours (the catalog can
/// draw it, unlike an alert).
struct DialogCard<Content: View, Buttons: View>: View {
    let title: String
    let colors: AppColors
    @ViewBuilder let content: () -> Content
    @ViewBuilder let buttons: () -> Buttons

    var body: some View {
        ZStack {
            Color.black.opacity(0.32).ignoresSafeArea()
            VStack(alignment: .leading, spacing: 14) {
                Text(title)
                    .font(.title3)
                    .foregroundColor(colors.text.swiftUI)
                content()
                HStack(spacing: 8) {
                    Spacer(minLength: 0)
                    buttons()
                }
            }
            .padding(22)
            .frame(maxWidth: 360)
            .background(colors.surfaceHigh.swiftUI, in: RoundedRectangle(cornerRadius: 24))
            .padding(24)
        }
    }
}

/// A dialog's text button in the primary colour.
struct DialogButton: View {
    let label: String
    let colors: AppColors
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.subheadline.weight(.medium))
                .foregroundColor(colors.primary.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                .padding(.horizontal, 12)
                .frame(minHeight: 40)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }
}

/// Rename (tap the title; Android's `RenameDialog`): the name without its
/// extension, and "Saved as “name.txt”" under it, or why the name can't be
/// used; the session's refusal stays here until the name changes.
struct RenameDialog: View {
    let displayName: String
    let colors: AppColors
    @Binding var name: String
    var refusal: String?
    /// False in the catalog: the field is drawn as text (ImageRenderer can't draw a TextField).
    var live = true
    var rename: (String) -> Void = { _ in }
    var cancel: () -> Void = {}

    @FocusState private var focused: Bool

    var body: some View {
        let problem = renameProblem(name, currentDisplayName: displayName)
        let hint = renameHint(name, currentDisplayName: displayName, refusal: refusal)
        DialogCard(title: "Rename", colors: colors) {
            VStack(alignment: .leading, spacing: 6) {
                field(error: hint.error)
                Text(hint.text)
                    .font(.caption)
                    .foregroundColor((hint.error ? colors.error : colors.muted).swiftUI)
                    .padding(.leading, 2)
                    .accessibilityIdentifier("rename-hint")
            }
        } buttons: {
            DialogButton(label: "Cancel", colors: colors, action: cancel)
            DialogButton(label: "Rename", colors: colors, enabled: problem == nil || problem == .unchanged) {
                submit(problem)
            }
        }
    }

    private func submit(_ problem: RenameProblem?) {
        if problem == nil {
            rename(name.trimmingCharacters(in: .whitespacesAndNewlines))
        } else if problem == .unchanged {
            cancel()
        }
    }

    @ViewBuilder
    private func field(error: Bool) -> some View {
        let border = (error ? colors.error : colors.primary).swiftUI
        if live {
            TextField("Name", text: $name)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .focused($focused)
                .onSubmit { submit(renameProblem(name, currentDisplayName: displayName)) }
                .padding(12)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(border, lineWidth: 2))
                .onAppear { focused = true }
                .accessibilityIdentifier("rename-field")
        } else {
            Text(name)
                .foregroundColor(colors.text.swiftUI)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(border, lineWidth: 2))
        }
    }
}

/// The storage couldn't rename (Android's `RenameFailedDialog`): why, and
/// Save As under the new name when that's the way out.
struct RenameFailedDialog: View {
    let name: String
    let reason: String
    let canSaveAs: Bool
    let colors: AppColors
    var saveAs: (String) -> Void = { _ in }
    var dismiss: () -> Void = {}

    var body: some View {
        DialogCard(title: "Couldn't rename", colors: colors) {
            Text(canSaveAs ? "\(reason)\n\nSave a copy under the new name instead?" : reason)
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
        } buttons: {
            if canSaveAs {
                DialogButton(label: "Cancel", colors: colors, action: dismiss)
                DialogButton(label: "Save as…", colors: colors) { saveAs(name) }
            } else {
                DialogButton(label: "OK", colors: colors, action: dismiss)
            }
        }
    }
}

/// The unsaved-changes question (Android's `ConfirmDiscardDialog`, the
/// desktop's "Unsaved Changes"): Don't save, Cancel, Save. The buttons stack
/// when they don't fit on one line (large text), as Android's flow row wraps.
struct DiscardDialog: View {
    let colors: AppColors
    var answer: (DiscardChoice) -> Void = { _ in }

    var body: some View {
        DialogCard(title: DiscardQuestion.title, colors: colors) {
            Text(DiscardQuestion.message)
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
        } buttons: {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) { buttons }
                VStack(alignment: .trailing, spacing: 0) { buttons }
            }
        }
        .accessibilityIdentifier("discard-dialog")
    }

    @ViewBuilder
    private var buttons: some View {
        DialogButton(label: DiscardQuestion.discard, colors: colors) { answer(.discard) }
        DialogButton(label: DiscardQuestion.cancel, colors: colors) { answer(.cancel) }
        DialogButton(label: DiscardQuestion.save, colors: colors) { answer(.save) }
    }
}

/// Examples (Android's `ExamplesSheet`): the songs the app ships, by file
/// name; a tap opens a copy of one.
struct ExamplesSheet: View {
    let names: [String]
    let colors: AppColors
    var scrolls = true
    var choose: (String) -> Void = { _ in }
    var done: () -> Void = {}

    var body: some View {
        PlayerSheet(title: "Examples", colors: colors, scrolls: scrolls, done: done) {
            ForEach(names, id: \.self) { name in
                Button { choose(name) } label: {
                    HStack(spacing: 14) {
                        MdiIcon("mdi_file_music", tint: MenuTint.examples.color.swiftUI)
                        Text(name)
                            .font(.body)
                            .foregroundColor(colors.text.swiftUI)
                            .lineLimit(1)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 20)
                    .frame(minHeight: 48)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("example-\(name)")
            }
        }
    }
}

/// A snackbar at the bottom (Android's): the session's status in Edit, errors
/// in both modes with a close button.
struct SnackbarView: View {
    let snackbar: Snackbar
    let colors: AppColors
    var dismiss: () -> Void = {}

    var body: some View {
        HStack(spacing: 8) {
            Text(snackbar.text)
                .font(.subheadline)
                .foregroundColor(colors.snackText.swiftUI)
                // An error's reason comes after its action and the document
                // ("Failed to open file:", the location, then why): keep it.
                .lineLimit(snackbar.error ? 12 : 3)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            if snackbar.error {
                Button(action: dismiss) {
                    Image(systemName: "xmark")
                        .font(.footnote.weight(.semibold))
                        .foregroundColor(colors.snackText.swiftUI)
                        .frame(width: 32, height: 32)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Close")
            }
        }
        .padding(.leading, 16)
        .padding(.trailing, snackbar.error ? 6 : 16)
        .padding(.vertical, 10)
        .frame(maxWidth: 560)
        .background(colors.snackBackground.swiftUI, in: RoundedRectangle(cornerRadius: 6))
        .padding(.horizontal, 12)
        .padding(.bottom, 12)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("snackbar")
    }
}

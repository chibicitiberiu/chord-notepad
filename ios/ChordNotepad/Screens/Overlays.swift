import ChordNotepadKit
import SwiftUI

/// The ☰ menu: a panel from the leading edge over a dimmed screen (Android's
/// drawer, without its edge swipe), drawn as an iPad's sidebar: the app's
/// name, then Android's entries (``AppMenu``) in inset grouped sections with
/// their symbols in the accent colour. It scrolls, and an entry's name wraps
/// at the largest text sizes. An entry the app can't do (none now) is greyed
/// with "Coming soon".
struct AppMenuPanel: View {
    let recent: [DocumentRef]
    let colors: AppColors
    var scrolls = true
    var choose: (MenuAction) -> Void = { _ in }
    var close: () -> Void = {}

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Color.black.opacity(0.25)
                    .ignoresSafeArea()
                    .onTapGesture { close() }
                    .accessibilityLabel("Close the menu")
                    .accessibilityAddTraits(.isButton)
                list
                    .frame(width: min(320, geometry.size.width * 0.85))
                    .frame(maxHeight: .infinity)
                    // The panel runs the screen's whole height, under the status
                    // bar and the home indicator, as Android's drawer does; its
                    // entries stay inside the safe area.
                    .background(alignment: .leading) {
                        UnevenRoundedRectangle(bottomTrailingRadius: 16, topTrailingRadius: 16, style: .continuous)
                            .fill(colors.groupedBackground)
                            .ignoresSafeArea()
                            .shadow(color: .black.opacity(0.15), radius: 12)
                    }
                    .accessibilityIdentifier("app-menu")
            }
        }
    }

    private var list: some View {
        List {
            Section {
            } header: {
                Text("Chord Notepad")
                    .font(.title2.weight(.bold))
                    .foregroundColor(colors.label)
                    .textCase(nil)
                    .padding(.top, 8)
                    .accessibilityAddTraits(.isHeader)
            }
            ForEach(Array(AppMenu.sections(recent: recent).enumerated()), id: \.offset) { pair in
                switch pair.element {
                case .entries(let entries):
                    Section {
                        ForEach(entries, id: \.self) { item($0) }
                    }
                case .recent(let entries):
                    Section("Recent") {
                        if entries.isEmpty {
                            Text("No recent songs")
                                .foregroundColor(colors.secondaryLabel)
                        }
                        ForEach(entries, id: \.self) { item($0) }
                    }
                case .separator:
                    EmptyView()
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
    }

    private func item(_ entry: MenuEntry) -> some View {
        Button {
            close()
            choose(entry.action)
        } label: {
            Label {
                VStack(alignment: .leading, spacing: 1) {
                    Text(entry.label)
                        .foregroundColor(colors.label)
                        .fixedSize(horizontal: false, vertical: true)
                    if !entry.enabled {
                        Text("Coming soon")
                            .font(.caption)
                            .foregroundColor(colors.secondaryLabel)
                    }
                }
            } icon: {
                Image(systemName: entry.icon)
                    .foregroundStyle(.tint)
            }
            .opacity(entry.enabled ? 1 : 0.45)
        }
        .disabled(!entry.enabled)
        .accessibilityLabel(entry.enabled ? entry.label : "\(entry.label), coming soon")
        .accessibilityIdentifier("menu-\(entry.label)")
    }
}

/// Rename (tap the title; Android's `RenameDialog`), as an alert with a
/// field: the name without its extension, and "Saved as “name.txt”" under
/// it, or why the name can't be used; the session's refusal stays here until
/// the name changes (so it is drawn: a system alert closes on any button).
struct RenameDialog: View {
    let displayName: String
    let colors: AppColors
    @Binding var name: String
    var refusal: String?
    /// False in the catalog: no focus, no material.
    var live = true
    var rename: (String) -> Void = { _ in }
    var cancel: () -> Void = {}

    var body: some View {
        let problem = renameProblem(name, currentDisplayName: displayName)
        let hint = renameHint(name, currentDisplayName: displayName, refusal: refusal)
        AlertCard(title: "Rename",
                  actions: [AlertAction(title: "Cancel", role: .cancel, action: cancel),
                            AlertAction(title: "Rename", role: .preferred,
                                        enabled: problem == nil || problem == .unchanged,
                                        identifier: "rename-ok") { submit(problem) }],
                  live: live, identifier: "rename-dialog") {
            VStack(alignment: .leading, spacing: 6) {
                AlertTextField(placeholder: "Name", text: $name, live: live, identifier: "rename-field") {
                    submit(renameProblem(name, currentDisplayName: displayName))
                }
                Text(hint.text)
                    .font(.caption)
                    .foregroundColor(hint.error ? colors.red : colors.secondaryLabel)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("rename-hint")
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
}

/// The storage couldn't rename (Android's `RenameFailedDialog`): why, and
/// Save As under the new name when that's the way out. Live it is the
/// system's alert (`MainScreen`); this is the catalog's picture of it.
struct RenameFailedDialog: View {
    let name: String
    let reason: String
    let canSaveAs: Bool
    let colors: AppColors
    var live = true
    var saveAs: (String) -> Void = { _ in }
    var dismiss: () -> Void = {}

    static let title = "Couldn't rename"

    static func message(reason: String, canSaveAs: Bool) -> String {
        canSaveAs ? "\(reason)\n\nSave a copy under the new name instead?" : reason
    }

    var body: some View {
        AlertCard(title: Self.title, message: Self.message(reason: reason, canSaveAs: canSaveAs),
                  actions: canSaveAs
                      ? [AlertAction(title: "Cancel", role: .cancel, action: dismiss),
                         AlertAction(title: "Save as…", role: .preferred) { saveAs(name) }]
                      : [AlertAction(title: "OK", role: .preferred, action: dismiss)],
                  live: live)
    }
}

/// "Preparing export…" while an export renders and is written, until the
/// export picker is up (docs/IOS.md "Files", Exports): drawn as iOS draws an
/// alert. A system spinner, the audio export's percentage, Cancel; system
/// fonts, the system material and tint.
struct ExportProgressDialog: View {
    let dialog: ExportDialog
    /// False in the catalog: a solid colour for the material.
    var live = true
    var cancel: () -> Void = {}

    @Environment(\.colorScheme) private var scheme

    var body: some View {
        ZStack {
            Color.black.opacity(0.2).ignoresSafeArea()
            VStack(spacing: 0) {
                VStack(spacing: 14) {
                    Text(ExportDialog.title)
                        .font(.headline)
                        .multilineTextAlignment(.center)
                    ProgressView()
                        .progressViewStyle(.circular)
                        .controlSize(.large)
                    if let percent = dialog.percent {
                        Text(percent)
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 20)
                .padding(.bottom, glassAlerts ? 16 : 18)
                cancelButton
            }
            .frame(width: glassAlerts ? 300 : 270)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: glassAlerts ? 34 : 14, style: .continuous))
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("export-dialog")
        }
    }

    /// iOS 26's alerts: a capsule button inside the card; before it, a
    /// full-width text button under a hairline.
    @ViewBuilder
    private var cancelButton: some View {
        if glassAlerts {
            Button(role: .cancel, action: cancel) {
                Text(ExportDialog.cancel)
                    .font(.body.weight(.medium))
                    .frame(maxWidth: .infinity, minHeight: 34)
            }
            .buttonStyle(.bordered)
            .buttonBorderShape(.capsule)
            .controlSize(.large)
            .tint(Color.primary)
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
            .accessibilityIdentifier("export-cancel")
        } else {
            Divider()
            Button(role: .cancel, action: cancel) {
                Text(ExportDialog.cancel)
                    .font(.body)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.borderless)
            .accessibilityIdentifier("export-cancel")
        }
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

/// The unsaved-changes question (Android's `ConfirmDiscardDialog`, the
/// desktop's "Unsaved Changes"): Save, Don't save, Cancel, stacked as the
/// system stacks three buttons. Drawn, not the system's alert: the session
/// can ask while a sheet is up or going away (Examples, a song from Files),
/// when the system can't present one.
struct DiscardDialog: View {
    let colors: AppColors
    var live = true
    var answer: (DiscardChoice) -> Void = { _ in }

    var body: some View {
        AlertCard(title: DiscardQuestion.title, message: DiscardQuestion.message,
                  actions: [AlertAction(title: DiscardQuestion.save, role: .preferred) { answer(.save) },
                            AlertAction(title: DiscardQuestion.discard, role: .destructive) { answer(.discard) },
                            AlertAction(title: DiscardQuestion.cancel, role: .cancel) { answer(.cancel) }],
                  live: live, identifier: "discard-dialog")
    }
}

/// A short message at the bottom (Android's snackbar), drawn as iOS draws a
/// banner: the session's status in Edit, errors in both modes with a red mark
/// and a close button, on the system material.
struct SnackbarView: View {
    let snackbar: Snackbar
    let colors: AppColors
    var dismiss: () -> Void = {}

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if snackbar.error {
                Image(systemName: AppSymbols.error)
                    .foregroundStyle(colors.red)
                    .accessibilityHidden(true)
            }
            Text(snackbar.text)
                .font(.subheadline)
                .foregroundColor(colors.label)
                // An error's reason comes after its action and the document
                // ("Failed to open file:", the location, then why): keep it.
                .lineLimit(snackbar.error ? 12 : 3)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            if snackbar.error {
                Button(action: dismiss) {
                    Image(systemName: AppSymbols.close)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(colors.secondaryLabel)
                        .frame(width: 32, height: 32)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(AccessibilityLabels.close)
            }
        }
        .padding(.leading, 16)
        .padding(.trailing, snackbar.error ? 6 : 16)
        .padding(.vertical, 12)
        .frame(maxWidth: 560)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(colors.separator, lineWidth: 0.5))
        .shadow(color: .black.opacity(0.15), radius: 10, y: 3)
        .padding(.horizontal, 12)
        .padding(.bottom, 12)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("snackbar")
    }
}

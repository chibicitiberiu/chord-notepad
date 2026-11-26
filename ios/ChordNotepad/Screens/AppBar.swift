import ChordNotepadKit
import SwiftUI

/// What the app bar's buttons do; nil in the catalog (inert).
struct AppBarActions {
    var menu: () -> Void
    var rename: () -> Void
    var mode: (AppMode) -> Void
    var save: () -> Void
}

/// The 48 pt app bar, drawn as iOS draws a navigation bar: ☰ and Save as
/// symbols in the accent colour, the song's title (• while modified; tap to
/// rename) and the Edit / Play segmented control. `trailing` fills the rest
/// of the line (phone landscape Edit: the Edit ribbon, with the title kept to
/// `titleMaxWidth`). Its layout is Android's `AppBar.kt`.
struct AppBar<Trailing: View>: View {
    let title: String
    let modified: Bool
    let mode: AppMode
    let colors: AppColors
    /// The segments' words (a phone at the accessibility text sizes shows the icons).
    var tabLabels = true
    var titleMaxWidth: CGFloat?
    var actions: AppBarActions?
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(spacing: 0) {
            BarIconButton(symbol: AppSymbols.menu, label: AccessibilityLabels.menu) { actions?.menu() }
                .accessibilityIdentifier("menu")
            titleButton
                .frame(maxWidth: titleMaxWidth ?? .infinity, alignment: .leading)
                .layoutPriority(1)
            ModeTabs(mode: mode, labels: tabLabels) { actions?.mode($0) }
                .layoutPriority(2)
            BarIconButton(symbol: AppSymbols.save, label: AccessibilityLabels.save, enabled: modified) {
                actions?.save()
            }
            .layoutPriority(2)
            .accessibilityIdentifier("save")
            trailing()
        }
        .padding(.horizontal, 4)
        .frame(height: MainMetrics.barHeight)
        .background(colors.background)
    }

    /// The name, cut short with …, and an accent • while there are unsaved changes.
    private var titleButton: some View {
        Button {
            actions?.rename()
        } label: {
            (Text(title).foregroundColor(colors.label)
             + Text(modified ? " •" : "").foregroundColor(colors.accent))
                .font(.headline)
                .lineLimit(1)
                .truncationMode(.tail)
                .padding(.leading, 4)
                .padding(.trailing, 6)
                .padding(.vertical, 8)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.trailing, 6)
        .accessibilityLabel(modified ? "\(title), not saved" : title)
        .accessibilityHint(AccessibilityLabels.rename)
        .accessibilityIdentifier("title")
    }
}

extension AppBar where Trailing == EmptyView {
    init(title: String, modified: Bool, mode: AppMode, colors: AppColors, tabLabels: Bool = true,
         actions: AppBarActions?) {
        self.init(title: title, modified: modified, mode: mode, colors: colors, tabLabels: tabLabels,
                  titleMaxWidth: nil, actions: actions, trailing: { EmptyView() })
    }
}

/// Edit / Play: the system's segmented control (icons only when `labels` is off).
struct ModeTabs: View {
    let mode: AppMode
    var labels = true
    let select: (AppMode) -> Void

    var body: some View {
        Picker(AccessibilityLabels.edit, selection: Binding(get: { mode }, set: { if $0 != mode { select($0) } })) {
            segment(AccessibilityLabels.edit, AppSymbols.edit).tag(AppMode.edit)
            segment(AccessibilityLabels.play, AppSymbols.play).tag(AppMode.play)
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .fixedSize()
        .padding(.horizontal, 6)
        .accessibilityIdentifier("mode")
    }

    @ViewBuilder
    private func segment(_ label: String, _ symbol: String) -> some View {
        if labels {
            Text(label)
        } else {
            Image(systemName: symbol)
                .accessibilityLabel(label)
        }
    }
}

/// A 44 pt symbol button in a bar, in the accent colour (grey when off).
struct BarIconButton: View {
    let symbol: String
    let label: String
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 19))
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .disabled(!enabled)
        .accessibilityLabel(label)
    }
}

import ChordNotepadKit
import SwiftUI

/// One of Android's Material Design Icons from the asset catalog
/// (ios/tools/mdi_assets.py), tinted; `sf.` names an SF Symbol instead.
struct MdiIcon: View {
    let name: String
    let tint: Color
    var size: CGFloat = 24
    /// A wider drawing's width (Transpose's is 32 × 24); nil: square.
    var width: CGFloat?

    init(_ name: String, tint: Color, size: CGFloat = 24, width: CGFloat? = nil) {
        self.name = name
        self.tint = tint
        self.size = size
        self.width = width
    }

    var body: some View {
        Group {
            if name.hasPrefix("sf.") {
                Image(systemName: String(name.dropFirst(3)))
                    .resizable()
                    .scaledToFit()
                    .padding(size * 0.08)
            } else {
                Image(name)
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
            }
        }
        .foregroundStyle(tint)
        .frame(width: width ?? size, height: size)
        .accessibilityHidden(true)
    }
}

/// What the app bar's buttons do; nil in the catalog (inert).
struct AppBarActions {
    var menu: () -> Void
    var rename: () -> Void
    var mode: (AppMode) -> Void
    var save: () -> Void
}

/// The 48 pt app bar (Android's `AppBar.kt`): ☰, the song's title (• while
/// modified; tap to rename), the Edit / Play tabs and Save. `trailing` fills
/// the rest of the line (phone landscape Edit: the Edit ribbon, with the title
/// kept to `titleMaxWidth`).
struct AppBar<Trailing: View>: View {
    let title: String
    let modified: Bool
    let mode: AppMode
    let colors: AppColors
    /// The tabs' captions (not on a phone at the accessibility text sizes).
    var tabLabels = true
    var titleMaxWidth: CGFloat?
    var actions: AppBarActions?
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(spacing: 0) {
            BarIconButton(icon: "mdi_menu", label: AccessibilityLabels.menu, tint: colors.muted.swiftUI) { actions?.menu() }
                .accessibilityIdentifier("menu")
            titleButton
                .frame(maxWidth: titleMaxWidth ?? .infinity, alignment: .leading)
                .layoutPriority(1)
            ModeTabs(mode: mode, colors: colors, labels: tabLabels) { actions?.mode($0) }
                .layoutPriority(2)
            BarIconButton(icon: "mdi_content_save", label: AccessibilityLabels.save,
                          tint: AppColors.saveTint.withAlpha(modified ? 1 : AppColors.disabledAlpha).swiftUI,
                          enabled: modified) { actions?.save() }
                .layoutPriority(2)
                .accessibilityIdentifier("save")
            trailing()
        }
        .padding(.leading, 2)
        .frame(height: MainMetrics.barHeight)
        .background(colors.surface.swiftUI)
    }

    /// The name, cut short with …, and a primary • while there are unsaved changes.
    private var titleButton: some View {
        Button {
            actions?.rename()
        } label: {
            (Text(title).foregroundColor(colors.text.swiftUI)
             + Text(modified ? " •" : "").foregroundColor(colors.primary.swiftUI))
                .font(.body.weight(.medium))
                .lineLimit(1)
                .truncationMode(.tail)
                .padding(.leading, 2)
                .padding(.trailing, 6)
                .padding(.vertical, 8)
                .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .padding(.trailing, 4)
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

/// Edit / Play: tabs with an underline under the open one.
struct ModeTabs: View {
    let mode: AppMode
    let colors: AppColors
    var labels = true
    let select: (AppMode) -> Void

    var body: some View {
        HStack(spacing: 0) {
            tab(.edit, icon: "mdi_pencil", label: AccessibilityLabels.edit)
            tab(.play, icon: "mdi_play_circle", label: AccessibilityLabels.play)
        }
        .frame(maxHeight: .infinity)
    }

    private func tab(_ target: AppMode, icon: String, label: String) -> some View {
        let selected = mode == target
        let color = (selected ? colors.primary : colors.muted).swiftUI
        return Button {
            select(target)
        } label: {
            HStack(spacing: 4) {
                MdiIcon(icon, tint: color, size: 19)
                if labels {
                    Text(label)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(color)
                        .lineLimit(1)
                        .fixedSize()
                }
            }
            .padding(.horizontal, labels ? 12 : 10)
            .frame(maxHeight: .infinity)
            .overlay(alignment: .bottom) {
                if selected {
                    UnevenRoundedRectangle(topLeadingRadius: 3, topTrailingRadius: 3)
                        .fill(colors.primary.swiftUI)
                        .frame(height: 3)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
        .accessibilityIdentifier(target == .edit ? "tab-edit" : "tab-play")
    }
}

/// A round 44 pt icon button in the app bar.
struct BarIconButton: View {
    let icon: String
    let label: String
    let tint: Color
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MdiIcon(icon, tint: tint)
                .frame(width: 44, height: 44)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
    }
}

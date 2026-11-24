import ChordNotepadKit
import SwiftUI
import UIKit

// Small form controls shared by the Settings pages, the voicing form, About
// and the licences, drawn in Android's Material shapes (ui/settings/
// SettingsWidgets.kt): outlined fields with the label on the outline, − and +
// buttons, dropdowns, switches, the segmented notation buttons. Live, a field
// is a TextField and a dropdown a menu; in the catalog (`live` false) the
// same shapes are drawn with their values as text, since ImageRenderer can't
// draw UIKit-backed views.

extension AppColors {
    /// Material's error container (Android's settings banners).
    var errorContainer: SheetColor { SheetColor(argb: dark ? 0xFF93_000A : 0xFFFF_DAD6) }
    var onErrorContainer: SheetColor { SheetColor(argb: dark ? 0xFFFF_DAD6 : 0xFF41_0002) }
}

/// A full-screen page's bar (Android's `TopAppBar`): ← and the title.
struct PageBar: View {
    let title: String
    let colors: AppColors
    var back: () -> Void = {}

    var body: some View {
        HStack(spacing: 4) {
            Button(action: back) {
                MdiIcon("app_arrow_back", tint: colors.text.swiftUI)
                    .frame(width: 48, height: 48)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(SettingsTexts.back)
            .accessibilityIdentifier("page-back")
            Text(title)
                .font(.title2)
                .foregroundColor(colors.text.swiftUI)
                .lineLimit(1)
                .truncationMode(.tail)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("page-title")
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
        .frame(height: 64)
        .dynamicTypeSize(...DynamicTypeSize.accessibility1)
    }
}

/// The outline of a Material field with its label on it, and the supporting
/// text under it.
struct OutlinedBox<Content: View>: View {
    let label: String
    let colors: AppColors
    var supporting: String?
    var error = false
    var focused = false
    var enabled = true
    /// The colour behind the label (the page's or the dialog's).
    var background: Color
    var labelLines: Int?
    @ViewBuilder let content: () -> Content

    var body: some View {
        let accent: Color = error ? colors.error.swiftUI : focused ? colors.primary.swiftUI : colors.muted.swiftUI
        let alpha = enabled ? 1 : AppColors.disabledAlpha
        VStack(alignment: .leading, spacing: 4) {
            content()
                .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
                .overlay(RoundedRectangle(cornerRadius: 4)
                    .stroke(accent.opacity(alpha), lineWidth: focused || error ? 2 : 1))
                .overlay(alignment: .topLeading) {
                    if !label.isEmpty {
                        Text(label)
                            .font(.caption)
                            .lineLimit(labelLines)
                            .foregroundColor(accent.opacity(alpha))
                            .padding(.horizontal, 4)
                            .background(background)
                            .offset(x: 12, y: -8)
                            .accessibilityHidden(true)
                    }
                }
            if let supporting {
                Text(supporting)
                    .font(.caption)
                    .foregroundColor((error ? colors.error : colors.muted).swiftUI.opacity(alpha))
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 16)
            }
        }
        .padding(.top, 8)
    }
}

/// A text field over a value that lives elsewhere (Android's
/// `StateTextField`): what the user types stays as typed; the value replaces
/// it only when it becomes something this field didn't send (the kit's
/// ``FieldEcho``). `id` it by what it edits, so another voicing starts afresh.
struct FormField<Trailing: View>: View {
    let label: String
    let value: String
    let colors: AppColors
    var live = true
    var supporting: String?
    var error = false
    var enabled = true
    var keyboard: UIKeyboardType = .default
    var labelLines: Int?
    var background: Color?
    /// Put the cursor here once (Edit in the problems dialog: Android's P8).
    var focusNow = false
    var focusShown: () -> Void = {}
    var identifier: String?
    var change: (String) -> Void = { _ in }
    @ViewBuilder var trailing: () -> Trailing

    @State private var echo: FieldEcho
    @FocusState private var focused: Bool

    init(label: String, value: String, colors: AppColors, live: Bool = true, supporting: String? = nil,
         error: Bool = false, enabled: Bool = true, keyboard: UIKeyboardType = .default, labelLines: Int? = nil,
         background: Color? = nil, focusNow: Bool = false, focusShown: @escaping () -> Void = {},
         identifier: String? = nil, change: @escaping (String) -> Void = { _ in },
         @ViewBuilder trailing: @escaping () -> Trailing) {
        self.label = label
        self.value = value
        self.colors = colors
        self.live = live
        self.supporting = supporting
        self.error = error
        self.enabled = enabled
        self.keyboard = keyboard
        self.labelLines = labelLines
        self.background = background
        self.focusNow = focusNow
        self.focusShown = focusShown
        self.identifier = identifier
        self.change = change
        self.trailing = trailing
        _echo = State(initialValue: FieldEcho(value))
    }

    var body: some View {
        OutlinedBox(label: label, colors: colors, supporting: supporting, error: error, focused: live && focused,
                    enabled: enabled, background: background ?? colors.surface.swiftUI, labelLines: labelLines) {
            HStack(spacing: 0) {
                Group {
                    if live {
                        TextField("", text: Binding(get: { echo.text }, set: { text in
                            echo.typed(text)
                            change(text)
                        }))
                        .keyboardType(keyboard)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .submitLabel(.done)
                        .focused($focused)
                        .disabled(!enabled)
                        .accessibilityLabel(label)
                        .accessibilityIdentifier(identifier ?? "field-\(label)")
                    } else {
                        Text(value.isEmpty ? " " : value)
                            .lineLimit(1)
                    }
                }
                .font(.body)
                .foregroundColor(colors.text.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.leading, 16)
                trailing()
            }
        }
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

extension FormField where Trailing == EmptyView {
    init(label: String, value: String, colors: AppColors, live: Bool = true, supporting: String? = nil,
         error: Bool = false, enabled: Bool = true, keyboard: UIKeyboardType = .default, labelLines: Int? = nil,
         background: Color? = nil, identifier: String? = nil, change: @escaping (String) -> Void = { _ in }) {
        self.init(label: label, value: value, colors: colors, live: live, supporting: supporting, error: error,
                  enabled: enabled, keyboard: keyboard, labelLines: labelLines, background: background,
                  identifier: identifier, change: change) { EmptyView() }
    }
}

/// − and + for a number field (hints only; `step` gets −1 or +1), each off
/// when it would do nothing (at a bound: Android's P8).
struct StepperButtons: View {
    let label: String
    let canDown: Bool
    let canUp: Bool
    let colors: AppColors
    var identifier: String?
    var step: (Int) -> Void = { _ in }

    var body: some View {
        HStack(spacing: 0) {
            button("settings_remove", enabled: canDown, name: SettingsTexts.decrease(label), suffix: "down") { step(-1) }
            button("settings_add", enabled: canUp, name: SettingsTexts.increase(label), suffix: "up") { step(1) }
        }
    }

    private func button(_ icon: String, enabled: Bool, name: String, suffix: String,
                        action: @escaping () -> Void) -> some View {
        Button(action: action) {
            MdiIcon(icon, tint: colors.muted.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                .frame(width: 48, height: 48)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(name)
        .accessibilityIdentifier("\(identifier ?? label)-\(suffix)")
    }
}

/// A read-only field that opens a menu of `options` (Android's `DropdownField`);
/// greyed and shut when not `enabled`.
struct DropdownField<Option: Hashable>: View {
    let label: String
    let selected: Option?
    let options: [Option]
    let optionLabel: (Option?) -> String
    let colors: AppColors
    var live = true
    var supporting: String?
    var error = false
    var enabled = true
    var background: Color?
    var identifier: String?
    var select: (Option) -> Void = { _ in }

    var body: some View {
        let box = OutlinedBox(label: label, colors: colors, supporting: supporting, error: error, enabled: enabled,
                              background: background ?? colors.surface.swiftUI) {
            HStack(spacing: 0) {
                Text(optionLabel(selected))
                    .font(.body)
                    .lineLimit(1)
                    .foregroundColor(colors.text.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.leading, 16)
                MdiIcon("app_arrow_drop_down", tint: colors.muted.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                    .frame(width: 48, height: 48)
            }
            .contentShape(Rectangle())
        }
        if live && enabled && !options.isEmpty {
            Menu {
                ForEach(options, id: \.self) { option in
                    Button(optionLabel(option)) { select(option) }
                }
            } label: {
                box
            }
            .buttonStyle(.plain)
            .accessibilityLabel(label)
            .accessibilityValue(optionLabel(selected))
            .accessibilityIdentifier(identifier ?? "dropdown-\(label)")
        } else {
            box
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier(identifier ?? "dropdown-\(label)")
        }
    }
}

/// Material's switch, drawn (a UISwitch is iOS's shape and the catalog can't
/// draw it): the track, filled when on, and the thumb.
struct MaterialSwitch: View {
    let checked: Bool
    let colors: AppColors
    var enabled = true

    var body: some View {
        let alpha = enabled ? 1 : AppColors.disabledAlpha
        ZStack(alignment: checked ? .trailing : .leading) {
            Capsule()
                .fill((checked ? colors.primary : colors.surfaceHigh).swiftUI.opacity(alpha))
                .overlay(Capsule().stroke(checked ? Color.clear : colors.muted.swiftUI.opacity(alpha), lineWidth: 2))
            Circle()
                .fill((checked ? colors.onPrimary : colors.muted).swiftUI.opacity(alpha))
                .frame(width: checked ? 24 : 16, height: checked ? 24 : 16)
                .padding(.horizontal, checked ? 4 : 8)
        }
        .frame(width: 52, height: 32)
    }
}

/// A switch with its label and supporting text; the whole row toggles.
struct SwitchRow: View {
    let label: String
    let checked: Bool
    let colors: AppColors
    var supporting: String?
    var enabled = true
    var identifier: String?
    var change: (Bool) -> Void = { _ in }

    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.body)
                    .foregroundColor(colors.text.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                    .fixedSize(horizontal: false, vertical: true)
                if let supporting {
                    Text(supporting)
                        .font(.caption)
                        .foregroundColor(colors.muted.swiftUI.opacity(enabled ? 1 : AppColors.disabledAlpha))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            MaterialSwitch(checked: checked, colors: colors, enabled: enabled)
        }
        .padding(.vertical, 8)
        .contentShape(Rectangle())
        .onTapGesture { if enabled { change(!checked) } }
        .accessibilityRepresentation {
            Toggle(label, isOn: Binding(get: { checked }, set: { change($0) }))
                .disabled(!enabled)
        }
        .accessibilityIdentifier(identifier ?? "switch-\(label)")
    }
}

/// Material's single-choice segmented buttons (the notation): the chosen one
/// filled, with a check.
struct SegmentedRow<Value: Hashable>: View {
    let options: [(value: Value, label: String)]
    let selected: Value
    let colors: AppColors
    var identifier = "segments"
    var select: (Value) -> Void = { _ in }

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(options.enumerated()), id: \.offset) { index, option in
                let on = option.value == selected
                Button { select(option.value) } label: {
                    HStack(spacing: 8) {
                        if on {
                            Image(systemName: "checkmark")
                                .font(.footnote.weight(.semibold))
                        }
                        Text(option.label)
                            .font(.subheadline.weight(.medium))
                            .lineLimit(1)
                    }
                    .foregroundColor(colors.text.swiftUI)
                    .frame(maxWidth: .infinity, minHeight: 40)
                    .background(on ? colors.primarySoft.swiftUI : Color.clear)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
                .accessibilityIdentifier("\(identifier)-\(index)")
                if index < options.count - 1 {
                    colors.muted.swiftUI.frame(width: 1)
                }
            }
        }
        .frame(minHeight: 40)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(colors.muted.swiftUI, lineWidth: 1))
    }
}

/// A section title, with an optional grey blurb under it.
struct SectionTitle: View {
    let title: String?
    var blurb: String?
    var level = 0
    let colors: AppColors

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let title {
                Text(title)
                    .font(level == 0 ? .headline : .subheadline.weight(.semibold))
                    .foregroundColor(colors.primary.swiftUI)
                    .accessibilityAddTraits(.isHeader)
            }
            if let blurb {
                Text(blurb)
                    .font(.caption)
                    .foregroundColor(colors.muted.swiftUI)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, level == 0 ? 20 : 12)
        .padding(.bottom, 4)
    }
}

/// Grey help text under a control.
struct HelpText: View {
    let text: String
    let colors: AppColors
    var indent: CGFloat = 16

    var body: some View {
        Text(text)
            .font(.caption)
            .foregroundColor(colors.muted.swiftUI)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.leading, indent)
    }
}

/// An error card: `title` (if any) over `messages`.
struct ErrorBanner: View {
    let messages: [String]
    var title: String?
    let colors: AppColors

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            MdiIcon("settings_error", tint: colors.onErrorContainer.swiftUI)
            VStack(alignment: .leading, spacing: 4) {
                if let title {
                    Text(title).font(.subheadline.weight(.semibold))
                }
                ForEach(Array(messages.enumerated()), id: \.offset) { _, message in
                    Text(message).font(.subheadline)
                }
            }
            .foregroundColor(colors.onErrorContainer.swiftUI)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .background(colors.errorContainer.swiftUI, in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }
}

/// How a button with an icon looks: Android's `TextButton` with an icon,
/// `FilledTonalButton` and `OutlinedButton`.
enum IconTextStyle { case text, tonal, outlined }

/// The face of a button with an icon (also a menu's label).
struct IconTextLabel: View {
    let icon: String
    let label: String
    let colors: AppColors
    var style = IconTextStyle.text
    var enabled = true

    var body: some View {
        let alpha = enabled ? 1 : AppColors.disabledAlpha
        let ink: Color = style == .tonal ? colors.text.swiftUI : colors.primary.swiftUI
        HStack(spacing: 8) {
            MdiIcon(icon, tint: ink.opacity(alpha), size: 18)
            Text(label)
                .font(.subheadline.weight(.medium))
                .foregroundColor(ink.opacity(alpha))
                .lineLimit(1)
        }
        .padding(.leading, style == .text ? 12 : 16)
        .padding(.trailing, style == .text ? 12 : 24)
        .frame(minHeight: 40)
        .background(style == .tonal ? colors.primarySoft.swiftUI.opacity(alpha) : Color.clear, in: Capsule())
        .overlay(Capsule().stroke(style == .outlined ? colors.muted.swiftUI.opacity(alpha) : Color.clear,
                                  lineWidth: 1))
        .contentShape(Capsule())
    }
}

/// A button with an icon and a label.
struct IconTextButton: View {
    let icon: String
    let label: String
    let colors: AppColors
    var style = IconTextStyle.text
    var enabled = true
    var identifier: String?
    var action: () -> Void = {}

    var body: some View {
        Button(action: action) {
            IconTextLabel(icon: icon, label: label, colors: colors, style: style, enabled: enabled)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityIdentifier(identifier ?? "button-\(label)")
    }
}

/// An icon button (48 pt), greyed when not `enabled`.
struct IconButton: View {
    let icon: String
    let label: String
    let colors: AppColors
    var enabled = true
    var tint: Color?
    var identifier: String?
    var action: () -> Void = {}

    var body: some View {
        Button(action: action) {
            MdiIcon(icon, tint: (tint ?? colors.muted.swiftUI).opacity(enabled ? 1 : AppColors.disabledAlpha))
                .frame(width: 48, height: 48)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(identifier ?? "icon-\(label)")
    }
}

extension View {
    /// Laid out at its ideal height from the top of the space it is given and
    /// cut at the bottom (the catalog, which can't draw a scroll view). Its
    /// size is the space's, so whatever sits over it stays on screen.
    func topClipped() -> some View {
        Color.clear
            .overlay(alignment: .top) { fixedSize(horizontal: false, vertical: true) }
            .clipped()
    }
}

/// A scrolling column of fields, not wider than a comfortable form (live), or
/// the same column cut at the bottom of its space (the catalog).
struct PageColumn<Content: View>: View {
    var live = true
    var spacing: CGFloat = 12
    var maxWidth: CGFloat = 640
    @ViewBuilder let content: () -> Content

    var body: some View {
        let column = VStack(alignment: .leading, spacing: spacing, content: content)
            .frame(maxWidth: maxWidth, alignment: .leading)
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        if live {
            ScrollView { column }
                .scrollDismissesKeyboard(.interactively)
        } else {
            column.topClipped()
        }
    }
}

/// A list row (Android's `ListItem`): the headline, an optional supporting
/// line, leading and trailing content, the selected one tinted.
struct ListRow<Leading: View, Trailing: View>: View {
    let headline: String
    var supporting: String?
    var supportingColor: Color?
    var headlineColor: Color?
    var selected = false
    let colors: AppColors
    var identifier: String?
    var action: () -> Void = {}
    @ViewBuilder var leading: () -> Leading
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                leading()
                VStack(alignment: .leading, spacing: 2) {
                    Text(headline)
                        .font(.body)
                        .foregroundColor(headlineColor ?? colors.text.swiftUI)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    if let supporting {
                        Text(supporting)
                            .font(.subheadline)
                            .foregroundColor(supportingColor ?? colors.muted.swiftUI)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                trailing()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, supporting == nil ? 16 : 12)
            .frame(minHeight: 56)
            .background(selected ? colors.primarySoft.swiftUI : Color.clear)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityIdentifier(identifier ?? "row-\(headline)")
    }
}

extension ListRow where Leading == EmptyView, Trailing == EmptyView {
    init(headline: String, supporting: String? = nil, selected: Bool = false, colors: AppColors,
         identifier: String? = nil, action: @escaping () -> Void = {}) {
        self.init(headline: headline, supporting: supporting, selected: selected, colors: colors,
                  identifier: identifier, action: action, leading: { EmptyView() }, trailing: { EmptyView() })
    }
}

/// A thin rule (Android's `HorizontalDivider` / `VerticalDivider`).
struct Rule: View {
    let colors: AppColors
    var vertical = false

    var body: some View {
        if vertical {
            colors.line.swiftUI.frame(width: 1).frame(maxHeight: .infinity)
        } else {
            colors.line.swiftUI.frame(height: 1).frame(maxWidth: .infinity)
        }
    }
}

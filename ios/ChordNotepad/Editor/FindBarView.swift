import ChordNotepadKit
import SwiftUI

/// The find bar under the text (the Qt desktop's `FindBar.qml`; Android has
/// none): ▸ for the Replace row, the find field, "3 of 7", ▲ ▼, match case
/// (Aa), whole words (W) and ✕; the Replace row has the replacement, Replace
/// and Replace all. Return goes to the next match, Shift-Return to the
/// previous one, Escape closes. What it finds and does is the kit's
/// (``FindBar``, ``FindAction``); this lays it out. The same view is live and
/// in the catalog (`live` false: the fields drawn as text, inert).
struct FindBarView: View {
    let bar: FindBar
    let colors: AppColors
    var live = true
    var act: (FindAction) -> Void = { _ in }

    @FocusState private var focus: Field?

    private enum Field: Hashable { case find, replace }

    /// A row's height.
    static let rowHeight: CGFloat = 44

    var body: some View {
        VStack(spacing: 0) {
            colors.line.swiftUI.frame(height: 1)
            VStack(spacing: 4) {
                findRow
                if let notice = bar.notice {
                    Text(notice)
                        .font(.caption)
                        .foregroundColor(colors.muted.swiftUI)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.leading, 40)
                        .accessibilityIdentifier("find-notice")
                }
                if bar.replacing {
                    replaceRow
                }
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 4)
        }
        .background(colors.surface2.swiftUI)
        // The rows are a fixed height: their text follows the text size up to a point.
        .dynamicTypeSize(...DynamicTypeSize.xxLarge)
        .onChange(of: bar.opened, initial: true) { _, _ in
            if live && bar.open { focus = .find }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("find-bar")
    }

    private var findRow: some View {
        HStack(spacing: 2) {
            iconButton(bar.replacing ? "chevron.down" : "chevron.right",
                       bar.replacing ? "Hide Replace" : "Replace", enabled: bar.canReplace, id: "find-replace-toggle") {
                act(.showReplace(!bar.replacing))
            }
            field(.find, text: bar.query, placeholder: "Find", identifier: "find-field") { act(.query($0)) }
            Text(bar.countText)
                .font(.footnote.monospacedDigit().weight(bar.noMatch ? .semibold : .regular))
                .foregroundColor((bar.noMatch ? colors.error : colors.muted).swiftUI)
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, 4)
                .accessibilityIdentifier("find-count")
            iconButton("chevron.up", "Previous match", enabled: bar.hasMatches, id: "find-previous") {
                act(.previous)
            }
            iconButton("chevron.down", "Next match", enabled: bar.hasMatches, id: "find-next") { act(.next) }
            toggle("Aa", "Match case", on: bar.matchCase, id: "find-match-case") { act(.matchCase($0)) }
            toggle("W", "Whole words only", on: bar.wholeWord, id: "find-whole-word") { act(.wholeWord($0)) }
            iconButton("xmark", "Close", enabled: true, id: "find-close") { act(.close) }
        }
        .frame(height: Self.rowHeight)
    }

    private var replaceRow: some View {
        HStack(spacing: 6) {
            Color.clear.frame(width: 34, height: 1)
            field(.replace, text: bar.replacement, placeholder: "Replace with", identifier: "replace-field") {
                act(.replacement($0))
            }
            textButton("Replace", id: "find-replace-one") { act(.replace) }
            textButton("Replace all", id: "find-replace-all") { act(.replaceAll) }
        }
        .frame(height: Self.rowHeight)
    }

    @ViewBuilder
    private func field(_ which: Field, text: String, placeholder: String, identifier: String,
                       change: @escaping (String) -> Void) -> some View {
        Group {
            if live {
                TextField(placeholder, text: Binding(get: { text }, set: change))
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(which == .find ? .search : .done)
                    .focused($focus, equals: which)
                    .onSubmit {
                        act(which == .find ? .next : .replace)
                        focus = which
                    }
                    .onKeyPress(keys: [.return], phases: .down) { press in
                        guard which == .find, press.modifiers.contains(.shift) else { return .ignored }
                        act(.previous)
                        return .handled
                    }
                    // Command-G and Shift-Command-G while the field has the keys (the
                    // system menu's find actions go to the text view, out of this chain).
                    .onKeyPress(characters: CharacterSet(charactersIn: "gG"), phases: .down) { press in
                        guard press.modifiers.contains(.command) else { return .ignored }
                        act(press.modifiers.contains(.shift) ? .previous : .next)
                        return .handled
                    }
                    .onKeyPress(.escape) {
                        act(.close)
                        return .handled
                    }
                    .accessibilityIdentifier(identifier)
            } else {
                Text(text.isEmpty ? placeholder : text)
                    .foregroundColor(text.isEmpty ? colors.muted.swiftUI : colors.text.swiftUI)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .font(.body)
        .foregroundColor(colors.text.swiftUI)
        .padding(.horizontal, 10)
        .frame(maxWidth: .infinity, minHeight: 36, maxHeight: 36)
        .background(colors.surface.swiftUI, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8)
            .stroke((live && focus == which ? colors.primary : colors.line).swiftUI, lineWidth: live && focus == which ? 2 : 1))
    }

    private func iconButton(_ symbol: String, _ label: String, enabled: Bool, id: String,
                            action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(colors.icon.swiftUI)
                .frame(width: 34, height: 40)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .opacity(enabled ? 1 : AppColors.disabledAlpha)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }

    private func toggle(_ text: String, _ label: String, on: Bool, id: String,
                        action: @escaping (Bool) -> Void) -> some View {
        Button { action(!on) } label: {
            Text(text)
                .font(.subheadline.weight(.bold))
                .foregroundColor((on ? colors.primary : colors.muted).swiftUI)
                .frame(width: 32, height: 30)
                .background(on ? colors.primarySoft.swiftUI : Color.clear, in: RoundedRectangle(cornerRadius: 6))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier(id)
    }

    private func textButton(_ label: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.subheadline.weight(.medium))
                .foregroundColor(colors.primary.swiftUI)
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, 10)
                .frame(height: 34)
                .overlay(Capsule().stroke(colors.line.swiftUI, lineWidth: 1))
                .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .opacity(bar.hasMatches ? 1 : AppColors.disabledAlpha)
        .disabled(!bar.hasMatches)
        .accessibilityIdentifier(id)
    }
}

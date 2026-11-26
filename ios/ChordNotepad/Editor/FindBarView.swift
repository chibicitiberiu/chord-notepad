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
            colors.separator.frame(height: 0.5).frame(height: 1, alignment: .top)
            VStack(spacing: 4) {
                findRow
                if let notice = bar.notice {
                    Text(notice)
                        .font(.caption)
                        .foregroundColor(colors.secondaryLabel)
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
        .background(colors.bar)
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
                       bar.replacing ? AccessibilityLabels.hideReplace : AccessibilityLabels.showReplace, enabled: bar.canReplace, id: "find-replace-toggle") {
                act(.showReplace(!bar.replacing))
            }
            field(.find, text: bar.query, placeholder: "Find", identifier: "find-field") { act(.query($0)) }
            Text(bar.countText)
                .font(.footnote.monospacedDigit().weight(bar.noMatch ? .semibold : .regular))
                .foregroundColor(bar.noMatch ? colors.red : colors.secondaryLabel)
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, 4)
                .accessibilityIdentifier("find-count")
            iconButton("chevron.up", AccessibilityLabels.previousMatch, enabled: bar.hasMatches, id: "find-previous") {
                act(.previous)
            }
            iconButton("chevron.down", AccessibilityLabels.nextMatch, enabled: bar.hasMatches, id: "find-next") { act(.next) }
            toggle("Aa", AccessibilityLabels.matchCase, on: bar.matchCase, id: "find-match-case") { act(.matchCase($0)) }
            toggle("W", AccessibilityLabels.wholeWords, on: bar.wholeWord, id: "find-whole-word") { act(.wholeWord($0)) }
            iconButton("xmark", AccessibilityLabels.close, enabled: true, id: "find-close") { act(.close) }
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
                    // Command-G, Shift-Command-G, Command-F and Option-Command-F while the
                    // field has the keys (the system menu's find actions go to the
                    // editor's host, out of this chain).
                    .onKeyPress(characters: CharacterSet(charactersIn: "gGfF"), phases: .down) { press in
                        guard press.modifiers.contains(.command) else { return .ignored }
                        if press.characters.lowercased() == "f" {
                            act(.open(replace: press.modifiers.contains(.option)))
                        } else {
                            act(press.modifiers.contains(.shift) ? .previous : .next)
                        }
                        return .handled
                    }
                    .onKeyPress(.escape) {
                        act(.close)
                        return .handled
                    }
                    .accessibilityIdentifier(identifier)
            } else {
                Text(text.isEmpty ? placeholder : text)
                    .foregroundColor(text.isEmpty ? colors.tertiaryLabel : colors.label)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .font(.body)
        .foregroundColor(colors.label)
        // A search field's look: the magnifier, a rounded fill, no border.
        .padding(.leading, which == .find ? 28 : 10)
        .padding(.trailing, 8)
        .frame(maxWidth: .infinity, minHeight: 36, maxHeight: 36)
        .background(colors.fill, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay(alignment: .leading) {
            if which == .find {
                Image(systemName: AppSymbols.find)
                    .font(.subheadline)
                    .foregroundStyle(colors.secondaryLabel)
                    .padding(.leading, 8)
                    .accessibilityHidden(true)
            }
        }
    }

    private func iconButton(_ symbol: String, _ label: String, enabled: Bool, id: String,
                            action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .medium))
                .frame(width: 34, height: 40)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .disabled(!enabled)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }

    private func toggle(_ text: String, _ label: String, on: Bool, id: String,
                        action: @escaping (Bool) -> Void) -> some View {
        Button { action(!on) } label: {
            Text(text)
                .font(.subheadline.weight(.semibold))
                .foregroundColor(on ? .white : colors.accent)
                .frame(width: 32, height: 30)
                .background(on ? colors.accent : Color.clear, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
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
                .font(.subheadline)
                .lineLimit(1)
                .fixedSize()
        }
        .buttonStyle(.bordered)
        .controlSize(.small)
        .disabled(!bar.hasMatches)
        .accessibilityIdentifier(id)
    }
}

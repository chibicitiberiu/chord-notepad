import ChordNotepadKit
import SwiftUI

/// The player's sheets, in their simplest form until the sheets slice: the
/// voicing and the instrument as lists from the session's menus (choosing
/// sends `set_voicing` / `set_instrument`), the speed and the song defaults
/// showing their values only.
struct PlayerSheet<Content: View>: View {
    let title: String
    let colors: AppColors
    /// False in the catalog (no ScrollView).
    var scrolls = true
    var done: () -> Void = {}
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title)
                    .font(.headline)
                    .foregroundColor(colors.text.swiftUI)
                Spacer(minLength: 8)
                DialogButton(label: "Done", colors: colors, action: done)
            }
            .padding(.leading, 20)
            .padding(.trailing, 8)
            .padding(.vertical, 8)
            colors.line.swiftUI.frame(height: 1)
            if scrolls {
                ScrollView { rows }
            } else {
                rows.frame(maxHeight: .infinity, alignment: .top).clipped()
            }
        }
        .background(colors.surfaceLow.swiftUI)
    }

    private var rows: some View {
        VStack(alignment: .leading, spacing: 0, content: content)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// A row with a check mark when it's the one in use.
struct CheckRow: View {
    let label: String
    var detail: String?
    let selected: Bool
    let colors: AppColors
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Text(label)
                    .font(.body)
                    .foregroundColor(colors.text.swiftUI)
                Spacer(minLength: 8)
                if let detail {
                    Text(detail)
                        .font(.footnote)
                        .foregroundColor(colors.muted.swiftUI)
                }
                Image(systemName: "checkmark")
                    .font(.body.weight(.semibold))
                    .foregroundColor(colors.primary.swiftUI)
                    .opacity(selected ? 1 : 0)
            }
            .padding(.horizontal, 20)
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
    }
}

/// A group heading.
struct SheetHeading: View {
    let text: String
    let colors: AppColors

    var body: some View {
        Text(text.uppercased())
            .font(.caption.weight(.medium))
            .foregroundColor(colors.muted.swiftUI)
            .padding(.horizontal, 20)
            .padding(.top, 14)
            .padding(.bottom, 4)
    }
}

/// Voicing: Piano, Fretted, Ensembles and Your voicings.
struct VoicingSheet: View {
    let state: VoicingMenuState?
    let colors: AppColors
    var scrolls = true
    var choose: (String) -> Void = { _ in }
    var done: () -> Void = {}

    var body: some View {
        PlayerSheet(title: "Voicing", colors: colors, scrolls: scrolls, done: done) {
            if let state {
                ForEach(voicingGroups(state), id: \.kind) { group in
                    SheetHeading(text: group.kind.title, colors: colors)
                    ForEach(group.choices, id: \.value) { choice in
                        CheckRow(label: choice.label, selected: choice.selected, colors: colors) {
                            choose(choice.value)
                        }
                    }
                }
            }
        }
    }
}

/// Instrument: the General MIDI families, the one in use open.
struct InstrumentSheet: View {
    let state: InstrumentMenuState?
    let colors: AppColors
    var scrolls = true
    var choose: (Int) -> Void = { _ in }
    var done: () -> Void = {}
    @State private var open: Int?

    var body: some View {
        let families = state.map(instrumentFamilies) ?? []
        let shown = open ?? initialFamilyIndex(families)
        PlayerSheet(title: "Instrument", colors: colors, scrolls: scrolls, done: done) {
            ForEach(Array(families.enumerated()), id: \.offset) { pair in
                let family = pair.element
                Button {
                    open = pair.offset
                } label: {
                    HStack {
                        Text(family.name)
                            .font(.body.weight(family.isCurrent ? .semibold : .regular))
                            .foregroundColor(colors.text.swiftUI)
                        Spacer(minLength: 8)
                        Image(systemName: pair.offset == shown ? "chevron.down" : "chevron.right")
                            .font(.footnote.weight(.semibold))
                            .foregroundColor(colors.muted.swiftUI)
                    }
                    .padding(.horizontal, 20)
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                if pair.offset == shown {
                    ForEach(family.programs, id: \.program) { program in
                        let parts = programParts(program)
                        CheckRow(label: parts.name, detail: parts.number, selected: program.selected, colors: colors) {
                            choose(program.program)
                        }
                        .padding(.leading, 12)
                    }
                }
            }
        }
    }
}

/// Speed and the song defaults until their sheets come: the values, read only.
struct ValuesSheet: View {
    let title: String
    let rows: [(String, String)]
    let colors: AppColors
    var scrolls = true
    var done: () -> Void = {}

    var body: some View {
        PlayerSheet(title: title, colors: colors, scrolls: scrolls, done: done) {
            ForEach(Array(rows.enumerated()), id: \.offset) { pair in
                HStack {
                    Text(pair.element.0)
                        .foregroundColor(colors.text.swiftUI)
                    Spacer(minLength: 8)
                    Text(pair.element.1)
                        .foregroundColor(colors.muted.swiftUI)
                }
                .font(.body)
                .padding(.horizontal, 20)
                .frame(minHeight: 44)
            }
            Text("Changing these here comes with the next version.")
                .font(.footnote)
                .foregroundColor(colors.muted.swiftUI)
                .padding(.horizontal, 20)
                .padding(.top, 8)
        }
    }

    /// The speed sheet's rows.
    static func speed(_ toolbar: ToolbarState?) -> [(String, String)] {
        let pct = toolbar?.multiplierPct ?? 100
        return [("Speed", "\(String(format: "%g", pct)) %")]
    }

    /// The song defaults' rows.
    static func songDefaults(_ state: SongDefaultsState?) -> [(String, String)] {
        guard let state else { return [] }
        var rows = [("Tempo", "\(state.tempo.value) BPM"), ("Time signature", state.time.value), ("Key", state.key.value)]
        if let locked = state.lockedReason { rows.append(("", locked)) }
        return rows
    }
}

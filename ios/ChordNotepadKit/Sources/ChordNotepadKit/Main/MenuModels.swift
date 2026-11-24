import Foundation

// What the voicing and instrument pickers and the recent songs list show, from
// the session's states (Android's ui/menus/MenuModels.kt). The views only draw
// these rows.

/// One row of the voicing list.
public enum VoicingRow: Sendable, Equatable {
    /// A voicing; choosing it sends `set_voicing` with `value`.
    case choice(label: String, value: String, selected: Bool)
    /// The separator between two groups (piano, fretboards, ensembles, user voicings).
    case divider
}

/// The voicing rows: the groups in order, a divider between two, the selected one marked.
public func voicingRows(_ state: VoicingMenuState) -> [VoicingRow] {
    var rows: [VoicingRow] = []
    for (index, group) in state.groups.filter({ !$0.isEmpty }).enumerated() {
        if index > 0 { rows.append(.divider) }
        rows += group.map { .choice(label: $0.label, value: $0.value, selected: $0.value == state.selected) }
    }
    return rows
}

/// One General MIDI program in an instrument family; choosing it sends `set_instrument`.
public struct ProgramRow: Sendable, Equatable, Hashable {
    public var label: String
    public var program: Int
    public var selected: Bool

    public init(_ label: String, _ program: Int, _ selected: Bool) {
        self.label = label
        self.program = program
        self.selected = selected
    }
}

/// One instrument family, marked when it holds the instrument in use.
public struct FamilyRow: Sendable, Equatable {
    public var name: String
    public var isCurrent: Bool
    public var programs: [ProgramRow]

    public init(_ name: String, _ isCurrent: Bool, _ programs: [ProgramRow]) {
        self.name = name
        self.isCurrent = isCurrent
        self.programs = programs
    }
}

/// The 16 families, each with its programs. Labels lose the desktop's column
/// padding (`" 24 - Nylon Guitar"`); an item whose value isn't a program
/// number is skipped.
public func instrumentFamilies(_ state: InstrumentMenuState) -> [FamilyRow] {
    state.families.map { family in
        FamilyRow(family.name, family.isCurrent, family.items.compactMap { item in
            Int(item.value.trimmingCharacters(in: .whitespaces)).map {
                ProgramRow(item.label.trimmingCharacters(in: .whitespaces), $0, $0 == state.current)
            }
        })
    }
}

/// The family to show first in the instrument picker: the current one, else the first.
public func initialFamilyIndex(_ families: [FamilyRow]) -> Int {
    families.firstIndex { $0.isCurrent } ?? 0
}

/// The recent songs, newest first, at most `max` of them (Settings'
/// `max_recent_files`; lowering the setting doesn't republish the list, so the
/// cap applies here too).
public func recentEntries(_ state: RecentDocumentsState?, max: Int? = nil) -> [DocumentRef] {
    let items = state?.items ?? []
    guard let max else { return items }
    return Array(items.prefix(Swift.max(max, 0)))
}

/// The voicing sheet's group headings.
public enum VoicingGroupKind: Int, Sendable, CaseIterable, Comparable {
    case piano, fretted, ensembles, yours

    public static func < (a: VoicingGroupKind, b: VoicingGroupKind) -> Bool { a.rawValue < b.rawValue }

    public var title: String {
        switch self {
        case .piano: return "Piano"
        case .fretted: return "Fretted"
        case .ensembles: return "Ensembles"
        case .yours: return "Your voicings"
        }
    }
}

/// One choice in the voicing sheet.
public struct VoicingChoice: Sendable, Equatable, Hashable {
    public var label: String
    public var value: String
    public var selected: Bool
}

/// One heading of the voicing sheet and its choices.
public struct VoicingSection: Sendable, Equatable {
    public var kind: VoicingGroupKind
    public var choices: [VoicingChoice]
}

/// The voicing sheet: Piano, Fretted, Ensembles and Your voicings, each with
/// its choices. The heading comes from the values (`piano`, `guitar:…`,
/// `ensemble:…`, `voicing:…`), so a group the session leaves out doesn't
/// shift the others; anything unknown joins Your voicings.
public func voicingGroups(_ state: VoicingMenuState) -> [VoicingSection] {
    var byKind: [VoicingGroupKind: [VoicingChoice]] = [:]
    for item in state.groups.joined() {
        let kind: VoicingGroupKind
        if item.value == "piano" {
            kind = .piano
        } else if item.value.hasPrefix("guitar:") {
            kind = .fretted
        } else if item.value.hasPrefix("ensemble:") {
            kind = .ensembles
        } else {
            kind = .yours
        }
        byKind[kind, default: []].append(VoicingChoice(label: item.label, value: item.value,
                                                       selected: item.value == state.selected))
    }
    return VoicingGroupKind.allCases.compactMap { kind in byKind[kind].map { VoicingSection(kind: kind, choices: $0) } }
}

/// The label of the voicing in use, or nil.
public func selectedVoicingLabel(_ state: VoicingMenuState?) -> String? {
    guard let state else { return nil }
    return state.groups.joined().first { $0.value == state.selected }?.label
}

/// A program's label split for the instrument sheet: `"24 - Nylon Guitar"` →
/// (`"Nylon Guitar"`, `"24"`). A label without the number keeps the row's program.
public func programParts(_ row: ProgramRow) -> (name: String, number: String) {
    let label = row.label
    if let dash = label.range(of: "-") {
        let number = label[..<dash.lowerBound].trimmingCharacters(in: .whitespaces)
        let name = label[dash.upperBound...].trimmingCharacters(in: .whitespaces)
        if !number.isEmpty, number.allSatisfy(\.isASCIIDigitCharacter), !name.isEmpty {
            return (name, number)
        }
    }
    return (label, String(row.program))
}

/// The name of the instrument in use (`"Steel Guitar"`), or nil.
public func currentProgramName(_ families: [FamilyRow]) -> String? {
    families.flatMap(\.programs).first(where: \.selected).map { programParts($0).name }
}

extension Character {
    fileprivate var isASCIIDigitCharacter: Bool { isASCII && isNumber }
}

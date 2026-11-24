import Foundation

// The voicing form as a flat list of items to draw, built from the schema and
// the editor state, plus the payloads the edits send (Android's
// ui/settings/VoicingForm.kt). No rule of a voicing is checked here: values
// go to Python as typed and the errors and hints come back in
// VoicingEditorState. Python validates a voicing by building it, so an
// unbuildable one comes back with its errors and isn't saved.

/// One input with what it shows now.
public struct FieldItem: Sendable, Equatable {
    public var spec: FieldSpec
    /// The current value (state values plus edits not echoed yet).
    public var value: JSONValue?
    /// Python's error for this field (or records cell), or nil.
    public var error: String?
    /// Python's hint ("N values expected"), or nil.
    public var hint: String?
    /// False for a cell that is off (the bottom voice's gap: drawn empty and
    /// greyed), and for every field of a read-only form (a built-in).
    public var enabled = true

    public init(spec: FieldSpec, value: JSONValue?, error: String?, hint: String?, enabled: Bool = true) {
        self.spec = spec
        self.value = value
        self.error = error
        self.hint = hint
        self.enabled = enabled
    }

    /// What a text field shows.
    public var text: String { fieldText(value) }

    /// What a switch shows.
    public var checked: Bool { fieldBool(value) }

    /// The option a choice field shows (the first one when the value matches none).
    public var choice: ChoiceOption? {
        spec.choices.first { $0.value == (value ?? .null) } ?? spec.choices.first
    }

    /// The supporting text under the field: Python's error, else its hint and help.
    public func supporting(withHelp: Bool = true) -> String? {
        if let error { return error }
        let parts = [hint, withHelp && !spec.help.trimmingCharacters(in: .whitespaces).isEmpty ? spec.help : nil]
            .compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: "\n")
    }
}

/// One row of a records field; the first row can't move up, the last one can't move down.
public struct RecordRow: Sendable, Equatable {
    public var index: Int
    public var cells: [FieldItem]
    public var canMoveUp = false
    public var canMoveDown = false
}

/// What the form draws, top to bottom.
public enum FormItem: Sendable, Equatable {
    /// A section or group title and its blurb (either may be missing, not both).
    case header(key: String, title: String?, blurb: String?, level: Int)
    /// Fields one under another (a `stack` section).
    case stack(key: String, fields: [FieldItem])
    /// Number fields in a two-column grid where there's room (a `grid` section or group).
    case grid(key: String, fields: [FieldItem])
    /// A labelled pair of (low, high) pitch fields (a `range_table` row).
    case range(key: String, label: String, help: String, low: FieldItem, high: FieldItem)
    /// A records field: rows of the spec's columns, add, move and remove buttons.
    case records(RecordsItem)

    /// Stable key (for lists and for resetting local text).
    public var key: String {
        switch self {
        case .header(let key, _, _, _), .stack(let key, _), .grid(let key, _), .range(let key, _, _, _, _):
            return key
        case .records(let item):
            return item.key
        }
    }

    /// The fields of a stack, a grid or a range (records cells aren't).
    public var fields: [FieldItem] {
        switch self {
        case .stack(_, let fields), .grid(_, let fields): return fields
        case .range(_, _, _, let low, let high): return [low, high]
        case .header, .records: return []
        }
    }
}

/// A records field: its rows and what may be done to them.
public struct RecordsItem: Sendable, Equatable {
    public var key: String
    public var spec: FieldSpec
    public var rows: [RecordRow]
    public var canAdd: Bool
    public var canRemove: Bool
    /// An error for the field as a whole (e.g. too few rows), or nil.
    public var error: String?
}

/// The form of `form` with `values` (the editor state's values with local
/// edits applied, see ``PendingEdits``), `errors` and `hints` from the state.
/// Not `enabled` (a built-in, `VoicingEditorState.readOnly`): every field is
/// greyed and records rows can't be added, moved or removed.
public func buildForm(_ form: FormSpec, values: JSONValue, errors: JSONValue, hints: JSONValue,
                      enabled: Bool = true) -> [FormItem] {
    var out: [FormItem] = []
    func item(_ spec: FieldSpec) -> FieldItem {
        FieldItem(spec: spec, value: values[spec.id], error: errors.text(spec.id), hint: hints.text(spec.id),
                  enabled: enabled)
    }
    func walk(_ section: SectionSpec, _ level: Int) {
        if section.title != nil || section.blurb != nil {
            out.append(.header(key: "h:\(section.id)", title: section.title, blurb: section.blurb, level: level))
        }
        switch section.kind {
        case .stack:
            if !section.fields.isEmpty { out.append(.stack(key: "s:\(section.id)", fields: section.fields.map(item))) }
        case .grid:
            if !section.fields.isEmpty { out.append(.grid(key: "g:\(section.id)", fields: section.fields.map(item))) }
        case .table:
            for spec in section.fields {
                if spec.kind == .records {
                    out.append(.records(recordsItem(spec, values: values, errors: errors, enabled: enabled)))
                } else {
                    out.append(.stack(key: "s:\(section.id):\(spec.id)", fields: [item(spec)]))
                }
            }
        case .rangeTable:
            for row in section.rows where row.fields.count >= 2 {
                out.append(.range(key: "r:\(row.id)", label: row.label, help: row.help,
                                  low: item(row.fields[0]), high: item(row.fields[1])))
            }
        case .groups:
            break
        }
        for group in section.groups { walk(group, level + 1) }
    }
    for s in form.sections { walk(s, 0) }
    return out
}

private func recordsItem(_ spec: FieldSpec, values: JSONValue, errors: JSONValue, enabled: Bool) -> RecordsItem {
    let rows = records(values[spec.id])
    let out = rows.enumerated().map { index, row -> RecordRow in
        let last = index == rows.count - 1
        let cells = spec.columns.map { column -> FieldItem in
            if last && column.disabledInLastRow {
                // Not saved (the bottom voice has no voice below); Python keeps its value.
                return FieldItem(spec: column, value: nil, error: nil, hint: nil, enabled: false)
            }
            return FieldItem(spec: column, value: row[column.id], error: errors.text(spec.cellErrorKey(index, column.id)),
                             hint: nil, enabled: enabled)
        }
        return RecordRow(index: index, cells: cells, canMoveUp: enabled && index > 0, canMoveDown: enabled && !last)
    }
    return RecordsItem(key: "t:\(spec.id)", spec: spec, rows: out,
                       canAdd: enabled && (spec.maxItems.map { rows.count < $0 } ?? true),
                       canRemove: enabled && (spec.minItems.map { rows.count > $0 } ?? true),
                       error: errors.text(spec.id))
}

extension JSONValue {
    /// A non-blank string member.
    func text(_ key: String) -> String? {
        guard let text = self[key]?.stringValue, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else { return nil }
        return text
    }
}

extension VoicingEditorState {
    /// Whether the form has errors to fix: a field's (or records cell's), or one
    /// across fields. The form's banner shows while this holds.
    public var hasErrors: Bool {
        fieldErrors.members.values.contains {
            guard let text = $0.stringValue else { return false }
            return !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        } || !formErrors.isEmpty
    }

    /// The form shows a built-in voicing (`select_builtin`): read-only, with a
    /// form (a newer release's model has none).
    public var showsBuiltin: Bool { readOnly && model != nil }

    /// Add voicing's menu, in the session's order: the blanks (group `blank`),
    /// the built-ins by model, then the user's voicings sorted by name. The
    /// state's `presets` leave out the selected voicing (it can't load itself);
    /// a new one may copy it, so it goes back in. A built-in or a newer
    /// release's voicing being viewed (`readOnly`) doesn't.
    public func addPresets() -> [VoicingPreset] {
        guard let name = selected, !readOnly,
              !presets.contains(where: { $0.group == VoicingPresetGroup.custom && $0.label == name })
        else { return presets }
        let custom = (presets.filter { $0.group == VoicingPresetGroup.custom }.map(\.label) + [name]).sorted()
        return presets.filter { $0.group != VoicingPresetGroup.custom }
            + custom.map { VoicingPreset(group: VoicingPresetGroup.custom, label: $0) }
    }
}

/// The presets groups the screen treats on their own.
public enum VoicingPresetGroup {
    /// The user's own voicings.
    public static let custom = "custom"
    /// Each model's blank defaults (first in the Add voicing menu).
    public static let blank = "blank"
}

/// Add voicing's menu as sections: each group of `presets` under its title
/// (the blanks without one: they say what they are), in the presets' order.
public func addVoicingSections(_ presets: [VoicingPreset], schema: EditorSchema)
    -> [(title: String?, presets: [VoicingPreset])] {
    var sections: [(title: String?, presets: [VoicingPreset])] = []
    var groups: [String] = []
    for preset in presets where !groups.contains(preset.group) { groups.append(preset.group) }
    for group in groups {
        let title: String? = group == VoicingPresetGroup.blank ? nil
            : schema.treeGroups.first { $0.model == group }?.label ?? SettingsTexts.voicingsPresetCustom
        sections.append((title, presets.filter { $0.group == group }))
    }
    return sections
}

/// The payloads of form edits (`set_voicing_values {values}`), keyed by field id.
public enum VoicingEdits {
    /// A typed value (every kind but bool, choice and records goes as the text typed).
    public static func text(_ fieldId: String, _ text: String) -> JSONValue { .object([fieldId: .string(text)]) }

    /// A switch.
    public static func bool(_ fieldId: String, _ checked: Bool) -> JSONValue { .object([fieldId: .bool(checked)]) }

    /// A choice, by the option's value (may be JSON null).
    public static func choice(_ fieldId: String, _ value: JSONValue) -> JSONValue { .object([fieldId: value]) }

    /// A records cell: the whole list goes back (Python merges top-level keys),
    /// `rows` being what the form shows now.
    public static func cell(_ fieldId: String, rows: [[String: JSONValue]], index: Int, column: String,
                            value: JSONValue) -> JSONValue {
        let updated = rows.enumerated().map { i, row -> JSONValue in
            var row = row
            if i == index { row[column] = value }
            return .object(row)
        }
        return .object([fieldId: .array(updated)])
    }
}

/// Form edits sent but not echoed by a `VoicingEditorState` yet, so a quick
/// second edit (two cells of one records field) builds on the first rather
/// than on the stale state. An edit is dropped once a state shows the same
/// value; ``clear()`` drops them all (another voicing, a preset, a model
/// switch) and ``clear(_:)`` one (rows added or removed by Python).
public struct PendingEdits: Sendable, Equatable {
    /// The edits by field id, in the order they were first made.
    private var order: [String] = []
    private var values: [String: JSONValue] = [:]

    public init() {}

    /// Remember the edit `payload` (a `set_voicing_values` argument).
    public mutating func record(_ payload: JSONValue) {
        for (id, value) in payload.members {
            if values[id] == nil { order.append(id) }
            values[id] = value
        }
    }

    /// A state arrived: forget the edits it already shows.
    public mutating func onState(_ state: JSONValue) {
        let shown = state.members
        for id in order where shown[id] == values[id] { values[id] = nil }
        order.removeAll { values[$0] == nil }
    }

    /// Forget every edit.
    public mutating func clear() {
        order = []
        values = [:]
    }

    /// Forget the edit of `fieldId`.
    public mutating func clear(_ fieldId: String) {
        values[fieldId] = nil
        order.removeAll { $0 == fieldId }
    }

    /// `state` with the edits not echoed yet on top.
    public func applyTo(_ state: JSONValue) -> JSONValue {
        if values.isEmpty { return state }
        return .object(state.members.merging(values) { _, edit in edit })
    }

    /// Whether nothing is waiting.
    public var isEmpty: Bool { values.isEmpty }
}

/// `text` as a plain decimal number (digits, an optional sign, point and
/// exponent: what Java's BigDecimal reads), else nil. Foundation's
/// `Decimal(string:)` alone would read "12abc" as 12.
func plainDecimal(_ text: String) -> Decimal? {
    let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard t.range(of: #"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$"#, options: .regularExpression) != nil
    else { return nil }
    return Decimal(string: t, locale: Locale(identifier: "en_US_POSIX"))
}

/// Whether a − (negative `steps`) or + on the field changes `text`: not at its min or max (P8).
public func canStep(_ spec: FieldSpec, _ text: String, _ steps: Int) -> Bool {
    guard let current = plainDecimal(text), let next = stepNumber(spec, text, steps).flatMap(plainDecimal)
    else { return false }
    return next != current
}

/// The spinner step of a number field: `text` moved by `steps` × the field's
/// step, kept within its min/max. Nil when `text` isn't a plain number (the
/// buttons are then disabled; Python reports what's wrong with it).
public func stepNumber(_ spec: FieldSpec, _ text: String, _ steps: Int) -> String? {
    guard let current = plainDecimal(text) else { return nil }
    func decimal(_ value: Double) -> Decimal {
        // Java's BigDecimal.valueOf(double) goes through the shortest decimal text, as Swift's does.
        Decimal(string: "\(value)", locale: Locale(identifier: "en_US_POSIX")) ?? Decimal(value)
    }
    var next = current + decimal(spec.step ?? 1) * Decimal(steps)
    if let min = spec.min { next = Swift.max(next, decimal(min)) }
    if let max = spec.max { next = Swift.min(next, decimal(max)) }
    if spec.kind == .int {
        var source = next
        var rounded = Decimal()
        NSDecimalRound(&rounded, &source, 0, .plain)
        return plainString(rounded)
    }
    let text = plainString(next)
    return text.contains(".") ? text : text + ".0"
}

/// A decimal without exponent or trailing zeros after the point.
private func plainString(_ value: Decimal) -> String {
    var text = NSDecimalNumber(decimal: value).stringValue
    if text.contains(".") {
        while text.hasSuffix("0") { text.removeLast() }
        if text.hasSuffix(".") { text.removeLast() }
    }
    return text == "-0" ? "0" : text
}

/// What a text field over a value that lives elsewhere (the draft, or the
/// voicing form's state plus edits not echoed yet) shows (Android's
/// `StateTextField`): what the user types stays as typed, even when it isn't
/// valid; the value replaces it only when it becomes something this field
/// didn't send (a stepper, a preset, a model switch). Values it sent are
/// remembered until the value catches up with the text, so a late echo of an
/// earlier keystroke never undoes a later one.
public struct FieldEcho: Sendable, Equatable {
    public private(set) var text: String
    private var sent: Set<String> = []

    public init(_ value: String) {
        text = value
    }

    /// The user typed `text` (it is sent).
    public mutating func typed(_ text: String) {
        self.text = text
        sent.insert(text)
    }

    /// The value from outside is `value` now.
    public mutating func valueChanged(_ value: String) {
        if value == text {
            sent = []
        } else if !sent.contains(value) {
            text = value
            sent = []
        }
    }
}

/// The voicing form's errors banner (Android's `FormErrorsBanner`): it shows
/// once the errors have stood for ``draftSaveDelay`` (an edit rests, not
/// every keystroke) and goes as soon as they are fixed. A new voicing starts
/// it over, shown at once when it opens with errors.
public struct ErrorsBanner: Sendable, Equatable {
    public private(set) var shown = false
    private var key: String?
    private var hadErrors = false

    public init() {}

    /// The form shows voicing `key` with or without errors; true: start the
    /// delay, then call ``delayElapsed(key:)``.
    @discardableResult
    public mutating func update(key: String, hasErrors: Bool) -> Bool {
        if key != self.key {
            self.key = key
            shown = hasErrors
            hadErrors = hasErrors
            return false
        }
        hadErrors = hasErrors
        if !hasErrors {
            shown = false
            return false
        }
        return !shown
    }

    /// The delay started for `key` ran out.
    public mutating func delayElapsed(key: String) {
        if key == self.key && hadErrors { shown = true }
    }

    /// Whether the banner is on screen.
    public var visible: Bool { shown && hadErrors }
}

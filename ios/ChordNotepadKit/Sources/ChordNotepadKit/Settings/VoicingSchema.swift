import Foundation

// The voicings editor's form schema (core/chordnotepad/settings_forms/voicing_form.py,
// `editor_schema("ios")`), read once into typed Swift. A port of Android's
// ui/settings/VoicingSchema.kt. Only the shape is read here: what a field
// accepts is Python's business (values go back as typed, errors come back in
// VoicingEditorState).

/// How a field is edited (`KIND_*` in voicing_form.py).
public enum FieldKind: String, Sendable, CaseIterable {
    case text
    case int
    case float
    case bool
    case choice
    case pitch
    case pitchList = "pitch_list"
    case records

    /// Whether the field is a number with a spinner range (``FieldSpec/min`` etc. are hints).
    public var numeric: Bool { self == .int || self == .float }

    /// The kind named `wire`; an unknown kind is edited as plain text.
    public static func of(_ wire: String?) -> FieldKind { wire.flatMap(FieldKind.init(rawValue:)) ?? .text }
}

/// How a section lays out its fields (`SECTION_*` in voicing_form.py).
public enum SectionKind: String, Sendable, CaseIterable {
    case stack
    case grid
    case table
    case rangeTable = "range_table"
    case groups

    /// The kind named `wire`; unknown kinds stack their fields.
    public static func of(_ wire: String?) -> SectionKind { wire.flatMap(SectionKind.init(rawValue:)) ?? .stack }
}

/// One option of a choice field; `value` may be JSON null (the staff's "Auto").
public struct ChoiceOption: Sendable, Equatable, Hashable {
    public var value: JSONValue
    public var label: String

    public init(value: JSONValue, label: String) {
        self.value = value
        self.label = label
    }
}

/// One input of a form, or a column of a records field.
///
/// `min`, `max` and `step` are spinner hints (Python reports what's really
/// wrong); `errorPath` is a records cell's error key (`voice:{index}:{column}`);
/// `disabledInLastRow` a column that is off in a records field's last row (a
/// voice's gap to the next voice: the bottom voice has none).
public struct FieldSpec: Sendable, Equatable {
    public var id: String
    public var kind: FieldKind
    public var label: String
    public var help: String
    public var defaultValue: JSONValue
    public var min: Double?
    public var max: Double?
    public var step: Double?
    public var choices: [ChoiceOption] = []
    public var columns: [FieldSpec] = []
    public var errorPath: String?
    public var minItems: Int?
    public var maxItems: Int?
    public var addLabel: String?
    public var addHelp: String?
    public var removeLabel: String?
    public var removeHelp: String?
    public var moveUpHelp: String?
    public var moveDownHelp: String?
    public var duplicateHelp: String?
    public var disabledInLastRow = false

    public init(id: String, kind: FieldKind, label: String, help: String = "", defaultValue: JSONValue = .null) {
        self.id = id
        self.kind = kind
        self.label = label
        self.help = help
        self.defaultValue = defaultValue
    }

    /// The error key of records cell (`index`, `column`); the field id itself for other fields.
    public func cellErrorKey(_ index: Int, _ column: String) -> String {
        (errorPath ?? "\(id):{index}:{column}")
            .replacingOccurrences(of: "{index}", with: String(index))
            .replacingOccurrences(of: "{column}", with: column)
    }
}

/// A labelled row of a `range_table` section: two pitch fields (low, high).
public struct RangeRow: Sendable, Equatable {
    public var id: String
    public var label: String
    public var help: String
    public var fields: [FieldSpec]
}

/// A form section. Its inputs are `fields`, except a `range_table` (`rows`)
/// and a `groups` section (`groups`, titled grids); a grid may also have
/// `groups` under its own fields.
public struct SectionSpec: Sendable, Equatable {
    public var id: String
    public var kind: SectionKind
    public var title: String?
    public var blurb: String?
    public var fields: [FieldSpec] = []
    public var rows: [RangeRow] = []
    public var columns: [String] = []
    public var groups: [SectionSpec] = []
}

/// One model's form.
public struct FormSpec: Sendable, Equatable {
    public var model: String
    public var title: String
    public var sections: [SectionSpec]
}

/// A model choice (`models` / `tree_groups`).
public struct ModelOption: Sendable, Equatable, Hashable {
    public var model: String
    public var label: String
}

/// Everything the voicings editor draws with (`VoicingEditorSchema.schema`).
///
/// `texts` are the fixed strings: buttons, the confirmation dialogs
/// (`remove_confirm` takes `{name}`), the placeholder; `help` the help of the
/// header controls (`name`, `model`, `load`, `tree_add`, `tree_remove`).
public struct EditorSchema: Sendable, Equatable {
    public var version: Int
    public var models: [ModelOption]
    public var treeGroups: [ModelOption]
    public var texts: [String: String]
    public var help: [String: String]
    public var forms: [String: FormSpec]

    /// A fixed text; `fallback` if the schema has none. Trailing colons (`Name:`) are dropped.
    public func text(_ key: String, fallback: String = "") -> String {
        let value = texts[key] ?? fallback
        return value.hasSuffix(":") ? String(value.dropLast()) : value
    }

    /// The form of `model`; unknown models get the piano form, as in Python.
    public func form(_ model: String?) -> FormSpec? {
        model.flatMap { forms[$0] } ?? forms["piano"]
    }

    /// Read `VoicingEditorSchema.schema`.
    public static func parse(_ json: JSONValue) -> EditorSchema {
        var forms: [String: FormSpec] = [:]
        if case .object(let members) = json["forms"] ?? .null {
            for (model, form) in members {
                forms[model] = FormSpec(model: model, title: form.str("title") ?? model,
                                        sections: form.list("sections").map(parseSection))
            }
        }
        return EditorSchema(version: json.int("version") ?? 0,
                            models: json.list("models").map { $0.modelOption("value") },
                            treeGroups: json.list("tree_groups").map { $0.modelOption("model") },
                            texts: json.strings("texts"), help: json.strings("help"), forms: forms)
    }
}

private func parseSection(_ json: JSONValue) -> SectionSpec {
    var columns: [String] = []
    if case .array(let items) = json["columns"] ?? .null {
        columns = items.compactMap(\.plainText)
    }
    return SectionSpec(
        id: json.str("id") ?? "", kind: SectionKind.of(json.str("kind")), title: json.str("title"),
        blurb: json.str("blurb"), fields: json.list("fields").map(parseField),
        rows: json.list("rows").map {
            RangeRow(id: $0.str("id") ?? "", label: $0.str("label") ?? "", help: $0.str("help") ?? "",
                     fields: $0.list("fields").map(parseField))
        },
        columns: columns, groups: json.list("groups").map(parseSection))
}

private func parseField(_ json: JSONValue) -> FieldSpec {
    var spec = FieldSpec(id: json.str("id") ?? "", kind: FieldKind.of(json.str("kind")),
                         label: json.str("label") ?? "", help: json.str("help") ?? "",
                         defaultValue: json["default"] ?? .null)
    spec.min = json.double("min")
    spec.max = json.double("max")
    spec.step = json.double("step")
    spec.choices = json.list("choices").map { ChoiceOption(value: $0["value"] ?? .null, label: $0.str("label") ?? "") }
    spec.columns = json.list("columns").map(parseField)
    spec.errorPath = json.str("error_path")
    spec.minItems = json.int("min_items")
    spec.maxItems = json.int("max_items")
    spec.addLabel = json.str("add_label")
    spec.addHelp = json.str("add_help")
    spec.removeLabel = json.str("remove_label")
    spec.removeHelp = json.str("remove_help")
    spec.moveUpHelp = json.str("move_up_help")
    spec.moveDownHelp = json.str("move_down_help")
    spec.duplicateHelp = json.str("duplicate_help")
    if case .bool(let off)? = json["disabled_in_last_row"] { spec.disabledInLastRow = off }
    return spec
}

extension JSONValue {
    /// A string member.
    func str(_ key: String) -> String? { self[key]?.stringValue }

    /// A whole-number member.
    func int(_ key: String) -> Int? {
        switch self[key] {
        case .int(let value)?: return value
        case .double(let value)? where value.rounded() == value && abs(value) < 1e15: return Int(value)
        default: return nil
        }
    }

    /// A number member.
    func double(_ key: String) -> Double? {
        switch self[key] {
        case .int(let value)?: return Double(value)
        case .double(let value)?: return value
        default: return nil
        }
    }

    /// The objects of an array member.
    func list(_ key: String) -> [JSONValue] {
        guard case .array(let items)? = self[key] else { return [] }
        return items.filter { if case .object = $0 { return true } else { return false } }
    }

    /// The string members of an object member.
    func strings(_ key: String) -> [String: String] {
        guard case .object(let members)? = self[key] else { return [:] }
        return members.compactMapValues(\.stringValue)
    }

    func modelOption(_ key: String) -> ModelOption {
        ModelOption(model: str(key) ?? "", label: str("label") ?? "")
    }

    /// A primitive as Kotlin's `JsonPrimitive.content` writes it (nil for arrays and objects).
    var plainText: String? {
        switch self {
        case .null: return "null"
        case .bool(let value): return value ? "true" : "false"
        case .int(let value): return String(value)
        case .double(let value): return String(value)
        case .string(let value): return value
        case .array, .object: return nil
        }
    }

    /// The value as JSON text (sorted keys).
    var jsonText: String {
        let encoder = BridgeJSON.encoder
        return (try? encoder.encode(self)).map { String(decoding: $0, as: UTF8.self) } ?? ""
    }

    /// The members of an object (empty for anything else).
    public var members: [String: JSONValue] {
        if case .object(let members) = self { return members }
        return [:]
    }
}

/// A form value as the text its field shows (JSON null and non-strings as written).
public func fieldText(_ value: JSONValue?) -> String {
    switch value {
    case nil, .null?: return ""
    case .array?, .object?: return value!.jsonText
    case let primitive?: return primitive.plainText ?? ""
    }
}

/// A form value as a switch state.
public func fieldBool(_ value: JSONValue?) -> Bool {
    switch value {
    case .bool(let on)?: return on
    // Kotlin's booleanOrNull reads a string primitive's content too.
    case .string("true")?: return true
    default: return false
    }
}

/// A records value as its rows (anything else: no rows).
public func records(_ value: JSONValue?) -> [[String: JSONValue]] {
    guard case .array(let items)? = value else { return [] }
    return items.compactMap { if case .object(let row) = $0 { return row } else { return nil } }
}

import Foundation

// The Edit ribbon's tools as plain data (Android's ui/tools/ToolForms.kt,
// DirectiveVerdict.kt and ToolActions.kt): what each dialog holds, the answer
// it sends and the commands the tools send. The rules (which BPM forms are
// valid, duplicate labels) stay in Python (session/directives.py): a bad
// answer comes back in a DirectiveCheck. Only the pickers' ranges are
// mirrored from the desktop's spinboxes (Transpose −11..+11, beats 1–16,
// loop count 2–100), so a picker can't offer a value the desktop couldn't.

/// The editor's selection `[start, end)` in UTF-16 units of `text` as a
/// code-point ``Selection``, or nil when nothing is selected (the tools then
/// work on the whole song).
public func selectionOf(_ text: String, _ start: Int, _ end: Int) -> Selection? {
    if start == end { return nil }
    let mapper = OffsetMapper(text)
    let a = mapper.toCodePoint(min(start, end))
    let b = mapper.toCodePoint(max(start, end))
    return a == b ? nil : Selection(start: a, end: b)
}

/// Transpose's semitones, kept within the desktop dialog's −11..+11.
public struct TransposeForm: Sendable, Equatable {
    /// The semitones Transpose offers.
    public static let range = -11...11

    public private(set) var semitones: Int

    public init(semitones: Int = 0) {
        self.semitones = min(max(semitones, Self.range.lowerBound), Self.range.upperBound)
    }

    /// One semitone up (stops at +11).
    public func up() -> TransposeForm { TransposeForm(semitones: semitones + 1) }

    /// One semitone down (stops at −11).
    public func down() -> TransposeForm { TransposeForm(semitones: semitones - 1) }

    public var canUp: Bool { semitones < Self.range.upperBound }
    public var canDown: Bool { semitones > Self.range.lowerBound }

    /// The stepper's value: `+2`, `0`, `-3`.
    public var display: String { semitones > 0 ? "+\(semitones)" : String(semitones) }
}

/// The Transpose dialog's words (Android's `transpose_*`).
public enum TransposeTexts {
    public static let title = "Transpose"
    public static let selection = "Transpose selection."
    public static let wholeSong = "Transpose whole song."
    public static let hint = "Shift every chord by the chosen number of semitones (positive = up, negative = down)."
    public static let semitones = "Semitones"
    public static let down = "One semitone down"
    public static let up = "One semitone up"
}

/// The directive kinds of ＋ Insert (`session.directives.DirectiveKind`).
public enum DirectiveKind: String, Sendable, CaseIterable, Hashable {
    case bpm, time, key, label, loop, capo

    /// The kind's wire name.
    public var wire: String { rawValue }

    /// The kind for a request's `kind`, or nil for one this app doesn't know.
    public static func of(_ wire: String) -> DirectiveKind? { DirectiveKind(rawValue: wire) }

    /// The fields its answer carries, in the dialog's order.
    public var fields: [String] {
        switch self {
        case .bpm: return ["value"]
        case .time: return ["beats", "unit"]
        case .key: return ["key"]
        case .label: return ["label"]
        case .loop: return ["label", "count"]
        case .capo: return ["capo"]
        }
    }

    /// The dialog's title (Android's `insert_*_title`).
    public var title: String {
        switch self {
        case .bpm: return "Insert BPM/Tempo Change"
        case .time: return "Insert Time Signature Change"
        case .key: return "Insert Key Change"
        case .label: return "Insert Label"
        case .loop: return "Insert Loop"
        case .capo: return "Insert Capo"
        }
    }

    /// What the dialog says above its fields (Android's `insert_*_hint`).
    public var hint: String {
        switch self {
        case .bpm:
            return "Starting from this point, the tempo of playback changes to/by the given amount.\n\n"
                + "Valid formats:\n  • 110 - absolute change\n  • +20 - relative change\n"
                + "  • 20% - relative change by percentage\n  • 2x - multiplier\n"
                + "  • reset or original - reset back to initial BPM"
        case .time:
            return "Starting from this point, the time signature of playback changes to this value."
        case .key:
            return "Starting from this point, the key in which relative chords play will change.\n\n"
                + "Select the new key signature from the list below."
        case .label:
            return "Inserts a label which can be used for making loops.\n\n"
                + "Enter a unique label name (letters, numbers, and underscores only)."
        case .loop:
            return "Placed at the end of a loop.\n\n"
                + "To set the beginning of a loop, use a label directive (＋ Insert → Label).\n"
                + "Use '@start' as a special keyword for the beginning of the song."
        case .capo:
            return "From this point on, chord boxes and tabs are shown for a capo on this fret. The key stays "
                + "the same, but a fretboard voicing plays these shapes, so its notes can change.\n\n"
                + "Enter a fret from 0 to 12 (0: no capo), or let Suggest pick the easiest one."
        }
    }
}

/// The Insert dialogs' other words (Android's `insert_*`).
public enum InsertTexts {
    public static let title = "Insert"
    public static let insert = "Insert"
    public static let cancel = "Cancel"
    public static let bpmField = "BPM"
    public static let beats = "Beats"
    public static let unit = "Unit"
    public static let keyField = "Key"
    public static let labelField = "Label"
    public static let capoField = "Fret"
    public static let suggest = "Suggest"
    public static let loopLabel = "Label"
    public static let loopCount = "Count"
    public static let fewer = "One repeat fewer"
    public static let more = "One repeat more"
}

/// One Insert directive dialog's fields. ``answer()`` is the `{field: value}`
/// map `respond` takes (`session/directives.py`'s module docstring); every
/// value goes as typed or picked, Python checks it.
public struct DirectiveForm: Sendable, Equatable {
    /// The loop target meaning the song's start (`session.directives.LOOP_START`).
    public static let loopStart = "@start"
    /// Time signature beats the picker offers (the desktop spinbox).
    public static let beatsRange = 1...16
    /// Loop repeats the stepper offers (the desktop spinbox).
    public static let countRange = 2...100

    public var kind: DirectiveKind
    /// BPM: `110`, `+20`, `20%`, `2x`, `reset`.
    public var bpm = ""
    public var beats = 4
    public var unit = 4
    public var key = ""
    /// Label: the new label's name.
    public var label = ""
    /// Loop: `@start` or a label.
    public var loopLabel = DirectiveForm.loopStart
    public var count = 2
    /// Capo: the fret, typed (`0`-`12`; Python checks it).
    public var capo = ""

    public init(kind: DirectiveKind, bpm: String = "", beats: Int = 4, unit: Int = 4, key: String = "",
                label: String = "", loopLabel: String = DirectiveForm.loopStart, count: Int = 2, capo: String = "") {
        self.kind = kind
        self.bpm = bpm
        self.beats = beats
        self.unit = unit
        self.key = key
        self.label = label
        self.loopLabel = loopLabel
        self.count = count
        self.capo = capo
    }

    /// The fields a fresh dialog shows for `kind`, as the desktop's do: 4/4,
    /// the first key of the notation, `@start` repeated twice.
    public static func initial(_ kind: DirectiveKind, keys: [String]) -> DirectiveForm {
        DirectiveForm(kind: kind, key: keys.first ?? "")
    }

    /// The answer to the request.
    public func answer() -> [String: String] {
        switch kind {
        case .bpm: return ["value": bpm]
        case .time: return ["beats": String(beats), "unit": String(unit)]
        case .key: return ["key": key]
        case .label: return ["label": label]
        case .loop: return ["label": loopLabel, "count": String(count)]
        case .capo: return ["capo": capo.trimmingCharacters(in: .whitespaces)]
        }
    }

    /// One more loop repeat (stops at 100).
    public func moreRepeats() -> DirectiveForm {
        var form = self
        form.count = min(max(count + 1, Self.countRange.lowerBound), Self.countRange.upperBound)
        return form
    }

    /// One loop repeat fewer (stops at 2).
    public func fewerRepeats() -> DirectiveForm {
        var form = self
        form.count = min(max(count - 1, Self.countRange.lowerBound), Self.countRange.upperBound)
        return form
    }
}

/// What a loop can jump back to: the song's start, then the request's labels
/// (`session.directives.loop_label_choices`; the session already sorted them).
public func loopChoices(_ request: InsertDirectiveRequest) -> [String] {
    var seen: Set<String> = [DirectiveForm.loopStart]
    var choices = [DirectiveForm.loopStart]
    for label in request.existingLabels where !seen.contains(label) {
        seen.insert(label)
        choices.append(label)
    }
    return choices
}

/// The keys the Key dialog offers: the notation's list from `SettingsState`
/// (`session.toolbar.key_options`), else the toolbar's list.
public func keyChoices(notation: String, american: [String]?, european: [String]?, toolbar: [String]?) -> [String] {
    let list = notation == "european" ? european : american
    if let list, !list.isEmpty { return list }
    return toolbar ?? []
}

/// The keys the Insert Key dialog offers for `request`: its own list (the 15
/// major and 15 minor keys with a signature), else ``keyChoices(notation:american:european:toolbar:)``'s.
public func keyChoices(_ request: InsertDirectiveRequest, american: [String]?, european: [String]?,
                       toolbar: [String]?) -> [String] {
    request.keyOptions.isEmpty
        ? keyChoices(notation: request.notation, american: american, european: european, toolbar: toolbar)
        : request.keyOptions
}

/// The desktop dialog's beat units, until `SettingsState` arrives (it's sent at start).
public let defaultTimeUnits = [1, 2, 4, 8, 16]

/// What an Insert dialog shows about its fields right now, from Python's
/// latest ``DirectiveCheck`` (the rules stay in `session/directives.py`).
///
/// Insert is enabled only once a reply for exactly the current fields came
/// back clean; a reply for older fields, or for another request, counts as
/// "not checked yet". Messages are shown only when `showErrors` (the user has
/// changed something), so a fresh dialog isn't red before anything is typed.
public struct DirectiveVerdict: Sendable, Equatable {
    public var canInsert: Bool
    public var messages: [String]

    public init(canInsert: Bool, messages: [String]) {
        self.canInsert = canInsert
        self.messages = messages
    }

    /// The verdict for `answer` (the form's fields) given the latest `check`.
    /// The messages follow the kind's field order (a JSON object has none
    /// in Swift), then any other field's, then the form's own.
    public static func of(kind: String, requestId: Int, answer: [String: String], check: DirectiveCheck?,
                          showErrors: Bool) -> DirectiveVerdict {
        guard let check, check.kind == kind, check.requestId == requestId,
              stringMap(check.fields) == answer else {
            return DirectiveVerdict(canInsert: false, messages: [])
        }
        let errors = stringMap(check.errors) ?? [:]
        let order = DirectiveKind.of(kind)?.fields ?? []
        var messages = order.compactMap { errors[$0] }
        messages += errors.keys.filter { !order.contains($0) }.sorted().compactMap { errors[$0] }
        if !check.formError.isEmpty { messages.append(check.formError) }
        return DirectiveVerdict(canInsert: messages.isEmpty, messages: showErrors ? messages : [])
    }

    private static func stringMap(_ value: JSONValue) -> [String: String]? {
        guard case .object(let members) = value else { return nil }
        var map: [String: String] = [:]
        for (key, member) in members {
            guard let text = member.stringValue else { return nil }
            map[key] = text
        }
        return map
    }
}

// MARK: - Suggest Capo

/// The Suggest Capo row that is chosen: `picked` while it is one of the
/// rows, else the first (the recommended one); nil with no rows.
public func capoChoice(_ state: CapoAdviceState, picked: Int?) -> Int? {
    state.rows.first { $0.capo == picked }?.capo ?? state.rows.first?.capo
}

/// Whether Suggest Capo's Apply can go: the rows are in, one is chosen and no song plays.
public func capoCanApply(_ state: CapoAdviceState, picked: Int?) -> Bool {
    state.status == CapoAdviceState.ready && !state.playing && capoChoice(state, picked: picked) != nil
}

extension CapoAdviceState {
    public static let computingStatus = "computing"
    public static let ready = "ready"
    public static let errorStatus = "error"

    /// The capos are being scored.
    public var computing: Bool { status == Self.computingStatus }

    /// The voicing in use, as its label.
    public var voicingLabel: String { voicings.first { $0.value == voicing }?.label ?? voicing }
}

extension CapoRow {
    /// The row's headline: `Capo 3`, or `No capo`.
    public var headline: String { capo > 0 ? "Capo \(capo)" : CapoTexts.none }

    /// Recommended · Current, or nil.
    public var tags: String? {
        let tags = [recommended ? CapoTexts.recommended : nil, current ? CapoTexts.current : nil].compactMap { $0 }
        return tags.isEmpty ? nil : tags.joined(separator: " · ")
    }
}

/// The Suggest Capo dialog's words (Android's `capo_*`).
public enum CapoTexts {
    public static let title = "Suggest Capo"
    public static let hint = "Each row is a capo position, the chord shapes you play with it, and how easy they are "
        + "next to no capo. The recommended one comes first."
    public static let voicing = "Voicing"
    public static let finding = "Finding the easiest capo…"
    public static let none = "No capo"
    public static let recommended = "Recommended"
    public static let current = "Current"
    public static let apply = "Apply"
    public static let stopToApply = "Stop playback to apply"
}

// MARK: - The tools' commands (Android's ToolActions)

extension EditorModel {
    /// The selection in code points, or nil for none (the whole song).
    public var toolSelection: Selection? { selectionOf(text, selection.start, selection.end) }

    /// Transpose `selection` (nil: the whole song) by `semitones`, the text
    /// sent first; the cursor stays on its line and column.
    public mutating func transposeCommands(_ semitones: Int, selection: Selection?) -> [BridgeCommand] {
        syncCommands() + [.transpose(cursor: cursorCodePoint, selection: selection, semitones: semitones)]
    }

    /// Insert ▸ `kind`: ask for its fields; the directive goes in at the cursor.
    public mutating func insertDirectiveCommands(_ kind: DirectiveKind) -> [BridgeCommand] {
        syncCommands() + [.requestInsertDirective(at: cursorCodePoint, kind: kind.wire)]
    }

    /// Suggest Capo for the selection (or the whole song): its dialog opens and scores at once.
    public mutating func suggestCapoCommands() -> [BridgeCommand] {
        syncCommands() + [.capoAdviceOpen(selection: toolSelection)]
    }

    /// The chord identifier's Insert: `chord` and a space at the cursor.
    public mutating func insertChordCommands(_ chord: String) -> [BridgeCommand] {
        syncCommands() + [.insertChord(at: cursorCodePoint, chord: chord)]
    }
}

/// The Edit ribbon's ends while it scrolls sideways (Android's `RibbonEdges`):
/// a fade on the left once scrolled, a fade and a › chevron while there's more
/// to the right.
public struct RibbonEdges: Sendable, Equatable {
    /// Below this many points from an end counts as at the end.
    public static let epsilon = 2.0

    public var fadeLeft: Bool
    public var more: Bool

    public init(fadeLeft: Bool, more: Bool) {
        self.fadeLeft = fadeLeft
        self.more = more
    }

    /// For a scroll at `value` of `max`.
    public static func of(_ value: Double, _ max: Double) -> RibbonEdges {
        RibbonEdges(fadeLeft: value > epsilon, more: value < max - epsilon)
    }

    /// The › chevron scrolls the ribbon this far (points).
    public static let moreScroll = 140.0
}

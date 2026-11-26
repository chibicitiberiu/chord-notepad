import Foundation

// The player's sheets as plain data (Android's ui/sheets/SheetRoute.kt,
// PlayerSheets.kt and SongDefaultsSheet.kt): the routes between them, the
// speed's limits, steps and texts, the Playback settings rows and the
// commands each sheet sends. The views only draw these.

extension MainRoute {
    /// Back (a sheet's ←, the dimmed screen, a swipe down): from a family's
    /// programs to the families, from the speed dialog to the speed sheet,
    /// otherwise closed.
    public func back() -> MainRoute {
        switch self {
        case .instrument(let family): return family != nil ? .instrument(family: nil) : .none
        case .speed(let manual): return manual ? .speed(manual: false) : .none
        default: return .none
        }
    }

    /// The route after a sheet dismissed itself, and whether it still shows a
    /// sheet (a family's programs go back to the families).
    public func afterSheetDismissed() -> (route: MainRoute, sheet: Bool) {
        let next = back()
        return (next, next != .none)
    }

    /// The instrument sheet after tapping family `index`.
    public func openingFamily(_ index: Int) -> MainRoute {
        .instrument(family: index)
    }
}

// MARK: - Speed

/// Speed limits (percent): the slider's and the typed value's, the session's
/// (`toolbar.MULTIPLIER_SCALE`, 12.5–400 %, as on the desktop toolbar).
public let speedMinPct = 12.5
public let speedMaxPct = 400.0
/// The slider's step, in percent (its lowest stop is ``speedMinPct``).
public let speedStepPct = 5.0

/// The speed typed in the Manual… dialog: a number of percent from 12.5 to
/// 400 (`12.5` or `12,5`; a trailing `%` and spaces are allowed), else nil.
public func parseSpeedPct(_ text: String) -> Double? {
    var t = text.trimmingCharacters(in: .whitespaces)
    if t.hasSuffix("%") { t.removeLast() }
    t = t.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
    guard !t.isEmpty, t.count <= 7 else { return nil }
    let parts = t.split(separator: ".", omittingEmptySubsequences: false)
    guard parts.count <= 2, !parts[0].isEmpty, parts[0].allSatisfy(\.isASCIIDigit),
          parts.count == 1 || (!parts[1].isEmpty && parts[1].allSatisfy(\.isASCIIDigit)),
          let value = Double(t), value >= speedMinPct, value <= speedMaxPct else { return nil }
    return value
}

/// A percentage as the desktop's `formatPct` writes it: six significant
/// digits, no trailing zeros (`125`, `12.5`, `133.333`).
public func formatPct(_ pct: Double) -> String {
    guard pct.isFinite else { return String(pct) }
    if pct == 0 { return "0" }
    let digits = 6 - Int(floor(log10(abs(pct)))) - 1
    let rounded: Double
    if digits >= 0 {
        let scale = pow(10, Double(digits))
        rounded = (pct * scale).rounded() / scale
    } else {
        let scale = pow(10, Double(-digits))
        rounded = (pct / scale).rounded() * scale
    }
    var text = String(format: "%.\(max(digits, 0))f", rounded)
    if text.contains(".") {
        while text.hasSuffix("0") { text.removeLast() }
        if text.hasSuffix(".") { text.removeLast() }
    }
    return text == "-0" ? "0" : text
}

/// A speed as the sheet shows it: `125`, `12.5` (to a tenth of a percent).
public func speedPctText(_ pct: Double) -> String {
    formatPct((pct * 10).rounded() / 10)
}

/// A slider position snapped to the 5 % grid within 12.5–400; below 15 % the
/// stops are 12.5 and 15.
public func snapSpeedPct(_ value: Double) -> Double {
    let v = min(max(value, speedMinPct), speedMaxPct)
    let next = (speedMinPct / speedStepPct).rounded(.up) * speedStepPct
    if v < next { return v < (speedMinPct + next) / 2 ? speedMinPct : next }
    return min(max((v / speedStepPct).rounded() * speedStepPct, speedMinPct), speedMaxPct)
}

/// Where `pct` sits on the slider's track, 0…1 (linear, as Android's Slider).
public func speedFraction(_ pct: Double) -> Double {
    (min(max(pct, speedMinPct), speedMaxPct) - speedMinPct) / (speedMaxPct - speedMinPct)
}

/// The speed at `fraction` of the track, before snapping.
public func speedAt(fraction: Double) -> Double {
    speedMinPct + min(max(fraction, 0), 1) * (speedMaxPct - speedMinPct)
}

/// The speed sheet's slider: the thumb follows the finger, each new snapped
/// value goes to the session (`set_multiplier_pct`), and the session's value
/// takes over once it has caught up (Android's `SpeedSheet`).
public struct SpeedSlider: Sendable, Equatable {
    /// The value being dragged to, until the session reports it.
    public private(set) var dragged: Double?

    public init() {}

    /// What the sheet shows for the session's `pct`.
    public func shown(_ pct: Double) -> Double { dragged ?? pct }

    /// The finger moved to `value` (unsnapped): the command for a new stop, else nil.
    public mutating func moved(to value: Double) -> BridgeCommand? {
        let snapped = snapSpeedPct(value)
        guard dragged != snapped else { return nil }
        dragged = snapped
        return .setMultiplierPct(pct: snapped)
    }

    /// The session's speed changed to `pct`.
    public mutating func sessionChanged(_ pct: Double) {
        if let dragged, abs(dragged - pct) < 0.01 { self.dragged = nil }
    }
}

/// The Manual… dialog's field: the speed typed, checked on OK.
public struct SpeedEntry: Sendable, Equatable {
    public var text: String
    /// Whether the last OK found no valid speed (cleared by typing).
    public private(set) var showError = false

    /// Opened on the session's `pct`.
    public init(pct: Double) { text = speedPctText(pct) }

    public mutating func type(_ text: String) {
        self.text = text
        showError = false
    }

    /// OK: the command to send, or nil (and the error shown).
    public mutating func submit() -> BridgeCommand? {
        guard let pct = parseSpeedPct(text) else {
            showError = true
            return nil
        }
        return .setMultiplierPct(pct: pct)
    }

    /// The line under the field.
    public var supportingText: String { showError ? SpeedTexts.manualError : SpeedTexts.manualHint }
}

/// The speed sheet's and dialog's words (Android's `speed_*`).
public enum SpeedTexts {
    public static let title = "Playback speed"
    public static let reset = "Reset"
    public static let manual = "Manual…"
    public static let manualHint = "12.5 to 400"
    public static let manualError = "Enter a number from 12.5 to 400"
}

// MARK: - Playback settings (the song pill)

/// The three rows of the Playback settings sheet.
public enum SongDefaultKind: String, Sendable, CaseIterable {
    case tempo = "bpm", time = "time", key = "key"

    /// The directive that sets it.
    public var directive: String { rawValue }
}

/// The directive that sets `value` for `kind`: `{bpm: 90}`, `{time: 3/4}`, `{key: G}`.
public func directiveCode(_ kind: SongDefaultKind, _ value: String) -> String {
    "{\(kind.directive): \(value)}"
}

/// The time signatures the default offers (the common ones; any other is a directive).
public let timeChoices: [(beats: Int, unit: Int)] = [
    (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (2, 2), (3, 8), (6, 8), (7, 8), (9, 8), (12, 8),
]

/// The pill's text: the values joined by " · ", an empty key left out.
public func songDefaultsSummary(tempo: String, time: String, key: String) -> String {
    [tempo, time, key].filter { !$0.isEmpty }.joined(separator: " · ")
}

extension SongDefaultsState {
    /// Whether "Write into song" has anything to write (a value no directive sets).
    public var anythingToWrite: Bool {
        !tempo.fromDirective || !time.fromDirective || (!key.fromDirective && !key.value.isEmpty)
    }

    /// Whether "Write into song" can be pressed now (not while a song plays).
    public var canWrite: Bool { lockedReason == nil && anythingToWrite }
}

/// One row of the Playback settings sheet.
public struct SongDefaultRow: Sendable, Equatable {
    public var kind: SongDefaultKind
    /// Android's icon resource name (`mdi_metronome`, `ic_time_signature`, `mdi_music_clef_treble`).
    public var icon: String
    public var label: String
    /// What the value does.
    public var about: String
    /// The value as the row shows it: `90 bpm`, `3/4`, `G`, `None`.
    public var display: String
    /// The value as written (`90`), what a choice is compared with.
    public var value: String
    /// Set by a directive: read only, with "Set by `{bpm: 90}` in the song".
    public var fromDirective: Bool
    /// Where the directive is (code points), for its Edit link; nil: no link.
    public var directiveOffset: Int?
    /// The dropdown's choices (none for the tempo, which is typed).
    public var choices: [String]

    /// The directive in "Set by … in the song".
    public var code: String { directiveCode(kind, value) }
}

/// The Playback settings sheet's words (Android's `song_defaults_*`).
public enum SongDefaultsTexts {
    public static let title = "Playback settings"
    public static let write = "Write into song"
    public static let noKey = "None"
    public static let setBy = "Set by"
    public static let inSong = "in the song"
    public static let edit = "Edit"
    public static let unsaved = "These aren't saved in the song and reset when you open it again."
    public static let tempoAbout = "Speed of playback, in beats per minute"
    public static let timeAbout = "Beats per bar: bar lines and the metronome"
    public static let keyAbout = "Key signature in the Staff view, and the key for relative chords (I, V, vi)"
}

/// Tempo, Time signature and Key, from the session's state; `keys` are the
/// toolbar's key choices.
public func songDefaultRows(_ state: SongDefaultsState, keys: [String]) -> [SongDefaultRow] {
    [
        SongDefaultRow(kind: .tempo, icon: AppSymbols.tempo, label: "Tempo", about: SongDefaultsTexts.tempoAbout,
                       display: "\(state.tempo.value) bpm", value: state.tempo.value,
                       fromDirective: state.tempo.fromDirective, directiveOffset: state.tempo.directiveOffset,
                       choices: []),
        SongDefaultRow(kind: .time, icon: AppSymbols.timeSignature, label: "Time signature",
                       about: SongDefaultsTexts.timeAbout, display: state.time.value, value: state.time.value,
                       fromDirective: state.time.fromDirective, directiveOffset: state.time.directiveOffset,
                       choices: timeChoices.map { "\($0.beats)/\($0.unit)" }),
        SongDefaultRow(kind: .key, icon: AppSymbols.key, label: "Key", about: SongDefaultsTexts.keyAbout,
                       display: state.key.value.isEmpty ? SongDefaultsTexts.noKey : state.key.value,
                       value: state.key.value, fromDirective: state.key.fromDirective,
                       directiveOffset: state.key.directiveOffset, choices: keys),
    ]
}

/// The command for picking `choice` in `row`'s dropdown, nil when it is the
/// value already (or not a time signature).
public func songDefaultChoice(_ row: SongDefaultRow, _ choice: String) -> BridgeCommand? {
    guard choice != row.value else { return nil }
    switch row.kind {
    case .time:
        let parts = choice.split(separator: "/")
        guard parts.count == 2, let beats = Int(parts[0]), let unit = Int(parts[1]) else { return nil }
        return .setTimeSignature(beats: beats, unit: unit)
    case .key:
        return .setKey(key: choice)
    case .tempo:
        return .setBpmText(text: choice)
    }
}

/// The tempo dialog's OK: the typed text as it is (the session parses and clamps it).
public func tempoCommand(_ text: String) -> BridgeCommand? {
    text.trimmingCharacters(in: .whitespaces).isEmpty ? nil : .setBpmText(text: text)
}

// MARK: - The voicing and instrument sheets' words

public enum VoicingSheetTexts {
    public static let title = "Voicing"
    public static let subtitle = "Which notes play for each chord."
    public static let edit = "Edit voicings…"
}

public enum InstrumentSheetTexts {
    public static let title = "Instrument"
    public static let back = "Back to the families"
}

/// The sheets' Done.
public let sheetDone = "Done"

// MARK: - Insert

/// One entry of the Insert sheet: the directive kind, its icon, label and code.
public struct InsertEntry: Sendable, Equatable, Hashable {
    public var kind: DirectiveKind
    /// Android's icon resource name.
    public var icon: String
    public var label: String
    public var code: String
}

/// Insert's entries, in Android's order.
public let insertEntries: [InsertEntry] = [
    InsertEntry(kind: .bpm, icon: AppSymbols.tempo, label: "Tempo", code: "{bpm}"),
    InsertEntry(kind: .time, icon: AppSymbols.timeSignature, label: "Time signature", code: "{time}"),
    InsertEntry(kind: .key, icon: AppSymbols.key, label: "Key", code: "{key}"),
    InsertEntry(kind: .capo, icon: AppSymbols.capo, label: "Capo", code: "{capo}"),
    InsertEntry(kind: .label, icon: AppSymbols.label, label: "Label (section)", code: "{label}"),
    InsertEntry(kind: .loop, icon: AppSymbols.loop, label: "Loop", code: "{loop}"),
]

/// Android's per-function icon tints (`IconTints`), as RGBA.
public enum IconTints {
    public static let undo = SheetColor(argb: 0xFF5C_6BC0)
    public static let insert = SheetColor(argb: 0xFF2E_7D32)
    public static let transpose = SheetColor(argb: 0xFF8E_24AA)
    public static let identify = SheetColor(argb: 0xFF00_897B)
    public static let tempo = SheetColor(argb: 0xFFE5_3935)
    public static let time = SheetColor(argb: 0xFFEF_6C00)
    public static let key = SheetColor(argb: 0xFF00_897B)
    public static let capo = SheetColor(argb: 0xFFEF_6C00)
    public static let label = SheetColor(argb: 0xFF8E_24AA)
    public static let loop = SheetColor(argb: 0xFF1E_88E5)
    public static let off = SheetColor(argb: 0xFF9E_9E9E)

    /// The tint of a directive kind's icon.
    public static func of(_ kind: DirectiveKind) -> SheetColor {
        switch kind {
        case .bpm: return tempo
        case .time: return time
        case .key: return key
        case .capo: return capo
        case .label: return label
        case .loop: return loop
        }
    }

    /// The tint of a Playback settings row's icon.
    public static func of(_ kind: SongDefaultKind) -> SheetColor {
        switch kind {
        case .tempo: return tempo
        case .time: return time
        case .key: return key
        }
    }
}

extension Character {
    fileprivate var isASCIIDigit: Bool { isASCII && isNumber }
}

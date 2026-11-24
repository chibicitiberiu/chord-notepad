import Foundation

// Settings › General and Playback's working values, ported from Android's
// ui/settings/SettingsDraft.kt. The key is always American, as the config
// keeps it (European is a spelling on screen only).

/// Notation values (`SettingsValues.notation`).
public enum Notation {
    public static let american = "american"
    public static let european = "european"
}

/// The General and Playback pages' working values. The font family is a kind
/// (Monospace, Sans, Serif: the settings visibility rule); `configuredFamily`
/// is what the config had, kept when the kind doesn't change (``toValues()``).
public struct SettingsDraft: Sendable, Equatable {
    public var configuredFamily: String
    public var fontKind: EditorFontKind
    public var fontSize: Int
    public var notation: String
    public var key: String
    public var showQuickStartOnStartup: Bool
    public var maxRecentFiles: Int
    public var bpm: Int
    public var timeSignatureBeats: Int
    public var timeSignatureUnit: Int
    public var wordWrap: Bool
    public var clickPlaysChartVoicing: Bool

    /// What `commit_settings` sends.
    public func toValues() -> SettingsValues {
        SettingsValues(bpm: bpm, clickPlaysChartVoicing: clickPlaysChartVoicing,
                       fontFamily: EditorFont.configFamily(for: fontKind, current: configuredFamily),
                       fontSize: fontSize, key: key, maxRecentFiles: maxRecentFiles, notation: notation,
                       showQuickStartOnStartup: showQuickStartOnStartup, timeSignatureBeats: timeSignatureBeats,
                       timeSignatureUnit: timeSignatureUnit, wordWrap: wordWrap)
    }

    /// Switch notation; the key stays (it is American, only its spelling on screen changes).
    public func withNotation(_ notation: String) -> SettingsDraft {
        var copy = self
        copy.notation = notation
        return copy
    }

    /// The draft of `state`'s values (the key in American spelling, as Python sends it).
    public static func of(_ state: SettingsState) -> SettingsDraft {
        let v = state.values
        return SettingsDraft(configuredFamily: v.fontFamily, fontKind: EditorFont.kind(forFamily: v.fontFamily),
                             fontSize: v.fontSize, notation: v.notation,
                             key: respellKey(v.key, notation: Notation.american, limits: state),
                             showQuickStartOnStartup: v.showQuickStartOnStartup, maxRecentFiles: v.maxRecentFiles,
                             bpm: v.bpm, timeSignatureBeats: v.timeSignatureBeats,
                             timeSignatureUnit: v.timeSignatureUnit, wordWrap: v.wordWrap,
                             clickPlaysChartVoicing: v.clickPlaysChartVoicing)
    }
}

/// The key choices of `notation` ("" = none comes first in the UI).
public func keysFor(_ notation: String, limits: SettingsState) -> [String] {
    notation == Notation.european ? limits.europeanKeys : limits.americanKeys
}

/// How `key` (American, as the draft and config keep it) shows in `notation`: Sol for G in European.
public func shownKey(_ key: String, notation: String, limits: SettingsState) -> String {
    respellKey(key, notation: notation, limits: limits)
}

/// `key` spelled in `notation`: kept if it's one of its keys, else mapped by position, else "".
public func respellKey(_ key: String, notation: String, limits: SettingsState) -> String {
    if key.isEmpty { return "" }
    let target = keysFor(notation, limits: limits)
    if target.contains(key) { return key }
    let other = notation == Notation.european ? limits.americanKeys : limits.europeanKeys
    guard let index = other.firstIndex(of: key), index < target.count else { return "" }
    return target[index]
}

/// The screen's pages (help/settings.rst: General, Playback, and the Voicings editor).
public enum SettingsPage: String, Sendable, CaseIterable, Hashable {
    case general, playback, voicings

    public var title: String {
        switch self {
        case .general: return SettingsTexts.pageGeneral
        case .playback: return SettingsTexts.pagePlayback
        case .voicings: return SettingsTexts.pageVoicings
        }
    }

    public var summary: String {
        switch self {
        case .general: return SettingsTexts.pageGeneralSummary
        case .playback: return SettingsTexts.pagePlaybackSummary
        case .voicings: return SettingsTexts.pageVoicingsSummary
        }
    }
}

/// The whole numbers the number fields of the General and Playback pages
/// accept, in page order. `key` is the setting's name in Python
/// (`SettingsValues`, `NUMBER_SETTINGS`), `page` the page it is on.
public enum NumberSetting: String, Sendable, CaseIterable, Hashable, Comparable {
    case fontSize = "font_size"
    case maxRecentFiles = "max_recent_files"
    case bpm
    case timeSignatureBeats = "time_signature_beats"

    public var key: String { rawValue }

    public var page: SettingsPage {
        switch self {
        case .fontSize, .maxRecentFiles: return .general
        case .bpm, .timeSignatureBeats: return .playback
        }
    }

    /// The field's label.
    public var label: String {
        switch self {
        case .fontSize: return SettingsTexts.fontSize
        case .maxRecentFiles: return SettingsTexts.recentFiles
        case .bpm: return SettingsTexts.defaultBpm
        case .timeSignatureBeats: return SettingsTexts.beats
        }
    }

    /// The field's help under it (nil: none).
    public var help: String? {
        switch self {
        case .fontSize, .timeSignatureBeats: return nil
        case .maxRecentFiles: return SettingsTexts.recentFilesHelp
        case .bpm: return SettingsTexts.defaultBpmHelp
        }
    }

    /// Page order (Android's enum order).
    private var order: Int { Self.allCases.firstIndex(of: self)! }

    public static func < (lhs: NumberSetting, rhs: NumberSetting) -> Bool { lhs.order < rhs.order }

    /// `texts` keyed by ``key``, as settings (unknown keys are skipped).
    public static func fromKeys(_ texts: [String: String]) -> [NumberSetting: String] {
        var out: [NumberSetting: String] = [:]
        for setting in allCases {
            if let text = texts[setting.key] { out[setting] = text }
        }
        return out
    }

    /// `staged_numbers` (a JSON object of strings) as settings.
    public static func fromKeys(_ json: JSONValue) -> [NumberSetting: String] {
        guard case .object(let members) = json else { return [:] }
        return fromKeys(members.compactMapValues { $0.stringValue })
    }

    /// The accepted range (`limits` from `SettingsState`).
    public func range(_ limits: SettingsState) -> ClosedRange<Int> {
        switch self {
        case .fontSize: return limits.fontSizeMin...max(limits.fontSizeMin, limits.fontSizeMax)
        case .maxRecentFiles: return 1...max(1, limits.maxRecentFilesMax)
        case .bpm: return limits.bpmMin...max(limits.bpmMin, limits.bpmMax)
        case .timeSignatureBeats: return 1...16
        }
    }

    /// The value in `draft`.
    public func get(_ draft: SettingsDraft) -> Int {
        switch self {
        case .fontSize: return draft.fontSize
        case .maxRecentFiles: return draft.maxRecentFiles
        case .bpm: return draft.bpm
        case .timeSignatureBeats: return draft.timeSignatureBeats
        }
    }

    /// `draft` with `value`.
    public func set(_ draft: SettingsDraft, _ value: Int) -> SettingsDraft {
        var copy = draft
        switch self {
        case .fontSize: copy.fontSize = value
        case .maxRecentFiles: copy.maxRecentFiles = value
        case .bpm: copy.bpm = value
        case .timeSignatureBeats: copy.timeSignatureBeats = value
        }
        return copy
    }

    /// "Enter a whole number from 6 to 72." for this setting.
    public func rangeText(_ limits: SettingsState) -> String {
        let range = self.range(limits)
        return SettingsTexts.numberRange(range.lowerBound, range.upperBound)
    }
}

/// The font family choices with their labels (Settings › General).
public func fontKindLabel(_ kind: EditorFontKind) -> String {
    switch kind {
    case .monospace: return SettingsTexts.fontMonospace
    case .sans: return SettingsTexts.fontSans
    case .serif: return SettingsTexts.fontSerif
    }
}

import Foundation

// The Settings screen's own texts, Android's res/values/strings_settings.xml
// word for word. The voicing form's texts (labels, help, the confirmations)
// come from Python with the schema (settings_forms).

public enum SettingsTexts {
    public static let title = "Settings"
    public static let back = "Back"
    public static let pageGeneral = "General"
    public static let pageGeneralSummary = "Font, word wrap, chord notation, default key, quick start, recent files"
    public static let pagePlayback = "Playback"
    public static let pagePlaybackSummary = "Default BPM and time signature, clicked chords"
    public static let pageVoicings = "Voicings"
    public static let pageVoicingsSummary = "Your custom fretboard, piano and ensemble voicings"
    public static let fontFamily = "Font family"
    public static let fontFamilyHelp = "The editor's font. Pinching the text changes its size too."
    public static let fontSize = "Font size"
    public static let notation = "Chord notation"
    public static let notationHelp = "The notation new songs are read in. An opened song starts in the notation its "
        + "chords are written in. AB / Do in the Edit ribbon switches only the song you have open."
    public static let notationAmerican = "American"
    public static let notationEuropean = "European"
    public static let defaultKey = "Default key"
    public static let defaultKeyHelp = "The key a new document starts in."
    public static let keyNone = "None"
    public static let wordWrap = "Word wrap"
    public static let wordWrapHelp = "Off: long lines scroll sideways, so chords stay over their lyrics."
    public static let quickStart = "Show quick start at startup"
    public static let quickStartHelp = "Whether the quick-start tour (also in ☰ → Quick start) opens automatically "
        + "when Chord Notepad starts."
    public static let recentFiles = "Number of recent files"
    public static let recentFilesHelp = "How many songs ☰ → Recent remembers."
    public static let defaultBpm = "Default BPM"
    public static let defaultBpmHelp = "The tempo a new document starts at."
    public static let timeSignature = "Default time signature"
    public static let timeSignatureHelp = "The time signature a new document starts at."
    public static let clickChartVoicing = "Clicked chords sound as in the chord sheet"
    public static let clickChartVoicingHelp = "Off: each click is voiced from the chord you clicked before it."
    public static let beats = "Beats"
    public static let beatUnit = "Beat unit"
    public static let problemsTitle = "Some values aren't saved"
    public static let problemsIntro = "These have mistakes, so they aren't saved:"
    public static let problemsEdit = "Edit"
    public static let problemsDiscard = "Discard"
    public static let problemEmpty = "(empty)"
    public static let restored = "Some values you typed last time have mistakes and weren't saved. They're back in "
        + "their fields: fix them, or discard them."
    public static let fontMonospace = "Monospace"
    public static let fontSans = "Sans"
    public static let fontSerif = "Serif"

    public static let voicingsAdd = "Add voicing"
    public static let voicingsRemove = "Remove voicing"
    public static let voicingsRename = "Rename"
    public static let voicingsInvalid = "Has errors"
    public static let voicingsEmptyGroup = "No voicings"
    public static let voicingsInvalidBanner = "A field with an error isn't saved until it's fixed; the rest of the "
        + "voicing is."
    public static let voicingsPresetCustom = "Your voicings"
    public static let voicingsBuiltin = "Built-in, read-only"
    public static let voicingsCopyBuiltin = "Copy to a new voicing"

    public static let ok = "OK"
    public static let cancel = "Cancel"

    /// `settings_number_range`.
    public static func numberRange(_ low: Int, _ high: Int) -> String {
        "Enter a whole number from \(low) to \(high)."
    }

    /// `settings_decrease`.
    public static func decrease(_ label: String) -> String { "Decrease \(label)" }

    /// `settings_increase`.
    public static func increase(_ label: String) -> String { "Increase \(label)" }

    /// `settings_problem_number`: "Playback, Default BPM: 1000. Enter a whole number from 20 to 400.".
    public static func problemNumber(page: String, label: String, text: String, range: String) -> String {
        "\(page), \(label): \(text). \(range)".trimmingCharacters(in: .whitespaces)
    }
}

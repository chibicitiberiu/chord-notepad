import Foundation

/// What VoiceOver says for the buttons whose face is an icon (or an icon and
/// a caption that may drop): Android's `contentDescription` strings, word for
/// word, and the Qt desktop's tooltips for the find bar, which Android hasn't.
/// The pages with texts of their own (Settings, the identifier, the tour, the
/// licences) keep them there; ``androidResources`` lists those too, so the
/// kit's test checks every label against Android's `res/values`.
public enum AccessibilityLabels {
    // The app bar (Android's AppBar.kt).
    public static let menu = "Open the menu"
    public static let save = "Save"
    public static let edit = "Edit"
    public static let play = "Play"
    /// The title's action.
    public static let rename = "Rename"

    // The player (Player.kt).
    public static func voicing(_ name: String) -> String { "Voicing: \(name)" }
    public static func instrument(_ name: String) -> String { "Instrument: \(name)" }
    public static let rewind = "Back to the start (stops playback)"
    public static let playSong = "Play"
    public static let pause = "Pause"
    public static let metronome = "Metronome"
    public static let speed = "Speed"
    public static let showSheet = "Show the chord sheet"
    public static let hideSheet = "Hide the chord sheet"
    /// The song pill: Android's click label, then what the pill says.
    public static let songDefaults = "Playback settings"
    public static func songDefaults(_ pill: String) -> String { "\(songDefaults): \(pill)" }

    // The chord sheet (ChordSheetPane.kt, SongScreen.kt).
    public static let zoomIn = "Zoom in"
    public static let zoomOut = "Zoom out"
    /// The split's handle (a literal on Android too).
    public static let resizeSheet = "Resize the chord sheet"

    // The Edit ribbon (EditRibbon.kt) and the undo chip by the keyboard.
    public static let undo = "Undo"
    public static let redo = "Redo"
    public static let insert = "Insert"
    public static let transpose = "Transpose"
    public static let capo = "Capo"
    public static let identify = "Identify"
    public static let convert = "Convert"
    public static let moreTools = "Show more tools"

    // The player's sheets (PlayerSheets.kt).
    public static let familiesBack = InstrumentSheetTexts.back
    public static let done = "Done"

    // What Android hasn't: the ribbon's Find, the find bar (the Qt desktop's
    // tooltips), a sheet's and an error snackbar's ✕, the notation segments.
    public static let find = "Find and Replace"
    public static let previousMatch = "Previous match"
    public static let nextMatch = "Next match"
    public static let matchCase = "Match case"
    public static let wholeWords = "Whole words only"
    public static let showReplace = "Replace"
    public static let hideReplace = "Hide Replace"
    public static let close = "Close"
    public static let americanNotation = "American notation"
    public static let europeanNotation = "European notation"

    /// Each label with Android's string resource for it (`%1$s` where a
    /// value goes), for the kit's test against `android/app/src/main/res/values`.
    public static let androidResources: [(resource: String, label: String)] = [
        ("drawer_open", menu),
        ("menu_save", save),
        ("mode_edit", edit),
        ("mode_play", play),
        ("rename_title", rename),
        ("player_voicing", voicing("%1$s")),
        ("player_instrument", instrument("%1$s")),
        ("player_rewind", rewind),
        ("player_play", playSong),
        ("player_pause", pause),
        ("player_metronome", metronome),
        ("player_speed", speed),
        ("player_sheet_show", showSheet),
        ("player_sheet_hide", hideSheet),
        ("song_defaults_title", songDefaults),
        ("sheet_zoom_in", zoomIn),
        ("sheet_zoom_out", zoomOut),
        ("sheet_done", done),
        ("menu_undo", undo),
        ("menu_redo", redo),
        ("ribbon_insert", insert),
        ("ribbon_transpose", transpose),
        ("ribbon_capo", capo),
        ("ribbon_identify", identify),
        ("ribbon_convert", convert),
        ("ribbon_more", moreTools),
        ("instrument_back", familiesBack),
        ("quick_start_close", QuickStartTexts.close),
        ("identifier_close", IdentifierTexts.close),
        ("settings_back", SettingsTexts.back),
        ("settings_increase", SettingsTexts.increase("%1$s")),
        ("settings_decrease", SettingsTexts.decrease("%1$s")),
        ("voicings_rename", SettingsTexts.voicingsRename),
        ("voicings_builtin", SettingsTexts.voicingsBuiltin),
        ("licences_back", AboutTexts.back),
    ]
}

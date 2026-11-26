import Foundation

/// The icons of the app's chrome: SF Symbols by role, and Chord Notepad's
/// own drawings (`ic_`, template images in the asset catalog) where no
/// symbol says the same (a capo, transposing, a time signature). Every name
/// here must exist on iOS 17, the deployment target (`AccessibilityTests`
/// checks them against the system's symbol list).
public enum AppSymbols {
    // The app bar.
    public static let menu = "line.3.horizontal"
    public static let save = "square.and.arrow.down"
    public static let edit = "pencil"
    public static let play = "play"

    // The player.
    public static let songDefaults = "music.quarternote.3"
    public static let voicing = "music.note"
    public static let instrument = "guitars"
    public static let rewind = "backward.end.fill"
    public static let playFill = "play.fill"
    public static let pauseFill = "pause.fill"
    public static let metronome = "metronome"
    public static let metronomeOn = "metronome.fill"
    public static let speed = "gauge.with.dots.needle.67percent"
    public static let chordSheet = "rectangle.bottomthird.inset.filled"
    public static let chevronDown = "chevron.down"
    public static let chevronUp = "chevron.up"
    public static let chevronRight = "chevron.right"
    public static let back = "chevron.backward"

    // The Edit ribbon and the chord sheet.
    public static let undo = "arrow.uturn.backward"
    public static let redo = "arrow.uturn.forward"
    public static let find = "magnifyingglass"
    public static let zoomIn = "plus.magnifyingglass"
    public static let zoomOut = "minus.magnifyingglass"
    public static let insert = "plus"
    public static let transpose = "ic_transpose"
    public static let capo = "ic_capo"
    public static let identify = "pianokeys"

    // The directives (Insert, Playback settings).
    public static let tempo = "metronome"
    public static let timeSignature = "ic_time_signature"
    public static let key = "number"
    public static let label = "tag"
    public static let loop = "repeat"

    // The ☰ menu.
    public static let newSong = "doc.badge.plus"
    public static let open = "folder"
    public static let recent = "doc.text"
    public static let saveAs = "square.and.arrow.down.on.square"
    public static let exportMidi = "square.and.arrow.up"
    public static let exportAudio = "waveform"
    public static let exportPdf = "doc.richtext"
    public static let settings = "gear"
    public static let examples = "music.note.list"
    public static let guide = "book"
    public static let quickStart = "graduationcap"
    public static let about = "info.circle"
    public static let diagnostics = "stethoscope"

    // Lists, forms and dialogs.
    public static let checkmark = "checkmark"
    public static let close = "xmark"
    public static let add = "plus"
    public static let remove = "minus"
    public static let moveUp = "arrow.up"
    public static let moveDown = "arrow.down"
    public static let copy = "doc.on.doc"
    public static let delete = "trash"
    public static let rename = "pencil"
    public static let error = "exclamationmark.circle.fill"
    public static let lock = "lock.fill"

    /// Whether `name` is one of the app's own images rather than an SF Symbol.
    public static func isOwnImage(_ name: String) -> Bool { name.hasPrefix("ic_") }

    /// Every name above.
    public static let all: [String] = [
        menu, save, edit, play,
        songDefaults, voicing, instrument, rewind, playFill, pauseFill, metronome, metronomeOn, speed, chordSheet,
        chevronDown, chevronUp, chevronRight, back,
        undo, redo, find, zoomIn, zoomOut, insert, transpose, capo, identify,
        tempo, timeSignature, key, label, loop,
        newSong, open, recent, saveAs, exportMidi, exportAudio, exportPdf, settings, examples, guide, quickStart,
        about, diagnostics,
        checkmark, close, add, remove, moveUp, moveDown, copy, delete, rename, error, lock,
    ]
}

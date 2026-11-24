import Foundation

// The chord identifier (Android's ui/identifier/: IdentifierModel.kt,
// PianoKeyboard.kt), as plain data: its piano, how keys look, the screen's
// own state over the session's IdentifierState and the commands it sends.

/// One key of the identifier's piano. `name` is spelled with sharps, as the
/// session sends notes back; `midi` is 60 for C4 (middle C).
public struct PianoKey: Sendable, Equatable, Hashable {
    public var name: String
    public var octave: Int
    public var midi: Int
    public var isBlack: Bool
    /// Left edge in white-key widths from the keyboard's left edge.
    public var left: Double
    /// Width in white-key widths (1 for white keys).
    public var width: Double

    public init(_ name: String, _ octave: Int, _ midi: Int, _ isBlack: Bool, _ left: Double, _ width: Double) {
        self.name = name
        self.octave = octave
        self.midi = midi
        self.isBlack = isBlack
        self.left = left
        self.width = width
    }
}

/// How a key is drawn. Selected keys are blue; the keys of what played last
/// are amber, and a key that is both stays blue with an amber dot.
public enum KeyLook: Sendable, Equatable {
    case plain, selected, sounding, selectedAndSounding

    public static func of(selected: Bool, sounding: Bool) -> KeyLook {
        switch (selected, sounding) {
        case (true, true): return .selectedAndSounding
        case (true, false): return .selected
        case (false, true): return .sounding
        default: return .plain
        }
    }
}

/// The desktop identifier's keyboard (`ui/chord_identifier.py`, `PianoRoll`):
/// `octaves` octaves from C of `baseOctave`, seven white keys each, the black
/// keys two thirds as wide and two thirds as tall as a white key, their left
/// edges 0.7 white keys past C, D, F, G and A.
public struct PianoKeyboard: Sendable, Equatable {
    /// Note names by semitone above C, spelled with sharps (the desktop's `NOTE_NAMES`).
    public static let noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    /// The same in European notation (solfège), for the key labels of a European song.
    public static let europeanNoteNames = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
    /// A black key's width, in white-key widths (20 px of 30 on the desktop).
    public static let blackWidth = 2.0 / 3.0
    /// A black key's height, as a fraction of the keyboard's (80 px of 120).
    public static let blackHeight = 2.0 / 3.0

    private static let white = [0, 2, 4, 5, 7, 9, 11]
    private static let black: [(Double, Int)] = [(0.7, 1), (1.7, 3), (3.7, 6), (4.7, 8), (5.7, 10)]

    public let baseOctave: Int
    public let octaves: Int
    /// Every key, white keys first (left to right), then black keys (left to right).
    public let keys: [PianoKey]

    public init(baseOctave: Int = 4, octaves: Int = 2) {
        self.baseOctave = baseOctave
        self.octaves = octaves
        var keys: [PianoKey] = []
        for o in 0..<octaves {
            for (i, step) in Self.white.enumerated() {
                keys.append(Self.key(step, baseOctave + o, Double(o * 7 + i), 1, black: false))
            }
        }
        for o in 0..<octaves {
            for (position, step) in Self.black {
                keys.append(Self.key(step, baseOctave + o, Double(o * 7) + position, Self.blackWidth, black: true))
            }
        }
        self.keys = keys
    }

    /// The number of white keys across.
    public var whiteKeyCount: Int { octaves * 7 }

    /// The key at (`x`, `y`) on a keyboard `width` × `height`, black keys
    /// first (they lie on top, over the upper ``blackHeight`` of the
    /// keyboard); nil outside it.
    public func keyAt(x: Double, y: Double, width: Double, height: Double) -> PianoKey? {
        if width <= 0 || height <= 0 || x < 0 || y < 0 || x >= width || y >= height { return nil }
        let u = x / (width / Double(whiteKeyCount))
        if y < height * Self.blackHeight,
           let key = keys.first(where: { $0.isBlack && u >= $0.left && u < $0.left + $0.width }) {
            return key
        }
        return keys.first { !$0.isBlack && u >= $0.left && u < $0.left + $0.width }
    }

    /// The keys whose MIDI numbers are in `midi` (notes outside the keyboard are skipped).
    public func selected(_ midi: [Int]) -> Set<PianoKey> {
        Set(keys.filter { midi.contains($0.midi) })
    }

    /// MIDI number of `step` semitones above C in `octave` (C4 = 60).
    public static func midiOf(_ step: Int, _ octave: Int) -> Int { (octave + 1) * 12 + step }

    /// What `key` is labelled in `notation` (`IdentifierState.notation`): `Sol#` for G# in `european`.
    public static func label(_ key: PianoKey, notation: String) -> String {
        notation == "european" ? europeanNoteNames[((key.midi % 12) + 12) % 12] : key.name
    }

    private static func key(_ step: Int, _ octave: Int, _ left: Double, _ width: Double, black: Bool) -> PianoKey {
        PianoKey(noteNames[step], octave, midiOf(step, octave), black, left, width)
    }
}

/// The keys to highlight as sounding: ``IdentifierState/sounding``, until the
/// screen's timer has marked its token `expiredToken`.
public func shownSounding(_ state: IdentifierState?, expiredToken: Int) -> Set<Int> {
    guard let state, state.soundingToken != expiredToken else { return [] }
    return Set(state.sounding)
}

/// The candidates to list: none while the typed notes have something that
/// isn't a note. The session still names chords for the part it could read
/// (`C Eb Gb Bbb` lists Cm7b5 from its `Bb`), which would read as the answer
/// for what was typed; the error under the field says what to fix.
public func shownCandidates(_ state: IdentifierState?) -> [String] {
    guard let state, state.typedTextError == nil else { return [] }
    return state.candidates
}

/// How the identifier is laid out in a window.
public enum IdentifierLayout: Sendable, Equatable {
    /// A floating dialog (tablets: room for the 640 × 720 panel).
    case dialog
    /// Full screen, the piano and field above the candidates (phones upright).
    case fullScreen
    /// Full screen, the piano and field beside the candidates (short, wide windows: phones on their side).
    case sideBySide
}

/// The dialog needs width and height both (a phone on its side is wide but
/// only about 400 pt tall); a window short of either is full screen, side by
/// side when it's wider than tall.
public func identifierLayout(width: Double, height: Double) -> IdentifierLayout {
    if width >= 600 && height >= 600 { return .dialog }
    return width > height ? .sideBySide : .fullScreen
}

/// The identifier's words (Android's `identifier_*`).
public enum IdentifierTexts {
    public static let title = "Identify Chord"
    public static let close = "Close"
    public static let hint = "Tap keys on the piano or type notes below (e.g., C E G or C, E, G). Long-press a key "
        + "to hear it without selecting it, and long-press Play or a chord to hear it rolled."
    public static let hintEuropean = "Tap keys on the piano or type notes below (e.g., Do Mi Sol or Do, Mi, Sol). "
        + "Long-press a key to hear it without selecting it, and long-press Play or a chord to hear it rolled."
    public static let notes = "Notes"
    public static let clear = "Clear"
    public static let play = "Play"
    public static let playRolled = "Play rolled"
    public static let candidates = "Possible Chords"
    public static let insert = "Insert"
    public static let keyboard = "Piano keyboard, two octaves from C4"

    public static func hint(notation: String?) -> String { notation == "european" ? hintEuropean : hint }
}

/// The identifier screen's own state over the session's ``IdentifierState``:
/// the typed-notes field and the candidate the user picked. The notes,
/// candidates and messages all come from Python. Each input returns the
/// commands to send.
///
/// The field follows the session only after a key tap (`notes_text` is what
/// it should show then); while the user types there it keeps their text. When
/// the song's notation changes, a field showing the selection and the picked
/// candidate are respelled with everything else.
public struct IdentifierModel: Sendable, Equatable {
    /// What the typed-notes field shows.
    public private(set) var typed = ""
    /// The candidate picked in the list (played, and what Insert inserts), or nil.
    public private(set) var picked: String?
    private var followKeys = false
    private var last: IdentifierState?

    public init(typed: String = "", picked: String? = nil) {
        self.typed = typed
        self.picked = picked
    }

    /// The screen opened: start from no notes, as the desktop's fresh dialog does.
    public mutating func open() -> [BridgeCommand] {
        typed = ""
        picked = nil
        followKeys = false
        return [.identifierClear()]
    }

    /// A new ``IdentifierState`` arrived.
    public mutating func onState(_ state: IdentifierState) {
        let before = last
        last = state
        if let before, before.notation != state.notation { respell(before, state) }
        if followKeys {
            typed = state.notesText
            followKeys = false
        }
        if let picked, !shownCandidates(state).contains(picked) { self.picked = nil }
    }

    private mutating func respell(_ before: IdentifierState, _ state: IdentifierState) {
        if typed.trimmingCharacters(in: .whitespaces) == before.notesText { typed = state.notesText }
        if let picked, let index = before.candidates.firstIndex(of: picked),
           before.candidates.count == state.candidates.count {
            self.picked = state.candidates[index]
        }
    }

    /// Tap on a key: select or deselect it (a newly selected key sounds).
    public mutating func tapKey(_ key: PianoKey) -> [BridgeCommand] {
        followKeys = true
        return [.identifierToggleNote(note: key.name, octave: key.octave)]
    }

    /// Long-press on a key: sound it without selecting it.
    public func pressKey(_ key: PianoKey) -> [BridgeCommand] {
        [.playNote(note: key.name, octave: key.octave)]
    }

    /// The user edited the typed-notes field.
    public mutating func type(_ text: String) -> [BridgeCommand] {
        guard text != typed else { return [] }
        typed = text
        followKeys = false
        return [.identifierSetNotesText(text: text)]
    }

    /// Clear: no notes, an empty field.
    public mutating func clear() -> [BridgeCommand] {
        open()
    }

    /// Tap on a candidate: pick it and play it; a long press (`rolled`) plays it rolled.
    public mutating func pick(_ chord: String, rolled: Bool = false) -> [BridgeCommand] {
        picked = chord
        return [.playIdentifiedChord(chord: chord, rolled: rolled)]
    }

    /// Play: the selected keys as they are; a long press (`rolled`) plays them rolled.
    public func play(rolled: Bool = false) -> [BridgeCommand] {
        [.identifierPlaySelection(rolled: rolled)]
    }

    /// Insert `chord` (default: the picked one): the chord to put at the
    /// editor's cursor, nil when none is picked.
    public mutating func insert(_ chord: String? = nil) -> String? {
        guard let chord = chord ?? picked else { return nil }
        picked = chord
        return chord
    }
}

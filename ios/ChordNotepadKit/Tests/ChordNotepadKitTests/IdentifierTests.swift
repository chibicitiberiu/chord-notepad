import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `IdentifierTest`, case for case: the piano, the screen's model
/// and the commands it sends, the layout, the key looks and the sounding keys.
final class IdentifierTests: XCTestCase {
    private let piano = PianoKeyboard()
    private var model = IdentifierModel()

    func testTwoOctavesFromC4With14WhiteAnd10BlackKeys() {
        XCTAssertEqual(piano.keys.count, 24)
        XCTAssertEqual(piano.keys.filter { !$0.isBlack }.count, 14)
        XCTAssertEqual(Set(piano.keys.map(\.midi)), Set(60...83))
        XCTAssertEqual(piano.keys.first, PianoKey("C", 4, 60, false, 0, 1))
        let b5 = piano.keys.filter { !$0.isBlack }.last!
        XCTAssertEqual([b5.name, String(b5.octave), String(b5.midi)], ["B", "5", "83"])
        XCTAssertEqual(piano.keys.filter(\.isBlack).map { "\($0.name)\($0.octave)" },
                       ["C#4", "D#4", "F#4", "G#4", "A#4", "C#5", "D#5", "F#5", "G#5", "A#5"])
    }

    func testMidiNumbers() {
        XCTAssertEqual(PianoKeyboard.midiOf(0, 4), 60)
        XCTAssertEqual(PianoKeyboard.midiOf(9, 4), 69)
        XCTAssertEqual(PianoKeyboard.midiOf(0, 5), 72)
    }

    func testHitTestingPutsBlackKeysOnTop() {
        // 14 white keys of 30 px, 120 px tall, like the desktop.
        func at(_ x: Double, _ y: Double) -> String? {
            piano.keyAt(x: x, y: y, width: 420, height: 120).map { "\($0.name)\($0.octave)" }
        }
        XCTAssertEqual(at(5, 100), "C4")
        XCTAssertEqual(at(5, 10), "C4", "left of C#'s edge (21 px)")
        XCTAssertEqual(at(25, 10), "C#4")
        XCTAssertEqual(at(25, 100), "C4", "below C#: still C")
        XCTAssertEqual(at(35, 100), "D4")
        XCTAssertEqual(at(75, 10), "E4", "no black key between E and F")
        XCTAssertEqual(at(7 * 30 + 3.7 * 30 + 5, 30), "F#5")
        XCTAssertEqual(at(419, 100), "B5")
        XCTAssertNil(at(-1, 10))
        XCTAssertNil(at(420, 10))
        XCTAssertNil(at(10, 120))
    }

    func testKeysAreLabelledInTheSongsNotation() {
        XCTAssertEqual(piano.keys.prefix(7).map { PianoKeyboard.label($0, notation: "european") },
                       ["Do", "Re", "Mi", "Fa", "Sol", "La", "Si"])
        let gSharp = piano.keys.first { $0.midi == 68 }!
        XCTAssertEqual(PianoKeyboard.label(gSharp, notation: "european"), "Sol#")
        XCTAssertEqual(PianoKeyboard.label(gSharp, notation: "american"), "G#")
    }

    func testSelectedKeysByMidiNotesOffTheKeyboardSkipped() {
        XCTAssertEqual(Set(piano.selected([60, 64, 67, 100]).map(\.name)), ["C", "E", "G"])
    }

    // MARK: - The screen's model

    private func state(_ text: String, _ candidates: String..., notation: String = "american",
                       error: String? = nil) -> IdentifierState {
        IdentifierState(candidates: candidates, message: nil, notation: notation,
                        notes: [IdentifierNote(midi: 60, name: "C", octave: 4)], notesText: text, sounding: [],
                        soundingAbove: nil, soundingBelow: nil, soundingSeconds: 0, soundingToken: 0,
                        typedTextError: error)
    }

    func testOpeningClearsKeysToggleAndPlay() throws {
        try assertCommands(model.open(), [("identifier_clear", "{}")])
        let e4 = piano.keys.first { $0.midi == 64 }!
        try assertCommands(model.tapKey(e4), [("identifier_toggle_note", #"{"note": "E", "octave": 4}"#)])
        try assertCommands(model.pressKey(e4), [("play_note", #"{"note": "E", "octave": 4}"#)])
    }

    func testTheFieldFollowsAKeyTapButNotTheSessionWhileTyping() throws {
        _ = model.tapKey(piano.keys[0])
        model.onState(state("C4"))
        XCTAssertEqual(model.typed, "C4")
        try assertCommands(model.type("C E"), [("identifier_set_notes_text", #"{"text": "C E"}"#)])
        // The state for the typed text doesn't rewrite the field.
        model.onState(state("C4 E4"))
        XCTAssertEqual(model.typed, "C E")
        // Same text again sends nothing.
        XCTAssertTrue(model.type("C E").isEmpty)
    }

    func testCandidatesPlayWhenPickedAndInsertAtTheCursor() throws {
        XCTAssertNil(model.insert(), "nothing picked")
        try assertCommands(model.pick("C"), [("play_identified_chord", #"{"chord": "C", "rolled": false}"#)])
        try assertCommands(model.pick("Am7", rolled: true),
                           [("play_identified_chord", #"{"chord": "Am7", "rolled": true}"#)])
        XCTAssertEqual(model.picked, "Am7")
        XCTAssertEqual(model.insert(), "Am7")
        XCTAssertEqual(model.insert("C"), "C", "a double tap inserts that one")
        XCTAssertEqual(model.picked, "C")
    }

    func testAPickThatIsNoLongerACandidateIsDroppedClearResets() throws {
        _ = model.pick("C")
        model.onState(state("C4", "C", "Am7"))
        XCTAssertEqual(model.picked, "C")
        model.onState(state("D4", "Dm"))
        XCTAssertNil(model.picked)
        _ = model.type("C")
        try assertCommands(model.clear(), [("identifier_clear", "{}")])
        XCTAssertEqual(model.typed, "")
    }

    func testNoCandidatesWhileTheTypedNotesHaveAnErrorAndThePickGoes() {
        let good = state("C Eb Gb Bb", "Cm7b5", "Ebm6/C")
        XCTAssertEqual(shownCandidates(good), ["Cm7b5", "Ebm6/C"])
        _ = model.pick("Cm7b5")
        model.onState(good)
        XCTAssertEqual(model.picked, "Cm7b5")
        var bad = good
        bad.typedTextError = "Not a note: Bbb"
        XCTAssertEqual(shownCandidates(bad), [])
        model.onState(bad)
        XCTAssertNil(model.picked)
        XCTAssertEqual(shownCandidates(nil), [])
    }

    func testTheDialogNeedsWidthAndHeightAShortWideWindowGoesSideBySide() {
        XCTAssertEqual(identifierLayout(width: 914, height: 411), .sideBySide)
        XCTAssertEqual(identifierLayout(width: 411, height: 914), .fullScreen)
        XCTAssertEqual(identifierLayout(width: 1280, height: 800), .dialog)
        XCTAssertEqual(identifierLayout(width: 800, height: 1280), .dialog)
        XCTAssertEqual(identifierLayout(width: 1280, height: 500), .sideBySide)
        XCTAssertEqual(identifierLayout(width: 640, height: 360), .sideBySide)
        XCTAssertEqual(identifierLayout(width: 500, height: 700), .fullScreen)
        // The catalog's windows: iPhone 17 upright and on its side, iPad Air 11-inch.
        XCTAssertEqual(identifierLayout(width: 402, height: 874), .fullScreen)
        XCTAssertEqual(identifierLayout(width: 874, height: 402), .sideBySide)
        XCTAssertEqual(identifierLayout(width: 820, height: 1180), .dialog)
    }

    func testANotationSwitchRespellsTheFieldAndThePick() {
        _ = model.tapKey(piano.keys[0])
        model.onState(state("A C E", "Am", "C6"))
        _ = model.pick("C6")
        model.onState(state("Do Mi La", "Lam", "Do6", notation: "european"))
        XCTAssertEqual(model.typed, "Do Mi La")
        XCTAssertEqual(model.picked, "Do6")
        // Typed text of the user's own stays as they wrote it.
        _ = model.type("A4, C5, E5")
        model.onState(state("A C E", "Am", "C6"))
        XCTAssertEqual(model.typed, "A4, C5, E5")
        XCTAssertEqual(model.picked, "C6")
    }

    func testPlaySendsTheSelectionRolledOnALongPress() throws {
        try assertCommands(model.play(), [("identifier_play_selection", #"{"rolled": false}"#)])
        try assertCommands(model.play(rolled: true), [("identifier_play_selection", #"{"rolled": true}"#)])
    }

    func testAKeyIsBlueWhenSelectedAmberWhenSoundingBlueWithADotWhenBoth() {
        XCTAssertEqual(KeyLook.of(selected: false, sounding: false), .plain)
        XCTAssertEqual(KeyLook.of(selected: true, sounding: false), .selected)
        XCTAssertEqual(KeyLook.of(selected: false, sounding: true), .sounding)
        XCTAssertEqual(KeyLook.of(selected: true, sounding: true), .selectedAndSounding)
    }

    func testSoundingKeysShowUntilTheirTokenExpires() {
        var played = state("E", "Eaddb6")
        played.sounding = [64, 68, 71, 72]
        played.soundingToken = 3
        XCTAssertEqual(shownSounding(played, expiredToken: 2), [64, 68, 71, 72])
        XCTAssertEqual(shownSounding(played, expiredToken: 3), [])
        // Played again: a new token shows it again.
        played.soundingToken = 4
        XCTAssertEqual(shownSounding(played, expiredToken: 3).count, 4)
        // New notes: Python sends no sounding notes.
        XCTAssertEqual(shownSounding(state("E"), expiredToken: 3), [])
        XCTAssertEqual(shownSounding(nil, expiredToken: 0), [])
    }

    func testTheSoundingFieldsDecodeFromTheSession() throws {
        let json = """
            {"notes": [], "notes_text": "", "typed_text_error": null, "candidates": ["C"],
             "message": null, "sounding": [48, 52, 55], "sounding_token": 2, "sounding_seconds": 3.0,
             "sounding_below": "◂ C3 E3 G3", "sounding_above": null, "notation": "european"}
            """
        let decoded = try JSONDecoder().decode(IdentifierState.self, from: Data(json.utf8))
        XCTAssertEqual(decoded.notation, "european")
        XCTAssertEqual(decoded.sounding, [48, 52, 55])
        XCTAssertEqual(decoded.soundingToken, 2)
        XCTAssertEqual(decoded.soundingBelow, "◂ C3 E3 G3")
        XCTAssertNil(decoded.soundingAbove)
    }
}

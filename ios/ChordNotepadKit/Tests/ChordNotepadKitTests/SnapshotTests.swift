import Foundation
import XCTest

@testable import ChordNotepadKit

/// ``SessionSnapshot`` (the fold every screen reads) and ``Fixture`` (the
/// recorded scenes the preview catalog shows).
final class SnapshotTests: XCTestCase {
    private var fixtures: URL { TestPython.repo.appendingPathComponent("ios/Fixtures") }

    private func edit(_ start: Int, _ end: Int, _ replacement: String, revision: Int = 1) -> SessionOutput {
        .textEdited(TextEdited(anchor: nil, cursor: start + replacement.unicodeScalars.count, end: end,
                               replacement: replacement, start: start, textRevision: revision, undo: .reset))
    }

    func testEditsAreCodePointRanges() {
        var snapshot = SessionSnapshot()
        snapshot.apply(edit(0, 0, "😀 Am  C\nla la\n"))
        // "C" is code point 6 (UTF-16 offset 7, after the surrogate pair).
        snapshot.apply(edit(6, 7, "G7", revision: 2))
        XCTAssertEqual(snapshot.text, "😀 Am  G7\nla la\n")
        XCTAssertEqual(snapshot.textRevision, 2)
        snapshot.apply(edit(0, 2, ""))
        XCTAssertEqual(snapshot.text, "Am  G7\nla la\n")
        // Past the end clamps, like the mapper.
        snapshot.apply(edit(100, 100, "!"))
        XCTAssertEqual(snapshot.text, "Am  G7\nla la\n!")
    }

    func testMessagesAreKeptInOrderAndCapped() {
        var snapshot = SessionSnapshot()
        for index in 0..<(SessionSnapshot.messageLimit + 5) {
            snapshot.apply(.userError(UserError(message: "m\(index)", title: "")))
        }
        snapshot.apply(.audioUnavailable(AudioUnavailable(fromClick: true, message: "No audio")))
        XCTAssertEqual(snapshot.messages.count, SessionSnapshot.messageLimit)
        XCTAssertEqual(snapshot.messages.last, "No audio")
        XCTAssertEqual(snapshot.audioProblem, "No audio")
        XCTAssertEqual(snapshot.messages.first, "m6")
    }

    func testEveryFixtureFolds() throws {
        let all = try Fixture.all(in: fixtures)
        XCTAssertEqual(all.map(\.scene), ["chord_sheet_fret", "chord_sheet_staff", "empty_song", "errors",
                                          "play_with_chord_sheet", "quick_start_edit"])
        for fixture in all {
            let snapshot = try fixture.snapshot()
            XCTAssertNotNil(snapshot.editor, fixture.scene)
            XCTAssertNotNil(snapshot.status, fixture.scene)
            XCTAssertNotNil(snapshot.document, fixture.scene)
            XCTAssertFalse(fixture.description.isEmpty, fixture.scene)
            // A scene recorded from too late a mark misses the TextEdited and
            // shows "No song open" under the song's name in the catalog.
            if snapshot.document?.documentId != nil {
                XCTAssertFalse(snapshot.text.isEmpty, "\(fixture.scene) has a document but no text")
            }
        }
    }

    func testTheQuickStartFixtureHasItsText() throws {
        let fixture = try Fixture(contentsOf: fixtures.appendingPathComponent("quick_start_edit.json"))
        let snapshot = try fixture.snapshot()
        XCTAssertTrue(snapshot.text.hasPrefix("{bpm: 190} {time: 4/4} {key: C}\n"), snapshot.text)
        XCTAssertTrue(snapshot.text.contains("Twinkle, twinkle, little star,"))
        XCTAssertEqual(snapshot.document?.displayName, "01_quick_start.txt")
        XCTAssertEqual(snapshot.status?.text, "Saved: On My iPhone")
        XCTAssertFalse(snapshot.highlight?.spans.isEmpty ?? true)
    }

    func testTheErrorsFixtureHasItsMessages() throws {
        let snapshot = try Fixture(contentsOf: fixtures.appendingPathComponent("errors.json")).snapshot()
        XCTAssertTrue(snapshot.messages.contains { $0.contains("File not found: missing") }, "\(snapshot.messages)")
        XCTAssertEqual(snapshot.text, "C G\n")
    }

    func testTheChordSheetScenesCarryBuffersForTheirViewAtThePhoneAndTabletHeights() throws {
        let expected = ["play_with_chord_sheet": ("keyboard", 1.0, 2), "errors": ("keyboard", 1.0, 0),
                        "chord_sheet_staff": ("staff", 1.2, 24), "chord_sheet_fret": ("fret", 1.0, 0)]
        for (scene, (view, zoom, cursor)) in expected {
            let fixture = try Fixture(contentsOf: fixtures.appendingPathComponent("\(scene).json"))
            let sheet = try XCTUnwrap(try fixture.snapshot().chordSheet, scene)
            XCTAssertTrue(sheet.visible, scene)
            XCTAssertEqual(sheet.activeView, view, scene)
            XCTAssertEqual(sheet.zoom, zoom, accuracy: 1e-9, scene)
            XCTAssertEqual(sheet.cursorIndex, cursor, scene)
            XCTAssertNil(sheet.currentIndex, scene)
            XCTAssertEqual(fixture.chordSheetBuffers.keys.sorted(), SceneRecorder.catalogHeights(stored: sheet.height))
            for (height, data) in fixture.chordSheetBuffers {
                let buffer = try SheetBuffer.decode(data)
                XCTAssertEqual(buffer.viewId, view, scene)
                XCTAssertEqual(buffer.height, Float(height), scene)
                XCTAssertEqual(buffer.slots.count, scene == "errors" ? 2 : 133, scene)
            }
            // Another height takes the tallest recorded one below it, else the shortest.
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 200), fixture.chordSheetBuffers[102])
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 50), fixture.chordSheetBuffers[102])
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 355), fixture.chordSheetBuffers[355])
        }
        let quickStart = try Fixture(contentsOf: fixtures.appendingPathComponent("quick_start_edit.json"))
        XCTAssertTrue(quickStart.chordSheetBuffers.isEmpty)
        XCTAssertNil(quickStart.chordSheetBuffer(forHeight: 102))
        XCTAssertEqual(try quickStart.snapshot().chordSheet?.visible, false)
    }
}

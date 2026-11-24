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
        XCTAssertEqual(all.map(\.scene), ["empty_song", "errors", "play_with_chord_sheet", "quick_start_edit"])
        for fixture in all {
            let snapshot = try fixture.snapshot()
            XCTAssertNotNil(snapshot.editor, fixture.scene)
            XCTAssertNotNil(snapshot.status, fixture.scene)
            XCTAssertNotNil(snapshot.document, fixture.scene)
            XCTAssertFalse(fixture.description.isEmpty, fixture.scene)
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
}

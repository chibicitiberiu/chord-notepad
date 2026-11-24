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
        XCTAssertEqual(all.map(\.scene), ["capo_advice", "chord_sheet_fret", "chord_sheet_staff",
                                          "discard_question", "editor_european", "editor_mid_edit", "empty_song",
                                          "errors", "export_done", "files_recent", "grace_edit",
                                          "identifier_cmaj7",
                                          "insert_bpm", "insert_capo", "insert_key", "insert_label",
                                          "insert_loop", "insert_time", "play_with_chord_sheet", "player_sheets",
                                          "quick_start_edit", "scarborough_edit", "scarborough_fret",
                                          "scarborough_piano_roll", "scarborough_tab"])
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

    func testTheToolScenesFoldIntoWhatTheirDialogsShow() throws {
        func scene(_ name: String) throws -> SessionSnapshot {
            try Fixture(contentsOf: fixtures.appendingPathComponent("\(name).json")).snapshot()
        }
        // Each Insert scene ends on its pending request; two carry the session's check.
        for kind in DirectiveKind.allCases {
            let snapshot = try scene("insert_\(kind.wire)")
            guard case .insertDirective(let request)? = snapshot.request else {
                return XCTFail("insert_\(kind.wire): no pending request")
            }
            XCTAssertEqual(request.kind, kind.wire)
            XCTAssertTrue(snapshot.text.contains("Amazing grace"), kind.wire)
        }
        let bpm = try scene("insert_bpm")
        XCTAssertEqual(bpm.directiveCheck?.kind, "bpm")
        XCTAssertEqual(bpm.directiveCheck?.formError, "")
        for name in ["grace_edit", "capo_advice", "identifier_cmaj7"] {
            XCTAssertNil(try scene(name).request, "\(name): no Insert dialog over it")
        }
        let advice = try XCTUnwrap(try scene("capo_advice").capoAdvice)
        XCTAssertTrue(advice.active)
        XCTAssertEqual(advice.rows.first?.capo, 0, "Amazing Grace in G: no capo is the easiest")
        let identifier = try XCTUnwrap(try scene("identifier_cmaj7").identifier)
        XCTAssertEqual(identifier.candidates.first, "Cmaj7")
        XCTAssertEqual(identifier.notesText, "C E G B")
        let sheets = try scene("player_sheets")
        XCTAssertEqual(sheets.toolbar?.multiplierPct, 125)
        XCTAssertEqual(sheets.songDefaults?.summary, "90 · 3/4 · G")
        XCTAssertEqual(sheets.instrumentMenu?.current, 25)
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

    func testTheFileScenesHaveTheirRecentListExportAndQuestion() throws {
        let recent = try Fixture(contentsOf: fixtures.appendingPathComponent("files_recent.json")).snapshot()
        XCTAssertEqual(recent.recentDocuments?.items.map(\.displayName), ["Lullaby.txt", "Evening.txt", "Morning.txt",
                                                                           "song.txt"])
        XCTAssertEqual(recent.document?.displayName, "Lullaby.txt")
        XCTAssertTrue(recent.text.contains("Hush now, the stars are out"))
        XCTAssertNil(recent.request)

        let export = try Fixture(contentsOf: fixtures.appendingPathComponent("export_done.json")).snapshot()
        XCTAssertEqual(export.status?.text, "Exported MIDI: Lullaby (2).mid")
        XCTAssertEqual(export.document?.displayName, "Lullaby (2).txt")
        XCTAssertTrue(export.text.hasSuffix("Sleep until the morning\n"), export.text)
        XCTAssertEqual(export.recentDocuments?.items.first?.displayName, "Lullaby (2).txt")
        // A fixture has no answers: the export's request stays (no screen draws a pick request).
        guard case .pickDocument(let pick)? = export.request else { return XCTFail("\(String(describing: export.request))") }
        XCTAssertEqual(pick.mode, .exportMidi)

        let question = try Fixture(contentsOf: fixtures.appendingPathComponent("discard_question.json")).snapshot()
        guard case .confirmDiscard? = question.request else {
            return XCTFail("the scene ends on the unsaved-changes question: \(String(describing: question.request))")
        }
        XCTAssertEqual(question.document?.isModified, true)
        XCTAssertTrue(question.text.hasPrefix("{key: G}\n{bpm: 72}"), question.text)
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
            XCTAssertEqual(fixture.chordSheetBuffers.keys.sorted(), [102, 185, 355, 603])
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 200), fixture.chordSheetBuffers[185])
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 50), fixture.chordSheetBuffers[102])
            XCTAssertEqual(fixture.chordSheetBuffer(forHeight: 355), fixture.chordSheetBuffers[355])
        }
        let quickStart = try Fixture(contentsOf: fixtures.appendingPathComponent("quick_start_edit.json"))
        XCTAssertTrue(quickStart.chordSheetBuffers.isEmpty)
        XCTAssertNil(quickStart.chordSheetBuffer(forHeight: 102))
        XCTAssertEqual(try quickStart.snapshot().chordSheet?.visible, false)
        // The editor's scenes come after the sheet was hidden again.
        for scene in ["editor_mid_edit", "editor_european"] {
            let fixture = try Fixture(contentsOf: fixtures.appendingPathComponent("\(scene).json"))
            XCTAssertEqual(try fixture.snapshot().chordSheet?.visible, false, scene)
            XCTAssertTrue(fixture.chordSheetBuffers.isEmpty, scene)
        }
    }

    func testTheScarboroughScenesAreFrozenWhileTheirChordSounds() throws {
        // (scene, view, the chord sounding, the strip's zoom, the status)
        let expected = [("scarborough_piano_roll", "keyboard", 4, 1.0, "Bar 5/56 · Playing G"),
                        ("scarborough_fret", "fret", 3, 0.5, "Bar 4/56 · Playing C"),
                        ("scarborough_tab", "tab", 6, 0.833, "Bar 7/56 · Playing Em")]
        for (scene, view, chord, zoom, status) in expected {
            let fixture = try Fixture(contentsOf: fixtures.appendingPathComponent("\(scene).json"))
            let snapshot = try fixture.snapshot()
            XCTAssertEqual(snapshot.document?.displayName, "Scarborough Fair.txt", scene)
            XCTAssertTrue(snapshot.text.hasPrefix("{bpm: 100} {time: 3/4} {key: Am}\n"), scene)
            let playback = try XCTUnwrap(snapshot.playback, scene)
            XCTAssertEqual(playback.status, .playing, scene)
            XCTAssertEqual(playback.chordIndex, chord, scene)
            XCTAssertNotNil(playback.playingSpan, scene)
            XCTAssertEqual(snapshot.status?.text, status, scene)
            let sheet = try XCTUnwrap(snapshot.chordSheet, scene)
            XCTAssertEqual(sheet.activeView, view, scene)
            XCTAssertEqual(sheet.currentIndex, chord, scene)
            XCTAssertEqual(sheet.zoom, zoom, accuracy: 1e-9, scene)
            XCTAssertEqual(sheet.height, 330, scene)
            XCTAssertEqual(fixture.chordSheetBuffers.keys.sorted(), SceneRecorder.catalogHeights(stored: 330), scene)
            XCTAssertEqual(snapshot.songDefaults?.summary, "100 · 3/4 · Am", scene)
            XCTAssertNotNil(snapshot.voicingMenu?.lockedReason, "\(scene): the voicing can't change while playing")
            // The editor paints the sounding chord.
            let editor = try fixture.editorModel()
            XCTAssertNotNil(editor.playing, scene)
        }
        let edit = try Fixture(contentsOf: fixtures.appendingPathComponent("scarborough_edit.json")).snapshot()
        XCTAssertEqual(edit.playback?.status, .idle)
        XCTAssertEqual(edit.document?.displayName, "Scarborough Fair.txt")
    }

    func testTheEditorScenesFoldIntoTheEditorAsTheCatalogShowsThem() throws {
        let midEdit = try Fixture(contentsOf: fixtures.appendingPathComponent("editor_mid_edit.json")).editorModel()
        // The commented lines are selected, as the session's anchor says.
        let selected = UTF16Text.substring(midEdit.text, midEdit.selection)
        XCTAssertEqual(selected, "// C/E Dm       Am       G\n// Up above the world so high,")
        XCTAssertEqual(Set(midEdit.spans.map(\.kind)), Set(SpanKind.allCases))
        XCTAssertEqual(midEdit.highlightedIdentity, midEdit.identity, "the spans are the session's for this text")
        XCTAssertTrue(midEdit.canUndo, "the insert and the comment are undo steps")
        XCTAssertEqual(midEdit.notation, "american")
        let european = try Fixture(contentsOf: fixtures.appendingPathComponent("editor_european.json")).editorModel()
        XCTAssertEqual(european.notation, "european")
        XCTAssertTrue(european.text.hasPrefix("{bpm: 190} {time: 4/4} {key: Do}\n"), european.text)
        XCTAssertTrue(european.spans.contains { $0.kind == .chord })
    }
}

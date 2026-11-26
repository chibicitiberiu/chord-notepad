import Foundation
import XCTest

@testable import ChordNotepadKit

extension IntegrationTests {
    /// The last song's launches over the real core (docs/IOS.md, "The last
    /// song"): each starts from the empty untitled song, as the start-up
    /// replay leaves it, sends what `LastSongPolicy` decides, and feeds the
    /// session's real output through the launch state as the app does. A
    /// saved song read again, one whose file is gone (the open's error), a
    /// changed song with its document, and one whose document is gone.
    func checkLastSongLaunches(_ session: Session, _ log: EventLog, _ store: MemoryStore) async throws {
        store.put("songs/Saved.txt", "G   D\nsaved words\n")
        let savedRef = memoryRef("songs/Saved.txt")

        // A saved song without changes, left in Edit: read again from its file, in Edit.
        try await emptySong(session, log)
        let unchanged = LastSong(text: "old words", documentId: savedRef.id, displayName: savedRef.displayName,
                                 location: savedRef.location, modified: false, mode: .edit)
        guard case .open(let ref, let readOnly, let mode) = LastSongPolicy.launchSong(.song(unchanged)) else {
            return XCTFail("an unchanged saved song is read again")
        }
        var ui = try await launch(session, log, .openDocument(readOnly: readOnly, ref: ref)) {
            $0.modes.expectRestore(documentId: ref.id, modified: false, mode: mode)
        }
        XCTAssertFalse(ui.launching, "the launch state ends with the song")
        XCTAssertEqual(ui.mode, .edit)
        var document = try log.decodeLatest(DocumentState.self, "DocumentState")
        XCTAssertEqual(document.documentId, savedRef.id)
        XCTAssertFalse(document.isModified)
        try await log.wait("the file's text") {
            log.events(since: 0, type: "TextEdited").last.flatMap { try? log.decode(TextEdited.self, $0) }?
                .replacement == "G   D\nsaved words\n"
        }

        // Its file gone: the open's usual error over the empty song ends the launch state.
        try await emptySong(session, log)
        let goneRef = memoryRef("songs/Gone.txt")
        let beforeGone = log.count
        ui = try await launch(session, log, .openDocument(readOnly: false, ref: goneRef)) {
            $0.modes.expectRestore(documentId: goneRef.id, modified: false, mode: .play)
        }
        XCTAssertFalse(ui.launching)
        XCTAssertFalse(ui.modes.expectingOpen)
        XCTAssertEqual(ui.mode, .edit, "the empty song")
        XCTAssertEqual(try log.decode(UserError.self, log.events(since: beforeGone, type: "UserError").last).message,
                       "Failed to open file:\nOn My iPhone\n\nFile not found: songs/Gone.txt")
        XCTAssertNil(try log.decodeLatest(DocumentState.self, "DocumentState").documentId)

        // Changed, its document reachable: the draft of that document, in Play as left.
        try await emptySong(session, log)
        let changed = LastSong(text: "G   D\nnew words\n", documentId: savedRef.id, displayName: savedRef.displayName,
                               location: savedRef.location, modified: true, mode: .play)
        var restore = LastSongPolicy.restore(changed, resolved: savedRef)
        ui = try await launch(session, log, restore.command) {
            $0.modes.expectRestore(documentId: restore.documentId, modified: restore.modified, mode: changed.appMode)
        }
        XCTAssertFalse(ui.launching)
        XCTAssertEqual(ui.mode, .play)
        document = try log.decodeLatest(DocumentState.self, "DocumentState")
        XCTAssertEqual(document.documentId, savedRef.id)
        XCTAssertTrue(document.isModified)
        XCTAssertEqual(store.contents(savedRef.id), Data("G   D\nsaved words\n".utf8), "the file isn't touched")

        // Changed, its document gone: the words as a new, unsaved song, in Edit as left.
        try await emptySong(session, log)
        var lost = changed
        lost.documentId = goneRef.id
        lost.mode = AppMode.edit.rawValue
        restore = LastSongPolicy.restore(lost, resolved: nil)
        XCTAssertNotNil(restore.notice)
        ui = try await launch(session, log, restore.command) {
            $0.modes.expectRestore(documentId: restore.documentId, modified: restore.modified, mode: lost.appMode)
        }
        XCTAssertFalse(ui.launching, "an untitled draft ends it too")
        XCTAssertEqual(ui.mode, .edit)
        document = try log.decodeLatest(DocumentState.self, "DocumentState")
        XCTAssertNil(document.documentId)
        XCTAssertTrue(document.isModified)
        try await emptySong(session, log)
    }

    /// Leave the session on an empty untitled song (Don't save if it asks).
    private func emptySong(_ session: Session, _ log: EventLog) async throws {
        let asked = log.count
        session.submit(.newDocument())
        try await log.wait("an empty song") {
            if let request = log.events(since: asked, type: "ConfirmDiscardRequest").last,
               let question = try? log.decode(ConfirmDiscardRequest.self, request),
               log.events(since: asked, type: "DocumentState").isEmpty {
                session.submit(.respondToConfirmDiscardRequest(requestId: question.requestId, value: .discard))
            }
            guard let document = try? log.decodeLatest(DocumentState.self, "DocumentState") else { return false }
            return document.documentId == nil && !document.isModified
        }
        await log.waitQuiet()
    }

    /// A launch: the launch state up, the session's empty untitled song (the
    /// start-up replay), `expect`, then `command`; the session's output fed
    /// through the screen's state as `AppModel.receive` does, until the
    /// launch state ends.
    private func launch(_ session: Session, _ log: EventLog, _ command: BridgeCommand,
                        expect: (inout MainUiState) -> Void) async throws -> MainUiState {
        var ui = MainUiState()
        ui.launchBegan()
        // The app asks before the reader task hands it the replay.
        expect(&ui)
        ui.documentChanged(try log.decodeLatest(DocumentState.self, "DocumentState"))
        XCTAssertTrue(ui.launching, "the replay's empty song isn't the launch's")
        var seen = log.count
        session.submit(command)
        try await log.wait("the launch's song") {
            let new = log.events(since: seen)
            seen += new.count
            for event in new {
                guard let output = try? SessionOutput.decode(typeName: event.typeName, json: event.json) else { continue }
                ui.received(output)
                if case .documentState(let document) = output { ui.documentChanged(document) }
            }
            return !ui.launching
        }
        await log.waitQuiet()
        return ui
    }
}

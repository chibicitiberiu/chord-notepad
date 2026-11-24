import Foundation
import XCTest

@testable import ChordNotepadKit

/// One session over the real core (FakePlayer, the venv's packages), as the
/// app runs it: start, restore a draft, check what comes back, save through
/// the Swift store, fetch and decode a chord sheet buffer, then shut down.
///
/// It also records the session's output for a few scenes into ios/Fixtures/,
/// which the SwiftUI preview catalog shows without Python: with
/// `CN_RECORD_FIXTURES=1` (`make ios-fixtures`) it writes them, otherwise it
/// checks the committed ones still match.
///
/// One process has one interpreter and starts one session, so this is a single
/// scenario rather than independent test methods.
final class IntegrationTests: XCTestCase {
    func testASessionOverTheRealCore() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let filesDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("cn-kit-\(UUID().uuidString)").path
        try FileManager.default.createDirectory(atPath: filesDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(atPath: filesDir) }
        let examples = TestPython.repo.appendingPathComponent("examples")
        let quickStart = try String(contentsOf: examples.appendingPathComponent("01_quick_start.txt"), encoding: .utf8)
        let complete = try String(contentsOf: examples.appendingPathComponent("02_american_complete.txt"), encoding: .utf8)
        let store = MemoryStore(files: ["locked.txt": Data("C G\n".utf8)])

        let session = try await Session.start(
            runtime: runtime, store: store,
            options: Session.LaunchOptions(filesDir: filesDir, configureLogging: false))
        let log = EventLog()
        let reader = Task { for await event in session.events { log.append(event) } }
        let scenes = SceneRecorder(runtime: runtime, log: log, filesDir: filesDir)

        // -- an empty song: the replay of every state ---------------------------------
        try await log.wait("the replay") {
            ["EditorState", "HighlightState", "DocumentState", "StatusState", "ToolbarState",
             "PlaybackState", "SettingsState", "ChordSheetState"].allSatisfy { log.latest($0) != nil }
        }
        await log.waitQuiet()
        try await scenes.record("empty_song", "A new, empty song: the replay of every state at start.", from: 0)

        // -- a draft with a supplementary character: offsets are code points ---------
        let draft = "😀 Am  C\nla la\n"
        var mark = log.count
        session.submit(.restoreDraft(document: memoryRef("song.txt"), modified: true, readOnly: false, text: draft))
        try await log.wait("the draft's highlights") { log.latest("HighlightState", since: mark) != nil }
        let highlight = try log.decodeLatest(HighlightState.self, "HighlightState")
        XCTAssertEqual(highlight.spans.filter { $0.kind == .chord }.map { [$0.start, $0.end] }, [[2, 4], [6, 7]])
        XCTAssertEqual(OffsetMapper(draft).toUTF16(6), 7, "C is UTF-16 offset 7, after the surrogate pair")
        let edited = try log.decode(TextEdited.self, log.events(since: mark, type: "TextEdited").last)
        XCTAssertEqual(edited.replacement, draft)
        XCTAssertEqual(edited.undo, .reset)
        try await log.wait("the draft's document") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.documentId == "song.txt"
        }
        XCTAssertTrue(try log.decodeLatest(DocumentState.self, "DocumentState").isModified)
        let editor = try log.decodeLatest(EditorState.self, "EditorState")
        XCTAssertFalse(editor.readOnly)

        // -- save: the core encodes the text and writes it through the store ---------
        session.submit(.save())
        try await log.wait("the save") { store.contents("song.txt") == Data(draft.utf8) }
        try await log.wait("the saved state") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.isModified == false
        }
        XCTAssertTrue(store.calls.contains("addRecent song.txt"), "\(store.calls)")

        // -- the quick-start song in Edit -------------------------------------------------
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("examples/01_quick_start.txt"), modified: false,
                                     readOnly: false, text: quickStart))
        try await log.wait("the quick-start song") {
            (try? log.decode(HighlightState.self, log.latest("HighlightState", since: mark)))?.spans.isEmpty == false
        }
        await log.waitQuiet()
        try await scenes.record("quick_start_edit", "The quick-start example open in Edit.", from: mark)

        // -- a song in Play with its chord sheet ------------------------------------------
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("examples/02_american_complete.txt"), modified: false,
                                     readOnly: false, text: complete))
        session.submit(.setChordSheetVisible(visible: true))
        try await log.wait("the chord sheet's render", timeout: 30) {
            guard let sheet = try? log.decode(ChordSheetState.self, log.latest("ChordSheetState", since: mark)) else {
                return false
            }
            return sheet.visible && sheet.cursorIndex != nil
        }
        // The playhead on the third chord, as a tap in Play mode puts it.
        let thirdChord = try log.decodeLatest(HighlightState.self, "HighlightState").spans
            .filter { $0.kind == .chord }[2]
        session.submit(.setPlayhead(offset: thirdChord.start))
        try await log.wait("the playhead") {
            (try? log.decodeLatest(PlaybackState.self, "PlaybackState"))?.playheadOffset == thirdChord.start
        }
        await log.waitQuiet()
        let sheet = try log.decodeLatest(ChordSheetState.self, "ChordSheetState")
        let data = await session.chordSheetBuffer(height: Double(sheet.height))
        let buffer = try SheetBuffer.decode(try XCTUnwrap(data, "no chord sheet buffer"))
        XCTAssertEqual(buffer.viewId, sheet.activeView)
        XCTAssertEqual(buffer.slots.count, 133, "examples/02_american_complete.txt has 133 chords")
        XCTAssertEqual(buffer.height, Float(sheet.height))
        XCTAssertGreaterThan(buffer.content.count, 100)
        try await scenes.record("play_with_chord_sheet",
                                "The complete American example in Play: chord sheet shown, playhead on the third chord.",
                                from: mark)

        // -- errors and statuses ------------------------------------------------------------
        mark = log.count
        session.submit(.openDocument(readOnly: false, ref: memoryRef("missing")))
        try await log.wait("the open failure") { !log.events(since: mark, type: "UserError").isEmpty }
        let failure = try log.decode(UserError.self, log.events(since: mark, type: "UserError").last)
        XCTAssertTrue(failure.message.contains("File not found: missing"), failure.message)
        let revisionBefore = try log.decodeLatest(ChordSheetState.self, "ChordSheetState").songRevision
        session.submit(.restoreDraft(document: memoryRef("locked.txt"), modified: false, readOnly: false,
                                     text: "C G\n"))
        session.submit(.renameDocument(name: "Better name"))
        try await log.wait("the refused rename") { !log.events(since: mark, type: "RenameFailed").isEmpty }
        // The scene records the strip's render of "C G" and the status it gives
        // ("Bar 1/2"); the render is debounced, so wait for it, not for quiet.
        try await log.wait("the chord sheet's render of the new text", timeout: 30) {
            guard let sheet = try? log.decodeLatest(ChordSheetState.self, "ChordSheetState"),
                  let status = try? log.decodeLatest(StatusState.self, "StatusState") else { return false }
            return sheet.songRevision > revisionBefore && sheet.cursorIndex != nil && status.text.hasPrefix("Bar ")
        }
        let refused = try log.decode(RenameFailed.self, log.events(since: mark, type: "RenameFailed").last)
        XCTAssertTrue(refused.canSaveAs, "a storage refusal offers Save As")
        XCTAssertEqual(refused.name, "Better name")
        await log.waitQuiet()
        try await scenes.record("errors", "A document that can't be opened, then a rename the storage refuses.",
                                from: mark)

        // -- every output decoded with the generated types; nothing unexpected -------------
        for event in log.events(since: 0) {
            XCTAssertNoThrow(try SessionOutput.decode(typeName: event.typeName, json: event.json),
                             "\(event.typeName) \(event.json)")
        }
        XCTAssertEqual(log.events(since: 0, type: "UnexpectedError").map(\.json), [])

        await session.shutdown()
        await reader.value
        XCTAssertNotNil(FileManager.default.contents(
            atPath: filesDir + "/config/chord-notepad/settings.json"), "shutdown saves the config")
    }
}

/// Every event the session sent, in order, safe to read from the test.
final class EventLog: @unchecked Sendable {
    private let lock = NSLock()
    private var all: [Session.Event] = []
    private var lastArrival = Date()

    func append(_ event: Session.Event) {
        lock.withLock {
            all.append(event)
            lastArrival = Date()
        }
    }

    var count: Int { lock.withLock { all.count } }

    func events(since index: Int, type: String? = nil) -> [Session.Event] {
        lock.withLock { all[index...].filter { type == nil || $0.typeName == type } }
    }

    /// The newest JSON of `type` at or after `index`.
    func latest(_ type: String, since index: Int = 0) -> String? {
        events(since: index, type: type).last?.json
    }

    /// `json` decoded; throws (without failing the test: waits poll this) when nil.
    func decode<T: Decodable>(_: T.Type, _ json: String?) throws -> T {
        guard let json else { throw PythonError("no \(T.self) yet") }
        return try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    func decode<T: Decodable>(_: T.Type, _ event: Session.Event?) throws -> T {
        try decode(T.self, event?.json)
    }

    func decodeLatest<T: Decodable>(_: T.Type, _ type: String) throws -> T {
        try decode(T.self, latest(type))
    }

    /// Wait until `condition` holds (polled every 20 ms).
    func wait(_ what: String, timeout: TimeInterval = 15, _ condition: () -> Bool) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition() {
            if Date() > deadline {
                let types = events(since: 0).map(\.typeName)
                XCTFail("Timed out waiting for \(what); got \(types.suffix(30))")
                throw CancellationError()
            }
            try await Task.sleep(nanoseconds: 20_000_000)
        }
    }

    /// Wait until no event has arrived for `quiet` seconds (debounced renders, autosave).
    func waitQuiet(_ quiet: TimeInterval = 0.5) async {
        while Date().timeIntervalSince(lock.withLock { lastArrival }) < quiet {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
    }
}

/// Writes or checks the ios/Fixtures scenes (canonical JSON, by Python).
struct SceneRecorder {
    let runtime: PythonRuntime
    let log: EventLog
    let filesDir: String

    static let directory = TestPython.repo.appendingPathComponent("ios/Fixtures")
    static var recording: Bool { TestPython.environment["CN_RECORD_FIXTURES"] == "1" }

    /// One scene: the newest JSON of every state (the whole screen) and the
    /// other outputs since `index`, in order, all as they crossed the bridge.
    func record(_ name: String, _ description: String, from index: Int) async throws {
        var states: [String: String] = [:]
        for event in log.events(since: 0) {
            if (try? SessionOutput.decode(typeName: event.typeName, json: event.json))?.kind == .state {
                states[event.typeName] = event.json
            }
        }
        let others = log.events(since: index).filter { states[$0.typeName] == nil }
        func quoted(_ text: String) -> String {
            String(decoding: try! JSONEncoder().encode(text), as: UTF8.self)
        }
        let stateMembers = states.keys.sorted().map { "\(quoted($0)): \(states[$0]!)" }
        let eventMembers = others.map { "{\"type\": \(quoted($0.typeName)), \"json\": \($0.json)}" }
        let scene = """
            {"scene": \(quoted(name)), "description": \(quoted(description)),
             "states": {\(stateMembers.joined(separator: ", "))},
             "events": [\(eventMembers.joined(separator: ", "))]}
            """
        let path = Self.directory.appendingPathComponent("\(name).json").path
        let problem = try await runtime.call("cn_kit_testmod", "scene_fixture",
                                             [path, scene, filesDir, Self.recording ? "1" : "0"])
        XCTAssertEqual(problem, "", "ios/Fixtures/\(name).json differs; if the change is intended, "
                       + "run make ios-fixtures:\n\(problem ?? "")")
    }
}

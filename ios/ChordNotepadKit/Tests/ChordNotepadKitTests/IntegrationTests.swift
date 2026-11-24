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
        // The self-test's audio status sees the running session's player
        // (here the FakePlayer, which counts as started and plays no SoundFont).
        let audio = try jsonObject(try await runtime.call("chordnotepad_ios.diagnostics", "audio_status"))
        XCTAssertEqual(audio["session"] as? Bool, true, "\(audio)")
        XCTAssertEqual(audio["initialized"] as? Bool, true, "\(audio)")
        XCTAssertTrue(audio["error"] is NSNull, "\(audio)")
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
                                from: mark, buffers: try await scenes.buffers(session, for: sheet))

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
                                from: mark,
                                buffers: try await scenes.buffers(session, for: try log.decodeLatest(ChordSheetState.self, "ChordSheetState")))

        // -- the chord sheet's other views (after errors, so its states stay as they were) --
        mark = log.count
        let songMark = mark
        session.submit(.restoreDraft(document: memoryRef("examples/02_american_complete.txt"), modified: false,
                                     readOnly: false, text: complete))
        let chords = try await waitForChords(log, since: mark, count: 133)
        session.submit(.setChordSheetView(viewId: "staff"))
        session.submit(.chordSheetZoom(step: 1))
        session.submit(.setPlayhead(offset: chords[24].start))
        let staff = try await waitForSheet(log, "the zoomed staff with the playhead on chord 24") {
            $0.activeView == "staff" && abs($0.zoom - 1.2) < 1e-9 && $0.cursorIndex == 24
        }
        await log.waitQuiet()
        try await scenes.record("chord_sheet_staff",
                                "The complete example on the staff, zoomed in one step, playhead on chord 24.",
                                from: mark, buffers: try await scenes.buffers(session, for: staff))

        // Fret cards need a fretted voicing; until then the view is unavailable (and ignored).
        // Recorded from the song's restore, like the staff scene: the editor's
        // text only comes in that TextEdited.
        session.submit(.setVoicing(voicing: "guitar:standard"))
        _ = try await waitForSheet(log, "the fret view to become available") {
            $0.views.contains { $0.viewId == "fret" && $0.available }
        }
        session.submit(.setChordSheetView(viewId: "fret"))
        session.submit(.setPlayhead(offset: chords[0].start))
        let fret = try await waitForSheet(log, "the fret cards with the playhead on the first chord") {
            $0.activeView == "fret" && $0.cursorIndex == 0
        }
        await log.waitQuiet()
        try await scenes.record("chord_sheet_fret",
                                "The complete example as guitar fret cards (standard tuning), playhead on the first chord.",
                                from: songMark, buffers: try await scenes.buffers(session, for: fret))

        // -- the editor (last: a notation change stays in every later scene's states) ------
        session.submit(.setChordSheetVisible(visible: false))
        _ = try await waitForSheet(log, "the chord sheet to hide") { !$0.visible }
        await log.waitQuiet()

        // Mid-edit: the session's own edits (the fixture can't carry the user's
        // typing, which the session doesn't echo): a line with an invalid
        // directive, a redundant one and a chord the core doesn't know, then two
        // lines commented out with the selection the command leaves.
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("examples/01_quick_start.txt"), modified: false,
                                     readOnly: false, text: quickStart))
        _ = try await waitForHighlight(log, since: mark, "the quick-start song for the editor")
        // {key: G} is replaced by {key: C} before any chord plays: redundant.
        let inserted = "{bpm: 1000} {key: G} {key: C}\nC      Gsus9    F/A    G7\n"
        let verse = (quickStart as NSString).range(of: "{label: verse}\n")
        let at = OffsetMapper(quickStart).toCodePoint(NSMaxRange(verse))
        session.submit(.insertText(at: at, text: inserted))
        let afterInsert = try await waitForEdit(log, since: mark) { $0.undo == .plain }
        let editedText = String(quickStart.unicodeScalars.prefix(at)) + inserted
            + String(quickStart.unicodeScalars.dropFirst(at))
        let lines = (editedText as NSString).range(of: "C/E Dm       Am       G\nUp above the world so high,")
        let mapper = OffsetMapper(editedText)
        session.submit(.toggleComment(anchor: mapper.toCodePoint(lines.location),
                                      cursor: mapper.toCodePoint(NSMaxRange(lines))))
        let commented = try await waitForEdit(log, since: mark) {
            $0.anchor != nil && $0.textRevision > afterInsert.textRevision
        }
        let midEdit = try await waitForHighlight(log, since: mark, "the edited song's highlight") {
            $0.textRevision == commented.textRevision
        }
        let kinds = Set(midEdit.spans.map(\.kind))
        XCTAssertEqual(kinds, Set(SpanKind.allCases), "the scene shows every span kind: \(kinds)")
        await log.waitQuiet()
        try await scenes.record("editor_mid_edit",
                                "The quick-start song mid-edit: an invalid and a redundant directive, an unknown "
                                + "chord, two lines commented out and selected.", from: mark)

        // European: the quick-start song converted (Convert on the ribbon).
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("examples/01_quick_start.txt"), modified: false,
                                     readOnly: false, text: quickStart))
        _ = try await waitForHighlight(log, since: mark, "the quick-start song again")
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        session.submit(.convertNotation(cursor: 0, target: "european"))
        let converted = try await waitForEdit(log, since: mark) { $0.textRevision > restored.textRevision }
        XCTAssertTrue(converted.replacement.contains("Do"), converted.replacement)
        _ = try await waitForHighlight(log, since: mark, "the converted song's highlight") {
            $0.textRevision == converted.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        try await log.wait("the European notation") {
            (try? log.decodeLatest(EditorState.self, "EditorState"))?.notation == "european"
        }
        await log.waitQuiet()
        try await scenes.record("editor_european", "The quick-start song converted to European notation.",
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

/// The chord spans of the newest highlight once it has `count` of them.
private func waitForChords(_ log: EventLog, since mark: Int, count: Int) async throws -> [Span] {
    try await log.wait("the song's \(count) chords") {
        (try? log.decode(HighlightState.self, log.latest("HighlightState", since: mark)))?
            .spans.filter { $0.kind == .chord }.count == count
    }
    return try log.decodeLatest(HighlightState.self, "HighlightState").spans.filter { $0.kind == .chord }
}

/// The newest `HighlightState` since `mark` once it has spans and `condition` holds for it.
private func waitForHighlight(_ log: EventLog, since mark: Int, _ what: String,
                              _ condition: @escaping (HighlightState) -> Bool = { _ in true })
    async throws -> HighlightState {
    try await log.wait(what) {
        guard let state = try? log.decode(HighlightState.self, log.latest("HighlightState", since: mark)) else {
            return false
        }
        return !state.spans.isEmpty && condition(state)
    }
    return try log.decode(HighlightState.self, log.latest("HighlightState", since: mark))
}

/// The newest `TextEdited` since `mark` once `condition` holds for it.
private func waitForEdit(_ log: EventLog, since mark: Int,
                         _ condition: @escaping (TextEdited) -> Bool) async throws -> TextEdited {
    try await log.wait("an edit") {
        (try? log.decode(TextEdited.self, log.events(since: mark, type: "TextEdited").last)).map(condition) ?? false
    }
    return try log.decode(TextEdited.self, log.events(since: mark, type: "TextEdited").last)
}

/// The newest `ChordSheetState` once `condition` holds for it.
private func waitForSheet(_ log: EventLog, _ what: String,
                          _ condition: @escaping (ChordSheetState) -> Bool) async throws -> ChordSheetState {
    try await log.wait(what, timeout: 30) {
        (try? log.decodeLatest(ChordSheetState.self, "ChordSheetState")).map(condition) ?? false
    }
    return try log.decodeLatest(ChordSheetState.self, "ChordSheetState")
}

/// Writes or checks the ios/Fixtures scenes (canonical JSON, by Python).
struct SceneRecorder {
    let runtime: PythonRuntime
    let log: EventLog
    let filesDir: String

    static let directory = TestPython.repo.appendingPathComponent("ios/Fixtures")
    static var recording: Bool { TestPython.environment["CN_RECORD_FIXTURES"] == "1" }

    /// The windows the preview catalog renders in, in points (the app's
    /// `CatalogRenderer.devices`: iPhone 17 and iPad Air 11-inch).
    static let catalogWindows: [(width: Double, height: Double)] = [(402, 874), (820, 1180)]

    /// The content heights the catalog's chord sheet asks for in those
    /// windows, for a sheet whose stored height is `stored` (the app's split
    /// and pane metrics, from the kit).
    static func catalogHeights(stored: Int) -> [Int] {
        Array(Set(catalogWindows.map { window in
            let pane = ChordSheetSplit.wantedHeight(stored: stored, windowWidth: window.width,
                                                    windowHeight: window.height)
            return ChordSheetPaneMetrics.contentHeight(stripHeight: ChordSheetPaneMetrics.stripHeight(paneHeight: pane))
        })).sorted()
    }

    /// The chord sheet's buffers for `sheet` at the catalog's heights,
    /// checked against the state they were packed for.
    func buffers(_ session: Session, for sheet: ChordSheetState) async throws -> [Int: Data] {
        var buffers: [Int: Data] = [:]
        for height in Self.catalogHeights(stored: sheet.height) {
            let fetched = await session.chordSheetBuffer(height: Double(height))
            let data = try XCTUnwrap(fetched, "no buffer at \(height)")
            let buffer = try SheetBuffer.decode(data)
            XCTAssertEqual(buffer.viewId, sheet.activeView)
            XCTAssertEqual(Double(buffer.zoom), sheet.zoom, accuracy: 1e-6)
            XCTAssertEqual(buffer.height, Float(height))
            buffers[height] = data
        }
        return buffers
    }

    /// One scene: the newest JSON of every state (the whole screen) and the
    /// other outputs since `index`, in order, all as they crossed the bridge,
    /// with the chord sheet's `buffers` (base64, by content height).
    func record(_ name: String, _ description: String, from index: Int,
                buffers: [Int: Data] = [:]) async throws {
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
        let bufferMembers = buffers.keys.sorted().map {
            "{\"height\": \($0), \"base64\": \(quoted(buffers[$0]!.base64EncodedString()))}"
        }
        let scene = """
            {"scene": \(quoted(name)), "description": \(quoted(description)),
             "states": {\(stateMembers.joined(separator: ", "))},
             "events": [\(eventMembers.joined(separator: ", "))],
             "chord_sheet_buffers": [\(bufferMembers.joined(separator: ", "))]}
            """
        let path = Self.directory.appendingPathComponent("\(name).json").path
        let problem = try await runtime.call("cn_kit_testmod", "scene_fixture",
                                             [path, scene, filesDir, Self.recording ? "1" : "0"])
        XCTAssertEqual(problem, "", "ios/Fixtures/\(name).json differs; if the change is intended, "
                       + "run make ios-fixtures:\n\(problem ?? "")")
    }
}

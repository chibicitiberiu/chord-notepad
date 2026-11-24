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

        // -- Scarborough Fair, as the Android store screenshots show it ---------------------
        // (android/tools/store_shots.json): Edit, then Play frozen mid-song on the
        // piano roll, the fret cards and the tab, with the strip 330 pt tall.
        let scarborough = try String(contentsOf: TestPython.repo.appendingPathComponent(
            "android/tools/help_shot_songs/scarborough_fair.txt"), encoding: .utf8)
        session.submit(.setVoicing(voicing: "piano"))
        session.submit(.setChordSheetView(viewId: "keyboard"))
        session.submit(.setChordSheetHeight(px: 330))
        // The piano voicing's render of the previous song first (fret cards no
        // longer available), so the revision read below already counts it.
        _ = try await waitForSheet(log, "the piano roll at 330 pt") {
            $0.activeView == "keyboard" && $0.height == 330
                && !$0.views.contains { $0.viewId == "fret" && $0.available }
        }
        await log.waitQuiet()
        let revisionBeforeFair = try log.decodeLatest(ChordSheetState.self, "ChordSheetState").songRevision
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Scarborough Fair.txt"), modified: false, readOnly: false,
                                     text: scarborough))
        let fair = try await waitForChords(log, since: mark, count: 28)
        // The strip's render of the new song is debounced and may land after a
        // quiet spell, so wait for it (the new revision, the playhead's chord,
        // the song's own sections) rather than for quiet alone: a scene recorded
        // before it carried the previous song's sheet and timeline.
        try await log.wait("the chord sheet's render of Scarborough Fair", timeout: 30) {
            guard let sheet = try? log.decodeLatest(ChordSheetState.self, "ChordSheetState"),
                  let playback = try? log.decodeLatest(PlaybackState.self, "PlaybackState") else { return false }
            return sheet.songRevision > revisionBeforeFair && sheet.cursorIndex != nil
                && playback.sections.map(\.label).contains("verse 2")
        }
        await log.waitQuiet()
        try await scenes.record("scarborough_edit", "Scarborough Fair (the Android store screenshots' song) in Edit.",
                                from: mark)

        var cut = try await freeze(session, log, chord: 4, of: fair)
        var frozen = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
        try await scenes.record("scarborough_piano_roll",
                                "Scarborough Fair playing on the piano roll, frozen as chord 4 (G, bar 5) sounds.",
                                from: mark, upTo: cut, buffers: try await scenes.buffers(session, for: frozen))

        session.submit(.setVoicing(voicing: "guitar:standard"))
        _ = try await waitForSheet(log, "the fret view to become available again") {
            $0.views.contains { $0.viewId == "fret" && $0.available }
        }
        session.submit(.setChordSheetView(viewId: "fret"))
        session.submit(.chordSheetZoom(step: -4))
        _ = try await waitForSheet(log, "the fret cards zoomed out") { $0.activeView == "fret" && $0.zoom == 0.5 }
        cut = try await freeze(session, log, chord: 3, of: fair)
        frozen = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
        try await scenes.record("scarborough_fret",
                                "Scarborough Fair playing on guitar fret cards (zoom 0.5), frozen as chord 3 (C) sounds.",
                                from: mark, upTo: cut, buffers: try await scenes.buffers(session, for: frozen))

        session.submit(.setChordSheetView(viewId: "tab"))
        session.submit(.chordSheetZoom(step: -1))
        _ = try await waitForSheet(log, "the tab zoomed out a step") { $0.activeView == "tab" && $0.zoom < 1 }
        cut = try await freeze(session, log, chord: 6, of: fair)
        frozen = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
        try await scenes.record("scarborough_tab",
                                "Scarborough Fair playing on the guitar tab, frozen as chord 6 (Em) sounds.",
                                from: mark, upTo: cut, buffers: try await scenes.buffers(session, for: frozen))

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

        // -- files (last again: the recent list and the document stay out of the
        // scenes before): open from the store, Recent, save, Save As, an export,
        // the unsaved-changes question, a recent song that has gone --------------------
        let morning = "{bpm: 90}\nC        G        Am       F\nMorning has broken, like the first morning\n"
        let evening = "{key: Am}\nAm       Dm       E7       Am\nEvening falls on the harbour\n"
        let lullaby = "{bpm: 72} {time: 3/4}\nG        Em       C        D\nHush now, the stars are out\n"
        store.put("songs/Morning.txt", morning)
        store.put("songs/Evening.txt", evening)
        store.put("songs/Lullaby.txt", lullaby)
        for (id, text) in [("songs/Morning.txt", morning), ("songs/Evening.txt", evening)] {
            let opened = log.count
            session.submit(.openDocument(readOnly: false, ref: memoryRef(id)))
            if id == "songs/Morning.txt" {
                // The converted song counts as changed: Open asks first, Don't save goes on.
                try await log.wait("Open's unsaved-changes question") {
                    !log.events(since: opened, type: "ConfirmDiscardRequest").isEmpty
                }
                let first = try log.decode(ConfirmDiscardRequest.self,
                                           log.events(since: opened, type: "ConfirmDiscardRequest").last)
                session.submit(.respondToConfirmDiscardRequest(requestId: first.requestId, value: .discard))
            }
            try await log.wait("the open of \(id)") {
                (try? log.decode(DocumentState.self, log.latest("DocumentState", since: opened)))?.documentId == id
            }
            let edit = try await waitForEdit(log, since: opened) { $0.undo == .reset }
            XCTAssertEqual(edit.replacement, text, "opened text replaces the editor's with a reset edit")
        }
        mark = log.count
        session.submit(.openDocument(readOnly: false, ref: memoryRef("songs/Lullaby.txt")))
        _ = try await waitForHighlight(log, since: mark, "the lullaby's highlight") {
            $0.spans.contains { $0.kind == .chord }
        }
        try await log.wait("the recent list") {
            (try? log.decodeLatest(RecentDocumentsState.self, "RecentDocumentsState"))?.items.map(\.id)
                == ["songs/Lullaby.txt", "songs/Evening.txt", "songs/Morning.txt", "song.txt"]
        }
        XCTAssertTrue(try log.decodeLatest(StatusState.self, "StatusState").text.hasPrefix("Opened: "))
        await log.waitQuiet()
        try await scenes.record("files_recent", "Three songs opened from the store, the last one on screen: "
                                + "the recent list has them and the song saved before.", from: mark)

        // Modified by the user's typing (set_text, not echoed), then saved in place.
        let typed = lullaby + "Sleep until the morning\n"
        session.submit(.setText(clientToken: 1, text: typed))
        try await log.wait("the modified flag") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.isModified == true
        }
        session.submit(.save())
        try await log.wait("the save in place") { store.contents("songs/Lullaby.txt") == Data(typed.utf8) }
        try await log.wait("the saved state") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.isModified == false
        }

        // Save As: the session asks where, with the document's name; the answer is a new id.
        var asked = log.count
        session.submit(.saveAs(name: nil))
        try await log.wait("Save As's picker request") { !log.events(since: asked, type: "PickDocumentRequest").isEmpty }
        let saveAs = try log.decode(PickDocumentRequest.self, log.events(since: asked, type: "PickDocumentRequest").last)
        XCTAssertEqual(saveAs.mode, .save)
        XCTAssertEqual(saveAs.suggestedName, "Lullaby.txt")
        XCTAssertEqual(pickerFor(saveAs), .save(suggestedName: "Lullaby.txt"))
        let copy = memoryRef("songs/Lullaby (2).txt")
        session.submit(.respondToPickDocumentRequest(requestId: saveAs.requestId, value: copy))
        try await log.wait("the copy") { store.contents(copy.id) == Data(typed.utf8) }
        try await log.wait("the copy as the open document") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.documentId == copy.id
        }
        XCTAssertEqual(store.recentIds.first, copy.id)

        // The copy again from Recent: the scenes below start from its text (the
        // user's set_text isn't echoed, so a scene can't carry the typed line).
        mark = log.count
        session.submit(.openRecent(ref: copy))
        let reopened = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        XCTAssertEqual(reopened.replacement, typed)
        _ = try await waitForHighlight(log, since: mark, "the copy's highlight") {
            $0.textRevision == reopened.textRevision
        }

        // Export MIDI: answered with a ref the store owns (iOS: a file for the
        // export picker); the render is written through the store.
        asked = log.count
        session.submit(.exportMidi())
        try await log.wait("the export's picker request") {
            !log.events(since: asked, type: "PickDocumentRequest").isEmpty
        }
        let export = try log.decode(PickDocumentRequest.self, log.events(since: asked, type: "PickDocumentRequest").last)
        XCTAssertEqual(export.mode, .exportMidi)
        XCTAssertEqual(export.suggestedName, "Lullaby (2).mid")
        XCTAssertEqual(pickerFor(export), .export(.exportMidi, suggestedName: "Lullaby (2).mid"))
        let exportRef = DocumentRef(displayName: "Lullaby (2).mid", id: "exports/Lullaby (2).mid",
                                    location: "Lullaby (2).mid")
        session.submit(.respondToPickDocumentRequest(requestId: export.requestId, value: exportRef))
        try await log.wait("the MIDI bytes") { store.contents(exportRef.id)?.prefix(4) == Data("MThd".utf8) }
        try await log.wait("the exported status") {
            (try? log.decodeLatest(StatusState.self, "StatusState"))?.text == "Exported MIDI: Lullaby (2).mid"
        }
        let statuses = log.events(since: asked, type: "StatusState").compactMap {
            try? log.decode(StatusState.self, $0).text
        }
        XCTAssertTrue(statuses.contains("Exporting MIDI: Lullaby (2).mid..."), "\(statuses)")
        XCTAssertNotEqual(store.recentIds.first, exportRef.id, "exports don't join Recent")
        XCTAssertEqual(try log.decodeLatest(DocumentState.self, "DocumentState").documentId, copy.id,
                       "nor change the open document")
        await log.waitQuiet()
        try await scenes.record("export_done", "The lullaby's copy exported as MIDI through the store.", from: mark)

        // The unsaved-changes question on New: Cancel keeps the song, Don't save clears it.
        session.submit(.insertText(at: 0, text: "{key: G}\n"))
        try await log.wait("the session's edit") {
            (try? log.decodeLatest(DocumentState.self, "DocumentState"))?.isModified == true
        }
        asked = log.count
        session.submit(.newDocument())
        try await log.wait("the unsaved-changes question") {
            !log.events(since: asked, type: "ConfirmDiscardRequest").isEmpty
        }
        var question = try log.decode(ConfirmDiscardRequest.self,
                                      log.events(since: asked, type: "ConfirmDiscardRequest").last)
        await log.waitQuiet()
        try await scenes.record("discard_question", "The lullaby's copy changed, then New: the unsaved-changes "
                                + "question.", from: mark)
        session.submit(.respondToConfirmDiscardRequest(requestId: question.requestId, value: .cancel))
        await log.waitQuiet()
        XCTAssertEqual(try log.decodeLatest(DocumentState.self, "DocumentState").documentId, copy.id, "Cancel: still open")
        XCTAssertTrue(try log.decodeLatest(DocumentState.self, "DocumentState").isModified)
        asked = log.count
        session.submit(.newDocument())
        try await log.wait("the question again") { !log.events(since: asked, type: "ConfirmDiscardRequest").isEmpty }
        question = try log.decode(ConfirmDiscardRequest.self, log.events(since: asked, type: "ConfirmDiscardRequest").last)
        session.submit(.respondToConfirmDiscardRequest(requestId: question.requestId, value: .discard))
        try await log.wait("a new, empty song") {
            guard let document = try? log.decodeLatest(DocumentState.self, "DocumentState") else { return false }
            return document.documentId == nil && !document.isModified
        }
        XCTAssertEqual(store.contents(copy.id), Data(typed.utf8), "Don't save: the file kept the saved text")

        // A recent song whose file has gone: the store's message, worded for the user.
        store.remove("songs/Morning.txt")
        asked = log.count
        session.submit(.openRecent(ref: memoryRef("songs/Morning.txt")))
        try await log.wait("the vanished song's error") { !log.events(since: asked, type: "UserError").isEmpty }
        let vanished = try log.decode(UserError.self, log.events(since: asked, type: "UserError").last)
        XCTAssertEqual(vanished.message, "Failed to open file:\nOn My iPhone\n\nFile not found: songs/Morning.txt")
        XCTAssertNil(try log.decodeLatest(DocumentState.self, "DocumentState").documentId, "nothing opened")

        try await checkSheetsAndTools(session, log, scenes)
        try await checkSettings(session, log, scenes, filesDir: filesDir)
        try await checkEditorFeatures(session, log, scenes)

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

    /// The events before `end`.
    func events(upTo end: Int, type: String? = nil) -> [Session.Event] {
        lock.withLock { all[..<end].filter { type == nil || $0.typeName == type } }
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

/// Play from chord `n` of `chords` and return the log index just after the
/// moment it sounds: its `PlaybackState` (playing, `chord_index` n) and the
/// status that names it. The FakePlayer plays the whole song at once, so a
/// scene "while playing" is the session's output up to that index (Android's
/// store screenshots freeze playback the same way, by republishing the states
/// seen while the chord sounded).
private func freeze(_ session: Session, _ log: EventLog, chord n: Int, of chords: [Span]) async throws -> Int {
    session.submit(.setPlayhead(offset: chords[n].start))
    try await log.wait("the playhead on chord \(n)") {
        guard let state = try? log.decodeLatest(PlaybackState.self, "PlaybackState") else { return false }
        return state.playheadOffset == chords[n].start && state.status == .idle
    }
    await log.waitQuiet()
    let mark = log.count
    session.submit(.playPause(fromOffset: nil))
    try await log.wait("the song to play to its end", timeout: 60) {
        let states = log.events(since: mark, type: "PlaybackState")
            .compactMap { try? JSONDecoder().decode(PlaybackState.self, from: Data($0.json.utf8)) }
        return states.contains { $0.status == .playing } && states.last?.status == .idle
    }
    await log.waitQuiet()
    let events = log.events(since: mark)
    let sounding = try XCTUnwrap(events.firstIndex {
        $0.typeName == "PlaybackState"
            && (try? JSONDecoder().decode(PlaybackState.self, from: Data($0.json.utf8)))?.chordIndex == n
    }, "chord \(n) never sounded")
    let named = try XCTUnwrap(events[sounding...].firstIndex { $0.typeName == "StatusState" },
                              "no status after chord \(n)")
    let cut = mark + named + 1
    let status = try log.decode(StatusState.self, events[named].json)
    XCTAssertTrue(status.text.contains("Playing"), status.text)
    let sheet = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
    XCTAssertEqual(sheet.currentIndex, n, "the strip's chord is the one sounding")
    let playing = try log.decode(PlaybackState.self, events[sounding].json)
    XCTAssertEqual(playing.playingSpan?.start, chords[n].start)
    return cut
}

/// The chord spans of the newest highlight once it has `count` of them.
func waitForChords(_ log: EventLog, since mark: Int, count: Int) async throws -> [Span] {
    try await log.wait("the song's \(count) chords") {
        (try? log.decode(HighlightState.self, log.latest("HighlightState", since: mark)))?
            .spans.filter { $0.kind == .chord }.count == count
    }
    return try log.decodeLatest(HighlightState.self, "HighlightState").spans.filter { $0.kind == .chord }
}

/// The newest `HighlightState` since `mark` once it has spans and `condition` holds for it.
func waitForHighlight(_ log: EventLog, since mark: Int, _ what: String,
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
func waitForEdit(_ log: EventLog, since mark: Int,
                         _ condition: @escaping (TextEdited) -> Bool) async throws -> TextEdited {
    try await log.wait("an edit") {
        (try? log.decode(TextEdited.self, log.events(since: mark, type: "TextEdited").last)).map(condition) ?? false
    }
    return try log.decode(TextEdited.self, log.events(since: mark, type: "TextEdited").last)
}

/// The newest `ChordSheetState` once `condition` holds for it.
func waitForSheet(_ log: EventLog, _ what: String,
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

    /// The windows the preview catalog shows Play mode in, in points (the
    /// app's `CatalogRenderer.devices`: iPhone 17 and iPad Air 11-inch, each
    /// upright and on its side).
    static let catalogWindows: [(width: Double, height: Double)] = [(402, 874), (820, 1180), (874, 402), (1180, 820)]

    /// The content heights the main screen's chord sheet asks for in those
    /// windows, for a sheet whose stored height is `stored` (below the text
    /// upright, in the side column on its side; ``MainSheetPane``).
    static func catalogHeights(stored: Int) -> [Int] {
        Array(Set(catalogWindows.compactMap { window in
            MainSheetPane.contentHeight(width: window.width, height: window.height, stored: stored)
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
    /// With `end`, the scene stops at that log index (a frozen moment of playback).
    func record(_ name: String, _ description: String, from index: Int, upTo end: Int? = nil,
                buffers: [Int: Data] = [:]) async throws {
        let end = end ?? log.count
        let upToEnd = log.events(upTo: end)
        var states: [String: String] = [:]
        for event in upToEnd {
            if (try? SessionOutput.decode(typeName: event.typeName, json: event.json))?.kind == .state {
                states[event.typeName] = event.json
            }
        }
        let others = upToEnd[index...].filter { states[$0.typeName] == nil }
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

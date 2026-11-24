import Foundation
import XCTest

@testable import ChordNotepadKit

extension IntegrationTests {
    /// The editor's remaining features over the real core: the find bar's
    /// Replace and Replace all on Scarborough Fair (the session's
    /// `replace_match` and `replace_all`, spans found by the kit's matching),
    /// the pinch's font steps, and the font family and size from Settings as
    /// the editor applies them. Last in the session (after Settings), so every
    /// scene before keeps its states; records `find_replaced`.
    func checkEditorFeatures(_ session: Session, _ log: EventLog, _ scenes: SceneRecorder) async throws {
        let songs = TestPython.repo.appendingPathComponent("android/tools/help_shot_songs")
        let fair = try String(contentsOf: songs.appendingPathComponent("scarborough_fair.txt"), encoding: .utf8)

        let mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Scarborough Fair.txt"), modified: false, readOnly: false,
                                     text: fair))
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Scarborough Fair's highlight for Find") {
            $0.textRevision == restored.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        var editor = try EditorModel.folding(log.events(since: mark).map {
            try SessionOutput.decode(typeName: $0.typeName, json: $0.json)
        })
        XCTAssertEqual(editor.text, fair)
        func fold(since index: Int) throws -> EditorEffects {
            var effects = EditorEffects()
            for event in log.events(since: index) {
                effects.merge(editor.receive(try SessionOutput.decode(typeName: event.typeName, json: event.json)))
            }
            return effects
        }
        func send(_ effects: EditorEffects) {
            for command in effects.commands { session.submit(command) }
        }

        // -- Replace: the first "Am" chord (match case, whole word), then on to the next ----------
        send(editor.find(.open(replace: true)))
        send(editor.find(.matchCase(true)))
        send(editor.find(.wholeWord(true)))
        send(editor.find(.query("Am")))
        send(editor.find(.replacement("Em")))
        let ams = TextFind.findAll(fair, query: "Am", matchCase: true, wholeWord: true)
        XCTAssertGreaterThan(ams.count, 10)
        XCTAssertEqual(editor.find.current, 1)
        var edits = log.count
        send(editor.find(.replace))
        let first = try await waitForEdit(log, since: edits) { $0.undo == .group }
        XCTAssertEqual(first.start, ams[0].start, "the session replaced the span the kit found")
        XCTAssertEqual(first.replacement, "Em")
        _ = try fold(since: edits)
        XCTAssertEqual(editor.find.current, 1, "the next Am selected")
        XCTAssertEqual(editor.find.matches.count, ams.count - 1)
        XCTAssertEqual(editor.find.matches.first, ams[1])

        // -- Replace all: one edit, the status counts them -------------------------------------
        edits = log.count
        send(editor.find(.replaceAll))
        let all = try await waitForEdit(log, since: edits) { $0.undo == .group }
        try await log.wait("Replace all's status") {
            (try? log.decodeLatest(StatusState.self, "StatusState"))?.text == "Replaced \(ams.count - 1) matches"
        }
        _ = try fold(since: edits)
        XCTAssertEqual(all.start, ams[1].start, "one edit from the first match left to the last")
        XCTAssertEqual(all.end, ams[ams.count - 1].end)
        var expected = Array(fair.unicodeScalars)
        for span in ams.reversed() {
            expected.replaceSubrange(span.start..<span.end, with: "Em".unicodeScalars)
        }
        XCTAssertEqual(editor.text, String(String.UnicodeScalarView(expected)))
        XCTAssertEqual(editor.find.countText, "No matches")
        _ = try await waitForHighlight(log, since: edits, "the replaced song's highlight") {
            $0.textRevision == all.textRevision
        }
        await log.waitQuiet()
        try await scenes.record("find_replaced", "Scarborough Fair after Find and Replace: the first Am chord (match "
                                + "case, whole words) replaced with Em by replace_match, then the rest by replace_all.",
                                from: mark)

        // A query that matches nothing: Replace all says so and changes nothing.
        send(editor.find(.query("Bb7")))
        edits = log.count
        send(editor.find(.replaceAll))
        try await log.wait("no matches") {
            (try? log.decodeLatest(StatusState.self, "StatusState"))?.text == "No matches for “Bb7”"
        }
        XCTAssertTrue(log.events(since: edits, type: "TextEdited").isEmpty)
        send(editor.find(.close))

        // -- the pinch: each new size a step, kept by the session -----------------------------
        let before = try log.decodeLatest(EditorState.self, "EditorState").fontSize
        var pinch = FontPinch()
        pinch.began(points: before)
        edits = log.count
        for scale in [1.1, 1.3, 1.5] {
            if let step = pinch.changed(scale: scale) { session.submit(.stepFontSize(delta: step)) }
        }
        pinch.ended()
        let pinched = EditorFont.pinchSize(before, zoom: 1.5)
        try await log.wait("the pinched size") {
            (try? log.decodeLatest(EditorState.self, "EditorState"))?.fontSize == pinched
        }
        _ = try fold(since: edits)
        XCTAssertEqual(editor.fontPoints, pinched)
        session.submit(.resetFontSize())
        try await log.wait("the size reset") {
            (try? log.decodeLatest(EditorState.self, "EditorState"))?.fontSize == EditorFont.defaultPoints
        }

        // -- the font from Settings: the family's kind and the size, as the editor draws them ------
        var controller = SettingsController()
        func feed() {
            if let settings = try? log.decodeLatest(SettingsState.self, "SettingsState") { controller.onSettings(settings) }
            if let state = try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState") {
                controller.onEditor(state)
            }
            for command in controller.takeCommands() { session.submit(command) }
        }
        feed()
        controller.start(needSchema: false)
        feed()
        try await log.wait("the settings edit") { (try? log.decodeLatest(VoicingEditorState.self,
                                                                          "VoicingEditorState"))?.active == true }
        feed()
        edits = log.count
        controller.updateDraft {
            $0.fontKind = .serif
            $0.fontSize = 16
        }
        feed()
        try await log.wait("the serif font at 16") {
            guard let state = try? log.decodeLatest(EditorState.self, "EditorState") else { return false }
            return state.fontSize == 16 && EditorFont.kind(forFamily: state.fontFamily) == .serif
        }
        _ = try fold(since: edits)
        XCTAssertEqual(editor.fontKind, .serif)
        XCTAssertEqual(editor.fontPoints, 16)
        controller.updateDraft {
            $0.fontKind = .monospace
            $0.fontSize = EditorFont.defaultPoints
        }
        feed()
        try await log.wait("the default font again") {
            guard let state = try? log.decodeLatest(EditorState.self, "EditorState") else { return false }
            return state.fontSize == EditorFont.defaultPoints && EditorFont.kind(forFamily: state.fontFamily) == .monospace
        }
        controller.requestClose()
        feed()
        try await log.wait("the edit ended") {
            (try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState"))?.active == false
        }
    }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// ``EditorModel``: Android's `EditorControllerTest` and `EditorWiringTest` as
/// behaviour (what the session gets, what the view shows), plus what iOS
/// adds: the undo history, composition, the selection a session edit makes,
/// and the actions.
final class EditorModelTests: XCTestCase {
    private var model = EditorModel()
    private var sent: [(name: String, args: [String: Any])] = []

    override func setUp() {
        model = EditorModel()
        sent = []
    }

    /// Run `effects`' commands through "the session" (record them) and check
    /// the view edits leave the model's text (what the app does).
    @discardableResult
    private func take(_ effects: EditorEffects, viewText: String? = nil) -> EditorEffects {
        for command in effects.commands {
            let json = try! command.argsJSON()
            sent.append((command.name, try! JSONSerialization.jsonObject(with: Data(json.utf8)) as! [String: Any]))
        }
        return effects
    }

    /// What the user does: the view's text becomes `text`, the caret at `caret` (default: after the change).
    private func type(_ text: String, caret: Int? = nil) {
        take(model.viewChanged(text: text, selection: UTF16Range(caret: caret ?? text.utf16.count), composing: false))
    }

    /// The user types `insert` at UTF-16 `at`.
    private func type(at: Int, _ insert: String) {
        let text = UTF16Text.replacing(model.text, UTF16Range(caret: at), with: insert)
        type(text, caret: at + insert.utf16.count)
    }

    private var setTexts: [(String, Int)] {
        sent.filter { $0.name == "set_text" }.map { ($0.args["text"] as! String, $0.args["client_token"] as! Int) }
    }

    private func chord(_ start: Int, _ end: Int) -> Span { Span(end: end, kind: .chord, message: "", start: start) }

    private func highlight(_ revision: Int, _ token: Int, _ spans: [Span]) -> SessionOutput {
        .highlightState(HighlightState(clientToken: token, spans: spans, textRevision: revision))
    }

    private func edited(_ revision: Int, _ start: Int, _ end: Int, _ replacement: String, _ undo: UndoPolicy,
                        cursor: Int, anchor: Int? = nil) -> SessionOutput {
        .textEdited(TextEdited(anchor: anchor, cursor: cursor, end: end, replacement: replacement, start: start,
                               textRevision: revision, undo: undo))
    }

    /// Apply the session's output the way the app does: the view takes the
    /// edits, which must leave the model's text.
    @discardableResult
    private func receive(_ output: SessionOutput, view: inout String) -> EditorEffects {
        let effects = take(model.receive(output))
        for edit in effects.viewEdits {
            view = UTF16Text.replacing(view, edit.range, with: edit.replacement)
        }
        XCTAssertEqual(view, model.text, "the view's text after the edits")
        return effects
    }

    private func receive(_ output: SessionOutput) {
        var view = model.text
        receive(output, view: &view)
    }

    private var spanRanges: [[Int]] { model.spans.map { [$0.start, $0.end] } }

    // -- EditorControllerTest ------------------------------------------------------------

    func testUserEditsGoToTheSessionWithIncreasingTokens() {
        type("C G")
        type("C G Am")
        XCTAssertEqual(setTexts.map(\.0), ["C G", "C G Am"])
        XCTAssertEqual(setTexts.map(\.1), [1, 2])
        XCTAssertEqual(model.identity, TextIdentity(clientToken: 2, revision: nil))
        XCTAssertTrue(model.syncCommands().isEmpty, "nothing new: nothing sent")
        // A caret move alone sends nothing.
        type("C G Am", caret: 1)
        XCTAssertEqual(setTexts.count, 2)
        XCTAssertEqual(model.selection, UTF16Range(caret: 1))
    }

    func testStaleHighlightStatesAreDroppedTheMatchingOneIsPainted() {
        type("C G")
        type("C G Am")
        receive(highlight(1, 1, [chord(0, 1)]))
        XCTAssertEqual(model.spans, [])
        receive(highlight(2, 2, [chord(0, 1), chord(2, 3), chord(4, 6)]))
        XCTAssertEqual(spanRanges, [[0, 1], [2, 3], [4, 6]])
    }

    func testPaintedSpansMoveWithTypingUntilTheNextHighlight() {
        type("C G")
        receive(highlight(1, 1, [chord(0, 1), chord(2, 3)]))
        let effects = model.viewChanged(text: "Am C G", selection: UTF16Range(caret: 3), composing: false)
        XCTAssertTrue(effects.restyle)
        XCTAssertEqual(spanRanges, [[3, 4], [5, 6]])
    }

    func testAGroupEditIsOneUndoStepAndIsntEchoedBack() {
        type("C G")
        let before = sent.count
        var view = model.text
        let effects = receive(edited(2, 0, 3, "D A", .group, cursor: 3), view: &view)
        XCTAssertEqual(model.text, "D A")
        XCTAssertEqual(effects.selection, UTF16Range(caret: 3))
        // The view reporting the new text (as UIKit may) sends nothing.
        take(model.viewChanged(text: view, selection: UTF16Range(caret: 3), composing: false))
        XCTAssertEqual(sent.count, before)
        XCTAssertEqual(model.identity, TextIdentity(clientToken: 0, revision: 2))
        // Undo restores the user's text, and sends it as a user edit.
        let undone = take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G")
        XCTAssertEqual(undone.viewEdits, [ViewEdit(range: UTF16Range(0, 3), replacement: "C G")])
        XCTAssertEqual(setTexts.last?.0, "C G")
    }

    func testAResetEditClearsTheUndoHistory() {
        type("C G")
        XCTAssertEqual(model.documentsOpened, 0)
        receive(edited(5, 0, 3, "Em", .reset, cursor: 2))
        XCTAssertEqual(model.text, "Em")
        XCTAssertFalse(model.canUndo)
        // Another document starts at its start, as on the Qt desktop (the
        // session's cursor after the text took Transpose to the end, S0 issue 14).
        XCTAssertEqual(model.selection, UTF16Range(caret: 0))
        // A document was opened (the view starts it unscrolled); other edits don't count.
        XCTAssertEqual(model.documentsOpened, 1)
        receive(edited(6, 0, 2, "G", .plain, cursor: 3))
        receive(edited(7, 0, 1, "A", .group, cursor: 4))
        XCTAssertEqual(model.documentsOpened, 1)
    }

    func testARewriteOfTheWholeSongAndItsUndoKeepTheScroll() {
        let song = "{key: G}\nG D Em C\nla la\nG D\n"
        receive(edited(1, 0, 0, song, .reset, cursor: song.unicodeScalars.count))
        type(song, caret: 9)  // the caret on the chord line, the view wherever the user scrolled
        // Transpose: the session rewrites the whole text, the caret kept on its line.
        let transposed = "{key: A}\nA E F#m D\nla la\nA E\n"
        let edit = take(model.receive(edited(2, 0, song.unicodeScalars.count, transposed, .group, cursor: 9)))
        XCTAssertTrue(edit.keepScroll, "the view stays where it was")
        XCTAssertEqual(model.selection, UTF16Range(caret: 9))
        let undone = take(model.perform(.undo))
        XCTAssertEqual(model.text, song)
        XCTAssertTrue(undone.keepScroll, "so does its Undo")
        XCTAssertTrue(take(model.perform(.redo)).keepScroll)
        // An edit of part of the song (an insert at the caret) shows the caret as before.
        let insert = take(model.receive(edited(3, 9, 9, "{capo: 2} ", .group, cursor: 19)))
        XCTAssertFalse(insert.keepScroll)
        XCTAssertFalse(take(model.perform(.undo)).keepScroll)
    }

    func testAPlainInsertPutsTheCursorAfterIt() {
        type("C G")
        receive(edited(2, 2, 2, "Am ", .plain, cursor: 5))
        XCTAssertEqual(model.text, "C Am G")
        XCTAssertEqual(model.selection, UTF16Range(caret: 5))
        XCTAssertTrue(model.canUndo)
    }

    func testAnEditWithAnAnchorSelects() {
        receive(edited(1, 0, 0, "C G\nAm F\n", .reset, cursor: 9))
        receive(edited(2, 0, 8, "// C G\n// Am F", .group, cursor: 14, anchor: 0))
        XCTAssertEqual(model.selection, UTF16Range(0, 14))
        XCTAssertEqual(model.selectionCodePoints.anchor, 0)
        XCTAssertEqual(model.selectionCodePoints.cursor, 14)
    }

    func testHighlightForASessionEditIsTakenByRevisionEvenIfItArrivesFirst() {
        type("C G")
        receive(highlight(2, 0, [chord(0, 1), chord(2, 3)]))  // delivered before the edit
        XCTAssertEqual(model.spans, [])
        receive(edited(2, 0, 3, "D A", .group, cursor: 3))
        XCTAssertEqual(spanRanges, [[0, 1], [2, 3]])
        // Older session revisions don't match.
        receive(highlight(1, 0, []))
        XCTAssertEqual(model.spans.count, 2)
    }

    func testTapsAndTheCursorAreSentAsCodePoints() {
        type("😀 C G")  // an emoji is two UTF-16 units, one code point
        let tap = model.tap(at: 3)
        XCTAssertEqual(tap.map(\.name), ["tap_chord_at"])
        XCTAssertEqual(try tap[0].argsJSON(), #"{"offset":2,"rolled":false}"#)
        type("😀 C G", caret: 5)
        XCTAssertEqual(model.cursorCodePoint, 4)
    }

    func testThePlayingChordIsConvertedToUTF16AndClearedWhenIdle() {
        type("😀 C G")
        let playing = PlaybackState(bar: 1, beat: 1, chordIndex: 1, key: nil, playheadOffset: 4,
                                    playingSpan: chord(4, 5), sections: [], status: .playing, tempoClamped: nil,
                                    timeSignature: [4, 4], totalBars: 2)
        let effects = model.receive(.playbackState(playing))
        XCTAssertEqual(model.playing, PlayingChord(start: 5, end: 6, chordIndex: 1, bar: 1))
        XCTAssertTrue(effects.playingMoved)
        var idle = playing
        idle.playingSpan = nil
        idle.status = .idle
        _ = model.receive(.playbackState(idle))
        XCTAssertNil(model.playing)
    }

    // -- EditorWiringTest ----------------------------------------------------------------

    func testSessionOutputReachesTheEditorAndUserEditsReachTheSession() {
        var view = ""
        let opened = receive(edited(1, 0, 0, "C G", .reset, cursor: 3), view: &view)
        XCTAssertTrue(opened.documentOpened)
        receive(highlight(1, 0, [chord(0, 1), chord(2, 3)]), view: &view)
        XCTAssertEqual(view, "C G")
        XCTAssertEqual(model.spans.count, 2)
        XCTAssertEqual(sent.count, 0, "the session's edit isn't echoed back")
        type("C G Am")
        XCTAssertEqual(sent.map(\.name), ["set_text"])
    }

    // -- the undo history ----------------------------------------------------------------

    func testTypingIsOneUndoStepPerRunAndALineBreakStartsAnother() {
        type(at: 0, "C")
        type(at: 1, " ")
        type(at: 2, "G")
        type(at: 3, "\n")
        type(at: 4, "A")
        type(at: 5, "m")
        XCTAssertEqual(model.text, "C G\nAm")
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G\n")
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G")
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "")
        XCTAssertFalse(model.canUndo)
        take(model.perform(.redo))
        XCTAssertEqual(model.text, "C G")
        XCTAssertEqual(model.selection, UTF16Range(caret: 3))
        // Every undo and redo told the session.
        XCTAssertEqual(setTexts.suffix(4).map(\.0), ["C G\n", "C G", "", "C G"])
    }

    func testMovingTheCaretEndsATypingRun() {
        type(at: 0, "C G")
        type("C G", caret: 0)
        type(at: 0, "Am ")
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G")
        XCTAssertEqual(model.selection, UTF16Range(caret: 0), "the selection before the step")
    }

    func testBackspacesMergeAndANewEditClearsRedo() {
        type("C G Am")
        type("C G A", caret: 5)
        type("C G ", caret: 4)
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G Am")
        XCTAssertTrue(model.canRedo)
        type(at: 6, "7")
        XCTAssertFalse(model.canRedo)
    }

    func testUndoneTextIsHighlightedUnderItsOwnToken() {
        type("C G")
        type("C G\nAm")
        take(model.perform(.undo))
        XCTAssertEqual(model.text, "C G")
        let token = model.identity.clientToken
        XCTAssertEqual(setTexts.last?.1, token)
        receive(highlight(9, token, [chord(0, 1), chord(2, 3)]))
        XCTAssertEqual(spanRanges, [[0, 1], [2, 3]])
    }

    func testUndoAndRedoDoNothingWhileReadOnlyOrEmpty() {
        XCTAssertTrue(model.perform(.undo).viewEdits.isEmpty)
        type("C G")
        receive(.editorState(EditorState(fontFamily: "TkFixedFont", fontSize: 11, notation: "american",
                                         readOnly: true, wordWrap: false)))
        XCTAssertFalse(model.canUndo)
        XCTAssertTrue(model.perform(.undo).viewEdits.isEmpty)
        XCTAssertEqual(model.willReplace(UTF16Range(caret: 0), with: "x"), .refuse)
    }

    // -- composition (marked text) -------------------------------------------------------

    func testSessionEditsWaitWhileAnInputMethodComposes() {
        receive(edited(1, 0, 0, "C G", .reset, cursor: 3))
        take(model.viewChanged(text: "C Gか", selection: UTF16Range(caret: 4), composing: true))
        XCTAssertTrue(model.composing)
        XCTAssertFalse(model.canUndo)
        let waiting = model.receive(edited(2, 0, 0, "{bpm: 90}\n", .plain, cursor: 10))
        XCTAssertTrue(waiting.viewEdits.isEmpty, "not while composing")
        XCTAssertEqual(model.text, "C Gか")
        // The composition is committed: the waiting edit lands, and the word is one undo step.
        let done = take(model.viewChanged(text: "C G蚊", selection: UTF16Range(caret: 4), composing: false))
        XCTAssertFalse(model.composing)
        XCTAssertEqual(done.viewEdits, [ViewEdit(range: UTF16Range(caret: 0), replacement: "{bpm: 90}\n")])
        XCTAssertEqual(model.text, "{bpm: 90}\nC G蚊")
        take(model.perform(.undo))  // the session's insert
        take(model.perform(.undo))  // the composed word
        XCTAssertEqual(model.text, "C G")
    }

    // -- input and actions ---------------------------------------------------------------

    func testPastedTextIsNormalized() {
        XCTAssertEqual(model.willReplace(UTF16Range(caret: 0), with: "C\u{00A0}G\r\n"), .replace("C G\n"))
        XCTAssertEqual(model.willReplace(UTF16Range(caret: 0), with: "C G\n"), .allow)
    }

    func testConvertGoesToTheOtherNotationAtTheCaret() {
        receive(.editorState(EditorState(fontFamily: "", fontSize: 11, notation: "american", readOnly: false,
                                         wordWrap: false)))
        type("😀 C G", caret: 4)
        let effects = model.perform(.convertNotation)
        XCTAssertEqual(effects.commandNames, ["convert_notation"])
        XCTAssertEqual(try effects.commands[0].argsJSON(), #"{"cursor":3,"target":"european"}"#)
        XCTAssertEqual(model.perform(.setNotation("american")).commandNames, [], "already American")
        XCTAssertEqual(model.perform(.setNotation("european")).commandNames, ["set_notation"])
    }

    func testLineCommandsSendTheSelectionInCodePoints() {
        type("😀\nC G\nAm", caret: 0)
        take(model.viewChanged(text: model.text, selection: UTF16Range(3, 9), composing: false))
        let effects = model.perform(.toggleComment)
        XCTAssertEqual(effects.commandNames, ["toggle_comment"])
        XCTAssertEqual(try effects.commands[0].argsJSON(), #"{"anchor":2,"cursor":8}"#)
        XCTAssertEqual(try model.perform(.moveLinesDown).commands[0].argsJSON(),
                       #"{"anchor":2,"cursor":8,"offset":1}"#)
        XCTAssertEqual(model.perform(.duplicateLines).commandNames, ["duplicate_lines"])
        XCTAssertEqual(model.perform(.deleteLines).commandNames, ["delete_lines"])
        XCTAssertEqual(model.perform(.fontBigger).commandNames, ["step_font_size"])
        XCTAssertEqual(model.perform(.fontReset).commandNames, ["reset_font_size"])
    }

    func testTheFontAndWrapComeFromTheEditorState() {
        XCTAssertEqual(model.fontPoints, 11)
        XCTAssertEqual(model.fontKind, .monospace)
        XCTAssertFalse(model.wordWrap)
        let effects = model.receive(.editorState(EditorState(fontFamily: "Georgia", fontSize: 14,
                                                             notation: "european", readOnly: false,
                                                             wordWrap: true)))
        XCTAssertTrue(effects.restyle)
        XCTAssertEqual(model.fontPoints, 14)
        XCTAssertEqual(model.fontKind, .serif)
        XCTAssertEqual(model.notation, "european")
        XCTAssertTrue(model.wordWrap)
    }

    func testEveryFixtureFoldsIntoTheEditorWithTheSnapshotsText() throws {
        let fixtures = try Fixture.all(in: TestPython.repo.appendingPathComponent("ios/Fixtures"))
        XCTAssertFalse(fixtures.isEmpty)
        for fixture in fixtures {
            let editor = try fixture.editorModel()
            let snapshot = try fixture.snapshot()
            XCTAssertEqual(editor.text, snapshot.text, fixture.scene)
            if snapshot.document != nil, !snapshot.text.isEmpty {
                XCTAssertFalse(editor.spans.isEmpty, "\(fixture.scene): no highlight painted")
            }
        }
    }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `ToolFormsTest` and `DirectiveVerdictTest`, case for case (the
/// commands through the editor's model instead of `ToolActions`), and
/// `ScreenLayoutTest`'s ribbon edges.
final class ToolsTests: XCTestCase {
    // MARK: - ToolFormsTest

    func testNoSelectionIsTheWholeSong() {
        XCTAssertNil(selectionOf("C G Am F", 3, 3))
        XCTAssertNil(selectionOf("", 0, 0))
    }

    func testASelectionMapsToCodePointsEitherDirection() {
        XCTAssertEqual(selectionOf("C G Am F", 2, 6), Selection(start: 2, end: 6))
        XCTAssertEqual(selectionOf("C G Am F", 6, 2), Selection(start: 2, end: 6))
        // An emoji is two UTF-16 units but one code point.
        let text = "🎸 C G Am"
        XCTAssertEqual(selectionOf(text, 3, 6), Selection(start: 2, end: 5))
        XCTAssertEqual(selectionOf(text, 0, 2), Selection(start: 0, end: 1))
        // Both ends inside the same pair select nothing.
        XCTAssertNil(selectionOf(text, 0, 1))
    }

    func testTransposeStepsStayWithinMinus11AndPlus11() {
        var form = TransposeForm()
        for _ in 0..<15 { form = form.up() }
        XCTAssertEqual(form.semitones, 11)
        XCTAssertFalse(form.canUp)
        XCTAssertEqual(form.display, "+11")
        for _ in 0..<30 { form = form.down() }
        XCTAssertEqual(form.semitones, -11)
        XCTAssertFalse(form.canDown)
        XCTAssertEqual(form.display, "-11")
        XCTAssertEqual(TransposeForm().display, "0")
    }

    func testEachDirectiveKindAnswersWithTheFieldsTheSessionTakes() {
        let keys = ["C", "G", "D"]
        var bpm = DirectiveForm.initial(.bpm, keys: keys)
        bpm.bpm = "+20"
        XCTAssertEqual(bpm.answer(), ["value": "+20"])
        var time = DirectiveForm.initial(.time, keys: keys)
        XCTAssertEqual(time.answer(), ["beats": "4", "unit": "4"])
        time.beats = 3
        time.unit = 8
        XCTAssertEqual(time.answer(), ["beats": "3", "unit": "8"])
        XCTAssertEqual(DirectiveForm.initial(.key, keys: keys).answer(), ["key": "C"])
        var label = DirectiveForm.initial(.label, keys: keys)
        label.label = "verse"
        XCTAssertEqual(label.answer(), ["label": "verse"])
        XCTAssertEqual(DirectiveForm.initial(.loop, keys: keys).answer(), ["label": "@start", "count": "2"])
        var capo = DirectiveForm.initial(.capo, keys: keys)
        capo.capo = " 3 "
        XCTAssertEqual(capo.answer(), ["capo": "3"])
        for kind in DirectiveKind.allCases {
            XCTAssertEqual(Set(DirectiveForm.initial(kind, keys: keys).answer().keys), Set(kind.fields), "\(kind)")
        }
    }

    func testValuesGoAsTypedPythonChecksThem() {
        XCTAssertEqual(DirectiveForm(kind: .bpm, bpm: " abc ").answer(), ["value": " abc "])
    }

    func testLoopCountStaysWithin2And100() {
        var form = DirectiveForm(kind: .loop)
        for _ in 0..<5 { form = form.fewerRepeats() }
        XCTAssertEqual(form.count, 2)
        for _ in 0..<200 { form = form.moreRepeats() }
        XCTAssertEqual(form.count, 100)
    }

    func testDirectiveKindsByWireName() {
        XCTAssertEqual(DirectiveKind.of("time"), .time)
        XCTAssertEqual(DirectiveKind.of("capo"), .capo)
        XCTAssertNil(DirectiveKind.of("chord"))
    }

    func testLoopTargetsAreTheStartThenTheLabels() {
        var request = InsertDirectiveRequest(existingLabels: ["chorus", "verse"], keyOptions: [], kind: "loop",
                                             notation: "american", requestId: 1)
        XCTAssertEqual(loopChoices(request), ["@start", "chorus", "verse"])
        request.existingLabels = []
        XCTAssertEqual(loopChoices(request), ["@start"])
        request.existingLabels = ["@start", "verse", "verse"]
        XCTAssertEqual(loopChoices(request), ["@start", "verse"])
    }

    func testKeysComeFromTheRequestsNotation() {
        let am = ["C", "D"]
        let eu = ["Do", "Re"]
        XCTAssertEqual(keyChoices(notation: "american", american: am, european: eu, toolbar: ["X"]), am)
        XCTAssertEqual(keyChoices(notation: "european", american: am, european: eu, toolbar: ["X"]), eu)
        XCTAssertEqual(keyChoices(notation: "european", american: nil, european: nil, toolbar: ["X"]), ["X"])
        XCTAssertEqual(keyChoices(notation: "american", american: nil, european: nil, toolbar: nil), [])
        // The request's own list (majors and minors with a signature) comes first.
        let withKeys = InsertDirectiveRequest(existingLabels: [], keyOptions: ["C", "Am", "Cb"], kind: "key",
                                              notation: "american", requestId: 1)
        XCTAssertEqual(keyChoices(withKeys, american: am, european: eu, toolbar: ["X"]), ["C", "Am", "Cb"])
        let without = InsertDirectiveRequest(existingLabels: [], keyOptions: [], kind: "key", notation: "american",
                                             requestId: 1)
        XCTAssertEqual(keyChoices(without, american: am, european: eu, toolbar: ["X"]), am)
    }

    func testSuggestCapoStartsOnTheRecommendedRowAndAppliesOnlyWhenItCan() {
        let rows = [
            CapoRow(capo: 2, current: false, ease: "Easier", label: "Capo 2 · E A B C#m · Easier",
                    recommended: true, shapes: "E A B C#m"),
            CapoRow(capo: 0, current: true, ease: "No capo", label: "No capo · F# B C# D#m", recommended: false,
                    shapes: "F# B C# D#m"),
        ]
        let voicings = [MenuItem(label: "Standard", value: "g:std")]
        let ready = CapoAdviceState(active: true, message: "", playing: false, rows: rows, scope: "",
                                    status: "ready", voicing: "g:std", voicings: voicings)
        XCTAssertEqual(capoChoice(ready, picked: nil), 2, "the recommended one, preselected")
        XCTAssertEqual(capoChoice(ready, picked: 0), 0)
        XCTAssertEqual(capoChoice(ready, picked: 5), 2, "not a row (any more): back to the first")
        XCTAssertTrue(capoCanApply(ready, picked: 0))
        var playing = ready
        playing.playing = true
        XCTAssertFalse(capoCanApply(playing, picked: 0))
        var computing = ready
        computing.status = "computing"
        computing.rows = []
        XCTAssertTrue(computing.computing)
        XCTAssertNil(capoChoice(computing, picked: 2))
        XCTAssertFalse(capoCanApply(computing, picked: 2))
        var empty = ready
        empty.rows = []
        empty.message = "No chords in this range"
        XCTAssertFalse(capoCanApply(empty, picked: nil))
        XCTAssertEqual(ready.voicingLabel, "Standard")
        XCTAssertEqual(rows.map(\.headline), ["Capo 2", "No capo"])
        XCTAssertEqual(rows.map(\.tags), ["Recommended", "Current"])
    }

    // MARK: - The commands the tools send

    private func editor(_ text: String, selection: UTF16Range) -> EditorModel {
        var model = EditorModel()
        _ = model.viewChanged(text: text, selection: selection, composing: false)
        return model
    }

    func testTransposeSendsTheSelectionInCodePointsOrNull() throws {
        // The typing went to the session already: only the transpose, with the
        // cursor, so the session keeps it on its line and column.
        var model = editor("C G Am F", selection: UTF16Range(4, 4))
        XCTAssertNil(model.toolSelection)
        try assertCommands(model.transposeCommands(2, selection: model.toolSelection),
                           [("transpose", #"{"semitones": 2, "selection": null, "cursor": 4}"#)])
        model = editor("🎸 C G Am", selection: UTF16Range(3, 6))
        try assertCommands(model.transposeCommands(-1, selection: model.toolSelection),
                           [("transpose", #"{"semitones": -1, "selection": [2, 5], "cursor": 5}"#)])
    }

    func testInsertCapoAndTheIdentifiersInsert() throws {
        var model = editor("C G Am F", selection: UTF16Range(4, 4))
        _ = model.syncCommands()
        try assertCommands(model.insertDirectiveCommands(.label),
                           [("request_insert_directive", #"{"kind": "label", "at": 4}"#)])
        model = editor("C G Am F", selection: UTF16Range(2, 6))
        _ = model.syncCommands()
        try assertCommands(model.suggestCapoCommands(), [("capo_advice_open", #"{"selection": [2, 6]}"#)])
        model = editor("C G Am F", selection: UTF16Range(4, 4))
        _ = model.syncCommands()
        try assertCommands(model.insertChordCommands("Am7"), [("insert_chord", #"{"at": 4, "chord": "Am7"}"#)])
    }

    // MARK: - DirectiveVerdictTest

    private let answer = ["value": "999"]

    private func check(fields: [String: String]? = nil, errors: [String: String] = [:], formError: String = "",
                       requestId: Int = 3, kind: String = "bpm") -> DirectiveCheck {
        func object(_ map: [String: String]) -> JSONValue { .object(map.mapValues { .string($0) }) }
        return DirectiveCheck(errors: object(errors), fields: object(fields ?? answer), formError: formError,
                              kind: kind, requestId: requestId)
    }

    func testNoReplyYetDisablesInsertAndShowsNothing() {
        XCTAssertEqual(DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer, check: nil, showErrors: true),
                       DirectiveVerdict(canInsert: false, messages: []))
    }

    func testACleanReplyForTheCurrentFieldsEnablesInsert() {
        XCTAssertTrue(DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer, check: check(),
                                          showErrors: true).canInsert)
    }

    func testAnErrorKeepsInsertDisabledAndIsShownOnceTheUserChangedSomething() {
        let bad = check(errors: ["value": "BPM must be between 20 and 400."])
        let shown = DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer, check: bad, showErrors: true)
        XCTAssertFalse(shown.canInsert)
        XCTAssertEqual(shown.messages, ["BPM must be between 20 and 400."])
        XCTAssertEqual(DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer, check: bad,
                                           showErrors: false).messages, [])
    }

    func testAFormLevelErrorIsShownToo() {
        let verdict = DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer, check: check(formError: "Nope"),
                                          showErrors: true)
        XCTAssertFalse(verdict.canInsert)
        XCTAssertEqual(verdict.messages, ["Nope"])
    }

    func testALateReplyForOlderFieldsOrAnotherRequestIsIgnored() {
        XCTAssertFalse(DirectiveVerdict.of(kind: "bpm", requestId: 3, answer: answer,
                                           check: check(fields: ["value": "99"]), showErrors: true).canInsert)
        XCTAssertFalse(DirectiveVerdict.of(kind: "bpm", requestId: 4, answer: answer, check: check(),
                                           showErrors: true).canInsert)
        XCTAssertFalse(DirectiveVerdict.of(kind: "label", requestId: 3, answer: answer, check: check(),
                                           showErrors: true).canInsert)
    }

    func testMessagesFollowTheFieldsOrder() {
        // A JSON object has no order in Swift: the loop's label, then its count, then the form's.
        let fields = ["label": "nope", "count": "1"]
        let bad = check(fields: fields, errors: ["count": "Count must be 2 to 100.", "label": "No label nope."],
                        formError: "Fix the loop.", kind: "loop")
        XCTAssertEqual(DirectiveVerdict.of(kind: "loop", requestId: 3, answer: fields, check: bad,
                                           showErrors: true).messages,
                       ["No label nope.", "Count must be 2 to 100.", "Fix the loop."])
    }

    // MARK: - ScreenLayoutTest: the ribbon's edges

    func testRibbonEdges() {
        XCTAssertEqual(RibbonEdges.of(0, 0), RibbonEdges(fadeLeft: false, more: false))
        XCTAssertEqual(RibbonEdges.of(0, 200), RibbonEdges(fadeLeft: false, more: true))
        XCTAssertEqual(RibbonEdges.of(100, 200), RibbonEdges(fadeLeft: true, more: true))
        XCTAssertEqual(RibbonEdges.of(199, 200), RibbonEdges(fadeLeft: true, more: false))
    }
}

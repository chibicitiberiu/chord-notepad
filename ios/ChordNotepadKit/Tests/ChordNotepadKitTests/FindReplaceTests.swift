import Foundation
import XCTest

@testable import ChordNotepadKit

/// Find and Replace: the core's `test_text_ops.py` find cases, the Qt
/// desktop's `test_qt_find_bar.py` as behaviour of the editor's model, and
/// the matching checked against the core's own `text_ops.find_all` on random
/// texts (the session's `replace_match` refuses a span Python doesn't match).
final class FindReplaceTests: XCTestCase {
    // -- text_ops: find_all and next_match ---------------------------------------------

    private func find(_ text: String, _ query: String, matchCase: Bool = false, wholeWord: Bool = false) -> [[Int]] {
        TextFind.findAll(text, query: query, matchCase: matchCase, wholeWord: wholeWord).map { [$0.start, $0.end] }
    }

    func testFindIgnoresCaseUnlessAsked() {
        XCTAssertEqual(find("Am C am AM", "am"), [[0, 2], [5, 7], [8, 10]])
        XCTAssertEqual(find("Am C am AM", "am", matchCase: true), [[5, 7]])
    }

    func testFindWholeWordIsntInsideALongerWord() {
        XCTAssertEqual(find("Am Am7 Am, xAm", "Am", wholeWord: true), [[0, 2], [7, 9]])
        XCTAssertEqual(find("{bpm: 90} ({bpm: 90}) x{bpm", "{bpm", wholeWord: true), [[0, 4], [11, 15]])
        XCTAssertEqual(find("F# F#m F#", "F#", matchCase: true, wholeWord: true), [[0, 2], [7, 9]])
    }

    func testFindTakesTheQueryLiterallyAndDoesntOverlap() {
        XCTAssertEqual(find("a.b axb", "a.b"), [[0, 3]])
        XCTAssertEqual(find("aaaa", "aa"), [[0, 2], [2, 4]])
        XCTAssertEqual(find("abc", ""), [])
        XCTAssertEqual(find("", "a"), [])
    }

    func testFindIsUnicodeSafeInCodePoints() {
        XCTAssertEqual(find("Ünd ünd 😀 ünd", "ÜND"), [[0, 3], [4, 7], [10, 13]])
        // Python's re: ſ matches s, ς matches σ, the Kelvin sign k; İ is "i" folded simply.
        XCTAssertEqual(find("ſ S s", "s"), [[0, 1], [2, 3], [4, 5]])
        XCTAssertEqual(find("ΣΑΣ σας", "σας"), [[0, 3], [4, 7]])
        XCTAssertEqual(find("\u{212A}ey key", "KEY"), [[0, 3], [4, 7]])
        XCTAssertEqual(find("ß ẞ ss", "ß"), [[0, 1], [2, 3]])
    }

    func testNextMatchFromAPositionAndWrapping() {
        let matches = [FindSpan(2, 4), FindSpan(8, 10), FindSpan(15, 17)]
        func next(_ position: Int, _ backward: Bool = false) -> [Int]? {
            TextFind.nextMatch(matches, position: position, backward: backward).map { [$0.index, $0.wrapped ? 1 : 0] }
        }
        XCTAssertEqual(next(0), [0, 0])
        XCTAssertEqual(next(2), [0, 0])
        XCTAssertEqual(next(3), [1, 0])
        XCTAssertEqual(next(16), [0, 1])
        XCTAssertEqual(next(10, true), [1, 0])
        XCTAssertEqual(next(9, true), [0, 0])
        XCTAssertEqual(next(3, true), [2, 1])
        XCTAssertNil(TextFind.nextMatch([], position: 3))
    }

    func testTheCountText() {
        XCTAssertEqual(TextFind.countText(query: "", count: 0, current: 0), "")
        XCTAssertEqual(TextFind.countText(query: "x", count: 0, current: 0), "No matches")
        XCTAssertEqual(TextFind.countText(query: "x", count: 7, current: 3), "3 of 7")
        XCTAssertEqual(TextFind.countText(query: "x", count: 7, current: 0), "7 matches")
        XCTAssertEqual(TextFind.countText(query: "x", count: 1, current: 0), "1 match")
    }

    // -- the same answers as the core's text_ops.find_all ---------------------------------

    /// Random texts and queries over characters `re` treats specially (cases
    /// that fold together, uncased marks, digits and `_` as word characters,
    /// astral characters), checked against the core.
    func testMatchingEqualsTheCoresFindAllOnRandomTexts() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let alphabet = Array("aAb #{}F♯ÜüßẞİiıIſsSσςΣKk\u{212A}é\u{0301}e😀𝔸\n_1٣ǅǆ")
        var rng = SeededRandom(seed: 7)
        var cases: [(String, String, Bool, Bool)] = []
        for _ in 0..<600 {
            let text = String((0..<rng.next(below: 31)).map { _ in alphabet[rng.next(below: alphabet.count)] })
            let query = String((0..<(1 + rng.next(below: 3))).map { _ in alphabet[rng.next(below: alphabet.count)] })
            for matchCase in [false, true] {
                for wholeWord in [false, true] { cases.append((text, query, matchCase, wholeWord)) }
            }
        }
        // A real song with the queries a person types.
        let song = try String(contentsOf: TestPython.repo.appendingPathComponent("examples/01_quick_start.txt"),
                              encoding: .utf8)
        for query in ["am", "Am", "G", "{bpm", "the", "//", "C/E", "\n", " "] {
            for matchCase in [false, true] {
                for wholeWord in [false, true] { cases.append((song, query, matchCase, wholeWord)) }
            }
        }
        let json = String(decoding: try JSONSerialization.data(withJSONObject: cases.map { [$0.0, $0.1, $0.2, $0.3] }),
                          as: UTF8.self)
        let reply = try await runtime.call("cn_kit_testmod", "find_all_cases", [json])
        let expected = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data((reply ?? "").utf8)) as? [[[Int]]])
        XCTAssertEqual(expected.count, cases.count)
        var failures = 0
        for (c, python) in zip(cases, expected) {
            let swift = find(c.0, c.1, matchCase: c.2, wholeWord: c.3)
            if swift != python {
                failures += 1
                if failures <= 10 {
                    XCTFail("find_all(\(c.0.debugDescription), \(c.1.debugDescription), case \(c.2), word \(c.3)): "
                            + "Python \(python), Swift \(swift)")
                }
            }
        }
        XCTAssertEqual(failures, 0)
    }

    /// The tables against the running interpreter's `re`: every code point
    /// of the Basic Multilingual Plane, each table boundary and a stride over
    /// the rest.
    func testTheTablesAreTheRunningPythonsRe() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        var points = Set<UInt32>((0..<0xD800).map(UInt32.init) + (0xE000..<0x10000).map(UInt32.init))
        for value in pythonCasedRanges + pythonWordRanges + pythonLowerPairs {
            for p in [value &- 1, value, value + 1] where p <= 0x10FFFF && !(0xD800...0xDFFF).contains(p) {
                points.insert(p)
            }
        }
        for p in stride(from: UInt32(0x10000), through: 0x10FFFF, by: 97) { points.insert(p) }
        let sorted = points.sorted()
        let json = String(decoding: try JSONSerialization.data(withJSONObject: sorted.map(Int.init)), as: UTF8.self)
        let reply = try await runtime.call("cn_kit_testmod", "find_char_facts", [json])
        let facts = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data((reply ?? "").utf8)) as? [[Any]])
        XCTAssertEqual(facts.count, sorted.count)
        var wrong: [String] = []
        for (p, fact) in zip(sorted, facts) {
            let lower = UInt32(fact[0] as! Int)
            let cased = fact[1] as! Bool
            let word = fact[2] as! Bool
            if TextFind.lower(p) != lower || TextFind.isCased(p) != cased || TextFind.isWord(p) != word {
                wrong.append(String(format: "U+%04X", p))
            }
        }
        XCTAssertEqual(wrong.prefix(20), [], "\(wrong.count) code points disagree")
    }

    // -- the find bar (the desktop's test_qt_find_bar.py) -----------------------------

    private static let text = "Am C Am G\nla am la\nAm7 F\n"
    private static let ams = [UTF16Range(0, 2), UTF16Range(5, 7), UTF16Range(13, 15), UTF16Range(19, 21)]

    private var model = EditorModel()
    private var commands: [BridgeCommand] = []

    override func setUp() {
        model = EditorModel()
        commands = []
    }

    private func song(_ text: String = FindReplaceTests.text, caret: Int = 0) {
        commands += model.viewChanged(text: text, selection: UTF16Range(caret: caret), composing: false).commands
    }

    private func caret(_ at: Int) {
        _ = model.viewChanged(text: model.text, selection: UTF16Range(caret: at), composing: false)
    }

    @discardableResult
    private func act(_ action: FindAction, canReplace: Bool = true) -> EditorEffects {
        let effects = model.find(action, canReplace: canReplace)
        commands += effects.commands
        return effects
    }

    private var selection: UTF16Range { model.selection }

    private func args(_ command: BridgeCommand) throws -> [String: Any] {
        try jsonObject(try command.argsJSON())
    }

    func testOpeningAndTypingFindsAsYouTypeFromTheCaret() {
        song(caret: 3)
        act(.open(replace: false))
        XCTAssertTrue(model.find.open)
        act(.query("a"))
        act(.query("am"))
        XCTAssertEqual(selection, UTF16Range(5, 7), "the first match after the caret")
        XCTAssertEqual(model.find.countText, "2 of 4")
        XCTAssertEqual(model.findPaint, FindPaint(matches: Self.ams, current: UTF16Range(5, 7)))
    }

    func testNextAndPreviousGoThroughTheMatchesAndWrapWithANotice() {
        song()
        act(.open(replace: false))
        act(.query("am"))
        XCTAssertEqual(selection, UTF16Range(0, 2))
        act(.next)
        XCTAssertEqual(selection, UTF16Range(5, 7))
        act(.next)
        XCTAssertEqual(selection, UTF16Range(13, 15))
        act(.next)
        XCTAssertEqual(selection, UTF16Range(19, 21))
        XCTAssertNil(model.find.notice)
        let wrapped = act(.next)
        XCTAssertEqual(selection, UTF16Range(0, 2))
        XCTAssertEqual(model.find.notice, "Continued from the top")
        XCTAssertTrue(wrapped.findNotice && wrapped.findMoved)
        act(.previous)
        XCTAssertEqual(selection, UTF16Range(19, 21))
        XCTAssertEqual(model.find.notice, "Continued from the bottom")
        act(.previous)
        XCTAssertEqual(selection, UTF16Range(13, 15))
        act(.clearNotice)
        XCTAssertNil(model.find.notice)
    }

    func testMatchCaseAndWholeWord() {
        song()
        act(.open(replace: false))
        act(.query("am"))
        act(.matchCase(true))
        XCTAssertEqual(model.find.matches.count, 1)
        XCTAssertEqual(selection, UTF16Range(13, 15))
        act(.matchCase(false))
        act(.wholeWord(true))
        XCTAssertEqual(model.find.matches.count, 3)
        XCTAssertFalse(model.findPaint?.matches.contains(UTF16Range(19, 21)) ?? true)
    }

    func testNoMatchesSaysSoAndPutsTheCaretBack() {
        song(caret: 3)
        act(.open(replace: false))
        act(.query("zz"))
        XCTAssertEqual(model.find.countText, "No matches")
        XCTAssertTrue(model.find.noMatch)
        XCTAssertFalse(model.find.hasMatches)
        XCTAssertEqual(selection, UTF16Range(caret: 3))
    }

    func testClosingRemovesTheTintsAndCommandGFindsTheLastQueryAgain() {
        song()
        act(.open(replace: false))
        act(.query("am"))
        act(.close)
        XCTAssertFalse(model.find.open)
        XCTAssertNil(model.findPaint)
        XCTAssertEqual(model.styleRuns(.light), [])
        caret(8)
        act(.again(backward: false))
        XCTAssertEqual(selection, UTF16Range(13, 15))
        XCTAssertFalse(model.find.open, "the bar stays closed")
        act(.again(backward: true))
        XCTAssertEqual(selection, UTF16Range(5, 7))
    }

    func testCommandGWithoutAQueryOpensTheBar() {
        song()
        act(.again(backward: false))
        XCTAssertTrue(model.find.open)
    }

    func testOpeningTakesAOneLineSelectionAsTheQuery() {
        song()
        _ = model.viewChanged(text: model.text, selection: UTF16Range(5, 9), composing: false)
        act(.open(replace: false))
        XCTAssertEqual(model.find.query, "Am G")
        XCTAssertEqual(model.find.countText, "1 of 1")
        act(.close)
        _ = model.viewChanged(text: model.text, selection: UTF16Range(0, 12), composing: false)
        act(.open(replace: false))
        XCTAssertEqual(model.find.query, "Am G", "two lines aren't taken")
    }

    func testTheTintsFollowTheText() {
        song()
        act(.open(replace: false))
        act(.query("la"))
        XCTAssertEqual(model.findPaint?.matches, [UTF16Range(10, 12), UTF16Range(16, 18)])
        song("x" + Self.text, caret: 1)
        XCTAssertEqual(model.findPaint?.matches, [UTF16Range(11, 13), UTF16Range(17, 19)])
        XCTAssertEqual(model.find.matches.count, 2)
    }

    func testTheTintsArePaintedUnderThePlayingChordAndTheCurrentMatchStronger() {
        let p = EditorPalette.dark
        let runs = styleRuns(spans: [PaintedSpan(0, 2, .chord)], playing: UTF16Range(5, 7), length: 10, palette: p,
                             find: FindPaint(matches: [UTF16Range(0, 2), UTF16Range(5, 7)], current: UTF16Range(0, 2)))
        XCTAssertEqual(runs, [
            StyleRun(0, 2, RunStyle(color: p.chord, underline: true, background: p.findCurrent)),
            StyleRun(5, 7, p.playingStyle),
        ])
        XCTAssertEqual(EditorPalette.light.findMatch.argb, 0xFFCD_ECD2)
        XCTAssertEqual(EditorPalette.light.findCurrent.argb, 0xFF9F_DCAA)
    }

    func testReplaceSendsTheSelectedMatchThenMovesOnOnceTheEditIsIn() throws {
        song()
        act(.open(replace: true))
        XCTAssertTrue(model.find.replacing)
        act(.query("am"))
        act(.replacement("Dm"))
        commands = []
        act(.replace)
        XCTAssertEqual(commands.map(\.name), ["replace_match"])
        let sent = try args(commands[0])
        XCTAssertEqual(sent["span"] as? [Int], [0, 2])
        XCTAssertEqual(sent["query"] as? String, "am")
        XCTAssertEqual(sent["replacement"] as? String, "Dm")
        XCTAssertEqual(sent["match_case"] as? Bool, false)
        XCTAssertEqual(sent["whole_word"] as? Bool, false)
        // The session's edit: the caret after the replacement; the bar selects the next match.
        let effects = model.receive(.textEdited(TextEdited(anchor: nil, cursor: 2, end: 2, replacement: "Dm",
                                                           start: 0, textRevision: 2, undo: .group)))
        XCTAssertEqual(model.text, "Dm C Am G\nla am la\nAm7 F\n")
        XCTAssertEqual(selection, UTF16Range(5, 7))
        XCTAssertEqual(effects.selection, UTF16Range(5, 7))
        XCTAssertEqual(model.find.countText, "1 of 3")
    }

    func testReplaceWhenTheSelectionIsntAMatchFindsFirst() {
        song()
        act(.open(replace: true))
        act(.query("am"))
        _ = model.viewChanged(text: model.text, selection: UTF16Range(3, 4), composing: false)
        commands = []
        act(.replace)
        XCTAssertEqual(commands.map(\.name), [])
        XCTAssertEqual(selection, UTF16Range(5, 7))
    }

    func testReplaceTheSessionRefusesStillMovesOn() {
        song()
        act(.open(replace: true))
        act(.query("am"))
        act(.next)
        act(.replace)
        _ = model.receive(.editRefused(EditRefused(message: "Stop playback to edit")))
        XCTAssertEqual(selection, UTF16Range(13, 15))
        XCTAssertEqual(model.text, Self.text)
    }

    func testReplaceAllSendsTheQueryWithTheCaretInCodePoints() throws {
        song("😀 am am", caret: 5)
        act(.open(replace: true))
        act(.query("am"))
        act(.replacement("Em"))
        commands = []
        act(.replaceAll)
        XCTAssertEqual(commands.map(\.name), ["replace_all"])
        let sent = try args(commands[0])
        // The typed search selected the match at code points 5..7 (UTF-16 6..8): the caret is its end.
        XCTAssertEqual(sent["cursor"] as? Int, 7)
        XCTAssertEqual(sent["query"] as? String, "am")
        XCTAssertEqual(sent["replacement"] as? String, "Em")
    }

    func testPlayModeHasNoReplaceRow() {
        song()
        act(.open(replace: true), canReplace: false)
        XCTAssertFalse(model.find.replacing)
        XCTAssertFalse(model.find.canReplace)
        act(.showReplace(true))
        XCTAssertFalse(model.find.replacing)
        act(.query("am"))
        commands = []
        act(.replace)
        act(.replaceAll)
        XCTAssertEqual(commands.map(\.name), [])
        XCTAssertEqual(MainUiState(mode: .play).findCanReplace, false)
        XCTAssertEqual(MainUiState(mode: .edit).findCanReplace, true)
    }

    func testUndoKeepsTheMatchesCurrent() {
        song()
        act(.open(replace: false))
        act(.query("la"))
        caret(0)
        song("la" + Self.text, caret: 2)
        XCTAssertEqual(model.find.matches.count, 3)
        _ = model.undo()
        XCTAssertEqual(model.text, Self.text)
        XCTAssertEqual(model.findPaint?.matches, [UTF16Range(10, 12), UTF16Range(16, 18)])
    }

    func testTheCatalogsBarShowsAQueryOverAScene() {
        song()
        let bar = FindBar.showing(model, query: "am", replacement: "Em", current: 2)
        XCTAssertTrue(bar.open && bar.replacing)
        XCTAssertEqual(bar.countText, "2 of 4")
        let play = FindBar.showing(model, query: "am", replacement: "Em", canReplace: false)
        XCTAssertFalse(play.replacing)
        XCTAssertEqual(bar.height, 1 + 8 + 44 + 48, "both rows")
        XCTAssertEqual(play.height, 1 + 8 + 44)
        XCTAssertEqual(FindBar().height, 0, "closed")
        model.showFind(bar)
        XCTAssertEqual(model.selection, UTF16Range(5, 7))
        XCTAssertEqual(model.find.countText, "2 of 4")
        XCTAssertEqual(model.findPaint?.current, UTF16Range(5, 7))
    }
}

/// A small deterministic generator (SplitMix64), so the random cases are the same on every run.
struct SeededRandom {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    mutating func next(below bound: Int) -> Int {
        bound <= 0 ? 0 : Int(next() % UInt64(bound))
    }
}

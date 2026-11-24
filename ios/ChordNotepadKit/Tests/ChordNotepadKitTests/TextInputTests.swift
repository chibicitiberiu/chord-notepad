import Foundation
import XCTest

@testable import ChordNotepadKit

/// What comes into the editor and how it wraps and scrolls: Android's
/// `PasteNormalizationTest` (the cases of tests/test_paste_normalization.py),
/// `ChordWrapTest`, `TextScrollTest` and `DirectiveHintControllerTest`.
final class TextInputTests: XCTestCase {
    // -- PasteNormalizationTest --------------------------------------------------------

    func testLineEndingsBecomeLF() {
        XCTAssertEqual(normalizeSongText("[Chorus]\r\nC  G\r\n"), "[Chorus]\nC  G\n")
        XCTAssertEqual(normalizeSongText("line one\rline two"), "line one\nline two")
        XCTAssertEqual(normalizeSongText("a\r\nb\nc\r"), "a\nb\nc\n")
    }

    func testNonBreakingSpacesBecomeSpacesZeroWidthCharactersGo() {
        XCTAssertEqual(normalizeSongText("C \u{00A0}G"), "C  G")
        XCTAssertEqual(normalizeSongText("\u{FEFF}C\u{200B}m"), "Cm")
    }

    func testPlainTextIsUnchanged() {
        let text = "{title: Song}\n[Verse]\nC G Am F\nlyrics here 😀\n"
        XCTAssertEqual(normalizeSongText(text), text)
        XCTAssertFalse(needsNormalizing(text))
        XCTAssertTrue(needsNormalizing("a\r\n"))
    }

    // -- ChordWrapTest -------------------------------------------------------------------

    private func chord(_ text: String, _ token: String, from: Int = 0) -> PaintedSpan {
        let units = Array(text.utf16)
        let needle = Array(token.utf16)
        var start = from
        while Array(units[start..<(start + needle.count)]) != needle { start += 1 }
        return PaintedSpan(start, start + needle.count, .chord)
    }

    func testASlashChordGetsAJoinPointAfterTheSlashPlainChordsNone() {
        // L7: D/F# wrapped as "D/" and "F#".
        let text = "G/B  C/E  D/F#  G/D\nword-word C"
        let spans = [chord(text, "G/B"), chord(text, "C/E"), chord(text, "D/F#"), chord(text, "G/D"),
                     chord(text, "C", from: 25)]
        XCTAssertEqual(chordJoinPoints(text, spans: spans), [2, 7, 12, 18])
        // A hyphen in the lyrics isn't a chord's: it still wraps there.
        XCTAssertEqual(chordJoinPoints("word-word", spans: []), [])
        let minus = "Bb-7 C+"
        XCTAssertEqual(chordJoinPoints(minus, spans: [chord(minus, "Bb-7"), chord(minus, "C+")]), [3])
    }

    func testTheLayoutMayBreakEverywhereButAtAJoinPoint() {
        let points = [2, 7]
        XCTAssertFalse(mayBreak(before: 2, points: points))
        XCTAssertFalse(mayBreak(before: 7, points: points))
        XCTAssertTrue(mayBreak(before: 3, points: points))
        XCTAssertTrue(mayBreak(before: 0, points: []))
    }

    func testOffsetsMovePastTheJoinersBeforeThem() {
        let text = "D/F# G/B"
        let joined = JoinedText(chordJoinPoints(text, spans: [chord(text, "D/F#"), chord(text, "G/B")]))
        let shown = joined.display(text)
        XCTAssertEqual(shown, "D/\u{2060}F# G/\u{2060}B")
        // Every character keeps its own place in the drawn text.
        let textUnits = Array(text.utf16)
        let shownUnits = Array(shown.utf16)
        for i in textUnits.indices {
            XCTAssertEqual(textUnits[i], shownUnits[joined.toDisplay(i)], "at \(i)")
        }
        XCTAssertEqual(joined.toDisplay(textUnits.count), shownUnits.count)
        // Span starts and ends: D/F# is [0, 4) → [0, 5); G/B [5, 8) → [6, 10).
        XCTAssertEqual([0, 4, 5, 8].map(joined.toDisplay), [0, 5, 6, 10])
        let none = JoinedText([])
        XCTAssertEqual(none.display(text), text)
        XCTAssertEqual(none.toDisplay(3), 3)
    }

    func testACopyAndAPasteLeaveNoJoinersInTheSong() {
        XCTAssertEqual(withoutJoiners("G/\u{2060}B C"), "G/B C")
        XCTAssertEqual(normalizeSongText("G/\u{2060}B"), "G/B")
        XCTAssertTrue(needsNormalizing("G/\u{2060}B"))
    }

    func testJoinPointsOnlyWhileTheTextWraps() {
        let text = "D/F# G/B"
        let spans = [chord(text, "D/F#"), chord(text, "G/B")]
        XCTAssertEqual(joinPoints(text, spans: spans, wordWrap: true), [2, 7])
        // Unwrapped, nothing can split a chord.
        XCTAssertEqual(joinPoints(text, spans: spans, wordWrap: false), [])
    }

    // -- TextScrollTest ------------------------------------------------------------------

    func testAChordInViewDoesntScroll() {
        XCTAssertNil(TextScroll.followChord(start: 100, end: 140, value: 0, viewport: 300, max: 1000))
        XCTAssertNil(TextScroll.followChord(start: 300, end: 340, value: 250, viewport: 300, max: 1000))
    }

    func testAChordOutOfViewLandsAThirdOfTheWayIn() {
        // Off the right edge (the next chord on a long line).
        XCTAssertEqual(TextScroll.followChord(start: 500, end: 540, value: 0, viewport: 300, max: 1000), 400)
        // Partly cut at the right edge counts as out of view.
        XCTAssertEqual(TextScroll.followChord(start: 280, end: 320, value: 0, viewport: 300, max: 1000), 180)
        // The next line's first chord, scrolled sideways: back to the start.
        XCTAssertEqual(TextScroll.followChord(start: 12, end: 30, value: 400, viewport: 300, max: 1000), 0)
        // Never past the end.
        XCTAssertEqual(TextScroll.followChord(start: 1250, end: 1290, value: 0, viewport: 300, max: 1000), 1000)
    }

    func testAnUnmeasuredViewDoesntScroll() {
        XCTAssertNil(TextScroll.followChord(start: 500, end: 540, value: 0, viewport: 0, max: 1000))
        XCTAssertNil(TextScroll.followCursor(start: 500, end: 502, value: 0, viewport: 0, max: 1000, margin: 24))
    }

    func testTheCursorInViewDoesntScroll() {
        XCTAssertNil(TextScroll.followCursor(start: 100, end: 102, value: 0, viewport: 300, max: 1000, margin: 24))
        XCTAssertNil(TextScroll.followCursor(start: 274, end: 276, value: 0, viewport: 300, max: 1000, margin: 24))
    }

    func testTypingPastTheRightEdgeScrollsJustEnough() {
        XCTAssertEqual(TextScroll.followCursor(start: 290, end: 292, value: 0, viewport: 300, max: 1000,
                                               margin: 24), 16)
        XCTAssertEqual(TextScroll.followCursor(start: 300, end: 302, value: 16, viewport: 300, max: 1000,
                                               margin: 24), 26)
    }

    func testMovingBackPastTheLeftEdgeScrollsBack() {
        XCTAssertEqual(TextScroll.followCursor(start: 100, end: 102, value: 200, viewport: 300, max: 1000,
                                               margin: 24), 76)
        XCTAssertEqual(TextScroll.followCursor(start: 12, end: 14, value: 200, viewport: 300, max: 1000,
                                               margin: 24), 0)
        XCTAssertNil(TextScroll.followCursor(start: 12, end: 14, value: 0, viewport: 300, max: 1000, margin: 24))
    }

    func testNeverScrollsPastTheEnd() {
        XCTAssertEqual(TextScroll.followCursor(start: 1290, end: 1292, value: 900, viewport: 300, max: 1000,
                                               margin: 24), 1000)
        XCTAssertNil(TextScroll.followCursor(start: 1290, end: 1292, value: 1000, viewport: 300, max: 1000,
                                             margin: 24))
    }

    // -- DirectiveHintControllerTest -----------------------------------------------------

    private let bpm = "{bpm: 120} · {bpm: +10}"

    private func hint(_ offset: Int, syntax: String? = nil, message: String = "", redundant: Bool = false,
                      start: Int = 0, end: Int = 10) -> DirectiveHint {
        DirectiveHint(end: end, keyword: "bpm", message: message, offset: offset, redundant: redundant,
                      start: start, syntax: syntax ?? bpm)
    }

    func testAnInvalidDirectivesReasonIsAnErrorARedundantOnesIsnt() {
        var state = DirectiveHintState()
        _ = state.explain(3)
        state.receive(hint(3, message: "Tempo must be 20-400"))
        XCTAssertEqual(state.explained?.card.error, true)
        XCTAssertEqual(state.explained?.card.reason, "Tempo must be 20-400")
        state.receive(hint(3, message: "Has no effect: replaced by {bpm: 90} on line 2", redundant: true))
        XCTAssertEqual(state.explained?.card.error, false)
    }

    func testAStaleReplyIsDropped() {
        var state = DirectiveHintState()
        _ = state.explain(3)
        state.receive(hint(2, message: "Tempo must be 20-400"))
        XCTAssertNil(state.explained)
    }

    func testHalfTypedKeywordsGiveOneSyntaxLinePerCandidate() {
        let card = HintCard.of(hint(2, syntax: "{label: verse}\n{loop: verse} · {loop: verse 3}"))
        XCTAssertEqual(card?.syntax, "{label:\u{00A0}verse}\n{loop:\u{00A0}verse} · {loop:\u{00A0}verse\u{00A0}3}")
    }

    func testALongPressExplainsOnlyADirectiveWithAReason() throws {
        var state = DirectiveHintState()
        let command = state.explain(0)
        XCTAssertEqual(command.name, "request_directive_hint")
        XCTAssertEqual(try command.argsJSON(), #"{"offset":0}"#)
        state.receive(hint(0, message: "Tempo must be 20-400", end: 8))
        XCTAssertEqual(state.explained, ExplainedDirective(
            card: HintCard(reason: "Tempo must be 20-400", error: true, syntax: HintCard.wrapFriendly(bpm)),
            start: 0, end: 8))
        state.dismiss()
        XCTAssertNil(state.explained)
        // A late reply after dismissing doesn't bring it back.
        state.receive(hint(0, message: "Tempo must be 20-400", end: 8))
        XCTAssertNil(state.explained)
        _ = state.explain(0)  // the same reply again: shown from the one kept
        XCTAssertEqual(state.explained?.card.reason, "Tempo must be 20-400")
        state.dismiss()
        _ = state.explain(30)
        state.receive(DirectiveHint(end: 40, keyword: "key", message: "", offset: 30, redundant: false, start: 30,
                                    syntax: "{key: G}"))
        XCTAssertNil(state.explained)
    }

    func testTheCardGoesUnderTheDirectiveOrAboveItAtTheBottomOfTheView() {
        XCTAssertEqual(DirectiveHintState.cardTop(anchorTop: 100, anchorBottom: 120, cardHeight: 60, viewTop: 0,
                                                  viewBottom: 800, gap: 6), 126)
        XCTAssertEqual(DirectiveHintState.cardTop(anchorTop: 780, anchorBottom: 800, cardHeight: 60, viewTop: 0,
                                                  viewBottom: 820, gap: 6), 714)
        // No room above either: under it, and the view scrolls.
        XCTAssertEqual(DirectiveHintState.cardTop(anchorTop: 10, anchorBottom: 30, cardHeight: 60, viewTop: 0,
                                                  viewBottom: 80, gap: 6), 36)
    }
}

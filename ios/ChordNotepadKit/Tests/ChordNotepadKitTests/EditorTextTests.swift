import Foundation
import XCTest

@testable import ChordNotepadKit

/// The editor's text arithmetic: Android's `SpanShiftTest` and `TextEditsTest`
/// (a session edit in UTF-16 against a code-point reference), case for case.
final class EditorTextTests: XCTestCase {
    private func chord(_ start: Int, _ end: Int) -> PaintedSpan { PaintedSpan(start, end, .chord) }

    // -- SpanShiftTest --------------------------------------------------------------

    func testDiffFindsTheOneChangedRange() {
        XCTAssertNil(diffTexts("C G Am", "C G Am"))
        XCTAssertEqual(diffTexts("C G", "C xG"), TextChange(start: 2, oldEnd: 2, newEnd: 3))
        XCTAssertEqual(diffTexts("C xG", "C G"), TextChange(start: 2, oldEnd: 3, newEnd: 2))
        XCTAssertEqual(diffTexts("C G", "Dm"), TextChange(start: 0, oldEnd: 3, newEnd: 2))
        XCTAssertEqual(diffTexts("C G", "C G Am"), TextChange(start: 3, oldEnd: 3, newEnd: 6))
    }

    func testDiffNeverSplitsASurrogatePair() {
        // Same high surrogate, different low ones: the change starts at the pair.
        let change = try! XCTUnwrap(diffTexts("a😀b", "a😁b"))
        XCTAssertEqual(change.start, 1)
        XCTAssertEqual(change.oldEnd, 3)
    }

    func testSpansAfterAnInsertShiftSpansBeforeStay() {
        XCTAssertEqual([chord(0, 1), chord(4, 6)].shifted(by: TextChange(start: 2, oldEnd: 2, newEnd: 4)),
                       [chord(0, 1), chord(6, 8)])
    }

    func testTypingAtASpanEdgeStaysOutsideItInsideJoinsIt() {
        let am = [chord(4, 6)]
        XCTAssertEqual(am.shifted(by: TextChange(start: 4, oldEnd: 4, newEnd: 5)), [chord(5, 7)])  // before "Am"
        XCTAssertEqual(am.shifted(by: TextChange(start: 6, oldEnd: 6, newEnd: 7)), [chord(4, 6)])  // after it
        XCTAssertEqual(am.shifted(by: TextChange(start: 5, oldEnd: 5, newEnd: 6)), [chord(4, 7)])  // A|m
    }

    func testDeletingASpansTextRemovesOrTrimsIt() {
        let am = [chord(4, 6)]
        XCTAssertEqual(am.shifted(by: TextChange(start: 3, oldEnd: 7, newEnd: 3)), [])
        XCTAssertEqual(am.shifted(by: TextChange(start: 5, oldEnd: 6, newEnd: 5)), [chord(4, 5)])
        XCTAssertEqual(am.shifted(by: TextChange(start: 3, oldEnd: 5, newEnd: 3)), [chord(3, 4)])
    }

    // -- TextEditsTest ------------------------------------------------------------------

    private func edit(_ start: Int, _ end: Int, _ replacement: String, cursor: Int,
                      anchor: Int? = nil) -> TextEdited {
        TextEdited(anchor: anchor, cursor: cursor, end: end, replacement: replacement, start: start,
                   textRevision: 1, undo: .plain)
    }

    /// What Python does: splice code points, the cursor in code points of the result.
    private func reference(_ text: String, _ e: TextEdited) -> (String, Int) {
        let scalars = Array(text.unicodeScalars)
        var out = String.UnicodeScalarView()
        out.append(contentsOf: scalars.prefix(e.start))
        out.append(contentsOf: e.replacement.unicodeScalars)
        out.append(contentsOf: scalars.dropFirst(e.end))
        let result = String(out)
        return (result, OffsetMapper(result).toUTF16(e.cursor))
    }

    private func check(_ text: String, _ e: TextEdited, file: StaticString = #filePath, line: UInt = #line) {
        let u = e.utf16(in: text)
        let (expected, cursor) = reference(text, e)
        XCTAssertEqual(UTF16Text.replacing(text, UTF16Range(u.start, u.end), with: u.replacement), expected,
                       file: file, line: line)
        XCTAssertEqual(u.cursor, cursor, "cursor for \(e) on \"\(text)\"", file: file, line: line)
    }

    func testInsertAfterAnEmoji() {
        // "😀 C" is 3 code points; insert "{bpm: 90}\n" at code point 2 (before C).
        let u = edit(2, 2, "{bpm: 90}\n", cursor: 12).utf16(in: "😀 C")
        XCTAssertEqual(u.start, 3)
        XCTAssertEqual(u.end, 3)
        XCTAssertEqual(UTF16Text.replacing("😀 C", UTF16Range(3, 3), with: u.replacement), "😀 {bpm: 90}\nC")
        XCTAssertEqual(u.cursor, 13)
    }

    func testWholeTextReplaceWithEmojiOnBothSides() {
        let text = "C 🎸 G\n😀 Am"
        let replacement = "D 🎸 A\n😀 Bm"
        check(text, edit(0, text.unicodeScalars.count, replacement, cursor: replacement.unicodeScalars.count))
    }

    func testCursorBeforeInsideAndAfterTheReplacement() {
        let text = "a😀b😀c"
        check(text, edit(2, 3, "X😀Y", cursor: 1))  // before
        check(text, edit(2, 3, "X😀Y", cursor: 4))  // inside, after the emoji
        check(text, edit(2, 3, "X😀Y", cursor: 6))  // after, past the second emoji
    }

    func testRandomEditsMatchTheCodePointReference() {
        var rng = SplitMix64(seed: 7)
        let alphabet: [String] = ["a", "b", " ", "\n", "😀", "🎸", "é", "C", "#"]
        func randomText(_ count: Int) -> String {
            (0..<count).map { _ in alphabet.randomElement(using: &rng)! }.joined()
        }
        for _ in 0..<500 {
            let text = randomText(Int.random(in: 0..<30, using: &rng))
            let cps = text.unicodeScalars.count
            let start = Int.random(in: 0...cps, using: &rng)
            let end = Int.random(in: start...cps, using: &rng)
            let replacement = randomText(Int.random(in: 0..<8, using: &rng))
            let newLength = cps - (end - start) + replacement.unicodeScalars.count
            check(text, edit(start, end, replacement, cursor: Int.random(in: 0...newLength, using: &rng)))
        }
    }

    func testOffsetsPastTheEndAreClamped() {
        let u = edit(5, 9, "x", cursor: 50).utf16(in: "ab")
        XCTAssertEqual(u.start, 2)
        XCTAssertEqual(u.end, 2)
        XCTAssertEqual(u.cursor, 3)
    }

    func testAnAnchorSelectsFromItToTheCursor() {
        // "// " put before two lines after an emoji; the selection covers them.
        let u = edit(2, 2, "// ", cursor: 9, anchor: 2).utf16(in: "😀\nC G\nAm")
        XCTAssertEqual(u.selection, UTF16Range(3, 10))
        XCTAssertNil(edit(0, 0, "x", cursor: 1).utf16(in: "").anchor)
    }

    func testASpanIsMappedAndClampedToTheText() {
        let mapper = OffsetMapper("😀 Am")
        XCTAssertEqual(Span(end: 4, kind: .chord, message: "", start: 2).utf16Range(mapper), UTF16Range(3, 5))
        XCTAssertEqual(Span(end: 40, kind: .chord, message: "", start: 30).utf16Range(mapper), UTF16Range(5, 5))
    }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `PlayheadGesturesTest`, case for case, and the marker's shape.
final class PlayheadGesturesTests: XCTestCase {
    // Two lines of chords, 20 pt tall: G (0..10) and C (50..60) on line 1, Em (5..25) on line 2.
    private let g = ChordBox(0, 1, left: 0, top: 0, right: 10, bottom: 20)
    private let c = ChordBox(8, 9, left: 50, top: 0, right: 60, bottom: 20)
    private let em = ChordBox(20, 22, left: 5, top: 40, right: 25, bottom: 60)
    private var boxes: [ChordBox] { [g, c, em] }

    func testVoiceOverReachesEachChordOnItsOwnAndReadsTheRestByLine() {
        // S0 issue 8: "Dm    Am     G        C" was one element; now four chords.
        let text = "{key: C}\nDm    Am  (x2)  G\n\nHow I wonder\nC♯m"
        let spans = [PaintedSpan(0, 8, .directive), PaintedSpan(9, 11, .chord), PaintedSpan(15, 17, .chord),
                     PaintedSpan(25, 26, .chord), PaintedSpan(41, 44, .chord), PaintedSpan(30, 30, .chord)]
        let items = playAccessibilityItems(text: text, spans: spans)
        XCTAssertEqual(items, [
            PlayAccessibilityItem(.text, 0, 8, "{key: C}"),
            PlayAccessibilityItem(.chord, 9, 11, "Dm"),
            PlayAccessibilityItem(.chord, 15, 17, "Am"),
            PlayAccessibilityItem(.text, 19, 23, "(x2)"),
            PlayAccessibilityItem(.chord, 25, 26, "G"),
            PlayAccessibilityItem(.text, 28, 40, "How I wonder"),
            PlayAccessibilityItem(.chord, 41, 44, "C♯m"),
        ], "an empty span is no chord; a blank line has nothing")
        XCTAssertTrue(playAccessibilityItems(text: "", spans: []).isEmpty)
    }

    func testATapOnAChordPlaysItATapElsewhereGoesToTheNearest() {
        XCTAssertEqual(resolveTap(boxes, 55, 10, slop: 4), .onChord(8))
        XCTAssertEqual(resolveTap(boxes, 62, 10, slop: 4), .onChord(8))
        XCTAssertEqual(resolveTap(boxes, 80, 10, slop: 4), .nearest(8))
        XCTAssertEqual(resolveTap(boxes, 20, 10, slop: 4), .nearest(0))
        XCTAssertNil(resolveTap([], 0, 0, slop: 4))
    }

    func testWhileASongPlaysATapThatMissesEveryChordDoesNothing() {
        XCTAssertEqual(resolveTap(boxes, 62, 10, slop: 4, nearestOnMiss: false), .onChord(8))
        XCTAssertNil(resolveTap(boxes, 80, 10, slop: 4, nearestOnMiss: false))
        XCTAssertNil(resolveTap(boxes, 30, 30, slop: 4, nearestOnMiss: false))
    }

    func testWhereGrownBoxesOverlapTheNearerChordWins() {
        let d = ChordBox(10, 11, left: 64, top: 0, right: 74, bottom: 20)
        let close = [g, c, d]
        XCTAssertEqual(resolveTap(close, 61, 10, slop: 8), .onChord(8))
        XCTAssertEqual(resolveTap(close, 63.5, 10, slop: 8), .onChord(10))
    }

    func testNearestPrefersTheSameLine() {
        XCTAssertEqual(nearestChord(boxes, 55, 50), em)
        XCTAssertEqual(nearestChord(boxes, 55, 25), c)
    }

    func testTheMarkerIsGrabbedAroundItsLeftEdgeOnly() {
        XCTAssertTrue(grabsMarker(c, 50, 10, grabWidth: 24))
        XCTAssertTrue(grabsMarker(c, 40, -8, grabWidth: 24))
        XCTAssertFalse(grabsMarker(c, 70, 10, grabWidth: 24))
        XCTAssertFalse(grabsMarker(c, 50, 40, grabWidth: 24))
        XCTAssertFalse(grabsMarker(nil, 50, 10, grabWidth: 24))
    }

    func testTheGrabBoxIsExactlyTheGrabStrip() {
        let box = markerGrabBox(g, grabWidth: 24)
        XCTAssertEqual(box.left, -12)
        XCTAssertEqual(box.right, 12)
        XCTAssertEqual(box.top, -12)
        XCTAssertEqual(box.bottom, 26)
        for x in -20...20 {
            for y in -20...40 {
                XCTAssertEqual(grabsMarker(g, Double(x), Double(y), grabWidth: 24), box.contains(Double(x), Double(y)),
                               "(\(x), \(y))")
            }
        }
    }

    func testAScrubMovesChordByChord() {
        XCTAssertNil(scrubTarget(boxes, current: 8, 52, 5))
        XCTAssertEqual(scrubTarget(boxes, current: 8, 10, 45), 20)
        XCTAssertEqual(scrubTarget(boxes, current: 8, 2, 5), 0)
    }

    func testTheMarkerSitsOnThePlayheadsChordOrTheNextOne() {
        let spans = [PaintedSpan(30, 32, .chord), PaintedSpan(0, 1, .chord), PaintedSpan(10, 14, .directive),
                     PaintedSpan(5, 7, .chordInvalid)]
        let chords = playableChords(spans)
        XCTAssertEqual(chords.map(\.start), [0, 30])
        XCTAssertEqual(markerChord(chords, playhead: 0)?.start, 0)
        XCTAssertEqual(markerChord(chords, playhead: 31)?.start, 30)
        XCTAssertEqual(markerChord(chords, playhead: 12)?.start, 30)
        XCTAssertNil(markerChord(chords, playhead: 40))
        XCTAssertNil(markerChord(chords, playhead: nil))
    }

    func testALongPressExplainsOnlyRedAndFadedDirectives() {
        let spans = [PaintedSpan(20, 28, .directiveRedundant), PaintedSpan(0, 8, .directiveInvalid),
                     PaintedSpan(9, 18, .directive), PaintedSpan(30, 31, .chord)]
        XCTAssertEqual(explainableDirectives(spans).map(\.start), [0, 20])
        let red = ChordBox(0, 8, left: 0, top: 0, right: 80, bottom: 20)
        XCTAssertEqual(explainableAt([red], 82, 10, slop: 4), red)
        XCTAssertNil(explainableAt([red], 90, 10, slop: 4))
    }

    func testTheMarkerIsABarLeftOfTheChordWithATriangleOnTop() {
        let marker = PlayheadMarker(before: c)
        XCTAssertEqual(marker.bar.x, 46.5)
        XCTAssertEqual(marker.bar.y, 0)
        XCTAssertEqual(marker.bar.width, 3)
        XCTAssertEqual(marker.bar.height, 20)
        XCTAssertEqual(marker.triangle.map(\.x), [42.5, 53.5, 48])
        XCTAssertEqual(marker.triangle.map(\.y), [-6, -6, 1])
    }
}

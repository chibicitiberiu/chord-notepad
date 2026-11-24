import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's ChordSheetSplitTest, the pane's content height and when the
/// strip follows the playhead.
final class ChordSheetLayoutTests: XCTestCase {
    // -- the split -----------------------------------------------------------------

    func testPlentyOfRoomKeepsTheStoredHeight() {
        XCTAssertEqual(ChordSheetSplit.height(wanted: 220, available: 700, windowHeight: 890)!, 220, accuracy: 0.01)
    }

    func testNeverMoreThan60PercentOfTheWindow() {
        XCTAssertEqual(ChordSheetSplit.height(wanted: 900, available: 900, windowHeight: 890)!, 534, accuracy: 0.01)
    }

    func testTheTextKeepsItsMinimumWhenTheKeyboardTakesTheRoom() {
        // 330 pt left (keyboard up): 330 - 96 (text) - 56 (below) = 178 for the sheet.
        XCTAssertEqual(ChordSheetSplit.height(wanted: 300, available: 330, windowHeight: 890)!, 178, accuracy: 0.01)
    }

    func testAShortSheetIsStillShownAboveTheHideLimit() {
        // 250 pt left: 250 - 96 - 56 = 98, below the usual 120 minimum but shown.
        XCTAssertEqual(ChordSheetSplit.height(wanted: 348, available: 250, windowHeight: 411)!, 98, accuracy: 0.01)
    }

    func testNoRoomForAUsableSheetHidesIt() {
        XCTAssertNil(ChordSheetSplit.height(wanted: 220, available: 220, windowHeight: 890))
    }

    func testATabletsUntouchedSheetTakesAShareOfTheWindowAMovedOneStays() {
        // Tablet portrait (800 x 1280) kept the phone's 160 pt strip.
        XCTAssertEqual(ChordSheetSplit.wantedHeight(stored: 160, windowWidth: 800, windowHeight: 1280), 448, accuracy: 0.01)
        XCTAssertEqual(ChordSheetSplit.wantedHeight(stored: 160, windowWidth: 1280, windowHeight: 800), 280, accuracy: 0.01)
        XCTAssertEqual(ChordSheetSplit.wantedHeight(stored: 200, windowWidth: 800, windowHeight: 1280), 200, accuracy: 0.01)
        // Phones keep the stored height, the default too.
        XCTAssertEqual(ChordSheetSplit.wantedHeight(stored: 160, windowWidth: 411, windowHeight: 914), 160, accuracy: 0.01)
    }

    func testADragStaysBetweenTheMinimumAndTheCap() {
        let range = ChordSheetSplit.dragRange(available: 700, windowHeight: 890)
        XCTAssertEqual(range.lowerBound, 120)
        XCTAssertEqual(range.upperBound, 534, accuracy: 0.01)
        // Little room: the cap is also the floor.
        let tight = ChordSheetSplit.dragRange(available: 250, windowHeight: 411)
        XCTAssertEqual(tight.lowerBound, 98, accuracy: 0.01)
        XCTAssertEqual(tight.upperBound, 98, accuracy: 0.01)
    }

    func testTheBufferIsFetchedForTheStripWithoutItsHeaderAndLane() {
        // A phone's 160 pt pane: 160 - 32 (tabs) - 2 (progress) - 4 (inset) = 122, less the 20 pt lane.
        XCTAssertEqual(ChordSheetPaneMetrics.stripHeight(paneHeight: 160), 122)
        XCTAssertEqual(ChordSheetPaneMetrics.contentHeight(stripHeight: 122), 102)
        XCTAssertEqual(ChordSheetPaneMetrics.contentHeight(stripHeight: 122.9, laneHeight: 20), 102)
        XCTAssertEqual(ChordSheetPaneMetrics.contentHeight(stripHeight: 10), 0)
        XCTAssertEqual(ChordSheetPaneMetrics.stripHeight(paneHeight: 10), 0)
    }

    // -- following the playhead ----------------------------------------------------

    func testTheChordSoundingIsFollowedWhenItTheSheetOrTheViewportChanges() {
        var follower = PlayheadFollower()
        XCTAssertEqual(follower.update(currentIndex: 3, cursorIndex: 3, sheetID: 1, viewportWidth: 400), 3)
        XCTAssertNil(follower.update(currentIndex: 3, cursorIndex: 3, sheetID: 1, viewportWidth: 400))
        XCTAssertEqual(follower.update(currentIndex: 4, cursorIndex: 4, sheetID: 1, viewportWidth: 400), 4)
        XCTAssertEqual(follower.update(currentIndex: 4, cursorIndex: 4, sheetID: 2, viewportWidth: 400), 4)  // a new buffer
        XCTAssertEqual(follower.update(currentIndex: 4, cursorIndex: 4, sheetID: 2, viewportWidth: 600), 4)  // rotated
    }

    func testWhileNothingPlaysOnlyAPlayheadMoveScrolls() {
        var follower = PlayheadFollower()
        // Before any buffer: nothing to scroll yet; the first sheet brings the playhead in.
        _ = follower.update(currentIndex: nil, cursorIndex: 7, sheetID: nil, viewportWidth: 0)
        XCTAssertEqual(follower.update(currentIndex: nil, cursorIndex: 7, sheetID: 1, viewportWidth: 400), 7)
        // A zoom (new buffer) or a rotation leaves a hand-scrolled strip alone.
        XCTAssertNil(follower.update(currentIndex: nil, cursorIndex: 7, sheetID: 2, viewportWidth: 400))
        XCTAssertNil(follower.update(currentIndex: nil, cursorIndex: 7, sheetID: 2, viewportWidth: 700))
        // A tapped chord or ⏮ moves it.
        XCTAssertEqual(follower.update(currentIndex: nil, cursorIndex: 12, sheetID: 2, viewportWidth: 700), 12)
        XCTAssertEqual(follower.update(currentIndex: nil, cursorIndex: 0, sheetID: 2, viewportWidth: 700), 0)
        // Playback stops: the chord sounding is gone, the playhead stays.
        XCTAssertEqual(follower.update(currentIndex: 5, cursorIndex: 5, sheetID: 2, viewportWidth: 700), 5)
        XCTAssertNil(follower.update(currentIndex: nil, cursorIndex: 5, sheetID: 2, viewportWidth: 700))
    }
}

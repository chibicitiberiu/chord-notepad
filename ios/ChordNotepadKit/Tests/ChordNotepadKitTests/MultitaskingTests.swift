import XCTest

@testable import ChordNotepadKit

/// The layouts in the window sizes iPad multitasking gives (Split View, Slide
/// Over, Stage Manager): every rule reads the window's size, so a narrow
/// window on an iPad is laid out as a phone's, at Android's breakpoints
/// (the 600 dp smallest width, the 600 dp Settings panes, the identifier's
/// 600 × 600 dialog). The sizes are an 11-inch iPad Air's (820 × 1180 pt)
/// windows, near enough: the exact Split View widths vary by model.
final class MultitaskingTests: XCTestCase {
    private let third = (width: 375.0, height: 820.0)     // a third on its side, or Slide Over
    private let half = (width: 585.0, height: 820.0)      // half on its side
    private let twoThirds = (width: 795.0, height: 820.0) // two thirds on its side
    private let portraitThird = (width: 320.0, height: 1180.0)
    private let portraitTwoThirds = (width: 490.0, height: 1180.0)

    func testNarrowWindowsAreLaidOutAsAnUprightPhone() {
        for window in [third, half, portraitThird, portraitTwoThirds] {
            let edit = ScreenLayout.of(width: window.width, height: window.height, mode: .edit, sheetVisible: true)
            XCTAssertTrue(edit.phone, "\(window)")
            XCTAssertFalse(edit.landscape)
            XCTAssertFalse(edit.oneLineHeader, "upright: the ribbon has its own line")
            let play = ScreenLayout.of(width: window.width, height: window.height, mode: .play, sheetVisible: true)
            XCTAssertTrue(play.sheetBelow, "\(window): the sheet below the text")
            XCTAssertFalse(play.sideBySide)
            XCTAssertFalse(play.compactPlayer)
        }
    }

    func testTwoThirdsAndTheFullScreenAreATablets() {
        let wide = ScreenLayout.of(width: twoThirds.width, height: twoThirds.height, mode: .play, sheetVisible: true)
        XCTAssertFalse(wide.phone)
        XCTAssertTrue(wide.sheetBelow, "taller than wide")
        let full = ScreenLayout.of(width: 1180, height: 820, mode: .play, sheetVisible: true)
        XCTAssertFalse(full.phone)
        XCTAssertTrue(full.sideBySide)
    }

    func testTheBreakpointIsTheSmallestSideAt600AsAndroidsSw600() {
        XCTAssertTrue(ScreenLayout.of(width: 599, height: 900, mode: .edit, sheetVisible: false).phone)
        XCTAssertFalse(ScreenLayout.of(width: 600, height: 900, mode: .edit, sheetVisible: false).phone)
        // A Stage Manager window wider than tall but under 600 pt high: a phone on its side.
        let short = ScreenLayout.of(width: 900, height: 560, mode: .edit, sheetVisible: false)
        XCTAssertTrue(short.phone && short.landscape && short.oneLineHeader)
        let shortPlay = ScreenLayout.of(width: 900, height: 560, mode: .play, sheetVisible: true)
        XCTAssertTrue(shortPlay.sideBySide)
    }

    func testTheSheetPaneFitsEachSplitWindow() throws {
        for window in [third, half, portraitThird, portraitTwoThirds, twoThirds] {
            for stored in [160, 330] {
                let pane = try XCTUnwrap(MainSheetPane.height(width: window.width, height: window.height, stored: stored))
                let header = MainMetrics.barHeight + MainMetrics.dividerHeight
                XCTAssertGreaterThan(pane, 0, "\(window)")
                XCTAssertLessThan(pane, window.height - header - MainMetrics.playerHeight, "\(window): text keeps room")
            }
        }
    }

    func testSettingsAndTheIdentifierFollowTheWindow() {
        XCTAssertFalse(settingsTwoPane(width: third.width))
        XCTAssertFalse(settingsTwoPane(width: half.width))
        XCTAssertTrue(settingsTwoPane(width: twoThirds.width))
        XCTAssertEqual(identifierLayout(width: third.width, height: third.height), .fullScreen)
        XCTAssertEqual(identifierLayout(width: half.width, height: half.height), .fullScreen)
        XCTAssertEqual(identifierLayout(width: twoThirds.width, height: twoThirds.height), .dialog)
        XCTAssertEqual(identifierLayout(width: 900, height: 560), .sideBySide)
    }

    // -- the keyboard over a window that isn't the whole screen ----------------------------------

    private let screen = PointRect(x: 0, y: 0, width: 1180, height: 820)
    private let keyboard = PointRect(x: 0, y: 422, width: 1180, height: 398)

    func testAFullScreenWindowGetsTheKeyboardsHeight() {
        XCTAssertEqual(keyboardOverlap(window: screen, keyboard: keyboard), 398)
    }

    func testASplitViewWindowGetsWhatLiesOverIt() {
        let right = PointRect(x: 805, y: 0, width: 375, height: 820)
        XCTAssertEqual(keyboardOverlap(window: right, keyboard: keyboard), 398)
    }

    func testAStageManagerWindowAboveTheKeyboardGetsNothingOrPart() {
        let high = PointRect(x: 100, y: 40, width: 700, height: 360)
        XCTAssertEqual(keyboardOverlap(window: high, keyboard: keyboard), 0)
        let low = PointRect(x: 100, y: 300, width: 700, height: 400)
        XCTAssertEqual(keyboardOverlap(window: low, keyboard: keyboard), 278)
    }

    func testAFloatingKeyboardBesideTheWindowOrGoneCoversNothing() {
        let window = PointRect(x: 0, y: 0, width: 585, height: 820)
        let floating = PointRect(x: 700, y: 500, width: 320, height: 260)
        XCTAssertEqual(keyboardOverlap(window: window, keyboard: floating), 0)
        let gone = PointRect(x: 0, y: 820, width: 1180, height: 398)
        XCTAssertEqual(keyboardOverlap(window: screen, keyboard: gone), 0)
        XCTAssertEqual(keyboardOverlap(window: screen, keyboard: PointRect(x: 0, y: 0, width: 0, height: 0)), 0)
    }

    func testAFloatingKeyboardOverTheWindowCoversFromItsTop() {
        let floating = PointRect(x: 100, y: 500, width: 320, height: 260)
        XCTAssertEqual(keyboardOverlap(window: screen, keyboard: floating), 320)
    }
}

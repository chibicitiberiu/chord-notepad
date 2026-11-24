import Foundation
import XCTest

@testable import ChordNotepadKit

/// The app's keyboard shortcuts (Android's `ShortcutsTest` for New, Open,
/// Save, Save As and the font size, the desktop's find keys as iPadOS has
/// them), the pinch on the text (Android's `pinchToZoomFont`) and the side
/// column's width kept across launches (Android's `UiPreferences`).
final class AppShortcutsTests: XCTestCase {
    private func command(_ input: String, shift: Bool = false, option: Bool = false) -> AppCommand? {
        AppShortcut.command(input: input, command: true, shift: shift, option: option)
    }

    func testAndroidsWindowShortcutsWithCommand() {
        XCTAssertEqual(command("n"), .newSong)
        XCTAssertEqual(command("o"), .open)
        XCTAssertEqual(command("s"), .save)
        XCTAssertEqual(command("S", shift: true), .saveAs)
        XCTAssertEqual(command("="), .fontBigger)
        XCTAssertEqual(command("-"), .fontSmaller)
        XCTAssertEqual(command("0"), .fontReset)
        // Android's F1, as Apple's Help key.
        XCTAssertEqual(command("?"), .userGuide)
    }

    func testFindAndReplaceUseApplesKeys() {
        XCTAssertEqual(command("f"), .find)
        XCTAssertEqual(command("f", option: true), .findAndReplace)
        XCTAssertEqual(command("g"), .findNext)
        XCTAssertEqual(command("G", shift: true), .findPrevious)
        // Command-H is the iPad's Home Screen key: not taken.
        XCTAssertNil(command("h"))
    }

    func testPlainKeysAndTheEditorsOwnKeysPassThrough() {
        XCTAssertNil(AppShortcut.command(input: "n", command: false, shift: false, option: false))
        XCTAssertNil(command("z"))
        XCTAssertNil(command("z", shift: true))
        XCTAssertNil(command("/"))
        XCTAssertNil(command("d"))
        XCTAssertNil(command("a"))
        // No key is both the app's and the text view's.
        for shortcut in AppShortcut.all {
            XCTAssertNil(EditorKeyBinding.action(input: shortcut.input, command: true, shift: shortcut.shift,
                                                 option: shortcut.option), shortcut.title)
        }
    }

    func testEveryCommandHasOneKeyAndATitleInItsMenu() {
        let keys = AppShortcut.all.map { "\($0.input) \($0.shift) \($0.option)" }
        XCTAssertEqual(Set(keys).count, keys.count)
        XCTAssertEqual(Set(AppShortcut.all.map(\.command)), Set(AppCommand.allCases))
        XCTAssertEqual(AppShortcut.all.count, AppCommand.allCases.count)
        XCTAssertEqual(AppShortcut.listed(in: .file).map(\.title), ["New Song", "Open…", "Save", "Save As…"])
        XCTAssertEqual(AppShortcut.listed(in: .edit).map(\.title),
                       ["Find…", "Find and Replace…", "Find Next", "Find Previous"])
        XCTAssertEqual(AppShortcut.listed(in: .view).map(\.title), ["Larger Text", "Smaller Text", "Reset Text Size"])
        XCTAssertEqual(AppShortcut.listed(in: .help).map(\.title), ["User Guide"])
        XCTAssertEqual(AppShortcut.of(.saveAs)?.shift, true)
        // The text view's untitled Command-+ isn't listed twice.
        XCTAssertEqual(EditorKeyBinding.all.filter { $0.title.isEmpty }.map(\.action), [.fontBigger, .fontBigger])
    }

    func testShortcutsActOnTheMainScreenOnly() {
        XCTAssertTrue(MainUiState(mode: .play).shortcutsAct(requestPending: false))
        XCTAssertTrue(MainUiState(mode: .edit).shortcutsAct(requestPending: false))
        XCTAssertFalse(MainUiState(mode: .edit).shortcutsAct(requestPending: true))
        for route in [MainRoute.menu, .voicing, .settings, .about, .identify, .insert, .rename] {
            XCTAssertFalse(MainUiState(mode: .edit, route: route).shortcutsAct(requestPending: false), "\(route)")
        }
    }

    // -- the pinch ---------------------------------------------------------------------

    func testAPinchSendsEachNewSizeAsAStepFromWhereItBegan() {
        var pinch = FontPinch()
        XCTAssertNil(pinch.changed(scale: 2), "no pinch yet")
        pinch.began(points: 11)
        XCTAssertNil(pinch.changed(scale: 1.02), "still 11")
        XCTAssertEqual(pinch.changed(scale: 1.1), 1)
        XCTAssertNil(pinch.changed(scale: 1.1))
        XCTAssertEqual(pinch.changed(scale: 2), 10)
        XCTAssertEqual(pinch.changed(scale: 0.5), -16)
        XCTAssertEqual(pinch.sent, 6)
        XCTAssertNil(pinch.changed(scale: 0.1), "clamped at 6")
        XCTAssertNil(pinch.changed(scale: .nan))
        pinch.ended()
        XCTAssertNil(pinch.base)
        XCTAssertNil(pinch.changed(scale: 3))
    }

    func testAPinchStopsAtTheLargestSize() {
        var pinch = FontPinch()
        pinch.began(points: 40)
        XCTAssertEqual(pinch.changed(scale: 3), 32)
        XCTAssertNil(pinch.changed(scale: 4))
        // The steps add up to what pinchSize says.
        var again = FontPinch()
        again.began(points: 11)
        var total = 11
        for scale in stride(from: 1.0, through: 3.0, by: 0.07) {
            total += again.changed(scale: scale) ?? 0
            XCTAssertEqual(total, EditorFont.pinchSize(11, zoom: scale))
        }
    }

    // -- the side column's width ---------------------------------------------------------

    func testTheSideColumnsWidthIsKeptClampedUnderAndroidsKey() {
        let store = MemoryPreferences()
        let prefs = UiPreferences(store: store)
        XCTAssertEqual(prefs.sideFraction, MainMetrics.sideFractionDefault)
        prefs.sideFraction = 0.62
        XCTAssertEqual(store.values["side_fraction"], 0.62)
        XCTAssertEqual(UiPreferences(store: store).sideFraction, 0.62, "a new launch reads it back")
        prefs.sideFraction = 0.95
        XCTAssertEqual(store.values["side_fraction"], MainMetrics.sideFractionMax)
        store.set(0.1, forKey: UiPreferences.sideFractionKey)
        XCTAssertEqual(prefs.sideFraction, MainMetrics.sideFractionMin)
        store.set(.nan, forKey: UiPreferences.sideFractionKey)
        XCTAssertEqual(prefs.sideFraction, MainMetrics.sideFractionDefault)
    }
}

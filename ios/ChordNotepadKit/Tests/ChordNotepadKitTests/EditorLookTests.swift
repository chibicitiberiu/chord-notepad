import Foundation
import XCTest

@testable import ChordNotepadKit

/// The editor's look: Android's `EditorLookTest` (fonts, priority, the faded
/// redundant directive, the pinch), the style runs both drawings share, and
/// the keyboard shortcuts (Android's `ShortcutsTest` with Command for Ctrl).
final class EditorLookTests: XCTestCase {
    func testDesktopFontFamiliesMapToTheThreeKinds() {
        XCTAssertEqual(EditorFont.kind(forFamily: "TkFixedFont"), .monospace)
        XCTAssertEqual(EditorFont.kind(forFamily: ""), .monospace)
        XCTAssertEqual(EditorFont.kind(forFamily: "DejaVu Sans Mono"), .monospace)
        XCTAssertEqual(EditorFont.kind(forFamily: "Courier New"), .monospace)
        XCTAssertEqual(EditorFont.kind(forFamily: "DejaVu Sans"), .sans)
        XCTAssertEqual(EditorFont.kind(forFamily: "Arial"), .sans)
        XCTAssertEqual(EditorFont.kind(forFamily: "Times New Roman"), .serif)
        XCTAssertEqual(EditorFont.kind(forFamily: "Noto Serif"), .serif)
        XCTAssertEqual(EditorFont.kind(forFamily: "Some Unknown Font"), .monospace)
    }

    func testPointsBecomeIOSPointsAtTks96DPI() {
        XCTAssertEqual(EditorFont.pointSize(12), 16, accuracy: 0.001)
        XCTAssertEqual(EditorFont.pointSize(11), 14.667, accuracy: 0.001)
    }

    func testAPinchScalesTheFontSizeClamped() {
        XCTAssertEqual(EditorFont.pinchSize(11, zoom: 1), 11)
        XCTAssertEqual(EditorFont.pinchSize(11, zoom: 2), 22)
        XCTAssertEqual(EditorFont.pinchSize(11, zoom: 0.1), 6)
        XCTAssertEqual(EditorFont.pinchSize(40, zoom: 3), 72)
    }

    func testTheConfiguredFamilyIsKeptWhenItAlreadyIsTheChosenKind() {
        XCTAssertEqual(EditorFont.configFamily(for: .monospace, current: "TkFixedFont"), "TkFixedFont")
        XCTAssertEqual(EditorFont.configFamily(for: .monospace, current: "Consolas"), "Consolas")
        XCTAssertEqual(EditorFont.configFamily(for: .serif, current: "Times New Roman"), "Times New Roman")
        for kind in EditorFontKind.allCases {
            for current in ["TkFixedFont", "Sans", "Serif", "Arial"] {
                XCTAssertEqual(EditorFont.kind(forFamily: EditorFont.configFamily(for: kind, current: current)), kind)
            }
        }
        XCTAssertEqual(EditorFont.configFamily(for: .monospace, current: "Arial"), "TkFixedFont")
        XCTAssertEqual(EditorFont.configFamily(for: .sans, current: "TkFixedFont"), "Sans")
        XCTAssertEqual(EditorFont.configFamily(for: .serif, current: "TkFixedFont"), "Serif")
    }

    func testSpanKindsPaintInTheDesktopsTagPriority() {
        XCTAssertEqual(spanPriority, [.chord, .chordInvalid, .directive, .directiveInvalid, .directiveRedundant,
                                      .comment])
        XCTAssertEqual(Set(spanPriority), Set(SpanKind.allCases))
    }

    func testARedundantDirectiveIsTheDirectiveColourFadedInBothThemes() {
        for palette in [EditorPalette.light, .dark] {
            XCTAssertEqual(palette.style(.directiveRedundant).color,
                           palette.directive.withAlpha(EditorPalette.redundantAlpha))
        }
        // The light theme is the desktop's Tk colours.
        XCTAssertEqual(EditorPalette.light.chord.argb, 0xFF00_00FF)
        XCTAssertEqual(EditorPalette.light.comment.argb, 0xFFBE_BEBE)
        XCTAssertEqual(EditorPalette.light.playing.argb, 0xFFFF_FF00)
    }

    func testRunsDontOverlapAndHigherPriorityKindsWin() {
        let p = EditorPalette.light
        // "C G // x": chords, then a comment over the second chord and beyond.
        let spans = [PaintedSpan(0, 1, .chord), PaintedSpan(2, 3, .chord), PaintedSpan(2, 8, .comment)]
        let runs = styleRuns(spans: spans, playing: nil, length: 8, palette: p)
        XCTAssertEqual(runs, [
            StyleRun(0, 1, RunStyle(color: p.chord, underline: true)),
            // The comment's colour wins, the chord's underline stays (the comment sets none).
            StyleRun(2, 3, RunStyle(color: p.comment, underline: true)),
            StyleRun(3, 8, RunStyle(color: p.comment)),
        ])
    }

    func testThePlayingChordIsPaintedOverEverything() {
        let p = EditorPalette.dark
        let runs = styleRuns(spans: [PaintedSpan(0, 2, .chord), PaintedSpan(3, 4, .chord)],
                             playing: UTF16Range(3, 4), length: 4, palette: p)
        XCTAssertEqual(runs, [
            StyleRun(0, 2, RunStyle(color: p.chord, underline: true)),
            StyleRun(3, 4, RunStyle(color: p.text, underline: true, background: p.playing)),
        ])
    }

    func testRunsAreClampedToTheTextAndNeighboursWithOneStyleMerge() {
        let p = EditorPalette.light
        let runs = styleRuns(spans: [PaintedSpan(0, 2, .directive), PaintedSpan(2, 5, .directive),
                                     PaintedSpan(4, 40, .comment), PaintedSpan(50, 60, .chord)],
                             playing: UTF16Range(70, 80), length: 6, palette: p)
        XCTAssertEqual(runs, [
            StyleRun(0, 4, RunStyle(color: p.directive, underline: false)),
            StyleRun(4, 5, RunStyle(color: p.comment, underline: false)),
            StyleRun(5, 6, RunStyle(color: p.comment)),
        ])
        XCTAssertEqual(styleRuns(spans: [], playing: nil, length: 10, palette: p), [])
    }

    // -- ShortcutsTest ---------------------------------------------------------------

    func testTheDesktopsShortcutsWithCommand() {
        func action(_ input: String, shift: Bool = false, option: Bool = false) -> EditorAction? {
            EditorKeyBinding.action(input: input, command: true, shift: shift, option: option)
        }
        XCTAssertEqual(action("="), .fontBigger)
        XCTAssertEqual(action("+", shift: true), .fontBigger)
        XCTAssertEqual(action("-"), .fontSmaller)
        XCTAssertEqual(action("0"), .fontReset)
        XCTAssertEqual(action("z"), .undo)
        XCTAssertEqual(action("Z", shift: true), .redo)
        XCTAssertEqual(action("/"), .toggleComment)
        XCTAssertEqual(action("d"), .duplicateLines)
        XCTAssertEqual(action("k", shift: true), .deleteLines)
        XCTAssertEqual(action(EditorKeyBinding.upArrow, option: true), .moveLinesUp)
        XCTAssertEqual(action(EditorKeyBinding.downArrow, option: true), .moveLinesDown)
    }

    func testPlainKeysAndTheTextViewsOwnShortcutsPassThrough() {
        XCTAssertNil(EditorKeyBinding.action(input: "z", command: false, shift: false, option: false))
        XCTAssertNil(EditorKeyBinding.action(input: "a", command: true, shift: false, option: false))
        XCTAssertNil(EditorKeyBinding.action(input: "c", command: true, shift: false, option: false))
        // Shift-Command-Up selects to the start on Apple platforms: not taken.
        XCTAssertNil(EditorKeyBinding.action(input: EditorKeyBinding.upArrow, command: true, shift: true,
                                             option: false))
        // Every binding is declared once.
        let keys = EditorKeyBinding.all.map { "\($0.input) \($0.shift) \($0.option)" }
        XCTAssertEqual(Set(keys).count, keys.count)
    }
}

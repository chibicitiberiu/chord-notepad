import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's ChordSheetThemeTest and ChordSheetPaperTest as behaviour specs:
/// how the buffer's colours paint in the light and the dark theme.
final class ChordSheetThemeTests: XCTestCase {
    private let light = ChordSheetColors.light
    private let dark = ChordSheetColors.dark

    private func c(_ argb: UInt32) -> SheetColor { SheetColor(argb: argb) }

    private func themed(_ spec: String, _ colors: ChordSheetColors) -> SheetColor {
        ChordSheetTheme.themed(spec, SheetColor(tk: spec)!, colors)
    }

    private func keyboard(_ spec: String, _ colors: ChordSheetColors) -> SheetColor {
        ChordSheetTheme.keyboardGutter(spec, SheetColor(tk: spec)!, colors)
    }

    func testTheKeyboardKeepsItsColoursInLightAndTakesTheAppsGreysInDark() {
        XCTAssertEqual(keyboard("#ffffff", light), c(0xFFFF_FFFF))
        XCTAssertEqual(keyboard("#31424a", light), c(0xFF31_424A))
        // The desktop's dark keyboard (sheet_paint._DARK_KEYS).
        XCTAssertEqual(keyboard("#ffffff", dark), c(0xFFC3_C6CF))
        XCTAssertEqual(keyboard("#31424a", dark), c(0xFF17_181B))
        XCTAssertEqual(keyboard("#B9C2C7", dark), c(0xFF8A_8D96))
        XCTAssertEqual(keyboard("#22323a", dark), c(0xFF1D_1E22))
        // White keys stay lighter than black keys, so the keyboard isn't inverted.
        XCTAssertGreaterThan(keyboard("#ffffff", dark).lightness, keyboard("#31424a", dark).lightness)
    }

    func testLightKeepsTheBuffersColours() {
        XCTAssertEqual(themed("#22323a", light), c(0xFF22_323A))
        XCTAssertEqual(themed("#a04848", light), c(0xFFA0_4848))
    }

    func testDarkLightensTheHandsBarsToTheSpecsColours() {
        XCTAssertEqual(themed("#2a6f8a", dark), c(0xFF78_A6D8))
        XCTAssertEqual(themed("#8A5A3A", dark), c(0xFFD0_9A6C))
    }

    func testDarkFlipsNeutralInksAndKeepsHuesReadable() {
        XCTAssertGreaterThan(themed("#22323a", dark).lightness, 0.7)
        XCTAssertLessThan(themed("#b9c2c7", dark).lightness, 0.4)
        let voice = themed("#a04848", dark)
        XCTAssertGreaterThanOrEqual(voice.lightness, 0.65)
        XCTAssertGreaterThan(voice.red, voice.green)
        // A warm off-white flips without turning olive: most of its tint goes.
        let warm = c(0xFFF6_F6F2)
        let flipped = ChordSheetTheme.darkVariant(warm)
        XCTAssertLessThan(flipped.lightness, 0.2)
        XCTAssertEqual(flipped.hsl.saturation, warm.hsl.saturation * 0.3, accuracy: 0.01)
        XCTAssertEqual(flipped.alpha, 1)
    }

    func testThePianoRollsNoteNamesAreWhiteOnLightBarsAndDarkOnTheDarkThemes() {
        XCTAssertEqual(themed("#fdfdff", light), c(0xFFFD_FDFF))
        XCTAssertLessThan(themed("#fdfdff", dark).lightness, 0.15)
        // The bars it sits on get lighter in the dark theme (the indigo note fill).
        XCTAssertGreaterThanOrEqual(themed("#5c6bc0", dark).lightness, 0.65)
    }

    func testTheStripsPaperIsTheSheetSurfaceInBothThemes() {
        XCTAssertEqual(themed("#fbfbf8", light), light.surfaceLow)
        XCTAssertEqual(themed("#FBFBF8", dark), dark.surfaceLow)
    }

    func testABandedSectionIsAStepFromTheStripAndTheRollsBlackRowsStayVisibleOnIt() {
        for colors in [light, dark] {
            let paper = themed("#fbfbf8", colors)
            let banded = themed("#f6f6f2", colors)
            XCTAssertEqual(banded, ChordSheetTheme.sectionBand(colors))
            // Halfway between the strip's paper and surface2 (Tibi, 2026-11-15: half the step).
            XCTAssertEqual(banded.lightness, (paper.lightness + colors.surface2.lightness) / 2, accuracy: 0.002)
            let step = banded.lightness - paper.lightness
            // Darker in the light theme, lighter in the dark one; subtle either way.
            if colors.dark {
                XCTAssertTrue(step > 0.008 && step < 0.03, "\(step)")
            } else {
                XCTAssertTrue(step < -0.008 && step > -0.03, "\(step)")
            }
            // Black-key rows differ from the paper they sit on, on both.
            XCTAssertGreaterThan(abs(themed("#eceef2", colors).lightness - paper.lightness), 0.02)
            XCTAssertGreaterThan(abs(themed("#e7e9ed", colors).lightness - banded.lightness), 0.02)
        }
    }

    func testHSLRoundTripsThroughTheConversion() {
        for argb: UInt32 in [0xFF22_323A, 0xFFA0_4848, 0xFF5C_6BC0, 0xFF2A_6F8A, 0xFFFF_FFFF, 0xFF00_0000, 0xFF80_FF20] {
            let color = c(argb)
            let (h, s, l) = color.hsl
            XCTAssertEqual(SheetColor(hue: h, saturation: s, lightness: l).argb, argb, String(format: "%08x", argb))
        }
    }

    func testAPaletteThemesEveryColourOfABufferAndNothingElse() throws {
        let buffer = try SheetBuffer.decode(try SheetBufferTests.bytes("american_staff"))
        let palette = ChordSheetPalette(strings: buffer.strings, colors: dark)
        XCTAssertEqual(palette.content["#fbfbf8"], dark.surfaceLow)
        XCTAssertNil(palette.content["slot:3"])
        XCTAssertEqual(Set(palette.content.keys), Set(buffer.strings.filter { SheetColor(tk: $0) != nil }))
        // Untinted glyphs take the dark theme's ink; light draws them as they are.
        XCTAssertEqual(palette.defaultGlyphTint, themed("#22323a", dark))
        XCTAssertNil(ChordSheetPalette(strings: buffer.strings, colors: light).defaultGlyphTint)
        XCTAssertEqual(palette.glyphTint("#a04848"), themed("#a04848", dark))
        XCTAssertEqual(ChordSheetPalette(strings: [], colors: light).glyphTint("#a04848"), c(0xFFA0_4848))
    }
}

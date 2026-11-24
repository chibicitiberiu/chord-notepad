import Foundation
import XCTest

@testable import ChordNotepadKit

/// A ``SheetCanvas`` that records every call, with a made-up but fixed font
/// metric (each character 0.5 em wide, the line box 1.2 em tall).
final class RecordingCanvas: SheetCanvas {
    enum Call: Equatable {
        case save, restore
        case translate(Double, Double)
        case clip(SheetRect)
        case fill(SheetRect, radius: Double, SheetColor)
        case stroke(SheetRect, radius: Double, SheetColor, width: Double)
        case fillEllipse(SheetRect, SheetColor)
        case strokeEllipse(SheetRect, SheetColor, width: Double)
        case line([Double], SheetColor, width: Double)
        case path([SheetPathElement], SheetColor)
        case text(String, SheetFont, x: Double, y: Double, SheetColor, clipRight: Double?)
        case glyph(String, SheetRect, tint: SheetColor?)
    }

    private(set) var calls: [Call] = []

    func saveState() { calls.append(.save) }
    func restoreState() { calls.append(.restore) }
    func translate(x: Double, y: Double) { calls.append(.translate(x, y)) }
    func clip(to rect: SheetRect) { calls.append(.clip(rect)) }
    func fill(_ rect: SheetRect, cornerRadius: Double, color: SheetColor) {
        calls.append(.fill(rect, radius: cornerRadius, color))
    }
    func stroke(_ rect: SheetRect, cornerRadius: Double, color: SheetColor, width: Double) {
        calls.append(.stroke(rect, radius: cornerRadius, color, width: width))
    }
    func fillEllipse(in rect: SheetRect, color: SheetColor) { calls.append(.fillEllipse(rect, color)) }
    func strokeEllipse(in rect: SheetRect, color: SheetColor, width: Double) {
        calls.append(.strokeEllipse(rect, color, width: width))
    }
    func strokeLine(_ points: [Double], color: SheetColor, width: Double) {
        calls.append(.line(points, color, width: width))
    }
    func fill(_ path: [SheetPathElement], color: SheetColor) { calls.append(.path(path, color)) }
    func measure(_ text: String, font: SheetFont) -> SheetSize {
        SheetSize(width: Double(text.count) * font.size * 0.5, height: font.size * 1.2)
    }
    func draw(_ text: String, font: SheetFont, x: Double, y: Double, color: SheetColor, clipRight: Double?) {
        calls.append(.text(text, font, x: x, y: y, color, clipRight: clipRight))
    }
    func drawGlyph(_ asset: String, in rect: SheetRect, tint: SheetColor?) {
        calls.append(.glyph(asset, rect, tint: tint))
    }

    var glyphs: [(asset: String, rect: SheetRect, tint: SheetColor?)] {
        calls.compactMap { if case .glyph(let a, let r, let t) = $0 { return (a, r, t) } else { return nil } }
    }

    var texts: [(text: String, font: SheetFont, x: Double, y: Double, color: SheetColor, clipRight: Double?)] {
        calls.compactMap {
            if case .text(let s, let f, let x, let y, let c, let r) = $0 { return (s, f, x, y, c, r) } else { return nil }
        }
    }

    /// Calls that draw something (not state changes).
    var drawCalls: [Call] {
        calls.filter {
            switch $0 {
            case .save, .restore, .translate, .clip: return false
            default: return true
            }
        }
    }
}

/// The painter over the Android fixtures with a recording canvas: what it
/// draws, where, in which colour, on the same rules as Android's
/// ChordSheetPainter.kt and ChordSheetPane.kt (and the desktop's sheet_paint.py).
final class SheetPainterTests: XCTestCase {
    /// The base glyph sizes from the core (what glyphs.json holds in the app).
    private func glyphIndex() async throws -> SheetGlyphIndex {
        let runtime = try await TestPython.runtime()
        let json = try await runtime.call("cn_kit_testmod", "glyph_index")
        return try SheetGlyphIndex(json: Data(try XCTUnwrap(json).utf8))
    }

    private func sheet(_ name: String) throws -> PreparedSheet {
        PreparedSheet(try SheetBuffer.decode(try SheetBufferTests.bytes(name)))
    }

    private let light = ChordSheetColors.light
    private let dark = ChordSheetColors.dark

    private func frame(_ sheet: PreparedSheet, width: Double = 400, scroll: Double = 0, current: Int? = nil,
                       cursor: Int? = nil) -> SheetFrame {
        SheetFrame(size: SheetSize(width: width, height: Double(sheet.buffer.laneHeight + sheet.buffer.contentHeight)),
                   scrollX: scroll, currentIndex: current, cursorIndex: cursor)
    }

    // -- glyph sizes ---------------------------------------------------------------

    func testGlyphsAreSizedLikeClefAssetsScaledWidth() async throws {
        let index = try await glyphIndex()
        XCTAssertEqual(index.baseSizes.count, 7)
        var keys = Set<String>()
        for name in ["american_staff", "american_staff_z1728", "multikey_staff"] {
            keys.formUnion(try sheet(name).imageKeys)
        }
        XCTAssertGreaterThan(keys.count, 10)
        let runtime = try await TestPython.runtime()
        let json = String(decoding: try JSONEncoder().encode(keys.sorted()), as: UTF8.self)
        let answer = try await runtime.call("cn_kit_testmod", "scaled_widths", [json])
        let expected = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(try XCTUnwrap(answer).utf8))
            as? [String: Int])
        for key in keys {
            let parsed = try XCTUnwrap(SheetImageKey(key), key)
            let size = try XCTUnwrap(index.size(of: parsed), key)
            XCTAssertEqual(Int(size.width), expected[key], key)
            XCTAssertEqual(size.height, Double(parsed.height), key)
        }
        XCTAssertNil(index.size(of: SheetImageKey(asset: "glyph_unknown", height: 9, tint: nil)))
        XCTAssertThrowsError(try SheetGlyphIndex(json: Data(#"{"version": 2, "assets": {}}"#.utf8)))
    }

    // -- the strip -------------------------------------------------------------------

    func testTheStripPaintsBackgroundThenLaneAndContentRightOfTheGutterThenTheGutter() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 1)
        let sheet = try sheet("american_staff")
        let buffer = sheet.buffer
        let palette = ChordSheetPalette(strings: buffer.strings, colors: light)
        let canvas = RecordingCanvas()
        let scroll = 2000.0
        let drawn = painter.paint(sheet, palette: palette, frame: frame(sheet, scroll: scroll), on: canvas)
        let gutter = Double(buffer.gutterWidth)
        let height = Double(buffer.laneHeight + buffer.contentHeight)
        let calls = canvas.calls
        XCTAssertEqual(calls[0], .fill(SheetRect(x: 0, y: 0, width: 400, height: height), radius: 0, light.surfaceLow))
        XCTAssertEqual(Array(calls[1...3]), [
            .save, .clip(SheetRect(x: gutter, y: 0, width: 400 - gutter, height: height)),
            .translate((gutter - scroll).rounded(), 0),
        ])
        let left = Float(scroll), right = Float(scroll + 400 - gutter)
        let laneCount = buffer.lane.visibleIndices(left: left, right: right).count
        let contentCount = buffer.content.visibleIndices(left: left, right: right).count
        let gutterCount = try XCTUnwrap(buffer.gutterVariant(at: left)).count
        XCTAssertEqual(drawn, laneCount + contentCount + gutterCount)
        // The lane, then the content one lane lower; the gutter last, clipped to its width.
        let laneShift = calls.firstIndex(of: .translate(0, Double(buffer.laneHeight)))!
        let gutterClip = calls.firstIndex(of: .clip(SheetRect(x: 0, y: 0, width: gutter, height: height)))!
        XCTAssertLessThan(laneShift, gutterClip)
        XCTAssertEqual(calls[gutterClip - 2], .restore)
        XCTAssertEqual(calls[gutterClip - 1], .save)
        XCTAssertEqual(calls[gutterClip + 1], .translate(0, Double(buffer.laneHeight)))
        XCTAssertEqual(calls.last, .restore)
        // The staff gutter's paper is the sheet's surface.
        guard case .fill(_, _, let paper) = calls[gutterClip + 2] else { return XCTFail("\(calls[gutterClip + 2])") }
        XCTAssertEqual(paper, light.surfaceLow)
        XCTAssertEqual(calls.filter { $0 == .save }.count, calls.filter { $0 == .restore }.count)
    }

    func testClefsAndNoteheadsLandWhereTheRendererPlacedThemInTheirInk() async throws {
        let index = try await glyphIndex()
        let painter = SheetPainter(glyphs: index, pixelScale: 1)
        let sheet = try sheet("american_staff")
        for colors in [light, dark] {
            let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: colors)
            let canvas = RecordingCanvas()
            painter.draw(sheet.content, colors: palette.content, palette: palette, left: -.infinity, right: .infinity,
                         on: canvas)
            var expected: [(String, SheetRect, SheetColor?)] = []
            for case .image(let x, let y, let key, let anchor, _) in sheet.buffer.content.ops {
                let parsed = SheetImageKey(key)!
                let size = index.size(of: parsed)!
                let origin = anchor.topLeft(x: Double(x), y: Double(y), width: size.width, height: size.height)
                expected.append((parsed.asset, SheetRect(x: origin.x.rounded(), y: origin.y.rounded(),
                                                          width: size.width, height: size.height),
                                 palette.glyphTint(parsed.tint)))
            }
            XCTAssertEqual(expected.count, 776)
            XCTAssertEqual(canvas.glyphs.count, expected.count)
            for (got, want) in zip(canvas.glyphs, expected) {
                XCTAssertEqual(got.asset, want.0)
                XCTAssertEqual(got.rect, want.1)
                XCTAssertEqual(got.tint, want.2)
            }
            // The last notehead: glyph_notehead_whole:7:22323a at nw (11917.55, 53.59).
            let last = try XCTUnwrap(canvas.glyphs.last)
            XCTAssertEqual(last.asset, "glyph_notehead_whole")
            XCTAssertEqual(last.rect, SheetRect(x: 11918, y: 54, width: 12, height: 7))
            XCTAssertEqual(last.tint, colors.dark ? ChordSheetTheme.themed("#22323a", SheetColor(tk: "#22323a")!, dark)
                                                  : SheetColor(tk: "#22323a"))
        }
        // An untinted clef: black ink as it is in light, the themed ink in dark.
        let gutter = try XCTUnwrap(sheet.gutter(at: 0))
        for (colors, tint) in [(light, nil), (dark, ChordSheetPalette(strings: [], colors: dark).defaultGlyphTint)] {
            let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: colors)
            let canvas = RecordingCanvas()
            painter.draw(gutter, colors: palette.content, palette: palette, left: -.infinity, right: .infinity, on: canvas)
            let clefs = canvas.glyphs.filter { $0.asset.hasPrefix("clef_") }
            XCTAssertEqual(clefs.map(\.asset), ["clef_treble", "clef_bass"])
            XCTAssertTrue(clefs.allSatisfy { $0.tint == tint })
        }
    }

    func testTextIsAnchoredOnItsMeasuredBoxAtTheTkSizeTimesFourThirds() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 3)
        let sheet = try sheet("american_keyboard_z125_h480")
        let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: dark)
        let canvas = RecordingCanvas()
        painter.draw(sheet.content, colors: palette.content, palette: palette, left: -.infinity, right: .infinity,
                     on: canvas)
        var count = 0
        var labels = 0
        for case .text(let x, let y, let text, let anchor, let bold, let size, let fill, let tags) in sheet.buffer.content.ops {
            let got = canvas.texts[count]
            count += 1
            XCTAssertEqual(got.text, text)
            XCTAssertEqual(got.font.size, Double(size) * 4 / 3, accuracy: 1e-9)
            XCTAssertEqual(got.font.bold, bold)
            let box = canvas.measure(text, font: got.font)
            let origin = anchor.topLeft(x: Double(x), y: Double(y), width: box.width, height: box.height)
            // On whole device pixels at 3 px per point.
            XCTAssertEqual(got.x, (origin.x * 3).rounded() / 3, accuracy: 1e-9)
            XCTAssertEqual(got.y, (origin.y * 3).rounded() / 3, accuracy: 1e-9)
            XCTAssertEqual(got.color, fill.flatMap { palette.content[$0] } ?? .black)
            XCTAssertNil(got.clipRight, "only the marker lane clips its labels")
            if tags.contains("note-label") {
                labels += 1
                XCTAssertEqual(anchor, .w)
                // The piano roll's note names: dark ink on the dark theme's lighter bars.
                XCTAssertEqual(got.color, ChordSheetTheme.darkNoteLabel)
            }
        }
        XCTAssertEqual(canvas.texts.count, count)
        XCTAssertGreaterThan(labels, 0)
    }

    func testLaneLabelsThatRunIntoTheNextAreClippedShortOfIt() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 1)
        let sheet = try sheet("american_staff")
        let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: light)
        let canvas = RecordingCanvas()
        painter.draw(sheet.lane, colors: palette.content, palette: palette, left: -.infinity, right: .infinity, on: canvas)
        let clips = try XCTUnwrap(sheet.lane.clipRights)
        var t = 0
        var clipped = 0
        for (i, op) in sheet.buffer.lane.ops.enumerated() {
            guard case .text = op else { continue }
            let got = canvas.texts[t]
            t += 1
            let width = canvas.measure(got.text, font: got.font).width
            if clips[i].isFinite && got.x + width > clips[i] {
                XCTAssertEqual(got.clipRight, clips[i], got.text)
                clipped += 1
            } else {
                XCTAssertNil(got.clipRight, got.text)
            }
        }
        XCTAssertEqual(t, canvas.texts.count)
        XCTAssertGreaterThan(t, 5)
        _ = clipped  // how many depends on the font; the rule is what's checked
    }

    func testThePlayheadIsAnEdgeWhileStoppedAndATintedColumnWhilePlaying() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 1)
        let sheet = try sheet("american_fret")
        let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: light)
        let slot = sheet.buffer.slots[3]
        let h = Double(sheet.buffer.contentHeight)
        let x = Double(slot.x), w = Double(slot.width)

        let stopped = RecordingCanvas()
        painter.paint(sheet, palette: palette, frame: frame(sheet, cursor: 3), on: stopped)
        let edge = RecordingCanvas.Call.fill(SheetRect(x: x, y: 2, width: 3, height: h - 4), radius: 1.5, light.primary)
        XCTAssertEqual(Array(stopped.calls.suffix(2)), [edge, .restore], "on top of the content, no gutter")

        let playing = RecordingCanvas()
        painter.paint(sheet, palette: palette, frame: frame(sheet, current: 3, cursor: 3), on: playing)
        let tint = light.sheetPlaying
        let strong = tint.withAlpha(min(tint.alpha * 4, 1))
        XCTAssertEqual(Array(playing.calls.suffix(4)), [
            .fill(SheetRect(x: x, y: 2, width: w, height: h - 4), radius: 6, tint),
            .fill(SheetRect(x: x + 1, y: 2, width: w - 2, height: 2), radius: 1, strong),
            .fill(SheetRect(x: x + 1, y: h - 4, width: w - 2, height: 2), radius: 1, strong),
            .restore,
        ])
        XCTAssertFalse(playing.calls.contains(edge))
        XCTAssertEqual(strong.argb >> 24, 0x90)  // 0x24 × 4

        // A chord the strip doesn't draw: no mark at all.
        let missing = RecordingCanvas()
        painter.paint(sheet, palette: palette, frame: frame(sheet, current: 10_000, cursor: 10_000), on: missing)
        XCTAssertEqual(missing.drawCalls.count, stopped.drawCalls.count - 1)
    }

    func testThePianoRollsKeyboardSitsOnABedOfItsWhiteKeysInItsOwnPalette() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 2)
        let sheet = try sheet("american_keyboard")
        let gutter = try XCTUnwrap(sheet.gutter(at: 0))
        let bed = try XCTUnwrap(gutter.rectBounds)
        for colors in [light, dark] {
            let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: colors)
            let canvas = RecordingCanvas()
            painter.paint(sheet, palette: palette, frame: frame(sheet), on: canvas)
            let clip = canvas.calls.firstIndex(of: .clip(SheetRect(x: 0, y: 0, width: Double(sheet.buffer.gutterWidth),
                                                                   height: Double(sheet.buffer.laneHeight + sheet.buffer.contentHeight))))!
            let white = colors.dark ? SheetColor(argb: 0xFFC3_C6CF) : SheetColor.white
            XCTAssertEqual(canvas.calls[clip + 2], .fill(bed, radius: 0, white))
            let gutterFills = canvas.calls[(clip + 3)...].compactMap { call -> SheetColor? in
                if case .fill(_, _, let c) = call { return c } else { return nil }
            }
            XCTAssertTrue(gutterFills.contains(colors.dark ? SheetColor(argb: 0xFF17_181B) : SheetColor(argb: 0xFF31_424A)))
            if colors.dark {
                XCTAssertFalse(gutterFills.contains(SheetColor(argb: 0xFF31_424A)),
                               "the dark keyboard's black keys take the app's near-black")
            }
        }
        // The bed covers every key.
        for case .rect(let x, let y, let w, let h, _, _, _, _, _) in gutter.list.ops {
            XCTAssertTrue(Double(x) >= bed.x && Double(x + w) <= bed.maxX + 1e-9
                          && Double(y) >= bed.y && Double(y + h) <= bed.maxY + 1e-9)
        }
    }

    func testOnlyTheVisibleOpsAreDrawn() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 1)
        let sheet = try sheet("american_tab")
        let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: light)
        let narrow = RecordingCanvas()
        let all = RecordingCanvas()
        let drawn = painter.draw(sheet.content, colors: palette.content, palette: palette, left: 2000, right: 2400, on: narrow)
        let every = painter.draw(sheet.content, colors: palette.content, palette: palette, left: -.infinity,
                                 right: .infinity, on: all)
        XCTAssertEqual(drawn, sheet.buffer.content.visibleIndices(left: 2000, right: 2400).count)
        XCTAssertEqual(every, sheet.buffer.content.count)
        XCTAssertLessThan(narrow.drawCalls.count, all.drawCalls.count / 5)
    }

    // -- single ops ------------------------------------------------------------------

    func testEachOpPaintsWhatItsColoursAndWidthsSay() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 1)
        let list = SheetOpList([
            .rect(x: 1, y: 2, w: 3, h: 4, fill: "#ff0000", outline: "#00ff00", width: 2, radius: 0, tags: []),
            .rect(x: 1, y: 2, w: 3, h: 4, fill: nil, outline: "#00ff00", width: 0, radius: 0, tags: []),  // nothing
            .rect(x: 1, y: 2, w: 3, h: 4, fill: "", outline: "#0000ff", width: 1, radius: 2.5, tags: []),
            .oval(x: 5, y: 6, w: 7, h: 8, fill: "#ff0000", outline: nil, width: 1, tags: []),
            .line(fill: nil, width: 1.5, points: [SheetPoint(x: 0, y: 0), SheetPoint(x: 10, y: 0)], tags: []),
            .line(fill: "#ff0000", width: 1, points: [SheetPoint(x: 0, y: 0)], tags: []),  // nothing
            .polygon(fill: "#0000ff", smooth: false, points: [SheetPoint(x: 0, y: 0), SheetPoint(x: 4, y: 0),
                                                             SheetPoint(x: 4, y: 4)], tags: []),
            .text(x: 10, y: 10, text: "Am", anchor: .center, bold: true, size: 9, fill: nil, tags: []),
            .image(x: 0, y: 0, key: "clef_nonsense", anchor: .nw, tags: []),  // nothing
        ])
        let strings = ["#ff0000", "#00ff00", "#0000ff", ""]
        let palette = ChordSheetPalette(strings: strings, colors: light)
        let canvas = RecordingCanvas()
        let drawn = painter.draw(PreparedOps(list), colors: palette.content, palette: palette, left: -100, right: 100,
                                 on: canvas)
        XCTAssertEqual(drawn, list.count)
        let red = SheetColor(argb: 0xFFFF_0000), green = SheetColor(argb: 0xFF00_FF00), blue = SheetColor(argb: 0xFF00_00FF)
        let box = SheetRect(x: 1, y: 2, width: 3, height: 4)
        XCTAssertEqual(canvas.calls, [
            .fill(box, radius: 0, red), .stroke(box, radius: 0, green, width: 2),
            .stroke(box, radius: 2.5, blue, width: 1),
            .fillEllipse(SheetRect(x: 5, y: 6, width: 7, height: 8), red),
            .line([0, 0, 10, 0], .black, width: 1.5),
            .path([.move(x: 0, y: 0), .line(x: 4, y: 0), .line(x: 4, y: 4), .close], blue),
            // 9 pt bold is 12 points; "Am" is 12 × 14.4 in the recording metric, centred on (10, 10).
            .text("Am", SheetPainter.font(size: 9, bold: true), x: 4, y: 3, .black, clipRight: nil),
        ])
    }

    func testASmoothPolygonIsTksQuadraticSplineThroughTheEdgeMidpoints() {
        let square = [SheetPoint(x: 0, y: 0), SheetPoint(x: 4, y: 0), SheetPoint(x: 4, y: 4), SheetPoint(x: 0, y: 4)]
        XCTAssertEqual(SheetPainter.polygonPath(square, smooth: true), [
            .move(x: 0, y: 2),
            .quad(cx: 0, cy: 0, x: 2, y: 0),
            .quad(cx: 4, cy: 0, x: 4, y: 2),
            .quad(cx: 4, cy: 4, x: 2, y: 4),
            .quad(cx: 0, cy: 4, x: 0, y: 2),
            .close,
        ])
        // Two points can't be smooth; one isn't a polygon.
        XCTAssertEqual(SheetPainter.polygonPath(Array(square.prefix(2)), smooth: true),
                       [.move(x: 0, y: 0), .line(x: 4, y: 0), .close])
        XCTAssertEqual(SheetPainter.polygonPath(Array(square.prefix(1)), smooth: true), [])
    }

    func testEveryFixturePaintsInBothThemesWithBalancedState() async throws {
        let painter = SheetPainter(glyphs: try await glyphIndex(), pixelScale: 3)
        for name in ["american_keyboard", "american_staff", "american_fret", "american_tab", "american_staff_z1728",
                     "multikey_staff", "multikey_tab_z0833", "american_keyboard_z125_h480"] {
            let sheet = try sheet(name)
            for colors in [light, dark] {
                let palette = ChordSheetPalette(strings: sheet.buffer.strings, colors: colors)
                for scroll in [0.0, 700, Double(sheet.buffer.contentWidth) - 200] {
                    let canvas = RecordingCanvas()
                    let drawn = painter.paint(sheet, palette: palette, frame: frame(sheet, scroll: scroll, cursor: 2),
                                              on: canvas)
                    XCTAssertGreaterThan(drawn, 0, name)
                    var depth = 0
                    for call in canvas.calls {
                        if call == .save { depth += 1 }
                        if call == .restore { depth -= 1 }
                        XCTAssertGreaterThanOrEqual(depth, 0, name)
                    }
                    XCTAssertEqual(depth, 0, name)
                    // Every colour drawn is a themed buffer colour or a theme token.
                    for call in canvas.drawCalls {
                        if case .fill(_, _, let c) = call, colors.dark {
                            XCTAssertNotEqual(c, SheetColor(tk: "#fbfbf8"), "\(name): the strip's paper unthemed")
                        }
                    }
                }
            }
        }
    }
}

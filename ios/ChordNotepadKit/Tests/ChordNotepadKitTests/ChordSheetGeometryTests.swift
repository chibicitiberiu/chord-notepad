import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's ChordSheetGeometryTest, case for case, on the same fixtures.
final class ChordSheetGeometryTests: XCTestCase {
    private func buffer(_ name: String) throws -> SheetBuffer {
        try SheetBuffer.decode(try SheetBufferTests.bytes(name))
    }

    // -- anchors -------------------------------------------------------------------

    func testAnchorsPlaceTheBoxLikeTk() {
        func at(_ anchor: SheetAnchor) -> [Double] {
            let p = anchor.topLeft(x: 100, y: 50, width: 40, height: 10)
            return [p.x, p.y]
        }
        XCTAssertEqual(at(.nw), [100, 50])
        XCTAssertEqual(at(.n), [80, 50])
        XCTAssertEqual(at(.ne), [60, 50])
        XCTAssertEqual(at(.w), [100, 45])
        XCTAssertEqual(at(.center), [80, 45])
        XCTAssertEqual(at(.e), [60, 45])
        XCTAssertEqual(at(.sw), [100, 40])
        XCTAssertEqual(at(.s), [80, 40])
        XCTAssertEqual(at(.se), [60, 40])
    }

    func testAnchorCodesFollowTheFormatsOrder() {
        XCTAssertEqual(SheetAnchor.allCases.map(\.rawValue), Array(0...8))
        XCTAssertEqual(SheetAnchor.allCases, [.nw, .n, .ne, .w, .center, .e, .sw, .s, .se])
    }

    // -- hit-testing ---------------------------------------------------------------

    func testATapInsideASlotAuditionsThatChordEdgesIncluded() throws {
        let staff = try buffer("american_staff")
        let slot = staff.slots[10]
        XCTAssertEqual(staff.slot(at: slot.x + slot.width / 2)?.chordIndex, 10)
        XCTAssertEqual(staff.slot(at: slot.x + 0.01), slot)
        XCTAssertEqual(staff.slot(at: slot.x + slot.width), slot)
        // A shared edge goes to the earlier slot, as on the desktop (first match).
        XCTAssertEqual(staff.slots[9].x + staff.slots[9].width, slot.x)
        XCTAssertEqual(staff.slot(at: slot.x), staff.slots[9])
        XCTAssertNil(staff.slot(at: -1))
        XCTAssertNil(staff.slot(at: staff.contentWidth + 100))
        XCTAssertEqual(staff.slot(forChord: 42), staff.slots[42])
        XCTAssertNil(staff.slot(forChord: 10_000))
    }

    // -- gutter --------------------------------------------------------------------

    func testTheGutterVariantIsTheLastRunStartingStrictlyBeforeTheScroll() throws {
        let multiKey = try buffer("multikey_staff")
        let runs = multiKey.gutterRuns
        // C, G, Eb, C, then C on the outro's section band, to the strip's end.
        XCTAssertEqual(runs.count, 6)
        XCTAssertEqual(runs[0].startX, -.infinity)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: 0), 0)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: runs[1].startX), 0)  // strict <
        XCTAssertEqual(multiKey.gutterVariantIndex(at: runs[1].startX + 0.01), 1)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: runs[2].startX + 1), 2)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: runs[3].startX + 1), 0)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: runs[4].startX + 1), 3)
        XCTAssertEqual(multiKey.gutterVariantIndex(at: 1e9), 0)
        XCTAssertEqual(multiKey.gutterVariant(at: runs[2].startX + 1), multiKey.gutterVariants[2])
        // The prepared sheet picks the same variant.
        let prepared = PreparedSheet(multiKey)
        XCTAssertEqual(prepared.gutter(at: Double(runs[2].startX) + 1)?.list, multiKey.gutterVariants[2])
    }

    func testTheStaffGutterTakesTheSectionBandAtItsEdge() throws {
        let staff = try buffer("american_staff")
        func paper(_ scroll: Float) -> String? {
            guard case .rect(_, _, _, _, let fill, _, _, _, _)? = staff.gutterVariant(at: scroll)?.ops.first else {
                return nil
            }
            return fill
        }
        let runs = staff.gutterRuns
        XCTAssertEqual(paper(0), "#fbfbf8")
        XCTAssertEqual(paper(runs[1].startX + 1), "#f6f6f2")
        XCTAssertEqual(paper(runs[2].startX + 1), "#fbfbf8")
    }

    func testViewsWithoutAGutterHaveNoVariant() throws {
        let fret = try buffer("american_fret")
        XCTAssertEqual(fret.gutterWidth, 0)
        XCTAssertNil(fret.gutterVariant(at: 0))
        XCTAssertNil(PreparedSheet(fret).gutter(at: 0))
        // One key: the plain gutter before the first band and between bands.
        let staff = try buffer("american_staff")
        XCTAssertEqual(staff.gutterVariantIndex(at: -5), 0)
        XCTAssertEqual(staff.gutterVariantIndex(at: 5000), 0)
    }

    // -- culling -------------------------------------------------------------------

    func testCullingKeepsEveryShapeThatReachesTheViewportAndFewOthers() throws {
        for name in ["american_keyboard", "american_staff", "american_fret", "american_tab"] {
            let buffer = try buffer(name)
            let left: Float = 2000
            let right: Float = 2400
            let visible = Set(buffer.content.visibleIndices(left: left, right: right))
            for (i, op) in buffer.content.ops.enumerated() {
                guard let exact = exactExtent(op) else { continue }
                if exact.upperBound >= left && exact.lowerBound <= right {
                    XCTAssertTrue(visible.contains(i), "\(name) op \(i) (\(op)) culled")
                }
            }
            // A 400 pt window of a ~12,000 pt strip draws a small fraction
            // (full-width ops such as the staff lines always qualify).
            XCTAssertLessThan(visible.count, buffer.content.count / 5,
                              "\(name) drew \(visible.count)/\(buffer.content.count)")
        }
    }

    func testTextAndImagesAreKeptWhileAnyOfThemCouldShow() {
        let list = SheetOpList([
            .text(x: 100, y: 0, text: "Cmaj7", anchor: .e, bold: false, size: 8, fill: "#000000", tags: []),
            .image(x: 500, y: 0, key: "clef_treble:96", anchor: .nw, tags: []),
        ])
        // Anchored east: the text paints left of x.
        XCTAssertTrue(list.intersects(0, left: 70, right: 80))
        XCTAssertTrue(list.intersects(1, left: 560, right: 570))  // the treble clef is 37 pt wide at 96
        XCTAssertFalse(list.intersects(0, left: 300, right: 400))
    }

    private func exactExtent(_ op: SheetOp) -> ClosedRange<Float>? {
        switch op {
        case .rect(let x, _, let w, _, _, _, _, _, _), .oval(let x, _, let w, _, _, _, _, _):
            return x...(x + w)
        case .line(_, _, let points, _), .polygon(_, _, let points, _):
            guard let lo = points.map(\.x).min(), let hi = points.map(\.x).max() else { return nil }
            return lo...hi
        case .text, .image:
            return nil
        }
    }

    // -- lane labels ---------------------------------------------------------------

    func testLaneLabelsClipShortOfTheNextLabel() throws {
        let lane = try buffer("american_staff").lane
        let clips = lane.laneClipRights()
        XCTAssertEqual(clips.count, lane.count)
        var xs: [Double] = []
        for case .text(let x, _, _, _, _, _, _, _) in lane.ops { xs.append(Double(x)) }
        xs.sort()
        XCTAssertGreaterThan(xs.count, 5)
        for (i, op) in lane.ops.enumerated() {
            if case .text(let x, _, _, _, _, _, _, _) = op {
                let next = xs.first { $0 > Double(x) + 0.5 }
                XCTAssertEqual(clips[i], next.map { $0 - 2 } ?? .infinity)
            } else {
                XCTAssertEqual(clips[i], .infinity)
            }
        }
        XCTAssertEqual(PreparedSheet(try buffer("american_staff")).lane.clipRights, clips)
    }

    // -- auto-scroll ---------------------------------------------------------------

    func testThePlayheadInsideTheComfortableBandDoesNotScroll() {
        XCTAssertNil(ChordSheetScroll.target(playheadX: 150, viewportWidth: 400, currentScroll: 0, contentWidth: 5000))
        XCTAssertNil(ChordSheetScroll.target(playheadX: 100, viewportWidth: 400, currentScroll: 0, contentWidth: 5000))  // exactly 25 %
        XCTAssertNil(ChordSheetScroll.target(playheadX: 280, viewportWidth: 400, currentScroll: 0, contentWidth: 5000))  // exactly 70 %
    }

    func testPast70PercentOrBehind25PercentItSnapsTo25Percent() {
        XCTAssertEqual(ChordSheetScroll.target(playheadX: 300, viewportWidth: 400, currentScroll: 0, contentWidth: 5000), 200)
        XCTAssertEqual(ChordSheetScroll.target(playheadX: 1000, viewportWidth: 400, currentScroll: 1200, contentWidth: 5000), 900)
        // Clamped to the content's ends.
        XCTAssertEqual(ChordSheetScroll.target(playheadX: 50, viewportWidth: 400, currentScroll: 300, contentWidth: 5000), 0)
        XCTAssertEqual(ChordSheetScroll.target(playheadX: 4990, viewportWidth: 400, currentScroll: 3000, contentWidth: 5000), 4600)
        XCTAssertNil(ChordSheetScroll.target(playheadX: 300, viewportWidth: 0, currentScroll: 0, contentWidth: 5000))
        // Within half a point of where it is: nothing to do.
        XCTAssertNil(ChordSheetScroll.target(playheadX: 4990, viewportWidth: 400, currentScroll: 4600, contentWidth: 5000))
    }

    func testAChordIsFollowedByItsSlotsCentre() throws {
        let staff = try buffer("american_staff")
        let slot = staff.slots[40]
        let centre = Double(slot.x) + Double(slot.width) / 2
        XCTAssertEqual(ChordSheetScroll.target(forChord: 40, in: staff, viewportWidth: 400, currentScroll: 0),
                       centre - 100)
        XCTAssertNil(ChordSheetScroll.target(forChord: 0, in: staff, viewportWidth: 400, currentScroll: 0))
        XCTAssertNil(ChordSheetScroll.target(forChord: nil, in: staff, viewportWidth: 400, currentScroll: 0))
        XCTAssertNil(ChordSheetScroll.target(forChord: 10_000, in: staff, viewportWidth: 400, currentScroll: 0))
    }

    // -- zoom ----------------------------------------------------------------------

    func testAPinchMapsToTheNearestNumberOfDesktopZoomSteps() {
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 1.05, currentZoom: 1), 0)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 1.2, currentZoom: 1), 1)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 1.5, currentZoom: 1), 2)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 0.8, currentZoom: 1), -1)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 0.55, currentZoom: 1), -3)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 0, currentZoom: 1), 0)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: .nan, currentZoom: 1), 0)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: .infinity, currentZoom: 1), 0)
    }

    func testZoomStepsStopAtTheDesktopBounds() {
        // 1.0 → 2.5 is 5.03 steps of 1.2: 6 steps, the last clamped to 2.5.
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 10, currentZoom: 1), 6)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 0.01, currentZoom: 1), -4)  // 1.0 → 0.5 is 3.8 steps
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 2, currentZoom: 2.5), 0)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: 0.5, currentZoom: 0.5), 0)
        // Android computes the scale in Float: 1.2f^3.
        XCTAssertEqual(ChordSheetZoom.steps(forScale: Double(Float(1.2) * Float(1.2) * Float(1.2)), currentZoom: 2.4), 1)
        XCTAssertEqual(ChordSheetZoom.steps(forScale: pow(1.2, 3), currentZoom: 2.4), 1)
    }

    func testAPinchDoesNothingOnAViewThatDoesNotZoom() {
        XCTAssertEqual(ChordSheetZoom.pinchSteps(zoomSupported: false, scale: 2, currentZoom: 1), 0)
        XCTAssertEqual(ChordSheetZoom.pinchSteps(zoomSupported: true, scale: 1.5, currentZoom: 1), 2)
    }

    func testAZoomKeepsTheMusicUnderTheFocusInPlace() {
        // Content x 600 at viewport x 100 stays there when the strip doubles.
        XCTAssertEqual(ChordSheetScroll.rescale(500, anchorX: 100, oldWidth: 5000, newWidth: 10000, viewportWidth: 400), 1100)
        XCTAssertEqual(ChordSheetScroll.rescale(10, anchorX: 0, oldWidth: 5000, newWidth: 2500, viewportWidth: 400), 5)
        XCTAssertEqual(ChordSheetScroll.rescale(10, anchorX: 300, oldWidth: 5000, newWidth: 2500, viewportWidth: 400), 0)  // clamped to the start
        XCTAssertEqual(ChordSheetScroll.rescale(4600, anchorX: 200, oldWidth: 5000, newWidth: 2500, viewportWidth: 400), 2100)  // clamped to the end
        XCTAssertEqual(ChordSheetScroll.rescale(4600, anchorX: 200, oldWidth: 0, newWidth: 2500, viewportWidth: 400), 2100)
    }

    func testANewBufferKeepsTheSameMusicInView() throws {
        let staff = try buffer("american_staff")
        let zoomed = try buffer("american_staff_z1728")
        let keyboard = try buffer("american_keyboard")
        let w = Double(staff.contentWidth), zw = Double(zoomed.contentWidth), kw = Double(keyboard.contentWidth)
        // A zoom: the content under the focus stays put.
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(zoomed, previous: staff, scroll: 1000, focusX: 100, viewportWidth: 400),
                       (1100 * zw / w) - 100, accuracy: 1e-6)
        // No pinch: about the viewport's middle.
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(zoomed, previous: staff, scroll: 1000, focusX: nil, viewportWidth: 400),
                       (1200 * zw / w) - 200, accuracy: 1e-6)
        // Another view: the same fraction of the song.
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(keyboard, previous: staff, scroll: 1000, focusX: nil, viewportWidth: 400),
                       1000 / w * kw, accuracy: 1e-6)
        // An edit or a new height: the offset stays, clamped to the new end.
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(staff, previous: staff, scroll: 1000, focusX: nil, viewportWidth: 400), 1000)
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(staff, previous: nil, scroll: 1e6, focusX: nil, viewportWidth: 400), w - 400)
        XCTAssertEqual(ChordSheetScroll.afterNewBuffer(staff, previous: staff, scroll: -5, focusX: nil, viewportWidth: 400), 0)
    }

    // -- colours and requests -----------------------------------------------------

    func testTkColoursParse() {
        XCTAssertEqual(SheetColor(tk: "#fbfbf8")?.argb, 0xFFFB_FBF8)
        XCTAssertEqual(SheetColor(tk: "#f80")?.argb, 0xFFFF_8800)
        XCTAssertEqual(SheetColor(tk: "#FBFBF8")?.argb, 0xFFFB_FBF8)
        XCTAssertEqual(SheetColor(tk: "black")?.argb, 0xFF00_0000)
        XCTAssertEqual(SheetColor(tk: "Grey")?.argb, 0xFFBE_BEBE)
        XCTAssertNil(SheetColor(tk: ""))
        XCTAssertNil(SheetColor(tk: nil))
        XCTAssertNil(SheetColor(tk: "#12345"))
        XCTAssertNil(SheetColor(tk: "#12345g"))
        XCTAssertNil(SheetColor(tk: "chartreuse"))
    }

    func testARequestFollowsRevisionViewZoomAndHeightNotThePlayhead() {
        let state = ChordSheetState(activeView: "staff", currentIndex: 3, cursorIndex: nil, disabledReason: nil,
                                    height: 200, songRevision: 7, views: [], visible: true, zoom: 1,
                                    zoomSupported: true)
        let request = SheetRequest.of(state, height: 130)
        XCTAssertEqual(request, SheetRequest(songRevision: 7, viewId: "staff", zoom: 1, height: 130))
        var moved = state
        moved.currentIndex = 9
        moved.cursorIndex = 4
        XCTAssertEqual(SheetRequest.of(moved, height: 130), request)
        var hidden = state
        hidden.visible = false
        XCTAssertNil(SheetRequest.of(hidden, height: 130))
        XCTAssertNil(SheetRequest.of(state, height: 0))
        XCTAssertNil(SheetRequest.of(nil, height: 130))
    }
}

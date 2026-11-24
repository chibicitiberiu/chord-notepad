import Foundation
import XCTest

@testable import ChordNotepadKit

/// Decodes the buffers android/tools/gen_chord_sheet_fixtures.py packed with
/// `chord_sheet.pack` and compares them with what Python's reference decoder
/// read from the same bytes (Android's ChordSheetBufferTest, case for case).
/// The fixtures stay in android/app/src/test/resources/chord_sheet/: SwiftPM
/// resources can't live outside the package, so they are read by path.
final class SheetBufferTests: XCTestCase {
    private let fixtures = [
        "american_keyboard", "american_staff", "american_fret", "american_tab",
        "american_staff_z1728", "multikey_staff", "multikey_tab_z0833",
        "american_keyboard_z125_h480",
    ]

    static let fixtureDir = TestPython.repo.appendingPathComponent("android/app/src/test/resources/chord_sheet")

    static func bytes(_ name: String) throws -> Data {
        try Data(contentsOf: fixtureDir.appendingPathComponent("\(name).bin"))
    }

    static func expected(_ name: String) throws -> [String: Any] {
        let data = try Data(contentsOf: fixtureDir.appendingPathComponent("\(name).json"))
        return try XCTUnwrap(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    func testEveryFixtureDecodesToWhatPythonsUnpackRead() throws {
        for name in fixtures {
            let buffer = try SheetBuffer.decode(try Self.bytes(name))
            let e = try Self.expected(name)
            func f(_ key: String) -> Double { (e[key] as? NSNumber)?.doubleValue ?? .nan }
            XCTAssertEqual(e["view_id"] as? String, buffer.viewId, name)
            XCTAssertEqual(f("zoom"), Double(buffer.zoom), accuracy: 1e-9, name)
            XCTAssertEqual(f("height"), Double(buffer.height), accuracy: 1e-9, name)
            XCTAssertEqual(f("content_width"), Double(buffer.contentWidth), accuracy: 1e-9, name)
            XCTAssertEqual(f("content_height"), Double(buffer.contentHeight), accuracy: 1e-9, name)
            XCTAssertEqual(f("gutter_width"), Double(buffer.gutterWidth), accuracy: 1e-9, name)
            XCTAssertEqual(f("lane_height"), Double(buffer.laneHeight), accuracy: 1e-9, name)
            XCTAssertEqual(e["background"] as? String, buffer.background, name)
            XCTAssertEqual(e["highlight"] as? String, buffer.highlight, name)
            XCTAssertEqual(e["string_count"] as? Int, buffer.strings.count, name)
            XCTAssertEqual(e["slot_count"] as? Int, buffer.slots.count, name)
            try assertSlot(e["first_slot"], buffer.slots.first, name)
            try assertSlot(e["last_slot"], buffer.slots.last, name)
            XCTAssertEqual(f("slot_x_sum"), buffer.slots.reduce(0) { $0 + Double($1.x) }, accuracy: 1e-3, name)

            try assertList("\(name) content", e["content"], buffer.content)
            try assertList("\(name) lane", e["lane"], buffer.lane)
            let variants = try XCTUnwrap(e["gutter_variants"] as? [Any])
            XCTAssertEqual(variants.count, buffer.gutterVariants.count, name)
            for (i, variant) in variants.enumerated() {
                try assertList("\(name) gutter \(i)", variant, buffer.gutterVariants[i])
            }
            let runs = try XCTUnwrap(e["gutter_runs"] as? [[Any]])
            XCTAssertEqual(runs.count, buffer.gutterRuns.count, name)
            for (i, run) in runs.enumerated() {
                let start = run[0] is NSNull ? -Float.infinity : Float((run[0] as! NSNumber).doubleValue)
                XCTAssertEqual(SheetGutterRun(startX: start, variant: run[1] as! Int), buffer.gutterRuns[i], name)
            }
        }
    }

    func testATallPianoRollDecodesRoundedBarsAndTheNamesInThem() throws {
        let buffer = try SheetBuffer.decode(try Self.bytes("american_keyboard_z125_h480"))
        var bars: [(radius: Float, outline: String?)] = []
        var names: [(anchor: SheetAnchor, fill: String?)] = []
        for op in buffer.content.ops {
            switch op {
            case .rect(_, _, _, _, _, let outline, _, let radius, let tags) where tags.contains(where: { $0.hasPrefix("note:") }):
                bars.append((radius, outline))
            case .text(_, _, _, let anchor, _, _, let fill, let tags) where tags.contains("note-label"):
                names.append((anchor, fill))
            default:
                break
            }
        }
        XCTAssertTrue(!bars.isEmpty && bars.allSatisfy { $0.radius > 0 && $0.outline == nil })
        XCTAssertTrue(!names.isEmpty && names.allSatisfy { $0.anchor == .w && $0.fill == "#fdfdff" })
        XCTAssertEqual(buffer.gutterVariants.count, 1)
        let keys = buffer.gutterVariants[0].ops.compactMap { op -> (x: Float, radius: Float)? in
            if case .rect(let x, _, _, _, _, _, _, let radius, _) = op { return (x, radius) }
            return nil
        }
        XCTAssertTrue(keys.contains { $0.radius > 0 && $0.x < 0 })
    }

    func testThe133ChordSampleHasOneSlotPerChordInSongOrder() throws {
        let buffer = try SheetBuffer.decode(try Self.bytes("american_staff"))
        XCTAssertEqual(133, buffer.slots.count)
        XCTAssertEqual(Array(0..<133), buffer.slots.map(\.chordIndex))
        XCTAssertTrue(zip(buffer.slots, buffer.slots.dropFirst()).allSatisfy { $0.x < $1.x })
    }

    func testANewerFormatVersionIsRejectedWithoutGuessing() throws {
        var data = [UInt8](try Self.bytes("multikey_staff"))
        let newer = SheetBuffer.formatVersion + 1
        data[4] = UInt8(newer & 0xFF)
        data[5] = UInt8(newer >> 8)
        XCTAssertThrowsError(try SheetBuffer.decode(Data(data))) { error in
            XCTAssertEqual(error as? SheetBufferError, .unsupportedVersion(newer))
        }
    }

    func testMalformedBuffersThrowMalformed() throws {
        let good = [UInt8](try Self.bytes("multikey_staff"))
        var badMagic = good
        badMagic[0] = UInt8(ascii: "X")
        let truncated = Array(good.dropLast(3))
        let trailing = good + [0]
        // The first content op's opcode: header, strings, slots, then u32 count + u32 length.
        var unknownOpcode = good
        unknownOpcode[firstOpOffset(good)] = 99
        let cases: [(String, [UInt8])] = [
            ("magic", badMagic), ("truncated", truncated), ("trailing", trailing),
            ("empty", []), ("opcode", unknownOpcode),
        ]
        for (label, data) in cases {
            XCTAssertThrowsError(try SheetBuffer.decode(Data(data)), label) { error in
                guard case .malformed? = error as? SheetBufferError else {
                    return XCTFail("\(label): \(error)")
                }
            }
        }
    }

    func testEveryTruncationThrowsInsteadOfTrapping() throws {
        let good = [UInt8](try Self.bytes("multikey_staff"))
        for length in stride(from: 0, to: good.count, by: 7) {
            XCTAssertThrowsError(try SheetBuffer.decode(Data(good.prefix(length))), "length \(length)")
        }
    }

    func testAHugeCountIsMalformedNotAnAllocation() throws {
        var data = [UInt8](try Self.bytes("multikey_staff"))
        data[40...43] = [0xFF, 0xFF, 0xFF, 0x7F]  // string_count
        XCTAssertThrowsError(try SheetBuffer.decode(Data(data)))
    }

    func testALaterMinorVersionsLongerHeaderIsSkipped() throws {
        let good = [UInt8](try Self.bytes("multikey_staff"))
        let headerSize = 48
        var longer = Array(good[0..<headerSize]) + [UInt8](repeating: 0, count: 8) + Array(good[headerSize...])
        longer[6] = UInt8(headerSize + 8)
        longer[7] = 0
        let buffer = try SheetBuffer.decode(Data(longer))
        XCTAssertEqual(try SheetBuffer.decode(Data(good)).content.count, buffer.content.count)
    }

    func testADataSliceDecodesLikeTheWholeBuffer() throws {
        let good = try Self.bytes("multikey_tab_z0833")
        let padded = Data([1, 2, 3]) + good
        XCTAssertEqual(try SheetBuffer.decode(padded.dropFirst(3)), try SheetBuffer.decode(good))
    }

    func testImageKeysParseLikeClefAssetsParseImageKey() {
        XCTAssertEqual(SheetImageKey(asset: "clef_treble", height: 96, tint: nil), SheetImageKey("clef_treble:96"))
        XCTAssertEqual(SheetImageKey(asset: "glyph_accidental_sharp", height: 40, tint: "#3a5a8a"),
                       SheetImageKey("glyph_accidental_sharp:40:3A5A8A"))
        XCTAssertNil(SheetImageKey("clef_treble:96:3a5a8a"))
        XCTAssertNil(SheetImageKey("clef_treble"))
        XCTAssertNil(SheetImageKey("glyph_x:0"))
        XCTAssertNil(SheetImageKey("glyph_x:12:zzzzzz"))
        XCTAssertNil(SheetImageKey("other:12"))
    }

    func testTheGutterVariantIsTheLastRunStartingBeforeTheScrollOffset() throws {
        let buffer = try SheetBuffer.decode(try Self.bytes("multikey_staff"))
        XCTAssertGreaterThan(buffer.gutterRuns.count, 1)
        XCTAssertEqual(buffer.gutterVariantIndex(at: 0), buffer.gutterRuns[0].variant)
        let second = buffer.gutterRuns[1]
        XCTAssertEqual(buffer.gutterVariantIndex(at: second.startX), buffer.gutterRuns[0].variant)
        XCTAssertEqual(buffer.gutterVariantIndex(at: second.startX + 0.5), second.variant)
        let slot = try XCTUnwrap(buffer.slots.dropFirst(3).first)
        XCTAssertEqual(buffer.slot(at: slot.x + slot.width / 2), slot)
        XCTAssertEqual(buffer.slot(forChord: slot.chordIndex), slot)
        XCTAssertFalse(buffer.content.visibleIndices(left: slot.x, right: slot.x + slot.width).isEmpty)
    }

    // MARK: - helpers

    private func firstOpOffset(_ data: [UInt8]) -> Int {
        func u16(_ at: Int) -> Int { Int(data[at]) | Int(data[at + 1]) << 8 }
        func u32(_ at: Int) -> Int { u16(at) | u16(at + 2) << 16 }
        var pos = u16(6)
        for _ in 0..<u32(40) { pos += 2 + u16(pos) }
        pos += 12 * u32(44)
        return pos + 8
    }

    private func assertSlot(_ expected: Any?, _ slot: SheetSlot?, _ label: String) throws {
        let e = try XCTUnwrap(expected as? [NSNumber], label)
        let slot = try XCTUnwrap(slot, label)
        XCTAssertEqual(e[0].intValue, slot.chordIndex, label)
        XCTAssertEqual(e[1].doubleValue, Double(slot.x), accuracy: 1e-9, label)
        XCTAssertEqual(e[2].doubleValue, Double(slot.width), accuracy: 1e-9, label)
    }

    private func assertList(_ label: String, _ expected: Any?, _ list: SheetOpList) throws {
        let e = try XCTUnwrap(expected as? [String: Any], label)
        XCTAssertEqual(e["count"] as? Int, list.count, label)
        var histogram: [String: Int] = [:]
        for op in list.ops { histogram[op.name, default: 0] += 1 }
        XCTAssertEqual(e["histogram"] as? [String: Int], histogram, label)
        XCTAssertEqual(e["tag_count"] as? Int, list.ops.reduce(0) { $0 + $1.tags.count }, label)
        let sum = try XCTUnwrap(e["coord_sum"] as? NSNumber).doubleValue
        XCTAssertEqual(sum, list.ops.reduce(0) { $0 + coordSum($1) }, accuracy: 1e-6 * max(1, abs(sum)), label)
        if let first = list.ops.first, let last = list.ops.last {
            try assertOp(label, e["first"], first)
            try assertOp(label, e["last"], last)
        }
    }

    private func assertOp(_ label: String, _ expected: Any?, _ op: SheetOp) throws {
        let e = try XCTUnwrap(expected as? [String: Any], label)
        XCTAssertEqual(e["op"] as? String, op.name, label)
        XCTAssertEqual(e["tags"] as? [String], op.tags, label)
        // The values are float32: compare as Float (Linux Foundation's JSONSerialization
        // can read a double one ulp off, which rounds to the same Float).
        func d(_ key: String) -> Float { Float((e[key] as? NSNumber)?.doubleValue ?? .nan) }
        func s(_ key: String) -> String? { e[key] as? String }
        func floats(_ values: [Float]) -> [Float] { values }
        func points() -> [Float] {
            ((e["points"] as? [[NSNumber]]) ?? []).flatMap { $0.map(\.floatValue) }
        }
        switch op {
        case .rect(let x, let y, let w, let h, let fill, let outline, let width, let radius, _):
            XCTAssertEqual([d("x"), d("y"), d("w"), d("h"), d("width"), d("radius")],
                           floats([x, y, w, h, width, radius]), label)
            XCTAssertEqual([s("fill"), s("outline")], [fill, outline], label)
        case .oval(let x, let y, let w, let h, let fill, let outline, let width, _):
            XCTAssertEqual([d("x"), d("y"), d("w"), d("h"), d("width")], floats([x, y, w, h, width]), label)
            XCTAssertEqual([s("fill"), s("outline")], [fill, outline], label)
        case .line(let fill, let width, let pts, _):
            XCTAssertEqual(s("fill"), fill, label)
            XCTAssertEqual(d("width"), width, label)
            XCTAssertEqual(points(), pts.flatMap { [$0.x, $0.y] }, label)
        case .polygon(let fill, let smooth, let pts, _):
            XCTAssertEqual(s("fill"), fill, label)
            XCTAssertEqual(e["smooth"] as? Bool, smooth, label)
            XCTAssertEqual(points(), pts.flatMap { [$0.x, $0.y] }, label)
        case .text(let x, let y, let text, let anchor, let bold, let size, let fill, _):
            XCTAssertEqual([d("x"), d("y"), d("size")], floats([x, y, size]), label)
            XCTAssertEqual(s("text"), text, label)
            XCTAssertEqual(s("anchor"), "\(anchor)", label)
            XCTAssertEqual(e["bold"] as? Bool, bold, label)
            XCTAssertEqual(s("fill"), fill, label)
        case .image(let x, let y, let key, let anchor, _):
            XCTAssertEqual([d("x"), d("y")], floats([x, y]), label)
            XCTAssertEqual(s("key"), key, label)
            XCTAssertEqual(s("anchor"), "\(anchor)", label)
        }
    }

    private func coordSum(_ op: SheetOp) -> Double {
        switch op {
        case .rect(let x, let y, let w, let h, _, _, let width, let radius, _):
            return Double(x + y + w + h) + Double(width) + Double(radius)
        case .oval(let x, let y, let w, let h, _, _, let width, _):
            return Double(x + y + w + h) + Double(width)
        case .line(_, let width, let points, _):
            return Double(width) + points.reduce(0) { $0 + Double($1.x) + Double($1.y) }
        case .polygon(_, _, let points, _):
            return points.reduce(0) { $0 + Double($1.x) + Double($1.y) }
        case .text(let x, let y, _, _, _, let size, _, _):
            return Double(x) + Double(y) + Double(size)
        case .image(let x, let y, _, _, _):
            return Double(x) + Double(y)
        }
    }
}

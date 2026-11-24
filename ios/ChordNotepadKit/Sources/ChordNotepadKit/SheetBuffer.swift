import Foundation

// Decoder for the chord sheet op buffer, format version 2 (docs/ANDROID.md,
// "Chord sheet op buffer"; the Python side is core/chordnotepad/chord_sheet/pack.py,
// the Kotlin one ui/chordsheet/ChordSheetBuffer.kt). Values only: drawing them
// is the app's business (CoreGraphics), so this runs and is tested on Linux.

/// Tk text/image anchors, in their one-byte code order. `fx`/`fy` place the box.
public enum SheetAnchor: Int, Sendable, CaseIterable {
    case nw, n, ne, w, center, e, sw, s, se

    /// The anchor's x as a fraction of the box width (0, ½, 1).
    public var fx: Double {
        switch self {
        case .nw, .w, .sw: return 0
        case .n, .center, .s: return 0.5
        case .ne, .e, .se: return 1
        }
    }

    /// The anchor's y as a fraction of the box height (0, ½, 1).
    public var fy: Double {
        switch self {
        case .nw, .n, .ne: return 0
        case .w, .center, .e: return 0.5
        case .sw, .s, .se: return 1
        }
    }
}

/// A point in content coordinates.
public struct SheetPoint: Sendable, Equatable {
    public var x: Float
    public var y: Float
}

/// One draw op, in points (1 Tk px = 1 pt). Colours are Tk colour strings
/// (`#rrggbb`); nil means none.
public enum SheetOp: Sendable, Equatable {
    /// A rectangle; fill and outline may each be absent. The outline is centred
    /// on the edge. `radius` rounds the corners (0 is square).
    case rect(x: Float, y: Float, w: Float, h: Float, fill: String?, outline: String?,
              width: Float, radius: Float, tags: [String])
    /// The ellipse inscribed in the box.
    case oval(x: Float, y: Float, w: Float, h: Float, fill: String?, outline: String?,
              width: Float, tags: [String])
    /// A polyline.
    case line(fill: String?, width: Float, points: [SheetPoint], tags: [String])
    /// A filled polygon; `smooth` means Tk's quadratic B-spline.
    case polygon(fill: String?, smooth: Bool, points: [SheetPoint], tags: [String])
    /// Single-line text; `size` in Tk points (on screen × 4/3), `anchor` places
    /// its box at (`x`, `y`).
    case text(x: Float, y: Float, text: String, anchor: SheetAnchor, bold: Bool, size: Float,
              fill: String?, tags: [String])
    /// A clef/glyph image by key (`clef_treble:96`, `glyph_<name>:<h>[:<rrggbb>]`).
    case image(x: Float, y: Float, key: String, anchor: SheetAnchor, tags: [String])

    /// The renderer's tags (`slot:<i>`, `marker-lane`, ...).
    public var tags: [String] {
        switch self {
        case .rect(_, _, _, _, _, _, _, _, let tags), .oval(_, _, _, _, _, _, _, let tags),
             .line(_, _, _, let tags), .polygon(_, _, _, let tags),
             .text(_, _, _, _, _, _, _, let tags), .image(_, _, _, _, let tags):
            return tags
        }
    }

    /// The op's name as the Python side calls it (`rect`, `oval`, ...).
    public var name: String {
        switch self {
        case .rect: return "rect"
        case .oval: return "oval"
        case .line: return "line"
        case .polygon: return "polygon"
        case .text: return "text"
        case .image: return "image"
        }
    }

    /// The x range the op can paint: exact for shapes (plus half the stroke),
    /// generous for text and images, whose measured size isn't known here.
    public var horizontalExtent: ClosedRange<Float>? {
        switch self {
        case .rect(let x, _, let w, _, _, _, let width, _, _), .oval(let x, _, let w, _, _, _, let width, _):
            return (x - width / 2)...(x + w + width / 2)
        case .line(_, let width, let points, _):
            return SheetOp.extent(points, pad: width / 2 + 1)
        case .polygon(_, _, let points, _):
            return SheetOp.extent(points, pad: 1)
        case .text(let x, _, let text, _, _, let size, _, _):
            // Wider than any sans serif at this size: up to one em per character.
            let reach = Float(text.utf16.count) * size * SheetBuffer.ptToPoints + 4
            return (x - reach)...(x + reach)
        case .image(let x, _, let key, _, _):
            // Images are at most ~1.7 × their height wide (the whole notehead).
            let reach = 2 * Float(SheetImageKey(key)?.height ?? 256) + 4
            return (x - reach)...(x + reach)
        }
    }

    private static func extent(_ points: [SheetPoint], pad: Float) -> ClosedRange<Float>? {
        guard let first = points.first else { return nil }
        var lo = first.x
        var hi = first.x
        for point in points {
            lo = min(lo, point.x)
            hi = max(hi, point.x)
        }
        return (lo - pad)...(hi + pad)
    }
}

/// One chord's box on the strip, for hit-testing and the playhead highlight.
public struct SheetSlot: Sendable, Equatable {
    /// Index into the rendered song's chords (what `audition` and the playhead use).
    public var chordIndex: Int
    public var x: Float
    public var width: Float

    /// Whether content x `cx` falls in this slot (edges included, as on the desktop).
    public func contains(_ cx: Float) -> Bool { cx >= x && cx <= x + width }
}

/// The gutter variant shown for every scroll position past `startX`.
public struct SheetGutterRun: Sendable, Equatable {
    public var startX: Float
    public var variant: Int
}

/// A list of ops with their horizontal extents, for culling.
public struct SheetOpList: Sendable, Equatable {
    public let ops: [SheetOp]
    /// Each op's x range (nil: it paints nothing, an empty line).
    public let extents: [ClosedRange<Float>?]

    init(_ ops: [SheetOp]) {
        self.ops = ops
        extents = ops.map(\.horizontalExtent)
    }

    public var count: Int { ops.count }

    /// Whether op `index` may paint anything between content x `left` and `right`.
    public func intersects(_ index: Int, left: Float, right: Float) -> Bool {
        guard let extent = extents[index] else { return false }
        return extent.upperBound >= left && extent.lowerBound <= right
    }

    /// Indices of the ops that intersect `[left, right]`, in paint order.
    public func visibleIndices(left: Float, right: Float) -> [Int] {
        ops.indices.filter { intersects($0, left: left, right: right) }
    }
}

/// The buffer can't be decoded.
public enum SheetBufferError: Error, Equatable {
    /// Another format version (a newer core); never guessed at.
    case unsupportedVersion(Int)
    /// Bad magic, truncated, an unknown opcode or anchor, a bad index...
    case malformed(String)
}

/// One chord-sheet view, decoded from the op buffer: everything the strip draws
/// for one (song, view, zoom, height). Immutable; decode once and keep it.
///
/// Coordinates are points (1 Tk px = 1 pt); text sizes are Tk points (× 4/3 on
/// screen, ``ptToPoints``).
public struct SheetBuffer: Sendable, Equatable {
    /// The only format version this decoder reads.
    public static let formatVersion = 2
    /// Screen points per Tk point: Tk lays text out at 96 DPI, 4/3 px per point.
    public static let ptToPoints: Float = 4.0 / 3.0

    public let version: Int
    public let viewId: String
    public let background: String
    public let highlight: String
    public let zoom: Float
    public let height: Float
    public let contentWidth: Float
    public let contentHeight: Float
    public let gutterWidth: Float
    public let laneHeight: Float
    public let strings: [String]
    public let slots: [SheetSlot]
    public let content: SheetOpList
    public let lane: SheetOpList
    public let gutterVariants: [SheetOpList]
    public let gutterRuns: [SheetGutterRun]

    /// The index of the gutter variant to draw when content x `scrollX` is at
    /// the viewport's left edge (the last run with `startX < scrollX`), or nil
    /// when the view has no gutter.
    public func gutterVariantIndex(at scrollX: Float) -> Int? {
        var found: Int?
        for run in gutterRuns {
            if run.startX < scrollX { found = run.variant } else { break }
        }
        return found
    }

    /// The gutter variant for `scrollX`, or nil.
    public func gutterVariant(at scrollX: Float) -> SheetOpList? {
        gutterVariantIndex(at: scrollX).map { gutterVariants[$0] }
    }

    /// The slot under content x `cx`, or nil (the first match, as on the desktop).
    public func slot(at cx: Float) -> SheetSlot? { slots.first { $0.contains(cx) } }

    /// The slot drawn for chord `chordIndex`, or nil.
    public func slot(forChord chordIndex: Int) -> SheetSlot? {
        slots.first { $0.chordIndex == chordIndex }
    }

    /// Decode `data`.
    ///
    /// - Throws: ``SheetBufferError``.
    public static func decode(_ data: Data) throws -> SheetBuffer {
        var reader = Reader(bytes: [UInt8](data))
        return try reader.readAll()
    }
}

private extension UInt8 {
    var isASCIIHexDigit: Bool {
        (0x30...0x39).contains(self) || (0x41...0x46).contains(self) || (0x61...0x66).contains(self)
    }
}

private let noString = 0xFFFF
private let minHeaderSize = 48

private struct Reader {
    let bytes: [UInt8]
    var pos = 0
    var strings: [String] = []

    init(bytes: [UInt8]) {
        self.bytes = bytes
    }

    mutating func readAll() throws -> SheetBuffer {
        guard bytes.count >= 8, bytes[0..<4].elementsEqual("CNSB".utf8) else {
            throw SheetBufferError.malformed("Not a chord sheet buffer")
        }
        let version = try u16(at: 4)
        guard version == SheetBuffer.formatVersion else {
            throw SheetBufferError.unsupportedVersion(version)
        }
        let headerSize = try u16(at: 6)
        guard headerSize >= minHeaderSize else {
            throw SheetBufferError.malformed("Header too short: \(headerSize)")
        }
        guard bytes.count >= headerSize else { throw truncated }
        let viewIdIndex = try u16(at: 8)
        let backgroundIndex = try u16(at: 10)
        let highlightIndex = try u16(at: 12)
        let zoom = try f32(at: 16)
        let height = try f32(at: 20)
        let contentWidth = try f32(at: 24)
        let contentHeight = try f32(at: 28)
        let gutterWidth = try f32(at: 32)
        let laneHeight = try f32(at: 36)
        let stringCount = try count(try u32(at: 40))
        let slotCount = try count(try u32(at: 44))

        pos = headerSize
        var strings: [String] = []
        strings.reserveCapacity(stringCount)
        for _ in 0..<stringCount {
            let length = try readU16()
            try need(length)
            strings.append(String(decoding: bytes[pos..<pos + length], as: UTF8.self))
            pos += length
        }
        self.strings = strings
        var slots: [SheetSlot] = []
        slots.reserveCapacity(slotCount)
        for _ in 0..<slotCount {
            let chordIndex = try count(try readU32())
            slots.append(SheetSlot(chordIndex: chordIndex, x: try readF32(), width: try readF32()))
        }
        let content = try readOpList()
        let lane = try readOpList()
        let variantCount = try readU16()
        var variants: [SheetOpList] = []
        for _ in 0..<variantCount {
            variants.append(try readOpList())
        }
        let runCount = try readU16()
        var runs: [SheetGutterRun] = []
        for _ in 0..<runCount {
            let start = try readF32()
            let variant = try readU16()
            guard variant < variants.count else {
                throw SheetBufferError.malformed("Gutter run names variant \(variant)")
            }
            runs.append(SheetGutterRun(startX: start, variant: variant))
        }
        guard pos == bytes.count else {
            throw SheetBufferError.malformed("Trailing bytes after the gutter runs")
        }
        return SheetBuffer(
            version: version,
            viewId: try str(viewIdIndex) ?? "",
            background: try str(backgroundIndex) ?? "#ffffff",
            highlight: try str(highlightIndex) ?? "#ffe58a",
            zoom: zoom, height: height,
            contentWidth: contentWidth, contentHeight: contentHeight,
            gutterWidth: gutterWidth, laneHeight: laneHeight,
            strings: strings, slots: slots, content: content, lane: lane,
            gutterVariants: variants, gutterRuns: runs)
    }

    private mutating func readOpList() throws -> SheetOpList {
        let opCount = try count(try readU32())
        let byteLength = try count(try readU32())
        let end = pos + byteLength
        guard end <= bytes.count else { throw SheetBufferError.malformed("Op list runs past the end") }
        var ops: [SheetOp] = []
        ops.reserveCapacity(opCount)
        for _ in 0..<opCount {
            ops.append(try readOp())
        }
        guard pos == end else { throw SheetBufferError.malformed("Op list length mismatch") }
        return SheetOpList(ops)
    }

    private mutating func readOp() throws -> SheetOp {
        let code = try readU8()
        switch code {
        case 1, 2, 7:
            let x = try readF32(), y = try readF32(), w = try readF32(), h = try readF32()
            let fill = try str(try readU16()), outline = try str(try readU16())
            let width = try readF32()
            let radius: Float = code == 7 ? try readF32() : 0
            let tags = try readTags()
            if code == 2 {
                return .oval(x: x, y: y, w: w, h: h, fill: fill, outline: outline, width: width, tags: tags)
            }
            return .rect(x: x, y: y, w: w, h: h, fill: fill, outline: outline, width: width,
                         radius: radius, tags: tags)
        case 3:
            let fill = try str(try readU16())
            let width = try readF32()
            let points = try readPoints(try readU16())
            return .line(fill: fill, width: width, points: points, tags: try readTags())
        case 4:
            let fill = try str(try readU16())
            let smooth = try readU8() != 0
            let points = try readPoints(try readU16())
            return .polygon(fill: fill, smooth: smooth, points: points, tags: try readTags())
        case 5:
            let x = try readF32(), y = try readF32()
            let text = try str(try readU16()) ?? ""
            let anchor = try readAnchor()
            let bold = try readU8() != 0
            let size = try readF32()
            let fill = try str(try readU16())
            return .text(x: x, y: y, text: text, anchor: anchor, bold: bold, size: size, fill: fill,
                         tags: try readTags())
        case 6:
            let x = try readF32(), y = try readF32()
            let key = try str(try readU16()) ?? ""
            let anchor = try readAnchor()
            return .image(x: x, y: y, key: key, anchor: anchor, tags: try readTags())
        default:
            throw SheetBufferError.malformed("Unknown opcode \(code) at byte \(pos - 1)")
        }
    }

    private mutating func readTags() throws -> [String] {
        let n = try readU8()
        if n == 0 { return [] }
        var tags: [String] = []
        tags.reserveCapacity(n)
        for _ in 0..<n {
            tags.append(try str(try readU16()) ?? "")
        }
        return tags
    }

    private mutating func readPoints(_ n: Int) throws -> [SheetPoint] {
        try need(8 * n)
        var points: [SheetPoint] = []
        points.reserveCapacity(n)
        for _ in 0..<n {
            points.append(SheetPoint(x: try readF32(), y: try readF32()))
        }
        return points
    }

    private mutating func readAnchor() throws -> SheetAnchor {
        let code = try readU8()
        guard let anchor = SheetAnchor(rawValue: code) else {
            throw SheetBufferError.malformed("Unknown anchor \(code)")
        }
        return anchor
    }

    private func str(_ index: Int) throws -> String? {
        if index == noString { return nil }
        guard index < strings.count else {
            throw SheetBufferError.malformed("String index \(index) out of range")
        }
        return strings[index]
    }

    private var truncated: SheetBufferError { .malformed("Truncated chord sheet buffer") }

    private func need(_ length: Int) throws {
        guard length >= 0, pos + length <= bytes.count else { throw truncated }
    }

    /// A count or index read from the buffer; anything larger than the buffer
    /// itself is malformed (and must not size an allocation).
    private func count(_ value: UInt32) throws -> Int {
        guard Int(value) <= bytes.count else {
            throw SheetBufferError.malformed("Count \(value) larger than the buffer")
        }
        return Int(value)
    }

    private func u16(at offset: Int) throws -> Int {
        guard offset >= 0, offset + 2 <= bytes.count else { throw truncated }
        return Int(bytes[offset]) | Int(bytes[offset + 1]) << 8
    }

    private func u32(at offset: Int) throws -> UInt32 {
        guard offset >= 0, offset + 4 <= bytes.count else { throw truncated }
        return UInt32(bytes[offset]) | UInt32(bytes[offset + 1]) << 8
            | UInt32(bytes[offset + 2]) << 16 | UInt32(bytes[offset + 3]) << 24
    }

    private func f32(at offset: Int) throws -> Float {
        Float(bitPattern: try u32(at: offset))
    }

    private mutating func readU8() throws -> Int {
        try need(1)
        defer { pos += 1 }
        return Int(bytes[pos])
    }

    private mutating func readU16() throws -> Int {
        defer { pos += 2 }
        return try u16(at: pos)
    }

    private mutating func readU32() throws -> UInt32 {
        defer { pos += 4 }
        return try u32(at: pos)
    }

    private mutating func readF32() throws -> Float {
        defer { pos += 4 }
        return try f32(at: pos)
    }
}

/// An image op's key split into its parts (`chord_sheet.clef_assets.parse_image_key`).
public struct SheetImageKey: Sendable, Equatable {
    /// The base PNG's name (`clef_treble`, `glyph_accidental_sharp`, ...).
    public var asset: String
    /// The height to draw it at, in points.
    public var height: Int
    /// `#rrggbb` to tint the black ink with, or nil.
    public var tint: String?

    public init(asset: String, height: Int, tint: String?) {
        self.asset = asset
        self.height = height
        self.tint = tint
    }

    /// Parse a key, or nil when malformed.
    public init?(_ key: String) {
        let parts = key.split(separator: ":", omittingEmptySubsequences: false).map(String.init)
        guard (2...3).contains(parts.count), let height = Int(parts[1]), height > 0 else { return nil }
        let name = parts[0]
        guard name.hasPrefix("clef_") || name.hasPrefix("glyph_") else { return nil }
        if parts.count == 3 {
            guard name.hasPrefix("glyph_") else { return nil }
            var hex = parts[2]
            if hex.hasPrefix("#") { hex.removeFirst() }
            guard hex.utf8.count == 6, hex.utf8.allSatisfy({ $0.isASCIIHexDigit }) else { return nil }
            self.init(asset: name, height: height, tint: "#" + hex.lowercased())
        } else {
            self.init(asset: name, height: height, tint: nil)
        }
    }
}

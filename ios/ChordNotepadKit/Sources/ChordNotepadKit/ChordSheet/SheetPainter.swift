import Foundation

// Replays a decoded op buffer on a SheetCanvas: Android's
// ui/chordsheet/ChordSheetPainter.kt and the strip composition of
// ChordSheetPane.kt (lane, content, gutter, playhead), with the desktop's
// key bed under the piano roll's keyboard (desktop/chordnotepad_desktop/
// sheet_paint.py, the second reference). Runs and is tested on Linux.

/// An op list ready to draw: the lane's clip edges and every polygon's path,
/// worked out once.
public struct PreparedOps: Sendable {
    public let list: SheetOpList
    /// Each op's right clip edge (+∞: none); the marker lane's labels only.
    public let clipRights: [Double]?
    /// The path of each polygon (nil for other ops).
    public let paths: [[SheetPathElement]?]
    /// The box the rectangles cover (the piano roll keyboard's key bed), or nil.
    public let rectBounds: SheetRect?

    public init(_ list: SheetOpList, clipRights: [Double]? = nil) {
        self.list = list
        self.clipRights = clipRights
        var bounds: SheetRect?
        paths = list.ops.map { op in
            switch op {
            case .polygon(_, let smooth, let points, _):
                return SheetPainter.polygonPath(points, smooth: smooth)
            case .rect(let x, let y, let w, let h, _, _, _, _, _):
                let rect = SheetRect(x: Double(x), y: Double(y), width: Double(w), height: Double(h))
                bounds = bounds.map { $0.union(rect) } ?? rect
                return nil
            default:
                return nil
            }
        }
        rectBounds = bounds
    }
}

/// A decoded buffer with everything drawing needs, prepared off the main thread.
public struct PreparedSheet: Sendable {
    private static let counter = Counter()

    /// Unique per prepared buffer: views compare sheets by it.
    public let id: Int
    public let buffer: SheetBuffer
    public let content: PreparedOps
    /// Marker lane ops, labels clipped short of the next one.
    public let lane: PreparedOps
    public let gutters: [PreparedOps]
    /// The image keys the buffer uses (for preloading glyphs).
    public let imageKeys: Set<String>

    public init(_ buffer: SheetBuffer) {
        id = Self.counter.next()
        self.buffer = buffer
        content = PreparedOps(buffer.content)
        lane = PreparedOps(buffer.lane, clipRights: buffer.lane.laneClipRights())
        gutters = buffer.gutterVariants.map { PreparedOps($0) }
        var keys = Set<String>()
        for list in [buffer.content, buffer.lane] + buffer.gutterVariants {
            for case .image(_, _, let key, _, _) in list.ops { keys.insert(key) }
        }
        imageKeys = keys
    }

    /// The prepared gutter for content x `scrollX` at the viewport's left edge, or nil.
    public func gutter(at scrollX: Double) -> PreparedOps? {
        guard buffer.gutterWidth > 0 else { return nil }
        return buffer.gutterVariantIndex(at: Float(scrollX)).map { gutters[$0] }
    }

    private final class Counter: @unchecked Sendable {
        private let lock = NSLock()
        private var value = 0

        func next() -> Int {
            lock.withLock {
                value += 1
                return value
            }
        }
    }
}

/// What one paint of the strip shows.
public struct SheetFrame: Sendable, Equatable {
    /// The strip's whole size (gutter included), in points.
    public var size: SheetSize
    /// Content x at the scrolling part's left edge (right of the gutter).
    public var scrollX: Double
    /// The chord sounding while a song plays.
    public var currentIndex: Int?
    /// The playhead's chord (an edge mark while nothing plays).
    public var cursorIndex: Int?

    public init(size: SheetSize, scrollX: Double, currentIndex: Int?, cursorIndex: Int?) {
        self.size = size
        self.scrollX = scrollX
        self.currentIndex = currentIndex
        self.cursorIndex = cursorIndex
    }
}

/// Draws prepared ops on a ``SheetCanvas`` in content points. Text uses the
/// system sans serif at the op's size × 4/3 and ignores the system text size:
/// the strip's geometry is fixed by the renderers. Text and glyphs land on
/// whole device pixels (`pixelScale` px per point), as on Android and the desktop.
public struct SheetPainter: Sendable {
    /// Screen points per Tk point (Tk lays text out at 96 DPI).
    public static let pointScale = 4.0 / 3.0
    /// The playing column's corner radius, and its top and bottom edges'
    /// thickness and alpha (a multiple of the tint's).
    public static let playingRadius = 6.0
    public static let playingEdge = 2.0
    public static let playingEdgeAlpha = 4.0

    public let glyphs: SheetGlyphIndex
    public let pixelScale: Double

    public init(glyphs: SheetGlyphIndex, pixelScale: Double) {
        self.glyphs = glyphs
        self.pixelScale = max(pixelScale, 1)
    }

    /// `value` on the device pixel grid.
    public func snap(_ value: Double) -> Double {
        (value * pixelScale).rounded() / pixelScale
    }

    /// The font of a text op of Tk point size `size`.
    public static func font(size: Float, bold: Bool) -> SheetFont {
        SheetFont(size: Double(size) * pointScale, bold: bold)
    }

    /// Paint the whole strip for `frame`: the background, then the lane and
    /// the content scrolled by `frame.scrollX` right of the gutter, the
    /// playhead (a primary edge left of the cursor's chord while nothing
    /// plays, else a tint over the chord sounding, on top of its content),
    /// then the frozen gutter.
    ///
    /// - Returns: How many ops were drawn.
    @discardableResult
    public func paint(_ sheet: PreparedSheet, palette: ChordSheetPalette, frame: SheetFrame,
                      on canvas: SheetCanvas) -> Int {
        let buffer = sheet.buffer
        let size = frame.size
        let gutter = Double(buffer.gutterWidth)
        let lane = Double(buffer.laneHeight)
        let contentHeight = Double(buffer.contentHeight)
        let viewport = max(size.width - gutter, 0)
        let left = frame.scrollX
        let right = frame.scrollX + viewport
        var drawn = 0
        canvas.fill(SheetRect(x: 0, y: 0, width: size.width, height: size.height), cornerRadius: 0,
                    color: palette.colors.surfaceLow)

        canvas.saveState()
        canvas.clip(to: SheetRect(x: gutter, y: 0, width: viewport, height: size.height))
        canvas.translate(x: snap(gutter - frame.scrollX), y: 0)
        drawn += draw(sheet.lane, colors: palette.content, palette: palette, left: left, right: right, on: canvas)
        canvas.translate(x: 0, y: lane)
        drawn += draw(sheet.content, colors: palette.content, palette: palette, left: left, right: right, on: canvas)
        if let playing = frame.currentIndex.flatMap(buffer.slot(forChord:)) {
            // The playing column: a tint over everything drawn there, with a
            // stronger edge of the same colour at its top and bottom.
            let tint = palette.colors.sheetPlaying
            let x = Double(playing.x), w = Double(playing.width)
            canvas.fill(SheetRect(x: x, y: 2, width: w, height: contentHeight - 4),
                        cornerRadius: Self.playingRadius, color: tint)
            let edge = tint.withAlpha(min(tint.alpha * Self.playingEdgeAlpha, 1))
            let e = Self.playingEdge
            canvas.fill(SheetRect(x: x + 1, y: 2, width: w - 2, height: e), cornerRadius: e / 2, color: edge)
            canvas.fill(SheetRect(x: x + 1, y: contentHeight - 2 - e, width: w - 2, height: e), cornerRadius: e / 2,
                        color: edge)
        } else if let cursor = frame.cursorIndex.flatMap(buffer.slot(forChord:)) {
            canvas.fill(SheetRect(x: Double(cursor.x), y: 2, width: 3, height: contentHeight - 4), cornerRadius: 1.5,
                        color: palette.colors.primary)
        }
        canvas.restoreState()

        if let variant = sheet.gutter(at: frame.scrollX) {
            canvas.saveState()
            canvas.clip(to: SheetRect(x: 0, y: 0, width: gutter, height: size.height))
            canvas.translate(x: 0, y: lane)
            var colors = palette.content
            if buffer.viewId == "keyboard" {
                // The piano roll's keyboard keeps its own look (its labels sit
                // on white keys), on a bed of the white keys' colour so the
                // space beside each black key isn't a hole (the desktop's key bed).
                colors = palette.keyboard
                let white = colors.first { $0.key.lowercased() == SheetInk.gutterWhite }?.value
                if let bed = variant.rectBounds, let white {
                    canvas.fill(bed, cornerRadius: 0, color: white)
                }
            }
            drawn += draw(variant, colors: colors, palette: palette, left: -.infinity, right: .infinity, on: canvas)
            canvas.restoreState()
        }
        return drawn
    }

    /// Draw the ops of `ops` that may paint between content x `left` and
    /// `right`, in order, looking colours up in `colors`.
    ///
    /// - Returns: How many ops were drawn.
    @discardableResult
    public func draw(_ ops: PreparedOps, colors: [String: SheetColor], palette: ChordSheetPalette,
                     left: Double, right: Double, on canvas: SheetCanvas) -> Int {
        let list = ops.list
        let l = Float(max(left, -Double(Float.greatestFiniteMagnitude)))
        let r = Float(min(right, Double(Float.greatestFiniteMagnitude)))
        var drawn = 0
        for i in 0..<list.count where list.intersects(i, left: l, right: r) {
            drawn += 1
            func color(_ spec: String?) -> SheetColor? { spec.flatMap { colors[$0] } }
            switch list.ops[i] {
            case .rect(let x, let y, let w, let h, let fill, let outline, let width, let radius, _):
                let rect = SheetRect(x: Double(x), y: Double(y), width: Double(w), height: Double(h))
                if let c = color(fill) { canvas.fill(rect, cornerRadius: Double(radius), color: c) }
                if width > 0, let c = color(outline) {
                    canvas.stroke(rect, cornerRadius: Double(radius), color: c, width: Double(width))
                }
            case .oval(let x, let y, let w, let h, let fill, let outline, let width, _):
                let rect = SheetRect(x: Double(x), y: Double(y), width: Double(w), height: Double(h))
                if let c = color(fill) { canvas.fillEllipse(in: rect, color: c) }
                if width > 0, let c = color(outline) { canvas.strokeEllipse(in: rect, color: c, width: Double(width)) }
            case .line(let fill, let width, let points, _):
                guard points.count >= 2 else { continue }
                canvas.strokeLine(points.flatMap { [Double($0.x), Double($0.y)] }, color: color(fill) ?? .black,
                                  width: Double(width))
            case .polygon(let fill, _, _, _):
                guard let path = ops.paths[i], !path.isEmpty else { continue }
                canvas.fill(path, color: color(fill) ?? .black)
            case .text(let x, let y, let text, let anchor, let bold, let size, let fill, _):
                let font = Self.font(size: size, bold: bold)
                let box = canvas.measure(text, font: font)
                let origin = anchor.topLeft(x: Double(x), y: Double(y), width: box.width, height: box.height)
                let left = snap(origin.x)
                let clip = ops.clipRights?[i] ?? .infinity
                canvas.draw(text, font: font, x: left, y: snap(origin.y), color: color(fill) ?? .black,
                            clipRight: clip.isFinite && left + box.width > clip ? clip : nil)
            case .image(let x, let y, let key, let anchor, _):
                guard let parsed = SheetImageKey(key), let size = glyphs.size(of: parsed) else { continue }
                let origin = anchor.topLeft(x: Double(x), y: Double(y), width: size.width, height: size.height)
                canvas.drawGlyph(parsed.asset,
                                 in: SheetRect(x: snap(origin.x), y: snap(origin.y), width: size.width,
                                               height: size.height),
                                 tint: palette.glyphTint(parsed.tint))
            }
        }
        return drawn
    }

    /// A polygon's path; smooth is Tk's quadratic B-spline through the edge
    /// midpoints. Empty for fewer than two points.
    public static func polygonPath(_ points: [SheetPoint], smooth: Bool) -> [SheetPathElement] {
        let n = points.count
        guard n >= 2 else { return [] }
        func px(_ i: Int) -> Double { Double(points[i % n].x) }
        func py(_ i: Int) -> Double { Double(points[i % n].y) }
        var path: [SheetPathElement] = []
        if !smooth || n < 3 {
            path.append(.move(x: px(0), y: py(0)))
            for i in 1..<n { path.append(.line(x: px(i), y: py(i))) }
            path.append(.close)
            return path
        }
        path.append(.move(x: (px(n - 1) + px(0)) / 2, y: (py(n - 1) + py(0)) / 2))
        for i in 0..<n {
            path.append(.quad(cx: px(i), cy: py(i), x: (px(i) + px(i + 1)) / 2, y: (py(i) + py(i + 1)) / 2))
        }
        path.append(.close)
        return path
    }
}

import Foundation

/// A rectangle in points.
public struct SheetRect: Sendable, Hashable, CustomStringConvertible {
    public var x: Double
    public var y: Double
    public var width: Double
    public var height: Double

    public init(x: Double, y: Double, width: Double, height: Double) {
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    }

    public var maxX: Double { x + width }
    public var maxY: Double { y + height }

    /// The smallest rectangle holding both.
    public func union(_ other: SheetRect) -> SheetRect {
        let left = min(x, other.x), top = min(y, other.y)
        return SheetRect(x: left, y: top, width: max(maxX, other.maxX) - left, height: max(maxY, other.maxY) - top)
    }

    public var description: String { "(\(x), \(y), \(width)×\(height))" }
}

/// A size in points.
public struct SheetSize: Sendable, Hashable {
    public var width: Double
    public var height: Double

    public init(width: Double, height: Double) {
        self.width = width
        self.height = height
    }
}

/// One step of a filled path (a polygon, smooth or not).
public enum SheetPathElement: Sendable, Hashable {
    case move(x: Double, y: Double)
    case line(x: Double, y: Double)
    /// A quadratic Bézier through control point (`cx`, `cy`) to (`x`, `y`).
    case quad(cx: Double, cy: Double, x: Double, y: Double)
    case close
}

/// The font of a text op: the system sans serif at `size` screen points.
public struct SheetFont: Sendable, Hashable {
    /// Screen points (a Tk point size × 4/3).
    public var size: Double
    public var bold: Bool

    public init(size: Double, bold: Bool) {
        self.size = size
        self.bold = bold
    }
}

/// What the chord sheet painter draws on: the app implements it over
/// CoreGraphics (and CoreText for text), the tests record the calls.
///
/// Coordinates are points in the current transform; the painter translates
/// and clips with ``saveState()`` / ``restoreState()`` around each part.
/// Strokes have butt caps; rounded shapes and polylines join round, square
/// rectangles mitre (Android's and the desktop's strokes).
public protocol SheetCanvas {
    func saveState()
    func restoreState()
    func translate(x: Double, y: Double)
    /// Intersect the clip with `rect`.
    func clip(to rect: SheetRect)

    func fill(_ rect: SheetRect, cornerRadius: Double, color: SheetColor)
    /// The outline centred on the rectangle's edge.
    func stroke(_ rect: SheetRect, cornerRadius: Double, color: SheetColor, width: Double)
    func fillEllipse(in rect: SheetRect, color: SheetColor)
    func strokeEllipse(in rect: SheetRect, color: SheetColor, width: Double)
    /// A polyline of two or more points (x0, y0, x1, y1, ...).
    func strokeLine(_ points: [Double], color: SheetColor, width: Double)
    func fill(_ path: [SheetPathElement], color: SheetColor)

    /// The size of `text`'s line box in `font` (ascent plus descent, no
    /// leading): what anchors place.
    func measure(_ text: String, font: SheetFont) -> SheetSize
    /// Draw `text` with its line box's top-left corner at (`x`, `y`). With
    /// `clipRight`, nothing right of that x shows.
    func draw(_ text: String, font: SheetFont, x: Double, y: Double, color: SheetColor, clipRight: Double?)
    /// Draw glyph `asset` scaled into `rect`; `tint` recolours its ink and
    /// keeps its alpha (SrcIn), nil draws it as it is.
    func drawGlyph(_ asset: String, in rect: SheetRect, tint: SheetColor?)
}

/// The seven base clef and glyph images' sizes (`glyphs.json`, written by
/// android/tools/export_clef_glyphs.py next to the PNGs), and the size an
/// image key is drawn at.
public struct SheetGlyphIndex: Sendable, Equatable {
    /// Base PNG width and height in pixels, by asset name.
    public let baseSizes: [String: SheetSize]

    public init(baseSizes: [String: SheetSize]) {
        self.baseSizes = baseSizes
    }

    /// Parse `glyphs.json` (`{"version": 1, "assets": {name: {"width", "height"}}}`).
    public init(json: Data) throws {
        guard let root = try JSONSerialization.jsonObject(with: json) as? [String: Any],
              root["version"] as? Int == 1, let assets = root["assets"] as? [String: Any] else {
            throw SheetBufferError.malformed("glyphs.json isn't version 1")
        }
        var sizes: [String: SheetSize] = [:]
        for (name, value) in assets {
            guard let size = value as? [String: Any], let w = size["width"] as? Int, let h = size["height"] as? Int,
                  w > 0, h > 0 else {
                throw SheetBufferError.malformed("glyphs.json: bad size for \(name)")
            }
            sizes[name] = SheetSize(width: Double(w), height: Double(h))
        }
        baseSizes = sizes
    }

    /// The size `key` is drawn at, in points: its height, and the width
    /// `clef_assets.scaled_width` gives (`max(1, round(base_w * h / base_h))`),
    /// so it lands where the renderer placed it. Nil for an unknown asset.
    public func size(of key: SheetImageKey) -> SheetSize? {
        guard let base = baseSizes[key.asset] else { return nil }
        // Python's round() rounds halves to even.
        let width = max(1, (base.width * Double(key.height) / base.height).rounded(.toNearestOrEven))
        return SheetSize(width: width, height: Double(key.height))
    }
}

import ChordNotepadKit
import CoreGraphics
import CoreText
import Foundation
import UIKit
import os

extension SheetColor {
    var cgColor: CGColor { CGColor(srgbRed: red, green: green, blue: blue, alpha: alpha) }
}

extension SheetRect {
    var cgRect: CGRect { CGRect(x: x, y: y, width: width, height: height) }
}

/// The kit's ``SheetCanvas`` over a CoreGraphics context whose origin is at
/// the top left, y down (a SwiftUI `Canvas`'s `withCGContext`, a UIKit view's
/// or a `UIGraphicsImageRenderer`'s context). Text goes through CoreText in
/// the system font, glyphs come pre-scaled to device pixels from
/// ``SheetGlyphImages``.
final class CGSheetCanvas: SheetCanvas {
    let context: CGContext
    let glyphs: SheetGlyphImages
    /// Device pixels per point.
    let scale: CGFloat

    init(_ context: CGContext, glyphs: SheetGlyphImages = .shared, scale: CGFloat) {
        self.context = context
        self.glyphs = glyphs
        self.scale = max(scale, 1)
    }

    func saveState() { context.saveGState() }
    func restoreState() { context.restoreGState() }
    func translate(x: Double, y: Double) { context.translateBy(x: x, y: y) }
    func clip(to rect: SheetRect) { context.clip(to: rect.cgRect) }

    func fill(_ rect: SheetRect, cornerRadius: Double, color: SheetColor) {
        guard rect.width > 0, rect.height > 0 else { return }
        context.setFillColor(color.cgColor)
        if cornerRadius > 0 {
            context.addPath(Self.roundedRect(rect, cornerRadius))
            context.fillPath()
        } else {
            context.fill(rect.cgRect)
        }
    }

    func stroke(_ rect: SheetRect, cornerRadius: Double, color: SheetColor, width: Double) {
        guard rect.width >= 0, rect.height >= 0 else { return }
        setStroke(color, width: width, join: cornerRadius > 0 ? .round : .miter)
        if cornerRadius > 0 {
            context.addPath(Self.roundedRect(rect, cornerRadius))
            context.strokePath()
        } else {
            context.stroke(rect.cgRect)
        }
    }

    func fillEllipse(in rect: SheetRect, color: SheetColor) {
        context.setFillColor(color.cgColor)
        context.fillEllipse(in: rect.cgRect)
    }

    func strokeEllipse(in rect: SheetRect, color: SheetColor, width: Double) {
        setStroke(color, width: width, join: .round)
        context.strokeEllipse(in: rect.cgRect)
    }

    func strokeLine(_ points: [Double], color: SheetColor, width: Double) {
        guard points.count >= 4 else { return }
        setStroke(color, width: width, join: .round)
        context.beginPath()
        context.move(to: CGPoint(x: points[0], y: points[1]))
        var i = 2
        while i + 1 < points.count {
            context.addLine(to: CGPoint(x: points[i], y: points[i + 1]))
            i += 2
        }
        context.strokePath()
    }

    func fill(_ path: [SheetPathElement], color: SheetColor) {
        let cgPath = CGMutablePath()
        for element in path {
            switch element {
            case .move(let x, let y): cgPath.move(to: CGPoint(x: x, y: y))
            case .line(let x, let y): cgPath.addLine(to: CGPoint(x: x, y: y))
            case .quad(let cx, let cy, let x, let y):
                cgPath.addQuadCurve(to: CGPoint(x: x, y: y), control: CGPoint(x: cx, y: cy))
            case .close: cgPath.closeSubpath()
            }
        }
        context.setFillColor(color.cgColor)
        context.addPath(cgPath)
        context.fillPath()
    }

    func measure(_ text: String, font: SheetFont) -> SheetSize {
        let line = SheetTextLines.shared.line(text, font: font)
        return SheetSize(width: line.width, height: line.ascent + line.descent)
    }

    func draw(_ text: String, font: SheetFont, x: Double, y: Double, color: SheetColor, clipRight: Double?) {
        let line = SheetTextLines.shared.line(text, font: font)
        context.saveGState()
        if let clipRight {
            context.clip(to: CGRect(x: x - 1, y: y - 1, width: max(0, clipRight - x + 1),
                                    height: line.ascent + line.descent + 2))
        }
        // CoreText draws y up: flip the text matrix in this y-down context.
        context.textMatrix = CGAffineTransform(scaleX: 1, y: -1)
        context.textPosition = CGPoint(x: x, y: y + line.ascent)
        context.setFillColor(color.cgColor)
        CTLineDraw(line.line, context)
        context.restoreGState()
    }

    func drawGlyph(_ asset: String, in rect: SheetRect, tint: SheetColor?) {
        let pixelWidth = max(1, Int((rect.width * scale).rounded()))
        let pixelHeight = max(1, Int((rect.height * scale).rounded()))
        guard let image = glyphs.image(asset, pixelWidth: pixelWidth, pixelHeight: pixelHeight, tint: tint) else {
            return
        }
        context.saveGState()
        // CGContext.draw puts an image y up: flip it about the rectangle.
        context.translateBy(x: rect.x, y: rect.y + rect.height)
        context.scaleBy(x: 1, y: -1)
        context.interpolationQuality = .high
        context.draw(image, in: CGRect(x: 0, y: 0, width: rect.width, height: rect.height))
        context.restoreGState()
    }

    private func setStroke(_ color: SheetColor, width: Double, join: CGLineJoin) {
        context.setStrokeColor(color.cgColor)
        context.setLineWidth(width)
        context.setLineCap(.butt)
        context.setLineJoin(join)
    }

    /// A rounded rectangle; CoreGraphics traps on a radius over half a side.
    private static func roundedRect(_ rect: SheetRect, _ radius: Double) -> CGPath {
        let r = max(0, min(radius, rect.width / 2, rect.height / 2))
        return CGPath(roundedRect: rect.cgRect, cornerWidth: r, cornerHeight: r, transform: nil)
    }
}

/// CoreText lines for the sheet's text, laid out once per (text, font) and
/// kept (any thread).
final class SheetTextLines: @unchecked Sendable {
    struct Line {
        let line: CTLine
        let width: Double
        let ascent: Double
        let descent: Double
    }

    static let shared = SheetTextLines()
    private static let limit = 4096

    private let lock = NSLock()
    private var lines: [Key: Line] = [:]
    private var fonts: [SheetFont: UIFont] = [:]

    private struct Key: Hashable {
        let text: String
        let font: SheetFont
    }

    func line(_ text: String, font: SheetFont) -> Line {
        let key = Key(text: text, font: font)
        return lock.withLock {
            if let found = lines[key] { return found }
            if lines.count > Self.limit { lines.removeAll() }
            let uiFont = fonts[font] ?? {
                let made = UIFont.systemFont(ofSize: font.size, weight: font.bold ? .bold : .regular)
                fonts[font] = made
                return made
            }()
            // UIFont is toll-free bridged to CTFont, and .font is kCTFontAttributeName.
            let attributes: [NSAttributedString.Key: Any] = [
                .font: uiFont,
                // The colour is the context's fill colour, set at each draw.
                NSAttributedString.Key(kCTForegroundColorFromContextAttributeName as String): true,
            ]
            let ctLine = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attributes))
            var ascent: CGFloat = 0
            var descent: CGFloat = 0
            var leading: CGFloat = 0
            let width = CTLineGetTypographicBounds(ctLine, &ascent, &descent, &leading)
            let made = Line(line: ctLine, width: width, ascent: ascent, descent: descent)
            lines[key] = made
            return made
        }
    }
}

/// The seven base clef and glyph PNGs the app's build exports into
/// `chord_sheet/` (android/tools/export_clef_glyphs.py, with `glyphs.json`),
/// scaled once per pixel size and tint and kept (any thread). A missing asset
/// is logged once and skipped, as on Android.
final class SheetGlyphImages: @unchecked Sendable {
    static let shared = SheetGlyphImages(folder: Bundle.main.bundleURL.appendingPathComponent("chord_sheet"))

    /// The base sizes the painter places images with (empty without glyphs.json).
    let index: SheetGlyphIndex

    private let folder: URL
    private let lock = NSLock()
    private var bases: [String: CGImage] = [:]
    private var missing: Set<String> = []
    private var scaled: [ScaledKey: CGImage] = [:]

    private struct ScaledKey: Hashable {
        let asset: String
        let width: Int
        let height: Int
        let tint: UInt32?
    }

    init(folder: URL) {
        self.folder = folder
        do {
            index = try SheetGlyphIndex(json: try Data(contentsOf: folder.appendingPathComponent("glyphs.json")))
        } catch {
            Log.ui.error("Chord sheet glyphs: \(String(describing: error), privacy: .public) in \(folder.path, privacy: .public)")
            index = SheetGlyphIndex(baseSizes: [:])
        }
    }

    /// `asset` at `pixelWidth` × `pixelHeight`, its black ink recoloured to
    /// `tint` with the alpha kept (SrcIn), or nil when the asset is missing.
    func image(_ asset: String, pixelWidth: Int, pixelHeight: Int, tint: SheetColor?) -> CGImage? {
        let key = ScaledKey(asset: asset, width: pixelWidth, height: pixelHeight, tint: tint?.argb)
        return lock.withLock {
            if let found = scaled[key] { return found }
            guard let base = base(asset) else { return nil }
            if scaled.count > 2048 { scaled.removeAll() }
            guard let made = Self.render(base, width: pixelWidth, height: pixelHeight, tint: tint) else { return nil }
            scaled[key] = made
            return made
        }
    }

    /// Every image the keys need, scaled ahead of the first paint.
    func preload(_ keys: Set<String>, scale: CGFloat, colors: ChordSheetPalette) {
        for key in keys {
            guard let parsed = SheetImageKey(key), let size = index.size(of: parsed) else { continue }
            _ = image(parsed.asset, pixelWidth: max(1, Int((size.width * scale).rounded())),
                      pixelHeight: max(1, Int((size.height * scale).rounded())), tint: colors.glyphTint(parsed.tint))
        }
    }

    private func base(_ asset: String) -> CGImage? {
        if let found = bases[asset] { return found }
        if missing.contains(asset) { return nil }
        let url = folder.appendingPathComponent("\(asset).png")
        guard let image = UIImage(contentsOfFile: url.path)?.cgImage else {
            missing.insert(asset)
            Log.ui.error("Missing chord sheet glyph asset \(asset, privacy: .public)")
            return nil
        }
        bases[asset] = image
        return image
    }

    private static func render(_ base: CGImage, width: Int, height: Int, tint: SheetColor?) -> CGImage? {
        guard let space = CGColorSpace(name: CGColorSpace.sRGB),
              let bitmap = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                                     space: space, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
            return nil
        }
        let rect = CGRect(x: 0, y: 0, width: width, height: height)
        bitmap.interpolationQuality = .high
        bitmap.draw(base, in: rect)
        if let tint {
            bitmap.setBlendMode(.sourceIn)
            bitmap.setFillColor(tint.cgColor)
            bitmap.fill(rect)
        }
        return bitmap.makeImage()
    }
}

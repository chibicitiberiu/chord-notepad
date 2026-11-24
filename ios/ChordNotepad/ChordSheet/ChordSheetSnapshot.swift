import ChordNotepadKit
import UIKit

/// The strip painted into an image with the same painter and CoreGraphics
/// canvas the live view uses (the session test's check of the drawing).
enum ChordSheetSnapshot {
    static func image(_ sheet: PreparedSheet, palette: ChordSheetPalette, size: CGSize, scale: CGFloat,
                      scrollX: Double = 0, currentIndex: Int? = nil, cursorIndex: Int? = nil) -> UIImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = true
        return UIGraphicsImageRenderer(size: size, format: format).image { context in
            let painter = SheetPainter(glyphs: SheetGlyphImages.shared.index, pixelScale: scale)
            painter.paint(sheet, palette: palette,
                          frame: SheetFrame(size: SheetSize(width: size.width, height: size.height), scrollX: scrollX,
                                            currentIndex: currentIndex, cursorIndex: cursorIndex),
                          on: CGSheetCanvas(context.cgContext, scale: scale))
        }
    }

    /// How many different colours the image has (sampled on a grid).
    static func distinctColors(_ image: UIImage, step: Int = 3) -> Int {
        guard let cgImage = image.cgImage,
              let space = CGColorSpace(name: CGColorSpace.sRGB),
              let bitmap = CGContext(data: nil, width: cgImage.width, height: cgImage.height, bitsPerComponent: 8,
                                     bytesPerRow: cgImage.width * 4, space: space,
                                     bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue),
              let data = bitmap.data else { return 0 }
        bitmap.draw(cgImage, in: CGRect(x: 0, y: 0, width: cgImage.width, height: cgImage.height))
        let pixels = data.bindMemory(to: UInt32.self, capacity: cgImage.width * cgImage.height)
        var seen = Set<UInt32>()
        for y in stride(from: 0, to: cgImage.height, by: step) {
            for x in stride(from: 0, to: cgImage.width, by: step) {
                seen.insert(pixels[y * cgImage.width + x])
            }
        }
        return seen.count
    }
}

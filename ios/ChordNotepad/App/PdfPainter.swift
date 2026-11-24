import ChordNotepadKit
import CoreText
import PDFKit
import UIKit

/// Export PDF's canvas (Android's `AndroidPdfCanvas`): the kit's
/// ``paintPdf(_:on:)`` draws on it, and ``document()`` renders the pages with
/// `UIGraphicsPDFRenderer`. Text is Menlo (0.602 em, the layout counts 0.6;
/// every word is a run of its own at its column, so the difference never adds
/// up across a line), drawn with Core Text on the layout's baselines.
final class UIKitPdfCanvas: PdfCanvas, @unchecked Sendable {
    private struct Run {
        let text: String
        let x: Double
        let y: Double
        let size: Double
        let color: UInt32
    }

    private struct Page {
        let width: Int
        let height: Int
        var runs: [Run] = []
    }

    private var pages: [Page] = []
    private var open: Page?

    func startPage(number: Int, width: Int, height: Int) {
        open = Page(width: width, height: height)
    }

    func drawText(_ text: String, x: Double, y: Double, size: Double, color: UInt32) {
        open?.runs.append(Run(text: text, x: x, y: y, size: size, color: color))
    }

    func finishPage() {
        if let open { pages.append(open) }
        open = nil
    }

    func document() throws -> Data {
        let first = pages.first.map { CGRect(x: 0, y: 0, width: $0.width, height: $0.height) }
            ?? CGRect(x: 0, y: 0, width: 595, height: 842)
        let format = UIGraphicsPDFRendererFormat()
        format.documentInfo = [kCGPDFContextCreator as String: "Chord Notepad"]
        let renderer = UIGraphicsPDFRenderer(bounds: first, format: format)
        return renderer.pdfData { context in
            for page in pages {
                context.beginPage(withBounds: CGRect(x: 0, y: 0, width: page.width, height: page.height),
                                  pageInfo: [:])
                let cg = context.cgContext
                for run in page.runs {
                    Self.draw(run.text, x: run.x, y: run.y, size: run.size, color: run.color, in: cg)
                }
            }
        }
    }

    /// The font the pages are set in at `size` points.
    static func font(size: Double) -> CTFont {
        let menlo = CTFontCreateWithName("Menlo-Regular" as CFString, CGFloat(size), nil)
        if (CTFontCopyPostScriptName(menlo) as String) == "Menlo-Regular" { return menlo }
        return UIFont.monospacedSystemFont(ofSize: CGFloat(size), weight: .regular) as CTFont
    }

    /// Draw `text` with its baseline at (`x`, `y`) in UIKit's flipped page
    /// coordinates (y down from the top).
    private static func draw(_ text: String, x: Double, y: Double, size: Double, color: UInt32, in cg: CGContext) {
        let uiColor = UIColor(red: CGFloat((color >> 16) & 0xFF) / 255, green: CGFloat((color >> 8) & 0xFF) / 255,
                              blue: CGFloat(color & 0xFF) / 255, alpha: CGFloat((color >> 24) & 0xFF) / 255)
        let attributes: [NSAttributedString.Key: Any] = [
            NSAttributedString.Key(kCTFontAttributeName as String): font(size: size),
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): uiColor.cgColor,
        ]
        let line = CTLineCreateWithAttributedString(NSAttributedString(string: text, attributes: attributes))
        cg.saveGState()
        // The page is flipped (y down); Core Text draws glyphs y up.
        cg.textMatrix = CGAffineTransform(scaleX: 1, y: -1)
        cg.textPosition = CGPoint(x: x, y: y)
        CTLineDraw(line, cg)
        cg.restoreGState()
    }

    /// The page font's advance of "M" in ems.
    static var advanceEm: Double {
        let font = font(size: 100)
        var glyph = CGGlyph()
        var character = UniChar(("M" as UnicodeScalar).value)
        guard CTFontGetGlyphsForCharacters(font, &character, &glyph, 1) else { return 0 }
        var advance = CGSize.zero
        CTFontGetAdvancesForGlyphs(font, .horizontal, &glyph, &advance, 1)
        return Double(advance.width) / 100
    }
}

/// `Diagnostics/pdf.json` (`-CNScreen pdf`, the session test): what an
/// exported PDF holds, read back with PDFKit.
struct PdfReport: Codable {
    var file: String?
    var bytes = 0
    var pages = 0
    /// A line of the song (no directive, short enough not to wrap) the PDF's text must have.
    var line: String?
    var lineFound = false
    /// Menlo's advance in ems (the layout counts 0.6).
    var fontAdvanceEm = UIKitPdfCanvas.advanceEm
    var ok = false
    var problem: String?

    init(problem: String?) {
        self.problem = problem
    }

    static func of(_ file: URL, song: String) -> PdfReport {
        var report = PdfReport(problem: nil)
        report.file = file.lastPathComponent
        report.bytes = (try? Data(contentsOf: file))?.count ?? 0
        guard let document = PDFDocument(url: file) else {
            report.problem = "PDFKit can't read the file"
            return report
        }
        report.pages = document.pageCount
        let text = squeezed((0..<document.pageCount).compactMap { document.page(at: $0)?.string }.joined(separator: "\n"))
        report.line = song.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .first { $0.count >= 12 && $0.count <= 40 && !$0.contains("{") && !$0.hasPrefix("//") }
        report.lineFound = report.line.map { text.contains(squeezed($0)) } ?? false
        report.ok = report.pages > 0 && report.lineFound && abs(report.fontAdvanceEm - 0.6) < 0.01
        if !report.ok {
            report.problem = "pages \(report.pages), line found \(report.lineFound), advance \(report.fontAdvanceEm)"
        }
        return report
    }

    /// `text` with every run of whitespace one space (PDF text comes back in runs).
    private static func squeezed(_ text: String) -> String {
        text.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }
}

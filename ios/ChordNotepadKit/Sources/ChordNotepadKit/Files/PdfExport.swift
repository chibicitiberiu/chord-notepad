import Foundation

// Export PDF's painting (Android's files/PdfExporter.kt): the session lays the
// pages out (`print_layout`, a `PaintPdfRequest`'s `PdfLayout`) and the front
// end paints them and writes the file. The drawing itself is the app's
// (`UIGraphicsPDFRenderer`, ios/ChordNotepad/App/PdfCanvas.swift); this is
// what is painted where, and the answer the session gets.

/// The countries (ISO 3166 codes) that use Letter paper, CLDR's list; the
/// same as the core's `print_layout.LETTER_TERRITORIES` and Android's
/// `LETTER_COUNTRIES`.
public let letterCountries: Set<String> = [
    "BZ", "CA", "CL", "CO", "CR", "GT", "MX", "NI", "PA", "PH", "PR", "SV", "US", "VE",
]

/// `export_pdf`'s page size for `country` (the locale's region): `letter` or `a4`.
public func paperFor(_ country: String?) -> String {
    letterCountries.contains((country ?? "").uppercased()) ? "letter" : "a4"
}

/// The colours the pages are painted in (ARGB), the desktop's (`pdf_export.py`).
public enum PdfColors {
    /// The song's text: near-black.
    public static let text: UInt32 = 0xFF1F_2328
    /// A directive's label.
    public static let dim: UInt32 = 0xFF7A_7F8A
    /// The header (the song's name) and the footer (`1 / 3`).
    public static let header: UInt32 = 0xFF7A_7F8A
}

/// What ``paintPdf(_:on:)`` paints on: the app's `UIGraphicsPDFRenderer`
/// canvas, a recorder in the tests.
public protocol PdfCanvas: AnyObject {
    /// Start page `number` (from 1), `width` by `height` points.
    func startPage(number: Int, width: Int, height: Int)
    /// Draw `text` from `x` on the baseline `y` (points from the top-left
    /// corner), `size` points, ARGB `color`.
    func drawText(_ text: String, x: Double, y: Double, size: Double, color: UInt32)
    /// Finish the page started last.
    func finishPage()
    /// The finished pages as a PDF.
    func document() throws -> Data
}

/// Paint `layout` on `canvas`, one page each: the header and the footer small
/// and grey, then the runs, labels dim. Every position comes from the layout.
public func paintPdf(_ layout: PdfLayout, on canvas: PdfCanvas) {
    let width = Int(layout.pageWidth.rounded())
    let height = Int(layout.pageHeight.rounded())
    for (index, page) in layout.pages.enumerated() {
        canvas.startPage(number: index + 1, width: width, height: height)
        canvas.drawText(layout.title, x: layout.titleX, y: layout.titleY, size: layout.smallFontSize,
                        color: PdfColors.header)
        canvas.drawText(page.footer, x: page.footerX, y: layout.footerY, size: layout.smallFontSize,
                        color: PdfColors.header)
        for line in page.lines {
            for run in line.runs {
                canvas.drawText(run.text, x: run.x, y: line.y, size: layout.fontSize,
                                color: run.dim ? PdfColors.dim : PdfColors.text)
            }
        }
        canvas.finishPage()
    }
}

/// Answers a `PaintPdfRequest`: paints its layout and writes it to the
/// session's document (an export's file of the store's, whose write offers
/// the export picker). File I/O: call ``export(_:)`` off the main actor.
public struct PdfExporter: Sendable {
    /// Replaces a document's content (``FileDocumentStore/writeBytes(id:data:)``,
    /// which says why it failed).
    public let write: @Sendable (_ id: String, _ data: Data) throws -> Void
    /// A fresh canvas for each export.
    public let newCanvas: @Sendable () -> PdfCanvas

    public init(write: @escaping @Sendable (String, Data) throws -> Void,
                newCanvas: @escaping @Sendable () -> PdfCanvas) {
        self.write = write
        self.newCanvas = newCanvas
    }

    /// Paint and write `request`'s pages: "" when written, else why not (the
    /// request's answer).
    public func export(_ request: PaintPdfRequest) -> String {
        let canvas = newCanvas()
        do {
            paintPdf(request.layout, on: canvas)
            try write(request.ref.id, try canvas.document())
            return ""
        } catch let error as DocumentStoreError {
            return error.description
        } catch {
            return "Failed to write file: \(error)"
        }
    }
}

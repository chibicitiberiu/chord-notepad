import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `PdfExporterTest`, case for case: what is painted where, the
/// answer the session gets, the paper for a country.
final class PdfExportTests: XCTestCase {
    /// Records what is painted; its document is "PDF:<pages>".
    private final class RecordingCanvas: PdfCanvas, @unchecked Sendable {
        var calls: [String] = []
        var documents = 0

        func startPage(number: Int, width: Int, height: Int) {
            calls.append("page \(number) \(width)x\(height)")
        }

        func drawText(_ text: String, x: Double, y: Double, size: Double, color: UInt32) {
            calls.append("'\(text)' at \(x),\(y) \(size) #" + String(format: "%06X", color & 0xFF_FFFF))
        }

        func finishPage() {
            calls.append("end")
        }

        func document() throws -> Data {
            documents += 1
            return Data("PDF:\(calls.filter { $0.hasPrefix("page") }.count)".utf8)
        }
    }

    private func page(_ footer: String, _ lines: PdfLine...) -> PdfPage {
        PdfPage(footer: footer, footerX: 290.0, lines: lines)
    }

    private lazy var layout = PdfLayout(
        fontSize: 9.5, footerY: 797.03, lineHeight: 12.94, pageCount: 2, pageHeight: 841.89, pageWidth: 595.28,
        pages: [
            page("1 / 2", PdfLine(runs: [PdfRun(dim: true, text: "Key: A", x: 42.52),
                                         PdfRun(dim: false, text: "A D", x: 102.52)], y: 76.0)),
            page("2 / 2", PdfLine(runs: [PdfRun(dim: false, text: "la la", x: 42.52)], y: 76.0)),
        ],
        smallFontSize: 8.0, title: "Song", titleX: 42.52, titleY: 51.07)

    private lazy var request = PaintPdfRequest(
        layout: layout,
        ref: DocumentRef(displayName: "song.pdf", id: "app:exports/U/song.pdf", location: "song.pdf"),
        requestId: 4)

    func testEveryPageOfTheLayoutAtItsSizeWithThePositionsAsGiven() {
        let canvas = RecordingCanvas()
        paintPdf(layout, on: canvas)
        XCTAssertEqual(canvas.calls, [
            "page 1 595x842",
            "'Song' at 42.52,51.07 8.0 #7A7F8A",
            "'1 / 2' at 290.0,797.03 8.0 #7A7F8A",
            "'Key: A' at 42.52,76.0 9.5 #7A7F8A",
            "'A D' at 102.52,76.0 9.5 #1F2328",
            "end",
            "page 2 595x842",
            "'Song' at 42.52,51.07 8.0 #7A7F8A",
            "'2 / 2' at 290.0,797.03 8.0 #7A7F8A",
            "'la la' at 42.52,76.0 9.5 #1F2328",
            "end",
        ])
    }

    func testLetterPagesAre612By792() {
        var letter = layout
        letter.pageWidth = 612
        letter.pageHeight = 792
        let canvas = RecordingCanvas()
        paintPdf(letter, on: canvas)
        XCTAssertEqual(canvas.calls.first, "page 1 612x792")
    }

    func testExportWritesThePagesToTheDocumentAndAnswersEmpty() {
        let canvas = RecordingCanvas()
        let written = LockedData()
        let exporter = PdfExporter(write: { id, data in written.put(id, data) }, newCanvas: { canvas })
        XCTAssertEqual(exporter.export(request), "")
        XCTAssertEqual(written.get("app:exports/U/song.pdf").map { String(decoding: $0, as: UTF8.self) }, "PDF:2")
        XCTAssertEqual(canvas.documents, 1)
    }

    func testAWriteThatFailsAnswersWithItsReason() {
        let exporter = PdfExporter(write: { _, _ in
            throw DocumentStoreError.failed("Permission denied: song.pdf (Downloads)")
        }, newCanvas: { RecordingCanvas() })
        XCTAssertEqual(exporter.export(request), "Permission denied: song.pdf (Downloads)")
        let other = PdfExporter(write: { _, _ in throw CocoaError(.fileWriteOutOfSpace) },
                                newCanvas: { RecordingCanvas() })
        XCTAssertTrue(other.export(request).hasPrefix("Failed to write file: "), other.export(request))
    }

    func testPaperFollowsTheCountry() {
        XCTAssertEqual(paperFor("US"), "letter")
        XCTAssertEqual(paperFor("ca"), "letter")
        XCTAssertEqual(paperFor("RO"), "a4")
        XCTAssertEqual(paperFor("GB"), "a4")
        XCTAssertEqual(paperFor(""), "a4")
        XCTAssertEqual(paperFor(nil), "a4")
    }

    func testTheLetterCountriesAreTheCores() throws {
        // core/chordnotepad/session/print_layout.py's LETTER_TERRITORIES.
        let source = try String(contentsOfFile: TestPython.coreDir + "/chordnotepad/session/print_layout.py",
                                encoding: .utf8)
        let start = try XCTUnwrap(source.range(of: "LETTER_TERRITORIES = frozenset({"))
        let rest = source[start.upperBound...]
        let body = rest[..<(rest.firstIndex(of: "}") ?? rest.endIndex)]
        let codes = Set(body.matches(of: /"([A-Z]{2})"/).map { String($0.output.1) })
        XCTAssertEqual(codes, letterCountries)
    }
}

private final class LockedData: @unchecked Sendable {
    private let lock = NSLock()
    private var values: [String: Data] = [:]
    func put(_ id: String, _ data: Data) { lock.withLock { values[id] = data } }
    func get(_ id: String) -> Data? { lock.withLock { values[id] } }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `RequestControllerTest` and `DocumentPickersTest` as behaviour,
/// with iOS's pickers: Save As moves a file the app made, an export is
/// answered with the store's file at once, an Insert directive's fields are
/// checked and answered from its dialog, and a PDF's pages painted once per
/// request and answered.
@MainActor
final class SessionRequestsTests: XCTestCase {
    private var snapshot = SessionSnapshot()
    private var sent: [(String, [String: Any])] = []
    private var adopted: [(URL, PickMode)] = []
    private var prepared: [(PickMode, String)] = []
    private var adoptFails = false
    private var offMain: [() -> Void] = []

    private func controller() -> RequestController {
        let adoptFails = self.adoptFails
        let adoptedBox = Box<[(URL, PickMode)]>([])
        let preparedBox = Box<[(PickMode, String)]>([])
        self.adoptedBox = adoptedBox
        self.preparedBox = preparedBox
        return RequestController(
            pending: { [unowned self] in self.snapshot.request },
            submit: { [unowned self] command in
                let json = try! command.argsJSON()
                self.sent.append((command.name, try! JSONSerialization.jsonObject(with: Data(json.utf8)) as! [String: Any]))
            },
            answered: { [unowned self] id in self.snapshot.requestAnswered(id) },
            adopt: { url, mode in
                adoptedBox.append((url, mode))
                if adoptFails { throw FileAccessError.permissionDenied }
                return DocumentRef(displayName: "song.txt", id: "bookmark:K", location: "song.txt (Downloads)")
            },
            prepareExport: { mode, name in
                preparedBox.append((mode, name))
                return DocumentRef(displayName: name, id: "app:exports/U/\(name)", location: name)
            },
            runOffMain: { [unowned self] work, done in
                self.offMain.append { done(work()) }
            },
            paint: { [paintedBox, paintAnswer] request in
                paintedBox.append(request.requestId)
                return try paintAnswer.get.answer()
            },
            paintOffMain: { [unowned self] work, done in
                self.offMain.append { done(work()) }
            })
    }

    private let paintedBox = Box<[Int]>([])
    /// What the painter answers (or throws), changed between requests.
    private let paintAnswer = Box(PaintAnswer { "" })

    private struct PaintAnswer: @unchecked Sendable {
        let answer: () throws -> String?
    }

    private struct Broken: Error, CustomStringConvertible {
        var description: String { "broken" }
    }

    private var adoptedBox = Box<[(URL, PickMode)]>([])
    private var preparedBox = Box<[(PickMode, String)]>([])

    /// Shared with the controller's `@Sendable` closures.
    private final class Box<T>: @unchecked Sendable {
        private let lock = NSLock()
        private var value: T
        init(_ value: T) { self.value = value }
        var get: T { lock.withLock { value } }
        func set(_ new: T) { lock.withLock { value = new } }
        func append<E>(_ item: E) where T == [E] { lock.withLock { value.append(item) } }
    }

    private func pend(_ output: SessionOutput) {
        snapshot.apply(output)
    }

    private func runOffMain() {
        let work = offMain
        offMain.removeAll()
        work.forEach { $0() }
    }

    private func assertResponded(_ id: Int, _ value: Any?, file: StaticString = #filePath, line: UInt = #line) {
        guard !sent.isEmpty else { return XCTFail("nothing sent", file: file, line: line) }
        let (name, args) = sent.removeFirst()
        XCTAssertEqual(name, "respond", file: file, line: line)
        XCTAssertEqual(args["request_id"] as? Int, id, file: file, line: line)
        switch value {
        case nil:
            XCTAssertTrue(args["value"] is NSNull, "\(args)", file: file, line: line)
        case let text as String:
            XCTAssertEqual(args["value"] as? String, text, file: file, line: line)
        case let ref as DocumentRef:
            let object = args["value"] as? [String: String]
            XCTAssertEqual(object, ["id": ref.id, "display_name": ref.displayName, "location": ref.location],
                           file: file, line: line)
        default:
            XCTFail("unexpected \(String(describing: value))", file: file, line: line)
        }
    }

    private func pick(_ id: Int, _ mode: PickMode, _ name: String = "") -> PickDocumentRequest {
        PickDocumentRequest(mode: mode, requestId: id, suggestedName: name)
    }

    private func paint(_ id: Int) -> PaintPdfRequest {
        PaintPdfRequest(
            layout: PdfLayout(fontSize: 10, footerY: 747.14, lineHeight: 13.62, pageCount: 1, pageHeight: 792,
                              pageWidth: 612, pages: [], smallFontSize: 8, title: "Song", titleX: 42.52, titleY: 51.07),
            ref: DocumentRef(displayName: "song.pdf", id: "app:exports/U/song.pdf", location: "song.pdf"),
            requestId: id)
    }

    // MARK: - DocumentPickersTest

    func testEachPickModeGetsItsPicker() async {
        XCTAssertEqual(pickerFor(pick(1, .open)), .open(contentTypes: ["public.plain-text", "public.text", "public.data"]))
        XCTAssertEqual(pickerFor(pick(1, .save, "song.txt")), .save(suggestedName: "song.txt"))
        XCTAssertEqual(pickerFor(pick(1, .exportMidi, "song.mid")), .export(.exportMidi, suggestedName: "song.mid"))
        XCTAssertEqual(pickerFor(pick(1, .exportAudio, "song.wav")), .export(.exportAudio, suggestedName: "song.wav"))
        XCTAssertEqual(pickerFor(pick(1, .exportPdf, "song.pdf")), .export(.exportPdf, suggestedName: "song.pdf"))
    }

    func testAnEmptySuggestionFallsBackToUntitledWithTheExtension() async {
        XCTAssertEqual(pickerFor(pick(1, .save)), .save(suggestedName: "Untitled.txt"))
        XCTAssertEqual(pickerFor(pick(1, .exportMidi)), .export(.exportMidi, suggestedName: "Untitled.mid"))
        XCTAssertEqual(pickerFor(pick(1, .exportAudio)), .export(.exportAudio, suggestedName: "Untitled.wav"))
        XCTAssertEqual(pickerFor(pick(1, .exportPdf)), .export(.exportPdf, suggestedName: "Untitled.pdf"))
    }

    // MARK: - RequestControllerTest

    func testEachRequestKindGetsItsPresentation() async {
        let discard = SessionRequest.confirmDiscard(ConfirmDiscardRequest(requestId: 1))
        XCTAssertEqual(presentationOf(discard), .dialog(discard))
        XCTAssertEqual(presentationOf(.pickDocument(pick(2, .open))), .picker(pick(2, .open)))
        let insert = SessionRequest.insertDirective(InsertDirectiveRequest(
            existingLabels: [], keyOptions: [], kind: "bpm", notation: "american", requestId: 4))
        XCTAssertEqual(presentationOf(insert), .dialog(insert))
        XCTAssertEqual(presentationOf(.paintPdf(paint(5))), .paint(paint(5)))
    }

    func testTheSnapshotKeepsTheNewestRequestUntilItIsAnswered() async {
        pend(.confirmDiscardRequest(ConfirmDiscardRequest(requestId: 1)))
        XCTAssertEqual(snapshot.request?.requestId, 1)
        pend(.pickDocumentRequest(pick(2, .open)))
        XCTAssertEqual(snapshot.request, .pickDocument(pick(2, .open)))
        snapshot.requestAnswered(1)
        XCTAssertEqual(snapshot.request?.requestId, 2, "an older answer doesn't clear a newer request")
        snapshot.requestAnswered(2)
        XCTAssertNil(snapshot.request)
        pend(.pickDocumentRequest(pick(3, .open)))
        snapshot.requestAnswered(nil)
        XCTAssertNil(snapshot.request, "restore_draft drops it")
    }

    func testOpenLaunchesThePickerOnceAndAnswersWithTheAdoptedRef() async {
        let c = controller()
        pend(.pickDocumentRequest(pick(7, .open)))
        XCTAssertEqual(c.onPending(snapshot.request), .open(contentTypes: openContentTypes))
        // The same request seen again: no second picker.
        XCTAssertNil(c.onPending(snapshot.request))
        XCTAssertNil(c.takePickerLaunch())

        let url = URL(fileURLWithPath: "/private/var/mobile/song.txt")
        c.onPicked(url)
        XCTAssertTrue(sent.isEmpty, "adopting is file I/O: off the main actor")
        runOffMain()
        XCTAssertEqual(adoptedBox.get.map(\.0), [url])
        XCTAssertEqual(adoptedBox.get.map(\.1), [.open])
        assertResponded(7, DocumentRef(displayName: "song.txt", id: "bookmark:K", location: "song.txt (Downloads)"))
        XCTAssertNil(snapshot.request)
    }

    func testSaveAsMovesAFileWithTheSuggestedNameAndAdoptsWhereItWent() async {
        let c = controller()
        pend(.pickDocumentRequest(pick(1, .save, "song.txt")))
        XCTAssertEqual(c.takePickerLaunch(), .save(suggestedName: "song.txt"))
        let moved = URL(fileURLWithPath: "/private/var/mobile/Library/Mobile Documents/song.txt")
        c.onPicked(moved)
        runOffMain()
        XCTAssertEqual(adoptedBox.get.map(\.0), [moved])
        XCTAssertEqual(adoptedBox.get.map(\.1), [.save])
        assertResponded(1, DocumentRef(displayName: "song.txt", id: "bookmark:K", location: "song.txt (Downloads)"))
    }

    func testAnExportIsAnsweredAtOnceWithTheStoresFileAndNoPicker() async {
        let c = controller()
        pend(.pickDocumentRequest(pick(2, .exportMidi, "song.mid")))
        XCTAssertNil(c.onPending(snapshot.request), "the export picker opens once the file is written")
        XCTAssertTrue(sent.isEmpty, "the file is made off the main actor")
        runOffMain()
        XCTAssertEqual(preparedBox.get.map(\.1), ["song.mid"])
        assertResponded(2, DocumentRef(displayName: "song.mid", id: "app:exports/U/song.mid", location: "song.mid"))
        XCTAssertNil(c.onPending(snapshot.request))
        XCTAssertTrue(adoptedBox.get.isEmpty)

        pend(.pickDocumentRequest(pick(3, .exportAudio, "song.wav")))
        XCTAssertNil(c.onPending(snapshot.request))
        XCTAssertNil(c.onPending(snapshot.request))
        runOffMain()
        XCTAssertEqual(preparedBox.get.map(\.0), [.exportMidi, .exportAudio], "once per request")
        assertResponded(3, DocumentRef(displayName: "song.wav", id: "app:exports/U/song.wav", location: "song.wav"))
    }

    func testBackingOutOfThePickerCancelsWithNull() async {
        let c = controller()
        pend(.pickDocumentRequest(pick(3, .save, "Untitled.txt")))
        _ = c.onPending(snapshot.request)
        c.onPicked(nil)
        assertResponded(3, nil)
        XCTAssertTrue(offMain.isEmpty)
        XCTAssertNil(snapshot.request)
    }

    func testADocumentThatCantBeAdoptedAnswersNull() async {
        adoptFails = true
        let c = controller()
        pend(.pickDocumentRequest(pick(4, .open)))
        _ = c.onPending(snapshot.request)
        c.onPicked(URL(fileURLWithPath: "/gone.txt"))
        runOffMain()
        assertResponded(4, nil)
    }

    func testAStalePickerResultIsIgnored() async {
        let c = controller()
        // Nothing pending.
        c.onPicked(URL(fileURLWithPath: "/song.txt"))
        // A pick request the picker wasn't opened for.
        pend(.pickDocumentRequest(pick(5, .open)))
        c.onPicked(URL(fileURLWithPath: "/song.txt"))
        runOffMain()
        XCTAssertTrue(sent.isEmpty)
        XCTAssertTrue(adoptedBox.get.isEmpty)
    }

    func testANewPickRequestGetsItsOwnPicker() async {
        let c = controller()
        pend(.pickDocumentRequest(pick(1, .open)))
        _ = c.takePickerLaunch()
        c.onPicked(nil)
        pend(.pickDocumentRequest(pick(2, .open)))
        XCTAssertEqual(c.onPending(snapshot.request), .open(contentTypes: openContentTypes))
    }

    func testUnsavedChangesAnswersSaveDiscardOrCancel() async {
        let c = controller()
        for (choice, value) in [(DiscardChoice.save, "save"), (.discard, "discard"), (.cancel, "cancel")] {
            let request = ConfirmDiscardRequest(requestId: 10)
            pend(.confirmDiscardRequest(request))
            XCTAssertNil(c.onPending(snapshot.request), "a dialog, not a picker")
            XCTAssertTrue(sent.isEmpty)
            c.answerDiscard(request, choice)
            assertResponded(10, value)
            XCTAssertNil(snapshot.request)
        }
        // Dismissing the dialog is Cancel.
        pend(.confirmDiscardRequest(ConfirmDiscardRequest(requestId: 11)))
        c.answerDiscard(ConfirmDiscardRequest(requestId: 11), nil)
        assertResponded(11, "cancel")
    }

    func testAPdfIsPaintedOffTheMainActorOncePerRequestAndAnswered() async {
        let c = controller()
        pend(.paintPdfRequest(paint(30)))
        XCTAssertNil(c.onPending(snapshot.request))
        // The same request seen again: not painted twice.
        XCTAssertNil(c.onPending(snapshot.request))
        XCTAssertTrue(paintedBox.get.isEmpty && sent.isEmpty)
        runOffMain()
        XCTAssertEqual(paintedBox.get, [30])
        assertResponded(30, "")
        XCTAssertNil(snapshot.request)

        paintAnswer.set(PaintAnswer { "Permission denied: song.pdf" })
        pend(.paintPdfRequest(paint(31)))
        _ = c.onPending(snapshot.request)
        runOffMain()
        assertResponded(31, "Permission denied: song.pdf")

        // A painter that throws still answers, with what went wrong.
        paintAnswer.set(PaintAnswer { throw Broken() })
        pend(.paintPdfRequest(paint(32)))
        _ = c.onPending(snapshot.request)
        runOffMain()
        assertResponded(32, "Broken: broken")
        XCTAssertEqual(paintedBox.get, [30, 31, 32])
        XCTAssertTrue(sent.isEmpty)
    }

    func testAnInsertDialogChecksItsFieldsAndAnswersThem() async {
        // Android's SessionRequests: the dialog stays until it is answered;
        // the fields go to check_directive as they change, Insert answers them.
        let c = controller()
        let insert = InsertDirectiveRequest(existingLabels: ["verse"], keyOptions: [], kind: "label",
                                            notation: "american", requestId: 21)
        pend(.insertDirectiveRequest(insert))
        XCTAssertNil(c.onPending(snapshot.request))
        XCTAssertTrue(sent.isEmpty, "not cancelled: the screen shows its dialog")
        XCTAssertEqual(snapshot.request, .insertDirective(insert))
        c.checkDirective(insert, ["label": "chorus"])
        let (name, args) = sent.removeFirst()
        XCTAssertEqual(name, "check_directive")
        XCTAssertEqual(args["kind"] as? String, "label")
        XCTAssertEqual(args["request_id"] as? Int, 21)
        XCTAssertEqual(args["fields"] as? [String: String], ["label": "chorus"])
        XCTAssertEqual(snapshot.request, .insertDirective(insert), "a check leaves the request pending")
        c.answerDirective(insert, ["label": "chorus"])
        let (respond, answer) = sent.removeFirst()
        XCTAssertEqual(respond, "respond")
        XCTAssertEqual(answer["request_id"] as? Int, 21)
        XCTAssertEqual(answer["value"] as? [String: String], ["label": "chorus"])
        XCTAssertNil(snapshot.request)
        // Cancel answers null.
        pend(.insertDirectiveRequest(insert))
        c.cancel(.insertDirective(insert))
        assertResponded(21, nil)
    }

    func testCancelAnswersEveryKindWithNullOrCancel() async {
        let c = controller()
        c.cancel(.confirmDiscard(ConfirmDiscardRequest(requestId: 1)))
        assertResponded(1, "cancel")
        c.cancel(.pickDocument(pick(2, .open)))
        assertResponded(2, nil)
        c.cancel(.paintPdf(paint(3)))
        assertResponded(3, nil)
    }

    func testNothingPendingDoesNothing() async {
        XCTAssertNil(controller().onPending(nil))
        XCTAssertTrue(sent.isEmpty)
    }
}

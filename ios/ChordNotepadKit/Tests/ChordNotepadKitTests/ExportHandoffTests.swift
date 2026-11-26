import ChordNotepadKit
import Foundation
import XCTest

/// "Preparing export…", the export picker after it and the snackbars meanwhile
/// (docs/IOS.md "Files", Exports).
final class ExportHandoffTests: XCTestCase {
    private let id = "app:exports/1/song.wav"
    private let file = URL(fileURLWithPath: "/tmp/exports/1/song.wav")

    private func preparing(_ progress: Double? = nil, kind: String = "audio", written: Bool = false) -> ExportState {
        ExportState(documentId: id, kind: kind, progress: progress, written: written)
    }

    func testTheDialogShowsFromThePickUntilThePickerIsUp() {
        var handoff = ExportHandoff()
        XCTAssertNil(handoff.dialog(nil))
        XCTAssertNil(handoff.dialog(ExportState(documentId: nil, kind: "", progress: nil, written: false)))
        XCTAssertEqual(handoff.dialog(preparing(0.42)), ExportDialog(documentId: id, kind: "audio", progress: 0.42))
        XCTAssertEqual(handoff.dialog(preparing(0.42))?.percent, "42%")
        XCTAssertNil(handoff.dialog(preparing(kind: "midi"))?.percent)

        // Written: still up while the picker opens (it took 12 s on a Mac's simulator).
        XCTAssertTrue(handoff.written(ExportFile(id: id, file: file)))
        XCTAssertNotNil(handoff.dialog(preparing(1, written: true)))
        XCTAssertEqual(handoff.nextOffer(), ExportFile(id: id, file: file))
        XCTAssertNil(handoff.nextOffer(), "one picker at a time")
        XCTAssertNotNil(handoff.dialog(preparing(1, written: true)))
        XCTAssertFalse(handoff.pickerPresented(id))
        XCTAssertNil(handoff.dialog(preparing(1, written: true)))

        // Saved or not, the session is told once; the dialog doesn't come back
        // before the session's state empties.
        XCTAssertTrue(handoff.pickerDone(id))
        XCTAssertNil(handoff.dialog(preparing(1, written: true)))
        XCTAssertNil(handoff.offering)
    }

    func testAFailedExportClosesTheDialog() {
        let handoff = ExportHandoff()
        XCTAssertNotNil(handoff.dialog(preparing(0.5)))
        // The session's state empties with its error.
        XCTAssertNil(handoff.dialog(ExportState(documentId: nil, kind: "", progress: nil, written: false)))
    }

    func testCancelWhileRenderingDropsTheFileWhenItArrives() {
        var handoff = ExportHandoff()
        XCTAssertEqual(handoff.cancel(id), ExportCancel())
        XCTAssertNil(handoff.dialog(preparing(0.3)))
        XCTAssertFalse(handoff.written(ExportFile(id: id, file: file)), "deleted, no picker")
        XCTAssertNil(handoff.nextOffer())
    }

    func testCancelAfterTheWriteDropsTheWaitingFile() {
        var handoff = ExportHandoff()
        XCTAssertTrue(handoff.written(ExportFile(id: id, file: file)))
        XCTAssertEqual(handoff.cancel(id).discard, ExportFile(id: id, file: file))
        XCTAssertNil(handoff.nextOffer())
    }

    func testCancelWhileThePickerOpensClosesItOnceUp() {
        var handoff = ExportHandoff()
        XCTAssertTrue(handoff.written(ExportFile(id: id, file: file)))
        _ = handoff.nextOffer()
        let effect = handoff.cancel(id)
        XCTAssertNil(effect.discard)
        XCTAssertFalse(effect.closePicker, "not up yet")
        XCTAssertNil(handoff.dialog(preparing(1, written: true)))
        XCTAssertTrue(handoff.pickerPresented(id), "close it now")
        XCTAssertFalse(handoff.pickerDone(id), "the session already knows")
    }

    func testExportsWaitTheirTurn() {
        var handoff = ExportHandoff()
        let other = ExportFile(id: "app:exports/2/song.mid", file: URL(fileURLWithPath: "/tmp/exports/2/song.mid"))
        XCTAssertTrue(handoff.written(ExportFile(id: id, file: file)))
        XCTAssertTrue(handoff.written(other))
        XCTAssertEqual(handoff.nextOffer()?.id, id)
        XCTAssertTrue(handoff.pickerDone(id))
        XCTAssertEqual(handoff.nextOffer(), other)
    }

    // -- the snackbars in Edit ------------------------------------------------------------------

    private func snapshot(_ outputs: [SessionOutput]) -> SessionSnapshot {
        var snapshot = SessionSnapshot()
        for output in outputs { snapshot.apply(output) }
        return snapshot
    }

    func testAnExportsProgressIsNoSnackbarAndOnlyASaveIs() {
        var bars = Snackbars(snapshot([.statusState(StatusState(text: "Bar 1/4"))]))
        var s = snapshot([.statusState(StatusState(text: "Bar 1/4"))])
        s.apply(.exportState(preparing(0)))
        s.apply(.statusState(StatusState(text: "Exporting audio… 0%")))
        bars.update(s, mode: .edit, now: 1)
        XCTAssertNil(bars.shown)
        s.apply(.statusState(StatusState(text: "Exporting audio… 100%")))
        s.apply(.exportState(preparing(1, written: true)))
        bars.update(s, mode: .edit, now: 2)
        XCTAssertNil(bars.shown)
        // Saved: the desktop's words, as a snackbar.
        s.apply(.exportState(ExportState(documentId: nil, kind: "", progress: nil, written: false)))
        s.apply(.statusState(StatusState(text: "Exported audio: song.wav (iCloud Drive)")))
        bars.update(s, mode: .edit, now: 3)
        XCTAssertEqual(bars.shown?.text, "Exported audio: song.wav (iCloud Drive)")
    }

    func testACancelledExportSaysNothing() {
        var bars = Snackbars(snapshot([.statusState(StatusState(text: "Bar 1/4"))]))
        var s = snapshot([.statusState(StatusState(text: "Bar 1/4"))])
        s.apply(.exportState(preparing(kind: "midi", written: true)))
        s.apply(.statusState(StatusState(text: "Exporting MIDI: song.mid...")))
        bars.update(s, mode: .edit, now: 1)
        s.apply(.exportState(ExportState(documentId: nil, kind: "", progress: nil, written: false)))
        s.apply(.statusState(StatusState(text: "Bar 1/4")))
        bars.update(s, mode: .edit, now: 2)
        XCTAssertNil(bars.shown)
        // The next status is news again.
        s.apply(.statusState(StatusState(text: "Saved: song.txt")))
        bars.update(s, mode: .edit, now: 3)
        XCTAssertEqual(bars.shown?.text, "Saved: song.txt")
    }
}

import ChordNotepadKit
import UIKit
import XCTest

@testable import ChordNotepad

/// The app's session in the simulator, the way the app starts it (the
/// bundled Python, the core, FluidSynth.framework), with the core's
/// FakePlayer instead of live audio: CI's runners may have no audio device,
/// and the live player is checked in its own, non-blocking step
/// (docs/IOS.md, "CI").
///
/// A process has one interpreter and one session, so this is one scenario.
@MainActor
final class SessionTests: XCTestCase {
    func testTheAppSessionOpensTheQuickStartSongAuditionsAndRendersSound() async throws {
        let model = AppModel()
        await model.start(fakePlayer: true)
        XCTAssertEqual(model.phase, .running, "\(model.timings)")
        guard model.phase == .running else { return }

        // The quick-start song arrives as TextEdited plus the states.
        let opened = await model.waitFor(timeout: .seconds(120)) {
            $0.editor != nil && $0.text.contains("Twinkle, twinkle, little star,")
                && $0.document?.displayName == "01_quick_start.txt"
                && $0.highlight?.spans.isEmpty == false
        }
        XCTAssertTrue(opened, "text \(model.snapshot.text.prefix(80)); messages \(model.snapshot.messages)")
        let editor = try XCTUnwrap(model.snapshot.editor)
        XCTAssertFalse(editor.readOnly)
        XCTAssertEqual(editor.notation, "american")
        XCTAssertNotNil(model.snapshot.status)
        XCTAssertGreaterThan(model.timings.pythonBoot ?? 0, 0)

        // A tap on the first chord: no error comes back.
        let before = model.snapshot.messages
        model.audition(index: 0)
        try await Task.sleep(for: .seconds(1))
        XCTAssertEqual(model.snapshot.messages, before, "the audition reported a problem")

        // The blocking audio check: FluidSynth.framework renders the chord
        // offline (no audio driver) through the core's FluidSynth binding and the SoundFont.
        let render = try await SelfTest.offlineRender(model: model)
        XCTAssertTrue(render.ok, render.error ?? "")
        XCTAssertGreaterThan(render.peak, 1000)
        XCTAssertEqual(render.frames, 22050)

        // The whole self-test runs and saves its report; live audio is the
        // FakePlayer here, so only the offline render must pass.
        let report = await SelfTest.run(model: model)
        XCTAssertEqual(report.offlineRender?.ok, true)
        XCTAssertEqual(report.liveAudio?.session, true)
        let saved = AppPaths.diagnostics.appendingPathComponent("selftest.json")
        XCTAssertTrue(FileManager.default.fileExists(atPath: saved.path))
        let attachment = XCTAttachment(contentsOfFile: saved)
        attachment.name = "selftest.json"
        attachment.lifetime = .keepAlways
        add(attachment)
        // Export diagnostics: a zip of the Files-visible folder, with the
        // self-test report and the core's log in it.
        let archive = try Diagnostics.shared.exportArchive()
        let archiveSize = try FileManager.default.attributesOfItem(atPath: archive.path)[.size] as? Int ?? 0
        XCTAssertGreaterThan(archiveSize, 200, archive.path)
        XCTAssertEqual(try Data(contentsOf: archive).prefix(2), Data("PK".utf8), "not a zip")
        for name in ["selftest.json", "build.json", "faulthandler.log"] {
            XCTAssertTrue(FileManager.default.fileExists(
                atPath: AppPaths.sharedDiagnostics.appendingPathComponent(name).path), name)
        }
        XCTAssertTrue(FileManager.default.fileExists(
            atPath: AppPaths.sharedDiagnostics.appendingPathComponent("logs/chord-notepad.log").path))
        let zipAttachment = XCTAttachment(contentsOfFile: archive)
        zipAttachment.name = "diagnostics.zip"
        zipAttachment.lifetime = .keepAlways
        add(zipAttachment)

        try await checkTheEditor(model)

        // The chord sheet, live: shown, its buffer fetched on the bridge thread
        // through the app's source, decoded, and painted with CoreGraphics.
        let session = try XCTUnwrap(model.session)
        let source = try XCTUnwrap(model.chordSheet)
        session.submit(.setChordSheetVisible(visible: true))
        let shown = await model.waitFor(timeout: .seconds(60)) {
            $0.chordSheet?.visible == true && $0.chordSheet?.cursorIndex != nil
        }
        XCTAssertTrue(shown, "\(String(describing: model.snapshot.chordSheet))")
        let state = try XCTUnwrap(model.snapshot.chordSheet)
        source.follow(SheetRequest.of(state, height: 102))
        let deadline = ContinuousClock.now + .seconds(60)
        while source.load.loading, ContinuousClock.now < deadline {
            try await Task.sleep(for: .milliseconds(50))
        }
        let sheet = try XCTUnwrap(source.load.sheet, source.load.failure ?? "no sheet")
        XCTAssertEqual(sheet.buffer.viewId, state.activeView)
        XCTAssertEqual(sheet.buffer.height, 102)
        XCTAssertGreaterThan(sheet.buffer.slots.count, 10)
        let image = ChordSheetSnapshot.image(sheet, palette: source.palette(for: sheet, colors: .light),
                                             size: CGSize(width: 400, height: 122), scale: 2,
                                             cursorIndex: state.cursorIndex)
        XCTAssertGreaterThan(ChordSheetSnapshot.distinctColors(image), 8, "the strip painted next to nothing")
        let png = XCTAttachment(image: image)
        png.name = "chordsheet-live.png"
        png.lifetime = .keepAlways
        add(png)
        session.submit(.setChordSheetVisible(visible: false))

        XCTAssertTrue(model.snapshot.messages.allSatisfy { !$0.hasPrefix("Unexpected error") },
                      "\(model.snapshot.messages)")
    }

    /// The song editor, live: the real text view (in a window, driven by the
    /// app's controller) gets typing through UIKit's input path; the session
    /// highlights it under the editor's own token; a session edit lands in
    /// the view without being sent back; undo goes back as a user edit.
    private func checkTheEditor(_ model: AppModel) async throws {
        let editor = model.editor
        let session = try XCTUnwrap(model.session)
        XCTAssertTrue(editor.model.text.contains(EditorScript.line), "the editor has the quick-start song")
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 402, height: 600))
        let host = EditorHost()
        let view = host.textView
        let coordinator = SongEditor.Coordinator(controller: editor)
        view.delegate = coordinator
        host.frame = window.bounds
        window.addSubview(host)
        window.isHidden = false
        editor.attach(view)
        defer { editor.detach(view) }
        XCTAssertEqual(view.text, editor.model.text)
        XCTAssertFalse(editor.model.wordWrap, "word wrap is off by default")

        // Typing: set_text with a new token, then the session's highlight for it.
        let setTextsBefore = editor.sentCommands.filter { $0 == "set_text" }.count
        XCTAssertTrue(EditorScript.type(into: editor))
        XCTAssertEqual(view.text, editor.model.text)
        XCTAssertTrue(editor.model.text.contains(EditorScript.line + EditorScript.typed))
        XCTAssertGreaterThan(editor.sentCommands.filter { $0 == "set_text" }.count, setTextsBefore)
        let highlighted = await EditorScript.waitForHighlight(editor, timeout: .seconds(30))
        XCTAssertTrue(highlighted, "painted \(EditorScript.paintedChords(editor)), identity \(editor.model.identity), "
                      + "highlighted \(String(describing: editor.model.highlightedIdentity))")
        // Unwrapped, the long line makes the content wider than the view, and
        // the caret at its end was scrolled into view sideways.
        host.layoutIfNeeded()
        XCTAssertGreaterThan(host.contentSize.width, host.bounds.width,
                             "the unwrapped text scrolls sideways: \(view.layoutDescription)")
        XCTAssertGreaterThan(host.contentOffset.x, 0, view.layoutDescription)
        XCTAssertTrue(view.caretOnScreen, view.layoutDescription)
        // The view's typing attributes are plain (not the chord's blue) after the chord line.
        let typingColor = view.typingAttributes[.foregroundColor] as? UIColor
        XCTAssertEqual(typingColor, EditorPalette.forScheme(dark: view.traitCollection.userInterfaceStyle == .dark)
                        .text.uiColor)

        // A session edit: in the view, at the session's place, not echoed.
        let setTexts = editor.sentCommands.filter { $0 == "set_text" }.count
        session.submit(.insertText(at: 0, text: "{capo: 2}\n"))
        let inserted = await model.waitFor(timeout: .seconds(30)) { _ in editor.model.text.hasPrefix("{capo: 2}\n") }
        XCTAssertTrue(inserted)
        XCTAssertEqual(view.text, editor.model.text)
        XCTAssertEqual(editor.sentCommands.filter { $0 == "set_text" }.count, setTexts, "the session's edit was sent back")
        XCTAssertTrue(editor.model.canUndo)

        // Undo: the insert goes, and the text goes back to the session as a user edit.
        editor.perform(.undo)
        XCTAssertFalse(editor.model.text.hasPrefix("{capo: 2}"))
        XCTAssertEqual(view.text, editor.model.text)
        XCTAssertEqual(editor.sentCommands.filter { $0 == "set_text" }.count, setTexts + 1)
        // Through the text view's undo manager too (the Edit menu, shake): redo.
        XCTAssertTrue(view.undoManager?.canRedo ?? false)
        view.undoManager?.redo()
        XCTAssertTrue(editor.model.text.hasPrefix("{capo: 2}\n"))
        XCTAssertEqual(view.text, editor.model.text)

        // A paste that needs normalising goes in normalised.
        XCTAssertEqual(editor.willReplace(NSRange(location: 0, length: 0), with: "C\u{00A0}G\r\n"),
                       .replace("C G\n"))

        let image = UIGraphicsImageRenderer(bounds: view.bounds).image { context in
            view.layer.render(in: context.cgContext)
        }
        let png = XCTAttachment(image: image)
        png.name = "editor-live.png"
        png.lifetime = .keepAlways
        add(png)
        window.isHidden = true
    }
}

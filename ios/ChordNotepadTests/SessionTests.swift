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

        XCTAssertTrue(model.snapshot.messages.allSatisfy { !$0.hasPrefix("Unexpected error") },
                      "\(model.snapshot.messages)")
    }
}

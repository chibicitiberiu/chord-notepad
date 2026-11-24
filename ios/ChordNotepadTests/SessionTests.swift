import ChordNotepadKit
import UIKit
import UniformTypeIdentifiers
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

        // The bundled song has a store id, so it opens in Play, as a saved song does on Android.
        XCTAssertEqual(model.ui.mode, .play)
        model.selectMode(.edit)
        try await checkTheEditor(model)
        try await checkPlayMode(model)

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

        try await checkFiles(model)
        try await checkSheetsAndTools(model)
        try await checkSettingsAndAbout(model)
        try await checkTheEditorsFeatures(model)

        XCTAssertTrue(model.snapshot.messages.allSatisfy { !$0.hasPrefix("Unexpected error") },
                      "\(model.snapshot.messages)")
    }

    /// Files, live: the app's real store (bookmarks, the security scope,
    /// NSFileCoordinator) on files in the app's Documents, with a stand-in
    /// for the system's pickers, which CI can't drive: Open (after the
    /// unsaved-changes question), a change saved in place, Save As (the
    /// empty file moved), Export MIDI (the store's file offered, then
    /// deleted), a second store reading the same lists (a relaunch), a song
    /// opened from Files and renamed, an example, a recent song that has gone,
    /// and New with its question answered Cancel, then Don't save.
    private func checkFiles(_ model: AppModel) async throws {
        let session = try XCTUnwrap(model.session)
        let store = try XCTUnwrap(model.store)
        let folder = AppPaths.documents.appendingPathComponent("session-test", isDirectory: true)
        try? FileManager.default.removeItem(at: folder)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let morningText = "{bpm: 90}\nC        G        Am       F\nMorning has broken\n"
        let morning = folder.appendingPathComponent("Morning.txt")
        try Data(morningText.utf8).write(to: morning)
        let picker = StandInPicker()
        model.picker = picker

        // Open…: the quick-start song has the editor check's changes, so the
        // session asks about them first.
        picker.openAnswer = morning
        model.choose(.open)
        _ = await model.waitFor(timeout: .seconds(30)) { snapshot in
            if case .confirmDiscard? = snapshot.request { return true }
            return snapshot.document?.displayName == "Morning.txt"
        }
        if case .confirmDiscard? = model.snapshot.request {
            model.answerDiscard(.discard)
        }
        let opened = await model.waitFor(timeout: .seconds(30)) {
            $0.document?.displayName == "Morning.txt" && $0.text.contains("Morning has broken")
        }
        XCTAssertTrue(opened, "document \(String(describing: model.snapshot.document)); messages \(model.snapshot.messages)")
        XCTAssertEqual(picker.calls.first, "open public.plain-text,public.text,public.data")
        let morningId = try XCTUnwrap(model.snapshot.document?.documentId)
        XCTAssertTrue(morningId.hasPrefix("bookmark:"), morningId)
        XCTAssertEqual(model.snapshot.document?.location, "Morning.txt (session-test)")
        XCTAssertEqual(model.ui.mode, .play, "an opened song is in Play")
        XCTAssertNil(model.snapshot.request)

        // A change, saved in place through the bookmark.
        session.submit(.insertText(at: 0, text: "{key: C}\n"))
        _ = await model.waitFor(timeout: .seconds(30)) { $0.document?.isModified == true }
        model.save()
        let saved = await model.waitFor(timeout: .seconds(30)) { $0.document?.isModified == false }
        XCTAssertTrue(saved, "\(model.snapshot.messages)")
        XCTAssertEqual(try String(contentsOf: morning, encoding: .utf8), "{key: C}\n" + morningText)

        // Save As: the picker moves an empty file with the suggested name; the song is written there.
        let copy = folder.appendingPathComponent("Morning copy.txt")
        picker.moveTarget = copy
        model.choose(.saveAs)
        let savedAs = await model.waitFor(timeout: .seconds(30)) { $0.document?.displayName == "Morning copy.txt" }
        XCTAssertTrue(savedAs, "\(String(describing: model.snapshot.document)); \(model.snapshot.messages)")
        XCTAssertEqual(picker.calls.last, "move Morning.txt")
        XCTAssertEqual(try String(contentsOf: copy, encoding: .utf8), "{key: C}\n" + morningText)
        let copyId = try XCTUnwrap(model.snapshot.document?.documentId)
        XCTAssertNotEqual(copyId, morningId)
        // The recent list follows the document's state.
        let listed = await model.waitFor(timeout: .seconds(10)) {
            $0.recentDocuments?.items.prefix(2).map(\.id) == [copyId, morningId]
        }
        XCTAssertTrue(listed, "\(String(describing: model.snapshot.recentDocuments))")

        // Export MIDI: the store's file, offered with the export picker once written, then deleted.
        let exports = folder.appendingPathComponent("exports", isDirectory: true)
        try FileManager.default.createDirectory(at: exports, withIntermediateDirectories: true)
        picker.exportFolder = exports
        model.choose(.exportMidi)
        let exported = await model.waitFor(timeout: .seconds(60)) { _ in picker.exported != nil }
        XCTAssertTrue(exported, "\(picker.calls); \(model.snapshot.messages)")
        if let file = picker.exported {
            XCTAssertEqual(file.lastPathComponent, "Morning copy.mid")
            XCTAssertEqual(try Data(contentsOf: file).prefix(4), Data("MThd".utf8))
        }
        let status = await model.waitFor(timeout: .seconds(10)) { $0.status?.text == "Exported MIDI: Morning copy.mid" }
        XCTAssertTrue(status, "\(String(describing: model.snapshot.status))")
        let leftover = (try? FileManager.default.contentsOfDirectory(
            atPath: AppPaths.filesDir.appendingPathComponent("exports").path)) ?? []
        XCTAssertEqual(leftover, [], "the store's export file goes once the picker is done")
        XCTAssertEqual(model.snapshot.document?.documentId, copyId, "an export doesn't change the open document")
        // Audio needs the real player's SoundFont, which the FakePlayer has not:
        // `-CNScreen export` checks it in the live app (ci_screenshots.sh).

        // A relaunch: another store over the same lists resolves the bookmarks.
        let relaunched = AppDocumentStore.make()
        XCTAssertEqual(relaunched.recentDocuments().prefix(2).map(\.id), [copyId, morningId])
        XCTAssertEqual(try relaunched.readBytes(id: copyId), Data(("{key: C}\n" + morningText).utf8))
        XCTAssertEqual(try relaunched.describe(id: morningId)?.displayName, "Morning.txt")
        _ = store

        // A song opened from Files (onOpenURL), then renamed in place (the id stays).
        let evening = folder.appendingPathComponent("Evening.txt")
        try Data("{key: Am}\nAm       Dm       E7\nEvening falls\n".utf8).write(to: evening)
        model.openURL(evening)
        let fromFiles = await model.waitFor(timeout: .seconds(30)) { $0.document?.displayName == "Evening.txt" }
        XCTAssertTrue(fromFiles, "\(String(describing: model.snapshot.document)); \(model.snapshot.messages)")
        let eveningId = model.snapshot.document?.documentId
        model.rename("Evening song")
        let renamed = await model.waitFor(timeout: .seconds(30)) { $0.document?.displayName == "Evening song.txt" }
        XCTAssertTrue(renamed, "\(String(describing: model.snapshot.renameFailure)); \(model.snapshot.messages)")
        XCTAssertEqual(model.snapshot.document?.documentId, eveningId)
        XCTAssertTrue(FileManager.default.fileExists(atPath: folder.appendingPathComponent("Evening song.txt").path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: evening.path))

        // An example: a copy in Application Support, opened.
        let example = try XCTUnwrap(AppDocumentStore.exampleNames.first { $0.hasPrefix("02_") })
        model.openExample(example)
        let exampleOpened = await model.waitFor(timeout: .seconds(30)) { $0.document?.displayName == example }
        XCTAssertTrue(exampleOpened, "\(AppDocumentStore.exampleNames); \(model.snapshot.messages)")
        XCTAssertEqual(model.snapshot.document?.documentId, "app:examples/\(example)")

        // A recent song whose file has gone: the store's message, and it leaves Recent.
        try FileManager.default.removeItem(at: morning)
        let morningRef = try XCTUnwrap(model.snapshot.recentDocuments?.items.first { $0.id == morningId })
        let messagesBefore = model.snapshot.messageCount
        model.choose(.openRecent(morningRef))
        let failed = await model.waitFor(timeout: .seconds(30)) { $0.messageCount > messagesBefore }
        XCTAssertTrue(failed)
        XCTAssertTrue(model.snapshot.messages.last?.contains("Failed to open file:\nMorning.txt (session-test)") == true,
                      "\(model.snapshot.messages)")
        XCTAssertTrue(model.snapshot.messages.last?.contains("File not found") == true, "\(model.snapshot.messages)")
        // The session publishes the pruned list after the error.
        let pruned = await model.waitFor(timeout: .seconds(10)) {
            $0.recentDocuments?.items.contains { $0.id == morningId } == false
        }
        XCTAssertTrue(pruned, "\(String(describing: model.snapshot.recentDocuments))")

        // New with changes: Cancel keeps the song, Don't save gives an empty one in Edit.
        session.submit(.insertText(at: 0, text: "{capo: 1}\n"))
        _ = await model.waitFor(timeout: .seconds(30)) { $0.document?.isModified == true }
        model.choose(.newSong)
        var asked = await model.waitFor(timeout: .seconds(30)) {
            if case .confirmDiscard? = $0.request { return true }
            return false
        }
        XCTAssertTrue(asked)
        model.answerDiscard(.cancel)
        XCTAssertNil(model.snapshot.request)
        try await Task.sleep(for: .milliseconds(500))
        XCTAssertEqual(model.snapshot.document?.displayName, example, "Cancel keeps the song")
        model.choose(.newSong)
        asked = await model.waitFor(timeout: .seconds(30)) {
            if case .confirmDiscard? = $0.request { return true }
            return false
        }
        XCTAssertTrue(asked)
        model.answerDiscard(.discard)
        let fresh = await model.waitFor(timeout: .seconds(30)) {
            $0.document?.documentId == nil && $0.document?.isModified == false
        }
        XCTAssertTrue(fresh, "\(String(describing: model.snapshot.document))")
        XCTAssertEqual(model.ui.mode, .edit, "a new song is in Edit")
        model.picker = SystemDocumentPicker()
        try? FileManager.default.removeItem(at: folder)
    }

    /// The player's sheets and the ribbon's tools, live, through the app's
    /// own path (`AppModel.sheet`, the kit's reducer, the session): the speed
    /// sheet's slider, Manual… and Reset; Playback settings' Write into song;
    /// Transpose, Insert › Tempo with the session's check, Suggest Capo and the
    /// chord identifier's Insert, each checked in the editor's text.
    private func checkSheetsAndTools(_ model: AppModel) async throws {
        let editor = model.editor
        model.openQuickStart()
        let opened = await model.waitFor(timeout: .seconds(60)) {
            $0.document?.displayName == "01_quick_start.txt" && $0.highlight?.spans.isEmpty == false
        }
        XCTAssertTrue(opened, "\(String(describing: model.snapshot.document))")
        XCTAssertTrue(editor.model.text.hasPrefix("{bpm: 190} {time: 4/4} {key: C}\n"))

        // Speed: the slider snaps to 5 % and the session follows; Manual… checks the value first.
        model.sheet(.open(.speed(manual: false)))
        XCTAssertEqual(model.ui.route, .speed(manual: false))
        model.sheet(.speedDragged(148))
        var done = await model.waitFor(timeout: .seconds(10)) { $0.toolbar?.multiplierPct == 150 }
        XCTAssertTrue(done, "\(String(describing: model.snapshot.toolbar?.multiplierPct))")
        XCTAssertNil(model.ui.tools.speedSlider.dragged, "the thumb lets go once the session has the value")
        model.sheet(.speedManual)
        model.sheet(.speedTyped("500"))
        model.sheet(.speedOK)
        XCTAssertEqual(model.ui.route, .speed(manual: true), "500 isn't a speed: the dialog stays")
        XCTAssertEqual(model.ui.tools.speedEntry?.showError, true)
        model.sheet(.speedTyped("80"))
        model.sheet(.speedOK)
        done = await model.waitFor(timeout: .seconds(10)) { $0.toolbar?.multiplierPct == 80 }
        XCTAssertTrue(done)
        XCTAssertEqual(model.ui.route, .speed(manual: false))
        model.sheet(.speedReset)
        done = await model.waitFor(timeout: .seconds(10)) { $0.toolbar?.multiplierPct == 100 }
        XCTAssertTrue(done)
        model.sheet(.done)
        XCTAssertEqual(model.ui.route, MainRoute.none)

        // Playback settings: every value is set by a directive in the quick-start song.
        model.sheet(.open(.songDefaults))
        let defaults = try XCTUnwrap(model.snapshot.songDefaults)
        XCTAssertTrue(defaults.tempo.fromDirective && defaults.time.fromDirective && defaults.key.fromDirective)
        XCTAssertFalse(defaults.anythingToWrite)
        model.sheet(.editDirective(defaults.key.directiveOffset ?? 0))
        XCTAssertEqual(model.ui.mode, .edit, "Edit under a value goes to Edit")
        XCTAssertEqual(model.ui.route, MainRoute.none)

        // Transpose the whole song up two semitones from the ribbon.
        var revision = model.snapshot.textRevision
        model.sheet(.ribbon(.transpose))
        XCTAssertEqual(model.ui.route, .transpose(selection: false))
        model.sheet(.transposeUp)
        model.sheet(.transposeUp)
        model.sheet(.transposeOK)
        done = await model.waitFor(timeout: .seconds(30)) { $0.textRevision > revision }
        XCTAssertTrue(done)
        XCTAssertTrue(editor.model.text.hasPrefix("{bpm: 190} {time: 4/4} {key: D}\n"), "\(editor.model.text.prefix(60))")
        XCTAssertEqual(chordsAbove("Twinkle, twinkle, little star,", in: editor.model.text), ["D", "D/F#", "G", "D"])

        // Insert › Tempo: the dialog's fields checked by the session; Insert only once they're clean.
        caretAtStart(editor)
        model.sheet(.ribbon(.insert))
        XCTAssertEqual(model.ui.route, .insert)
        model.sheet(.insert(.bpm))
        var asked = await model.waitFor(timeout: .seconds(30)) {
            if case .insertDirective? = $0.request { return true }
            return false
        }
        XCTAssertTrue(asked)
        model.sheet(.directiveShown)
        var form = try XCTUnwrap(model.ui.tools.directive?.form)
        form.bpm = "999"
        model.sheet(.directiveChanged(form))
        let checked = await model.waitFor(timeout: .seconds(10)) { $0.directiveCheck?.fields["value"]?.stringValue == "999" }
        XCTAssertTrue(checked)
        guard case .insertDirective(let request)? = model.snapshot.request else { return XCTFail("no request") }
        XCTAssertFalse(model.ui.directiveVerdict(for: request, snapshot: model.snapshot).messages.isEmpty)
        form.bpm = "110"
        model.sheet(.directiveChanged(form))
        let clean = await model.waitFor(timeout: .seconds(10)) { $0.directiveCheck?.fields["value"]?.stringValue == "110" }
        XCTAssertTrue(clean)
        XCTAssertTrue(model.ui.directiveVerdict(for: request, snapshot: model.snapshot).canInsert)
        revision = model.snapshot.textRevision
        model.sheet(.directiveInsert)
        XCTAssertNil(model.snapshot.request)
        done = await model.waitFor(timeout: .seconds(30)) { $0.textRevision > revision }
        XCTAssertTrue(done)
        XCTAssertTrue(editor.model.text.hasPrefix("{bpm: 110}"), "\(editor.model.text.prefix(60))")

        // Suggest Capo from the ribbon: scored at once, closed without a change.
        model.sheet(.ribbon(.capo))
        asked = await model.waitFor(timeout: .seconds(60)) {
            $0.capoAdvice?.active == true && $0.capoAdvice?.status == CapoAdviceState.ready
        }
        XCTAssertTrue(asked, "\(String(describing: model.snapshot.capoAdvice))")
        let advice = try XCTUnwrap(model.snapshot.capoAdvice)
        XCTAssertNotNil(model.ui.capoChosen(advice))
        model.sheet(.capoCancel)
        done = await model.waitFor(timeout: .seconds(10)) { $0.capoAdvice?.active == false }
        XCTAssertTrue(done)

        // The chord identifier: C, E and G tapped, C picked and inserted at the cursor.
        model.sheet(.ribbon(.identify))
        XCTAssertEqual(model.ui.route, .identify)
        // One key at a time, as a person taps: the field follows the session's
        // state after each tap (Android's IdentifierModel).
        var tapped = 0
        for key in PianoKeyboard().keys where [60, 64, 67].contains(key.midi) {
            model.sheet(.identifierTap(key))
            tapped += 1
            let count = tapped
            _ = await model.waitFor(timeout: .seconds(10)) { $0.identifier?.notes.count == count }
        }
        let named = await model.waitFor(timeout: .seconds(30)) { $0.identifier?.candidates.contains("C") == true }
        XCTAssertTrue(named, "\(String(describing: model.snapshot.identifier))")
        XCTAssertEqual(model.ui.tools.identifier.typed, model.snapshot.identifier?.notesText)
        model.sheet(.identifierPick("C", rolled: false))
        caretAtStart(editor)
        revision = model.snapshot.textRevision
        model.sheet(.identifierInsert(nil))
        done = await model.waitFor(timeout: .seconds(30)) { $0.textRevision > revision }
        XCTAssertTrue(done)
        XCTAssertTrue(editor.model.text.hasPrefix("C {bpm: 110}"), "\(editor.model.text.prefix(60))")
        model.sheet(.dismiss)
        XCTAssertEqual(model.ui.route, MainRoute.none)
    }

    /// Settings, live, through the app's own calls (the screen's taps): a
    /// General value saved at once and applied, a number saved once its
    /// typing rests (the 400 ms timer), a voicing made from a blank
    /// fretboard, renamed, given strings, then an unbuildable value the core
    /// refuses (the problems question on leaving, Edit back to it), fixed and
    /// removed; Edit voicings… from the Voicing sheet; About and the bundled
    /// licences. Everything is put back as it was.
    private func checkSettingsAndAbout(_ model: AppModel) async throws {
        model.choose(.settings)
        XCTAssertEqual(model.ui.route, .settings)
        var ok = await model.waitForSettings(timeout: .seconds(30)) {
            $0.ui.phase == .editing && $0.ui.draft != nil && $0.editor != nil
        }
        XCTAssertTrue(ok, "\(String(describing: model.settings?.ui))")
        ok = await model.waitFor(timeout: .seconds(30)) { _ in model.voicingSchema != nil }
        XCTAssertTrue(ok, "the voicings editor's schema")

        // A General value: saved at once, applied to the editor.
        let wrap = try XCTUnwrap(model.settings?.ui.draft?.wordWrap)
        model.settingsAct { $0.updateDraft { $0.wordWrap = !wrap } }
        ok = await model.waitFor(timeout: .seconds(10)) {
            $0.settings?.values.wordWrap == !wrap && $0.editor?.wordWrap == !wrap
        }
        XCTAssertTrue(ok, "word wrap saved and applied")
        model.settingsAct { $0.updateDraft { $0.wordWrap = wrap } }
        ok = await model.waitFor(timeout: .seconds(10)) { $0.settings?.values.wordWrap == wrap }
        XCTAssertTrue(ok)

        // A number typed: nothing until the typing rests, then saved; one out of range isn't.
        let bpm = try XCTUnwrap(model.snapshot.settings?.values.bpm)
        model.settingsAct { $0.setNumber(.bpm, "9") }
        model.settingsAct { $0.setNumber(.bpm, "96") }
        XCTAssertNotEqual(model.snapshot.settings?.values.bpm, 96, "saved before the typing rested")
        ok = await model.waitFor(timeout: .seconds(10)) { $0.settings?.values.bpm == 96 }
        XCTAssertTrue(ok, "the typed tempo saved once the typing rested")
        model.settingsAct { $0.setNumber(.bpm, "1000") }
        XCTAssertEqual(model.settings?.ui.numberTexts, [.bpm: "1000"])
        ok = await model.waitFor(timeout: .seconds(10)) { snapshot in
            NumberSetting.fromKeys(snapshot.voicingEditor?.stagedNumbers ?? .null) == [.bpm: "1000"]
        }
        XCTAssertTrue(ok, "the wrong number staged, not saved")
        XCTAssertEqual(model.snapshot.settings?.values.bpm, 96)
        model.settingsAct { $0.setNumber(.bpm, String(bpm)) }
        ok = await model.waitFor(timeout: .seconds(10)) { $0.settings?.values.bpm == bpm }
        XCTAssertTrue(ok)

        // A voicing: a blank fretboard, renamed, its strings typed.
        model.settingsAct { $0.openPage(.voicings) }
        model.settingsAct { $0.addVoicingFrom(VoicingPreset(group: VoicingPresetGroup.blank, label: "Blank fretboard")) }
        ok = await model.waitForSettings(timeout: .seconds(10)) {
            $0.editor?.state.model == "fretboard" && $0.editor?.state.selected?.hasPrefix("New fretboard voicing") == true
        }
        XCTAssertTrue(ok, "\(String(describing: model.settings?.editor?.state.selected))")
        let blank = try XCTUnwrap(model.settings?.editor?.state.selected)
        model.settingsAct { $0.askRename(blank) }
        XCTAssertEqual(model.settings?.ui.dialog, .rename(blank))
        model.settingsAct { $0.confirmDialog(newName: "CI 7-String") }
        ok = await model.waitForSettings(timeout: .seconds(10)) { $0.editor?.state.selected == "CI 7-String" }
        XCTAssertTrue(ok)
        model.settingsAct { $0.edit(VoicingEdits.text("tuning", "B1 E2 A2 D3 G3 B3 E4")) }
        ok = await model.waitFor(timeout: .seconds(10)) { snapshot in
            snapshot.voicingEditor?.values["tuning"] == .string("B1 E2 A2 D3 G3 B3 E4")
                && snapshot.voicingEditor?.problems.isEmpty == true
                && snapshot.voicingMenu?.groups.joined().contains { $0.label == "CI 7-String" } == true
        }
        XCTAssertTrue(ok, "the voicing saved and in the Voicing sheet")

        // Unbuildable: a string that isn't a note. Shown, not saved; leaving asks.
        model.settingsAct { $0.edit(VoicingEdits.text("tuning", "B1 E2 X9")) }
        ok = await model.waitFor(timeout: .seconds(10)) { snapshot in
            snapshot.voicingEditor?.problems.contains { $0.fieldId == "tuning" } == true
        }
        XCTAssertTrue(ok, "\(String(describing: model.snapshot.voicingEditor?.problems))")
        XCTAssertEqual(model.snapshot.voicingEditor?.invalid, ["CI 7-String"])
        XCTAssertTrue(model.snapshot.voicingEditor?.hasErrors == true)
        model.settingsAct { $0.requestClose() }
        XCTAssertEqual(model.settings?.ui.dialog, .problems, "leaving with a refused value asks first")
        XCTAssertEqual(model.ui.route, .settings)
        model.settingsAct { $0.editProblems() }
        XCTAssertEqual(model.settings?.ui.nav, SettingsNav(.voicings, voicingDetail: true))
        model.settingsAct { $0.edit(VoicingEdits.text("tuning", "B1 E2 A2 D3 G3 B3 E4")) }
        ok = await model.waitFor(timeout: .seconds(10)) { $0.voicingEditor?.problems.isEmpty == true }
        XCTAssertTrue(ok, "fixed")

        // Removed again, through its question.
        model.settingsAct { $0.askRemove("CI 7-String") }
        model.settingsAct { $0.confirmDialog() }
        ok = await model.waitFor(timeout: .seconds(10)) { snapshot in
            snapshot.voicingEditor?.groups.allSatisfy { !$0.names.contains("CI 7-String") } == true
                && snapshot.voicingMenu?.groups.joined().contains { $0.label == "CI 7-String" } == false
        }
        XCTAssertTrue(ok, "removed")
        model.settingsAct { $0.back(twoPane: false, split: false) }
        model.settingsAct { $0.back(twoPane: false, split: false) }
        model.settingsAct { $0.back(twoPane: false, split: false) }
        XCTAssertNil(model.settings, "left")
        XCTAssertEqual(model.ui.route, MainRoute.none)
        ok = await model.waitFor(timeout: .seconds(10)) { $0.voicingEditor?.active == false }
        XCTAssertTrue(ok, "the edit ended")

        // Edit voicings… in the Voicing sheet opens Settings at Voicings.
        model.sheet(.open(.voicing))
        model.sheet(.editVoicings)
        XCTAssertEqual(model.ui.route, .settings)
        XCTAssertEqual(model.settings?.ui.nav, SettingsNav(.voicings))
        ok = await model.waitForSettings(timeout: .seconds(10)) { $0.ui.phase == .editing }
        XCTAssertTrue(ok)
        model.settingsAct { $0.requestClose() }
        XCTAssertEqual(model.ui.route, MainRoute.none)

        // About and the licences the build phase put in the app.
        model.choose(.about)
        XCTAssertEqual(model.ui.route, .about)
        XCTAssertGreaterThan(AppLicences.entries.count, 20)
        let app = try XCTUnwrap(AppLicences.entries.first { $0.id == appLicenceId })
        XCTAssertTrue(AppLicences.text(app)?.contains("GNU AFFERO GENERAL PUBLIC LICENSE") == true)
        let fluidsynth = try XCTUnwrap(AppLicences.entries.first { $0.id == "fluidsynth" })
        XCTAssertTrue(AppLicences.text(fluidsynth)?.contains("GNU LESSER GENERAL PUBLIC LICENSE") == true)
        for entry in AppLicences.entries {
            XCTAssertNotNil(AppLicences.text(entry), "\(entry.id): its text isn't in the app")
        }
        model.ui.route = .licence(id: appLicenceId, fromAbout: true)
        model.pageBack()
        XCTAssertEqual(model.ui.route, .about)
        model.ui.route = .licences
        model.ui.route = .licence(id: "fluidsynth", fromAbout: false)
        model.pageBack()
        XCTAssertEqual(model.ui.route, .licences)
        model.pageBack()
        model.pageBack()
        XCTAssertEqual(model.ui.route, MainRoute.none)
    }

    /// The caret to the song's start, as a tap there puts it.
    private func caretAtStart(_ editor: EditorController) {
        editor.run { model in
            _ = model.viewChanged(text: model.text, selection: UTF16Range(0, 0), composing: false)
            return []
        }
    }

    /// The chords on the line above the first line that starts with `lyric`.
    private func chordsAbove(_ lyric: String, in text: String) -> [String] {
        let lines = text.components(separatedBy: "\n")
        guard let index = lines.firstIndex(where: { $0.hasPrefix(lyric) }), index > 0 else { return [] }
        return lines[index - 1].split(separator: " ").map(String.init)
    }

    /// Play mode, live: the same text view, frozen, with the playhead marker.
    /// A tap on a chord moves the playhead there (`tap_chord_at`), a drag from
    /// the marker moves it to the chord it ends on (`set_playhead`), both in
    /// code points; back in Edit the text is editable again.
    private func checkPlayMode(_ model: AppModel) async throws {
        let editor = model.editor
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 402, height: 600))
        let host = EditorHost()
        let view = host.textView
        let coordinator = SongEditor.Coordinator(controller: editor)
        view.delegate = coordinator
        host.frame = window.bounds
        window.addSubview(host)
        window.isHidden = false
        editor.attach(view)
        defer {
            editor.detach(view)
            window.isHidden = true
        }
        model.selectMode(.play)
        XCTAssertTrue(editor.playMode)
        XCTAssertFalse(view.isEditable)
        XCTAssertFalse(view.isSelectable)
        host.layoutIfNeeded()
        let boxes = editor.chordBoxes()
        XCTAssertGreaterThan(boxes.count, 5, view.layoutDescription)
        guard boxes.count > 5 else { return }
        func middle(_ box: ChordBox) -> CGPoint {
            CGPoint(x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2)
        }

        // A tap on the third chord.
        let third = boxes[2]
        editor.playTapped(at: middle(third))
        let thirdOffset = OffsetMapper(editor.model.text).toCodePoint(third.start)
        let tapped = await model.waitFor(timeout: .seconds(30)) { $0.playback?.playheadOffset == thirdOffset }
        XCTAssertTrue(tapped, "playhead \(String(describing: model.snapshot.playback?.playheadOffset)), wanted \(thirdOffset)")
        XCTAssertEqual(editor.markerBox()?.start, third.start)
        XCTAssertNotNil(view.markerLayer.path, "the marker is drawn")

        // A scrub from the marker to the fifth chord.
        let marker = try XCTUnwrap(editor.markerBox())
        let grab = CGPoint(x: marker.left, y: (marker.top + marker.bottom) / 2)
        XCTAssertTrue(editor.scrubGrabs(grab))
        XCTAssertFalse(editor.scrubGrabs(middle(boxes[4])), "only the marker is grabbed")
        let fifth = boxes[4]
        editor.scrubbed(.began, at: grab)
        editor.scrubbed(.changed, at: middle(fifth))
        XCTAssertEqual(editor.playhead, fifth.start, "the marker follows the finger")
        editor.scrubbed(.ended, at: middle(fifth))
        let fifthOffset = OffsetMapper(editor.model.text).toCodePoint(fifth.start)
        let scrubbed = await model.waitFor(timeout: .seconds(30)) { $0.playback?.playheadOffset == fifthOffset }
        XCTAssertTrue(scrubbed, "playhead \(String(describing: model.snapshot.playback?.playheadOffset)), wanted \(fifthOffset)")

        let image = UIGraphicsImageRenderer(bounds: view.bounds).image { context in
            view.layer.render(in: context.cgContext)
        }
        let png = XCTAttachment(image: image)
        png.name = "play-live.png"
        png.lifetime = .keepAlways
        add(png)

        model.selectMode(.edit)
        XCTAssertFalse(editor.playMode)
        XCTAssertTrue(view.isEditable)
        XCTAssertNil(view.markerLayer.path)
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

/// Stands in for the system's document pickers: answers as a user would,
/// one main-actor turn later.
@MainActor
final class StandInPicker: DocumentPicking {
    private(set) var calls: [String] = []
    /// What Open picks.
    var openAnswer: URL?
    /// Where Save As moves the file.
    var moveTarget: URL?
    /// The folder an export is copied into.
    var exportFolder: URL?
    /// Where the last export went.
    private(set) var exported: URL?

    func pickToOpen(contentTypes: [UTType], done: @escaping (URL?) -> Void) {
        calls.append("open " + contentTypes.map(\.identifier).joined(separator: ","))
        let answer = openAnswer
        DispatchQueue.main.async { done(answer) }
    }

    func pickToMove(_ file: URL, done: @escaping (URL?) -> Void) {
        calls.append("move " + file.lastPathComponent)
        guard let target = moveTarget else { return done(nil) }
        do {
            try? FileManager.default.removeItem(at: target)
            try FileManager.default.moveItem(at: file, to: target)
            DispatchQueue.main.async { done(target) }
        } catch {
            done(nil)
        }
    }

    func pickToExport(_ file: URL, done: @escaping (URL?) -> Void) {
        calls.append("export " + file.lastPathComponent)
        guard let folder = exportFolder else { return done(nil) }
        let target = folder.appendingPathComponent(file.lastPathComponent)
        do {
            try? FileManager.default.removeItem(at: target)
            try FileManager.default.copyItem(at: file, to: target)
            exported = target
            DispatchQueue.main.async { done(target) }
        } catch {
            done(nil)
        }
    }
}

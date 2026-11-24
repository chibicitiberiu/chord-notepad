import Foundation
import XCTest

@testable import ChordNotepadKit

extension IntegrationTests {
    /// Settings over the real core, as the iOS screen drives it (the
    /// controller's own commands): the edit opened with the schema, a General
    /// value saved and put back, My 7-String made from a blank fretboard as
    /// Android's help screenshots have it (`android/tools/help_shots.json`), an
    /// unbuildable value the core refuses (shown, not saved, the config on
    /// disk unchanged), the fix, Jazz Vocal Trio as an ensemble, a built-in
    /// viewed read-only, then the edit ended. Last in the session, so every
    /// scene before keeps its states; each scene waits for its own states.
    func checkSettings(_ session: Session, _ log: EventLog, _ scenes: SceneRecorder, filesDir: String) async throws {
        let songs = TestPython.repo.appendingPathComponent("android/tools/help_shot_songs")
        let grace = try String(contentsOf: songs.appendingPathComponent("amazing_grace.txt"), encoding: .utf8)
        let configFile = URL(fileURLWithPath: filesDir + "/config/chord-notepad/settings.json")

        // The scenes start at the song's restore, so they carry its text and
        // the schema (an event: only what comes after the mark is recorded).
        let mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight for Settings") {
            $0.textRevision == restored.textRevision && $0.spans.contains { $0.kind == .chord }
        }

        var controller = SettingsController()
        func send() {
            for command in controller.takeCommands() { session.submit(command) }
        }
        /// Feed the newest states to the controller, as the app does.
        func feed() throws {
            if let settings = try? log.decodeLatest(SettingsState.self, "SettingsState") {
                controller.onSettings(settings)
            }
            if let editor = try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState") {
                controller.onEditor(editor)
            }
            send()
        }
        func editor() throws -> VoicingEditorState { try log.decodeLatest(VoicingEditorState.self, "VoicingEditorState") }
        /// Wait for an active editor state newer than `revision` that `condition` accepts, and feed it.
        func waitForEditor(_ what: String, after revision: Int,
                           _ condition: @escaping (VoicingEditorState) -> Bool) async throws {
            try await log.wait(what) {
                guard let state = try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState") else {
                    return false
                }
                return state.active && state.revision > revision && condition(state)
            }
            try feed()
        }

        // -- the edit opens with the schema: General, Playback and the voicings ------------
        try feed()
        let opened = log.count
        controller.start(needSchema: true)
        send()
        try await log.wait("the voicings editor's schema") {
            !log.events(since: opened, type: "VoicingEditorSchema").isEmpty
                && (try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState"))?.active == true
        }
        try feed()
        XCTAssertEqual(controller.ui.phase, .editing)
        let schemaEvent = try log.decode(VoicingEditorSchema.self, log.events(since: opened, type: "VoicingEditorSchema").last)
        let schema = EditorSchema.parse(schemaEvent.schema)
        XCTAssertEqual(Set(schema.forms.keys), ["fretboard", "ensemble", "piano"])
        // The iOS schema's texts fall back to Android's.
        XCTAssertEqual(schema.text("errors_banner"), "Fix these errors to apply changes")
        let start = try editor()
        XCTAssertEqual(start.groups.map(\.model), ["fretboard", "piano", "ensemble"])
        XCTAssertTrue(start.groups.allSatisfy(\.names.isEmpty), "no voicings of the user's yet")
        XCTAssertEqual(controller.ui.draft, SettingsDraft.of(try log.decodeLatest(SettingsState.self, "SettingsState")))
        await log.waitQuiet()
        try await scenes.record("settings_open", "Settings open on Amazing Grace: the session's settings edit "
                                + "(begin_settings_edit) with the voicings editor's schema, the defaults, no voicings "
                                + "of the user's.", from: mark)

        // -- a General value saved at once, applied, and put back --------------------------
        let wrapBefore = controller.ui.draft!.wordWrap
        controller.updateDraft { $0.wordWrap = !wrapBefore }
        send()
        try await log.wait("word wrap saved and applied") {
            (try? log.decodeLatest(SettingsState.self, "SettingsState"))?.values.wordWrap == !wrapBefore
                && (try? log.decodeLatest(EditorState.self, "EditorState"))?.wordWrap == !wrapBefore
        }
        // A number out of range isn't saved: only staged, for next time.
        controller.setNumber(.bpm, "1000")
        controller.saveDraft()
        send()
        controller.updateDraft { $0.wordWrap = wrapBefore }
        send()
        try await log.wait("word wrap back") {
            (try? log.decodeLatest(SettingsState.self, "SettingsState"))?.values.wordWrap == wrapBefore
        }
        try await log.wait("the wrong number staged") {
            NumberSetting.fromKeys((try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState"))?
                .stagedNumbers ?? .null) == [.bpm: "1000"]
        }
        XCTAssertEqual(try log.decodeLatest(SettingsState.self, "SettingsState").values.bpm, 120, "1000 isn't saved")
        controller.setNumber(.bpm, "120")
        controller.saveDraft()
        send()
        try await log.wait("the wrong number gone") {
            NumberSetting.fromKeys((try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState"))?
                .stagedNumbers ?? .null).isEmpty
        }
        try feed()

        // -- My 7-String: a blank fretboard, renamed, its strings typed --------------------
        var revision = try editor().revision
        controller.addVoicingFrom(VoicingPreset(group: VoicingPresetGroup.blank, label: "Blank fretboard"))
        send()
        try await waitForEditor("a new fretboard voicing", after: revision) { $0.selected != nil && $0.model == "fretboard" }
        let blank = try XCTUnwrap(try editor().selected)
        XCTAssertEqual(blank, "New fretboard voicing")
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))
        revision = try editor().revision
        controller.askRename(blank)
        controller.confirmDialog(newName: "My 7-String")
        send()
        try await waitForEditor("the voicing renamed", after: revision) { $0.selected == "My 7-String" }
        revision = try editor().revision
        controller.edit(VoicingEdits.text("tuning", "B1 E2 A2 D3 G3 B3 E4"))
        send()
        try await waitForEditor("the seven strings", after: revision) {
            $0.values["tuning"] == .string("B1 E2 A2 D3 G3 B3 E4") && $0.problems.isEmpty
        }
        try await log.wait("My 7-String in the player's Voicing sheet") {
            guard let menu = try? log.decodeLatest(VoicingMenuState.self, "VoicingMenuState") else { return false }
            return menu.groups.joined().contains { $0.label == "My 7-String" }
        }
        let saved = try savedVoicing(configFile, "My 7-String")
        XCTAssertEqual(saved["tuning"] as? [Int], [35, 40, 45, 50, 55, 59, 64], "the config keeps MIDI numbers: \(saved)")
        XCTAssertFalse(controller.hasProblems)
        let form = try XCTUnwrap(schema.form(try editor().model))
        let fields = buildForm(form, values: controller.editor!.values, errors: try editor().fieldErrors,
                               hints: try editor().hints).flatMap(\.fields)
        XCTAssertEqual(fields.first { $0.spec.id == "tuning" }?.text, "B1 E2 A2 D3 G3 B3 E4")
        await log.waitQuiet()
        try await scenes.record("settings_voicing_form", "Settings › Voicings with My 7-String (a fretboard, strings "
                                + "B1 E2 A2 D3 G3 B3 E4) made from a blank fretboard and selected, as Android's help "
                                + "screenshots have it.", from: mark)

        // -- an unbuildable voicing: shown with its errors, not saved ----------------------
        // A string that isn't a note and a relaxed span under the span (a rule the
        // core checks by building the voicing): both refused.
        let relaxedSpan = fieldText(controller.editor?.values["relaxed_span"])
        XCTAssertNotEqual(relaxedSpan, "2")
        revision = try editor().revision
        controller.edit(VoicingEdits.text("tuning", "B1 E2 X9 G3"))
        controller.edit(VoicingEdits.text("relaxed_span", "2"))
        send()
        try await waitForEditor("the refused values", after: revision) {
            $0.fieldErrors.text("tuning") != nil && $0.fieldErrors.text("relaxed_span") != nil
                && $0.problems.count == 2
        }
        let refused = try editor()
        XCTAssertEqual(refused.invalid, ["My 7-String"])
        XCTAssertTrue(refused.hasErrors)
        XCTAssertEqual(refused.problems.map(\.fieldId), ["tuning", "relaxed_span"])
        XCTAssertTrue(refused.problems.allSatisfy { $0.voicing == "My 7-String" })
        XCTAssertTrue(refused.problems[0].text.contains("X9 isn't a note name"), refused.problems[0].text)
        XCTAssertEqual(try savedVoicing(configFile, "My 7-String")["tuning"] as? [Int],
                       [35, 40, 45, 50, 55, 59, 64], "the refused strings aren't saved")
        // The form shows them as typed, red; leaving asks first.
        XCTAssertEqual(controller.editor?.values["tuning"], .string("B1 E2 X9 G3"))
        XCTAssertTrue(controller.hasProblems)
        controller.requestClose()
        XCTAssertEqual(controller.ui.dialog, .problems)
        XCTAssertEqual(settingsProblemLines(controller.ui, editor: controller.editor, limits: controller.limits),
                       refused.problems.map(\.text))
        controller.dismissDialog()
        XCTAssertEqual(controller.outbox.count, 0, "asking sends nothing")
        await log.waitQuiet()
        try await scenes.record("settings_voicing_refused", "My 7-String with strings B1 E2 X9 G3 and a relaxed span of "
                                + "2: both refused (field errors, two problems, the config keeps the seven strings).",
                                from: mark)

        // The fix: saved again.
        revision = try editor().revision
        controller.edit(VoicingEdits.text("tuning", "B1 E2 A2 D3 G3 B3 E4"))
        controller.edit(VoicingEdits.text("relaxed_span", relaxedSpan))
        send()
        try await waitForEditor("the values fixed", after: revision) { $0.problems.isEmpty && !$0.hasErrors }
        XCTAssertEqual(try editor().invalid, [])
        XCTAssertFalse(controller.hasProblems)

        // -- Jazz Vocal Trio: an ensemble of three voices ----------------------------------
        revision = try editor().revision
        controller.addVoicingFrom(VoicingPreset(group: VoicingPresetGroup.blank, label: "Blank ensemble"))
        send()
        try await waitForEditor("a new ensemble voicing", after: revision) { $0.model == "ensemble" && $0.selected != nil }
        let ensembleName = try XCTUnwrap(try editor().selected)
        revision = try editor().revision
        controller.askRename(ensembleName)
        controller.confirmDialog(newName: "Jazz Vocal Trio")
        send()
        try await waitForEditor("the ensemble renamed", after: revision) { $0.selected == "Jazz Vocal Trio" }
        let template = try XCTUnwrap(records(controller.editor?.values["voices"]).first)
        let voices: [[String: JSONValue]] = [("Lead", "A3", "F5", "12"), ("Harmony", "F3", "D5", "19"),
                                             ("Bass", "E2", "C4", "12")].map { name, low, high, gap in
            var row = template
            row["name"] = .string(name)
            row["low"] = .string(low)
            row["high"] = .string(high)
            row["gap"] = .string(gap)
            return row
        }
        revision = try editor().revision
        controller.edit(.object(["voices": .array(voices.map { .object($0) }), "allow_unisons": .bool(false)]))
        send()
        try await waitForEditor("the trio's voices", after: revision) {
            records($0.values["voices"]).map { $0["name"] } == [.string("Lead"), .string("Harmony"), .string("Bass")]
                && $0.problems.isEmpty
        }
        let trio = try savedVoicing(configFile, "Jazz Vocal Trio")
        XCTAssertEqual((trio["voices"] as? [[String: Any]])?.compactMap { $0["name"] as? String },
                       ["Lead", "Harmony", "Bass"], "\(trio)")
        let trioState = try editor()
        let ensembleForm = try XCTUnwrap(schema.form("ensemble"))
        let trioForm: [FormItem] = buildForm(ensembleForm, values: controller.editor!.values,
                                             errors: trioState.fieldErrors, hints: trioState.hints)
        var trioRows: [RecordRow] = []
        for item in trioForm {
            if case .records(let r) = item { trioRows = r.rows }
        }
        let bottomGap = trioRows.last?.cells.first { $0.spec.id == "gap" }
        XCTAssertEqual(bottomGap?.enabled, false, "the bottom voice has no gap")
        await log.waitQuiet()
        try await scenes.record("settings_voicing_ensemble", "Jazz Vocal Trio (Lead A3–F5, Harmony F3–D5, Bass E2–C4, "
                                + "unisons off) made from a blank ensemble and selected, as Android's help screenshot "
                                + "of a custom ensemble has it.", from: mark)

        // -- a built-in, read-only: nothing is saved, Copy makes a voicing of it ---------------
        revision = try editor().revision
        let commandsBefore = log.count
        controller.selectBuiltin(model: "fretboard", label: "Guitar (Standard - EADGBE)")
        send()
        try await waitForEditor("the built-in shown", after: revision) { $0.showsBuiltin }
        XCTAssertTrue(log.events(since: commandsBefore, type: "UserError").isEmpty)
        controller.edit(VoicingEdits.text("tuning", "D2 A2"))
        XCTAssertEqual(controller.outbox.count, 0, "a built-in takes no edits")
        await log.waitQuiet()
        try await scenes.record("settings_builtin", "Settings › Voicings showing the built-in Guitar (Standard - EADGBE) "
                                + "read-only (select_builtin), My 7-String and Jazz Vocal Trio listed.", from: mark)

        // -- a refused rename: the session's error, nothing renamed ------------------------
        controller.selectVoicing("Jazz Vocal Trio")
        send()
        try await waitForEditor("the trio again", after: try editor().revision) { $0.selected == "Jazz Vocal Trio" }
        let errorsBefore = log.count
        controller.askRename("Jazz Vocal Trio")
        controller.confirmDialog(newName: "My 7-String")
        send()
        try await log.wait("the taken name refused") { !log.events(since: errorsBefore, type: "UserError").isEmpty }
        XCTAssertEqual(try editor().selected, "Jazz Vocal Trio")

        // -- leaving ends the edit ---------------------------------------------------------
        controller.requestClose()
        send()
        XCTAssertEqual(controller.ui.phase, .closed)
        try await log.wait("the edit ended") {
            (try? log.decodeLatest(VoicingEditorState.self, "VoicingEditorState"))?.active == false
        }
    }

    /// Voicing `name` as the config file has it now.
    private func savedVoicing(_ file: URL, _ name: String) throws -> [String: Any] {
        let config = try jsonObject(String(contentsOf: file, encoding: .utf8))
        let voicings = try XCTUnwrap(config["voicings"] as? [String: Any], "\(config.keys)")
        return try XCTUnwrap(voicings[name] as? [String: Any], "\(voicings.keys)")
    }
}

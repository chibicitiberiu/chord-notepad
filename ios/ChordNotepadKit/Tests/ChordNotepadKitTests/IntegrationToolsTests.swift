import Foundation
import XCTest

@testable import ChordNotepadKit

extension IntegrationTests {
    /// The player's sheets and the Edit ribbon's tools over the real core, on
    /// Amazing Grace as Android's help screenshots show them
    /// (`android/tools/help_shots.json`): Playback settings, the speed and the
    /// instrument, each Insert dialog with the session's check, Suggest Capo,
    /// the chord identifier and Transpose. Last in the session, so the scenes
    /// before keep their states; each scene waits for its own states.
    func checkSheetsAndTools(_ session: Session, _ log: EventLog, _ scenes: SceneRecorder) async throws {
        let songs = TestPython.repo.appendingPathComponent("android/tools/help_shot_songs")
        let tempoOnly = try String(contentsOf: songs.appendingPathComponent("amazing_grace_tempo_only.txt"),
                                   encoding: .utf8)
        let grace = try String(contentsOf: songs.appendingPathComponent("amazing_grace.txt"), encoding: .utf8)

        // -- the player's sheets: Tempo set by {bpm: 90}, 3/4 and G as this
        // song's own values (song-defaults), 125 % (speed-sheet), Steel
        // Guitar (instrument-programs) ------------------------------------------------
        var mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: tempoOnly))
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight") {
            $0.textRevision == restored.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        session.submit(.setTimeSignature(beats: 3, unit: 4))
        session.submit(.setKey(key: "G"))
        session.submit(.setMultiplierPct(pct: 125))
        session.submit(.setInstrument(program: 25))
        // Piano, as Android's help screenshots' config has it (the Scarborough
        // Fair scenes left the standard guitar on).
        session.submit(.setVoicing(voicing: "piano"))
        try await log.wait("the song's defaults, the speed, the instrument and the voicing") {
            guard let defaults = try? log.decodeLatest(SongDefaultsState.self, "SongDefaultsState"),
                  let toolbar = try? log.decodeLatest(ToolbarState.self, "ToolbarState"),
                  let instruments = try? log.decodeLatest(InstrumentMenuState.self, "InstrumentMenuState"),
                  let voicings = try? log.decodeLatest(VoicingMenuState.self, "VoicingMenuState")
            else { return false }
            return defaults.time.value == "3/4" && defaults.key.value == "G" && defaults.tempo.fromDirective
                && toolbar.multiplierPct == 125 && instruments.current == 25 && voicings.selected == "piano"
        }
        let defaults = try log.decodeLatest(SongDefaultsState.self, "SongDefaultsState")
        XCTAssertEqual(defaults.tempo.value, "90")
        XCTAssertEqual(defaults.tempo.directiveOffset, 0)
        XCTAssertFalse(defaults.time.fromDirective)
        XCTAssertTrue(defaults.canWrite)
        XCTAssertEqual(defaults.summary, "90 · 3/4 · G")
        await log.waitQuiet()
        try await scenes.record("player_sheets", "Amazing Grace in Play's sheets: Tempo set by {bpm: 90}, 3/4 and G "
                                + "as the song's own values, speed 125 %, Steel Guitar.", from: mark)

        // The speed's Reset, and Write into song: the values no directive sets
        // go in at the top, and every row is then set by a directive.
        session.submit(.resetMultiplier())
        try await log.wait("the speed back at 100 %") {
            (try? log.decodeLatest(ToolbarState.self, "ToolbarState"))?.multiplierPct == 100
        }
        var before = try log.decodeLatest(TextEdited.self, "TextEdited").textRevision
        session.submit(.writeSongDefaults())
        let written = try await waitForEdit(log, since: mark) { $0.textRevision > before }
        XCTAssertTrue(written.replacement.contains("{time: 3/4}"), written.replacement)
        XCTAssertTrue(written.replacement.contains("{key: G}"), written.replacement)
        try await log.wait("every default set by a directive") {
            (try? log.decodeLatest(SongDefaultsState.self, "SongDefaultsState"))?.anythingToWrite == false
        }

        // -- the tools, on the whole song with the cursor after "me" (Android's
        // grace_edit_cursor) ------------------------------------------------------------
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let graceEdit = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight again") {
            $0.textRevision == graceEdit.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        let me = (grace as NSString).range(of: "That saved a wretch like me\n")
        let cursor = OffsetMapper(grace).toCodePoint(NSMaxRange(me))
        await log.waitQuiet()

        // Each Insert dialog: the request, and for two of them the session's
        // check of typed fields (an error for the tempo, a clean label).
        let checks: [DirectiveKind: [String: String]] = [.bpm: ["value": "999"], .label: ["label": "chorus"]]
        for entry in insertEntries {
            let asked = log.count
            session.submit(.requestInsertDirective(at: cursor, kind: entry.kind.wire))
            try await log.wait("the \(entry.kind) request") {
                (try? log.decode(InsertDirectiveRequest.self,
                                 log.events(since: asked, type: "InsertDirectiveRequest").last))?.kind
                    == entry.kind.wire
            }
            let request = try log.decode(InsertDirectiveRequest.self,
                                         log.events(since: asked, type: "InsertDirectiveRequest").last)
            if entry.kind == .loop { XCTAssertEqual(loopChoices(request), ["@start", "verse"]) }
            if entry.kind == .key { XCTAssertFalse(request.keyOptions.isEmpty, "the keys with a signature") }
            // The dialog's first check, of the fields it opens with (the app sends
            // it when the dialog appears): Insert is on for 4/4, the first key and
            // @start × 2, off for the empty fields.
            let settings = try log.decodeLatest(SettingsState.self, "SettingsState")
            let toolbar = try log.decodeLatest(ToolbarState.self, "ToolbarState")
            let initial = DirectiveForm.initial(entry.kind, keys: keyChoices(
                request, american: settings.americanKeys, european: settings.europeanKeys,
                toolbar: toolbar.keyOptions)).answer()
            session.submit(.checkDirective(fields: .object(initial.mapValues { .string($0) }),
                                           kind: entry.kind.wire, requestId: request.requestId))
            try await log.wait("the \(entry.kind) dialog's first check") {
                (try? log.decode(DirectiveCheck.self, log.events(since: asked, type: "DirectiveCheck").last))?
                    .requestId == request.requestId
            }
            let first = try log.decode(DirectiveCheck.self, log.events(since: asked, type: "DirectiveCheck").last)
            XCTAssertEqual(DirectiveVerdict.of(kind: entry.kind.wire, requestId: request.requestId, answer: initial,
                                               check: first, showErrors: false).canInsert,
                           [.time, .key, .loop].contains(entry.kind), "\(entry.kind): \(first)")
            if let fields = checks[entry.kind] {
                session.submit(.checkDirective(fields: .object(fields.mapValues { .string($0) }),
                                               kind: entry.kind.wire, requestId: request.requestId))
                let typed = JSONValue.object(fields.mapValues { .string($0) })
                try await log.wait("the \(entry.kind) check") {
                    (try? log.decode(DirectiveCheck.self, log.events(since: asked, type: "DirectiveCheck").last))?
                        .fields == typed
                }
                let check = try log.decode(DirectiveCheck.self, log.events(since: asked, type: "DirectiveCheck").last)
                let verdict = DirectiveVerdict.of(kind: entry.kind.wire, requestId: request.requestId,
                                                  answer: fields, check: check, showErrors: true)
                XCTAssertEqual(verdict.canInsert, entry.kind == .label, "\(verdict)")
                if entry.kind == .bpm { XCTAssertFalse(verdict.messages.isEmpty) }
            }
            await log.waitQuiet()
            try await scenes.record("insert_\(entry.kind.wire)", "Amazing Grace in Edit with ＋ Insert › "
                                    + "\(entry.label)'s dialog pending, the cursor after “me”"
                                    + (checks[entry.kind].map { ", fields checked: \($0)" } ?? "") + ".", from: mark)
            session.submit(.respondToInsertDirectiveRequest(requestId: request.requestId, value: nil))
        }

        // The song again, so the scenes below carry no Insert request (a
        // fixture has no answers, so the last one would stay pending): the
        // Insert sheet and Transpose draw over this one.
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let graceAgain = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight once more") {
            $0.textRevision == graceAgain.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        await log.waitQuiet()
        try await scenes.record("grace_edit", "Amazing Grace (Android's help screenshots' song) in Edit, nothing "
                                + "pending: the ribbon's sheets and Transpose draw over it.", from: mark)

        // Suggest Capo for the whole song: the session scores at once.
        session.submit(.capoAdviceOpen(selection: nil))
        try await log.wait("the capo advice", timeout: 30) {
            guard let advice = try? log.decodeLatest(CapoAdviceState.self, "CapoAdviceState") else { return false }
            return advice.active && advice.status == CapoAdviceState.ready && !advice.rows.isEmpty
        }
        let advice = try log.decodeLatest(CapoAdviceState.self, "CapoAdviceState")
        XCTAssertNotNil(capoChoice(advice, picked: nil))
        XCTAssertTrue(capoCanApply(advice, picked: nil))
        XCTAssertTrue(advice.rows.contains { $0.recommended }, "\(advice.rows)")
        XCTAssertFalse(advice.voicings.isEmpty)
        await log.waitQuiet()
        try await scenes.record("capo_advice", "Amazing Grace in Edit with Suggest Capo open on the whole song, "
                                + "its rows scored.", from: mark)
        session.submit(.capoAdviceClose())
        try await log.wait("Suggest Capo closed") {
            (try? log.decodeLatest(CapoAdviceState.self, "CapoAdviceState"))?.active == false
        }

        // The chord identifier: C, E, G and B selected, Cmaj7 played (Android's identify).
        let piano = PianoKeyboard()
        var identifier = IdentifierModel()
        var commands = identifier.open()
        for midi in [60, 64, 67, 71] {
            commands += identifier.tapKey(piano.keys.first { $0.midi == midi }!)
        }
        commands.forEach(session.submit)
        try await log.wait("Cmaj7 among the candidates") {
            guard let state = try? log.decodeLatest(IdentifierState.self, "IdentifierState") else { return false }
            return state.notes.map(\.midi) == [60, 64, 67, 71] && state.candidates.contains("Cmaj7")
        }
        var state = try log.decodeLatest(IdentifierState.self, "IdentifierState")
        identifier.onState(state)
        XCTAssertEqual(identifier.typed, state.notesText, "the field follows the keys")
        let played = state.soundingToken
        identifier.pick("Cmaj7").forEach(session.submit)
        try await log.wait("Cmaj7 sounding") {
            (try? log.decodeLatest(IdentifierState.self, "IdentifierState"))?.soundingToken ?? 0 > played
        }
        state = try log.decodeLatest(IdentifierState.self, "IdentifierState")
        XCTAssertEqual(Set(state.sounding), [60, 64, 67, 71], "\(state.sounding)")
        await log.waitQuiet()

        // -- what the tools do to the song --------------------------------------------
        // The identifier's Insert: the chord and a space at the cursor.
        before = try log.decodeLatest(TextEdited.self, "TextEdited").textRevision
        let chord = try XCTUnwrap(identifier.insert())
        session.submit(.insertChord(at: cursor, chord: chord))
        let insertedChord = try await waitForEdit(log, since: mark) { $0.textRevision > before }
        XCTAssertEqual(insertedChord.replacement, "Cmaj7 ")
        XCTAssertEqual(insertedChord.start, cursor)

        // An Insert dialog answered: the directive at the cursor.
        var asked = log.count
        session.submit(.requestInsertDirective(at: cursor, kind: "bpm"))
        try await log.wait("a tempo request") { !log.events(since: asked, type: "InsertDirectiveRequest").isEmpty }
        let tempo = try log.decode(InsertDirectiveRequest.self,
                                   log.events(since: asked, type: "InsertDirectiveRequest").last)
        before = try log.decodeLatest(TextEdited.self, "TextEdited").textRevision
        session.submit(.respondToInsertDirectiveRequest(requestId: tempo.requestId, value: ["value": "110"]))
        let insertedTempo = try await waitForEdit(log, since: mark) { $0.textRevision > before }
        XCTAssertTrue(insertedTempo.replacement.contains("{bpm: 110}"), insertedTempo.replacement)

        // Transpose the whole song up two semitones: G → A, Em → F#m, D → E.
        before = insertedTempo.textRevision
        session.submit(.transpose(cursor: cursor, selection: nil, semitones: 2))
        let transposed = try await waitForEdit(log, since: mark) { $0.textRevision > before }
        let text = try await sessionText(log, since: mark)
        XCTAssertEqual(chordsAbove("That saved a wretch like me", in: text), ["A", "F#m", "E"], text)
        XCTAssertTrue(text.contains("{key: A}"), "the key directive moves with the chords: \(text)")
        XCTAssertEqual(transposed.undo, .group)

        // Then a selection: only the chords inside it move.
        let lines = text.components(separatedBy: "\n")
        let index = try XCTUnwrap(lines.firstIndex { $0.hasPrefix("That saved a wretch like me") })
        let line = (text as NSString).range(of: lines[index - 1] + "\nThat saved")
        let mapper = OffsetMapper(text)
        let selection = Selection(start: mapper.toCodePoint(line.location),
                                  end: mapper.toCodePoint(line.location + (lines[index - 1] as NSString).length))
        before = transposed.textRevision
        session.submit(.transpose(cursor: selection.end, selection: selection, semitones: -2))
        _ = try await waitForEdit(log, since: mark) { $0.textRevision > before }
        let partly = try await sessionText(log, since: mark)
        XCTAssertEqual(chordsAbove("That saved a wretch like me", in: partly), ["G", "Em", "D"], partly)
        XCTAssertEqual(chordsAbove("Amazing grace, how sweet the sound", in: partly), ["A", "A7", "D", "A"],
                       "outside the selection: unchanged")
        XCTAssertTrue(partly.contains("{key: A}"), "outside the selection: unchanged")

        // Suggest Capo applied: the chosen capo goes into the song.
        session.submit(.capoAdviceOpen(selection: nil))
        try await log.wait("the capo advice again", timeout: 30) {
            guard let advice = try? log.decodeLatest(CapoAdviceState.self, "CapoAdviceState") else { return false }
            return advice.active && advice.status == CapoAdviceState.ready
        }
        let rows = try log.decodeLatest(CapoAdviceState.self, "CapoAdviceState").rows
        let capo = try XCTUnwrap(rows.first { $0.capo > 0 }?.capo, "\(rows)")
        asked = log.count
        session.submit(.capoAdviceApply(capo: capo))
        try await log.wait("the capo in the song") {
            (try? log.decodeLatest(CapoAdviceState.self, "CapoAdviceState"))?.active == false
                && !log.events(since: asked, type: "TextEdited").isEmpty
        }
        let capoText = try await sessionText(log, since: mark)
        XCTAssertTrue(capoText.contains("{capo: \(capo)}"), capoText)
    }

    /// The chords on the line above the first line that starts with `lyric`.
    private func chordsAbove(_ lyric: String, in text: String) -> [String] {
        let lines = text.components(separatedBy: "\n")
        guard let index = lines.firstIndex(where: { $0.hasPrefix(lyric) }), index > 0 else { return [] }
        return lines[index - 1].split(separator: " ").map(String.init)
    }

    /// The session's text after the edits since `mark`, which starts at a restore.
    private func sessionText(_ log: EventLog, since mark: Int) async throws -> String {
        var snapshot = SessionSnapshot()
        for event in log.events(since: mark, type: "TextEdited") {
            try snapshot.apply(typeName: event.typeName, json: event.json)
        }
        return snapshot.text
    }
}

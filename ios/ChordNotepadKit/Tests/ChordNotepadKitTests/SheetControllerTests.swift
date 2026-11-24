import Foundation
import XCTest

@testable import ChordNotepadKit

/// What a tap in the player's sheets and the tools' dialogs does (Android's
/// SongScreen `Sheets`, `CapoDialog` and the Insert dialogs as behaviour):
/// the route, the dialogs' fields and the commands.
final class SheetControllerTests: XCTestCase {
    private var ui = MainUiState(mode: .play)
    private var snapshot = SessionSnapshot()
    private var editor = EditorModel()

    override func setUp() {
        super.setUp()
        _ = editor.viewChanged(text: "C G Am F\nla la\n", selection: UTF16Range(4, 4), composing: false)
        snapshot.apply(.toolbarState(ToolbarState(
            beats: 4, bpm: 120, bpmDisplay: 120, bpmEditable: true, bpmSetBy: nil, key: "C", keyOptions: ["C", "G"],
            keySetBy: nil, metronome: false, multiplierPct: 125, notation: "american", playAction: .play,
            timeSetBy: nil, unit: 4)))
    }

    @discardableResult
    private func tap(_ event: SheetEvent) -> SheetEffects {
        ui.handle(event, snapshot: snapshot, editor: &editor)
    }

    private func defaults(locked: String? = nil) -> SongDefaultsState {
        SongDefaultsState(key: SongDefault(directiveOffset: nil, fromDirective: false, value: "G"),
                          lockedReason: locked, summary: "90 · 3/4 · G",
                          tempo: SongDefault(directiveOffset: 0, fromDirective: true, value: "90"),
                          time: SongDefault(directiveOffset: nil, fromDirective: false, value: "3/4"))
    }

    func testTheSpeedSheetTheSliderResetAndManual() throws {
        tap(.open(.speed(manual: false)))
        XCTAssertEqual(ui.route, .speed(manual: false))
        try assertCommands(tap(.speedDragged(149)).commands, [("set_multiplier_pct", #"{"pct": 150}"#)])
        XCTAssertEqual(ui.tools.speedSlider.shown(125), 150)
        var toolbar = try XCTUnwrap(snapshot.toolbar)
        toolbar.multiplierPct = 150
        ui.received(.toolbarState(toolbar))
        XCTAssertNil(ui.tools.speedSlider.dragged, "the session caught up")
        _ = tap(.speedDragged(149))
        try assertCommands(tap(.speedReset).commands, [("reset_multiplier", "{}")])
        XCTAssertNil(ui.tools.speedSlider.dragged)

        tap(.speedManual)
        XCTAssertEqual(ui.route, .speed(manual: true))
        XCTAssertEqual(ui.tools.speedEntry?.text, "125")
        tap(.speedTyped("9"))
        XCTAssertTrue(tap(.speedOK).commands.isEmpty)
        XCTAssertEqual(ui.tools.speedEntry?.showError, true)
        XCTAssertEqual(ui.route, .speed(manual: true), "stays open until the value is valid")
        tap(.speedTyped("80"))
        try assertCommands(tap(.speedOK).commands, [("set_multiplier_pct", #"{"pct": 80}"#)])
        XCTAssertEqual(ui.route, .speed(manual: false), "back on the sheet")
        XCTAssertNil(ui.tools.speedEntry)

        tap(.speedManual)
        tap(.back)
        XCTAssertEqual(ui.route, .speed(manual: false), "Cancel goes back to the sheet")
        tap(.done)
        XCTAssertEqual(ui.route, MainRoute.none)
    }

    func testPlaybackSettingsTempoChoicesEditAndWrite() throws {
        snapshot.apply(.songDefaultsState(defaults()))
        tap(.open(.songDefaults))
        tap(.tempoOpen)
        XCTAssertEqual(ui.tools.tempoEntry, "90")
        tap(.tempoTyped("  "))
        XCTAssertTrue(tap(.tempoOK).commands.isEmpty, "OK is off with nothing typed")
        tap(.tempoTyped("132"))
        try assertCommands(tap(.tempoOK).commands, [("set_bpm_text", #"{"text": "132"}"#)])
        XCTAssertNil(ui.tools.tempoEntry)
        XCTAssertEqual(ui.route, .songDefaults, "the sheet stays")

        let rows = songDefaultRows(defaults(), keys: ["C", "G"])
        XCTAssertTrue(tap(.chooseDefault(rows[1], "3/4")).commands.isEmpty, "the value already")
        try assertCommands(tap(.chooseDefault(rows[1], "6/8")).commands,
                           [("set_time_signature", #"{"beats": 6, "unit": 8}"#)])
        try assertCommands(tap(.chooseDefault(rows[2], "C")).commands, [("set_key", #"{"key": "C"}"#)])

        try assertCommands(tap(.writeIntoSong).commands, [("write_song_defaults", "{}")])
        XCTAssertEqual(ui.route, MainRoute.none, "Write into song closes the sheet")

        tap(.open(.songDefaults))
        let edit = tap(.editDirective(0))
        XCTAssertEqual(edit.editAt, 0)
        XCTAssertEqual(ui.route, MainRoute.none)
    }

    func testWhileASongPlaysTheValuesSayWhyTheyAreOff() {
        snapshot.apply(.songDefaultsState(defaults(locked: "Pause to change the playback settings")))
        tap(.open(.songDefaults))
        let rows = songDefaultRows(defaults(), keys: ["C", "G"])
        for event in [SheetEvent.tempoOpen, .chooseDefault(rows[1], "6/8"), .writeIntoSong, .locked] {
            let effects = tap(event)
            XCTAssertTrue(effects.commands.isEmpty, "\(event)")
            XCTAssertEqual(effects.notice, "Pause to change the playback settings", "\(event)")
        }
        XCTAssertNil(ui.tools.tempoEntry)
        XCTAssertEqual(ui.route, .songDefaults)
    }

    func testTheVoicingAndInstrumentSheets() throws {
        snapshot.apply(.voicingMenuState(VoicingMenuState(groups: [[MenuItem(label: "Piano", value: "piano")]],
                                                          lockedReason: nil, selected: "piano")))
        tap(.open(.voicing))
        XCTAssertTrue(tap(.chooseVoicing("piano")).commands.isEmpty, "the one in use")
        try assertCommands(tap(.chooseVoicing("guitar:standard")).commands,
                           [("set_voicing", #"{"voicing": "guitar:standard"}"#)])
        XCTAssertEqual(ui.route, .voicing, "choosing applies at once; the sheet stays")
        // Edit voicings…: the sheet closes and Settings opens at Voicings.
        let edit = tap(.editVoicings)
        XCTAssertEqual(edit.openSettings, .voicings)
        XCTAssertNil(edit.notice)
        XCTAssertEqual(ui.route, MainRoute.none)

        tap(.open(.instrument(family: nil)))
        tap(.openFamily(3))
        XCTAssertEqual(ui.route, .instrument(family: 3))
        try assertCommands(tap(.chooseInstrument(25)).commands, [("set_instrument", #"{"program": 25}"#)])
        tap(.dismiss)
        XCTAssertEqual(ui.route, .instrument(family: nil), "a swipe down on a family goes back to the families")
        tap(.openFamily(3))
        tap(.done)
        XCTAssertEqual(ui.route, MainRoute.none, "Done closes from any level")
    }

    func testInsertSendsTheRequestForTheKindAtTheCursor() throws {
        tap(.ribbon(.insert))
        XCTAssertEqual(ui.route, .insert)
        try assertCommands(tap(.insert(.loop)).commands, [("request_insert_directive", #"{"kind": "loop", "at": 4}"#)])
        XCTAssertEqual(ui.route, MainRoute.none)
    }

    func testTransposeKnowsTheSelectionWhenItOpens() throws {
        tap(.ribbon(.transpose))
        XCTAssertEqual(ui.route, .transpose(selection: false))
        tap(.transposeUp)
        tap(.transposeUp)
        tap(.transposeDown)
        tap(.transposeUp)
        XCTAssertEqual(ui.tools.transpose.display, "+2")
        try assertCommands(tap(.transposeOK).commands,
                           [("transpose", #"{"semitones": 2, "selection": null, "cursor": 4}"#)])
        XCTAssertEqual(ui.route, MainRoute.none)
        _ = editor.viewChanged(text: editor.text, selection: UTF16Range(0, 8), composing: false)
        tap(.ribbon(.transpose))
        XCTAssertEqual(ui.route, .transpose(selection: true))
        XCTAssertEqual(ui.tools.transpose.semitones, 0, "a fresh dialog starts at 0")
        tap(.transposeDown)
        try assertCommands(tap(.transposeOK).commands,
                           [("transpose", #"{"semitones": -1, "selection": [0, 8], "cursor": 8}"#)])
    }

    func testAnInsertDialogIsCheckedAsItChangesAndInsertsOnlyWhenClean() throws {
        let request = InsertDirectiveRequest(existingLabels: ["verse"], keyOptions: [], kind: "bpm",
                                             notation: "american", requestId: 7)
        snapshot.apply(.insertDirectiveRequest(request))
        try assertCommands(tap(.directiveShown).commands,
                           [("check_directive", #"{"kind": "bpm", "fields": {"value": ""}, "request_id": 7}"#)])
        XCTAssertTrue(tap(.directiveShown).commands.isEmpty, "shown again (a redraw): not checked again")
        XCTAssertTrue(tap(.directiveInsert).commands.isEmpty, "no clean reply yet")
        var form = try XCTUnwrap(ui.tools.directive?.form)
        form.bpm = "999"
        try assertCommands(tap(.directiveChanged(form)).commands,
                           [("check_directive", #"{"kind": "bpm", "fields": {"value": "999"}, "request_id": 7}"#)])
        snapshot.apply(.directiveCheck(DirectiveCheck(errors: .object(["value": .string("BPM must be between 20 and 400.")]),
                                                      fields: .object(["value": .string("999")]), formError: "",
                                                      kind: "bpm", requestId: 7)))
        XCTAssertEqual(ui.directiveVerdict(for: request, snapshot: snapshot).messages,
                       ["BPM must be between 20 and 400."])
        XCTAssertTrue(tap(.directiveInsert).commands.isEmpty)
        form.bpm = "110"
        tap(.directiveChanged(form))
        snapshot.apply(.directiveCheck(DirectiveCheck(errors: .object([:]), fields: .object(["value": .string("110")]),
                                                      formError: "", kind: "bpm", requestId: 7)))
        let inserted = tap(.directiveInsert)
        try assertCommands(inserted.commands, [("respond", #"{"request_id": 7, "value": {"value": "110"}}"#)])
        XCTAssertEqual(inserted.answered, 7)
        XCTAssertNil(ui.tools.directive)
    }

    func testAnInsertDialogStartsFromTheDesktopsDefaultsAndCancelAnswersNull() throws {
        snapshot.apply(.settingsState(SettingsState(
            americanKeys: ["C", "G"], bpmMax: 400, bpmMin: 20, europeanKeys: ["Do", "Sol"], fontSizeMax: 72,
            fontSizeMin: 6, maxRecentFilesMax: 50, timeSignatureUnits: [2, 4, 8],
            values: SettingsValues(bpm: 120, clickPlaysChartVoicing: true, fontFamily: "", fontSize: 11, key: "C",
                                   maxRecentFiles: 10, notation: "american", showQuickStartOnStartup: true,
                                   timeSignatureBeats: 4, timeSignatureUnit: 4, wordWrap: false))))
        let key = InsertDirectiveRequest(existingLabels: [], keyOptions: [], kind: "key", notation: "european",
                                         requestId: 8)
        snapshot.apply(.insertDirectiveRequest(key))
        tap(.directiveShown)
        XCTAssertEqual(ui.tools.directive?.form.key, "Do", "the first key of the request's notation")
        XCTAssertEqual(snapshot.insertChoices(key).units, [2, 4, 8])
        let cancelled = tap(.directiveCancel)
        try assertCommands(cancelled.commands, [("respond", #"{"request_id": 8, "value": null}"#)])
        XCTAssertEqual(cancelled.answered, 8)

        // Insert Capo's Suggest: the request goes, Suggest Capo opens for the selection.
        let capo = InsertDirectiveRequest(existingLabels: [], keyOptions: [], kind: "capo", notation: "american",
                                          requestId: 9)
        snapshot.apply(.insertDirectiveRequest(capo))
        tap(.directiveShown)
        try assertCommands(tap(.directiveSuggest).commands, [
            ("respond", #"{"request_id": 9, "value": null}"#),
            ("capo_advice_open", #"{"selection": null}"#),
        ])

        // A kind the app doesn't know is cancelled.
        let unknown = InsertDirectiveRequest(existingLabels: [], keyOptions: [], kind: "chord", notation: "american",
                                             requestId: 10)
        snapshot.apply(.insertDirectiveRequest(unknown))
        try assertCommands(tap(.directiveShown).commands, [("respond", #"{"request_id": 10, "value": null}"#)])
    }

    func testSuggestCapoPicksAppliesAndStartsAgainOnNewRows() throws {
        let rows = [
            CapoRow(capo: 0, current: true, ease: "No capo", label: "", recommended: true, shapes: "G C D"),
            CapoRow(capo: 3, current: false, ease: "About the same", label: "", recommended: false, shapes: "E A B"),
        ]
        let voicings = [MenuItem(label: "Guitar", value: "guitar:standard"), MenuItem(label: "Uke", value: "uke")]
        var advice = CapoAdviceState(active: true, message: "", playing: false, rows: rows, scope: "",
                                     status: "ready", voicing: "guitar:standard", voicings: voicings)
        tap(.ribbon(.capo))
        snapshot.apply(.capoAdviceState(advice))
        XCTAssertEqual(ui.capoChosen(advice), 0, "the recommended row")
        tap(.capoPick(3))
        XCTAssertEqual(ui.capoChosen(advice), 3)
        XCTAssertTrue(tap(.capoVoicing("guitar:standard")).commands.isEmpty)
        try assertCommands(tap(.capoVoicing("uke")).commands, [("capo_advice_voicing", #"{"voicing": "uke"}"#)])
        advice.voicing = "uke"
        snapshot.apply(.capoAdviceState(advice))
        XCTAssertEqual(ui.capoChosen(advice), 0, "another voicing: the recommended row again")
        tap(.capoPick(3))
        advice.playing = true
        snapshot.apply(.capoAdviceState(advice))
        XCTAssertFalse(ui.capoCanApplyNow(advice))
        XCTAssertTrue(tap(.capoApply).commands.isEmpty, "not while a song plays")
        advice.playing = false
        snapshot.apply(.capoAdviceState(advice))
        try assertCommands(tap(.capoApply).commands, [("capo_advice_apply", #"{"capo": 3}"#)])
        try assertCommands(tap(.capoCancel).commands, [("capo_advice_close", "{}")])
    }

    func testTheRibbonsCapoOpensSuggestCapoForTheSelection() throws {
        _ = editor.viewChanged(text: editor.text, selection: UTF16Range(2, 6), composing: false)
        try assertCommands(tap(.ribbon(.capo)).commands, [("capo_advice_open", #"{"selection": [2, 6]}"#)])
    }

    func testTheIdentifierOpensClearedAndInsertsAtTheCursor() throws {
        try assertCommands(tap(.ribbon(.identify)).commands, [("identifier_clear", "{}")])
        XCTAssertEqual(ui.route, .identify)
        let c4 = PianoKeyboard().keys[0]
        try assertCommands(tap(.identifierTap(c4)).commands,
                           [("identifier_toggle_note", #"{"note": "C", "octave": 4}"#)])
        ui.received(.identifierState(IdentifierState(
            candidates: ["C5"], message: nil, notation: "american", notes: [IdentifierNote(midi: 60, name: "C", octave: 4)],
            notesText: "C", sounding: [60], soundingAbove: nil, soundingBelow: nil, soundingSeconds: 3,
            soundingToken: 1, typedTextError: nil)))
        XCTAssertEqual(ui.tools.identifier.typed, "C", "the field follows the key")
        try assertCommands(tap(.identifierPress(c4)).commands, [("play_note", #"{"note": "C", "octave": 4}"#)])
        try assertCommands(tap(.identifierPick("C5", rolled: true)).commands,
                           [("play_identified_chord", #"{"chord": "C5", "rolled": true}"#)])
        try assertCommands(tap(.identifierPlay(rolled: false)).commands,
                           [("identifier_play_selection", #"{"rolled": false}"#)])
        try assertCommands(tap(.identifierInsert(nil)).commands, [("insert_chord", #"{"at": 4, "chord": "C5"}"#)])
        try assertCommands(tap(.identifierType("C E")).commands,
                           [("identifier_set_notes_text", #"{"text": "C E"}"#)])
        tap(.identifierExpired(1))
        XCTAssertEqual(ui.tools.identifierExpired, 1)
        try assertCommands(tap(.identifierClear).commands, [("identifier_clear", "{}")])
        tap(.dismiss)
        XCTAssertEqual(ui.route, MainRoute.none)
        XCTAssertEqual(ui.tools.identifier, IdentifierModel())
    }
}

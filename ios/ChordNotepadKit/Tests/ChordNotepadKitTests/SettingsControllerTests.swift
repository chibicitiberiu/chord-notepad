import Foundation
import XCTest

@testable import ChordNotepadKit

/// The fixtures android/tools/gen_voicing_form_fixtures.py wrote from a real
/// session (`{"type", "json"}`), kept in Android's test resources and decoded
/// as the bridge would (Android's ui/settings/Fixtures.kt).
enum SettingsFixtures {
    static let directory = TestPython.repo.appendingPathComponent("android/app/src/test/resources/voicing_form")

    static func load(_ name: String) -> SessionOutput {
        let data = try! Data(contentsOf: directory.appendingPathComponent("\(name).json"))
        let root = try! JSONDecoder().decode([String: JSONValue].self, from: data)
        let json = String(decoding: try! BridgeJSON.encoder.encode(root["json"]!), as: UTF8.self)
        return try! SessionOutput.decode(typeName: root["type"]!.stringValue!, json: json)
    }

    /// The editor schema.
    static let schema: EditorSchema = {
        guard case .voicingEditorSchema(let event) = load("schema") else { fatalError("schema.json") }
        return EditorSchema.parse(event.schema)
    }()

    /// `SettingsState` at startup (American, key C, 120 BPM, 4/4).
    static let settings: SettingsState = {
        guard case .settingsState(let state) = load("settings") else { fatalError("settings.json") }
        return state
    }()

    private static func editor(_ name: String) -> VoicingEditorState {
        guard case .voicingEditorState(let state) = load(name) else { fatalError("\(name).json") }
        return state
    }

    /// "New voicing" (fretboard): tuning "E2 A2 X9 G3" (field error), relaxed span 2 (form error).
    static let fretboardInvalid = editor("fretboard_invalid")
    /// The same as an ensemble with a third voice moved up (Voice 1, Voice 3,
    /// Voice 2): voice 1 low "H9" and gap "0" (cell errors), voice 0 low above
    /// high (a rule across fields, blamed on both cells).
    static let ensemble = editor("ensemble")
    /// The same as a piano, untouched.
    static let piano = editor("piano")
}

/// A copy of `value` changed by `change`.
func with<T>(_ value: T, _ change: (inout T) -> Void) -> T {
    var copy = value
    change(&copy)
    return copy
}

/// A sent command: its name and arguments.
struct SentCommand: Equatable {
    let name: String
    let args: [String: JSONValue]

    init(_ command: BridgeCommand) {
        name = command.name
        args = try! JSONDecoder().decode([String: JSONValue].self, from: Data(command.argsJSON().utf8))
    }
}

/// Android's `SettingsControllerTest`, case for case: the edit's life,
/// autosave, the draft, navigation and the voicing commands. Android's three
/// cases on `snapshot()`/`restore()` (a rotation, a process restarted under
/// the screen) have no iOS counterpart: SwiftUI keeps the controller across a
/// rotation, and the app doesn't restore screens after the system ends it
/// (docs/IOS.md, "Settings, About and Licences").
final class SettingsControllerTests: XCTestCase {
    private var controller = SettingsController()
    private var sent: [SentCommand] = []

    private func drain() {
        sent += controller.takeCommands().map(SentCommand.init)
    }

    private func clear() {
        drain()
        sent = []
    }

    private var names: [String] {
        drain()
        return sent.map(\.name)
    }

    /// What was sent apart from the autosaves.
    private var voicingCommands: [SentCommand] {
        drain()
        return sent.filter { $0.name != "commit_settings" }
    }

    /// The `values` of every `commit_settings` sent.
    private var commits: [JSONValue] {
        drain()
        return sent.filter { $0.name == "commit_settings" }.map { $0.args["values"]! }
    }

    /// The `invalid_numbers` of every `commit_settings` sent.
    private var numberCommits: [JSONValue] {
        drain()
        return sent.filter { $0.name == "commit_settings" }.map { $0.args["invalid_numbers"]! }
    }

    private func texts(_ pairs: [String: String]) -> JSONValue { .object(pairs.mapValues { .string($0) }) }

    private let inactive = with(SettingsFixtures.piano) {
        $0.active = false
        $0.revision = 0
        $0.groups = []
        $0.invalid = []
        $0.presets = []
        $0.selected = nil
        $0.model = nil
        $0.values = .object([:])
        $0.fieldErrors = .object([:])
        $0.formErrors = []
        $0.hints = .object([:])
        $0.dirty = false
    }
    private var opened: VoicingEditorState { with(inactive) { $0.active = true; $0.revision = 0 } }

    /// A controller with the edit open and the settings loaded.
    private func editing() {
        controller = SettingsController()
        controller.start(needSchema: true)
        controller.onSettings(SettingsFixtures.settings)
        controller.onEditor(inactive)
        controller.onEditor(opened)
        clear()
    }

    private func value(_ commit: JSONValue, _ key: String) -> JSONValue? { commit[key] }

    func testStartBeginsTheEditOnceAndAsksForTheSchema() {
        controller.start(needSchema: true)
        XCTAssertEqual(names, ["request_voicing_editor_schema", "begin_settings_edit"])
        XCTAssertEqual(controller.ui.phase, .opening)
        // The old (inactive) state still in the snapshot doesn't count.
        controller.onEditor(inactive)
        XCTAssertEqual(controller.ui.phase, .opening)
        controller.onEditor(opened)
        XCTAssertEqual(controller.ui.phase, .editing)
        clear()
        controller.start(needSchema: false)
        XCTAssertEqual(names, [])
    }

    func testTheDraftStartsFromTheFirstSettingsState() {
        editing()
        let draft = controller.ui.draft!
        XCTAssertEqual(draft.fontKind, .monospace)
        XCTAssertEqual(draft.fontSize, 11)
        XCTAssertEqual(draft.key, "C")
        XCTAssertFalse(controller.ui.draftPending)
        // A later SettingsState (the toolbar, or our own save) doesn't reset the draft.
        controller.updateDraft { $0.bpm = 90 }
        controller.onSettings(SettingsFixtures.settings)
        XCTAssertEqual(controller.ui.draft!.bpm, 90)
    }

    func testAGeneralOrPlaybackChangeIsSavedAtOnce() {
        editing()
        controller.updateDraft { $0.fontKind = .serif }
        controller.setNotation(Notation.european)
        XCTAssertEqual(commits.count, 2)
        XCTAssertEqual(commits[0]["font_family"], .string("Serif"))
        XCTAssertEqual(commits[1]["notation"], .string("european"))
        // The key stays American (shown as Do); the config never holds European names.
        XCTAssertEqual(commits[1]["key"], .string("C"))
        XCTAssertEqual(shownKey(controller.ui.draft!.key, notation: Notation.european, limits: SettingsFixtures.settings),
                       "Do")
        XCTAssertFalse(controller.ui.draftPending)
        XCTAssertEqual(controller.ui.phase, .editing)
    }

    func testWordWrapStartsFromTheSettingsAndIsSavedAtOnce() {
        editing()
        XCTAssertFalse(controller.ui.draft!.wordWrap)
        XCTAssertFalse(SettingsFixtures.settings.values.wordWrap)
        controller.updateDraft { $0.wordWrap = true }
        XCTAssertEqual(commits.count, 1)
        XCTAssertEqual(commits.last?["word_wrap"], .bool(true))
        XCTAssertTrue(controller.ui.draft!.wordWrap)
        // Sent even when off (Python wants every field).
        controller.updateDraft { $0.wordWrap = false }
        XCTAssertEqual(commits.last?["word_wrap"], .bool(false))
    }

    func testClickedChordsSoundAsInTheChordSheetOnFromTheSettingsAndSavedAtOnce() {
        editing()
        XCTAssertTrue(SettingsFixtures.settings.values.clickPlaysChartVoicing)
        XCTAssertTrue(controller.ui.draft!.clickPlaysChartVoicing)
        controller.updateDraft { $0.clickPlaysChartVoicing = false }
        XCTAssertEqual(commits.count, 1)
        XCTAssertEqual(commits.last?["click_plays_chart_voicing"], .bool(false))
        XCTAssertFalse(controller.ui.draft!.clickPlaysChartVoicing)
        // Sent with the other values, and back on.
        XCTAssertEqual(commits.last?["word_wrap"], .bool(false))
        controller.updateDraft { $0.clickPlaysChartVoicing = true }
        XCTAssertEqual(commits.last?["click_plays_chart_voicing"], .bool(true))
    }

    func testANumberWaitsForSaveDraftAndOnlyAValidOneIsSaved() {
        editing()
        controller.setNumber(.bpm, "9")
        controller.setNumber(.bpm, "96")
        XCTAssertEqual(names, [])
        XCTAssertTrue(controller.ui.draftPending)
        XCTAssertTrue(controller.needsSave)
        controller.saveDraft()
        XCTAssertEqual(commits.count, 1)
        XCTAssertEqual(commits.single?["bpm"], .int(96))
        controller.saveDraft()
        XCTAssertEqual(commits.count, 1)

        clear()
        controller.setNumber(.bpm, "1000")
        XCTAssertEqual(controller.ui.numberTexts, [.bpm: "1000"])
        XCTAssertEqual(controller.ui.draft!.bpm, 96)
        controller.saveDraft()
        // Not saved: only kept by Python, for next time.
        XCTAssertEqual(commits, [.null])
        XCTAssertEqual(numberCommits, [texts(["bpm": "1000"])])
        controller.setNumber(.bpm, " 100 ")
        XCTAssertEqual(controller.ui.numberTexts, [:])
        controller.saveDraft()
        XCTAssertEqual(commits.last?["bpm"], .int(100))
        XCTAssertEqual(numberCommits.last, texts([:]))
        controller.saveDraft()
        XCTAssertEqual(commits.count, 2)
    }

    func testAValidNumberTypedOnTheWayToAnInvalidOneIsntSaved() {
        editing()
        let saved = controller.ui.saved!.bpm
        // Typing 2500 a digit at a time: 25 and 250 are in range, 2500 isn't.
        for text in ["2", "25", "250", "2500"] { controller.setNumber(.bpm, text) }
        XCTAssertEqual(controller.ui.draft!.bpm, saved)
        XCTAssertFalse(controller.ui.draftPending)
        controller.saveDraft()
        XCTAssertEqual(commits, [.null])
        XCTAssertEqual(numberCommits, [texts(["bpm": "2500"])])
    }

    func testEveryVoicingCommandButSelectIsFollowedByAnAutosave() {
        editing()
        controller.selectVoicing("New voicing")
        XCTAssertEqual(names, ["select_voicing"])
        controller.onEditor(SettingsFixtures.piano)
        controller.edit(VoicingEdits.text("rh_center", "60"))
        controller.addVoicingFrom(VoicingPreset(group: VoicingPresetGroup.blank, label: "Blank piano"))
        XCTAssertEqual(names, ["select_voicing", "set_voicing_values", "commit_settings", "add_voicing_from",
                               "commit_settings"])
        // Nothing pending on General: the config's values stay.
        XCTAssertEqual(commits, [.null, .null])
        // A number still being typed goes out with the voicing's save.
        controller.setNumber(.fontSize, "14")
        controller.edit(VoicingEdits.text("rh_center", "62"))
        XCTAssertEqual(commits.last?["font_size"], .int(14))
        XCTAssertFalse(controller.ui.draftPending)
    }

    func testLeavingWithNothingInvalidEndsTheEditAtOnceSavingAPendingNumberFirst() {
        editing()
        controller.onEditor(SettingsFixtures.piano)
        controller.setNumber(.maxRecentFiles, "7")
        controller.requestClose()
        XCTAssertNil(controller.ui.dialog)
        XCTAssertEqual(names, ["commit_settings", "cancel_settings_edit"])
        XCTAssertEqual(commits.single?["max_recent_files"], .int(7))
        XCTAssertEqual(controller.ui.phase, .closed)
    }

    func testLeavingWithAWrongVoicingValueAsksAndEditOpensThatVoicing() {
        editing()
        let bad = SettingsFixtures.fretboardInvalid
        XCTAssertFalse(bad.problems.isEmpty)
        controller.onEditor(with(bad) { $0.selected = nil; $0.model = nil })
        controller.openPage(.general)
        controller.requestClose()
        XCTAssertEqual(controller.ui.dialog, .problems)
        XCTAssertEqual(names, [])
        controller.editProblems()
        XCTAssertNil(controller.ui.dialog)
        XCTAssertEqual(controller.ui.phase, .editing)
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))
        XCTAssertEqual(voicingCommands.map(\.name), ["select_voicing"])
        XCTAssertEqual(sent.single?.args["name"], .string(bad.problems.first!.voicing))

        // Already shown: Edit just opens the form.
        clear()
        controller.onEditor(bad)
        controller.openPage(.voicings)
        controller.requestClose()
        controller.editProblems()
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))
        XCTAssertEqual(names, [])
    }

    func testDiscardInTheLeaveDialogDropsTheWrongValuesAndLeaves() {
        editing()
        controller.onEditor(SettingsFixtures.fretboardInvalid)
        controller.setNumber(.fontSize, "999")
        controller.back(twoPane: true, split: true)
        XCTAssertEqual(controller.ui.dialog, .problems)
        controller.confirmDialog()
        XCTAssertEqual(names.last, "cancel_settings_edit")
        XCTAssertEqual(controller.ui.phase, .closed)
        XCTAssertEqual(controller.ui.numberTexts, [:])
    }

    func testAWrongNumberCountsAsAProblemAndEditOpensItsPage() {
        editing()
        controller.onEditor(SettingsFixtures.piano)
        controller.setNumber(.bpm, "1000")
        controller.setNumber(.fontSize, "")
        controller.requestClose()
        XCTAssertEqual(controller.ui.dialog, .problems)
        // General comes before Playback.
        controller.editProblems()
        XCTAssertEqual(controller.ui.nav, SettingsNav(.general))
        // P8: and the cursor goes to the wrong field, once.
        XCTAssertEqual(controller.ui.focus, .fontSize)
        controller.focusShown()
        XCTAssertNil(controller.ui.focus)
        controller.setNumber(.fontSize, "12")
        controller.requestClose()
        controller.editProblems()
        XCTAssertEqual(controller.ui.nav, SettingsNav(.playback))
        // Nothing wrong left: Back just leaves.
        controller.setNumber(.bpm, "100")
        controller.requestClose()
        XCTAssertEqual(controller.ui.phase, .closed)
    }

    func testValuesKeptFromLastTimeComeBackOnEntryAndCanBeDiscarded() {
        controller.start(needSchema: false)
        controller.onSettings(SettingsFixtures.settings)
        controller.onEditor(inactive)
        let restored = with(SettingsFixtures.fretboardInvalid) {
            $0.selected = nil
            $0.model = nil
            $0.restored = true
            $0.stagedNumbers = .object(["bpm": .string("5")])
        }
        controller.onEditor(restored)
        XCTAssertEqual(controller.ui.numberTexts, [.bpm: "5"])
        // Python has them already: nothing to send.
        XCTAssertFalse(controller.ui.numbersPending)
        XCTAssertTrue(controller.hasProblems)
        XCTAssertTrue(settingsShowsRestoredBanner(controller.ui, editor: controller.editor))
        clear()
        controller.discardProblems()
        XCTAssertEqual(names, ["discard_settings_problems"])
        XCTAssertEqual(controller.ui.numberTexts, [:])
        controller.onEditor(with(SettingsFixtures.piano) { $0.revision = 30 })
        XCTAssertFalse(controller.hasProblems)
        controller.requestClose()
        XCTAssertEqual(controller.ui.phase, .closed)
    }

    func testAReopenedEditKeepsThisScreensNumberTexts() {
        editing()
        controller.setNumber(.bpm, "7")
        controller.saveDraft()
        controller.setNumber(.bpm, "120")
        clear()
        // The edit was opened again: it has the texts sent before (bpm 7), the screen has none.
        controller.onEditor(with(inactive) { $0.revision = 3 })
        controller.onEditor(with(opened) { $0.stagedNumbers = .object(["bpm": .string("7")]) })
        XCTAssertEqual(controller.ui.numberTexts, [:])
        XCTAssertTrue(controller.ui.numbersPending)
        controller.saveDraft()
        XCTAssertEqual(numberCommits.last, texts([:]))
    }

    func testLeavingBeforeTheEditOpenedJustEndsIt() {
        controller.start(needSchema: false)
        controller.onSettings(SettingsFixtures.settings)
        controller.setNumber(.bpm, "90")
        clear()
        controller.requestClose()
        XCTAssertEqual(names, ["cancel_settings_edit"])
        XCTAssertEqual(controller.ui.phase, .closed)
    }

    func testVoicingsGoSideBySideOnlyWithRoomBesideThePagesList() {
        // Android's L14: a phone on its side (914 dp) had pages, list and a cramped form.
        XCTAssertFalse(splitsVoicings(width: 914))
        XCTAssertFalse(splitsVoicings(width: 800))
        XCTAssertTrue(splitsVoicings(width: 1280))
        XCTAssertTrue(splitsVoicings(width: 960))
        // The catalog's windows: an iPhone either way and an upright iPad don't split; an iPad on its side does.
        XCTAssertFalse(splitsVoicings(width: 402))
        XCTAssertFalse(splitsVoicings(width: 874))
        XCTAssertFalse(splitsVoicings(width: 820))
        XCTAssertTrue(splitsVoicings(width: 1180))
        XCTAssertFalse(settingsTwoPane(width: 402))
        XCTAssertTrue(settingsTwoPane(width: 820))
        XCTAssertTrue(settingsTwoPane(width: 874))
    }

    func testTwoPanesToOneKeepsThePageThatWasShowing() {
        // L8: General showed by default in two panes (page nil), and one pane
        // after a rotation showed the pages list instead.
        editing()
        XCTAssertEqual(controller.ui.nav, SettingsNav())
        controller.settleNav(twoPane: true)
        XCTAssertEqual(controller.ui.nav, SettingsNav(.general))
        XCTAssertEqual(controller.ui.nav.shown(twoPane: false), .general)
        // One pane from the start keeps the list; an open page stays as it is.
        XCTAssertEqual(SettingsNav().settled(twoPane: false), SettingsNav())
        XCTAssertEqual(SettingsNav(.playback).settled(twoPane: true), SettingsNav(.playback))
    }

    func testPhoneNavigationPagesVoicingFormBackUpToTheListThenOut() {
        editing()
        controller.openPage(.voicings)
        controller.selectVoicing("New voicing")
        controller.onEditor(SettingsFixtures.piano)
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))
        XCTAssertEqual(settingsTitle(controller.ui, editor: controller.editor, twoPane: false, split: false),
                       "New voicing")
        controller.back(twoPane: false, split: false)
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings))
        XCTAssertEqual(settingsTitle(controller.ui, editor: controller.editor, twoPane: false, split: false),
                       "Voicings")
        controller.back(twoPane: false, split: false)
        XCTAssertEqual(controller.ui.nav, SettingsNav())
        XCTAssertEqual(settingsTitle(controller.ui, editor: controller.editor, twoPane: false, split: false),
                       "Settings")
        controller.back(twoPane: false, split: false)
        XCTAssertEqual(controller.ui.phase, .closed)
    }

    func testTabletNavigationGeneralShowsByDefaultBackLeaves() {
        XCTAssertEqual(SettingsNav().shown(twoPane: true), .general)
        XCTAssertNil(SettingsNav().shown(twoPane: false))
        let detail = SettingsNav(.voicings, voicingDetail: true)
        // Split: list and form are both on screen, so Back leaves.
        XCTAssertNil(detail.back(twoPane: true, split: true))
        // Two panes but no split: the form goes back to the list first.
        XCTAssertEqual(detail.back(twoPane: true, split: false), SettingsNav(.voicings))
        XCTAssertNil(SettingsNav(.playback).back(twoPane: true, split: false))
        XCTAssertEqual(settingsTitle(SettingsUi(nav: detail), editor: nil, twoPane: true, split: false), "Settings")
    }

    func testTheFormClosesOnPhonesWhenItsVoicingGoesAway() {
        editing()
        controller.selectVoicing("New voicing")
        controller.onEditor(SettingsFixtures.piano)
        controller.onEditor(with(SettingsFixtures.piano) { $0.selected = nil; $0.model = nil; $0.revision = 9 })
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings))
    }

    func testRemoveRenameModelSwitchAndPresetGoThroughTheirDialogs() {
        editing()
        controller.onEditor(SettingsFixtures.fretboardInvalid)
        controller.askRemove("New voicing")
        XCTAssertEqual(controller.ui.dialog, .removeVoicing("New voicing"))
        controller.confirmDialog()
        XCTAssertEqual(voicingCommands.last?.name, "remove_voicing")
        XCTAssertEqual(voicingCommands.last?.args["name"], .string("New voicing"))
        XCTAssertEqual(names.last, "commit_settings")

        controller.askRename("A")
        controller.confirmDialog(newName: "A")
        XCTAssertEqual(voicingCommands.count, 1)  // the same name: nothing sent
        controller.askRename("A")
        controller.confirmDialog(newName: "B")
        XCTAssertEqual(voicingCommands.last?.name, "rename_voicing")
        XCTAssertEqual(voicingCommands.last?.args["new"], .string("B"))
        XCTAssertEqual(voicingCommands.last?.args["old"], .string("A"))

        // dirty → ask before switching model.
        controller.askModel("piano")
        XCTAssertEqual(controller.ui.dialog, .changeModel("piano"))
        controller.confirmDialog()
        XCTAssertEqual(voicingCommands.last?.name, "set_voicing_model")
        // Not dirty → no question; the same model → nothing.
        controller.onEditor(with(SettingsFixtures.fretboardInvalid) { $0.dirty = false; $0.revision = 20 })
        controller.askModel("ensemble")
        XCTAssertNil(controller.ui.dialog)
        XCTAssertEqual(voicingCommands.last?.args["model"], .string("ensemble"))
        let before = names.count
        controller.askModel("fretboard")
        XCTAssertEqual(names.count, before)
    }

    /// The piano fixture showing its built-in, as `select_builtin` leaves it.
    private let pianoBuiltin = with(SettingsFixtures.piano) {
        $0.selected = "Piano (default)"
        $0.readOnly = true
        $0.dirty = false
    }

    func testAddVoicingOffersTheBlanksFirstThenTheBuiltInsAndTheUsersVoicings() {
        let piano = SettingsFixtures.piano
        let presets = piano.addPresets()
        XCTAssertEqual(Array(presets.prefix { $0.group == VoicingPresetGroup.blank }.map(\.label)),
                       ["Blank fretboard", "Blank piano", "Blank ensemble"])
        var groups: [String] = []
        for p in presets where !groups.contains(p.group) { groups.append(p.group) }
        XCTAssertEqual(groups, [VoicingPresetGroup.blank, "fretboard", "ensemble", "piano", VoicingPresetGroup.custom])
        // The voicing shown is left out of the state's presets, but a new one may copy it.
        XCTAssertFalse(piano.presets.contains { $0.label == "New voicing" })
        XCTAssertEqual(presets.last, VoicingPreset(group: VoicingPresetGroup.custom, label: "New voicing"))
        // Sorted in among the others, and only once.
        let more = with(piano) {
            $0.presets += [VoicingPreset(group: VoicingPresetGroup.custom, label: "Alto"),
                           VoicingPreset(group: VoicingPresetGroup.custom, label: "Tenor")]
        }
        XCTAssertEqual(more.addPresets().filter { $0.group == VoicingPresetGroup.custom }.map(\.label),
                       ["Alto", "New voicing", "Tenor"])
        let listed = with(more) { $0.presets = more.addPresets() }
        XCTAssertEqual(listed.addPresets(), listed.presets)
        // A built-in being viewed isn't one of the user's voicings.
        XCTAssertEqual(pianoBuiltin.addPresets(), pianoBuiltin.presets)
        // The menu's sections: the blanks untitled, then each model's title and "Your voicings".
        let sections = addVoicingSections(presets, schema: SettingsFixtures.schema)
        XCTAssertEqual(sections.map(\.title), [nil, "Fretboard", "Ensemble", "Piano", "Your voicings"])
        XCTAssertEqual(sections.flatMap(\.presets), presets)
    }

    func testAddVoicingSendsOneAddVoicingFromAndOpensTheNewVoicing() {
        editing()
        controller.openPage(.voicings)
        controller.addVoicingFrom(VoicingPreset(group: "fretboard", label: "Ukulele"))
        let commands = voicingCommands
        XCTAssertEqual(commands.map(\.name), ["add_voicing_from"])
        XCTAssertEqual(commands[0].args["label"], .string("Ukulele"))
        XCTAssertEqual(commands[0].args["group"], .string("fretboard"))
        XCTAssertEqual(commits.count, 1)
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))
    }

    func testABuiltInShowsReadOnlyNothingSavedNoEditSentCopyAddsAVoicingFromIt() {
        editing()
        controller.openPage(.voicings)
        controller.selectBuiltin(model: "piano", label: "Piano (default)")
        XCTAssertEqual(names, ["select_builtin"])
        XCTAssertEqual(sent.single?.args["group"], .string("piano"))
        XCTAssertEqual(sent.single?.args["label"], .string("Piano (default)"))
        // On a phone the form opens.
        XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true))

        controller.onEditor(pianoBuiltin)
        XCTAssertTrue(pianoBuiltin.showsBuiltin)
        clear()
        // Python would refuse these (RuntimeError): none goes out.
        controller.edit(VoicingEdits.text("rh_center", "60"))
        controller.addRecord("voices")
        controller.removeRecord(0, "voices")
        controller.moveRecord(0, 1, "voices")
        controller.duplicateRecord(0, "voices")
        controller.askModel("ensemble")
        controller.askRemove("Piano (default)")
        controller.askRename("Piano (default)")
        XCTAssertEqual(names, [])
        XCTAssertNil(controller.ui.dialog)
        XCTAssertEqual(controller.editor?.values, SettingsFixtures.piano.values)

        controller.addVoicingFrom(VoicingPreset(group: "piano", label: "Piano (default)"))
        XCTAssertEqual(names, ["add_voicing_from", "commit_settings"])
    }

    func testANewerReleasesVoicingIsReadOnlyButNoBuiltInItCanBeRenamedAndRemoved() {
        let newer = with(SettingsFixtures.piano) { $0.model = nil; $0.readOnly = true; $0.values = .object([:]) }
        XCTAssertFalse(newer.showsBuiltin)
        editing()
        controller.onEditor(newer)
        controller.edit(VoicingEdits.text("rh_center", "60"))
        controller.askModel("piano")
        XCTAssertEqual(names, [])
        controller.askRemove("New voicing")
        XCTAssertEqual(controller.ui.dialog, .removeVoicing("New voicing"))
        controller.dismissDialog()
        controller.askRename("New voicing")
        XCTAssertEqual(controller.ui.dialog, .rename("New voicing"))
    }

    func testFormEditsGoOutAtOnceAndShowBeforeTheEcho() {
        editing()
        controller.onEditor(SettingsFixtures.ensemble)
        let rows = records(controller.editor!.values["voices"])
        controller.edit(VoicingEdits.cell("voices", rows: rows, index: 1, column: "low", value: .string("G2")))
        let first = voicingCommands
        XCTAssertEqual(first.map(\.name), ["set_voicing_values"])
        XCTAssertEqual(records(first[0].args["values"]?["voices"])[1]["low"], .string("G2"))
        XCTAssertEqual(records(controller.editor!.values["voices"])[1]["low"], .string("G2"))

        controller.addRecord("voices")
        controller.removeRecord(0, "voices")
        XCTAssertEqual(voicingCommands.dropFirst().map(\.name), ["add_voicing_record", "remove_voicing_record"])
        XCTAssertEqual(voicingCommands.last?.args["index"], .int(0))

        controller.moveRecord(2, -1, "voices")
        let move = voicingCommands.last!
        XCTAssertEqual(move.name, "move_voicing_record")
        XCTAssertEqual(move.args["index"], .int(2))
        XCTAssertEqual(move.args["offset"], .int(-1))
        XCTAssertEqual(move.args["field_id"], .string("voices"))
    }

    func testTwoQuickCellEditsBothStayBeforeAnyEcho() {
        editing()
        controller.onEditor(SettingsFixtures.ensemble)
        controller.editCell("voices", index: 0, column: "name", value: .string("Bass"))
        controller.editCell("voices", index: 1, column: "low", value: .string("G2"))
        // The (late) echo of the first edit doesn't undo the second.
        let first = voicingCommands[0].args["values"]!
        controller.onEditor(with(SettingsFixtures.ensemble) { $0.revision = 50; $0.values = first })
        let rows = records(controller.editor!.values["voices"])
        XCTAssertEqual(rows[0]["name"], .string("Bass"))
        XCTAssertEqual(rows[1]["low"], .string("G2"))
        let last = records(voicingCommands.last!.args["values"]?["voices"])
        XCTAssertEqual(last[0]["name"], .string("Bass"))
    }

    func testALostEditIsOpenedAgain() {
        editing()
        controller.onEditor(with(inactive) { $0.revision = 3 })
        XCTAssertEqual(names, ["begin_settings_edit"])
        XCTAssertEqual(controller.ui.phase, .opening)
    }

    func testTheDraftKeepsTheKeyAmericanWhateverTheNotation() {
        let s = SettingsFixtures.settings
        // An older config could send a European key: the draft takes it as American.
        let old = with(s) { $0.values.notation = Notation.european; $0.values.key = "Sol" }
        XCTAssertEqual(SettingsDraft.of(old).key, "G")
        let draft = with(SettingsDraft.of(s)) { $0.key = "Bb" }
        XCTAssertEqual(draft.withNotation(Notation.european).key, "Bb")
        XCTAssertEqual(draft.withNotation(Notation.european).toValues().key, "Bb")
        XCTAssertEqual(shownKey("Bb", notation: Notation.european, limits: s), "Sib")
        XCTAssertEqual(shownKey("Bb", notation: Notation.american, limits: s), "Bb")
    }

    func testRespellingKeysBetweenNotations() {
        let s = SettingsFixtures.settings
        XCTAssertEqual(respellKey("G#", notation: Notation.european, limits: s), "Sol#")
        XCTAssertEqual(respellKey("Sib", notation: Notation.american, limits: s), "Bb")
        XCTAssertEqual(respellKey("C", notation: Notation.american, limits: s), "C")
        XCTAssertEqual(respellKey("", notation: Notation.european, limits: s), "")
        XCTAssertEqual(respellKey("Xyz", notation: Notation.european, limits: s), "")
    }

    // MARK: - iOS additions

    func testTheLeaveDialogWordsEachProblemNumbersFirstInPageOrder() {
        editing()
        controller.onEditor(SettingsFixtures.fretboardInvalid)
        controller.setNumber(.bpm, "1000")
        controller.setNumber(.fontSize, " ")
        let lines = settingsProblemLines(controller.ui, editor: controller.editor, limits: controller.limits)
        XCTAssertEqual(Array(lines.prefix(2)), ["General, Font size: (empty). Enter a whole number from 6 to 72.",
                                         "Playback, Default BPM: 1000. Enter a whole number from 20 to 400."])
        XCTAssertEqual(Array(lines.dropFirst(2)), SettingsFixtures.fretboardInvalid.problems.map(\.text))
    }

    func testTheSteppersMoveANumberWithinItsRange() {
        editing()
        controller.stepNumber(.timeSignatureBeats, 1)
        XCTAssertEqual(controller.ui.draft?.timeSignatureBeats, 5)
        controller.setNumber(.timeSignatureBeats, "16")
        controller.stepNumber(.timeSignatureBeats, 1)
        XCTAssertEqual(controller.ui.draft?.timeSignatureBeats, 16)
        // From a wrong text the step goes from the saved value.
        controller.setNumber(.bpm, "abc")
        controller.stepNumber(.bpm, -1)
        XCTAssertEqual(controller.ui.draft?.bpm, 119)
        XCTAssertEqual(controller.ui.numberTexts, [:])
    }

    func testAScreenOpenedFromTheVoicingSheetStartsAtVoicings() {
        let fromSheet = SettingsController(initialPage: .voicings)
        XCTAssertEqual(fromSheet.ui.nav, SettingsNav(.voicings))
    }
}

/// The Settings scenes the integration test records (ios/Fixtures/settings_*)
/// fold into what the catalog draws: an editing controller, the schema, the song's text.
final class SettingsScenesTests: XCTestCase {
    private func scene(_ name: String) throws -> SessionSnapshot {
        try Fixture(contentsOf: SceneRecorder.directory.appendingPathComponent("\(name).json")).snapshot()
    }

    func testEverySettingsSceneFoldsIntoAnEditingScreenWithItsSchema() throws {
        let names = ["settings_open", "settings_voicing_form", "settings_voicing_refused", "settings_voicing_ensemble",
                     "settings_builtin"]
        for name in names {
            let snapshot = try scene(name)
            XCTAssertEqual(snapshot.voicingEditor?.active, true, name)
            let schema = try XCTUnwrap(snapshot.voicingEditorSchema, name)
            XCTAssertFalse(EditorSchema.parse(schema.schema).forms.isEmpty, name)
            XCTAssertNotNil(snapshot.settings, name)
            XCTAssertFalse(snapshot.text.isEmpty, "\(name): the song's text")
            let controller = SettingsController.showing(snapshot, nav: SettingsNav(.voicings, voicingDetail: true))
            XCTAssertEqual(controller.ui.phase, .editing, name)
            XCTAssertNotNil(controller.ui.draft, name)
            XCTAssertTrue(controller.outbox.isEmpty, name)
            XCTAssertEqual(controller.ui.nav, SettingsNav(.voicings, voicingDetail: true), name)
        }
    }

    func testTheScenesShowWhatTheirScreensNeed() throws {
        XCTAssertNil(try scene("settings_open").voicingEditor?.selected)
        let form = try XCTUnwrap(try scene("settings_voicing_form").voicingEditor)
        XCTAssertEqual(form.selected, "My 7-String")
        XCTAssertEqual(form.values["tuning"], .string("B1 E2 A2 D3 G3 B3 E4"))
        XCTAssertEqual(form.groups.first { $0.model == "fretboard" }?.names, ["My 7-String"])
        let refused = try XCTUnwrap(try scene("settings_voicing_refused").voicingEditor)
        XCTAssertEqual(refused.problems.count, 2)
        XCTAssertEqual(refused.invalid, ["My 7-String"])
        XCTAssertTrue(refused.hasErrors)
        let trio = try XCTUnwrap(try scene("settings_voicing_ensemble").voicingEditor)
        XCTAssertEqual(trio.model, "ensemble")
        XCTAssertEqual(records(trio.values["voices"]).map { $0["name"] }, [.string("Lead"), .string("Harmony"), .string("Bass")])
        let builtin = try XCTUnwrap(try scene("settings_builtin").voicingEditor)
        XCTAssertTrue(builtin.showsBuiltin)
        XCTAssertEqual(builtin.selected, "Guitar (Standard - EADGBE)")
    }
}

extension Array {
    /// The only element, else nil.
    var single: Element? { count == 1 ? first : nil }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `VoicingFormTest`, case for case: the schema-driven voicing form
/// against what Python sends (fixtures from a real session), plus the text
/// field's echo and the errors banner's timing (Android's `StateTextField`
/// and `FormErrorsBanner`, which are Compose there).
final class VoicingFormTests: XCTestCase {
    private let schema = SettingsFixtures.schema

    private func formOf(_ state: VoicingEditorState) -> [FormItem] {
        buildForm(schema.form(state.model)!, values: state.values, errors: state.fieldErrors, hints: state.hints)
    }

    private func fields(_ items: [FormItem]) -> [FieldItem] { items.flatMap(\.fields) }

    private func byId(_ items: [FormItem]) -> [String: FieldItem] {
        Dictionary(fields(items).map { ($0.spec.id, $0) }, uniquingKeysWith: { first, _ in first })
    }

    private func recordsOf(_ items: [FormItem]) -> [RecordsItem] {
        items.compactMap { if case .records(let r) = $0 { return r } else { return nil } }
    }

    private func headers(_ items: [FormItem]) -> [(title: String?, blurb: String?, level: Int)] {
        items.compactMap {
            if case .header(_, let title, let blurb, let level) = $0 { return (title, blurb, level) }
            return nil
        }
    }

    func testTheSchemaReadsModelsTextsHelpAndEveryModelsForm() {
        XCTAssertEqual(schema.models.map(\.model), ["fretboard", "ensemble", "piano"])
        XCTAssertEqual(schema.treeGroups.map(\.model), ["fretboard", "piano", "ensemble"])
        XCTAssertEqual(schema.text("name_label"), "Name")
        XCTAssertEqual(schema.text("remove_confirm"), "Remove voicing '{name}'?")
        XCTAssertTrue(schema.help["name"]!.contains("the player's Voicing sheet"))
        XCTAssertEqual(Set(schema.forms.keys), ["fretboard", "ensemble", "piano"])
        // Unknown models fall back to the piano form, as in Python.
        XCTAssertEqual(schema.form("harp")?.model, "piano")
    }

    func testEveryFieldKindAndSectionKindOfTheSchemaIsKnownToSwift() {
        var kinds = Set<FieldKind>()
        var sections = Set<SectionKind>()
        func walk(_ s: SectionSpec) {
            sections.insert(s.kind)
            for f in s.fields + s.rows.flatMap(\.fields) {
                kinds.insert(f.kind)
                f.columns.forEach { kinds.insert($0.kind) }
            }
            s.groups.forEach(walk)
        }
        schema.forms.values.flatMap(\.sections).forEach(walk)
        XCTAssertEqual(kinds, Set(FieldKind.allCases))
        XCTAssertEqual(sections, Set(SectionKind.allCases))
    }

    func testFretboardFormFieldListPerKindValuesFromTheState() {
        let items = formOf(SettingsFixtures.fretboardInvalid)
        let fields = byId(items)
        XCTAssertEqual(fields["tuning"]?.spec.kind, .pitchList)
        XCTAssertEqual(fields["tuning"]?.text, "E2 A2 X9 G3")
        XCTAssertEqual(fields["max_fret"]?.spec.kind, .int)
        XCTAssertEqual(fields["max_fret"]?.spec.min, 5)
        XCTAssertEqual(fields["max_fret"]?.spec.max, 24)
        XCTAssertEqual(fields["allow_barres"]?.spec.kind, .bool)
        XCTAssertEqual(fields["allow_barres"]?.checked, true)
        XCTAssertEqual(fields["weight:open_string_bonus"]?.spec.kind, .float)
        // The weights are a grid with a titled, blurbed header.
        let header = headers(items)
        XCTAssertEqual(header.count, 1)
        XCTAssertEqual(header.first?.title, "Weights")
        XCTAssertTrue(header.first?.blurb?.hasPrefix("Each weight") == true)
        XCTAssertTrue(items.contains {
            if case .grid(_, let fields) = $0 { return fields.contains { $0.spec.id == "weight:open_string_bonus" } }
            return false
        })
    }

    func testFieldErrorsAndHintsGoToTheirField() {
        let fields = byId(formOf(SettingsFixtures.fretboardInvalid))
        XCTAssertEqual(fields["tuning"]?.error, "Not a valid note name")
        XCTAssertEqual(fields["tuning"]?.hint, "(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4)")
        XCTAssertNil(fields["max_fret"]?.error)
        XCTAssertNil(fields["max_fret"]?.hint)
        // The relaxed span below the normal span: blamed on the field just edited.
        XCTAssertTrue(fields["relaxed_span"]?.error?.contains("Relaxed span") == true)
        // Python leaves the form errors out while a field has one.
        XCTAssertTrue(SettingsFixtures.fretboardInvalid.formErrors.isEmpty)
        XCTAssertTrue(SettingsFixtures.fretboardInvalid.hasErrors)
        // The supporting text: the error, else the hint and the help.
        XCTAssertEqual(fields["tuning"]?.supporting(), "Not a valid note name")
        let maxFret = fields["max_fret"]!
        XCTAssertEqual(maxFret.supporting(), maxFret.spec.help)
        XCTAssertNil(maxFret.supporting(withHelp: false))
    }

    func testEnsembleFormRecordsRowsWithCellErrorsFromErrorPath() {
        let items = formOf(SettingsFixtures.ensemble)
        let records = recordsOf(items)
        XCTAssertEqual(records.count, 1)
        let voices = records[0]
        XCTAssertEqual(voices.spec.id, "voices")
        XCTAssertEqual(voices.spec.columns.map(\.id), ["name", "low", "high", "staff", "gap", "movement"])
        // Voice 3 was added and moved up one place.
        XCTAssertEqual(voices.rows.map { r in r.cells.first { $0.spec.id == "name" }!.text },
                       ["Voice 1", "Voice 3", "Voice 2"])
        // min_items 2, max_items 8: may add and remove.
        XCTAssertTrue(voices.canAdd)
        XCTAssertTrue(voices.canRemove)
        let row1 = Dictionary(uniqueKeysWithValues: voices.rows[1].cells.map { ($0.spec.id, $0) })
        XCTAssertEqual(row1["low"]?.text, "H9")
        XCTAssertEqual(row1["low"]?.error, "Not a valid note name")
        // Voice 0's low is above its high: the rule blames both cells.
        XCTAssertTrue(voices.rows[0].cells.first { $0.spec.id == "low" }?.error?.contains("low < high") == true)
        XCTAssertNil(voices.rows[0].cells.first { $0.spec.id == "name" }?.error)
        // staff is a choice whose value is null: "Auto".
        XCTAssertEqual(row1["staff"]?.choice?.label, "Auto")
        XCTAssertEqual(voices.spec.cellErrorKey(1, "low"), "voice:1:low")
        let fields = byId(items)
        // No spacing field: the gaps are per voice.
        XCTAssertNil(fields["max_spacing"])
        XCTAssertNil(fields["movement"])  // a column of the voices table
        // The upper staff's clef: a choice in its own stack, plain treble by default.
        let clef = fields["upper_clef"]!
        XCTAssertEqual(clef.spec.kind, .choice)
        XCTAssertEqual(clef.spec.label, "Upper staff")
        XCTAssertEqual(clef.spec.choices.map(\.label), ["Treble", "Treble, octave lower (tenors)"])
        XCTAssertEqual(clef.choice?.label, "Treble")
        XCTAssertTrue(items.contains {
            if case .stack(_, let fields) = $0 { return fields.contains { $0.spec.id == "upper_clef" } }
            return false
        })
        // The nested groups (doubling, omit, inversion) are titled sub-grids.
        XCTAssertEqual(headers(items).filter { $0.level == 1 }.count, 3)
        XCTAssertTrue(SettingsFixtures.ensemble.formErrors.isEmpty)
    }

    func testEachVoiceHasAGapToTheNextOneOffInTheLastRow() {
        let voices = recordsOf(formOf(SettingsFixtures.ensemble))[0]
        let gap = voices.spec.columns.first { $0.id == "gap" }!
        XCTAssertEqual(gap.kind, .int)
        XCTAssertEqual(gap.label, "Max gap to next voice")
        XCTAssertTrue(gap.disabledInLastRow)
        XCTAssertFalse(voices.spec.columns.first { $0.id == "low" }!.disabledInLastRow)
        let gaps = voices.rows.map { r in r.cells.first { $0.spec.id == "gap" }! }
        XCTAssertEqual(gaps.map(\.text), ["19", "0", ""])
        XCTAssertEqual(gaps.map(\.enabled), [true, true, false])
        XCTAssertEqual(gaps[1].error, "Must be from 1 to 127")
        // The last row's gap is off and empty, though Python keeps its value.
        XCTAssertNil(gaps[2].error)
        XCTAssertEqual(records(SettingsFixtures.ensemble.values["voices"])[2]["gap"], .string("12"))
    }

    func testMoveButtonsAreOffAtTheEndsAndSayWhatTheyDo() {
        let voices = recordsOf(formOf(SettingsFixtures.ensemble))[0]
        XCTAssertEqual(voices.rows.map(\.canMoveUp), [false, true, true])
        XCTAssertEqual(voices.rows.map(\.canMoveDown), [true, true, false])
        XCTAssertEqual(voices.spec.moveUpHelp, "Move up")
        XCTAssertEqual(voices.spec.duplicateHelp, "Duplicate this voice")
        XCTAssertEqual(voices.spec.columns.first { $0.id == "movement" }?.label, "Movement cost")
        XCTAssertEqual(voices.spec.moveDownHelp, "Move down")
    }

    func testAReadOnlyFormABuiltInGreysEveryFieldAndHasNoRowButtons() {
        for state in [SettingsFixtures.fretboardInvalid, SettingsFixtures.ensemble, SettingsFixtures.piano] {
            let items = buildForm(schema.form(state.model)!, values: state.values, errors: state.fieldErrors,
                                  hints: state.hints, enabled: false)
            XCTAssertFalse(fields(items).isEmpty)
            XCTAssertTrue(fields(items).allSatisfy { !$0.enabled })
            // The values still show.
            XCTAssertEqual(fields(items).map(\.value), fields(formOf(state)).map(\.value))
            for records in recordsOf(items) {
                XCTAssertFalse(records.canAdd || records.canRemove)
                XCTAssertTrue(records.rows.allSatisfy { !$0.canMoveUp && !$0.canMoveDown })
                XCTAssertTrue(records.rows.flatMap(\.cells).allSatisfy { !$0.enabled })
            }
        }
    }

    func testTheErrorsBannerShowsWhileAFieldOrTheFormHasAnError() {
        XCTAssertTrue(SettingsFixtures.ensemble.hasErrors)
        XCTAssertFalse(SettingsFixtures.piano.hasErrors)
        let none = JSONValue.object([:])
        XCTAssertTrue(with(SettingsFixtures.piano) { $0.fieldErrors = none; $0.formErrors = ["Ensemble 'x': no"] }
            .hasErrors)
        XCTAssertFalse(with(SettingsFixtures.ensemble) { $0.fieldErrors = none; $0.formErrors = [] }.hasErrors)
        XCTAssertEqual(schema.text("errors_banner"), "Fix these errors to apply changes")
    }

    func testPianoFormRangeRowsOfLowAndHighPitchFieldsAGridWithAGroup() {
        let items = formOf(SettingsFixtures.piano)
        let ranges: [(key: String, label: String, low: FieldItem, high: FieldItem)] = items.compactMap {
            if case .range(let key, let label, _, let low, let high) = $0 { return (key, label, low, high) }
            return nil
        }
        XCTAssertEqual(ranges.map { String($0.key.dropFirst(2)) }, ["lh_range", "rh_range", "bass_range", "rh_low_anchor"])
        XCTAssertEqual(ranges[0].label, "Left hand")
        XCTAssertEqual(ranges[0].low.spec.id, "range:lh_range:low")
        XCTAssertEqual(ranges[0].high.spec.kind, .pitch)
        XCTAssertFalse(ranges[0].low.text.isEmpty)
        let fields = byId(items)
        XCTAssertEqual(fields["rh_center"]?.spec.step, 0.5)
        XCTAssertTrue(fields.keys.contains { $0.hasPrefix("nested:omit:") })
        XCTAssertTrue(self.fields(items).allSatisfy { $0.error == nil })
    }

    func testEditsBecomeSetVoicingValuesPayloadsKeyedByFieldId() {
        XCTAssertEqual(VoicingEdits.text("tuning", "E2 A2"), .object(["tuning": .string("E2 A2")]))
        XCTAssertEqual(VoicingEdits.bool("allow_barres", false), .object(["allow_barres": .bool(false)]))
        XCTAssertEqual(VoicingEdits.choice("x", .null), .object(["x": .null]))
        let rows = records(SettingsFixtures.ensemble.values["voices"])
        let payload = VoicingEdits.cell("voices", rows: rows, index: 1, column: "low", value: .string("G2"))
        let sent = records(payload["voices"])
        XCTAssertEqual(sent.count, 3)
        XCTAssertEqual(sent[1]["low"], .string("G2"))
        XCTAssertEqual(sent[1]["name"], .string("Voice 3"))
        XCTAssertEqual(sent[0], rows[0])
        XCTAssertEqual(Set(payload.members.keys), ["voices"])
        // The payload a command carries.
        let command = SentCommand(.setVoicingValues(values: payload))
        XCTAssertEqual(command.name, "set_voicing_values")
        XCTAssertEqual(command.args["values"], payload)
    }

    func testPendingEditsShowUntilAStateEchoesThem() {
        var pending = PendingEdits()
        let state = JSONValue.object(["tuning": .string("E2"), "max_fret": .string("12")])
        pending.record(VoicingEdits.text("tuning", "E2 A"))
        pending.record(VoicingEdits.text("tuning", "E2 A2"))
        XCTAssertEqual(pending.applyTo(state)["tuning"], .string("E2 A2"))
        // The reply to the first keystroke doesn't undo the second.
        pending.onState(.object(["tuning": .string("E2 A")]))
        XCTAssertEqual(pending.applyTo(state)["tuning"], .string("E2 A2"))
        pending.onState(.object(["tuning": .string("E2 A2")]))
        XCTAssertTrue(pending.isEmpty)
    }

    func testASecondCellEditBuildsOnTheFirstBeforeTheStateEchoesIt() {
        var pending = PendingEdits()
        let state = SettingsFixtures.ensemble.values
        let first = VoicingEdits.cell("voices", rows: records(pending.applyTo(state)["voices"]), index: 0,
                                      column: "low", value: .string("C3"))
        pending.record(first)
        let second = VoicingEdits.cell("voices", rows: records(pending.applyTo(state)["voices"]), index: 1,
                                       column: "low", value: .string("G2"))
        XCTAssertEqual(records(second["voices"]).map { $0["low"] }, [.string("C3"), .string("G2"), .string("C3")])
    }

    func testSteppersMoveByTheFieldsStepWithinItsRangeNeverParseRules() {
        let fields = byId(formOf(SettingsFixtures.piano))
        let center = fields["rh_center"]!.spec
        XCTAssertEqual(stepNumber(center, "63.0", 1), "63.5")
        XCTAssertEqual(stepNumber(center, "127", 3), "127.0")
        let maxNotes = fields["max_notes_per_hand"]!.spec
        XCTAssertEqual(stepNumber(maxNotes, "1", -1), "1")
        XCTAssertEqual(stepNumber(maxNotes, "4", 1), "5")
        let weight = byId(formOf(SettingsFixtures.fretboardInvalid))["weight:open_string_bonus"]!.spec
        XCTAssertEqual(stepNumber(weight, "0.5", 1), "0.6")
        XCTAssertEqual(stepNumber(weight, "0", -1), "-0.1")
        XCTAssertNil(stepNumber(weight, "abc", 1))
        // P8: − and + are off at the bounds (and on text that isn't a number).
        XCTAssertFalse(canStep(maxNotes, "1", -1))
        XCTAssertTrue(canStep(maxNotes, "1", 1))
        XCTAssertFalse(canStep(center, "127", 1))
        XCTAssertTrue(canStep(center, "127", -1))
        XCTAssertFalse(canStep(weight, "abc", 1))
        // Not plain numbers, as BigDecimal reads them.
        XCTAssertNil(stepNumber(weight, "12abc", 1))
        XCTAssertNil(stepNumber(weight, "", 1))
        XCTAssertEqual(stepNumber(weight, " 1.20 ", 1), "1.3")
    }

    // MARK: - The field's echo and the banner (Compose on Android)

    func testATypedTextStaysUntilTheValueBecomesSomethingItDidntSend() {
        var echo = FieldEcho("E2")
        echo.typed("E2 A")
        echo.typed("E2 A2")
        // A late echo of the first keystroke doesn't undo the second.
        echo.valueChanged("E2 A")
        XCTAssertEqual(echo.text, "E2 A2")
        echo.valueChanged("E2 A2")
        XCTAssertEqual(echo.text, "E2 A2")
        // A stepper, a preset or a model switch: a value it never sent replaces the text.
        echo.valueChanged("B1 E2")
        XCTAssertEqual(echo.text, "B1 E2")
        // An invalid text the session keeps as typed stays.
        echo.typed("X9")
        echo.valueChanged("X9")
        XCTAssertEqual(echo.text, "X9")
    }

    func testTheErrorsBannerWaitsForAnEditToRestAndGoesAtOnce() {
        var banner = ErrorsBanner()
        // A voicing that opens with errors shows them at once.
        XCTAssertFalse(banner.update(key: "A", hasErrors: true))
        XCTAssertTrue(banner.visible)
        XCTAssertFalse(banner.update(key: "A", hasErrors: false))
        XCTAssertFalse(banner.visible)
        // An error typed: shown after the delay.
        XCTAssertTrue(banner.update(key: "A", hasErrors: true))
        XCTAssertFalse(banner.visible)
        banner.delayElapsed(key: "A")
        XCTAssertTrue(banner.visible)
        // Fixed before the delay ran out: never shown.
        banner.update(key: "A", hasErrors: false)
        XCTAssertTrue(banner.update(key: "A", hasErrors: true))
        banner.update(key: "A", hasErrors: false)
        banner.delayElapsed(key: "A")
        XCTAssertFalse(banner.visible)
        // Another voicing's delay doesn't count.
        banner.update(key: "B", hasErrors: false)
        banner.update(key: "B", hasErrors: true)
        banner.delayElapsed(key: "A")
        XCTAssertFalse(banner.visible)
    }
}

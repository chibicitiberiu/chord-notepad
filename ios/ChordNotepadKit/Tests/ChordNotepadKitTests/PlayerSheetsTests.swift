import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `SheetRouteTest`, case for case, and the sheets' state: the speed
/// slider and Manual… field, the Playback settings rows and the commands each
/// sheet sends.
final class PlayerSheetsTests: XCTestCase {
    // MARK: - SheetRouteTest

    func testTheInstrumentSheetGoesFamiliesFamilyBackToFamiliesClosed() {
        let families = MainRoute.instrument(family: nil)
        let guitar = families.openingFamily(3)
        XCTAssertEqual(guitar, .instrument(family: 3))
        XCTAssertEqual(guitar.back(), families)
        XCTAssertEqual(families.back(), MainRoute.none)
    }

    func testAFamilysSheetDismissedNeedsTheFamiliesAgain() {
        XCTAssertTrue(MainRoute.instrument(family: 3).afterSheetDismissed() == (.instrument(family: nil), true))
        XCTAssertTrue(MainRoute.instrument(family: nil).afterSheetDismissed() == (MainRoute.none, false))
        XCTAssertTrue(MainRoute.voicing.afterSheetDismissed() == (MainRoute.none, false))
        XCTAssertTrue(MainRoute.speed(manual: false).afterSheetDismissed() == (MainRoute.none, false))
    }

    func testTheSpeedDialogGoesBackToTheSpeedSheet() {
        XCTAssertEqual(MainRoute.speed(manual: true).back(), .speed(manual: false))
        XCTAssertEqual(MainRoute.speed(manual: false).back(), MainRoute.none)
        XCTAssertEqual(MainRoute.voicing.back(), MainRoute.none)
        XCTAssertEqual(MainRoute.transpose(selection: true).back(), MainRoute.none)
        XCTAssertEqual(MainRoute.identify.back(), MainRoute.none)
    }

    func testTypedSpeedIsAPercentageFrom12_5To400LikeTheSessions() {
        XCTAssertEqual(parseSpeedPct("125"), 125)
        XCTAssertEqual(parseSpeedPct(" 125 % "), 125)
        XCTAssertEqual(parseSpeedPct("12.5"), 12.5)
        XCTAssertEqual(parseSpeedPct("12,5"), 12.5)
        XCTAssertEqual(parseSpeedPct("25"), 25)
        XCTAssertEqual(parseSpeedPct("400"), 400)
        for bad in ["12.4", "12", "401", "1.5", "-50", "", ".", "1..5", "abc", "99999999999", "1e2", "١٢٥"] {
            XCTAssertNil(parseSpeedPct(bad), bad)
        }
    }

    func testTheSliderSnapsTo5PercentStepsFrom12_5() {
        XCTAssertEqual(snapSpeedPct(123.4), 125)
        XCTAssertEqual(snapSpeedPct(5), 12.5)
        XCTAssertEqual(snapSpeedPct(13.5), 12.5)
        XCTAssertEqual(snapSpeedPct(14), 15)
        XCTAssertEqual(snapSpeedPct(420), 400)
        XCTAssertEqual(speedPctText(speedMinPct), "12.5")
        XCTAssertEqual(speedPctText(speedMaxPct), "400")
        XCTAssertEqual(speedPctText(133.3333), "133.3")
        XCTAssertEqual(speedPctText(100), "100")
    }

    func testTheSpeedBadgeShowsTheFactorWhenNot100Percent() {
        XCTAssertNil(speedBadge(100))
        XCTAssertEqual(speedBadge(125), "1.25×")
        XCTAssertEqual(speedBadge(50), "0.5×")
        XCTAssertEqual(speedBadge(200), "2×")
        XCTAssertEqual(speedBadge(25), "0.25×")
        XCTAssertEqual(speedBadge(12.5), "0.125×")
    }

    func testSongDefaultsPillAndWhatWriteIntoSongCanDo() {
        XCTAssertEqual(songDefaultsSummary(tempo: "90", time: "3/4", key: "G"), "90 · 3/4 · G")
        XCTAssertEqual(songDefaultsSummary(tempo: "120", time: "4/4", key: ""), "120 · 4/4")
        let allSet = defaults(tempo: ("90", true, 0), time: ("3/4", true, 10), key: ("G", true, 22))
        XCTAssertFalse(allSet.anythingToWrite)
        var unset = allSet
        unset.time = SongDefault(directiveOffset: nil, fromDirective: false, value: "4/4")
        XCTAssertTrue(unset.anythingToWrite)
        // An empty default key writes nothing.
        var noKey = allSet
        noKey.key = SongDefault(directiveOffset: nil, fromDirective: false, value: "")
        XCTAssertFalse(noKey.anythingToWrite)
        // While a song plays nothing can be written (paused, the session sends no reason).
        XCTAssertTrue(unset.canWrite)
        var locked = unset
        locked.lockedReason = "Pause to change the playback settings"
        XCTAssertFalse(locked.canWrite)
        XCTAssertTrue(locked.anythingToWrite)
        XCTAssertEqual(directiveCode(.tempo, "90"), "{bpm: 90}")
        XCTAssertEqual(directiveCode(.time, "3/4"), "{time: 3/4}")
        XCTAssertEqual(directiveCode(.key, "G"), "{key: G}")
    }

    // MARK: - The sheets' state and commands

    func testTheSliderFollowsTheFingerUntilTheSessionCatchesUp() throws {
        var slider = SpeedSlider()
        XCTAssertEqual(slider.shown(100), 100)
        let first = try XCTUnwrap(slider.moved(to: 123.4))
        try assertCommand(first, "set_multiplier_pct", #"{"pct": 125}"#)
        XCTAssertNil(slider.moved(to: 124.9), "the same stop sends nothing")
        XCTAssertEqual(slider.shown(100), 125, "the thumb stays where the finger is")
        slider.sessionChanged(110)
        XCTAssertEqual(slider.shown(110), 125, "an older value doesn't move it back")
        slider.sessionChanged(125)
        XCTAssertNil(slider.dragged)
        XCTAssertEqual(slider.shown(125), 125)
        XCTAssertEqual(speedFraction(speedMinPct), 0)
        XCTAssertEqual(speedFraction(speedMaxPct), 1)
        XCTAssertEqual(speedFraction(1000), 1)
        XCTAssertEqual(speedAt(fraction: 0.5), speedMinPct + (speedMaxPct - speedMinPct) / 2)
        XCTAssertEqual(speedAt(fraction: -1), speedMinPct)
    }

    func testTheManualSpeedIsCheckedBeforeOK() throws {
        var entry = SpeedEntry(pct: 133.3333)
        XCTAssertEqual(entry.text, "133.3")
        XCTAssertEqual(entry.supportingText, "12.5 to 400")
        entry.type("9")
        XCTAssertNil(entry.submit())
        XCTAssertTrue(entry.showError)
        XCTAssertEqual(entry.supportingText, "Enter a number from 12.5 to 400")
        entry.type("90 %")
        XCTAssertFalse(entry.showError, "typing clears the error")
        try assertCommand(try XCTUnwrap(entry.submit()), "set_multiplier_pct", #"{"pct": 90}"#)
    }

    func testThePlaybackSettingsRows() throws {
        let state = defaults(tempo: ("90", true, 0), time: ("3/4", false, nil), key: ("", false, nil))
        let rows = songDefaultRows(state, keys: ["C", "G"])
        XCTAssertEqual(rows.map(\.kind), [.tempo, .time, .key])
        XCTAssertEqual(rows.map(\.display), ["90 bpm", "3/4", "None"])
        XCTAssertEqual(rows.map(\.label), ["Tempo", "Time signature", "Key"])
        XCTAssertEqual(rows[0].code, "{bpm: 90}")
        XCTAssertEqual(rows[0].directiveOffset, 0)
        XCTAssertTrue(rows[0].fromDirective)
        XCTAssertEqual(rows[1].choices.first, "2/4")
        XCTAssertEqual(rows[1].choices.count, 12)
        XCTAssertEqual(rows[2].choices, ["C", "G"])
        XCTAssertNil(songDefaultChoice(rows[1], "3/4"), "the value already")
        try assertCommand(try XCTUnwrap(songDefaultChoice(rows[1], "6/8")), "set_time_signature",
                          #"{"beats": 6, "unit": 8}"#)
        try assertCommand(try XCTUnwrap(songDefaultChoice(rows[2], "G")), "set_key", #"{"key": "G"}"#)
        try assertCommand(try XCTUnwrap(tempoCommand("120")), "set_bpm_text", #"{"text": "120"}"#)
        XCTAssertNil(tempoCommand("  "), "OK is off with nothing typed")
    }

    func testInsertsEntriesInAndroidsOrder() {
        XCTAssertEqual(insertEntries.map(\.kind), [.bpm, .time, .key, .capo, .label, .loop])
        XCTAssertEqual(insertEntries.map(\.code), ["{bpm}", "{time}", "{key}", "{capo}", "{label}", "{loop}"])
        XCTAssertEqual(insertEntries.map(\.label),
                       ["Tempo", "Time signature", "Key", "Capo", "Label (section)", "Loop"])
    }

    // MARK: - Helpers

    private func defaults(tempo: (String, Bool, Int?), time: (String, Bool, Int?), key: (String, Bool, Int?))
        -> SongDefaultsState {
        func value(_ v: (String, Bool, Int?)) -> SongDefault {
            SongDefault(directiveOffset: v.2, fromDirective: v.1, value: v.0)
        }
        return SongDefaultsState(key: value(key), lockedReason: nil, summary: "", tempo: value(tempo),
                                 time: value(time))
    }
}

/// `command` is `name` with exactly the arguments `json`.
func assertCommand(_ command: BridgeCommand, _ name: String, _ json: String,
                   file: StaticString = #filePath, line: UInt = #line) throws {
    XCTAssertEqual(command.name, name, file: file, line: line)
    let actual = try JSONSerialization.jsonObject(with: Data(try command.argsJSON().utf8)) as? NSDictionary
    let expected = try JSONSerialization.jsonObject(with: Data(json.utf8)) as? NSDictionary
    XCTAssertEqual(actual, expected, file: file, line: line)
}

/// The names and arguments of `commands`.
func assertCommands(_ commands: [BridgeCommand], _ expected: [(String, String)],
                    file: StaticString = #filePath, line: UInt = #line) throws {
    XCTAssertEqual(commands.map(\.name), expected.map(\.0), file: file, line: line)
    for (command, (name, json)) in zip(commands, expected) {
        try assertCommand(command, name, json, file: file, line: line)
    }
}

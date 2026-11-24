import Foundation
import XCTest

@testable import ChordNotepadKit

/// The main screen's rules: Android's `ModeControllerTest`, `ScreenLayoutTest`,
/// `PlaybackUiTest` and `RenameFlowTest`, case for case, then the iOS parts
/// (the snackbars, the menu, the screen's own state, the player's state).
final class MainScreenTests: XCTestCase {
    private func doc(_ id: String?, modified: Bool = false, name: String? = nil) -> DocumentState {
        let name = name ?? id ?? "Untitled"
        return DocumentState(displayName: name, documentId: id, isModified: modified, location: nil, readOnly: false,
                             title: name)
    }

    // -- ModeControllerTest ----------------------------------------------------------------

    func testASavedSongOpensInPlayAnUntitledOneInEdit() {
        var saved = ModeController()
        saved.onDocument(doc("content://a"))
        XCTAssertEqual(saved.mode, .play)

        var untitled = ModeController()
        untitled.onDocument(doc(nil))
        XCTAssertEqual(untitled.mode, .edit)
    }

    func testAnOpenedSongSwitchesToPlayANewOneToEdit() {
        var m = ModeController()
        m.onDocument(doc(nil))
        m.expectOpen()
        m.onDocument(doc("content://a"))
        XCTAssertEqual(m.mode, .play)

        m.expectNew()
        m.onDocument(doc(nil))
        XCTAssertEqual(m.mode, .edit)
    }

    func testSavingAnUntitledSongKeepsTheMode() {
        var m = ModeController()
        m.onDocument(doc(nil))
        m.expectSave()
        m.onDocument(doc("content://saved"))
        XCTAssertEqual(m.mode, .edit)
    }

    func testACancelledOpenFollowedBySaveAsDoesntSwitch() {
        var m = ModeController()
        m.onDocument(doc(nil))
        m.expectOpen()
        m.expectSave()
        m.onDocument(doc("content://b"))
        XCTAssertEqual(m.mode, .edit)
    }

    func testTheUsersChoiceSticksOverLaterDocumentStatesOfTheSameSong() {
        var m = ModeController()
        m.onDocument(doc("content://a"))
        _ = m.select(.edit, playback: .idle)
        m.onDocument(doc("content://a", modified: true))
        XCTAssertEqual(m.mode, .edit)
    }

    func testSwitchingToEditWhilePlayingOrPausedStopsPlayback() {
        var m = ModeController(.play)
        XCTAssertTrue(m.select(.edit, playback: .playing))
        XCTAssertEqual(m.mode, .edit)
        _ = m.select(.play, playback: .idle)
        XCTAssertTrue(m.select(.edit, playback: .paused))
        _ = m.select(.play, playback: .idle)
        XCTAssertFalse(m.select(.edit, playback: .idle))
        XCTAssertFalse(m.select(.play, playback: .playing))
    }

    func testAnOpenIntoARunningAppSwitchesToPlayAndCountsTheOpen() {
        var m = ModeController()
        m.onDocument(doc(nil))
        _ = m.select(.edit, playback: .idle)
        XCTAssertEqual(m.opened, 0)
        m.expectOpen()
        // The unsaved-changes question doesn't change the document: no open yet.
        m.onDocument(doc(nil, modified: true))
        XCTAssertEqual(m.opened, 0)
        m.onDocument(doc("content://a"))
        XCTAssertEqual(m.mode, .play)
        XCTAssertEqual(m.opened, 1)
        m.onDocument(doc("content://a", modified: true))
        XCTAssertEqual(m.opened, 1)
    }

    func testAColdStartFromAnOpenCountsItOnce() {
        var m = ModeController()
        m.expectOpen()
        m.onDocument(doc("content://a"))
        XCTAssertEqual(m.mode, .play)
        XCTAssertEqual(m.opened, 1)
        // A rename (expectSave) changes the id but isn't an open.
        m.expectSave()
        m.onDocument(doc("content://b"))
        XCTAssertEqual(m.opened, 1)
    }

    func testTheSavedTabComesBackAfterProcessDeathNotOnceDecided() {
        var fresh = ModeController()
        fresh.restore(.play)
        fresh.onDocument(doc(nil, modified: true))
        XCTAssertEqual(fresh.mode, .play)

        var running = ModeController()
        running.onDocument(doc("content://a"))
        _ = running.select(.edit, playback: .idle)
        running.restore(.play)
        XCTAssertEqual(running.mode, .edit)
    }

    func testOpeningTheSongThatIsAlreadyOpenLandsInPlayToo() {
        var m = ModeController()
        m.onDocument(doc("content://t"))
        _ = m.select(.edit, playback: .idle)
        m.onDocument(doc("content://t", modified: true))
        m.expectOpen(target: "content://t", current: doc("content://t", modified: true))
        XCTAssertEqual(m.mode, .edit)
        m.onDocument(doc("content://t"))
        XCTAssertEqual(m.mode, .play)
        XCTAssertEqual(m.opened, 1)

        _ = m.select(.edit, playback: .idle)
        m.expectOpen(target: "content://t", current: doc("content://t"))
        XCTAssertEqual(m.mode, .play)
        XCTAssertEqual(m.opened, 2)
        _ = m.select(.edit, playback: .idle)
        m.onDocument(doc("content://t", modified: true))
        m.expectSave()
        m.onDocument(doc("content://t"))
        XCTAssertEqual(m.mode, .edit)
    }

    func testTheBundledQuickStartSongOpensInPlay() {
        // The app's first song is a draft with the bundle's store id: a saved song.
        var m = ModeController()
        m.onDocument(doc("bundle:01_quick_start.txt"))
        XCTAssertEqual(m.mode, .play)
        // The app asks for it as an open: the session's start-up replay (an
        // empty, untitled song) comes first and must not keep Edit.
        var app = ModeController()
        app.expectOpen()
        app.onDocument(doc(nil))
        XCTAssertEqual(app.mode, .edit)
        app.onDocument(doc("bundle:01_quick_start.txt"))
        XCTAssertEqual(app.mode, .play)
        XCTAssertEqual(app.opened, 1)
    }

    // -- ScreenLayoutTest ----------------------------------------------------------------------

    func testPhonePortraitInEditHasATwoLineHeaderAndNoChordSheet() {
        let l = ScreenLayout.of(width: 360, height: 640, mode: .edit, sheetVisible: true)
        XCTAssertTrue(l.phone)
        XCTAssertFalse(l.oneLineHeader)
        XCTAssertFalse(l.sheetBelow)
        XCTAssertFalse(l.sideBySide)
        XCTAssertEqual(l.headerHeight(mode: .edit), 97)
        XCTAssertEqual(l.headerHeight(mode: .play), 49)
    }

    func testPhoneLandscapeInEditPutsTabsAndRibbonOnOneLine() {
        XCTAssertTrue(ScreenLayout.of(width: 640, height: 360, mode: .edit, sheetVisible: true).oneLineHeader)
        XCTAssertFalse(ScreenLayout.of(width: 640, height: 360, mode: .play, sheetVisible: true).oneLineHeader)
        XCTAssertFalse(ScreenLayout.of(width: 1280, height: 800, mode: .edit, sheetVisible: true).oneLineHeader)
        XCTAssertEqual(ScreenLayout.of(width: 874, height: 402, mode: .edit, sheetVisible: false)
            .headerHeight(mode: .edit), 49)
    }

    func testTheChordSheetIsAPlayModeViewBelowInPortraitBesideInLandscape() {
        XCTAssertTrue(ScreenLayout.of(width: 360, height: 640, mode: .play, sheetVisible: true).sheetBelow)
        XCTAssertFalse(ScreenLayout.of(width: 360, height: 640, mode: .play, sheetVisible: false).sheetBelow)
        let side = ScreenLayout.of(width: 1280, height: 800, mode: .play, sheetVisible: true)
        XCTAssertTrue(side.sideBySide)
        XCTAssertTrue(side.compactPlayer)
        XCTAssertFalse(side.sheetBelow)
        XCTAssertTrue(ScreenLayout.of(width: 640, height: 360, mode: .play, sheetVisible: true).sideBySide)
        XCTAssertFalse(ScreenLayout.of(width: 640, height: 360, mode: .play, sheetVisible: false).sideBySide)
    }

    func testTheHeaderCollapsesOnlyInEditWithTheKeyboardUpAndLittleRoom() {
        XCTAssertTrue(collapseHeader(mode: .edit, keyboardVisible: true, textRoom: 120))
        XCTAssertFalse(collapseHeader(mode: .edit, keyboardVisible: true, textRoom: 170))
        XCTAssertFalse(collapseHeader(mode: .edit, keyboardVisible: false, textRoom: 50))
        XCTAssertFalse(collapseHeader(mode: .play, keyboardVisible: true, textRoom: 50))
    }

    func testTheSideColumnStaysWithin30To70Percent() {
        XCTAssertEqual(clampSideFraction(.nan), 0.5)
        XCTAssertEqual(clampSideFraction(0.1), 0.3)
        XCTAssertEqual(clampSideFraction(0.95), 0.7)
        XCTAssertEqual(sideFractionAt(handleX: 600, rowWidth: 1000), 0.4, accuracy: 1e-9)
        XCTAssertEqual(sideFractionAt(handleX: 10, rowWidth: 1000), 0.7)
        XCTAssertEqual(sideFractionAt(handleX: 5, rowWidth: 0), MainMetrics.sideFractionDefault)
    }

    func testTheSideColumnIsNeverTooNarrowForTheCompactPlayer() {
        for row in [816.0, 914, 640, 560, 1280, 2000, 874, 1180] {
            let lower = minSideFraction(row)
            let column = clampSideFraction(0.3, min: lower) * (row - MainMetrics.sideHandleWidth)
            XCTAssertGreaterThanOrEqual(column, MainMetrics.compactPlayerWidth - 0.01, "row \(row)")
            XCTAssertEqual(clampSideFraction(0.5, min: lower), max(0.5, lower))
            XCTAssertEqual(clampSideFraction(0.95, min: lower), max(0.7, lower))
        }
        XCTAssertEqual(minSideFraction(1280), MainMetrics.sideFractionMin)
        XCTAssertEqual(MainMetrics.compactPlayerWidth, 296)
    }

    func testPhoneLandscapeEditKeepsAShortTitleNextToTheRibbon() {
        XCTAssertEqual(oneLineTitleMaxWidth(914), 182.8, accuracy: 0.01)
        XCTAssertEqual(oneLineTitleMaxWidth(640), 128, accuracy: 0.01)
        XCTAssertEqual(oneLineTitleMaxWidth(400), 96)
        XCTAssertEqual(oneLineTitleMaxWidth(1400), 200)
    }

    func testTheChordSheetPaneIsTheSplitBelowOrTheColumnBeside() {
        // iPhone 17 portrait: the stored 160 pt; iPad Air portrait: 35 % of its 1180 pt.
        XCTAssertEqual(MainSheetPane.height(width: 402, height: 874, stored: 160), 160)
        XCTAssertEqual(MainSheetPane.height(width: 820, height: 1180, stored: 160)!, 413, accuracy: 1e-9)
        XCTAssertEqual(MainSheetPane.contentHeight(width: 402, height: 874, stored: 160), 102)
        // Landscape: the column is the window less the app bar (48 + 1) and the player (110).
        XCTAssertEqual(MainSheetPane.height(width: 1180, height: 820, stored: 160), 661)
        XCTAssertEqual(MainSheetPane.height(width: 874, height: 402, stored: 330), 243)
        XCTAssertEqual(MainSheetPane.contentHeight(width: 1180, height: 820, stored: 160), 661 - 38 - 20)
    }

    // -- PlaybackUiTest ---------------------------------------------------------------------------

    private func playback(_ status: PlaybackStatus, chord: Int? = nil) -> PlaybackState {
        PlaybackState(bar: 0, beat: 0, chordIndex: chord, key: nil, playheadOffset: nil, playingSpan: nil,
                      sections: [], status: status, tempoClamped: nil, timeSignature: [4, 4], totalBars: 0)
    }

    func testStartingIsPlayingBeforeTheFirstChord() {
        XCTAssertTrue(playback(.playing).isStarting)
        XCTAssertFalse(playback(.playing, chord: 0).isStarting)
        XCTAssertFalse(playback(.paused).isStarting)
        XCTAssertFalse(playback(.idle).isStarting)
    }

    func testTheScreenStaysOnOnlyWhilePlayingOrStarting() {
        XCTAssertTrue(keepScreenOn(playback(.playing)))
        XCTAssertTrue(keepScreenOn(playback(.playing, chord: 3)))
        XCTAssertFalse(keepScreenOn(playback(.paused, chord: 3)))
        XCTAssertFalse(keepScreenOn(playback(.idle)))
        XCTAssertFalse(keepScreenOn(nil))
    }

    func testSnackbarsStayInEditPlayUsesTheStatusLineAndClearsThePlayer() {
        XCTAssertTrue(statusSnackbarsShown(.edit))
        XCTAssertFalse(statusSnackbarsShown(.play))
        XCTAssertEqual(snackbarClearance(mode: .edit, sideBySide: false), 0)
        XCTAssertEqual(snackbarClearance(mode: .play, sideBySide: false), MainMetrics.playerHeight)
        XCTAssertEqual(snackbarClearance(mode: .play, sideBySide: true), 0)
    }

    func testAStoppedSongsStatusIsNoSnackbarInEdit() {
        XCTAssertFalse(statusSnackbarAllowed(mode: .edit, now: 10.4, stoppedAt: 10.0))
        XCTAssertTrue(statusSnackbarAllowed(mode: .edit, now: 12.0, stoppedAt: 10.0))
        XCTAssertTrue(statusSnackbarAllowed(mode: .edit, now: 0.005, stoppedAt: nil))
        XCTAssertFalse(statusSnackbarAllowed(mode: .play, now: 12.0, stoppedAt: nil))
    }

    func testTheSpeedBadgeShowsTheFactorExceptAt100Percent() {
        XCTAssertNil(speedBadge(100))
        XCTAssertEqual(speedBadge(125), "1.25×")
        XCTAssertEqual(speedBadge(50), "0.5×")
        XCTAssertEqual(speedBadge(200), "2×")
        XCTAssertEqual(speedBadge(112.5), "1.125×")
        XCTAssertEqual(speedBadge(33.33), "0.333×")
    }

    // -- RenameFlowTest ---------------------------------------------------------------------------

    func testTheFieldStartsWithTheNameWithoutItsExtension() {
        XCTAssertEqual(renameFieldText("Amazing Grace.txt"), "Amazing Grace")
        XCTAssertEqual(renameFieldText("Untitled"), "Untitled")
        XCTAssertEqual(renameFieldText("song.v2.cho"), "song.v2")
        XCTAssertEqual(renameFieldText("notes.toolong"), "notes.toolong")
    }

    func testTheFileNameKeepsTheDocumentsExtension() {
        XCTAssertEqual(renamedFileName(" Hymn ", currentDisplayName: "Amazing Grace.txt"), "Hymn.txt")
        XCTAssertEqual(renamedFileName("Hymn", currentDisplayName: "old.cho"), "Hymn.cho")
        XCTAssertEqual(renamedFileName("Hymn", currentDisplayName: "Untitled"), "Hymn.txt")
        XCTAssertEqual(renamedFileName("Hymn.pro", currentDisplayName: "old.txt"), "Hymn.pro")
        XCTAssertEqual(renamedFileName("  ", currentDisplayName: "old.txt"), "")
    }

    func testProblemsDisableRename() {
        XCTAssertEqual(renameProblem(" ", currentDisplayName: "a.txt"), .empty)
        XCTAssertEqual(renameProblem("a/b", currentDisplayName: "a.txt"), .badCharacter)
        XCTAssertEqual(renameProblem("a\u{7}", currentDisplayName: "a.txt"), .badCharacter)
        XCTAssertEqual(renameProblem("a", currentDisplayName: "a.txt"), .unchanged)
        XCTAssertNil(renameProblem("b", currentDisplayName: "a.txt"))
    }

    func testTheHintSaysTheFileNameTheProblemOrTheRefusal() {
        XCTAssertEqual(renameHint("Hymn", currentDisplayName: "a.txt", refusal: nil).text, "Saved as “Hymn.txt”")
        XCTAssertFalse(renameHint("Hymn", currentDisplayName: "a.txt", refusal: nil).error)
        XCTAssertTrue(renameHint("a:b", currentDisplayName: "a.txt", refusal: nil).error)
        XCTAssertEqual(renameHint("", currentDisplayName: "a.txt", refusal: nil).text, "Type a name")
        XCTAssertEqual(renameHint("b", currentDisplayName: "a.txt", refusal: "Taken").text, "Taken")
        XCTAssertTrue(renameHint("b", currentDisplayName: "a.txt", refusal: "Taken").error)
    }

    func testARefusedRenameOffersSaveAsWithTheTypedNameOrStaysInTheDialog() {
        var ui = MainUiState(mode: .play, route: .rename)
        ui.renameFailed(RenameFailure(name: "Hymn", reason: "This storage can't rename files.", canSaveAs: true))
        XCTAssertEqual(ui.route, .renameFailed(name: "Hymn", reason: "This storage can't rename files.", canSaveAs: true))

        ui = MainUiState(mode: .play, route: .rename)
        ui.renameFailed(RenameFailure(name: "Hymn", reason: "A song with that name exists.", canSaveAs: false))
        XCTAssertEqual(ui.route, .rename)
        XCTAssertEqual(ui.renameRefusal, "A song with that name exists.")
        ui.documentRenamed()
        XCTAssertEqual(ui.route, .none)
        XCTAssertNil(ui.renameRefusal)
    }

    // -- the snackbars -------------------------------------------------------------------------------

    private func snapshot(_ outputs: [SessionOutput]) -> SessionSnapshot {
        var snapshot = SessionSnapshot()
        for output in outputs { snapshot.apply(output) }
        return snapshot
    }

    func testANewStatusIsASnackbarInEditOnlyAndAnErrorInBothModes() {
        var bars = Snackbars()
        var s = snapshot([.statusState(StatusState(text: "Saved"))])
        bars.update(s, mode: .play, now: 1)
        XCTAssertNil(bars.shown)
        s.apply(.statusState(StatusState(text: "Saved: On My iPhone")))
        bars.update(s, mode: .edit, now: 2)
        XCTAssertEqual(bars.shown?.text, "Saved: On My iPhone")
        XCTAssertEqual(bars.shown?.error, false)
        bars.modeChanged(.play)
        XCTAssertNil(bars.shown)

        s.apply(.userError(UserError(message: "File not found: x", title: "")))
        bars.update(s, mode: .play, now: 3)
        XCTAssertEqual(bars.shown?.text, "File not found: x")
        XCTAssertEqual(bars.shown?.error, true)
        // An error stays over a later status, and across a mode switch.
        s.apply(.statusState(StatusState(text: "Bar 1/2")))
        bars.update(s, mode: .edit, now: 4)
        bars.modeChanged(.edit)
        XCTAssertEqual(bars.shown?.text, "File not found: x")
        bars.dismiss(bars.shown!.id)
        XCTAssertNil(bars.shown)
    }

    func testANoticeShowsInEitherModeButNotOverAnError() {
        var bars = Snackbars()
        bars.notice("Pause to change the voicing")
        XCTAssertEqual(bars.shown?.text, "Pause to change the voicing")
        XCTAssertEqual(bars.shown?.error, false)
        var s = SessionSnapshot()
        s.apply(.userError(UserError(message: "Broken", title: "")))
        bars.update(s, mode: .play, now: 1)
        bars.notice("Pause first")
        XCTAssertEqual(bars.shown?.text, "Broken")
    }

    func testWhatTheSnapshotAlreadyHeldDoesntPopUp() {
        let s = snapshot([.statusState(StatusState(text: "Ready")), .userError(UserError(message: "old", title: ""))])
        var bars = Snackbars(s)
        bars.update(s, mode: .edit, now: 1)
        XCTAssertNil(bars.shown)
    }

    func testAStoppedSongsStatusDoesntPopUpInEdit() {
        var bars = Snackbars()
        var s = snapshot([.playbackState(playback(.playing, chord: 2))])
        bars.update(s, mode: .play, now: 1)
        s.apply(.playbackState(playback(.idle)))
        s.apply(.statusState(StatusState(text: "Bar 5/8")))
        bars.update(s, mode: .edit, now: 1.2)
        XCTAssertNil(bars.shown)
        s.apply(.statusState(StatusState(text: "Saved")))
        bars.update(s, mode: .edit, now: 4)
        XCTAssertEqual(bars.shown?.text, "Saved")
    }

    func testTheTabsLoseTheirCaptionsOnlyOnAPhoneAtAccessibilitySizes() {
        XCTAssertTrue(modeTabLabelsShown(windowWidth: 402, accessibilityText: false))
        XCTAssertFalse(modeTabLabelsShown(windowWidth: 402, accessibilityText: true))
        XCTAssertTrue(modeTabLabelsShown(windowWidth: 820, accessibilityText: true))
    }

    // -- the menu ------------------------------------------------------------------------------------

    func testTheMenuHasAndroidsEntriesInOrderAndDiagnosticsWorks() {
        let recent = [DocumentRef(displayName: "a.txt", id: "a", location: "On My iPhone")]
        let sections = AppMenu.sections(recent: recent)
        var labels: [String] = []
        var enabled: [String] = []
        for section in sections {
            switch section {
            case .entries(let entries), .recent(let entries):
                labels += entries.map(\.label)
                enabled += entries.filter(\.enabled).map(\.label)
            case .separator:
                labels.append("—")
            }
        }
        XCTAssertEqual(labels, ["New song", "Open…", "a.txt", "—", "Save as…", "Export MIDI…", "Export audio…",
                                "Export PDF…", "—", "Settings", "Examples", "User guide", "Quick start", "About",
                                "Diagnostics"])
        XCTAssertEqual(enabled, ["Diagnostics"])
    }

    // -- the player's state ------------------------------------------------------------------------

    func testThePlayerShowsTheSessionsStates() throws {
        let s = snapshot([
            .songDefaultsState(SongDefaultsState(
                key: SongDefault(directiveOffset: 23, fromDirective: true, value: "Am"), lockedReason: nil,
                summary: "100 · 3/4 · Am", tempo: SongDefault(directiveOffset: 0, fromDirective: true, value: "100"),
                time: SongDefault(directiveOffset: 11, fromDirective: true, value: "3/4"))),
            .playbackState(playback(.playing, chord: 4)),
            .statusState(StatusState(text: "Bar 5/56 · Playing G")),
            .voicingMenuState(voicing),
            .instrumentMenuState(instruments),
        ])
        let player = PlayerState.of(s)
        XCTAssertEqual(player.pill, "100 · 3/4 · Am")
        XCTAssertTrue(player.playing)
        XCTAssertFalse(player.starting)
        XCTAssertEqual(player.status, "Bar 5/56 · Playing G")
        XCTAssertEqual(player.voicingLabel, "Guitar (standard)")
        XCTAssertEqual(player.instrumentLabel, "Steel Guitar")
        XCTAssertFalse(player.sheetVisible)
        XCTAssertEqual(PlayerState.of(SessionSnapshot(), fallbackStatus: "Starting…").status, "Starting…")
    }

    // -- MenuModelsTest ------------------------------------------------------------------------------

    private let voicing = VoicingMenuState(
        groups: [
            [MenuItem(label: "Piano", value: "piano")],
            [MenuItem(label: "Guitar (standard)", value: "guitar:standard"),
             MenuItem(label: "Ukulele", value: "guitar:ukulele")],
            [],
            [MenuItem(label: "SATB choir", value: "ensemble:satb")],
        ],
        lockedReason: nil, selected: "guitar:standard")

    private let instruments = InstrumentMenuState(current: 25, families: [
        InstrumentFamily(isCurrent: false, items: [MenuItem(label: "  0 - Acoustic Grand Piano", value: "0")],
                         name: "Piano"),
        InstrumentFamily(isCurrent: true, items: [
            MenuItem(label: " 24 - Nylon Guitar", value: "24"), MenuItem(label: " 25 - Steel Guitar", value: "25"),
            MenuItem(label: "bad", value: "x"),
        ], name: "Guitar"),
    ])

    func testVoicingRowsKeepTheGroupsApartAndMarkTheSelection() {
        XCTAssertEqual(voicingRows(voicing), [
            .choice(label: "Piano", value: "piano", selected: false),
            .divider,
            .choice(label: "Guitar (standard)", value: "guitar:standard", selected: true),
            .choice(label: "Ukulele", value: "guitar:ukulele", selected: false),
            .divider,
            .choice(label: "SATB choir", value: "ensemble:satb", selected: false),
        ])
        XCTAssertEqual(voicingRows(VoicingMenuState(groups: [], lockedReason: nil, selected: "piano")), [])
    }

    func testInstrumentFamiliesMarkTheCurrentFamilyAndProgram() {
        let families = instrumentFamilies(instruments)
        XCTAssertEqual(families.map(\.name), ["Piano", "Guitar"])
        XCTAssertEqual(families.map(\.isCurrent), [false, true])
        XCTAssertEqual(families[1].programs, [ProgramRow("24 - Nylon Guitar", 24, false),
                                              ProgramRow("25 - Steel Guitar", 25, true)])
        XCTAssertEqual(families[0].programs, [ProgramRow("0 - Acoustic Grand Piano", 0, false)])
        XCTAssertEqual(initialFamilyIndex(families), 1)
        XCTAssertEqual(initialFamilyIndex(families.map { FamilyRow($0.name, false, $0.programs) }), 0)
        XCTAssertEqual(initialFamilyIndex([]), 0)
    }

    func testRecentEntriesAreTheSessionsListNewestFirst() {
        let a = DocumentRef(displayName: "a.txt", id: "content://a", location: "Downloads/a.txt")
        let b = DocumentRef(displayName: "b.txt", id: "content://b", location: "Drive/b.txt")
        XCTAssertEqual(recentEntries(RecentDocumentsState(items: [a, b])), [a, b])
        XCTAssertTrue(recentEntries(RecentDocumentsState(items: [])).isEmpty)
        XCTAssertTrue(recentEntries(nil).isEmpty)
        XCTAssertEqual(recentEntries(RecentDocumentsState(items: [a, b]), max: 1), [a])
        XCTAssertEqual(recentEntries(RecentDocumentsState(items: [a, b]), max: 10), [a, b])
        XCTAssertTrue(recentEntries(RecentDocumentsState(items: [a, b]), max: 0).isEmpty)
    }

    func testMenuChoicesSendTheirCommands() throws {
        func json(_ command: BridgeCommand) throws -> [String: Any] {
            try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(try command.argsJSON().utf8)) as? [String: Any])
        }
        guard case .choice(_, let value, _) = voicingRows(voicing).last! else { return XCTFail("no choice") }
        let setVoicing = BridgeCommand.setVoicing(voicing: value)
        XCTAssertEqual(setVoicing.name, "set_voicing")
        XCTAssertEqual(try json(setVoicing)["voicing"] as? String, "ensemble:satb")
        let setInstrument = BridgeCommand.setInstrument(program: instrumentFamilies(instruments)[1].programs[0].program)
        XCTAssertEqual(setInstrument.name, "set_instrument")
        XCTAssertEqual(try json(setInstrument)["program"] as? Int, 24)
        let visible = BridgeCommand.setChordSheetVisible(visible: false)
        XCTAssertEqual(try json(visible)["visible"] as? Bool, false)
    }

    func testVoicingsAreGroupedByTheirValuesMissingGroupsLeftOut() {
        let state = VoicingMenuState(groups: [
            [MenuItem(label: "Piano", value: "piano")],
            [MenuItem(label: "Guitar (standard)", value: "guitar:standard")],
            [MenuItem(label: "Trio", value: "voicing:Trio")],
        ], lockedReason: nil, selected: "voicing:Trio")
        let groups = voicingGroups(state)
        XCTAssertEqual(groups.map(\.kind), [.piano, .fretted, .yours])
        XCTAssertTrue(groups.last!.choices.first!.selected)
        XCTAssertEqual(selectedVoicingLabel(state), "Trio")
    }

    func testProgramLabelsSplitIntoNameAndNumber() {
        XCTAssertTrue(programParts(ProgramRow("24 - Nylon Guitar", 24, false)) == ("Nylon Guitar", "24"))
        XCTAssertTrue(programParts(ProgramRow("Odd", 7, false)) == ("Odd", "7"))
        XCTAssertEqual(currentProgramName([FamilyRow("Guitar", true, [ProgramRow("25 - Steel Guitar", 25, true)])]),
                       "Steel Guitar")
    }
}

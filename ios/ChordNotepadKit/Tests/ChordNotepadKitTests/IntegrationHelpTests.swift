import Foundation
import XCTest

@testable import ChordNotepadKit

extension IntegrationTests {
    /// The chord identifier over Amazing Grace: C, E, G and B selected, Cmaj7
    /// played (Android's identify). Right after the start, while the status
    /// is still "Ready" as in Android's screenshot of a fresh app; cleared
    /// again afterwards.
    func recordIdentifier(_ session: Session, _ log: EventLog, _ scenes: SceneRecorder) async throws {
        let grace = try String(contentsOf: TestPython.repo.appendingPathComponent(
            "android/tools/help_shot_songs/amazing_grace.txt"), encoding: .utf8)
        let mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight") {
            $0.textRevision == restored.textRevision && $0.spans.contains { $0.kind == .chord }
        }
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
        let played = try log.decodeLatest(IdentifierState.self, "IdentifierState").soundingToken
        identifier.onState(try log.decodeLatest(IdentifierState.self, "IdentifierState"))
        identifier.pick("Cmaj7").forEach(session.submit)
        try await log.wait("Cmaj7 sounding") {
            (try? log.decodeLatest(IdentifierState.self, "IdentifierState"))?.soundingToken ?? 0 > played
        }
        await log.waitQuiet()
        XCTAssertEqual(try log.decodeLatest(StatusState.self, "StatusState").text, "Ready")
        try await scenes.record("identifier_cmaj7", "The chord identifier over Amazing Grace: C, E, G and B selected, "
                                + "Cmaj7 played; the status still the start's Ready.", from: mark)
        session.submit(.identifierClear())
        try await log.wait("the identifier cleared") {
            (try? log.decodeLatest(IdentifierState.self, "IdentifierState"))?.notes.isEmpty == true
        }
        await log.waitQuiet()
    }

    /// Scenes for the iOS user guide's screenshots (ios/tools/help_shots.json),
    /// as Android's help screenshots set them up (`android/tools/help_shots.json`:
    /// Amazing Grace, Piano, the piano roll 330 pt tall): the Quick Start
    /// tour, the song in Play with the playhead on its first chord in each of
    /// the four views, playing frozen on chord 5 (Em), the same with the
    /// metronome on at 125 %, the playhead on chord 5, and the colour demo in
    /// Edit. Last in the session, so no other scene changes.
    func recordHelpScenes(_ session: Session, _ log: EventLog, _ scenes: SceneRecorder) async throws {
        let songs = TestPython.repo.appendingPathComponent("android/tools/help_shot_songs")
        let grace = try String(contentsOf: songs.appendingPathComponent("amazing_grace.txt"), encoding: .utf8)
        let colours = try String(contentsOf: songs.appendingPathComponent("colours.txt"), encoding: .utf8)

        // -- the Quick Start tour --------------------------------------------------------------
        var mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let behind = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForHighlight(log, since: mark, "Amazing Grace's highlight under the tour") {
            $0.textRevision == behind.textRevision && $0.spans.contains { $0.kind == .chord }
        }
        session.submit(.requestQuickStart())
        try await log.wait("the tour") { !log.events(since: mark, type: "QuickStartContent").isEmpty }
        let tour = try log.decode(QuickStartContent.self, log.events(since: mark, type: "QuickStartContent").last)
        XCTAssertEqual(tour.pages.first?.title, "Welcome to Chord Notepad")
        XCTAssertEqual(tour.pages.count, 7)
        XCTAssertTrue(tour.pages[0].blocks.contains { $0.kind == "snippet" && !$0.spans.isEmpty })
        XCTAssertFalse(tour.pages.flatMap(\.blocks).contains { $0.kind == "image" }, "the mobile tour has no picture")
        await log.waitQuiet()
        try await scenes.record("quick_start_tour", "The Quick Start tour (request_quick_start).", from: mark)

        // -- Amazing Grace with the chord sheet ---------------------------------------------------
        session.submit(.setVoicing(voicing: "piano"))
        session.submit(.setInstrument(program: 0))
        session.submit(.resetMultiplier())
        if (try? log.decodeLatest(ToolbarState.self, "ToolbarState"))?.metronome == true {
            session.submit(.toggleMetronome())
        }
        session.submit(.setChordSheetVisible(visible: true))
        session.submit(.setChordSheetHeight(px: 330))
        session.submit(.setChordSheetView(viewId: "keyboard"))
        session.submit(.chordSheetZoomReset())
        _ = try await waitForSheet(log, "the piano roll shown at 330 pt") {
            $0.visible && $0.activeView == "keyboard" && $0.height == 330
        }
        await log.waitQuiet()
        let revisionBefore = try log.decodeLatest(ChordSheetState.self, "ChordSheetState").songRevision
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Amazing Grace.txt"), modified: false, readOnly: false,
                                     text: grace))
        let restored = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        _ = try await waitForSheet(log, "the chord sheet's render of Amazing Grace") {
            $0.songRevision > revisionBefore
        }
        let chords = try await waitForHighlight(log, since: mark, "Amazing Grace's chords") {
            $0.textRevision == restored.textRevision && $0.spans.contains { $0.kind == .chord }
        }.spans.filter { $0.kind == .chord }
        try await log.wait("the piano, the first program, 100 %, no metronome") {
            guard let toolbar = try? log.decodeLatest(ToolbarState.self, "ToolbarState"),
                  let voicings = try? log.decodeLatest(VoicingMenuState.self, "VoicingMenuState"),
                  let instruments = try? log.decodeLatest(InstrumentMenuState.self, "InstrumentMenuState")
            else { return false }
            return voicings.selected == "piano" && instruments.current == 0 && toolbar.multiplierPct == 100
                && !toolbar.metronome
        }
        try await sheetAt(view: "keyboard", playhead: chords[0].start, session, log)
        try await scenes.record("grace_play", "Amazing Grace in Play, the playhead on its first chord, the piano roll "
                                + "330 pt tall (Android's chord-sheet-piano-roll).", from: mark,
                                buffers: try await scenes.buffers(session, for: log.decodeLatest(ChordSheetState.self, "ChordSheetState")))
        try await sheetAt(view: "staff", playhead: chords[0].start, session, log)
        try await scenes.record("grace_staff", "Amazing Grace on the staff, Piano: Fret cards and Tab greyed "
                                + "(Android's chord-sheet-staff).", from: mark,
                                buffers: try await scenes.buffers(session, for: log.decodeLatest(ChordSheetState.self, "ChordSheetState")))
        session.submit(.setVoicing(voicing: "guitar:standard"))
        _ = try await waitForSheet(log, "the fret view available") {
            $0.views.contains { $0.viewId == "fret" && $0.available }
        }
        try await sheetAt(view: "fret", playhead: chords[0].start, session, log)
        try await scenes.record("grace_fret", "Amazing Grace on fret cards, the standard guitar "
                                + "(Android's chord-sheet-fret-cards).", from: mark,
                                buffers: try await scenes.buffers(session, for: log.decodeLatest(ChordSheetState.self, "ChordSheetState")))
        try await sheetAt(view: "tab", playhead: chords[0].start, session, log)
        try await scenes.record("grace_tab", "Amazing Grace as tab, the standard guitar (Android's chord-sheet-tab).",
                                from: mark,
                                buffers: try await scenes.buffers(session, for: log.decodeLatest(ChordSheetState.self, "ChordSheetState")))

        // Playing, frozen as chord 5 (Em, bar 6) sounds: the main screen's shots.
        session.submit(.setVoicing(voicing: "piano"))
        _ = try await waitForSheet(log, "the fret view greyed again") {
            !$0.views.contains { $0.viewId == "fret" && $0.available }
        }
        try await sheetAt(view: "keyboard", playhead: chords[0].start, session, log)
        var cut = try await freeze(session, log, chord: 5, of: chords)
        var frozen = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
        try await scenes.record("grace_playing", "Amazing Grace playing on the piano roll, frozen as chord 5 (Em, bar 6) "
                                + "sounds (Android's editor-main-window and main-play-labeled).",
                                from: mark, upTo: cut, buffers: try await scenes.buffers(session, for: frozen))
        // The player with the metronome on at 125 % (Android's player-labeled).
        session.submit(.toggleMetronome())
        session.submit(.setMultiplierPct(pct: 125))
        try await log.wait("the metronome on at 125 %") {
            guard let toolbar = try? log.decodeLatest(ToolbarState.self, "ToolbarState") else { return false }
            return toolbar.metronome && toolbar.multiplierPct == 125
        }
        cut = try await freeze(session, log, chord: 5, of: chords)
        frozen = try log.decode(ChordSheetState.self, log.events(upTo: cut, type: "ChordSheetState").last)
        try await scenes.record("grace_playing_metronome", "Amazing Grace playing, frozen on chord 5, the metronome on "
                                + "and the speed at 125 % (Android's player-labeled).",
                                from: mark, upTo: cut, buffers: try await scenes.buffers(session, for: frozen))
        session.submit(.toggleMetronome())
        session.submit(.resetMultiplier())
        // The playhead on chord 5, nothing playing (Android's playhead).
        session.submit(.setPlayhead(offset: chords[5].start))
        try await log.wait("the playhead on chord 5, the metronome off, 100 %") {
            guard let playback = try? log.decodeLatest(PlaybackState.self, "PlaybackState"),
                  let toolbar = try? log.decodeLatest(ToolbarState.self, "ToolbarState") else { return false }
            return playback.playheadOffset == chords[5].start && playback.status == .idle && !toolbar.metronome
                && toolbar.multiplierPct == 100
        }
        await log.waitQuiet()
        try await scenes.record("grace_playhead", "Amazing Grace in Play, the playhead on chord 5 (Em), nothing playing "
                                + "(Android's playhead).", from: mark,
                                buffers: try await scenes.buffers(session, for: log.decodeLatest(ChordSheetState.self, "ChordSheetState")))

        // -- the colour demo in Edit (Android's editor-colours) -------------------------------------
        session.submit(.setChordSheetVisible(visible: false))
        _ = try await waitForSheet(log, "the chord sheet hidden") { !$0.visible }
        mark = log.count
        session.submit(.restoreDraft(document: memoryRef("Colours.txt"), modified: false, readOnly: false,
                                     text: colours))
        let demo = try await waitForEdit(log, since: mark) { $0.undo == .reset }
        let painted = try await waitForHighlight(log, since: mark, "the colour demo's highlight") {
            $0.textRevision == demo.textRevision
        }
        let kinds = Set(painted.spans.map(\.kind))
        XCTAssertTrue(kinds.isSuperset(of: [.chord, .chordInvalid, .directive, .directiveInvalid, .comment]), "\(kinds)")
        await log.waitQuiet()
        try await scenes.record("colours_edit", "The colour demo (android/tools/help_shot_songs/colours.txt) in Edit: "
                                + "every span kind (Android's editor-colours).", from: mark)
    }

    /// The chord sheet on `view` at its default zoom, the playhead at `offset`
    /// and nothing playing, its render settled.
    private func sheetAt(view: String, playhead offset: Int, _ session: Session, _ log: EventLog) async throws {
        session.submit(.setChordSheetView(viewId: view))
        _ = try await waitForSheet(log, "the \(view) view") { $0.activeView == view }
        session.submit(.chordSheetZoomReset())
        session.submit(.setPlayhead(offset: offset))
        try await log.wait("the playhead set, nothing playing") {
            guard let playback = try? log.decodeLatest(PlaybackState.self, "PlaybackState") else { return false }
            return playback.playheadOffset == offset && playback.status == .idle
        }
        _ = try await waitForSheet(log, "the \(view) view at its default zoom") {
            $0.activeView == view && $0.zoom == 1 && $0.cursorIndex != nil
        }
        await log.waitQuiet()
    }
}

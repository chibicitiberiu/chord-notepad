import ChordNotepadKit
import Foundation
import SwiftUI
import UIKit
import os

/// Start-up timings, in seconds from the start of ``AppModel/start(fakePlayer:)``.
struct LaunchTimings: Codable, Equatable {
    var pythonBoot: Double?
    var sessionStart: Double?
    var firstText: Double?
    var error: String?
}

/// The app's one session (one interpreter and one session per process):
/// starts Python and the core, folds the session's output into a
/// ``SessionSnapshot`` the screens read, and sends commands.
///
/// Everything here runs on the main actor; Python runs on the kit's bridge
/// thread and its own threads, never here.
@MainActor
final class AppModel: ObservableObject {
    enum Phase: Equatable {
        case idle
        case starting
        case running
        case failed(String)
    }

    static let shared = AppModel()

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var snapshot = SessionSnapshot()
    @Published private(set) var timings = LaunchTimings()
    /// The main screen's own state: the tab, what is open over it, the keyboard.
    @Published var ui = MainUiState()
    /// The snackbar on screen.
    @Published private(set) var snackbars = Snackbars()
    /// Play mode's long-press explanation.
    private var hints = DirectiveHintState()
    private var hintTask: Task<Void, Never>?
    private var snackbarTask: Task<Void, Never>?
    private var snackbarShown: Int?
    /// The chord sheet's buffers, once the session runs.
    @Published private(set) var chordSheet: ChordSheetSource?
    /// The song editor: the text the user sees and edits (``snapshot``'s
    /// `text` has the session's edits only; the user's typing isn't echoed).
    let editor = EditorController()

    private(set) var runtime: PythonRuntime?
    private(set) var session: Session?
    private(set) var store: AppDocumentStore?
    private var reader: Task<Void, Never>?
    private var startedAt = ContinuousClock.now
    private var auditionState: OSSignpostIntervalState?

    /// What the status line shows while there is no session status yet.
    var phaseText: String {
        switch phase {
        case .idle: return "Not started"
        case .starting: return "Starting Python…"
        case .running: return snapshot.status?.text ?? "Ready"
        case .failed(let message): return "Failed: \(message)"
        }
    }

    /// The app's launch: start the session and open the quick-start song,
    /// unless XCTest hosts the process (its tests start their own).
    func launch() async {
        guard !AppEnvironment.isRunningTests, phase == .idle else { return }
        if AppEnvironment.startScreen == "selftest" {
            ui.route = .diagnostics
        }
        await start(fakePlayer: false)
    }

    /// Start Python, the session (FluidSynth's CoreAudio player, or the
    /// core's FakePlayer for tests), then open the quick-start song.
    func start(fakePlayer: Bool) async {
        guard phase == .idle else { return }
        phase = .starting
        startedAt = .now
        let signpost = Signposts.python.beginInterval("start")
        defer { Signposts.python.endInterval("start", signpost) }
        do {
            let runtime = try await PythonRuntime.start(Self.configuration(fakePlayer: fakePlayer))
            self.runtime = runtime
            timings.pythonBoot = elapsed()
            Log.python.info("Python started in \(self.timings.pythonBoot ?? 0, format: .fixed(precision: 3)) s")
            _ = try? await runtime.call("chordnotepad_ios.diagnostics", "enable_faulthandler",
                                        [Diagnostics.shared.faultLog.path])

            let store = AppDocumentStore(location: AppEnvironment.storageName)
            self.store = store
            let session = try await Session.start(runtime: runtime, store: store, options: Self.launchOptions())
            self.session = session
            editor.submit = { session.submit($0) }
            editor.playHandlers = playHandlers
            timings.sessionStart = elapsed()
            Log.bridge.info("Session started in \(self.timings.sessionStart ?? 0, format: .fixed(precision: 3)) s")
            reader = Task { [weak self] in
                for await event in session.events {
                    self?.receive(event)
                }
            }
            chordSheet = ChordSheetSource(session: session)
            phase = .running
            openQuickStart()
            switch AppEnvironment.startScreen {
            case "chordsheet":
                // CI's live chord sheet screenshot (ios/tools/ci_screenshots.sh): Play with the sheet.
                selectMode(.play)
                session.submit(.setChordSheetVisible(visible: true))
            case "editor":
                // CI's live editor check and screenshot: type into the text view in Edit.
                selectMode(.edit)
                Task { await self.runEditorCheck() }
            case "menu":
                // CI's screenshot of the menu, over the song.
                ui.route = .menu
            default:
                break
            }
        } catch {
            Log.python.error("Start failed: \(String(describing: error), privacy: .public)")
            timings.error = String(describing: error)
            phase = .failed(String(describing: error))
            Diagnostics.shared.writeJSON(timings, name: "launch.json")
        }
    }

    /// Python's settings: the bundled stdlib, the core and its packages, and
    /// where FluidSynth is (read when the core is imported).
    static func configuration(fakePlayer: Bool) -> PythonRuntime.Configuration {
        var environment = ["CHORD_NOTEPAD_LIBFLUIDSYNTH": AppPaths.fluidSynth.path]
        if fakePlayer {
            environment["CN_TEST_FAKE_PLAYER"] = "1"
        }
        return PythonRuntime.Configuration(
            home: AppPaths.pythonHome.path,
            searchPaths: [AppPaths.pythonApp.path, AppPaths.pythonPackages.path],
            environment: environment)
    }

    static func launchOptions() -> Session.LaunchOptions {
        Session.LaunchOptions(filesDir: AppPaths.filesDir.path, soundfontPath: AppPaths.soundFont?.path)
    }

    private func elapsed() -> Double {
        let duration = ContinuousClock.now - startedAt
        return Double(duration.components.seconds) + Double(duration.components.attoseconds) / 1e18
    }

    func openQuickStart() {
        guard let session, let store, let url = AppPaths.quickStart,
              let text = try? String(contentsOf: url, encoding: .utf8) else {
            Log.ui.error("The quick-start song is missing from the bundle")
            return
        }
        session.submit(.restoreDraft(document: store.bundledRef(url.lastPathComponent), modified: false,
                                     readOnly: false, text: text))
    }

    /// Play chord `index` of the song, as a tap on it does.
    func audition(index: Int = 0) {
        guard let session else { return }
        editor.sync()
        if let auditionState {
            Signposts.audio.endInterval("audition", auditionState)
        }
        auditionState = Signposts.audio.beginInterval("audition", id: Signposts.audio.makeSignpostID())
        Log.audio.info("Audition chord \(index)")
        session.submit(.audition(index: index, rolled: false))
        Signposts.audio.emitEvent("submitted")
    }

    private func receive(_ event: Session.Event) {
        do {
            let output = try SessionOutput.decode(typeName: event.typeName, json: event.json)
            let previousName = snapshot.document?.displayName
            snapshot.apply(output)
            editor.receive(output)
            switch output {
            case .documentState(let document):
                ui.modes.onDocument(document)
                if previousName != nil, document.displayName != previousName { ui.documentRenamed() }
            case .renameFailed(let event):
                ui.renameFailed(RenameFailure(event))
            case .directiveHint(let hint):
                hints.receive(hint)
                showHint()
            default:
                break
            }
            playChanged()
            scheduleSnackbars()
        } catch {
            Log.bridge.error("Undecodable \(event.typeName, privacy: .public): \(String(describing: error), privacy: .public)")
        }
        if let auditionState {
            Signposts.audio.endInterval("audition", auditionState, "first output: \(event.typeName)")
            self.auditionState = nil
        }
        if event.typeName == "UnexpectedError" || event.typeName == "UserError" || event.typeName == "AudioUnavailable" {
            Log.bridge.error("\(event.typeName, privacy: .public): \(event.json, privacy: .public)")
        }
        if timings.firstText == nil, !snapshot.text.isEmpty, snapshot.editor != nil,
           snapshot.document?.documentId != nil {
            timings.firstText = elapsed()
            Log.ui.info("First text after \(self.timings.firstText ?? 0, format: .fixed(precision: 3)) s")
            Diagnostics.shared.writeJSON(LaunchReport(timings: timings, snapshot: snapshot), name: "launch.json")
        }
    }

    // MARK: - The main screen's actions

    /// The user picked a tab: Edit while a song plays or is paused stops it.
    func selectMode(_ target: AppMode) {
        if ui.modes.select(target, playback: snapshot.playback?.status) {
            session?.submit(.stop())
        }
        snackbars.modeChanged(ui.mode)
        if target == .edit {
            hints.dismiss()
            showHint()
        }
        playChanged()
    }

    /// The editor's Play mode follows the tab and the session's playhead; the
    /// screen stays awake while a song plays.
    private func playChanged() {
        let playback = snapshot.playback
        editor.updatePlay(mode: ui.mode, playhead: playback?.playheadOffset, playing: playback?.status == .playing)
        let awake = keepScreenOn(playback)
        if UIApplication.shared.isIdleTimerDisabled != awake {
            UIApplication.shared.isIdleTimerDisabled = awake
        }
    }

    /// What Play mode's touches send (offsets from the text view, UTF-16).
    var playHandlers: PlayHandlers {
        PlayHandlers(
            tap: { [weak self] tap in
                guard let self else { return }
                switch tap {
                case .onChord(let start):
                    self.tapChord(utf16: start)
                case .nearest(let start):
                    self.setPlayhead(utf16: start)
                }
            },
            scrub: { [weak self] in self?.setPlayhead(utf16: $0) },
            explain: { [weak self] start in
                guard let self, let session = self.session else { return }
                self.editor.sync()
                session.submit(self.hints.explain(OffsetMapper(self.editor.model.text).toCodePoint(start)))
                self.showHint()
            },
            touched: { [weak self] in
                guard let self, self.hints.explained != nil else { return }
                self.hints.dismiss()
                self.showHint()
            })
    }

    /// A tapped chord: the playhead goes there and it sounds (`tap_chord_at`).
    func tapChord(utf16: Int) {
        guard let session else { return }
        editor.sync()
        if let auditionState {
            Signposts.audio.endInterval("audition", auditionState)
        }
        auditionState = Signposts.audio.beginInterval("audition", id: Signposts.audio.makeSignpostID())
        session.submit(.tapChordAt(offset: OffsetMapper(editor.model.text).toCodePoint(utf16), rolled: false))
        Signposts.audio.emitEvent("submitted")
    }

    /// Move the playhead to the chord at `utf16` (silent).
    func setPlayhead(utf16: Int) {
        guard let session else { return }
        editor.sync()
        session.submit(.setPlayhead(offset: OffsetMapper(editor.model.text).toCodePoint(utf16)))
    }

    func playPause() {
        editor.sync()
        session?.submit(.playPause(fromOffset: nil))
    }

    /// ⏮: stop and put the playhead back on the first chord.
    func rewind() {
        editor.sync()
        session?.submit(.rewind())
    }

    func toggleMetronome() {
        session?.submit(.toggleMetronome())
    }

    func toggleChordSheet() {
        guard let sheet = snapshot.chordSheet else { return }
        session?.submit(.setChordSheetVisible(visible: !sheet.visible))
    }

    func save() {
        ui.modes.expectSave()
        editor.sync()
        session?.submit(.save())
    }

    /// Rename to `name` (the session keeps the extension); the dialog stays
    /// until the title changes or the session refuses.
    func rename(_ name: String) {
        ui.modes.expectSave()
        ui.renameRefusal = nil
        session?.submit(.renameDocument(name: name))
    }

    func setVoicing(_ value: String) {
        session?.submit(.setVoicing(voicing: value))
    }

    func setInstrument(_ program: Int) {
        session?.submit(.setInstrument(program: program))
    }

    /// A menu entry: only what the iOS app has now (``AppMenu/available``).
    func choose(_ action: MenuAction) {
        if action == .diagnostics { ui.route = .diagnostics }
    }

    /// A short notice (why a greyed button does nothing).
    func notice(_ text: String) {
        snackbars.notice(text)
        timeSnackbar()
    }

    func dismissSnackbar(_ id: Int) {
        snackbars.dismiss(id)
    }

    /// Show the explanation the session sent, for 6 s or until the next touch.
    private func showHint() {
        editor.showHint(ui.mode == .play ? hints.explained : nil)
        hintTask?.cancel()
        guard hints.explained != nil else { return }
        hintTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(6))
            guard !Task.isCancelled, let self else { return }
            self.hints.dismiss()
            self.editor.showHint(nil)
        }
    }

    /// New output: after 150 ms (a song that opens switches to Play along with
    /// its status), show what's new as a snackbar.
    private func scheduleSnackbars() {
        Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(150))
            guard let self else { return }
            self.snackbars.update(self.snapshot, mode: self.ui.mode, now: ContinuousClock.now.seconds)
            self.timeSnackbar()
        }
    }

    /// A new snackbar goes away after its time.
    private func timeSnackbar() {
        guard let shown = snackbars.shown, shown.id != snackbarShown else { return }
        snackbarShown = shown.id
        snackbarTask?.cancel()
        snackbarTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(shown.duration))
            guard !Task.isCancelled else { return }
            self?.snackbars.dismiss(shown.id)
        }
    }

    /// `-CNScreen editor` (CI): once the song is on screen, type a long chord
    /// line into the real text view, wait for the session's highlight of it,
    /// and write `Diagnostics/editor.json`, which the screenshot waits for.
    func runEditorCheck() async {
        _ = await waitFor(timeout: .seconds(120)) { $0.highlight?.spans.isEmpty == false }
        let deadline = ContinuousClock.now + .seconds(30)
        while ContinuousClock.now < deadline,
              editor.textView == nil || !editor.model.text.contains(EditorScript.line) {
            try? await Task.sleep(for: .milliseconds(100))
        }
        let typed = EditorScript.type(into: editor)
        var highlighted = false
        if typed {
            highlighted = await EditorScript.waitForHighlight(editor, timeout: .seconds(30))
        }
        let report = EditorScript.report(editor, typed: typed, highlighted: highlighted)
        Log.ui.info("Editor check: \(report.ok ? "passed" : "failed", privacy: .public) \(report.problems.joined(separator: "; "), privacy: .public)")
        Diagnostics.shared.writeJSON(report, name: "editor.json")
    }

    /// Wait until `condition` holds for the snapshot (polled), or `timeout` passes.
    func waitFor(timeout: Duration, _ condition: (SessionSnapshot) -> Bool) async -> Bool {
        let deadline = ContinuousClock.now + timeout
        while ContinuousClock.now < deadline {
            if condition(snapshot) { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return condition(snapshot)
    }

    /// The scene went to the background or came back.
    func scenePhaseChanged(_ newPhase: ScenePhase) {
        guard let session else { return }
        switch newPhase {
        case .background:
            session.submit(.appBackground())
            Diagnostics.shared.mirror()
        case .active:
            session.submit(.appForeground())
        default:
            break
        }
    }
}

extension ContinuousClock.Instant {
    /// Seconds since an arbitrary start (the snackbars' clock).
    var seconds: Double {
        let duration = self - ContinuousClock.Instant.reference
        return Double(duration.components.seconds) + Double(duration.components.attoseconds) / 1e18
    }

    private static let reference = ContinuousClock.now
}

/// `Diagnostics/launch.json`: written once the first song is on screen (CI
/// waits for it before its screenshot).
struct LaunchReport: Codable {
    var timings: LaunchTimings
    var build = BuildInfo.current
    var document: String?
    var status: String?
    var textLength: Int
    var messages: [String]

    @MainActor init(timings: LaunchTimings, snapshot: SessionSnapshot) {
        self.timings = timings
        document = snapshot.document?.displayName
        status = snapshot.status?.text
        textLength = snapshot.text.count
        messages = snapshot.messages
    }
}

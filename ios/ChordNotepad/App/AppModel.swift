import ChordNotepadKit
import Foundation
import SwiftUI
import UIKit
import UniformTypeIdentifiers
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
    /// Settings while it is open (the kit's controller: Android's
    /// `SettingsController`); nil once it is left.
    @Published private(set) var settings: SettingsController?
    /// The save of a number being typed, once the typing rests (``draftSaveDelay``).
    private var settingsSave: Task<Void, Never>?
    /// The voicings editor's schema, read once it arrives.
    @Published private(set) var voicingSchema: EditorSchema?
    /// The song editor: the text the user sees and edits (``snapshot``'s
    /// `text` has the session's edits only; the user's typing isn't echoed).
    let editor = EditorController()
    /// View-only preferences (the side column's width), in UserDefaults.
    let preferences = UiPreferences(store: UserDefaultsPreferences())
    /// The landscape chord sheet column's share of the width, as last kept.
    @Published var sideFraction = UiPreferences(store: UserDefaultsPreferences()).sideFraction

    private(set) var runtime: PythonRuntime?
    private(set) var session: Session?
    private(set) var store: FileDocumentStore?
    /// The system's document pickers (the session test puts a stand-in here).
    var picker: DocumentPicking = SystemDocumentPicker()
    /// Answers the session's requests (the pickers, the unsaved-changes question).
    private var requests: RequestController?
    /// Files opened from Files or another app before the session ran.
    private var waitingURLs: [URL] = []
    /// Exports written and waiting for the export picker, oldest first.
    private var exportsToOffer: [(id: String, file: URL)] = []
    private var offeringExport = false
    /// `-CNScreen export` waits for its export (``runExportCheck()``).
    private var exportCheck = false
    /// `-CNScreen pdf` waits for its PDF (``runPdfCheck()``).
    private var pdfCheck = false
    /// Songs from Files were waiting when the session started (a document launch).
    private var launchOpensDocument = false
    /// The tour's "Show at startup" as the user just set it, until the
    /// session's settings echo it (Android's `QuickStartRoute`).
    @Published private(set) var quickStartPicked: Bool?
    /// The guide's page on screen, once one has loaded.
    @Published private(set) var guidePage: String?
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
        reportLaunch()
        if AppEnvironment.startScreen == nil {
            // `Diagnostics/startup.json`: what opened over the song at this
            // launch (CI's first launch after the install waits for the tour).
            _ = await waitForModel(timeout: .seconds(60)) { model in
                guard let startup = model.snapshot.startup else { return false }
                return startup.screen != .quickStart || (model.ui.route == .quickStart && model.snapshot.quickStart != nil)
            }
            let tour = ui.route == .quickStart && snapshot.quickStart != nil
            Diagnostics.shared.writeJSON(ToolScreenReport(name: "startup", ok: tour, route: String(describing: ui.route)),
                                         name: "startup.json")
        }
    }

    /// Tell the session how the app came up, so it decides what opens over the
    /// song (`app_started`: Quick Start at a direct launch while its setting
    /// is on; nothing for a song from Files or a CI hook). No purchase on iOS,
    /// so never the support prompt.
    private func reportLaunch() {
        guard phase == .running, let session else { return }
        let kind = LaunchKind.of(startScreen: AppEnvironment.startScreen, openingDocument: launchOpensDocument)
        let now = Date()
        let created = (try? FileManager.default.attributesOfItem(atPath: AppPaths.filesDir.path))?[.creationDate] as? Date
        session.submit(.appStarted(canAskForSupport: false, installedOn: isoDay(created ?? now),
                                   launchKind: kind.rawValue, today: isoDay(now)))
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

            let store = AppDocumentStore.make()
            store.discardAllExports()
            store.onExportWritten { [weak self] id, file in
                Task { @MainActor in self?.exportWritten(id: id, file: file) }
            }
            self.store = store
            let session = try await Session.start(runtime: runtime, store: store, options: Self.launchOptions())
            self.session = session
            requests = RequestController(
                pending: { [weak self] in self?.snapshot.request },
                submit: { session.submit($0) },
                answered: { [weak self] id in self?.snapshot.requestAnswered(id) },
                adopt: { url, _ in try store.adopt(url) },
                prepareExport: { _, name in try store.prepareExport(named: name) },
                runOffMain: { work, done in
                    Task.detached {
                        let ref = work()
                        await MainActor.run { done(ref) }
                    }
                },
                // Export PDF: the session's pages painted with UIGraphicsPDFRenderer and
                // written through the store, whose write offers the export picker.
                paint: { request in
                    PdfExporter(write: { id, data in try store.writeBytes(id: id, data: data) },
                                newCanvas: { UIKitPdfCanvas() }).export(request)
                })
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
            let waiting = waitingURLs
            waitingURLs = []
            launchOpensDocument = !waiting.isEmpty
            waiting.forEach(openURL)
            switch AppEnvironment.startScreen {
            case "chordsheet":
                // CI's live chord sheet screenshot (ios/tools/ci_screenshots.sh): Play with the sheet.
                selectMode(.play)
                session.submit(.setChordSheetVisible(visible: true))
            case "editor":
                // CI's live editor check and screenshot: type into the text view in Edit.
                selectMode(.edit)
                Task { await self.runEditorCheck() }
            case "export":
                // CI's live audio export: the real player's SoundFont, the store's file, the export picker.
                Task { await self.runExportCheck() }
            case "menu":
                // CI's screenshot of the menu, over the song.
                ui.route = .menu
            case "find":
                // CI's screenshot of the find bar with its Replace row, live (AppShortcuts.swift).
                Task { await self.runFindScreen() }
            case "speed", "instrument", "insert", "capo", "identify", "settings", "voicings", "about",
                 "families", "guide", "quickstart", "hint", "keyboard", "landscape":
                // CI's screenshots of a sheet, a tool or a page, live.
                Task { await self.runToolScreen(AppEnvironment.startScreen ?? "") }
            case "pdf":
                // CI's live PDF export: painted, written through the store, checked, then the picker.
                Task { await self.runPdfCheck() }
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
        guard let session, let url = AppPaths.quickStart,
              let text = try? String(contentsOf: url, encoding: .utf8) else {
            Log.ui.error("The quick-start song is missing from the bundle")
            return
        }
        // The session's start-up replay reports an empty, untitled song first:
        // the bundled song is the open that decides the tab (Play, as a saved song).
        // It is read only, so Save asks where to save it (Save As).
        ui.modes.expectOpen()
        snapshot.requestAnswered(nil)
        session.submit(.restoreDraft(document: AppDocumentStore.bundledRef(url.lastPathComponent), modified: false,
                                     readOnly: true, text: text))
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
            ui.received(output)
            switch output {
            case .settingsState(let state):
                settingsAct { $0.onSettings(state) }
                // The tour's checkbox follows the setting once the session has echoed it.
                if quickStartPicked == state.values.showQuickStartOnStartup { quickStartPicked = nil }
            case .voicingEditorState(let state):
                settingsAct { $0.onEditor(state) }
            case .voicingEditorSchema(let event):
                voicingSchema = EditorSchema.parse(event.schema)
            case .startupState(let state) where state.screen == .quickStart:
                // The session's answer to app_started: the tour opens over the song.
                openTour()
            default:
                break
            }
            switch output {
            case .documentState(let document):
                ui.modes.onDocument(document)
                if previousName != nil, document.displayName != previousName { ui.documentRenamed() }
            case .renameFailed(let event):
                ui.renameFailed(RenameFailure(event))
            case .directiveHint(let hint):
                hints.receive(hint)
                showHint()
            case .confirmDiscardRequest, .pickDocumentRequest, .insertDirectiveRequest, .paintPdfRequest:
                requestArrived()
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

    /// A tap in the player's sheets, the ribbon's tools or their dialogs: the
    /// kit's reducer decides the route, the fields and the commands (the
    /// editor's text first when a tool reads it).
    func sheet(_ event: SheetEvent) {
        let current = snapshot
        var effects = SheetEffects()
        editor.run { model in
            effects = ui.handle(event, snapshot: current, editor: &model)
            return effects.commands
        }
        if let id = effects.answered { snapshot.requestAnswered(id) }
        if let notice = effects.notice { self.notice(notice) }
        if let page = effects.openSettings { openSettings(page: page) }
        if let offset = effects.editAt {
            selectMode(.edit)
            editor.placeCursor(codePoint: offset)
        }
    }

    // MARK: - Settings

    /// Open Settings (at `page`: Edit voicings… opens Voicings). The edit
    /// begins in the session (`begin_settings_edit`); the schema is asked for
    /// once per process.
    func openSettings(page: SettingsPage? = nil) {
        editor.sync()
        var controller = SettingsController(initialPage: page)
        controller.start(needSchema: snapshot.voicingEditorSchema == nil)
        if let state = snapshot.settings { controller.onSettings(state) }
        if let state = snapshot.voicingEditor { controller.onEditor(state) }
        settings = controller
        ui.route = .settings
        flushSettings()
    }

    /// A change to Settings (a tap, a typed value, a state from the session):
    /// the controller's commands go out, a number being typed is saved once
    /// it rests, and the screen goes once the edit has ended.
    func settingsAct(_ change: (inout SettingsController) -> Void) {
        guard var controller = settings else { return }
        change(&controller)
        settings = controller
        flushSettings()
    }

    private func flushSettings() {
        guard var controller = settings else { return }
        let commands = controller.takeCommands()
        settings = controller
        for command in commands { session?.submit(command) }
        settingsSave?.cancel()
        settingsSave = nil
        if controller.ui.phase == .closed {
            settings = nil
            if ui.route == .settings { ui.route = .none }
            return
        }
        if controller.needsSave {
            settingsSave = Task { [weak self] in
                try? await Task.sleep(for: .milliseconds(Int(draftSaveDelay * 1000)))
                guard !Task.isCancelled else { return }
                self?.settingsAct { $0.saveDraft() }
            }
        }
    }

    /// A full-screen page's ← (About, the licences, a licence's text).
    func pageBack() {
        ui.route = ui.route.parent
    }

    /// A menu entry: only what the iOS app has now (``AppMenu/available``).
    /// The file commands send the editor's text first, as Android's do.
    func choose(_ action: MenuAction) {
        switch action {
        case .diagnostics:
            ui.route = .diagnostics
        case .examples:
            ui.route = .examples
        case .newSong:
            editor.sync()
            ui.modes.expectNew()
            session?.submit(.newDocument())
        case .open:
            editor.sync()
            ui.modes.expectOpen()
            session?.submit(.openDocument(readOnly: false, ref: nil))
        case .openRecent(let ref):
            editor.sync()
            ui.modes.expectOpen(target: ref.id, current: snapshot.document)
            session?.submit(.openRecent(ref: ref))
        case .saveAs:
            saveAs(name: nil)
        case .exportMidi:
            editor.sync()
            session?.submit(.exportMidi())
        case .exportAudio:
            editor.sync()
            session?.submit(.exportAudio())
        case .settings:
            openSettings()
        case .about:
            ui.route = .about
        case .exportPdf:
            // A4 or Letter from the region, as Android's locale country.
            editor.sync()
            session?.submit(.exportPdf(page: paperFor(Locale.current.region?.identifier)))
        case .userGuide:
            guidePage = nil
            ui.route = .userGuide
        case .quickStart:
            openTour()
        }
    }

    // MARK: - Quick Start

    /// Open the tour: the session sends its pages (`request_quick_start`).
    func openTour() {
        editor.sync()
        quickStartPicked = nil
        ui.route = .quickStart
        session?.submit(.requestQuickStart())
    }

    /// Leave the tour (✕, Done, a song opened from Files); the startup screen
    /// is dismissed in the session at once, so it doesn't come back.
    func closeTour() {
        if ui.route == .quickStart { ui.route = .none }
        if snapshot.startup?.screen == .quickStart {
            snapshot.startupDismissed()
            session?.submit(.dismissStartupScreen())
        }
    }

    /// The tour's "Show at startup" (the same setting as Settings › General's switch).
    func setShowQuickStart(_ show: Bool) {
        quickStartPicked = show
        session?.submit(.setShowQuickStartOnStartup(show: show))
    }

    /// The guide put a page on screen.
    func guideLoaded(_ url: String) {
        guidePage = url
    }

    /// Save As, suggesting `name` (typed without the extension, after a
    /// rename the storage refused) or the document's own.
    func saveAs(name: String?) {
        editor.sync()
        ui.modes.expectSave()
        session?.submit(.saveAs(name: name))
    }

    /// The unsaved-changes question's answer (nil: dismissed, as Cancel).
    func answerDiscard(_ choice: DiscardChoice?) {
        guard case .confirmDiscard(let request)? = snapshot.request else { return }
        requests?.answerDiscard(request, choice)
    }

    /// Open a copy of the bundled example `name` (Android's Examples sheet).
    func openExample(_ name: String) {
        guard let store else { return }
        editor.sync()
        // An open copy with unsaved edits must not be picked again as "identical".
        let skip = snapshot.document.flatMap { $0.isModified ? $0.documentId : nil }
        let library = AppDocumentStore.examples
        Task.detached {
            let copy = Result { try store.exampleCopy(library, name: name, skipId: skip) }
            await MainActor.run {
                switch copy {
                case .success(let ref):
                    self.ui.modes.expectOpen(target: ref.id, current: self.snapshot.document)
                    self.session?.submit(.openDocument(readOnly: false, ref: ref))
                case .failure(let error):
                    Log.store.error("Copying the example \(name, privacy: .public) failed: \(String(describing: error), privacy: .public)")
                    self.showError("Couldn't copy the example \(name) into the app's storage.")
                }
            }
        }
    }

    /// A song opened from Files or another app (`onOpenURL`): bookmarked and
    /// opened like a picked one (the session asks about unsaved changes first).
    func openURL(_ url: URL) {
        guard phase == .running, let store, let session else {
            waitingURLs.append(url)
            return
        }
        editor.sync()
        Task.detached {
            let adopted = Result { try store.adopt(url) }
            await MainActor.run {
                switch adopted {
                case .success(let ref):
                    // Nothing over the screen: the unsaved-changes question may
                    // follow. Settings is left as ← leaves it: it asks first
                    // while a value is wrong (Android's P1).
                    switch self.ui.route.onSongOpened {
                    case .leaveSettings: self.settingsAct { $0.requestClose() }
                    case .close where self.ui.route == .quickStart: self.closeTour()
                    case .close: self.ui.route = .none
                    case .stay: break
                    }
                    self.ui.modes.expectOpen(target: ref.id, current: self.snapshot.document)
                    session.submit(.openDocument(readOnly: false, ref: ref))
                case .failure(let error):
                    Log.store.error("Can't keep \(url.lastPathComponent, privacy: .public): \(String(describing: error), privacy: .public)")
                    self.showError("Failed to open file: \(url.lastPathComponent)")
                }
            }
        }
    }

    /// A request just arrived: the controller answers or cancels what has no
    /// screen, and says which picker to open.
    private func requestArrived() {
        guard let launch = requests?.onPending(snapshot.request) else { return }
        switch launch {
        case .open(let types):
            picker.pickToOpen(contentTypes: types.compactMap { UTType($0) }) { [weak self] url in
                self?.requests?.onPicked(url)
            }
        case .save(let name):
            // The export picker needs the file first: an empty one with the
            // name, which it moves; the session then writes the song into it.
            let folder = FileManager.default.temporaryDirectory
                .appendingPathComponent("save-\(UUID().uuidString)", isDirectory: true)
            let file = folder.appendingPathComponent(name)
            do {
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try Data().write(to: file)
            } catch {
                Log.store.error("Can't make the file to save: \(error.localizedDescription, privacy: .public)")
                requests?.onPicked(nil)
                return
            }
            picker.pickToMove(file) { [weak self] url in
                try? FileManager.default.removeItem(at: folder)
                self?.requests?.onPicked(url)
            }
        case .export:
            // Answered with the store's file; offered once written (exportWritten).
            break
        }
    }

    /// The store wrote an export's file: offer it with the export picker, one at a time.
    private func exportWritten(id: String, file: URL) {
        if exportCheck {
            // `-CNScreen export`: what the store got, before the picker opens over it.
            let data = (try? Data(contentsOf: file)) ?? Data()
            let riff = data.prefix(4) == Data("RIFF".utf8)
            Diagnostics.shared.writeJSON(ExportReport(file: file.lastPathComponent, bytes: data.count, riff: riff,
                                                      ok: riff && data.count > 10_000, problem: nil),
                                         name: "export.json")
            exportCheck = false
        }
        if pdfCheck, file.pathExtension == "pdf" {
            // `-CNScreen pdf`: the file the store got, read back with PDFKit.
            Diagnostics.shared.writeJSON(PdfReport.of(file, song: editor.model.text), name: "pdf.json")
            try? Diagnostics.shared.copy(file, name: "export.pdf")
            pdfCheck = false
        }
        exportsToOffer.append((id, file))
        offerNextExport()
    }

    private func offerNextExport() {
        guard !offeringExport, let next = exportsToOffer.first else { return }
        offeringExport = true
        picker.pickToExport(next.file) { [weak self] saved in
            guard let self else { return }
            Log.store.info("Export \(next.file.lastPathComponent, privacy: .public): \(saved == nil ? "not saved" : "saved", privacy: .public)")
            self.store?.discardExport(next.id)
            self.exportsToOffer.removeFirst()
            self.offeringExport = false
            self.offerNextExport()
        }
    }

    /// An error of the app's own, as a snackbar.
    private func showError(_ text: String) {
        snackbars.error(text)
        timeSnackbar()
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

    /// `-CNScreen export` (CI): once the song is on screen, export it as audio
    /// with the real player's SoundFont (the session test's FakePlayer has
    /// none, so the core refuses there). `Diagnostics/export.json` says what
    /// the store got, written before the export picker opens; the screenshot
    /// then shows the picker.
    func runExportCheck() async {
        _ = await waitFor(timeout: .seconds(120)) { $0.highlight?.spans.isEmpty == false }
        let before = snapshot.messageCount
        exportCheck = true
        choose(.exportAudio)
        _ = await waitFor(timeout: .seconds(120)) { snapshot in
            !self.exportCheck || snapshot.messageCount > before
        }
        if exportCheck {
            exportCheck = false
            let problem = snapshot.messageCount > before ? snapshot.messages.last : "no export after 120 s"
            Diagnostics.shared.writeJSON(ExportReport(file: nil, bytes: 0, riff: false, ok: false, problem: problem),
                                         name: "export.json")
        }
    }

    /// `-CNScreen speed|instrument|insert|capo|identify|settings|voicings|about`
    /// (CI): once the song is on screen, open that sheet, tool or page as a
    /// person would (the speed at 125 %, the Guitar family's programs with
    /// Steel Guitar from the real SoundFont, Insert › Tempo, Suggest Capo scored, the
    /// identifier with C, E, G and B and Cmaj7 picked, Settings › General,
    /// Settings › Voicings with the built-in standard guitar shown, About),
    /// then write `Diagnostics/tool-<name>.json`, which the screenshot waits for.
    func runToolScreen(_ name: String) async {
        _ = await waitFor(timeout: .seconds(120)) { $0.highlight?.spans.isEmpty == false }
        var ok = false
        /// What a hook saw, for the report when it isn't ready.
        var detail: String?
        switch name {
        case "speed":
            selectMode(.play)
            sheet(.open(.speed(manual: false)))
            sheet(.speedDragged(124))
            ok = await waitFor(timeout: .seconds(30)) { $0.toolbar?.multiplierPct == 125 }
        case "instrument":
            selectMode(.play)
            sheet(.open(.instrument(family: nil)))
            sheet(.chooseInstrument(25))
            sheet(.openFamily(3))
            ok = await waitFor(timeout: .seconds(30)) { snapshot in
                guard let menu = snapshot.instrumentMenu, menu.families.count > 3 else { return false }
                return menu.current == 25 && !menu.families[3].items.isEmpty
            }
        case "insert":
            selectMode(.edit)
            sheet(.ribbon(.insert))
            sheet(.insert(.bpm))
            // The dialog's task asks the session to check its first fields.
            ok = await waitFor(timeout: .seconds(30)) { snapshot in
                guard case .insertDirective(let request)? = snapshot.request else { return false }
                return snapshot.directiveCheck?.requestId == request.requestId
            }
        case "capo":
            selectMode(.edit)
            sheet(.ribbon(.capo))
            ok = await waitFor(timeout: .seconds(60)) {
                $0.capoAdvice?.active == true && $0.capoAdvice?.status == CapoAdviceState.ready
            }
        case "identify":
            selectMode(.edit)
            sheet(.ribbon(.identify))
            // One key at a time, as a person taps: the field follows each tap's state.
            var tapped = 0
            for key in PianoKeyboard().keys where [60, 64, 67, 71].contains(key.midi) {
                sheet(.identifierTap(key))
                tapped += 1
                let count = tapped
                _ = await waitFor(timeout: .seconds(10)) { $0.identifier?.notes.count == count }
            }
            ok = await waitFor(timeout: .seconds(30)) { $0.identifier?.candidates.contains("Cmaj7") == true }
            if ok { sheet(.identifierPick("Cmaj7", rolled: false)) }
        case "settings":
            openSettings(page: .general)
            ok = await waitForSettings(timeout: .seconds(30)) { $0.ui.phase == .editing && $0.ui.draft != nil }
        case "voicings":
            openSettings(page: .voicings)
            ok = await waitForSettings(timeout: .seconds(30)) {
                $0.ui.phase == .editing && $0.editor != nil && self.snapshot.voicingEditorSchema != nil
            }
            if ok {
                settingsAct { $0.selectBuiltin(model: "fretboard", label: "Guitar (Standard - EADGBE)") }
                ok = await waitForSettings(timeout: .seconds(30)) {
                    $0.editor?.state.showsBuiltin == true && $0.editor?.state.selected == "Guitar (Standard - EADGBE)"
                }
            }
        case "about":
            ui.route = .about
            ok = true
        case "families":
            // The Instrument sheet's families, Grand Piano the current one (Android's instrument-families).
            selectMode(.play)
            sheet(.open(.instrument(family: nil)))
            sheet(.chooseInstrument(0))
            ok = await waitFor(timeout: .seconds(30)) { $0.instrumentMenu?.current == 0 }
        case "guide":
            choose(.userGuide)
            ok = await waitForModel(timeout: .seconds(60)) { $0.guidePage != nil }
            // The theme's fonts and images after the page itself.
            try? await Task.sleep(for: .seconds(2))
        case "quickstart":
            openTour()
            ok = await waitFor(timeout: .seconds(30)) { $0.quickStart != nil }
        case "hint":
            // A typo'd tempo in Play, touched and held (Android's directive-explain).
            restoreSong(HelpShotSongs.typo, name: "Amazing Grace.txt")
            ok = await waitFor(timeout: .seconds(30)) { snapshot in
                snapshot.text == HelpShotSongs.typo && snapshot.highlight?.spans.contains { $0.kind == .directiveInvalid } == true
            }
            selectMode(.play)
            try? await Task.sleep(for: .seconds(1))
            if ok {
                // The song starts with the red {bpm: 500}.
                playHandlers.explain(0)
                ok = await waitFor(timeout: .seconds(15)) { $0.directiveHint != nil }
                // The card by the directive, on screen (shown again once the text has settled).
                try? await Task.sleep(for: .milliseconds(500))
                showHint()
                let card = editor.textView?.hintCard
                ok = ok && card?.isHidden == false
                detail = "explained \(hints.explained != nil), mode \(ui.mode), card "
                    + (card.map { $0.isHidden ? "hidden" : "shown" } ?? "none") + ", hint "
                    + (snapshot.directiveHint.map { "\($0.offset) \($0.start)-\($0.end) \($0.message)" } ?? "none")
            }
        case "keyboard":
            // A new song typed in Edit with the keyboard up (Android's edit-keyboard).
            choose(.newSong)
            ok = await waitFor(timeout: .seconds(30)) { $0.document?.documentId == nil && $0.text.isEmpty }
            selectMode(.edit)
            try? await Task.sleep(for: .seconds(1))
            ok = ok && EditorScript.type(HelpShotSongs.typed, at: 0, into: editor)
            if ok {
                ok = await waitFor(timeout: .seconds(30)) { snapshot in
                    snapshot.highlight?.spans.filter { $0.kind == .chord }.count == 4
                }
            }
        case "landscape":
            // The phone on its side, typing in Edit: the header gives way (Android's edit-keyboard-collapsed).
            if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene {
                scene.requestGeometryUpdate(.iOS(interfaceOrientations: .landscapeRight)) { error in
                    Log.ui.error("Rotation: \(error.localizedDescription, privacy: .public)")
                }
            }
            // Amazing Grace as a song of the user's (the bundled one is read only: no keyboard).
            restoreSong(HelpShotSongs.grace, name: "Amazing Grace.txt", readOnly: false)
            ok = await waitFor(timeout: .seconds(30)) { $0.text == HelpShotSongs.grace && $0.editor?.readOnly == false }
            selectMode(.edit)
            try? await Task.sleep(for: .seconds(2))
            let line = (editor.model.text as NSString).range(of: "That saved a wretch like me")
            ok = ok && line.location != NSNotFound && EditorScript.type(" x", at: NSMaxRange(line), into: editor)
            try? await Task.sleep(for: .seconds(2))
            ok = ok && ui.keyboardHeight > 0
            detail = "mode \(ui.mode), keyboard \(ui.keyboardHeight), editable \(editor.textView?.isEditable == true)"
        default:
            break
        }
        Log.ui.info("Tool screen \(name, privacy: .public): \(ok ? "ready" : "failed", privacy: .public)")
        Diagnostics.shared.writeJSON(ToolScreenReport(name: name, ok: ok, route: String(describing: ui.route),
                                                      detail: detail),
                                     name: "tool-\(name).json")
    }

    /// Open `text` as the song `name`, saved (a help screenshot's song).
    private func restoreSong(_ text: String, name: String, readOnly: Bool = true) {
        guard let session else { return }
        editor.sync()
        ui.modes.expectOpen()
        snapshot.requestAnswered(nil)
        session.submit(.restoreDraft(document: DocumentRef(displayName: name, id: "bundle:\(name)", location: name),
                                     modified: false, readOnly: readOnly, text: text))
    }

    /// `-CNScreen pdf` (CI): once the song is on screen, export it as a PDF:
    /// the session lays the pages out, the app paints them and the store
    /// writes the file. `Diagnostics/pdf.json` says what the file holds (its
    /// pages, whether the song's first lyric line is in its text, the font's
    /// advance) and `Diagnostics/export.pdf` is the file itself, written
    /// before the export picker opens; the screenshot then shows the picker.
    func runPdfCheck() async {
        _ = await waitFor(timeout: .seconds(120)) { $0.highlight?.spans.isEmpty == false }
        let before = snapshot.messageCount
        pdfCheck = true
        choose(.exportPdf)
        _ = await waitFor(timeout: .seconds(120)) { snapshot in !self.pdfCheck || snapshot.messageCount > before }
        if pdfCheck {
            pdfCheck = false
            let problem = snapshot.messageCount > before ? snapshot.messages.last : "no PDF after 120 s"
            Diagnostics.shared.writeJSON(PdfReport(problem: problem), name: "pdf.json")
        }
    }

    /// Wait until `condition` holds for the model (polled), or `timeout` passes.
    func waitForModel(timeout: Duration, _ condition: (AppModel) -> Bool) async -> Bool {
        let deadline = ContinuousClock.now + timeout
        while ContinuousClock.now < deadline {
            if condition(self) { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return condition(self)
    }

    /// Wait until `condition` holds for Settings (polled), or `timeout` passes.
    func waitForSettings(timeout: Duration, _ condition: (SettingsController) -> Bool) async -> Bool {
        let deadline = ContinuousClock.now + timeout
        while ContinuousClock.now < deadline {
            if let settings, condition(settings) { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return settings.map(condition) ?? false
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

/// `Diagnostics/tool-<name>.json` (`-CNScreen speed|instrument|insert|capo|identify|...`):
/// whether the sheet or tool got to the state the screenshot shows.
struct ToolScreenReport: Codable {
    var name: String
    var ok: Bool
    var route: String
    var detail: String?
}

/// `Diagnostics/export.json` (`-CNScreen export`): the audio export the store
/// wrote, or why there was none.
struct ExportReport: Codable {
    var file: String?
    var bytes: Int
    var riff: Bool
    var ok: Bool
    var problem: String?
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

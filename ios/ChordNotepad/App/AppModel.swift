import ChordNotepadKit
import Foundation
import SwiftUI
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
    @Published var showSelfTest = false

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
            showSelfTest = true
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
            timings.sessionStart = elapsed()
            Log.bridge.info("Session started in \(self.timings.sessionStart ?? 0, format: .fixed(precision: 3)) s")
            reader = Task { [weak self] in
                for await event in session.events {
                    self?.receive(event)
                }
            }
            phase = .running
            openQuickStart()
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
            try snapshot.apply(typeName: event.typeName, json: event.json)
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

import Foundation
import UIKit

/// Where the app's pieces are: Python and the frameworks in the bundle, the
/// app's files in its container (docs/IOS.md, "The app bundle").
enum AppPaths {
    static var bundle: URL { Bundle.main.bundleURL }

    /// `PyConfig.home`: `python/lib/python3.14` holds the standard library.
    static var pythonHome: URL { bundle.appendingPathComponent("python", isDirectory: true) }
    /// The core and the kit's glue (`chordnotepad`, `chordnotepad_ios`).
    static var pythonApp: URL { pythonHome.appendingPathComponent("app", isDirectory: true) }
    /// The core's packages.
    static var pythonPackages: URL { pythonHome.appendingPathComponent("app_packages", isDirectory: true) }

    /// FluidSynth's binary, which the core's FluidSynth binding loads by path
    /// (`CHORD_NOTEPAD_LIBFLUIDSYNTH`).
    static var fluidSynth: URL {
        (Bundle.main.privateFrameworksURL ?? bundle.appendingPathComponent("Frameworks"))
            .appendingPathComponent("FluidSynth.framework/FluidSynth")
    }

    /// The SoundFont the app ships.
    static var soundFont: URL? { Bundle.main.url(forResource: "GeneralUser-GS", withExtension: "sf2") }

    /// The quick-start song the shell opens.
    static var quickStart: URL? { Bundle.main.url(forResource: "01_quick_start", withExtension: "txt") }

    /// The recorded scenes the preview catalog shows (ios/Fixtures).
    static var fixtures: URL { bundle.appendingPathComponent("Fixtures", isDirectory: true) }

    /// Application Support: the core's `files_dir` (config, data, logs).
    static var filesDir: URL {
        directory(FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0])
    }

    /// The core's rotating log folder (`files_dir/data/chord-notepad/logs`).
    static var coreLogs: URL { filesDir.appendingPathComponent("data/chord-notepad/logs", isDirectory: true) }

    /// Where the app writes its own diagnostics (fault handler, MetricKit,
    /// self-test, launch timings), under Application Support.
    static var diagnostics: URL { directory(filesDir.appendingPathComponent("Diagnostics", isDirectory: true)) }

    /// The copy of the diagnostics the Files app shows (Documents is the
    /// only folder it can see: UIFileSharingEnabled).
    static var sharedDiagnostics: URL {
        directory(FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Diagnostics", isDirectory: true))
    }

    /// The songs folder of the Files app's "Chord Notepad" location.
    static var documents: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

    private static func directory(_ url: URL) -> URL {
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}

/// How the process was started.
enum AppEnvironment {
    /// Hosting XCTest: the tests start the session themselves (one per process).
    static var isRunningTests: Bool {
        let environment = ProcessInfo.processInfo.environment
        return environment["XCTestConfigurationFilePath"] != nil
            || environment["XCTestBundlePath"] != nil
            || environment["XCTestSessionIdentifier"] != nil
    }

    /// A Debug build (About's build type).
    static var debugBuild: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }

    /// `-CNScreen selftest` opens the self-test at launch, `-CNScreen
    /// chordsheet` shows the chord sheet (CI's screenshots).
    static var startScreen: String? { argument(after: "-CNScreen") }

    private static func argument(after flag: String) -> String? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: flag), index + 1 < arguments.count else { return nil }
        return arguments[index + 1]
    }

    /// "On My iPhone" / "On My iPad", the Files app's name for the app's storage.
    @MainActor static var storageName: String {
        UIDevice.current.userInterfaceIdiom == .pad ? "On My iPad" : "On My iPhone"
    }
}

/// The build stamp: version, build number and the commit CI built
/// (Info.plist `CNGitCommit` and `CNBuildDate`, from the xcodebuild command line).
struct BuildInfo: Codable, Equatable {
    var version: String
    var build: String
    var commit: String
    var date: String

    static let current: BuildInfo = {
        let info = Bundle.main.infoDictionary ?? [:]
        func value(_ key: String, _ fallback: String) -> String {
            let text = (info[key] as? String) ?? ""
            return text.isEmpty ? fallback : text
        }
        return BuildInfo(version: value("CFBundleShortVersionString", "?"), build: value("CFBundleVersion", "?"),
                         commit: value("CNGitCommit", "dev"), date: value("CNBuildDate", ""))
    }()

    /// "0.6.2 (41) abc1234".
    var line: String { "\(version) (\(build)) \(commit)" }
}

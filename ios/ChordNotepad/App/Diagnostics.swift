import Foundation
import MetricKit
import os

/// The unified log: subsystem `com.tibich.chordnotepad`, one category per
/// layer. `log stream --predicate 'subsystem == "com.tibich.chordnotepad"'`
/// on a Mac shows them; Python's own output arrives through
/// `use_system_logger` under the process's name.
enum Log {
    static let subsystem = "com.tibich.chordnotepad"
    static let bridge = Logger(subsystem: subsystem, category: "bridge")
    static let python = Logger(subsystem: subsystem, category: "python")
    static let audio = Logger(subsystem: subsystem, category: "audio")
    static let store = Logger(subsystem: subsystem, category: "store")
    static let ui = Logger(subsystem: subsystem, category: "ui")
}

/// Signposts for Instruments (docs/IOS.md, S2): a tap's way to sound.
///
/// `audition` is an interval from the tap to the session's first output
/// after the command, with an event when the command is queued on the
/// bridge. The note-on and the render happen in Python, on its threads;
/// signposts there need a `_cnbridge` hook (BACKLOG.md).
enum Signposts {
    static let audio = OSSignposter(subsystem: Log.subsystem, category: "audio")
    static let python = OSSignposter(subsystem: Log.subsystem, category: "python")
}

/// The files that make a device session pay off later (docs/IOS.md,
/// "Diagnostics"):
///
/// - Application Support/Diagnostics: `faulthandler.log` (Python's tracebacks
///   on a native crash), `metrickit/` (MetricKit's daily metrics and crash and
///   hang diagnostics), `launch.json` (start-up timings), `selftest.json`;
/// - the core's rotating log, in Application Support/data/chord-notepad/logs.
///
/// The Files app can't see Application Support, so ``mirror()`` copies all
/// of it into Documents/Diagnostics (at launch, when the app goes to the
/// background, and before an export), and ``exportArchive()`` zips that copy
/// for the share sheet.
final class Diagnostics: NSObject, MXMetricManagerSubscriber, @unchecked Sendable {
    static let shared = Diagnostics()

    private let queue = DispatchQueue(label: "com.tibich.chordnotepad.diagnostics", qos: .utility)

    var faultLog: URL { AppPaths.diagnostics.appendingPathComponent("faulthandler.log") }
    private var metricKitFolder: URL { AppPaths.diagnostics.appendingPathComponent("metrickit", isDirectory: true) }

    /// Subscribe to MetricKit and refresh the visible copy.
    func start() {
        MXMetricManager.shared.add(self)
        writeJSON(BuildInfo.current, name: "build.json")
        mirror()
    }

    // MARK: MetricKit (delivered on a device, about once a day; never in the simulator)

    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            save(payload.jsonRepresentation(), kind: "metrics")
        }
    }

    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        for payload in payloads {
            save(payload.jsonRepresentation(), kind: "diagnostics")
        }
        mirror()
    }

    private func save(_ data: Data, kind: String) {
        queue.async { [self] in
            try? FileManager.default.createDirectory(at: metricKitFolder, withIntermediateDirectories: true)
            let name = "\(kind)-\(Self.stamp()).json"
            do {
                try data.write(to: metricKitFolder.appendingPathComponent(name), options: .atomic)
                Log.ui.info("Saved MetricKit \(kind, privacy: .public) payload \(name, privacy: .public)")
            } catch {
                Log.ui.error("Saving a MetricKit payload failed: \(error.localizedDescription, privacy: .public)")
            }
        }
    }

    // MARK: Files

    /// Write `value` as `Diagnostics/<name>` (and its visible copy), now.
    func writeJSON<T: Encodable>(_ value: T, name: String) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(value) else { return }
        queue.sync {
            for folder in [AppPaths.diagnostics, AppPaths.sharedDiagnostics] {
                try? data.write(to: folder.appendingPathComponent(name), options: .atomic)
            }
        }
    }

    /// Copy `file` in as `Diagnostics/<name>` (and its visible copy), now.
    func copy(_ file: URL, name: String) throws {
        let data = try Data(contentsOf: file)
        queue.sync {
            for folder in [AppPaths.diagnostics, AppPaths.sharedDiagnostics] {
                try? data.write(to: folder.appendingPathComponent(name), options: .atomic)
            }
        }
    }

    /// Copy the diagnostics and the core's logs into Documents/Diagnostics.
    func mirror() {
        queue.sync {
            let files = FileManager.default
            let target = AppPaths.sharedDiagnostics
            for (source, name) in [(AppPaths.diagnostics, ""), (AppPaths.coreLogs, "logs")] {
                guard let items = try? files.contentsOfDirectory(at: source, includingPropertiesForKeys: nil) else {
                    continue
                }
                let folder = name.isEmpty ? target : target.appendingPathComponent(name, isDirectory: true)
                try? files.createDirectory(at: folder, withIntermediateDirectories: true)
                for item in items {
                    let copy = folder.appendingPathComponent(item.lastPathComponent)
                    try? files.removeItem(at: copy)
                    try? files.copyItem(at: item, to: copy)
                }
            }
        }
    }

    /// A zip of Documents/Diagnostics in the temporary folder, for the share sheet.
    func exportArchive() throws -> URL {
        mirror()
        var coordinationError: NSError?
        var result: Result<URL, Error> = .failure(CocoaError(.fileReadUnknown))
        // .forUploading hands over a zip of the folder (Foundation makes it).
        NSFileCoordinator().coordinate(readingItemAt: AppPaths.sharedDiagnostics, options: .forUploading,
                                       error: &coordinationError) { zip in
            let target = FileManager.default.temporaryDirectory
                .appendingPathComponent("ChordNotepad-diagnostics-\(Self.stamp()).zip")
            do {
                try? FileManager.default.removeItem(at: target)
                try FileManager.default.copyItem(at: zip, to: target)
                result = .success(target)
            } catch {
                result = .failure(error)
            }
        }
        if let coordinationError { throw coordinationError }
        return try result.get()
    }

    /// "20261124-101500", for file names.
    static func stamp(_ date: Date = Date()) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter.string(from: date)
    }
}

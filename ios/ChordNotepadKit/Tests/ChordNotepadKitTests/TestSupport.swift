import Foundation
import XCTest

@testable import ChordNotepadKit

/// The one interpreter every test in this process shares (one per process,
/// never finalized), and where the tests find the core.
///
/// Environment (set by `make ios-kit-test`):
/// - `CN_SITE_PACKAGES`: the core's packages (the pipenv venv's site-packages).
///   Without it the tests that need the core are skipped.
/// - `CN_CORE_DIR`: the core to test against (default: this checkout's `core/`).
enum TestPython {
    /// The repository root, from this file's path.
    static let repo: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()  // ChordNotepadKitTests
        .deletingLastPathComponent()  // Tests
        .deletingLastPathComponent()  // ChordNotepadKit
        .deletingLastPathComponent()  // ios
        .deletingLastPathComponent()

    static let environment = ProcessInfo.processInfo.environment

    static var sitePackages: String? {
        environment["CN_SITE_PACKAGES"].flatMap { $0.isEmpty ? nil : $0 }
    }

    static var coreDir: String {
        environment["CN_CORE_DIR"] ?? repo.appendingPathComponent("core").path
    }

    /// Whether the core's packages are on the path.
    static var hasCore: Bool { sitePackages != nil }

    static let configuration = PythonRuntime.Configuration(
        searchPaths: [
            repo.appendingPathComponent("ios/ChordNotepadKit/Tests/ChordNotepadKitTests/python").path,
            coreDir,
        ] + (sitePackages.map { [$0] } ?? []),
        environment: ["CN_TEST_FAKE_PLAYER": "1"])

    static func runtime() async throws -> PythonRuntime {
        try await PythonRuntime.start(configuration)
    }

    static func requireCore() throws {
        try XCTSkipUnless(hasCore, "Set CN_SITE_PACKAGES to the core's site-packages (make ios-kit-test)")
    }
}

/// An in-memory ``DocumentStore`` with fixed ids, safe on any thread.
///
/// - `missing`: never exists ("File not found: missing").
/// - `locked`: can't be renamed (``DocumentStoreError/renameUnsupported(_:)``).
/// - ids starting with `slow`: `readBytes` blocks for 300 ms.
final class MemoryStore: DocumentStore, @unchecked Sendable {
    private let lock = NSLock()
    private var files: [String: Data] = [:]
    private var recentRefs: [DocumentRef] = []
    private(set) var maxRecent = 10
    private(set) var copies: [(id: String, path: String)] = []
    private(set) var calls: [String] = []

    init(files: [String: Data] = [:]) {
        self.files = files
    }

    func contents(_ id: String) -> Data? { lock.withLock { files[id] } }

    func readBytes(id: String) throws -> Data {
        log("readBytes \(id)")
        if id.hasPrefix("slow") { Thread.sleep(forTimeInterval: 0.3) }
        guard let data = lock.withLock({ files[id] }) else {
            throw DocumentStoreError.failed("File not found: \(id)")
        }
        return data
    }

    func writeBytes(id: String, data: Data) throws {
        log("writeBytes \(id)")
        if id == "missing" { throw DocumentStoreError.failed("Failed to write file: \(id)") }
        lock.withLock { files[id] = data }
    }

    func copyFromFile(id: String, path: String) throws {
        log("copyFromFile \(id)")
        lock.withLock { copies.append((id, path)) }
    }

    func isAvailable(id: String) -> Bool {
        log("isAvailable \(id)")
        return lock.withLock { files[id] != nil }
    }

    func recent() throws -> [DocumentRef] {
        log("recent")
        return lock.withLock { recentRefs }
    }

    func addRecent(_ ref: DocumentRef) throws {
        log("addRecent \(ref.id)")
        lock.withLock {
            recentRefs.removeAll { $0.id == ref.id }
            recentRefs.insert(ref, at: 0)
            recentRefs = Array(recentRefs.prefix(maxRecent))
        }
    }

    func setMaxRecent(_ count: Int) throws {
        log("setMaxRecent \(count)")
        lock.withLock { maxRecent = count }
    }

    func describe(id: String) throws -> DocumentRef? {
        log("describe \(id)")
        return lock.withLock { files[id] == nil ? nil : memoryRef(id) }
    }

    func rename(id: String, displayName: String) throws -> DocumentRef {
        log("rename \(id)")
        if id == "locked" {
            throw DocumentStoreError.renameUnsupported("This storage can't rename “\(id)”.")
        }
        return lock.withLock {
            let newId = "renamed/" + displayName
            files[newId] = files.removeValue(forKey: id)
            return DocumentRef(displayName: displayName, id: newId, location: "On My iPhone")
        }
    }

    private func log(_ call: String) {
        lock.withLock { calls.append(call) }
    }
}

/// The ref the memory store gives a document: its id's last part as the name.
func memoryRef(_ id: String) -> DocumentRef {
    DocumentRef(displayName: (id as NSString).lastPathComponent, id: id, location: "On My iPhone")
}

/// Decodes a JSON object into a dictionary for assertions.
func jsonObject(_ text: String?, file: StaticString = #filePath, line: UInt = #line) throws -> [String: Any] {
    let text = try XCTUnwrap(text, file: file, line: line)
    let value = try JSONSerialization.jsonObject(with: Data(text.utf8))
    return try XCTUnwrap(value as? [String: Any], file: file, line: line)
}

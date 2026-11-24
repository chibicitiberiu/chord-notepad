import ChordNotepadKit
import Foundation
import os

/// The shell's document store (phase 1): the songs the app ships, read-only,
/// and plain files in the app's Documents folder. The document picker with
/// security-scoped bookmarks comes with the editor screen (BACKLOG.md).
///
/// Ids: `bundle:<file>` for a shipped song, otherwise a path relative to
/// Documents. Python calls this on its own threads; a lock guards the
/// recent list, the files need none.
final class AppDocumentStore: DocumentStore, @unchecked Sendable {
    static let bundlePrefix = "bundle:"

    private let lock = NSLock()
    private let location: String
    private let recentFile: URL
    private var recentRefs: [DocumentRef]
    private var maxRecent = 10

    init(location: String, recentFile: URL = AppPaths.filesDir.appendingPathComponent("recent-documents.json")) {
        self.location = location
        self.recentFile = recentFile
        recentRefs = (try? JSONDecoder().decode([DocumentRef].self, from: Data(contentsOf: recentFile))) ?? []
    }

    /// The ref of a song the app ships.
    func bundledRef(_ fileName: String) -> DocumentRef {
        DocumentRef(displayName: fileName, id: Self.bundlePrefix + fileName, location: location)
    }

    private func url(_ id: String) -> URL? {
        if id.hasPrefix(Self.bundlePrefix) {
            let name = String(id.dropFirst(Self.bundlePrefix.count)) as NSString
            return Bundle.main.url(forResource: name.deletingPathExtension, withExtension: name.pathExtension)
        }
        let url = AppPaths.documents.appendingPathComponent(id).standardizedFileURL
        // Nothing outside Documents.
        return url.path.hasPrefix(AppPaths.documents.standardizedFileURL.path) ? url : nil
    }

    func readBytes(id: String) throws -> Data {
        Log.store.debug("readBytes \(id, privacy: .public)")
        guard let url = url(id), let data = FileManager.default.contents(atPath: url.path) else {
            throw DocumentStoreError.failed("File not found: \(id)")
        }
        return data
    }

    func writeBytes(id: String, data: Data) throws {
        Log.store.debug("writeBytes \(id, privacy: .public) (\(data.count) bytes)")
        guard !id.hasPrefix(Self.bundlePrefix), let url = url(id) else {
            throw DocumentStoreError.failed("Permission denied: \(id) can't be changed. Use Save As.")
        }
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to: url, options: .atomic)
        } catch {
            throw DocumentStoreError.failed("Failed to write file: \(error.localizedDescription)")
        }
    }

    func copyFromFile(id: String, path: String) throws {
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        try writeBytes(id: id, data: data)
    }

    func isAvailable(id: String) -> Bool {
        guard let url = url(id) else { return false }
        return FileManager.default.fileExists(atPath: url.path)
    }

    func recent() throws -> [DocumentRef] {
        let refs = lock.withLock { recentRefs }
        return refs.filter { isAvailable(id: $0.id) }
    }

    func addRecent(_ ref: DocumentRef) throws {
        let refs: [DocumentRef] = lock.withLock {
            recentRefs.removeAll { $0.id == ref.id }
            recentRefs.insert(ref, at: 0)
            recentRefs = Array(recentRefs.prefix(maxRecent))
            return recentRefs
        }
        save(refs)
    }

    func setMaxRecent(_ count: Int) throws {
        let refs: [DocumentRef] = lock.withLock {
            maxRecent = max(0, count)
            recentRefs = Array(recentRefs.prefix(maxRecent))
            return recentRefs
        }
        save(refs)
    }

    func describe(id: String) throws -> DocumentRef? {
        guard isAvailable(id: id) else { return nil }
        if id.hasPrefix(Self.bundlePrefix) {
            return bundledRef(String(id.dropFirst(Self.bundlePrefix.count)))
        }
        return DocumentRef(displayName: (id as NSString).lastPathComponent, id: id, location: location)
    }

    func rename(id: String, displayName: String) throws -> DocumentRef {
        guard !id.hasPrefix(Self.bundlePrefix), let source = url(id) else {
            throw DocumentStoreError.renameUnsupported("“\(id)” comes with the app and can't be renamed.")
        }
        let newId = ((id as NSString).deletingLastPathComponent as NSString).appendingPathComponent(displayName)
        guard let target = url(newId) else { throw DocumentStoreError.failed("Can't rename to \(displayName)") }
        do {
            try FileManager.default.moveItem(at: source, to: target)
        } catch {
            throw DocumentStoreError.failed("Rename failed: \(error.localizedDescription)")
        }
        let renamed = DocumentRef(displayName: displayName, id: newId, location: location)
        let refs: [DocumentRef] = lock.withLock {
            recentRefs = recentRefs.map { $0.id == id ? renamed : $0 }
            return recentRefs
        }
        save(refs)
        return renamed
    }

    private func save(_ refs: [DocumentRef]) {
        do {
            try JSONEncoder().encode(refs).write(to: recentFile, options: .atomic)
        } catch {
            Log.store.error("Saving the recent list failed: \(error.localizedDescription, privacy: .public)")
        }
    }
}

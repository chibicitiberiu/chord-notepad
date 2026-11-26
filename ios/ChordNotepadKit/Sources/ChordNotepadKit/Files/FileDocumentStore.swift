import Foundation

/// The iOS ``DocumentStore`` (Android's `SafDocumentStore`): documents by the
/// ids of ``DocumentId``, the recent list and the bookmark table. The UI
/// presents the pickers and hands what they return to ``adopt(_:)``; this
/// class only does I/O by id, through a ``DocumentFileAccess``.
///
/// Python calls the ``DocumentStore`` methods on its session thread
/// (blocking I/O is fine there), and `writeBytes` and `copyFromFile` also on
/// an export's worker thread. A lock guards the lists; file I/O runs outside
/// it, so an audio export streaming megabytes doesn't hold up the session's
/// next `recent()`. Bytes go back raw: decoding and normalisation stay in
/// Python. Messages follow the desktop's `FileService` wording ("File not
/// found: …", "Permission denied: …") and name the document by its location,
/// from the recent list when the file itself is gone.
public final class FileDocumentStore: DocumentStore, @unchecked Sendable {
    /// The largest document ``readBytes(id:)`` reads (5 MB).
    public static let maxReadBytes = 5 * 1024 * 1024
    /// The desktop's default `max_recent_files`.
    public static let defaultMaxRecent = 10
    /// Where exports wait for the export picker, under the app's folder.
    public static let exportsFolder = "exports"

    private let access: DocumentFileAccess
    private let appDir: URL
    private let recentFile: URL
    private let bookmarksFile: URL
    private let bundled: @Sendable (String) -> URL?
    private let appLabel: String
    private let lock = NSLock()
    private var maxRecent: Int
    private var recentRefs: [DocumentRef]
    private var table: BookmarkTable
    private var exportWritten: (@Sendable (String, URL) -> Void)?

    /// - Parameters:
    ///   - access: The file I/O (the app's scoped and coordinated one, or
    ///     ``PlainFileAccess`` in tests).
    ///   - appDir: The app's own folder (Application Support): `app:` ids are
    ///     paths in it.
    ///   - recentFile: The recent list (JSON).
    ///   - bookmarksFile: The bookmark table (JSON).
    ///   - bundled: The URL of a song the app ships, by file name.
    ///   - appLabel: Shown after the name of a shipped song or an example
    ///     copy (`song.txt (Examples)`).
    public init(access: DocumentFileAccess, appDir: URL, recentFile: URL, bookmarksFile: URL,
                bundled: @escaping @Sendable (String) -> URL?, appLabel: String = "Examples",
                maxRecent: Int = FileDocumentStore.defaultMaxRecent) {
        self.access = access
        self.appDir = appDir
        self.recentFile = recentFile
        self.bookmarksFile = bookmarksFile
        self.bundled = bundled
        self.appLabel = appLabel
        self.maxRecent = max(0, maxRecent)
        recentRefs = Self.loadRecent(recentFile)
        table = BookmarkTable.load(bookmarksFile)
    }

    /// Call `handler` after an export's file was written (on the thread that
    /// wrote it: the session's or the audio export's), with the export's id and
    /// file, so the UI can offer it with the export picker.
    public func onExportWritten(_ handler: (@Sendable (String, URL) -> Void)?) {
        lock.withLock { exportWritten = handler }
    }

    // MARK: - The UI's side

    /// Take a document the user picked (Open, Save As) or opened from Files:
    /// bookmark it and describe it. Picking a file that already has an id
    /// gives that id again. Does provider I/O; call it off the main thread.
    public func adopt(_ url: URL) throws -> DocumentRef {
        let bookmark = try access.makeBookmark(for: url)
        let facts = access.facts(url)
        let name = facts?.displayName ?? url.lastPathComponent
        let location = facts?.location ?? name
        let path = url.standardizedFileURL.path
        let key: String = lock.withLock {
            let key = table.key(forPath: path) ?? UUID().uuidString
            table.put(key, BookmarkEntry(bookmark: bookmark, path: path, displayName: name, location: location))
            saveTableLocked()
            return key
        }
        return DocumentRef(displayName: name, id: DocumentId.bookmark(key).string, location: location)
    }

    /// The ref for a document the app can still reach, or nil.
    public func refFor(_ id: String) -> DocumentRef? {
        guard let parsed = DocumentId(id), let url = try? resolve(id), let facts = access.facts(url) else {
            return nil
        }
        switch parsed {
        case .bundled(let name):
            return DocumentRef(displayName: name, id: id, location: "\(name) (\(appLabel))")
        case .app(let path):
            if Self.isExport(path) {
                return DocumentRef(displayName: facts.displayName, id: id, location: facts.displayName)
            }
            return DocumentRef(displayName: facts.displayName, id: id, location: "\(facts.displayName) (\(appLabel))")
        case .bookmark(let key):
            lock.withLock {
                if var entry = table[key], entry.displayName != facts.displayName || entry.location != facts.location {
                    entry.displayName = facts.displayName
                    entry.location = facts.location
                    table.put(key, entry)
                    saveTableLocked()
                }
            }
            return DocumentRef(displayName: facts.displayName, id: id, location: facts.location)
        }
    }

    /// A store-owned file for an export named `name` (iOS's export picker
    /// needs the file before it opens): `app:exports/<uuid>/<name>`, empty
    /// until the export writes it.
    public func prepareExport(named name: String) throws -> DocumentRef {
        let safe = DocumentId.isFileName(name) ? name : "Export"
        let path = "\(Self.exportsFolder)/\(UUID().uuidString)/\(safe)"
        let url = appDir.appendingPathComponent(path)
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                    withIntermediateDirectories: true)
        } catch {
            throw DocumentStoreError.failed("Failed to write file: \(error.localizedDescription)")
        }
        guard FileManager.default.createFile(atPath: url.path, contents: nil) else {
            throw DocumentStoreError.failed("Failed to write file: \(safe)")
        }
        return DocumentRef(displayName: safe, id: DocumentId.app(path).string, location: safe)
    }

    /// The file of an export ``prepareExport(named:)`` made, or nil.
    public func exportFile(_ id: String) -> URL? {
        guard case .app(let path)? = DocumentId(id), Self.isExport(path) else { return nil }
        return appDir.appendingPathComponent(path)
    }

    /// Where the export picker saved a file, as the store names places in
    /// its messages ("song.wav (iCloud Drive)", "song.wav (Chord Notepad)");
    /// the name alone when the place can't be read. Does provider I/O; call
    /// it off the main thread.
    public func savedLocation(_ url: URL) -> String {
        access.facts(url)?.location ?? url.lastPathComponent
    }

    /// Delete an export's file once the export picker is done with it.
    public func discardExport(_ id: String) {
        guard let file = exportFile(id) else { return }
        try? FileManager.default.removeItem(at: file.deletingLastPathComponent())
    }

    /// Delete every export left from an earlier run.
    public func discardAllExports() {
        try? FileManager.default.removeItem(at: appDir.appendingPathComponent(Self.exportsFolder))
    }

    /// Copy the example `name` into the app's folder (``ExampleLibrary``) and
    /// return the copy's ref. `skipId`: the open document when it has unsaved
    /// edits, so a second tap makes a fresh copy.
    public func exampleCopy(_ library: ExampleLibrary, name: String, skipId: String?) throws -> DocumentRef {
        let file = try library.copyFor(name, skipId: skipId)
        let id = library.idFor(file)
        return refFor(id) ?? DocumentRef(displayName: file.lastPathComponent, id: id,
                                         location: "\(file.lastPathComponent) (\(appLabel))")
    }

    /// The recent list, newest first, without documents that can't be
    /// reached any more (dropped for good, with their bookmarks).
    public func recentDocuments() -> [DocumentRef] {
        let saved = lock.withLock { recentRefs }
        // Resolving is I/O: outside the lock.
        let gone = Set(saved.filter { !isAvailable(id: $0.id) }.map(\.id))
        return lock.withLock {
            let current = recentRefs.filter { !gone.contains($0.id) }
            if current != recentRefs || current.count > maxRecent { return storeLocked(current) }
            return current
        }
    }

    /// The bookmark table, for tests and Diagnostics.
    public var bookmarks: BookmarkTable { lock.withLock { table } }

    // MARK: - DocumentStore (Python's side)

    public func readBytes(id: String) throws -> Data {
        do {
            let url = try resolve(id)
            // A song is a few kilobytes; this keeps a huge file from exhausting
            // memory. The size can be missing or wrong, so the read stops too.
            if let size = access.facts(url)?.size, size > Self.maxReadBytes { throw tooLarge(id) }
            guard let data = try access.read(url, limit: Self.maxReadBytes) else { throw tooLarge(id) }
            return data
        } catch let error as DocumentStoreError {
            throw error
        } catch {
            let failure = FileAccessError.from(error)
            if failure == .notFound {
                // Named before it leaves the recent list, which has its name.
                let message = "File not found: \(place(of: id))"
                forgetRecent(id)
                throw DocumentStoreError.failed(message)
            }
            throw failed(failure, id, action: "read")
        }
    }

    public func writeBytes(id: String, data: Data) throws {
        let url = try writableURL(id)
        do {
            try access.write(url, data: data)
        } catch {
            throw failed(FileAccessError.from(error), id, action: "write")
        }
        exportWrote(id, url)
    }

    public func copyFromFile(id: String, path: String) throws {
        let url = try writableURL(id)
        // The source is the export's own render: its absence isn't the document's.
        guard FileManager.default.fileExists(atPath: path) else {
            throw DocumentStoreError.failed("Failed to write file: \((path as NSString).lastPathComponent) is missing")
        }
        do {
            try access.copy(from: URL(fileURLWithPath: path), to: url)
        } catch {
            throw failed(FileAccessError.from(error), id, action: "write")
        }
        exportWrote(id, url)
    }

    public func isAvailable(id: String) -> Bool {
        guard let url = try? resolve(id) else { return false }
        return access.facts(url) != nil
    }

    public func recent() throws -> [DocumentRef] {
        recentDocuments()
    }

    public func addRecent(_ ref: DocumentRef) throws {
        lock.withLock {
            _ = storeLocked([ref] + recentRefs.filter { $0.id != ref.id })
        }
    }

    public func setMaxRecent(_ count: Int) throws {
        lock.withLock { maxRecent = max(0, count) }
    }

    public func describe(id: String) throws -> DocumentRef? {
        refFor(id)
    }

    public func rename(id: String, displayName: String) throws -> DocumentRef {
        guard let parsed = DocumentId(id) else {
            throw DocumentStoreError.renameUnsupported("\(place(of: id)) is stored where Chord Notepad can't rename it.")
        }
        let ref: DocumentRef
        switch parsed {
        case .bundled(let name):
            throw DocumentStoreError.renameUnsupported("“\(name)” comes with the app and can't be renamed.")
        case .app(let path):
            if Self.isExport(path) {
                throw DocumentStoreError.renameUnsupported("\(place(of: id)) is stored where Chord Notepad can't rename it.")
            }
            let renamed = try renameFile(appDir.appendingPathComponent(path), id: id, to: displayName)
            let folder = (path as NSString).deletingLastPathComponent
            let newId = DocumentId.app(folder.isEmpty ? renamed.lastPathComponent
                                       : "\(folder)/\(renamed.lastPathComponent)").string
            ref = refFor(newId) ?? DocumentRef(displayName: renamed.lastPathComponent, id: newId,
                                               location: "\(renamed.lastPathComponent) (\(appLabel))")
        case .bookmark(let key):
            let url: URL
            do {
                url = try resolve(id)
            } catch {
                throw DocumentStoreError.failed("File not found: \(place(of: id))")
            }
            let renamed = try renameFile(url, id: id, to: displayName)
            // The id stays: it is a key, and the bookmark follows the new name.
            guard let bookmark = try? access.makeBookmark(for: renamed), let facts = access.facts(renamed) else {
                throw DocumentStoreError.failed(
                    "Renamed to \(displayName), but Chord Notepad can't reach the file any more. "
                        + "Open it again (Open…) to keep working on it.")
            }
            lock.withLock {
                table.put(key, BookmarkEntry(bookmark: bookmark, path: renamed.standardizedFileURL.path,
                                             displayName: facts.displayName, location: facts.location))
                saveTableLocked()
            }
            ref = DocumentRef(displayName: facts.displayName, id: id, location: facts.location)
        }
        lock.withLock {
            if recentRefs.contains(where: { $0.id == id }) {
                recentRefs = recentRefs.map { $0.id == id ? ref : $0 }
                saveRecentLocked()
            }
        }
        return ref
    }

    // MARK: - Ids to files

    /// The file `id` names now. A stale bookmark is made again under the same
    /// id; one that can't be resolved throws ``FileAccessError/notFound``.
    private func resolve(_ id: String) throws -> URL {
        guard let parsed = DocumentId(id) else { throw FileAccessError.notFound }
        switch parsed {
        case .bundled(let name):
            guard let url = bundled(name) else { throw FileAccessError.notFound }
            return url
        case .app(let path):
            return appDir.appendingPathComponent(path)
        case .bookmark(let key):
            guard let entry = lock.withLock({ table[key] }) else { throw FileAccessError.notFound }
            let (url, stale) = try access.resolveBookmark(entry.bookmark)
            let path = url.standardizedFileURL.path
            if stale || path != entry.path {
                var updated = entry
                updated.path = path
                if stale, let fresh = try? access.makeBookmark(for: url) {
                    updated.bookmark = fresh
                }
                lock.withLock {
                    if table[key] != nil {
                        table.put(key, updated)
                        saveTableLocked()
                    }
                }
            }
            return url
        }
    }

    /// The file to write for `id`; a shipped song can't be written.
    private func writableURL(_ id: String) throws -> URL {
        if case .bundled? = DocumentId(id) {
            throw DocumentStoreError.failed("Permission denied: \(place(of: id)) comes with the app and can't be "
                                            + "changed. Use Save As.")
        }
        do {
            let url = try resolve(id)
            if case .app? = DocumentId(id) {
                try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                        withIntermediateDirectories: true)
            }
            return url
        } catch {
            throw failed(FileAccessError.from(error), id, action: "write")
        }
    }

    private func renameFile(_ url: URL, id: String, to displayName: String) throws -> URL {
        do {
            return try access.rename(url, to: displayName)
        } catch {
            switch FileAccessError.from(error) {
            case .exists:
                throw DocumentStoreError.failed("Couldn't rename to \(displayName): a file with that name is "
                                                + "already there.")
            case .unsupported, .permissionDenied:
                throw DocumentStoreError.renameUnsupported(
                    "\(place(of: id)) is stored where Chord Notepad can't rename it.")
            case .notFound:
                throw DocumentStoreError.failed("File not found: \(place(of: id))")
            case .notDownloaded:
                throw DocumentStoreError.failed(notDownloaded(id))
            case .other(let message):
                throw DocumentStoreError.failed("Couldn't rename to \(displayName): \(message)")
            }
        }
    }

    private func exportWrote(_ id: String, _ url: URL) {
        guard case .app(let path)? = DocumentId(id), Self.isExport(path) else { return }
        lock.withLock { exportWritten }?(id, url)
    }

    private static func isExport(_ path: String) -> Bool {
        path.hasPrefix(exportsFolder + "/")
    }

    // MARK: - Messages

    private func failed(_ failure: FileAccessError, _ id: String, action: String) -> DocumentStoreError {
        switch failure {
        case .notFound:
            return .failed("File not found: \(place(of: id))")
        case .permissionDenied, .unsupported:
            return .failed("Permission denied: \(place(of: id))")
        case .notDownloaded:
            return .failed(notDownloaded(id))
        case .exists:
            return .failed("Failed to \(action) file: \(place(of: id)) already exists")
        case .other(let message):
            return .failed("Failed to \(action) file: \(message)")
        }
    }

    private func notDownloaded(_ id: String) -> String {
        "File not downloaded yet (open it in the Files app to download it, then try again): \(place(of: id))"
    }

    private func tooLarge(_ id: String) -> DocumentStoreError {
        .failed("File too large to open (over \(Self.maxReadBytes / (1024 * 1024)) MB): \(place(of: id))")
    }

    /// Where a document is, for a message: its location now, else its recent
    /// entry's or its bookmark's (a file that has gone: "song.txt (Music)",
    /// not a UUID), else a name made from the id.
    private func place(of id: String) -> String {
        if let ref = refFor(id) { return ref.location }
        let known: String? = lock.withLock {
            if let entry = recentRefs.first(where: { $0.id == id }) { return entry.location }
            if case .bookmark(let key)? = DocumentId(id) { return table[key]?.location }
            return nil
        }
        return known ?? Self.fallbackName(id)
    }

    /// A name for an id nothing else knows.
    public static func fallbackName(_ id: String) -> String {
        switch DocumentId(id) {
        case .bundled(let name)?: return name
        case .app(let path)?: return (path as NSString).lastPathComponent
        case .bookmark?, nil: return "the document"
        }
    }

    // MARK: - The lists (the lock held)

    /// Drop `id` from the recent list (a document that's gone) and its bookmark.
    private func forgetRecent(_ id: String) {
        lock.withLock {
            guard recentRefs.contains(where: { $0.id == id }) else { return }
            _ = storeLocked(recentRefs.filter { $0.id != id }, released: [id])
        }
    }

    /// Cap `items`, forget the bookmarks of what fell off (and of `released`),
    /// save; returns what was kept. The newest entry keeps its bookmark even
    /// with a cap of 0: it is the document the user has open.
    private func storeLocked(_ items: [DocumentRef], released: Set<String> = []) -> [DocumentRef] {
        let kept = Array(items.prefix(maxRecent))
        var keep = Set(kept.map(\.id))
        if let first = items.first { keep.insert(first.id) }
        let dropped = Set(recentRefs.map(\.id)).union(items.map(\.id)).union(released).subtracting(keep)
        var tableChanged = false
        for id in dropped {
            if case .bookmark(let key)? = DocumentId(id), table.remove(key) != nil { tableChanged = true }
        }
        if tableChanged { saveTableLocked() }
        recentRefs = kept
        saveRecentLocked()
        return kept
    }

    private func saveRecentLocked() {
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            try FileManager.default.createDirectory(at: recentFile.deletingLastPathComponent(),
                                                    withIntermediateDirectories: true)
            try encoder.encode(recentRefs).write(to: recentFile, options: .atomic)
        } catch {
            // The list in memory still holds; the next change tries again.
        }
    }

    private func saveTableLocked() {
        try? table.save(bookmarksFile)
    }

    private static func loadRecent(_ url: URL) -> [DocumentRef] {
        guard let data = FileManager.default.contents(atPath: url.path) else { return [] }
        return (try? JSONDecoder().decode([DocumentRef].self, from: data)) ?? []
    }
}

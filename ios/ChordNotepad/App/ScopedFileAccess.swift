import ChordNotepadKit
import Foundation
import os

/// The app's ``DocumentFileAccess`` (docs/IOS.md, "Files"): real bookmarks,
/// the security scope held around each call, and NSFileCoordinator around
/// every read, write and rename, as Files providers and iCloud Drive need.
/// The I/O itself is the kit's ``PlainFileAccess``, which the Linux tests run.
///
/// Python's threads call it (the store's callbacks), so it blocks: a read of
/// a cloud file that isn't on the device yet asks for it and waits up to
/// ``downloadWait`` before saying it isn't downloaded, rather than letting a
/// coordinated read wait for the network with the session stuck behind it.
struct ScopedFileAccess: DocumentFileAccess {
    /// How long a read waits for a cloud file to arrive.
    static let downloadWait: TimeInterval = 20

    /// The app's Documents folder, which Files shows as "Chord Notepad".
    let documents: URL

    func makeBookmark(for url: URL) throws -> Data {
        try scoped(url) { () throws -> Data in
            do {
                // `.withSecurityScope` is macOS only; on iOS the bookmark of a
                // security-scoped URL carries its scope.
                return try url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil)
            } catch {
                Log.store.error("Bookmark of \(url.lastPathComponent, privacy: .public) failed: \(error.localizedDescription, privacy: .public)")
                throw FileAccessError.from(error)
            }
        }
    }

    func resolveBookmark(_ bookmark: Data) throws -> (url: URL, stale: Bool) {
        var stale = false
        do {
            let url = try URL(resolvingBookmarkData: bookmark, options: [.withoutUI], relativeTo: nil,
                              bookmarkDataIsStale: &stale)
            return (url, stale)
        } catch {
            // Deleted, or on a provider that is gone.
            Log.store.info("A bookmark doesn't resolve: \(error.localizedDescription, privacy: .public)")
            throw FileAccessError.notFound
        }
    }

    func facts(_ url: URL) -> FileFacts? {
        scoped(url) { () -> FileFacts? in
            let reachable = (try? url.checkResourceIsReachable()) == true
            guard reachable || FileManager.default.fileExists(atPath: url.path) else { return nil }
            let values = try? url.resourceValues(forKeys: [.isDirectoryKey, .fileSizeKey, .nameKey])
            if values?.isDirectory == true { return nil }
            let name = values?.name ?? url.lastPathComponent
            return FileFacts(displayName: name, location: location(of: url, name: name), size: values?.fileSize)
        }
    }

    func read(_ url: URL, limit: Int) throws -> Data? {
        try scoped(url) { () throws -> Data? in
            try waitForDownload(url)
            return try coordinate(reading: url) { try PlainFileAccess.read($0, limit: limit) }
        }
    }

    func write(_ url: URL, data: Data) throws {
        try scoped(url) { () throws -> Void in
            try coordinate(writing: url) { try PlainFileAccess.write($0, data: data) }
        }
    }

    func copy(from source: URL, to url: URL) throws {
        try scoped(url) { () throws -> Void in
            try coordinate(writing: url) { try PlainFileAccess.copy(from: source, to: $0) }
        }
    }

    func rename(_ url: URL, to name: String) throws -> URL {
        guard DocumentId.isFileName(name) else { throw FileAccessError.other("Not a file name: \(name)") }
        return try scoped(url) { () throws -> URL in
            let target = url.deletingLastPathComponent().appendingPathComponent(name)
            if target.standardizedFileURL.path == url.standardizedFileURL.path { return url }
            let sameFile = target.path.lowercased() == url.path.lowercased()
            if !sameFile && FileManager.default.fileExists(atPath: target.path) { throw FileAccessError.exists }
            let coordinator = NSFileCoordinator(filePresenter: nil)
            var coordinationError: NSError?
            var outcome: Result<URL, Error> = .failure(FileAccessError.other("The file couldn't be renamed"))
            coordinator.coordinate(writingItemAt: url, options: .forMoving, writingItemAt: target,
                                   options: .forReplacing, error: &coordinationError) { from, to in
                outcome = Result<URL, Error> { () throws -> URL in
                    try FileManager.default.moveItem(at: from, to: to)
                    coordinator.item(at: from, didMoveTo: to)
                    return to
                }
            }
            if let coordinationError { throw Self.renameError(coordinationError) }
            do {
                return try outcome.get()
            } catch {
                throw Self.renameError(error)
            }
        }
    }

    /// A picked file's folder is the provider's: the app may not change it,
    /// so a refused move means the storage can't rename here (Save As).
    private static func renameError(_ error: Error) -> FileAccessError {
        switch FileAccessError.from(error) {
        case .permissionDenied: return .unsupported
        case let other: return other
        }
    }

    // MARK: - Scope, coordination, downloads

    /// Run `body` with access to `url` (a security-scoped URL needs it; a file
    /// in the app's container doesn't, and starting returns false there).
    private func scoped<T>(_ url: URL, _ body: () throws -> T) rethrows -> T {
        let started = url.startAccessingSecurityScopedResource()
        defer {
            if started { url.stopAccessingSecurityScopedResource() }
        }
        return try body()
    }

    private func coordinate<T>(reading url: URL, _ body: (URL) throws -> T) throws -> T {
        var coordinationError: NSError?
        var outcome: Result<T, Error>?
        NSFileCoordinator(filePresenter: nil).coordinate(readingItemAt: url, options: [],
                                                         error: &coordinationError) { actual in
            outcome = Result<T, Error> { try body(actual) }
        }
        if let coordinationError { throw FileAccessError.from(coordinationError) }
        guard let outcome else { throw FileAccessError.other("The file couldn't be read") }
        return try outcome.get()
    }

    private func coordinate(writing url: URL, _ body: (URL) throws -> Void) throws {
        var coordinationError: NSError?
        var outcome: Result<Void, Error>?
        NSFileCoordinator(filePresenter: nil).coordinate(writingItemAt: url, options: .forReplacing,
                                                         error: &coordinationError) { actual in
            outcome = Result<Void, Error> { try body(actual) }
        }
        if let coordinationError { throw FileAccessError.from(coordinationError) }
        guard let outcome else { throw FileAccessError.other("The file couldn't be written") }
        try outcome.get()
    }

    /// A cloud file whose content isn't on the device: ask for it, wait up to
    /// ``downloadWait``, else throw ``FileAccessError/notDownloaded``.
    private func waitForDownload(_ url: URL) throws {
        guard let status = downloadStatus(url), status == .notDownloaded else { return }
        Log.store.info("Downloading \(url.lastPathComponent, privacy: .public)")
        try? FileManager.default.startDownloadingUbiquitousItem(at: url)
        let deadline = Date().addingTimeInterval(Self.downloadWait)
        while Date() < deadline {
            Thread.sleep(forTimeInterval: 0.25)
            if downloadStatus(url) != .notDownloaded { return }
        }
        throw FileAccessError.notDownloaded
    }

    private func downloadStatus(_ url: URL) -> URLUbiquitousItemDownloadingStatus? {
        var fresh = url
        fresh.removeAllCachedResourceValues()
        guard let values = try? fresh.resourceValues(forKeys: [.isUbiquitousItemKey,
                                                               .ubiquitousItemDownloadingStatusKey]),
              values.isUbiquitousItem == true else { return nil }
        return values.ubiquitousItemDownloadingStatus
    }

    /// "song.txt (Chord Notepad)" for the app's own Documents, else the name
    /// and the folder as Files names it ("song.txt (iCloud Drive)",
    /// "song.txt (Downloads)").
    private func location(of url: URL, name: String) -> String {
        let folder = url.deletingLastPathComponent().standardizedFileURL
        if folder.path == documents.standardizedFileURL.path {
            return "\(name) (Chord Notepad)"
        }
        let folderName = (try? folder.resourceValues(forKeys: [.localizedNameKey]))?.localizedName
            ?? folder.lastPathComponent
        return folderName.isEmpty || folderName == "/" ? name : "\(name) (\(folderName))"
    }
}

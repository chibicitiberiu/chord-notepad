import Foundation

// File I/O by URL for the document store, the part that differs between the
// app and the tests (Android's DocumentAccess). The app's implementation
// resolves real security-scoped bookmarks, holds the security scope around
// each call and coordinates reads and writes with NSFileCoordinator; Linux
// Foundation has none of those, so the kit's tests use ``PlainFileAccess``,
// which does the same I/O with FileManager and fakes the bookmarks.

/// Why a file operation failed. The store words the message, with where the
/// document is (``FileDocumentStore``).
public enum FileAccessError: Error, Equatable, Sendable {
    /// No file there (deleted, moved where the bookmark can't follow, a
    /// provider that is gone).
    case notFound
    /// The app may not read or write it (a revoked or missing scope).
    case permissionDenied
    /// A provider's file whose content isn't on the device and didn't arrive
    /// in time (iCloud Drive while offline).
    case notDownloaded
    /// A rename to a name that is taken.
    case exists
    /// The storage can't do this here (a rename needs the folder, and the app
    /// only has the file).
    case unsupported
    /// Anything else, with the system's description.
    case other(String)

    /// The error a FileManager or Data call threw, sorted.
    public static func from(_ error: Error) -> FileAccessError {
        if let error = error as? FileAccessError { return error }
        if let cocoa = error as? CocoaError {
            switch cocoa.code {
            case .fileNoSuchFile, .fileReadNoSuchFile:
                return .notFound
            case .fileReadNoPermission, .fileWriteNoPermission:
                return .permissionDenied
            case .fileWriteFileExists:
                return .exists
            default:
                if let posix = (cocoa.userInfo[NSUnderlyingErrorKey] as? NSError).flatMap(posixCode) {
                    return fromPOSIX(posix, cocoa.localizedDescription)
                }
                return .other(cocoa.localizedDescription)
            }
        }
        let ns = error as NSError
        if let posix = posixCode(ns) { return fromPOSIX(posix, ns.localizedDescription) }
        return .other(ns.localizedDescription)
    }

    private static func posixCode(_ error: NSError) -> Int32? {
        error.domain == NSPOSIXErrorDomain ? Int32(error.code) : nil
    }

    private static func fromPOSIX(_ code: Int32, _ description: String) -> FileAccessError {
        switch code {
        case ENOENT: return .notFound
        case EACCES, EPERM: return .permissionDenied
        case EEXIST: return .exists
        default: return .other(description)
        }
    }
}

/// What the store needs to know about a file.
public struct FileFacts: Sendable, Equatable {
    /// The file's name, with its extension.
    public var displayName: String
    /// Where it is, for status lines and messages: "song.txt (Downloads)".
    public var location: String
    /// Its size in bytes, when known.
    public var size: Int?

    public init(displayName: String, location: String, size: Int?) {
        self.displayName = displayName
        self.location = location
        self.size = size
    }
}

/// File I/O by URL. Python's threads call the store, so an implementation
/// must be safe on any thread; it may block on I/O.
public protocol DocumentFileAccess: Sendable {
    /// A bookmark for `url`, which the user just picked (and the app may
    /// reach now).
    func makeBookmark(for url: URL) throws -> Data
    /// Where `bookmark` points now, and whether it should be made again from
    /// that URL (stale). Throws ``FileAccessError/notFound`` when it can't be
    /// resolved.
    func resolveBookmark(_ bookmark: Data) throws -> (url: URL, stale: Bool)
    /// The file's name, location and size, or nil when there's no file.
    func facts(_ url: URL) -> FileFacts?
    /// The file's bytes, or nil when it has more than `limit`.
    func read(_ url: URL, limit: Int) throws -> Data?
    /// Replace the file's content in place (the file may be one the app can
    /// reach without its folder, so never through a temporary file beside it).
    func write(_ url: URL, data: Data) throws
    /// Replace the file's content with the local file at `source`, streamed.
    func copy(from source: URL, to url: URL) throws
    /// Rename the file in its folder; returns its new URL.
    func rename(_ url: URL, to name: String) throws -> URL
}

/// ``DocumentFileAccess`` with FileManager only: no security scope, no file
/// coordination, and a bookmark that is just the file's path. The kit's tests
/// use it on Linux; its helpers do the I/O for the app's implementation too.
public struct PlainFileAccess: DocumentFileAccess {
    public init() {}

    private static let pathBookmark = "path:"

    public func makeBookmark(for url: URL) throws -> Data {
        guard FileManager.default.fileExists(atPath: url.path) else { throw FileAccessError.notFound }
        return Data((Self.pathBookmark + url.standardizedFileURL.path).utf8)
    }

    public func resolveBookmark(_ bookmark: Data) throws -> (url: URL, stale: Bool) {
        let text = String(decoding: bookmark, as: UTF8.self)
        guard text.hasPrefix(Self.pathBookmark) else { throw FileAccessError.notFound }
        let url = URL(fileURLWithPath: String(text.dropFirst(Self.pathBookmark.count)))
        guard FileManager.default.fileExists(atPath: url.path) else { throw FileAccessError.notFound }
        return (url, false)
    }

    public func facts(_ url: URL) -> FileFacts? {
        Self.facts(url)
    }

    public func read(_ url: URL, limit: Int) throws -> Data? {
        try Self.read(url, limit: limit)
    }

    public func write(_ url: URL, data: Data) throws {
        try Self.write(url, data: data)
    }

    public func copy(from source: URL, to url: URL) throws {
        try Self.copy(from: source, to: url)
    }

    public func rename(_ url: URL, to name: String) throws -> URL {
        try Self.rename(url, to: name)
    }

    // MARK: - The I/O itself

    /// The name, "name (folder)" and size of a regular file, or nil.
    public static func facts(_ url: URL, location: ((URL) -> String)? = nil) -> FileFacts? {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory), !isDirectory.boolValue
        else { return nil }
        let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
        let size = (attributes?[.size] as? NSNumber)?.intValue
        let name = url.lastPathComponent
        return FileFacts(displayName: name, location: location?(url) ?? folderLocation(url), size: size)
    }

    /// "song.txt (Music)": the name and the folder it is in.
    public static func folderLocation(_ url: URL) -> String {
        let folder = url.deletingLastPathComponent().lastPathComponent
        return folder.isEmpty || folder == "/" ? url.lastPathComponent : "\(url.lastPathComponent) (\(folder))"
    }

    /// Read at most `limit` bytes; nil when the file has more.
    public static func read(_ url: URL, limit: Int) throws -> Data? {
        do {
            let handle = try FileHandle(forReadingFrom: url)
            defer { try? handle.close() }
            var data = Data()
            while true {
                guard let chunk = try handle.read(upToCount: 64 * 1024), !chunk.isEmpty else { return data }
                if data.count + chunk.count > limit { return nil }
                data.append(chunk)
            }
        } catch {
            throw FileAccessError.from(error)
        }
    }

    /// Write in place: create or truncate the file, then write (not atomically,
    /// which would need a temporary file in a folder the app may not reach).
    public static func write(_ url: URL, data: Data) throws {
        do {
            try data.write(to: url, options: [])
        } catch {
            throw FileAccessError.from(error)
        }
    }

    /// Stream `source` into `url`, replacing its content, in 256 KB chunks.
    public static func copy(from source: URL, to url: URL) throws {
        do {
            let input = try FileHandle(forReadingFrom: source)
            defer { try? input.close() }
            if !FileManager.default.fileExists(atPath: url.path) {
                guard FileManager.default.createFile(atPath: url.path, contents: nil) else {
                    throw FileAccessError.permissionDenied
                }
            }
            let output = try FileHandle(forWritingTo: url)
            defer { try? output.close() }
            try output.truncate(atOffset: 0)
            while let chunk = try input.read(upToCount: 256 * 1024), !chunk.isEmpty {
                try output.write(contentsOf: chunk)
            }
        } catch {
            throw FileAccessError.from(error)
        }
    }

    /// Rename within the folder. A name that is taken is refused (moveItem
    /// would refuse it too, but say so plainly).
    public static func rename(_ url: URL, to name: String) throws -> URL {
        guard DocumentId.isFileName(name) else { throw FileAccessError.other("Not a file name: \(name)") }
        let target = url.deletingLastPathComponent().appendingPathComponent(name)
        if target.standardizedFileURL.path == url.standardizedFileURL.path { return url }
        // A case-only change on a case-insensitive volume is the same file.
        let sameFile = target.path.lowercased() == url.path.lowercased()
        if !sameFile && FileManager.default.fileExists(atPath: target.path) { throw FileAccessError.exists }
        do {
            try FileManager.default.moveItem(at: url, to: target)
        } catch {
            throw FileAccessError.from(error)
        }
        return target
    }
}

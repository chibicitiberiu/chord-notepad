import Foundation

/// One document the user picked: its bookmark and what was last known of it.
public struct BookmarkEntry: Codable, Sendable, Equatable {
    /// The security-scoped bookmark (on Linux, ``PlainFileAccess``'s path).
    public var bookmark: Data
    /// The file's path when it was last resolved: picking the same file again
    /// reuses its id rather than adding a second one to Recent.
    public var path: String
    public var displayName: String
    /// Where it was, for a message once it can't be found any more.
    public var location: String

    public init(bookmark: Data, path: String, displayName: String, location: String) {
        self.bookmark = bookmark
        self.path = path
        self.displayName = displayName
        self.location = location
    }

    enum CodingKeys: String, CodingKey {
        case bookmark
        case path
        case displayName = "display_name"
        case location
    }
}

/// The bookmarks behind `bookmark:<key>` ids, by key, as a value (saved as
/// JSON in Application Support by ``FileDocumentStore``; no UserDefaults,
/// which would need a privacy reason).
public struct BookmarkTable: Codable, Sendable, Equatable {
    public private(set) var entries: [String: BookmarkEntry] = [:]

    public init(entries: [String: BookmarkEntry] = [:]) {
        self.entries = entries
    }

    public subscript(key: String) -> BookmarkEntry? {
        entries[key]
    }

    /// The key of the entry last resolved at `path`, if any.
    public func key(forPath path: String) -> String? {
        entries.keys.sorted().first { entries[$0]?.path == path }
    }

    public mutating func put(_ key: String, _ entry: BookmarkEntry) {
        entries[key] = entry
    }

    @discardableResult
    public mutating func remove(_ key: String) -> BookmarkEntry? {
        entries.removeValue(forKey: key)
    }

    /// Keep only the entries whose keys are in `keys`.
    public mutating func retain(_ keys: Set<String>) {
        entries = entries.filter { keys.contains($0.key) }
    }

    /// The table in a file, or an empty one when it's missing or unreadable.
    public static func load(_ url: URL) -> BookmarkTable {
        guard let data = FileManager.default.contents(atPath: url.path) else { return BookmarkTable() }
        return (try? JSONDecoder().decode(BookmarkTable.self, from: data)) ?? BookmarkTable()
    }

    /// Write the table atomically (a temporary file, then a rename).
    public func save(_ url: URL) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try encoder.encode(self).write(to: url, options: .atomic)
    }
}

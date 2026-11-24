import Foundation

// The iOS store's document ids (docs/IOS.md, "Files"). Python treats ids as
// opaque strings and compares them as strings (Recent, ModeController), so an
// id must never change while the document is the same: a picked file is a
// key into the bookmark table, never its URL, which changes when the file
// moves or a provider renames it. Android's ids are content URIs.

/// What a store id names.
public enum DocumentId: Sendable, Hashable {
    /// A song the app ships, read only: `bundle:<file name>`.
    case bundled(String)
    /// A file in the app's own container (Application Support), by its path
    /// there: `app:examples/<name>` (the copies Examples opens),
    /// `app:exports/<uuid>/<name>` (an export waiting for the export picker).
    case app(String)
    /// A document the user picked or opened from Files, found again through
    /// its security-scoped bookmark: `bookmark:<UUID>`.
    case bookmark(String)

    public static let bundlePrefix = "bundle:"
    public static let appPrefix = "app:"
    public static let bookmarkPrefix = "bookmark:"

    /// The id `text` names, or nil for anything else (an `app:` path that
    /// would leave its folder included).
    public init?(_ text: String) {
        if text.hasPrefix(Self.bundlePrefix) {
            let name = String(text.dropFirst(Self.bundlePrefix.count))
            guard Self.isFileName(name) else { return nil }
            self = .bundled(name)
        } else if text.hasPrefix(Self.appPrefix) {
            let path = String(text.dropFirst(Self.appPrefix.count))
            guard Self.isRelativePath(path) else { return nil }
            self = .app(path)
        } else if text.hasPrefix(Self.bookmarkPrefix) {
            let key = String(text.dropFirst(Self.bookmarkPrefix.count))
            guard !key.isEmpty, !key.contains("/") else { return nil }
            self = .bookmark(key)
        } else {
            return nil
        }
    }

    /// The id as Python gets it.
    public var string: String {
        switch self {
        case .bundled(let name): return Self.bundlePrefix + name
        case .app(let path): return Self.appPrefix + path
        case .bookmark(let key): return Self.bookmarkPrefix + key
        }
    }

    /// A one-component name: not empty, no `/`, not `.` or `..`.
    public static func isFileName(_ name: String) -> Bool {
        !name.isEmpty && !name.contains("/") && name != "." && name != ".."
    }

    /// A relative path of file names (no empty, `.` or `..` component).
    static func isRelativePath(_ path: String) -> Bool {
        let parts = path.split(separator: "/", omittingEmptySubsequences: false)
        return !parts.isEmpty && parts.allSatisfy { isFileName(String($0)) }
    }
}

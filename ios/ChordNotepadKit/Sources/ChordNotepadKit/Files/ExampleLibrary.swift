import Foundation

/// The example songs the app ships, and their private copies under `dir`
/// (Android's `ExampleLibrary`, the menu's Examples). `list` and `read`
/// stand in for the bundle.
///
/// A copy's id is `app:examples/<name>` (``DocumentId/app(_:)``), so the
/// store reads and writes it as a plain file in the container: always
/// writable, kept in Recent until it's deleted, not visible in Files.
public struct ExampleLibrary: Sendable {
    /// The folder under Application Support the copies live in.
    public static let folder = "examples"

    private let list: @Sendable () -> [String]
    private let read: @Sendable (String) throws -> Data
    public let dir: URL

    public init(list: @escaping @Sendable () -> [String], read: @escaping @Sendable (String) throws -> Data,
                dir: URL) {
        self.list = list
        self.read = read
        self.dir = dir
    }

    /// The example file names (`*.txt`), sorted.
    public func names() -> [String] {
        list().filter { $0.hasSuffix(".txt") }.sorted()
    }

    /// The copy of `name` in `dir`, without checking it exists.
    public func fileFor(_ name: String) -> URL {
        dir.appendingPathComponent(name)
    }

    /// The store id of a copy (from its name, never a resolved path: ids are
    /// compared as strings).
    public func idFor(_ file: URL) -> String {
        DocumentId.app("\(Self.folder)/\(file.lastPathComponent)").string
    }

    /// The copy to open for `name`: the first of `x.txt`, `x (2).txt`,
    /// `x (3).txt`... that doesn't exist (written now) or is byte-identical to
    /// the bundled song. A copy whose id is `skipId` (the open document, when
    /// it has unsaved edits) is passed over even when identical.
    public func copyFor(_ name: String, skipId: String?) throws -> URL {
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let bytes = try read(name)
        let stem = (name as NSString).deletingPathExtension
        let ext = (name as NSString).pathExtension
        var n = 1
        while true {
            let candidate = fileFor(n == 1 ? name : "\(stem) (\(n))" + (ext.isEmpty ? "" : ".\(ext)"))
            if !FileManager.default.fileExists(atPath: candidate.path) {
                try bytes.write(to: candidate, options: .atomic)
                return candidate
            }
            if idFor(candidate) != skipId, FileManager.default.contents(atPath: candidate.path) == bytes {
                return candidate
            }
            n += 1
        }
    }
}

import Foundation

// The song every launch reopens (docs/IOS.md, "The last song"): Android's
// `Draft` (lifecycle/DraftRestore.kt), kept in a file instead of the
// activity's saved state, so it comes back after a swipe-away or a crash
// too, not only after the system ended the process.

/// What was open when the app last kept it: the text, the document it
/// belongs to (nil for a never-saved song), whether it had unsaved changes,
/// whether it was open read only, and the tab it was in.
public struct LastSong: Codable, Sendable, Equatable {
    public var text: String
    /// The store id (`DocumentState.documentId`), or nil.
    public var documentId: String?
    /// The document's name and location, for its ref when it can't be
    /// resolved any more (the open's "File not found: … (Downloads)").
    public var displayName: String?
    public var location: String?
    public var modified: Bool
    /// `DocumentState.readOnly`: Save runs Save As (the quick-start song).
    public var readOnly: Bool
    /// `AppMode.rawValue`.
    public var mode: String

    public init(text: String, documentId: String?, displayName: String? = nil, location: String? = nil,
                modified: Bool, readOnly: Bool = false, mode: AppMode = .play) {
        self.text = text
        self.documentId = documentId
        self.displayName = displayName
        self.location = location
        self.modified = modified
        self.readOnly = readOnly
        self.mode = mode.rawValue
    }

    /// The song on screen: the session's document and the editor's text
    /// (the session's lacks typing not sent yet, which counts as a change).
    /// Nil before the session has reported a document.
    public static func of(document: DocumentState?, editorText: String, unsentTyping: Bool,
                          mode: AppMode) -> LastSong? {
        guard let document else { return nil }
        return LastSong(text: editorText, documentId: document.documentId, displayName: document.displayName,
                        location: document.location, modified: document.isModified || unsentTyping,
                        readOnly: document.readOnly, mode: mode)
    }

    /// The tab it was in (Play for an unknown value).
    public var appMode: AppMode { AppMode(rawValue: mode) ?? .play }

    /// The ref to open or restore it with when the store can't give one.
    public var keptRef: DocumentRef? {
        guard let documentId else { return nil }
        let name = displayName ?? documentId
        return DocumentRef(displayName: name, id: documentId, location: location ?? name)
    }
}

/// What a launch opens.
public enum LaunchSong: Sendable, Equatable {
    /// No last song (the first launch), or the quick-start song unchanged:
    /// the bundled quick-start song, read only, in Play.
    case quickStart
    /// An empty, never-saved song: the session's own start-up song.
    case empty
    /// A saved song without changes: read again through the store
    /// (`open_document`), so changes made elsewhere show. A failure is the
    /// open's usual error over the empty song.
    case open(DocumentRef, readOnly: Bool, mode: AppMode)
    /// A song with unsaved changes, or a never-saved one with text: its
    /// text back as a draft (``LastSongPolicy/restore(_:resolved:)`` once
    /// the document is resolved).
    case draft(LastSong)

    /// The tab the song lands in.
    public var mode: AppMode {
        switch self {
        case .quickStart: return .play
        case .empty: return .edit
        case .open(_, _, let mode): return mode
        case .draft(let song): return song.appMode
        }
    }

    /// Its name in the diagnostics (`launch.json`).
    public var kind: String {
        switch self {
        case .quickStart: return "quickStart"
        case .empty: return "empty"
        case .open: return "open"
        case .draft: return "draft"
        }
    }

    /// It has words the user typed that are saved nowhere else.
    public var hasUnsavedText: Bool {
        if case .draft = self { return true }
        return false
    }
}

/// When to reopen what (pure logic; the app does the file and store I/O).
public enum LastSongPolicy {
    /// The quick-start song's store id.
    public static let quickStartId = DocumentId.bundled("01_quick_start.txt").string

    /// What this launch opens. `kept` is the last song read from its file:
    /// `.missing` on the first launch (no file yet), `.unreadable` for a
    /// file that is there but can't be decoded.
    public static func launchSong(_ kept: KeptLastSong) -> LaunchSong {
        switch kept {
        case .missing:
            return .quickStart
        case .unreadable:
            // The app ran before, so not Quick Start; whatever it was is gone.
            return .empty
        case .song(let song):
            guard let ref = song.keptRef else {
                // Never saved: its text as an unsaved draft, if it has any.
                return song.text.isEmpty ? .empty : .draft(song)
            }
            if song.modified { return .draft(song) }
            if ref.id == quickStartId { return .quickStart }
            return .open(ref, readOnly: song.readOnly, mode: song.appMode)
        }
    }

    /// The `restore_draft` for a draft and what to tell the user. `resolved`
    /// is the store's ref for its document (nil when it can't be reached any
    /// more: deleted, a bookmark that no longer resolves). A document that
    /// is gone is dropped and the text kept as unsaved changes of a new
    /// song (Android's `DraftPolicy.restore`), and the user is told.
    /// `documentId` and `modified` are the document state the restore leads to.
    public static func restore(_ song: LastSong, resolved: DocumentRef?)
        -> (command: BridgeCommand, documentId: String?, modified: Bool, notice: String?) {
        let gone = song.documentId != nil && resolved == nil
        let modified = song.modified || song.documentId == nil || gone
        let command = BridgeCommand.restoreDraft(document: resolved, modified: modified,
                                                 readOnly: resolved != nil && song.readOnly, text: song.text)
        let notice = gone ? goneNotice(song.keptRef?.location ?? song.documentId ?? "") : nil
        return (command, resolved?.id, modified, notice)
    }

    /// The message for a draft whose document is gone.
    public static func goneNotice(_ location: String) -> String {
        "Couldn't find \(location): its unsaved changes are open as a new song."
    }
}

/// The last song's file as read at launch.
public enum KeptLastSong: Sendable, Equatable {
    case missing
    case unreadable
    case song(LastSong)
}

/// The last song as a JSON file (in Application Support: not in Files, not
/// cleared by the system). Written in full each time, atomically.
public struct LastSongFile: Sendable {
    public let url: URL

    public init(url: URL) {
        self.url = url
    }

    /// The file's song, `.missing` when there is no file.
    public func read() -> KeptLastSong {
        guard FileManager.default.fileExists(atPath: url.path) else { return .missing }
        guard let data = try? Data(contentsOf: url),
              let song = try? JSONDecoder().decode(LastSong.self, from: data) else { return .unreadable }
        return .song(song)
    }

    /// Keep `song`; false (and the old file kept) when it can't be written.
    @discardableResult
    public func write(_ song: LastSong) -> Bool {
        guard let data = try? JSONEncoder().encode(song) else { return false }
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                    withIntermediateDirectories: true)
            try data.write(to: url, options: .atomic)
            return true
        } catch {
            return false
        }
    }
}

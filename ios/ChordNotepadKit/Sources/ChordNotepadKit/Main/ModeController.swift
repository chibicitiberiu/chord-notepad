import Foundation

// The main screen's two tabs (Android's ui/main/ModeController.kt), as a
// value the app keeps on the main actor.

/// The app bar's two tabs.
public enum AppMode: String, Sendable, Hashable, CaseIterable {
    /// Editable text, the Edit ribbon, no chord sheet.
    case edit
    /// Frozen text with the playhead, the player, the chord sheet.
    case play
}

/// Which tab is open (Android's `ModeController`).
///
/// - The first document the session reports decides the start: a saved one
///   opens in Play, an untitled one in Edit.
/// - After the user asks to open a document (``expectOpen(target:current:)``),
///   the document that then arrives opens in Play; after New
///   (``expectNew()``), the empty one opens in Edit. Saving (which can change
///   the document too) never switches.
/// - Switching to Edit while a song plays or is paused stops it
///   (``select(_:playback:)``).
/// - Every open that arrives after ``expectOpen(target:current:)`` counts in
///   ``opened``, so the main screen can close a page over it.
/// - The launch's last song (``expectRestore(documentId:modified:mode:)``)
///   lands in the tab it was left in, untitled or not.
public struct ModeController: Sendable, Equatable {
    /// The open tab.
    public private(set) var mode: AppMode
    /// How many asked-for opens have arrived.
    public private(set) var opened = 0

    private var decided: Bool
    private var expecting = Expect.none
    private var lastDocument: String?
    private var lastModified = false

    private enum Expect: Sendable, Equatable {
        case none, open, new
        /// The launch's last song (``expectRestore(documentId:modified:mode:)``).
        case restore(id: String?, modified: Bool, mode: AppMode)
    }

    public init(_ initial: AppMode? = nil) {
        mode = initial ?? .edit
        decided = initial != nil
    }

    /// The user picked `target`. Returns true when playback must be stopped
    /// first (Edit while a song plays or is paused; the session keeps the
    /// text read-only until it stops).
    public mutating func select(_ target: AppMode, playback: PlaybackStatus?) -> Bool {
        let stop = target == .edit && mode == .play && playback != nil && playback != .idle
        mode = target
        decided = true
        return stop
    }

    /// The tab saved with the scene, when the process was killed and is
    /// coming back. It wins over the first document's rule; once the mode is
    /// decided it is ignored.
    public mutating func restore(_ saved: AppMode) {
        if decided { return }
        mode = saved
        decided = true
    }

    /// Open… or a recent document was asked for; with `target`, the document
    /// asked for. When that's the `current` one, unmodified, the session has
    /// nothing to change (no new document state comes), so it counts as
    /// opened now.
    public mutating func expectOpen(target: String? = nil, current: DocumentState? = nil) {
        if let target, let current, current.documentId == target, !current.isModified {
            mode = .play
            decided = true
            expecting = .none
            opened += 1
            return
        }
        expecting = .open
    }

    /// An asked-for open (or the launch's last song) hasn't arrived yet.
    public var expectingOpen: Bool {
        switch expecting {
        case .open, .restore: return true
        case .none, .new: return false
        }
    }

    /// The launch reopens the last song: the document `documentId` (nil for
    /// a never-saved song) with `modified` as given. It lands in `mode`, the
    /// tab it was left in, and counts in ``opened``; the start-up replay's
    /// empty untitled song (no id, unmodified) isn't it.
    public mutating func expectRestore(documentId: String?, modified: Bool, mode: AppMode) {
        expecting = .restore(id: documentId, modified: modified, mode: mode)
    }

    /// The asked-for open failed (its error came instead): nothing is expected any more.
    public mutating func openFailed() {
        if expectingOpen { expecting = .none }
    }

    /// New was asked for.
    public mutating func expectNew() {
        expecting = .new
    }

    /// Save, Save As or Rename was asked for: a document change that follows isn't an open.
    public mutating func expectSave() {
        expecting = .none
    }

    /// The session's document changed.
    public mutating func onDocument(_ document: DocumentState) {
        let id = document.documentId
        let changed = id != lastDocument
        // The same song again after "Don't save": its changes are gone.
        let reread = !changed && lastModified && !document.isModified
        lastDocument = id
        lastModified = document.isModified
        if case .restore(let target, let modified, let restoredMode) = expecting {
            if id == target && document.isModified == modified {
                mode = restoredMode
                decided = true
                expecting = .none
                opened += 1
            } else if !decided {
                mode = id != nil ? .play : .edit
                decided = true
            }
            return
        }
        if !decided {
            mode = id != nil ? .play : .edit
            decided = true
            // A cold start from an open: this is the open that was asked for.
            if expecting == .open && id != nil {
                expecting = .none
                opened += 1
            }
        } else if expecting == .open && (changed || reread) && id != nil {
            mode = .play
            expecting = .none
            opened += 1
        } else if expecting == .new && id == nil && !document.isModified {
            mode = .edit
            expecting = .none
        }
    }
}

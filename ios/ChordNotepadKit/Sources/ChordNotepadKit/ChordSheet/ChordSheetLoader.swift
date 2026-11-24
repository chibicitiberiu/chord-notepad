import Foundation

// Fetching, decoding and keeping the strip's op buffer: the testable half of
// Android's ui/chordsheet/ChordSheetController.kt. A plain state machine
// (ChordSheetLoad) and a small driver (ChordSheetLoader) that settles height
// changes, fetches on the bridge thread through the given closure and
// decodes off the main thread.

/// What a buffer depends on: a new one is fetched whenever this changes
/// (docs/ANDROID.md: song revision, view, zoom, height; never on scroll or
/// a playhead move).
public struct SheetRequest: Sendable, Hashable {
    public var songRevision: Int
    public var viewId: String
    public var zoom: Double
    /// The strip's content height in points (the marker lane excluded).
    public var height: Int

    public init(songRevision: Int, viewId: String, zoom: Double, height: Int) {
        self.songRevision = songRevision
        self.viewId = viewId
        self.zoom = zoom
        self.height = height
    }

    /// The request for `state` and a strip content `height` points tall, or
    /// nil when nothing should be fetched (no state, hidden, no room).
    public static func of(_ state: ChordSheetState?, height: Int) -> SheetRequest? {
        guard let state, state.visible, height > 0 else { return nil }
        return SheetRequest(songRevision: state.songRevision, viewId: state.activeView, zoom: state.zoom,
                            height: height)
    }
}

/// A fetched buffer, decoded (or why it can't be drawn).
public enum SheetOutcome: Sendable {
    case sheet(PreparedSheet)
    /// The session has no rendered song.
    case noSong
    /// The buffer can't be shown; the message is for the user.
    case failure(String)

    /// Decode and prepare `data` (nil: no song). Slow enough to keep off the
    /// main thread for a long song.
    public static func decode(_ data: Data?) -> SheetOutcome {
        guard let data else { return .noSong }
        do {
            return .sheet(PreparedSheet(try SheetBuffer.decode(data)))
        } catch SheetBufferError.unsupportedVersion {
            return .failure(ChordSheetLoad.newerVersionMessage)
        } catch {
            return .failure(ChordSheetLoad.malformedMessage)
        }
    }
}

/// The strip's buffer state: which request was asked for, which one the
/// shown sheet answers, and why nothing can be drawn.
public struct ChordSheetLoad: Sendable {
    public static let newerVersionMessage = "This chord sheet needs a newer version of the app."
    public static let malformedMessage = "The chord sheet couldn't be drawn."

    /// The last sheet decoded, kept until a newer one is ready; nil without a song.
    public private(set) var sheet: PreparedSheet?
    /// Why the last buffer couldn't be shown, or nil.
    public private(set) var failure: String?
    /// The request ``sheet`` answers.
    public private(set) var loaded: SheetRequest?
    /// The newest request (loaded or not yet).
    public private(set) var requested: SheetRequest?

    public init() {}

    /// A fixed sheet (the preview catalog), loaded for `request`.
    public init(sheet: PreparedSheet?, request: SheetRequest? = nil) {
        self.sheet = sheet
        requested = request
        loaded = request
    }

    /// True from a request until its buffer is shown (or fails): the pane
    /// shows a thin progress bar.
    public var loading: Bool { requested != nil && requested != loaded }

    /// Note the newest request.
    ///
    /// - Returns: Whether it differs from the last one and needs a fetch
    ///   (nil never does: a hidden sheet keeps its last buffer).
    public mutating func request(_ request: SheetRequest?) -> Bool {
        guard request != requested else { return false }
        requested = request
        return request != nil
    }

    /// Apply the outcome of `request`'s fetch; a reply to an older request
    /// than the newest is dropped.
    ///
    /// - Returns: Whether anything changed.
    @discardableResult
    public mutating func finish(_ request: SheetRequest, _ outcome: SheetOutcome) -> Bool {
        guard request == requested else { return false }
        loaded = request
        switch outcome {
        case .sheet(let prepared):
            sheet = prepared
            failure = nil
        case .noSong:
            sheet = nil
            failure = nil
        case .failure(let message):
            sheet = nil
            failure = message
        }
        return true
    }
}

/// Drives a ``ChordSheetLoad``: each distinct request waits for the settle
/// time (a split drag's heights settle first), a newer request cancels the
/// wait for an older one, then the buffer is fetched (the app's closure calls
/// `Session.chordSheetBuffer` on the bridge thread) and decoded off the main
/// actor. ``onChange`` reports every change on the main actor.
@MainActor
public final class ChordSheetLoader {
    public typealias Fetch = @Sendable (_ height: Double) async -> Data?

    /// Height changes during a split drag settle this long before a fetch.
    public static let defaultSettle: Duration = .milliseconds(60)

    public private(set) var state = ChordSheetLoad()
    /// Called after every change of ``state``.
    public var onChange: ((ChordSheetLoad) -> Void)?
    /// How many fetches were started (diagnostics, tests).
    public private(set) var fetchCount = 0

    private let fetch: Fetch
    private let settle: Duration
    private var task: Task<Void, Never>?

    public init(settle: Duration = ChordSheetLoader.defaultSettle, fetch: @escaping Fetch) {
        self.fetch = fetch
        self.settle = settle
    }

    /// Follow the newest request (from `ChordSheetState` and the strip's height).
    public func follow(_ request: SheetRequest?) {
        guard request != state.requested else { return }
        let needsFetch = state.request(request)
        task?.cancel()
        task = nil
        onChange?(state)
        guard needsFetch, let request else { return }
        let fetch = self.fetch
        let settle = self.settle
        task = Task { [weak self] in
            do {
                try await Task.sleep(for: settle)
            } catch {
                return
            }
            self?.fetchCount += 1
            let data = await fetch(Double(request.height))
            guard !Task.isCancelled else { return }
            let outcome = await Task.detached(priority: .userInitiated) { SheetOutcome.decode(data) }.value
            guard !Task.isCancelled, let self else { return }
            if self.state.finish(request, outcome) {
                self.onChange?(self.state)
            }
        }
    }

    /// Wait for the fetch in flight, if any (tests).
    public func settled() async {
        await task?.value
    }
}

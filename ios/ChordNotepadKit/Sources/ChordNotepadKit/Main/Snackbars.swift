import Foundation

// The main screen's snackbars (Android's StatusSnackbars in SongScreen.kt):
// in Edit, which has no status line, each new status message shows briefly;
// errors show in both modes with a close button. As plain state, fed the
// session's snapshot and a clock, so the rules are tested on Linux.

/// One snackbar.
public struct Snackbar: Sendable, Equatable {
    public var text: String
    /// An error: it has a close button and stays longer.
    public var error: Bool
    /// Counts up, so the same text twice is two snackbars.
    public var id: Int

    /// How long it stays, in seconds (Android's Short, and Long for errors).
    public var duration: Double { error ? 10 : 4 }
}

/// Which snackbar shows. Times are seconds on a monotonic clock.
public struct Snackbars: Sendable, Equatable {
    /// The snackbar on screen, or nil.
    public private(set) var shown: Snackbar?
    private var lastStatus: String?
    private var messagesSeen: Int
    private var stoppedAt: Double?
    private var wasActive = false
    private var count = 0

    /// Start from what `snapshot` already holds: nothing old pops up.
    public init(_ snapshot: SessionSnapshot = SessionSnapshot()) {
        lastStatus = snapshot.status?.text
        messagesSeen = snapshot.messageCount
        wasActive = (snapshot.playback?.status ?? .idle) != .idle
    }

    /// The session's output changed: show what's new. Call
    /// after a mode switch has settled (Android waits 150 ms), so a song that
    /// opens in Play along with its status doesn't flash it.
    public mutating func update(_ snapshot: SessionSnapshot, mode: AppMode, now: Double) {
        let active = (snapshot.playback?.status ?? .idle) != .idle
        if wasActive && !active { stoppedAt = now }
        wasActive = active
        if snapshot.messageCount > messagesSeen {
            messagesSeen = snapshot.messageCount
            if let message = snapshot.messages.last {
                show(message, error: true)
                return
            }
        }
        let status = snapshot.status?.text
        if status != lastStatus {
            lastStatus = status
            if let status, !status.trimmingCharacters(in: .whitespaces).isEmpty,
               statusSnackbarAllowed(mode: mode, now: now, stoppedAt: stoppedAt), shown?.error != true {
                show(status, error: false)
            }
        }
    }

    /// The mode changed: a status message still up from Edit goes (errors stay).
    public mutating func modeChanged(_ mode: AppMode) {
        if !statusSnackbarsShown(mode), shown?.error == false { shown = nil }
    }

    /// A short notice in either mode (why a greyed button does nothing;
    /// Android shows a Toast). It doesn't replace an error.
    public mutating func notice(_ text: String) {
        if shown?.error != true { show(text, error: false) }
    }

    /// The snackbar `id` timed out or was closed.
    public mutating func dismiss(_ id: Int) {
        if shown?.id == id { shown = nil }
    }

    private mutating func show(_ text: String, error: Bool) {
        count += 1
        shown = Snackbar(text: text, error: error, id: count)
    }
}

/// The app bar's tab captions: shown, except on a phone at the accessibility
/// text sizes, where the tabs are icons only so the title keeps its room.
public func modeTabLabelsShown(windowWidth: Double, accessibilityText: Bool) -> Bool {
    !(accessibilityText && windowWidth < MainMetrics.phoneMaxSmallestWidth)
}

import Foundation

// What the main screen shows about playback (Android's ui/main/PlaybackUi.kt)
// and what the player bar draws (ui/play/Player.kt's PlayerState).

extension PlaybackState {
    /// True from Play until the first chord sounds: the session renders the
    /// whole song before the first note, so it reports `playing` with no chord
    /// yet. A resume keeps its chord, so it never counts.
    public var isStarting: Bool { status == .playing && chordIndex == nil }
}

/// Whether the screen stays awake: while a song plays or starts; a pause, stop
/// or the end lets it sleep (iOS: the idle timer).
public func keepScreenOn(_ playback: PlaybackState?) -> Bool {
    playback?.status == .playing
}

/// Edit mode shows the session's status messages as snackbars; Play shows
/// them on the player's status line.
public func statusSnackbarsShown(_ mode: AppMode) -> Bool {
    mode == .edit
}

/// How long after playback stops its status ("Bar 5/8") is still the player's, not news.
public let stoppedStatusSeconds = 1.5

/// Whether a status that arrived at `now` shows as a snackbar: in Edit, and
/// not as the echo of a song that stopped at `stoppedAt` (switching to Edit
/// while playing stops the song, and its "Bar 5/8" means nothing there).
/// Times in seconds on any monotonic clock.
public func statusSnackbarAllowed(mode: AppMode, now: Double, stoppedAt: Double?) -> Bool {
    statusSnackbarsShown(mode) && (stoppedAt.map { now - $0 > stoppedStatusSeconds } ?? true)
}

/// How far above the bottom a snackbar sits so it clears the player (error
/// snackbars show in Play too). Side by side, the player is in the column
/// beside the text and the bottom is free.
public func snackbarClearance(mode: AppMode, sideBySide: Bool) -> Double {
    mode == .play && !sideBySide ? MainMetrics.playerHeight : 0
}

/// The speed badge on the player's speed button ("1.25×"), nil at 100 %.
public func speedBadge(_ pct: Double) -> String? {
    if abs(pct - 100) < 0.001 { return nil }
    let factor = (pct * 10).rounded(.toNearestOrAwayFromZero) / 1000
    var text = String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), factor)
    while text.hasSuffix("0") { text.removeLast() }
    if text.hasSuffix(".") { text.removeLast() }
    if text.isEmpty { text = "0" }
    return text + "×"
}

/// What the player bar shows (Android's `PlayerState`).
public struct PlayerState: Sendable, Equatable {
    /// The song pill: "100 · 3/4 · Am".
    public var pill: String
    public var playing: Bool
    /// Play was pressed and the song is still being rendered: the play button
    /// shows a ring and ignores taps.
    public var starting: Bool
    public var metronome: Bool
    /// "1.25×", nil at 100 %.
    public var speedBadge: String?
    public var sheetVisible: Bool
    /// Position and activity: "Bar 6/24 · Playing Em".
    public var status: String
    /// For the buttons' descriptions.
    public var voicingLabel: String
    /// Set while a song plays: the voicing button is greyed out and says why.
    public var voicingLockedReason: String?
    public var instrumentLabel: String

    public init(pill: String = "", playing: Bool = false, starting: Bool = false, metronome: Bool = false,
                speedBadge: String? = nil, sheetVisible: Bool = false, status: String = "",
                voicingLabel: String = "", voicingLockedReason: String? = nil, instrumentLabel: String = "") {
        self.pill = pill
        self.playing = playing
        self.starting = starting
        self.metronome = metronome
        self.speedBadge = speedBadge
        self.sheetVisible = sheetVisible
        self.status = status
        self.voicingLabel = voicingLabel
        self.voicingLockedReason = voicingLockedReason
        self.instrumentLabel = instrumentLabel
    }

    /// The player's state from the session's. `fallbackStatus` is what the
    /// status line says before the session has a status (starting, failed).
    public static func of(_ snapshot: SessionSnapshot, fallbackStatus: String? = nil) -> PlayerState {
        let instruments = snapshot.instrumentMenu.map(instrumentFamilies)
        return PlayerState(
            pill: snapshot.songDefaults?.summary ?? "",
            playing: snapshot.playback?.status == .playing,
            starting: snapshot.playback?.isStarting ?? false,
            metronome: snapshot.toolbar?.metronome ?? false,
            speedBadge: snapshot.toolbar.flatMap { ChordNotepadKit.speedBadge($0.multiplierPct) },
            sheetVisible: snapshot.chordSheet?.visible ?? false,
            status: snapshot.status?.text ?? fallbackStatus ?? "",
            voicingLabel: selectedVoicingLabel(snapshot.voicingMenu) ?? "",
            voicingLockedReason: snapshot.voicingMenu?.lockedReason,
            instrumentLabel: instruments.flatMap(currentProgramName) ?? "")
    }
}

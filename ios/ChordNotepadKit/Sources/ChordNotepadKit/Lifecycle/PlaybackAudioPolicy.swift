import Foundation

// Android's lifecycle/PlaybackAudioPolicy.kt and AppLifecycleHooks.kt for iOS:
// which audio session and scene event sends which of the session's host
// commands. The app's AudioSessionObserver feeds it AVAudioSession's
// notifications and the scene phase; nothing here knows AVFoundation.

/// The commands the policy sends: the bridge's `pause` and its two host
/// commands, which are the only way to release and reopen FluidSynth's output.
public enum AudioPolicyCommand: String, Sendable, Equatable {
    /// `pause`: pause a playing song; nothing otherwise (never plays).
    case pause
    /// `app_background`: pause, save the settings, release the audio output
    /// (refused while a song renders).
    case appBackground
    /// `app_foreground`: reopen the audio output released by `app_background`.
    case appForeground

    public var command: BridgeCommand {
        switch self {
        case .pause: return .pause()
        case .appBackground: return .appBackground()
        case .appForeground: return .appForeground()
        }
    }
}

/// The scene's phase, as SwiftUI's `ScenePhase` has it.
public enum ScenePresence: Sendable, Equatable {
    case active
    case inactive
    case background
}

/// Audio focus as iOS has it: the audio session's category options.
/// FluidSynth sets Playback with mix-with-others each time it opens its output
/// (`fluid_coreaudio_avaudiosession.m`), which plays along with other apps'
/// music. "Focus" is Playback without that option, activated: other apps'
/// music stops, as Android's `AUDIOFOCUS_GAIN` makes it, and another app's
/// audio interrupts ours, as a focus loss does.
public protocol AudioFocusGateway: AnyObject {
    /// Make the session non-mixable and activate it; `done` gets whether that
    /// worked (on the main thread).
    func request(_ done: @escaping (Bool) -> Void)

    /// Make the session mixable again (FluidSynth's options). It stays
    /// active: the output is still open.
    func abandon()
}

/// Plays by iOS's audio rules, as Android's `PlaybackAudioPolicy` does by
/// Android's, driven by `PlaybackState`'s status, the audio session's
/// notifications and the scene phase:
///
/// - entering PLAYING asks for focus (denied → `pause`); IDLE gives it back;
///   PAUSED keeps it, so a resume doesn't ask again. Every event that
///   releases the output drops it too, since FluidSynth makes the session
///   mixable again when it reopens the output.
/// - an interruption (a call, an alarm, Siri, another app's audio) is a focus
///   loss: `app_background`, which pauses and releases the output the system
///   has just stopped. Its end reopens the output (`app_foreground`) while
///   the app is on screen, but never resumes the song: Android doesn't on a
///   focus gain. An interruption that only says the app was suspended in the
///   background is ignored: `app_background` went when the app left the
///   screen, and the scene's return reopens the output.
/// - the old route gone (headphones unplugged, a Bluetooth device
///   disconnected) is Android's "becoming noisy": `pause` while a song plays
///   or is paused.
/// - the media services reset: the output is gone with them, so
///   `app_background` and, on screen, `app_foreground` open a new one.
/// - the scene in the background: `app_background` (Android's `onStop`); back
///   from it, `app_foreground` (`onStart`). Nothing for `inactive`.
///
/// No background playback: like Android, the app pauses when it leaves the
/// screen (no `UIBackgroundModes` audio).
public final class PlaybackAudioPolicy {
    private let focus: AudioFocusGateway
    private let send: (AudioPolicyCommand) -> Void
    private var last: PlaybackStatus = .idle
    private var engaged = false
    private var focusHeld = false
    private var background = false
    /// `app_background` went for an interruption or the background, and no
    /// `app_foreground` since.
    private var outputReleased = false
    /// Between an interruption's start and its end (not every start gets one).
    private var interrupted = false

    /// - Parameters:
    ///   - focus: The audio session's category.
    ///   - send: Submits the command to the session.
    public init(focus: AudioFocusGateway, send: @escaping (AudioPolicyCommand) -> Void) {
        self.focus = focus
        self.send = send
    }

    /// React to the transport's status (`PlaybackState.status`; nil is IDLE).
    public func onStatus(_ status: PlaybackStatus?) {
        let status = status ?? .idle
        let previous = last
        last = status
        switch status {
        case .playing:
            if previous != .playing { startPlaying() }
        case .paused:
            break
        case .idle:
            if engaged { release() }
        }
    }

    /// An interruption began. `appWasSuspended`: the system's note, on the
    /// way back, that the app was suspended (`AVAudioSession.InterruptionReason.appWasSuspended`).
    public func interruptionBegan(appWasSuspended: Bool) {
        guard !appWasSuspended else { return }
        interrupted = true
        guard !background else { return }
        releaseOutput()
    }

    /// The interruption ended (`shouldResume` isn't followed: no resume).
    public func interruptionEnded() {
        interrupted = false
        reopenIfReleased()
    }

    /// The audio route changed; `oldDeviceUnavailable` when the device it
    /// played on went away.
    public func routeChanged(oldDeviceUnavailable: Bool) {
        if oldDeviceUnavailable && engaged { send(.pause) }
    }

    /// The media services were reset: every audio object is gone.
    public func mediaServicesReset() {
        releaseOutput()
        interrupted = false
        reopenIfReleased()
    }

    /// The scene's phase changed.
    public func scene(_ presence: ScenePresence) {
        switch presence {
        case .background:
            guard !background else { return }
            background = true
            // Backgrounding supersedes an interruption that never ended.
            interrupted = false
            releaseOutput()
        case .active:
            guard background else { return }
            background = false
            reopenIfReleased()
        case .inactive:
            break
        }
    }

    private func startPlaying() {
        engaged = true
        // A resume after pause: focus is still held.
        if focusHeld { return }
        focusHeld = true
        focus.request { [weak self] granted in
            guard let self, !granted else { return }
            self.focusHeld = false
            self.send(.pause)
        }
    }

    private func release() {
        engaged = false
        focusHeld = false
        focus.abandon()
    }

    private func releaseOutput() {
        // The output FluidSynth opens next makes the session mixable again.
        focusHeld = false
        outputReleased = true
        send(.appBackground)
    }

    private func reopenIfReleased() {
        guard outputReleased, !background, !interrupted else { return }
        outputReleased = false
        send(.appForeground)
    }
}

// The notifications' userInfo values as AVFoundation defines them, so the
// decoding is tested here.
extension PlaybackAudioPolicy {
    /// `AVAudioSession.InterruptionType`: began.
    public static let interruptionBegan: UInt = 1
    /// `AVAudioSession.InterruptionType`: ended.
    public static let interruptionEnded: UInt = 0
    /// `AVAudioSession.InterruptionReason.appWasSuspended` (iOS 14.5 to 16; later
    /// systems don't send it, but an older note costs nothing to ignore).
    public static let reasonAppWasSuspended: UInt = 1
    /// `AVAudioSession.RouteChangeReason.oldDeviceUnavailable`.
    public static let routeOldDeviceUnavailable: UInt = 2

    /// An `interruptionNotification`: its `AVAudioSessionInterruptionTypeKey`,
    /// `AVAudioSessionInterruptionReasonKey` and the older
    /// `AVAudioSessionInterruptionWasSuspendedKey`. One without a known type is ignored.
    public func interruption(type: UInt?, reason: UInt?, wasSuspended: Bool?) {
        switch type {
        case Self.interruptionBegan?:
            interruptionBegan(appWasSuspended: reason == Self.reasonAppWasSuspended || wasSuspended == true)
        case Self.interruptionEnded?:
            interruptionEnded()
        default:
            break
        }
    }

    /// A `routeChangeNotification` with its `AVAudioSessionRouteChangeReasonKey`.
    public func routeChange(reason: UInt?) {
        routeChanged(oldDeviceUnavailable: reason == Self.routeOldDeviceUnavailable)
    }
}

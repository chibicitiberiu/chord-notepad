import AVFoundation
import ChordNotepadKit
import UIKit

/// Android's `AppGraph.install` audio wiring for iOS: AVAudioSession's
/// interruption, route change and media services reset notifications, the
/// scene phase and the playback status go to the kit's
/// ``PlaybackAudioPolicy``, whose commands go to the session
/// (docs/IOS.md, "Audio, multitasking and accessibility").
@MainActor
final class AudioSessionObserver {
    let policy: PlaybackAudioPolicy
    /// What the policy sent, oldest first (the session test reads it; the log has each).
    private(set) var sent: [AudioPolicyCommand] = []
    private var tokens: [NSObjectProtocol] = []

    init(focus: AudioFocusGateway, submit: @escaping (BridgeCommand) -> Void) {
        var record: (AudioPolicyCommand) -> Void = { _ in }
        policy = PlaybackAudioPolicy(focus: focus) { record($0) }
        record = { [weak self] command in
            self?.sent.append(command)
            Log.audio.info("Audio policy: \(command.rawValue, privacy: .public)")
            submit(command.command)
        }
    }

    /// Observe the shared audio session's notifications (main queue).
    func start(center: NotificationCenter = .default) {
        guard tokens.isEmpty else { return }
        let session = AVAudioSession.sharedInstance()
        tokens.append(center.addObserver(forName: AVAudioSession.interruptionNotification, object: session,
                                         queue: .main) { [weak self] note in
            let info = note.userInfo ?? [:]
            let type = (info[AVAudioSessionInterruptionTypeKey] as? NSNumber)?.uintValue
            let reason = (info[AVAudioSessionInterruptionReasonKey] as? NSNumber)?.uintValue
            // AVAudioSessionInterruptionWasSuspendedKey, deprecated since iOS 14.5.
            let suspended = (info["AVAudioSessionInterruptionWasSuspendedKey"] as? NSNumber)?.boolValue
            let described = "type \(type.map { String($0) } ?? "?"), reason \(reason.map { String($0) } ?? "-")"
            Log.audio.info("Interruption \(described, privacy: .public)")
            MainActor.assumeIsolated {
                self?.policy.interruption(type: type, reason: reason, wasSuspended: suspended)
            }
        })
        tokens.append(center.addObserver(forName: AVAudioSession.routeChangeNotification, object: session,
                                         queue: .main) { [weak self] note in
            let reason = (note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? NSNumber)?.uintValue
            let described = reason.map { String($0) } ?? "?"
            Log.audio.info("Route change, reason \(described, privacy: .public)")
            MainActor.assumeIsolated {
                self?.policy.routeChange(reason: reason)
            }
        })
        tokens.append(center.addObserver(forName: AVAudioSession.mediaServicesWereResetNotification, object: session,
                                         queue: .main) { [weak self] _ in
            Log.audio.error("The media services were reset")
            MainActor.assumeIsolated {
                self?.policy.mediaServicesReset()
            }
        })
        tokens.append(center.addObserver(forName: AVAudioSession.mediaServicesWereLostNotification, object: session,
                                         queue: .main) { _ in
            // Nothing to do until they're back (the reset above).
            Log.audio.error("The media services were lost")
        })
    }

    func stop(center: NotificationCenter = .default) {
        tokens.forEach(center.removeObserver)
        tokens = []
    }
}

/// ``AudioFocusGateway`` over AVAudioSession: Playback without
/// mix-with-others, activated, while a song plays; FluidSynth's options
/// (Playback, mix with others) again once it stops. AVAudioSession's calls
/// can block, so they run on a queue of their own.
final class SystemAudioFocus: AudioFocusGateway {
    private let queue = DispatchQueue(label: "audio-focus", qos: .userInitiated)

    func request(_ done: @escaping (Bool) -> Void) {
        queue.async {
            let session = AVAudioSession.sharedInstance()
            var granted = true
            do {
                try session.setCategory(.playback, mode: .default, options: [])
                try session.setActive(true)
            } catch {
                granted = false
                Log.audio.error("Audio focus refused: \(String(describing: error), privacy: .public)")
            }
            DispatchQueue.main.async { done(granted) }
        }
    }

    func abandon() {
        queue.async {
            do {
                try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.mixWithOthers])
            } catch {
                Log.audio.error("Audio focus not given back: \(String(describing: error), privacy: .public)")
            }
        }
    }
}

extension AVAudioSession.CategoryOptions {
    /// The options' names, for the self-test's report.
    var names: [String] {
        var names: [String] = []
        if contains(.mixWithOthers) { names.append("mixWithOthers") }
        if contains(.duckOthers) { names.append("duckOthers") }
        if contains(.defaultToSpeaker) { names.append("defaultToSpeaker") }
        if contains(.allowBluetoothA2DP) { names.append("allowBluetoothA2DP") }
        if contains(.allowAirPlay) { names.append("allowAirPlay") }
        // allowBluetooth (HFP), whose name changes in iOS 26.
        if rawValue & 0x4 != 0 { names.append("allowBluetoothHFP") }
        return names
    }
}

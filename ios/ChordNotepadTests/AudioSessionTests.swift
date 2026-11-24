import AVFoundation
import ChordNotepadKit
import UIKit
import XCTest

@testable import ChordNotepad

/// The session test's audio focus: grants every request and records the calls
/// (the real one changes the simulator's audio session, checked once at the end).
final class RecordingAudioFocus: AudioFocusGateway {
    private(set) var calls: [String] = []

    func request(_ done: @escaping (Bool) -> Void) {
        calls.append("request")
        done(true)
    }

    func abandon() {
        calls.append("abandon")
    }
}

extension SessionTests {
    /// The platform glue, live: AVAudioSession's notifications posted as the
    /// system posts them (the same names, object and userInfo keys) while the
    /// session's FakePlayer holds a song playing (`CN_TEST_FAKE_PLAYER=hold`):
    /// an interruption pauses (`app_background`) and its end reopens the
    /// output without resuming; headphones unplugged pause, another route
    /// change doesn't; the scene in the background pauses; a media services
    /// reset pauses and opens a new output; focus is asked for at each play
    /// after the output was reopened and given back at the stop. Last, the
    /// app's real focus on the simulator's audio session (not blocking: a
    /// runner may have no audio device).
    func checkAudioSession(_ model: AppModel) async throws {
        let session = try XCTUnwrap(model.session)
        let audio = try XCTUnwrap(model.audio)
        let focus = try XCTUnwrap(model.audioFocus as? RecordingAudioFocus)
        let center = NotificationCenter.default
        let avSession = AVAudioSession.sharedInstance()

        model.selectMode(.play)
        session.submit(.restoreDraft(document: nil, modified: true, readOnly: false, text: "C G Am F\nG C\n"))
        let restored = await model.waitFor(timeout: .seconds(30)) { $0.playback?.playheadOffset == 0 && $0.text.hasPrefix("C G") }
        XCTAssertTrue(restored, "\(String(describing: model.snapshot.playback))")
        let sentBefore = audio.sent.count
        let focusBefore = focus.calls.count
        func sent() -> [AudioPolicyCommand] { Array(audio.sent.dropFirst(sentBefore)) }
        func focusCalls() -> [String] { Array(focus.calls.dropFirst(focusBefore)) }

        /// Play (or resume) and wait until the session says it plays, the song started in the FakePlayer.
        func play(_ what: String) async {
            model.playPause()
            let playing = await model.waitFor(timeout: .seconds(30)) { $0.playback?.status == .playing }
            XCTAssertTrue(playing, "\(what): \(String(describing: model.snapshot.playback))")
            // The session renders the song on its own thread before the player starts.
            try? await Task.sleep(for: .seconds(1))
            XCTAssertEqual(model.snapshot.playback?.status, .playing, "\(what): the FakePlayer holds it")
        }
        func paused(_ what: String) async {
            let ok = await model.waitFor(timeout: .seconds(15)) { $0.playback?.status == .paused }
            XCTAssertTrue(ok, "\(what): \(String(describing: model.snapshot.playback?.status)), sent \(sent())")
        }
        func interruption(_ type: AVAudioSession.InterruptionType, options: AVAudioSession.InterruptionOptions = []) {
            var info: [AnyHashable: Any] = [AVAudioSessionInterruptionTypeKey: NSNumber(value: type.rawValue)]
            if type == .began {
                info[AVAudioSessionInterruptionReasonKey] = NSNumber(value: AVAudioSession.InterruptionReason.default.rawValue)
            } else {
                info[AVAudioSessionInterruptionOptionKey] = NSNumber(value: options.rawValue)
            }
            center.post(name: AVAudioSession.interruptionNotification, object: avSession, userInfo: info)
        }
        func routeChange(_ reason: AVAudioSession.RouteChangeReason) {
            center.post(name: AVAudioSession.routeChangeNotification, object: avSession, userInfo: [
                AVAudioSessionRouteChangeReasonKey: NSNumber(value: reason.rawValue),
                AVAudioSessionRouteChangePreviousRouteKey: avSession.currentRoute,
            ])
        }

        // -- an interruption (a call, an alarm, Siri) --------------------------------------
        await play("play")
        XCTAssertEqual(focusCalls(), ["request"], "focus asked for at play")
        interruption(.began)
        await paused("interruption began")
        XCTAssertEqual(sent(), [.appBackground])
        interruption(.ended, options: .shouldResume)
        XCTAssertEqual(sent(), [.appBackground, .appForeground], "the output reopened")
        try await Task.sleep(for: .seconds(1))
        XCTAssertEqual(model.snapshot.playback?.status, .paused, "no resume after an interruption, as on Android")

        // -- headphones unplugged, and a route change that isn't --------------------------
        await play("resume after the interruption")
        XCTAssertEqual(focusCalls(), ["request", "request"], "asked for again: the reopened output made the session mixable")
        routeChange(.newDeviceAvailable)
        routeChange(.categoryChange)
        try await Task.sleep(for: .milliseconds(500))
        XCTAssertEqual(model.snapshot.playback?.status, .playing, "headphones plugged in don't pause")
        routeChange(.oldDeviceUnavailable)
        await paused("headphones unplugged")
        XCTAssertEqual(sent().last, .pause)

        // -- the background (no background playback, as on Android) -----------------------
        await play("resume after the headphones")
        model.scenePhaseChanged(.inactive)
        model.scenePhaseChanged(.background)
        await paused("the app in the background")
        XCTAssertEqual(sent().last, .appBackground)
        model.scenePhaseChanged(.inactive)
        model.scenePhaseChanged(.active)
        XCTAssertEqual(sent().last, .appForeground)

        // -- the media services reset -----------------------------------------------------
        await play("resume after the background")
        center.post(name: AVAudioSession.mediaServicesWereResetNotification, object: avSession)
        await paused("media services reset")
        XCTAssertEqual(Array(sent().suffix(2)), [.appBackground, .appForeground])

        // -- the stop gives focus back ----------------------------------------------------
        session.submit(.stop())
        let stopped = await model.waitFor(timeout: .seconds(15)) { $0.playback?.status == .idle }
        XCTAssertTrue(stopped, "\(String(describing: model.snapshot.playback?.status))")
        // Play, then each resume after the output was released (the interruption, the
        // background); not the resume after the headphones, which kept it.
        XCTAssertEqual(focusCalls().filter { $0 == "request" }.count, 3, "\(focusCalls())")
        XCTAssertEqual(focusCalls().last, "abandon")
        XCTAssertTrue(model.snapshot.messages.allSatisfy { !$0.hasPrefix("Unexpected error") }, "\(model.snapshot.messages)")

        // -- the real focus on the simulator's audio session (reported, not blocking) -----
        let real = SystemAudioFocus()
        let answered = expectation(description: "the audio session answered")
        var granted: Bool?
        real.request { granted = $0; answered.fulfill() }
        await fulfillment(of: [answered], timeout: 15)
        let held = (category: avSession.category.rawValue, options: avSession.categoryOptions.names)
        real.abandon()
        try await Task.sleep(for: .milliseconds(500))
        let report: [String: Any] = [
            "granted": granted as Any,
            "held_category": held.category,
            "held_options": held.options,
            "after_category": avSession.category.rawValue,
            "after_options": avSession.categoryOptions.names,
            "policy_sent": audio.sent.map(\.rawValue),
            "focus_calls": focus.calls,
        ]
        let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = "audio-session.json"
        attachment.lifetime = .keepAlways
        add(attachment)
        if granted == true {
            XCTAssertFalse(held.options.contains("mixWithOthers"), "focus: not mixable")
            XCTAssertTrue(avSession.categoryOptions.contains(.mixWithOthers), "given back: mixable again")
        }
    }
}

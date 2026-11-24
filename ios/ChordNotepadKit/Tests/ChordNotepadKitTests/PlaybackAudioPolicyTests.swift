import XCTest

@testable import ChordNotepadKit

/// Android's `PlaybackAudioPolicyTest` and `DraftAndLifecycleTest`'s lifecycle
/// case, case for case (the noisy receiver's register and unregister are the
/// route-change filter here: a route change pauses only while engaged), then
/// iOS's interruptions, media services reset and scene phases.
final class PlaybackAudioPolicyTests: XCTestCase {
    private var events: [String] = []
    private var sent: [AudioPolicyCommand] = []
    private var grant = true
    /// Hold the focus answer until `answer()` (AVAudioSession's activation is asynchronous).
    private var deferAnswer = false
    private var pendingAnswer: ((Bool) -> Void)?

    private final class Focus: AudioFocusGateway {
        weak var test: PlaybackAudioPolicyTests?

        func request(_ done: @escaping (Bool) -> Void) {
            guard let test else { return }
            test.events.append("request")
            if test.deferAnswer {
                test.pendingAnswer = done
            } else {
                done(test.grant)
            }
        }

        func abandon() {
            test?.events.append("abandon")
        }
    }

    private var focus = Focus()
    private lazy var policy = PlaybackAudioPolicy(focus: focus) { [unowned self] in self.sent.append($0) }

    override func setUp() {
        super.setUp()
        focus.test = self
    }

    private func go(_ statuses: PlaybackStatus...) {
        statuses.forEach(policy.onStatus)
    }

    private var pauses: Int { sent.filter { $0 == .pause }.count }

    // -- PlaybackAudioPolicyTest ------------------------------------------------------------

    func testPlayTakesFocusAndStopGivesItBack() {
        go(.idle, .playing)
        XCTAssertEqual(events, ["request"])
        go(.idle)
        XCTAssertEqual(events, ["request", "abandon"])
        XCTAssertEqual(pauses, 0)
    }

    func testPauseKeepsFocusResumeDoesNotAskAgain() {
        go(.playing, .paused)
        XCTAssertEqual(events, ["request"])
        go(.playing)
        XCTAssertEqual(events, ["request"])
        XCTAssertEqual(sent, [])
    }

    func testResumeAfterAFocusLossAsksAgain() {
        go(.playing)
        policy.interruptionBegan(appWasSuspended: false)
        go(.paused, .playing)
        XCTAssertEqual(events, ["request", "request"])
    }

    func testDeniedFocusPausesAtOnce() {
        grant = false
        go(.playing)
        XCTAssertEqual(pauses, 1)
        // Denied: the next play asks again.
        go(.paused, .playing)
        XCTAssertEqual(events, ["request", "request"])
    }

    func testFocusLossAndTheOldRouteGonePause() {
        go(.playing)
        policy.interruptionBegan(appWasSuspended: false)
        policy.routeChanged(oldDeviceUnavailable: true)
        XCTAssertEqual(sent, [.appBackground, .pause])
    }

    func testIdleWithoutPlayingDoesNothing() {
        go(.idle, .idle)
        XCTAssertTrue(events.isEmpty)
        XCTAssertTrue(sent.isEmpty)
    }

    func testTheSameStatusAgainIsNothingNew() {
        policy.onStatus(nil)
        go(.playing, .playing)
        XCTAssertEqual(events, ["request"])
        policy.onStatus(nil)
        XCTAssertEqual(events.last, "abandon")
    }

    // -- DraftAndLifecycleTest: AppLifecycleHooks -------------------------------------------

    func testTheBackgroundAndBackSendTheHostCommands() {
        policy.scene(.inactive)
        policy.scene(.background)
        policy.scene(.inactive)
        policy.scene(.active)
        XCTAssertEqual(sent, [.appBackground, .appForeground])
        XCTAssertEqual(AudioPolicyCommand.appBackground.command.name, "app_background")
        XCTAssertEqual(AudioPolicyCommand.appForeground.command.name, "app_foreground")
        XCTAssertEqual(AudioPolicyCommand.pause.command.name, "pause")
    }

    func testActiveWithoutHavingLeftSendsNothing() {
        // The launch, Control Center pulled down and back: the app never left the screen.
        policy.scene(.active)
        policy.scene(.inactive)
        policy.scene(.active)
        XCTAssertTrue(sent.isEmpty)
    }

    func testABackgroundAfterAnotherIsOnlyOne() {
        policy.scene(.background)
        policy.scene(.background)
        XCTAssertEqual(sent, [.appBackground])
    }

    // -- the route ---------------------------------------------------------------------------

    func testAnotherRouteChangeDoesNotPause() {
        go(.playing)
        policy.routeChanged(oldDeviceUnavailable: false)
        XCTAssertTrue(sent.isEmpty)
    }

    func testHeadphonesUnpluggedWhilePausedSendsPauseAsAndroidsReceiverDoes() {
        go(.playing, .paused)
        policy.routeChanged(oldDeviceUnavailable: true)
        XCTAssertEqual(sent, [.pause])
    }

    func testHeadphonesUnpluggedWithNothingPlayingIsIgnored() {
        policy.routeChanged(oldDeviceUnavailable: true)
        go(.playing, .idle)
        policy.routeChanged(oldDeviceUnavailable: true)
        XCTAssertTrue(sent.isEmpty)
    }

    // -- interruptions -----------------------------------------------------------------------

    func testAnInterruptionReleasesTheOutputAndItsEndReopensItWithoutResuming() {
        go(.playing)
        policy.interruptionBegan(appWasSuspended: false)
        XCTAssertEqual(sent, [.appBackground])
        go(.paused)
        policy.interruptionEnded()
        XCTAssertEqual(sent, [.appBackground, .appForeground])
        XCTAssertFalse(sent.contains(.pause), "app_background pauses on its own")
    }

    func testAnInterruptionWhileIdleStillReleasesTheStoppedOutput() {
        // The system stops the output whatever plays: a tap after it needs a new one.
        policy.interruptionBegan(appWasSuspended: false)
        policy.interruptionEnded()
        XCTAssertEqual(sent, [.appBackground, .appForeground])
        XCTAssertTrue(events.isEmpty, "no focus asked or given while idle")
    }

    func testTheSuspendedNoteIsIgnored() {
        policy.scene(.background)
        policy.interruptionBegan(appWasSuspended: true)
        policy.scene(.active)
        XCTAssertEqual(sent, [.appBackground, .appForeground])
    }

    func testAnInterruptionInTheBackgroundEndsWithTheScenesReturn() {
        policy.scene(.background)
        policy.interruptionBegan(appWasSuspended: false)
        policy.interruptionEnded()
        XCTAssertEqual(sent, [.appBackground], "nothing reopens in the background")
        policy.scene(.active)
        XCTAssertEqual(sent, [.appBackground, .appForeground])
    }

    func testInactiveAndBackDuringAnInterruptionWaitsForItsEnd() {
        policy.scene(.background)
        policy.scene(.active)
        policy.interruptionBegan(appWasSuspended: false)
        policy.scene(.inactive)
        policy.scene(.active)
        XCTAssertEqual(sent, [.appBackground, .appForeground, .appBackground])
        policy.interruptionEnded()
        XCTAssertEqual(sent.last, .appForeground)
    }

    func testAnInterruptionThatNeverEndsIsOverOnceTheAppLeftAndCameBack() {
        policy.interruptionBegan(appWasSuspended: false)
        policy.scene(.background)
        policy.scene(.active)
        // The background's own app_background still goes: it saves the settings.
        XCTAssertEqual(sent, [.appBackground, .appBackground, .appForeground])
    }

    func testAnEndWithNothingReleasedSendsNothing() {
        policy.interruptionEnded()
        XCTAssertTrue(sent.isEmpty)
    }

    func testFocusIsAskedForAgainAfterTheOutputWasReopened() {
        // FluidSynth makes the session mixable again when it opens a new output.
        go(.playing, .paused)
        policy.scene(.background)
        policy.scene(.active)
        go(.playing)
        XCTAssertEqual(events, ["request", "request"])
    }

    // -- the media services ------------------------------------------------------------------

    func testAMediaServicesResetOpensANewOutput() {
        go(.playing)
        policy.mediaServicesReset()
        XCTAssertEqual(sent, [.appBackground, .appForeground])
        go(.paused, .playing)
        XCTAssertEqual(events, ["request", "request"])
    }

    func testAMediaServicesResetInTheBackgroundWaitsForTheScene() {
        policy.scene(.background)
        policy.mediaServicesReset()
        XCTAssertEqual(sent, [.appBackground, .appBackground])
        policy.scene(.active)
        XCTAssertEqual(sent.last, .appForeground)
    }

    // -- the notifications' values -----------------------------------------------------------

    func testTheInterruptionsUserInfoAsAVFoundationDefinesIt() {
        go(.playing)
        policy.interruption(type: 1, reason: 0, wasSuspended: nil)
        XCTAssertEqual(sent, [.appBackground], "began, the default reason")
        policy.interruption(type: 0, reason: nil, wasSuspended: nil)
        XCTAssertEqual(sent, [.appBackground, .appForeground], "ended")
        policy.interruption(type: 1, reason: 1, wasSuspended: nil)
        policy.interruption(type: 1, reason: nil, wasSuspended: true)
        policy.interruption(type: nil, reason: nil, wasSuspended: nil)
        policy.interruption(type: 7, reason: nil, wasSuspended: nil)
        XCTAssertEqual(sent, [.appBackground, .appForeground], "the suspended notes and unknown types are ignored")
        policy.interruption(type: 1, reason: 2, wasSuspended: false)
        XCTAssertEqual(sent.last, .appBackground, "the built-in microphone muted is an interruption like any")
    }

    func testTheRouteChangesReason() {
        go(.playing)
        for reason: UInt in [0, 1, 3, 4, 5, 6, 7, 8] {
            policy.routeChange(reason: reason)
        }
        policy.routeChange(reason: nil)
        XCTAssertTrue(sent.isEmpty, "only the old device gone pauses")
        policy.routeChange(reason: 2)
        XCTAssertEqual(sent, [.pause])
    }

    // -- the focus answer comes later --------------------------------------------------------

    func testALateDenialPauses() {
        deferAnswer = true
        go(.playing)
        XCTAssertTrue(sent.isEmpty)
        pendingAnswer?(false)
        XCTAssertEqual(sent, [.pause])
    }

    func testALateGrantDoesNothing() {
        deferAnswer = true
        go(.playing)
        pendingAnswer?(true)
        go(.paused, .playing)
        XCTAssertEqual(events, ["request"])
        XCTAssertTrue(sent.isEmpty)
    }
}

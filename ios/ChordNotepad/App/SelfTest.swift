import AVFAudio
import ChordNotepadKit
import Foundation
import UIKit

/// The self-test screen's checks (docs/IOS.md, "Diagnostics"): how long
/// Python took, whether the synth renders sound with no audio device
/// involved, whether the live player started and where the sound goes.
/// The report is saved as `Diagnostics/selftest.json`.
struct SelfTestReport: Codable, Equatable {
    struct Render: Codable, Equatable {
        var ok: Bool
        var peak: Int
        var frames: Int
        var seconds: Double
        var error: String?
    }

    struct AudioStatus: Codable, Equatable {
        var session: Bool
        var initialized: Bool
        var error: String?
        var soundfont: String?
    }

    var date: String
    var build: BuildInfo
    var device: String
    var timings: LaunchTimings
    /// The chord rendered offline (FluidSynth with no driver): the blocking check.
    var offlineRender: Render?
    /// The live player (FluidSynth's CoreAudio driver), after a chord was auditioned.
    var liveAudio: AudioStatus?
    /// Messages the session sent after the audition (an `AudioUnavailable`, say).
    var auditionMessages: [String]
    var audioCategory: String
    var audioRoute: [String]
    var sampleRate: Double
    var ioBufferDuration: Double
    var problems: [String]

    var passed: Bool { problems.isEmpty }
}

@MainActor
enum SelfTest {
    /// Run every check against the model's session.
    static func run(model: AppModel) async -> SelfTestReport {
        var problems: [String] = []
        let render: SelfTestReport.Render?
        do {
            render = try await offlineRender(model: model)
            if let render, !render.ok { problems.append("Offline render: \(render.error ?? "silent")") }
        } catch {
            render = nil
            problems.append("Offline render: \(error)")
        }

        let before = model.snapshot.messages.count
        model.audition(index: 0)
        try? await Task.sleep(for: .seconds(1.5))
        let auditionMessages = Array(model.snapshot.messages.suffix(max(0, model.snapshot.messages.count - before)))
        let live = try? await audioStatus(model: model)
        if live?.initialized != true {
            problems.append("Live audio: \(live?.error ?? "not started")")
        }

        let audio = AVAudioSession.sharedInstance()
        let route = audio.currentRoute.outputs.map { "\($0.portType.rawValue): \($0.portName)" }
        let device = UIDevice.current
        let report = SelfTestReport(
            date: ISO8601DateFormatter().string(from: Date()),
            build: .current,
            device: "\(device.model) \(device.systemName) \(device.systemVersion)",
            timings: model.timings,
            offlineRender: render,
            liveAudio: live,
            auditionMessages: auditionMessages,
            audioCategory: audio.category.rawValue,
            audioRoute: route,
            sampleRate: audio.sampleRate,
            ioBufferDuration: audio.ioBufferDuration,
            problems: problems)
        Diagnostics.shared.writeJSON(report, name: "selftest.json")
        let outcome = report.passed ? "passed" : "problems: " + problems.joined(separator: "; ")
        Log.ui.info("Self-test: \(outcome, privacy: .public)")
        return report
    }

    /// A chord rendered by FluidSynth with no audio driver, measured (the core's audio export renderer).
    static func offlineRender(model: AppModel) async throws -> SelfTestReport.Render {
        guard let runtime = model.runtime else { throw SelfTestError("Python isn't running") }
        guard let soundFont = AppPaths.soundFont else { throw SelfTestError("The SoundFont is missing") }
        let signpost = Signposts.audio.beginInterval("offline render")
        defer { Signposts.audio.endInterval("offline render", signpost) }
        let json = try await runtime.call("chordnotepad_ios.diagnostics", "offline_render", [soundFont.path]) ?? "{}"
        return try JSONDecoder().decode(SelfTestReport.Render.self, from: Data(json.utf8))
    }

    /// The session's live player.
    static func audioStatus(model: AppModel) async throws -> SelfTestReport.AudioStatus {
        guard let runtime = model.runtime else { throw SelfTestError("Python isn't running") }
        let json = try await runtime.call("chordnotepad_ios.diagnostics", "audio_status") ?? "{}"
        return try JSONDecoder().decode(SelfTestReport.AudioStatus.self, from: Data(json.utf8))
    }
}

struct SelfTestError: Error, CustomStringConvertible {
    let description: String

    init(_ description: String) {
        self.description = description
    }
}

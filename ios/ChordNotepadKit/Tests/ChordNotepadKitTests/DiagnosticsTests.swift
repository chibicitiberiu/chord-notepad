import Foundation
import XCTest

@testable import ChordNotepadKit

/// `chordnotepad_ios.diagnostics`, which the app's self-test and Diagnostics
/// folder call: the offline synth render (the same check CI's simulators
/// make with the iOS framework) and the fault handler's file.
final class DiagnosticsTests: XCTestCase {
    func testTheOfflineRenderOfAChordIsNotSilent() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let soundfont = TestPython.repo.appendingPathComponent("resources/soundfont/GeneralUser-GS.sf2").path
        let result = try jsonObject(try await runtime.call("chordnotepad_ios.diagnostics", "offline_render", [soundfont]))
        XCTAssertEqual(result["ok"] as? Bool, true, "\(result)")
        XCTAssertGreaterThan(result["peak"] as? Int ?? 0, 1000, "\(result)")
        XCTAssertEqual(result["frames"] as? Int, 22050)
        XCTAssertTrue(result["error"] is NSNull, "\(result)")
    }

    func testAMissingSoundFontIsReportedNotRaised() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let result = try jsonObject(try await runtime.call("chordnotepad_ios.diagnostics", "offline_render",
                                                           ["/nonexistent/none.sf2"]))
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertNotNil(result["error"] as? String, "\(result)")
    }

    func testTheFaultHandlerWritesItsFile() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let path = FileManager.default.temporaryDirectory.appendingPathComponent("cn-fault-\(UUID().uuidString).log").path
        defer { try? FileManager.default.removeItem(atPath: path) }
        let result = try jsonObject(try await runtime.call("chordnotepad_ios.diagnostics", "enable_faulthandler", [path]))
        XCTAssertEqual(result["path"] as? String, path)
        let text = try String(contentsOfFile: path, encoding: .utf8)
        XCTAssertTrue(text.hasPrefix("-- faulthandler enabled "), text)
        _ = try await runtime.call("faulthandler", "disable")
    }
}

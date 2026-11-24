import Foundation
import XCTest

@testable import ChordNotepadKit

/// The buttons' VoiceOver labels against Android's `contentDescription`
/// strings in `android/app/src/main/res/values`, word for word.
final class AccessibilityLabelsTests: XCTestCase {
    /// Every `<string name="…">…</string>` in Android's default resources.
    private static func androidStrings() throws -> [String: String] {
        let folder = TestPython.repo.appendingPathComponent("android/app/src/main/res/values")
        let files = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
            .filter { $0.lastPathComponent.hasPrefix("strings") && $0.pathExtension == "xml" }
        XCTAssertFalse(files.isEmpty, folder.path)
        let pattern = try NSRegularExpression(pattern: #"<string name="([a-z0-9_]+)"[^>]*>(.*?)</string>"#,
                                              options: [.dotMatchesLineSeparators])
        var strings: [String: String] = [:]
        for file in files {
            let xml = try String(contentsOf: file, encoding: .utf8)
            for match in pattern.matches(in: xml, range: NSRange(xml.startIndex..., in: xml)) {
                guard let name = Range(match.range(at: 1), in: xml), let value = Range(match.range(at: 2), in: xml)
                else { continue }
                strings[String(xml[name])] = String(xml[value])
                    .replacingOccurrences(of: "\\'", with: "'")
                    .replacingOccurrences(of: "\\\"", with: "\"")
                    .replacingOccurrences(of: "&amp;", with: "&")
                    .replacingOccurrences(of: "&lt;", with: "<")
            }
        }
        return strings
    }

    func testEveryLabelIsAndroidsString() throws {
        let android = try Self.androidStrings()
        XCTAssertGreaterThan(android.count, 100, "Android's strings weren't read")
        for (resource, label) in AccessibilityLabels.androidResources {
            XCTAssertEqual(label, android[resource], resource)
        }
    }

    func testNoResourceIsListedTwice() {
        let names = AccessibilityLabels.androidResources.map(\.resource)
        XCTAssertEqual(names.count, Set(names).count)
    }

    func testTheValuesGoWhereAndroidPutsThem() {
        XCTAssertEqual(AccessibilityLabels.voicing("Piano"), "Voicing: Piano")
        XCTAssertEqual(AccessibilityLabels.instrument("Steel Guitar"), "Instrument: Steel Guitar")
        XCTAssertEqual(AccessibilityLabels.songDefaults("𝄞 90 · 3/4 · G"), "Playback settings: 𝄞 90 · 3/4 · G")
    }

    func testTheFindBarsLabelsAreTheQtDesktopsTooltips() throws {
        let qml = try String(contentsOf: TestPython.repo.appendingPathComponent(
            "desktop/chordnotepad_desktop/qml/app/FindBar.qml"), encoding: .utf8)
        for label in [AccessibilityLabels.previousMatch, AccessibilityLabels.nextMatch, AccessibilityLabels.matchCase,
                      AccessibilityLabels.wholeWords, AccessibilityLabels.close] {
            XCTAssertTrue(qml.contains("tip: \"\(label)\""), label)
        }
    }
}

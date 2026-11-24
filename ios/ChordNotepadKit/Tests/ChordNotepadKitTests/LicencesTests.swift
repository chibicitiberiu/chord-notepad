import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `LicencesTest`, case for case, on the iOS app's list
/// (ios/Licenses/components.json) and the texts the "Licences"
/// build phase copies from resources/licenses/texts. Android's Maven cases
/// have no iOS counterpart (no AboutLibraries; Apple's frameworks are the
/// system's). The pages' routes are ``MainRoute``'s.
final class LicencesTests: XCTestCase {
    private static let componentsURL = TestPython.repo.appendingPathComponent("ios/Licenses/components.json")
    private static let textsURL = TestPython.repo.appendingPathComponent("resources/licenses/texts")

    private let data = try! Data(contentsOf: LicencesTests.componentsURL)
    private var components: [LicenceEntry] { try! Licences.parseComponents(data) }

    private func text(_ entry: LicenceEntry) throws -> String {
        try Licences.text(of: entry, textsDirectory: Self.textsURL)
    }

    func testEveryEntryParsesAndHasTheFieldsTheScreenNeeds() {
        XCTAssertGreaterThan(components.count, 20)
        for c in components {
            XCTAssertFalse(c.name.trimmingCharacters(in: .whitespaces).isEmpty, "\(c.id): name")
            XCTAssertFalse(c.license.trimmingCharacters(in: .whitespaces).isEmpty, "\(c.id): license")
            XCTAssertFalse(c.textFiles.isEmpty, "\(c.id): needs a licence text")
            XCTAssertTrue(!(c.url ?? "").isEmpty || c.group == .app, "\(c.id): needs a home page")
        }
        XCTAssertEqual(Set(components.map(\.id)).count, components.count, "duplicate ids")
    }

    func testEveryLicenceTextAnEntryNamesExistsAndHasContent() throws {
        for c in components {
            XCTAssertGreaterThan(try text(c).count, 100, "\(c.id): empty licence text")
        }
    }

    func testTheBuildPhaseCopiesTheTextsTheEntriesNameAndNoOther() throws {
        let used = Set(components.flatMap(\.textFiles))
        let available = Set(try FileManager.default.contentsOfDirectory(atPath: Self.textsURL.path)
            .filter { $0.hasSuffix(".txt") }.map { String($0.dropLast(4)) })
        XCTAssertEqual(used.subtracting(available), [], "texts that are missing")
        let tool = try String(contentsOf: TestPython.repo.appendingPathComponent("ios/tools/copy_licences.py"),
                              encoding: .utf8)
        XCTAssertTrue(tool.contains("resources/licenses/texts"))
        XCTAssertTrue(tool.contains("ios/Licenses/components.json"))
    }

    func testTheComponentsTheAppShipsAreAllThere() {
        let ids = Set(components.map(\.id))
        let expected = ["chord-notepad", "chord-notepad-logo", "cpython", "openssl", "libffi", "xz", "bzip2",
                        "libmpdec", "zstd", "expat", "fluidsynth", "gcem", "pychord", "music21", "mido",
                        "generaluser-gs", "bravura", "material-design-icons-mdi", "material-icons-google"]
        XCTAssertEqual(expected.filter { !ids.contains($0) }, [])
        // Android's own (Chaquopy, Oboe, the libsndfile family, libc++) and
        // what the iOS app leaves out (chardet, the guide it doesn't ship yet).
        let notOnIOS = ["chaquopy", "oboe", "libsndfile", "libogg", "libvorbis", "flac", "opus", "libcxx",
                        "signalsmith-dsp", "chardet", "chord-notepad-guide", "sphinx", "ca-bundle"]
        XCTAssertEqual(notOnIOS.filter { ids.contains($0) }, [])
        XCTAssertFalse(components.contains { $0.group == .guide })
    }

    func testTheVersionsAreTheOnesTheBuildPins() throws {
        let entry = Dictionary(uniqueKeysWithValues: components.map { ($0.id, $0) })
        let fluidsynth = try String(contentsOf: TestPython.repo.appendingPathComponent("packaging/ios/build_fluidsynth.sh"),
                                    encoding: .utf8)
        XCTAssertTrue(fluidsynth.contains("FLUIDSYNTH_VERSION=\(entry["fluidsynth"]!.version!)\n"))
        let python = try String(contentsOf: TestPython.repo.appendingPathComponent("packaging/ios/fetch_python.sh"),
                                encoding: .utf8)
        // BeeWare's 3.14-b14: CPython 3.14.10 with OpenSSL 3.5.9 (its VERSIONS file, printed in CI's log).
        XCTAssertTrue(python.contains("SUPPORT_RELEASE=3.14-b14\n"))
        XCTAssertEqual(entry["cpython"]?.version, "3.14.10")
        XCTAssertEqual(entry["openssl"]?.version, "3.5.9")
        XCTAssertTrue(entry["cpython"]?.note?.contains("3.14-b14") == true)
    }

    func testTheAppIsAGPLAndTheSoundFontCarriesItsOwnLicence() throws {
        let app = components.first { $0.id == appLicenceId }!
        XCTAssertEqual(app.license, "AGPL-3.0-only WITH AdditionRef-ChordNotepad-Section7")
        let appText = try text(app)
        XCTAssertTrue(appText.contains("GNU AFFERO GENERAL PUBLIC LICENSE"))
        // ADDITIONAL-TERMS.txt must be among the Appropriate Legal Notices (its permission 2(b)).
        XCTAssertTrue(appText.contains("Additional permissions and terms under GNU AGPL version 3 section 7"))
        let logo = components.first { $0.id == "chord-notepad-logo" }!
        XCTAssertTrue(try text(logo).contains("Chord Notepad logos and promotional material"))
        let font = components.first { $0.id == "generaluser-gs" }!
        XCTAssertTrue(try text(font).contains("GeneralUser GS"))
    }

    func testLGPLAndMPLComponentsSayWhereTheirSourceIs() {
        let copyleft = components.filter { $0.license.hasPrefix("LGPL") || $0.license.hasPrefix("MPL") }
        XCTAssertFalse(copyleft.isEmpty)
        for c in copyleft {
            XCTAssertFalse((c.sourceURL ?? "").isEmpty, "\(c.id): sourceUrl")
        }
        // FluidSynth: a separate dynamic framework, built from the pinned source by the repository's script.
        let fluidsynth = components.first { $0.id == "fluidsynth" }!
        XCTAssertEqual(fluidsynth.license, "LGPL-2.1-or-later")
        XCTAssertTrue(fluidsynth.note?.contains("dynamic framework") == true)
        XCTAssertTrue(fluidsynth.note?.contains("packaging/ios/build_fluidsynth.sh") == true)
    }

    func testEveryPythonPackageTheAppShipsHasAnEntryWithThePinnedVersion() throws {
        let requirements = try String(contentsOf: TestPython.repo.appendingPathComponent("android/requirements.txt"),
                                      encoding: .utf8)
        var pins: [String: String] = [:]
        let pin = try NSRegularExpression(pattern: #"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)"#)
        for line in requirements.split(separator: "\n") {
            let code = String(line.split(separator: "#", omittingEmptySubsequences: false).first ?? "")
                .trimmingCharacters(in: .whitespaces)
            let range = NSRange(code.startIndex..., in: code)
            guard let m = pin.firstMatch(in: code, range: range) else { continue }
            let name = String(code[Range(m.range(at: 1), in: code)!]).lowercased().replacingOccurrences(of: "_", with: "-")
            pins[name] = String(code[Range(m.range(at: 2), in: code)!])
        }
        XCTAssertGreaterThanOrEqual(pins.count, 12)
        // What build_python_bundle.py leaves out of the iOS bundle.
        let bundler = try String(contentsOf: TestPython.repo.appendingPathComponent("packaging/ios/build_python_bundle.py"),
                                 encoding: .utf8)
        XCTAssertTrue(bundler.contains(#"LEFT_OUT = {"chardet"}"#), "the packages left out changed")
        pins["chardet"] = nil
        let python = Dictionary(uniqueKeysWithValues: components.filter { $0.group == .python }.map { ($0.id, $0.version ?? "") })
        XCTAssertEqual(python, pins, "packages without an entry, or with another version")
    }

    func testTheListIsGroupedInAFixedOrderAndSortedByName() throws {
        let all = try Licences.entries(data)
        XCTAssertEqual(all.first?.group, .app)
        let order = all.map { LicenceGroup.allCases.firstIndex(of: $0.group)! }
        XCTAssertEqual(order, order.sorted())
        let pythonNames = all.filter { $0.group == .python }.map { $0.name.lowercased() }
        XCTAssertEqual(pythonNames, pythonNames.sorted())
        let sections = Licences.sections(all)
        XCTAssertEqual(sections.map(\.group), [.app, .runtime, .native, .python, .data])
        XCTAssertEqual(sections.map { $0.group.title },
                       ["This app", "Python runtime", "Audio libraries", "Python packages", "Sounds and graphics"])
        XCTAssertEqual(sections.flatMap(\.entries), all)
        // Two texts are shown one after the other.
        let app = all.first { $0.id == appLicenceId }!
        XCTAssertEqual(try Licences.text(of: app, textsDirectory: Self.textsURL)
            .components(separatedBy: Licences.separator).count, 2)
    }

    func testBadDataIsAnError() {
        XCTAssertThrowsError(try Licences.entries(Data(#"{"components": [{"id": "a", "name": "A", "group": "x", "license": "MIT", "texts": []}]}"#.utf8)))
        let twice = #"{"components": [{"id": "a", "name": "A", "group": "app", "license": "MIT", "texts": []},"#
            + #" {"id": "a", "name": "B", "group": "data", "license": "MIT", "texts": []}]}"#
        XCTAssertThrowsError(try Licences.entries(Data(twice.utf8)))
    }

    func testPagesGoBackToWhereTheyCameFrom() {
        XCTAssertEqual(MainRoute.about.parent, MainRoute.none)
        XCTAssertEqual(MainRoute.licences.parent, .about)
        XCTAssertEqual(MainRoute.licence(id: "fluidsynth", fromAbout: false).parent, .licences)
        XCTAssertEqual(MainRoute.licence(id: "fluidsynth", fromAbout: false).licenceId, "fluidsynth")
        XCTAssertNil(MainRoute.about.licenceId)
        // P7: the app's licence opened from About goes back to About.
        let fromAbout = MainRoute.licence(id: appLicenceId, fromAbout: true)
        XCTAssertEqual(fromAbout.licenceId, appLicenceId)
        XCTAssertEqual(fromAbout.parent, .about)
        XCTAssertEqual(MainRoute.settings.parent, MainRoute.none)
        XCTAssertTrue([MainRoute.settings, .about, .licences, fromAbout].allSatisfy(\.isFullPage))
        XCTAssertFalse([MainRoute.none, .menu, .voicing, .identify, .diagnostics].contains(where: \.isFullPage))
    }

    func testAnOpenedSongClosesThePageOverTheEditorSettingsAsksFirst() {
        // P1: a song from Files lands on the song whatever page was open.
        XCTAssertEqual(MainRoute.none.onSongOpened, .stay)
        XCTAssertEqual(MainRoute.settings.onSongOpened, .leaveSettings)
        for route: MainRoute in [.about, .licences, .licence(id: "x", fromAbout: false), .licence(id: "x", fromAbout: true),
                                 .menu, .examples, .voicing, .identify] {
            XCTAssertEqual(route.onSongOpened, .close, "\(route)")
        }
    }

    func testBuildInfoHasAVersionAndNoDate() {
        let info = AboutBuildInfo.from(info: ["CFBundleShortVersionString": "0.6.2", "CFBundleVersion": "123",
                                         "CNGitCommit": "f31fbb5b39345578918245345b85f6a7b03b862d",
                                         "CNBuildDate": "2026-11-24"], debug: false)
        XCTAssertEqual(info, AboutBuildInfo(versionName: "0.6.2", buildNumber: "123", commit: "f31fbb5", buildType: "release"))
        XCTAssertEqual(info.rows.map(\.label), ["Version", "Build type", "Build number", "Commit"])
        XCTAssertFalse(info.rows.contains { $0.value.contains("2026") })
        let dev = AboutBuildInfo.from(info: ["CNGitCommit": ""], debug: true)
        XCTAssertEqual(dev.commit, "unknown")
        XCTAssertEqual(dev.buildType, "debug")
        XCTAssertEqual(AboutBuildInfo.from(info: ["CNGitCommit": "dev"], debug: true).commit, "dev")
        let version = try! String(contentsOf: TestPython.repo.appendingPathComponent("VERSION"), encoding: .utf8)
        XCTAssertNotNil(version.trimmingCharacters(in: .whitespacesAndNewlines)
            .range(of: #"^\d+\.\d+(\.\d+)?$"#, options: .regularExpression))
    }

    func testAboutLinksAreTheFossFlavours() {
        XCTAssertEqual(AboutLinks.source, "https://github.com/chibicitiberiu/chord-notepad")
        let foss = try! String(contentsOf: TestPython.repo.appendingPathComponent(
            "android/app/src/foss/kotlin/com/tibich/chordnotepad/support/SupportBillingFactory.kt"), encoding: .utf8)
        XCTAssertTrue(foss.contains("\"\(AboutLinks.support!)\""))
    }
}

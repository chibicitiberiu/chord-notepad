import Foundation

// About and the open source licences, ported from Android's about/Licences.kt,
// about/BuildInfo.kt and ui/about/. The list is the iOS app's own
// (ios/Licenses/components.json, in Android's format: Android
// keeps its own in its assets too); the core's licence catalog is the desktop
// builds' inventory. The texts are resources/licenses/texts, which the
// "Licences" build phase copies into the app (ios/tools/copy_licences.py).

/// The kinds of component, in the order the list shows them.
public enum LicenceGroup: String, Sendable, CaseIterable {
    case app, runtime, native, python, data, guide

    /// The group's heading.
    public var title: String {
        switch self {
        case .app: return AboutTexts.groupApp
        case .runtime: return AboutTexts.groupRuntime
        case .native: return AboutTexts.groupNative
        case .python: return AboutTexts.groupPython
        case .data: return AboutTexts.groupData
        case .guide: return AboutTexts.groupGuide
        }
    }
}

/// One line of the licences screen.
///
/// `id` is unique and stable (the detail page's route); `license` the
/// licence's short name (an SPDX id where there is one); `copyright` the
/// holders when the text doesn't name them; `url` the project's home;
/// `sourceURL` where the source is, when the licence asks for it to be
/// available; `textFiles` the texts to show (file names without `.txt`);
/// `note` what the component is here for, and anything unusual.
public struct LicenceEntry: Sendable, Equatable, Identifiable {
    public var id: String
    public var name: String
    public var version: String?
    public var group: LicenceGroup
    public var license: String
    public var copyright: String?
    public var url: String?
    public var sourceURL: String?
    public var textFiles: [String]
    public var note: String?

    /// The name and version, as the list's line shows them.
    public var title: String { [name, version].compactMap { $0 }.joined(separator: " ") }
}

public struct LicenceError: Error, CustomStringConvertible, Equatable {
    public let description: String

    init(_ description: String) {
        self.description = description
    }
}

/// Reads and combines the licence data.
public enum Licences {
    /// The licence texts' folder, inside the licence folder.
    public static let texts = "texts"
    /// The list of components.
    public static let components = "components.json"
    /// What separates two texts of one entry.
    public static let separator = "\n\n----------------------------------------\n\n"

    private struct File: Decodable {
        let components: [Component]
    }

    private struct Component: Decodable {
        let id: String
        let name: String
        let group: String
        let license: String
        let texts: [String]
        let version: String?
        let copyright: String?
        let url: String?
        let sourceUrl: String?
        let note: String?
    }

    /// Parses `components.json`; an unknown group is an error in the data file.
    public static func parseComponents(_ data: Data) throws -> [LicenceEntry] {
        let file = try JSONDecoder().decode(File.self, from: data)
        return try file.components.map { c in
            guard let group = LicenceGroup(rawValue: c.group) else {
                throw LicenceError("Unknown licence group '\(c.group)'")
            }
            return LicenceEntry(id: c.id, name: c.name, version: c.version, group: group, license: c.license,
                                copyright: c.copyright, url: c.url, sourceURL: c.sourceUrl, textFiles: c.texts,
                                note: c.note)
        }
    }

    /// The whole list, by group and then name; duplicate ids are an error.
    public static func entries(_ data: Data) throws -> [LicenceEntry] {
        let all = try parseComponents(data)
        var seen = Set<String>()
        let duplicates = Set(all.map(\.id).filter { !seen.insert($0).inserted })
        if !duplicates.isEmpty { throw LicenceError("Duplicate licence ids: \(duplicates.sorted())") }
        let order = LicenceGroup.allCases
        return all.sorted {
            let (a, b) = (order.firstIndex(of: $0.group)!, order.firstIndex(of: $1.group)!)
            return a != b ? a < b : $0.name.lowercased() < $1.name.lowercased()
        }
    }

    /// Loads the list from a licence folder (`components.json`, `texts/`).
    public static func load(from directory: URL) throws -> [LicenceEntry] {
        try entries(Data(contentsOf: directory.appendingPathComponent(components)))
    }

    /// The text to show for `entry`: its licence files, one after another,
    /// from `textsDirectory`.
    public static func text(of entry: LicenceEntry, textsDirectory: URL) throws -> String {
        try entry.textFiles.map { name in
            try String(contentsOf: textsDirectory.appendingPathComponent("\(name).txt"), encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }.joined(separator: separator)
    }

    /// The list's sections: each group with entries, in order.
    public static func sections(_ entries: [LicenceEntry]) -> [(group: LicenceGroup, entries: [LicenceEntry])] {
        LicenceGroup.allCases.compactMap { group in
            let rows = entries.filter { $0.group == group }
            return rows.isEmpty ? nil : (group, rows)
        }
    }
}

/// What About shows about this build (Android's `BuildInfo`). There is no
/// build date, as on Android.
public struct AboutBuildInfo: Sendable, Equatable {
    /// The `VERSION` file's version (`CFBundleShortVersionString`).
    public var versionName: String
    /// The build number (`CFBundleVersion`: CI's run number).
    public var buildNumber: String
    /// The short git commit the build was made from, or `unknown`.
    public var commit: String
    /// `release` or `debug`.
    public var buildType: String

    public init(versionName: String, buildNumber: String, commit: String, buildType: String) {
        self.versionName = versionName
        self.buildNumber = buildNumber
        self.commit = commit
        self.buildType = buildType
    }

    /// From the app's Info.plist (`CNGitCommit` is CI's full hash; shown short).
    public static func from(info: [String: Any], debug: Bool) -> AboutBuildInfo {
        let commit = (info["CNGitCommit"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "unknown"
        return AboutBuildInfo(versionName: info["CFBundleShortVersionString"] as? String ?? "0.0.0",
                         buildNumber: info["CFBundleVersion"] as? String ?? "0",
                         commit: commit.count == 40 ? String(commit.prefix(7)) : commit,
                         buildType: debug ? "debug" : "release")
    }

    /// About's rows: label and value.
    public var rows: [(label: String, value: String)] {
        [(AboutTexts.version, versionName), (AboutTexts.buildType, buildType),
         (AboutTexts.buildNumber, buildNumber), (AboutTexts.commit, commit)]
    }
}

/// The links About opens (only when the user taps one).
public enum AboutLinks {
    /// The project's home.
    public static let source = "https://github.com/chibicitiberiu/chord-notepad"
    /// The donation page Android's FOSS flavour links after the source. The
    /// iOS app shows none: an App Store app may not link to an outside
    /// payment page, and the iOS app's monetization isn't decided
    /// (BACKLOG.md).
    public static let support: String? = nil
}

/// About's and the licences' texts (Android's strings.xml).
public enum AboutTexts {
    public static let title = "About Chord Notepad"
    public static let appName = "Chord Notepad"
    public static let description = "A simple text editor for musicians with chord detection and playback"
    public static let version = "Version"
    public static let buildType = "Build type"
    public static let buildNumber = "Build number"
    public static let commit = "Commit"
    public static let copyright = "© 2025–2026 Tiberiu Chibici"
    public static let license = "GNU AGPL-3.0"
    public static let source = "github.com/chibicitiberiu/chord-notepad"
    public static let warranty = "Free software with ABSOLUTELY NO WARRANTY. You may share and change it under the "
        + "GNU AGPL-3.0 with the additional terms in Open source licences."
    public static let licences = "Open source licences"
    public static let support = "Support development"
    public static let openFailed = "No app can open this link"
    public static let licencesTitle = "Open source licences"
    public static let licencesIntro = "Chord Notepad is free software. It is built from the components below."
    public static let textMissing = "The licence text could not be loaded."
    public static let groupApp = "This app"
    public static let groupRuntime = "Python runtime"
    public static let groupNative = "Audio libraries"
    public static let groupPython = "Python packages"
    public static let groupData = "Sounds and graphics"
    public static let groupGuide = "User guide"
    public static let website = "Website"
    public static let sourceCode = "Source code"
    public static let back = "Back"

    /// `licences_copyright`.
    public static func copyright(_ holders: String) -> String { "Copyright \(holders)" }
}

/// The id of the app's own entry in the licence list (the AGPL text).
public let appLicenceId = "chord-notepad"

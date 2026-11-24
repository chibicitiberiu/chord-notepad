import ChordNotepadKit
import SwiftUI
import UIKit

/// One screen in the catalog: its name, the recorded scenes it is shown with
/// (ios/Fixtures) and how to draw it from a snapshot.
struct CatalogScreen {
    let name: String
    let fixtures: [String]
    let make: @MainActor (SessionSnapshot) -> AnyView

    init<Screen: View>(_ name: String, fixtures: [String],
                       make: @escaping @MainActor (SessionSnapshot) -> Screen) {
        self.name = name
        self.fixtures = fixtures
        self.make = { AnyView(make($0)) }
    }
}

/// Every screen drawn from the recorded scenes, without Python
/// (docs/IOS.md, "Preview catalog"). `#Preview`s use the same fixtures, and
/// CI's CatalogTests render each entry on a phone and a tablet, light and
/// dark, at the default and a large text size.
///
/// Adding a screen is one line in ``screens``.
@MainActor
enum PreviewCatalog {
    static let screens: [CatalogScreen] = [
        CatalogScreen("shell", fixtures: ["quick_start_edit", "empty_song", "play_with_chord_sheet", "errors"]) {
            ShellScreen(snapshot: $0, build: "catalog", scrolls: false)
        },
        CatalogScreen("selftest", fixtures: ["empty_song"]) { _ in
            SelfTestContent(report: .sample, timings: SelfTestReport.sample.timings, running: false, scrolls: false)
        },
    ]

    /// A recorded scene folded into a snapshot (an empty one if it's missing,
    /// so a preview still draws).
    static func snapshot(_ fixture: String) -> SessionSnapshot {
        do {
            return try Fixture(contentsOf: AppPaths.fixtures.appendingPathComponent("\(fixture).json")).snapshot()
        } catch {
            Log.ui.error("Fixture \(fixture, privacy: .public): \(String(describing: error), privacy: .public)")
            return SessionSnapshot()
        }
    }
}

/// The sizes, colour schemes and text sizes the catalog is rendered in.
enum CatalogRenderer {
    struct Device {
        let name: String
        let size: CGSize
        let scale: CGFloat
    }

    /// iPhone 17 and iPad Air 11-inch (M4), in points.
    static let devices = [
        Device(name: "iphone", size: CGSize(width: 402, height: 874), scale: 3),
        Device(name: "ipad", size: CGSize(width: 820, height: 1180), scale: 2),
    ]
    static let schemes: [(String, ColorScheme)] = [("light", .light), ("dark", .dark)]
    static let textSizes: [(String, DynamicTypeSize)] = [("default", .large), ("large", .accessibility2)]

    /// How many images ``renderAll(to:)`` writes.
    @MainActor static var imageCount: Int {
        PreviewCatalog.screens.reduce(0) { $0 + $1.fixtures.count } * devices.count * schemes.count * textSizes.count
    }

    /// Render every entry into `folder` as `<screen>-<fixture>-<device>-<scheme>-<text>.png`.
    @MainActor static func renderAll(to folder: URL) throws -> [URL] {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var written: [URL] = []
        for screen in PreviewCatalog.screens {
            for fixture in screen.fixtures {
                let snapshot = PreviewCatalog.snapshot(fixture)
                for device in devices {
                    for (schemeName, scheme) in schemes {
                        for (textName, textSize) in textSizes {
                            let view = screen.make(snapshot)
                                .frame(width: device.size.width, height: device.size.height)
                                .environment(\.colorScheme, scheme)
                                .environment(\.dynamicTypeSize, textSize)
                            let renderer = ImageRenderer(content: view)
                            renderer.scale = device.scale
                            renderer.proposedSize = ProposedViewSize(device.size)
                            guard let png = renderer.uiImage?.pngData() else {
                                throw CatalogError("\(screen.name)/\(fixture) didn't render")
                            }
                            let url = folder.appendingPathComponent(
                                "\(screen.name)-\(fixture)-\(device.name)-\(schemeName)-\(textName).png")
                            try png.write(to: url)
                            written.append(url)
                        }
                    }
                }
            }
        }
        return written
    }
}

struct CatalogError: Error, CustomStringConvertible {
    let description: String

    init(_ description: String) {
        self.description = description
    }
}

extension SelfTestReport {
    /// A passed report with plausible values, for the catalog.
    static let sample = SelfTestReport(
        date: "2026-11-24T10:00:00Z",
        build: BuildInfo(version: "0.6.2", build: "1", commit: "catalog", date: "2026-11-24"),
        device: "iPhone iOS 26.5",
        timings: LaunchTimings(pythonBoot: 0.42, sessionStart: 3.1, firstText: 3.4),
        offlineRender: Render(ok: true, peak: 9120, frames: 22050, seconds: 0.08, error: nil),
        liveAudio: AudioStatus(session: true, initialized: true, error: nil, soundfont: "GeneralUser-GS.sf2"),
        auditionMessages: [],
        audioCategory: "AVAudioSessionCategoryPlayback",
        audioRoute: ["Speaker: Speaker"],
        sampleRate: 48000,
        ioBufferDuration: 0.0107,
        problems: [])
}

/// Every catalog entry in a list (for Previews; not reachable in the app).
struct CatalogView: View {
    var body: some View {
        NavigationStack {
            List {
                ForEach(PreviewCatalog.screens, id: \.name) { screen in
                    Section(screen.name) {
                        ForEach(screen.fixtures, id: \.self) { fixture in
                            NavigationLink(fixture) {
                                screen.make(PreviewCatalog.snapshot(fixture))
                            }
                        }
                    }
                }
            }
            .navigationTitle("Catalog")
        }
    }
}

#Preview("Catalog") {
    CatalogView()
}

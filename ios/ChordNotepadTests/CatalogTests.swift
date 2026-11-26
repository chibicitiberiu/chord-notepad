import ChordNotepadKit
import SwiftUI
import XCTest

@testable import ChordNotepad

/// Renders every preview catalog entry (ios/Fixtures through the app's
/// screens, no Python) on a phone and a tablet, light and dark, at the
/// default and a large text size, into PNGs CI uploads (docs/IOS.md,
/// "Preview catalog").
///
/// The images go to `CN_CATALOG_DIR` (CI passes it as
/// `TEST_RUNNER_CN_CATALOG_DIR`) and are attached to the result bundle too.
@MainActor
final class CatalogTests: XCTestCase {
    func testEveryCatalogEntryRenders() throws {
        let environment = ProcessInfo.processInfo.environment
        let folder = URL(fileURLWithPath: environment["CN_CATALOG_DIR"]
                         ?? FileManager.default.temporaryDirectory.appendingPathComponent("catalog").path)
        let written = try CatalogRenderer.renderAll(to: folder)
        XCTAssertEqual(written.count, CatalogRenderer.imageCount)
        for url in written {
            let attachment = XCTAttachment(contentsOfFile: url)
            attachment.name = url.lastPathComponent
            attachment.lifetime = .keepAlways
            add(attachment)
            let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
            XCTAssertGreaterThan(size, 10_000, "\(url.lastPathComponent) is nearly empty")
        }
        print("Catalog: \(written.count) images in \(folder.path)")
    }

    /// The system's controls captured both ways the renderer can, on a
    /// phone and a tablet, light and dark, into the catalog folder as
    /// `probe-*.png`, with the safe areas the windows had (`probe.txt`): which
    /// controls a window's layers draw, and which need the render server.
    func testNativeControlsProbe() throws {
        let environment = ProcessInfo.processInfo.environment
        let folder = URL(fileURLWithPath: environment["CN_CATALOG_DIR"]
                         ?? FileManager.default.temporaryDirectory.appendingPathComponent("catalog").path)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var report: [String] = []
        let devices = [CatalogRenderer.devices[0], CatalogRenderer.devices[1]]
        let play = PreviewCatalog.screens.first { $0.name == "play" }
        for device in devices {
            for (schemeName, scheme) in CatalogRenderer.schemes {
                for capture in [CatalogRenderer.Capture.layers, .snapshot] {
                    let method = capture == .layers ? "layers" : "snapshot"
                    for (name, view) in [("controls", AnyView(ControlsProbe())),
                                         ("play", play.map { $0.make(PreviewCatalog.scene("scarborough_piano_roll"), device) }
                                            ?? AnyView(EmptyView()))] {
                        let image = autoreleasepool {
                            CatalogRenderer.render(view, device: device, scheme: scheme, textSize: .large,
                                                   capture: capture)
                        }
                        let insets = CatalogRenderer.lastInsets
                        report.append("\(name)\t\(method)\t\(device.name)\t\(schemeName)\twindow \(insets.window)"
                                      + "\thost \(insets.host)\tblank \(image.map(isBlank) ?? true)")
                        if let png = image?.pngData() {
                            try png.write(to: folder.appendingPathComponent(
                                "probe-\(name)-\(method)-\(device.name)-\(schemeName).png"))
                        }
                    }
                }
            }
        }
        let text = report.joined(separator: "\n")
        print("Probe:\n" + text)
        try text.write(to: folder.appendingPathComponent("probe.txt"), atomically: true, encoding: .utf8)
    }

    func testEveryChordSheetSceneHasABufferAtEachDevicesHeight() throws {
        for screen in PreviewCatalog.screens where ["play", "help_play", "help_play_phone", "split_play"].contains(screen.name) {
            for name in screen.fixtures {
                let fixture = try XCTUnwrap(PreviewCatalog.fixture(name), name)
                guard let state = try fixture.snapshot().chordSheet, state.visible else { continue }
                for device in screen.devices {
                    // The main screen's pane in that window (MainScreen, ChordSheetSplitView, ChordSheetPane).
                    let height = try XCTUnwrap(MainSheetPane.contentHeight(
                        width: Double(device.size.width), height: Double(device.size.height), stored: state.height))
                    XCTAssertNotNil(fixture.chordSheetBuffers[height],
                                    "\(name) has no buffer for \(device.name)'s \(height) pt: make ios-fixtures")
                }
            }
        }
    }

    func testTheChordSheetGlyphsAreInTheApp() throws {
        let glyphs = SheetGlyphImages.shared
        XCTAssertEqual(glyphs.index.baseSizes.count, 7, "chord_sheet/glyphs.json")
        for (asset, size) in glyphs.index.baseSizes {
            let image = try XCTUnwrap(glyphs.image(asset, pixelWidth: 20, pixelHeight: 40, tint: .black), asset)
            XCTAssertEqual(image.width, 20)
            XCTAssertGreaterThan(size.height, 0)
        }
    }

    func testEveryFixtureTheCatalogNamesExists() {
        for screen in PreviewCatalog.screens {
            for fixture in screen.fixtures {
                let url = AppPaths.fixtures.appendingPathComponent("\(fixture).json")
                XCTAssertTrue(FileManager.default.fileExists(atPath: url.path), "\(screen.name): \(fixture)")
            }
        }
    }
}

/// One of each system control the iOS look uses, in a navigation stack.
private struct ControlsProbe: View {
    @State private var on = true
    @State private var off = false
    @State private var segment = 1
    @State private var speed = 0.4
    @State private var count = 2
    @State private var text = "Monospace"
    @State private var key = "C"

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("Word wrap", isOn: $off)
                    Toggle("Show quick start at startup", isOn: $on)
                    Picker("Mode", selection: $segment) {
                        Text("Edit").tag(0)
                        Text("Play").tag(1)
                    }
                    .pickerStyle(.segmented)
                    Picker("Default key", selection: $key) {
                        ForEach(["C", "G", "D"], id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.menu)
                    Stepper("Font size: \(count)", value: $count)
                    TextField("Name", text: $text)
                    Slider(value: $speed)
                } header: {
                    Text("General")
                } footer: {
                    Text("The editor's font. Pinching the text changes its size too.")
                }
                Section("Buttons") {
                    Button("Bordered prominent") {}.buttonStyle(.borderedProminent)
                    Button("Bordered") {}.buttonStyle(.bordered)
                    Label("Settings", systemImage: "gear")
                    ProgressView()
                    RoundedRectangle(cornerRadius: 12).fill(.regularMaterial).frame(height: 40)
                }
            }
            .navigationTitle("Probe")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { } label: { Image(systemName: "chevron.backward") }
                }
                ToolbarItem(placement: .confirmationAction) { Button("Done") {} }
            }
        }
    }
}

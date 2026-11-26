import ChordNotepadKit
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


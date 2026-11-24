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

    func testEveryFixtureTheCatalogNamesExists() {
        for screen in PreviewCatalog.screens {
            for fixture in screen.fixtures {
                let url = AppPaths.fixtures.appendingPathComponent("\(fixture).json")
                XCTAssertTrue(FileManager.default.fileExists(atPath: url.path), "\(screen.name): \(fixture)")
            }
        }
    }
}

import ChordNotepadKit
import SwiftUI
import UIKit
import XCTest

@testable import ChordNotepad

/// Drives a hosted strip's playhead as the session's states do.
@MainActor
private final class StripDriver: ObservableObject {
    @Published var current: Int?
    @Published var cursor: Int?
}

private struct StripHarness: View {
    let sheet: PreparedSheet
    let palette: ChordSheetPalette
    @ObservedObject var driver: StripDriver

    var body: some View {
        ChordSheetStrip(sheet: sheet, palette: palette, currentIndex: driver.current, cursorIndex: driver.cursor,
                        zoomSupported: true, zoom: 1)
    }
}

extension SessionTests {
    /// The strip in a window, live: it follows a song playing chord by chord,
    /// stays put while paused, and ⏮ (the session's one state with no
    /// sounding chord and the playhead on the first) scrolls it back to the
    /// start (S0 issue 7: it stayed near the paused bar).
    func checkTheStripFollowsTheRewind(_ sheet: PreparedSheet, palette: ChordSheetPalette) async throws {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = CGRect(x: 0, y: 0, width: 402, height: 122)
        let driver = StripDriver()
        driver.cursor = 0
        let host = UIHostingController(rootView: StripHarness(sheet: sheet, palette: palette, driver: driver))
        host.view.frame = window.bounds
        window.rootViewController = host
        window.isHidden = false
        defer { window.isHidden = true }
        func settle(_ ms: Int = 250) async { try? await Task.sleep(for: .milliseconds(ms)) }
        await settle(500)
        let scrollView = try XCTUnwrap(Self.firstScrollView(in: host.view), "the strip's scroll view")
        XCTAssertLessThan(scrollView.contentOffset.x, 1, "it opens at the start")

        let chords = Array(Set(sheet.buffer.slots.map(\.chordIndex))).sorted()
        for chord in chords {
            driver.current = chord
            driver.cursor = chord
            await settle(120)
        }
        await settle(800)
        let played = scrollView.contentOffset.x
        XCTAssertGreaterThan(played, 100, "the strip followed the song")
        // Paused: nothing changes. ⏮: no sounding chord, the playhead on the first.
        driver.current = nil
        driver.cursor = chords.first
        await settle(1200)
        XCTAssertLessThan(scrollView.contentOffset.x, 1, "⏮ scrolls back to the start (was \(played))")
    }

    private static func firstScrollView(in view: UIView) -> UIScrollView? {
        if let scroll = view as? UIScrollView { return scroll }
        for child in view.subviews {
            if let found = firstScrollView(in: child) { return found }
        }
        return nil
    }
}

import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `QuickStartModelTest`, case for case (the guide's links against
/// iOS's scheme), plus the guide's files, the startup screen and the launch kind.
final class HelpTests: XCTestCase {
    func testThePagerWalksThePagesAndStopsAtTheEnds() {
        var pager = QuickStartPager(pageCount: 3)
        XCTAssertTrue(pager.isFirst)
        XCTAssertFalse(pager.isLast)
        XCTAssertEqual(pager.previous().current, 0)
        pager = pager.next().next()
        XCTAssertEqual(pager.current, 2)
        XCTAssertTrue(pager.isLast)
        XCTAssertEqual(pager.next().current, 2)
        XCTAssertEqual(pager.previous().current, 1)
    }

    func testAnIndexOutsideTheTourIsClamped() {
        XCTAssertEqual(QuickStartPager(pageCount: 2, index: 9).current, 1)
        XCTAssertEqual(QuickStartPager(pageCount: 2, index: -3).current, 0)
        let one = QuickStartPager(pageCount: 1)
        XCTAssertTrue(one.isFirst && one.isLast)
    }

    private func snippet(_ text: String, _ spans: Span...) -> QuickStartBlock {
        QuickStartBlock(image: nil, kind: "snippet", notation: "american", spans: spans, text: text)
    }

    func testSnippetRunsUseUTF16OffsetsForCodePointSpans() {
        // The emoji is two UTF-16 units but one code point: "C" starts at 2 in Swift's UTF-16, 1 in Python.
        let block = snippet("🎵C Am", Span(end: 2, kind: .chord, message: "", start: 1), Span(end: 5, kind: .chord, message: "", start: 3))
        XCTAssertEqual(snippetRuns(block), [SnippetRun(2, 3, .chord), SnippetRun(4, 6, .chord)])
    }

    func testEmptySpansAreDroppedAndHigherPriorityKindsPaintLast() {
        let block = snippet("{bpm: 90} C",
                            Span(end: 11, kind: .chord, message: "", start: 10),
                            Span(end: 9, kind: .directive, message: "", start: 0),
                            Span(end: 4, kind: .comment, message: "", start: 4),
                            Span(end: 9, kind: .chordInvalid, message: "", start: 0))
        let runs = snippetRuns(block)
        XCTAssertEqual(runs.count, 3)
        // CHORD < CHORD_INVALID < DIRECTIVE in the editor's priority order.
        XCTAssertEqual(runs.map(\.kind), [.chord, .chordInvalid, .directive])
    }

    func testASnippetIsStyledAsTheEditorStylesItsText() {
        let block = snippet("C  Am", Span(end: 1, kind: .chord, message: "", start: 0), Span(end: 5, kind: .chord, message: "", start: 3))
        let palette = EditorPalette.forScheme(dark: false)
        XCTAssertEqual(snippetStyleRuns(block, palette: palette),
                       [StyleRun(0, 1, palette.style(.chord)), StyleRun(3, 5, palette.style(.chord))])
    }

    func testGuideLinksStayInsideTheBundledGuideOrLeaveForTheBrowser() {
        XCTAssertTrue(HelpLinks.isInternal(HelpLinks.startURL))
        XCTAssertTrue(HelpLinks.isInternal("cnhelp://guide/settings.html#voicings"))
        XCTAssertFalse(HelpLinks.isInternal("cnhelp://other/index.html"))
        XCTAssertFalse(HelpLinks.isInternal("https://example.com/cnhelp://guide/index.html"))
        XCTAssertTrue(HelpLinks.isExternal("https://github.com/chibicitiberiu/chord-notepad"))
        XCTAssertTrue(HelpLinks.isExternal("mailto:a@b.c"))
        XCTAssertFalse(HelpLinks.isExternal(HelpLinks.startURL))
        XCTAssertFalse(HelpLinks.isExternal("file:///etc/passwd"))
    }

    func testAGuideURLNamesAFileInsideTheGuideOnly() {
        XCTAssertEqual(HelpLinks.resourcePath(HelpLinks.startURL), "index.html")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/"), "index.html")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/settings.html#voicings"), "settings.html")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/search.html?q=capo"), "search.html")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/_static/css/theme.css"), "_static/css/theme.css")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/_images/a%20b.png"), "_images/a b.png")
        XCTAssertEqual(HelpLinks.resourcePath("cnhelp://guide/./_static//x.js"), "_static/x.js")
        XCTAssertNil(HelpLinks.resourcePath("cnhelp://guide/../Info.plist"))
        XCTAssertNil(HelpLinks.resourcePath("cnhelp://guide/_static/%2E%2E/%2E%2E/Info.plist"))
        XCTAssertNil(HelpLinks.resourcePath("https://guide/index.html"))
    }

    func testGuideFilesGetTheirTypes() {
        XCTAssertEqual(HelpLinks.mimeType("index.html"), "text/html")
        XCTAssertEqual(HelpLinks.mimeType("_static/css/theme.css"), "text/css")
        XCTAssertEqual(HelpLinks.mimeType("_static/searchtools.js"), "text/javascript")
        XCTAssertEqual(HelpLinks.mimeType("_images/drawer.PNG"), "image/png")
        XCTAssertEqual(HelpLinks.mimeType("_static/css/fonts/lato-normal.woff2"), "font/woff2")
        XCTAssertEqual(HelpLinks.mimeType("searchindex"), "application/octet-stream")
        XCTAssertTrue(HelpLinks.isText("text/css"))
        XCTAssertFalse(HelpLinks.isText("image/png"))
    }

    func testTheCheckboxFollowsThePickThenTheSettingsThenTheTour() {
        let tour = QuickStartContent(pages: [], showOnStartup: false)
        XCTAssertFalse(quickStartShowsAtStartup(picked: nil, settings: nil, content: tour))
        XCTAssertTrue(quickStartShowsAtStartup(picked: nil, settings: nil, content: nil))
        XCTAssertTrue(quickStartShowsAtStartup(picked: true, settings: nil, content: tour))
    }

    func testTheLaunchKind() {
        XCTAssertEqual(LaunchKind.of(startScreen: nil, openingDocument: false), .direct)
        XCTAssertEqual(LaunchKind.of(startScreen: nil, openingDocument: true), .document)
        XCTAssertEqual(LaunchKind.of(startScreen: "menu", openingDocument: false), .restore)
        XCTAssertEqual(LaunchKind.of(startScreen: "quickstart", openingDocument: false), .direct)
    }

    func testDaysAreLocalISODates() {
        let date = Date(timeIntervalSince1970: 1_793_000_000)  // 2026-10-26 07:33 UTC
        XCTAssertEqual(isoDay(date, timeZone: TimeZone(identifier: "UTC")!), "2026-10-26")
        XCTAssertEqual(isoDay(date, timeZone: TimeZone(identifier: "Pacific/Kiritimati")!), "2026-10-26")
        XCTAssertEqual(isoDay(date, timeZone: TimeZone(identifier: "America/Adak")!), "2026-10-25")
    }

    func testTheStartupScreenIsForgottenOnceDismissed() {
        var snapshot = SessionSnapshot()
        snapshot.startupDismissed()
        XCTAssertNil(snapshot.startup)
        snapshot.apply(.startupState(StartupState(screen: .quickStart)))
        XCTAssertEqual(snapshot.startup?.screen, .quickStart)
        snapshot.startupDismissed()
        XCTAssertEqual(snapshot.startup?.screen, .noScreen)
        let tour = QuickStartContent(pages: [QuickStartPage(blocks: [], title: "Welcome")], showOnStartup: true)
        snapshot.apply(.quickStartContent(tour))
        XCTAssertEqual(snapshot.quickStart, tour)
    }
}

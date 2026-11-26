import Foundation

// ☰ › Quick start (Android's ui/help/QuickStartModel.kt and QuickStartScreen.kt):
// the session's tour (`request_quick_start` → `QuickStartContent`), one page
// at a time, and whether it opens at startup (`app_started` → `StartupState`).

/// Which page of the Quick Start tour is showing. ``next()`` and
/// ``previous()`` stop at the ends, as the desktop dialog's buttons do.
public struct QuickStartPager: Sendable, Equatable {
    /// Number of pages (at least 1).
    public let pageCount: Int
    /// The page asked for, 0-based (``current`` clamps it).
    public let index: Int

    public init(pageCount: Int, index: Int = 0) {
        precondition(pageCount >= 1, "a tour has pages")
        self.pageCount = pageCount
        self.index = index
    }

    /// The page, clamped into the tour.
    public var current: Int { min(max(index, 0), pageCount - 1) }
    /// The first page (Previous is disabled).
    public var isFirst: Bool { current == 0 }
    /// The last page (Next becomes Done).
    public var isLast: Bool { current == pageCount - 1 }

    /// The pager one page on (the same on the last page).
    public func next() -> QuickStartPager { QuickStartPager(pageCount: pageCount, index: min(current + 1, pageCount - 1)) }
    /// The pager one page back (the same on the first page).
    public func previous() -> QuickStartPager { QuickStartPager(pageCount: pageCount, index: max(current - 1, 0)) }
}

/// A highlighted run of a snippet in UTF-16 units.
public struct SnippetRun: Sendable, Hashable {
    public var start: Int
    public var end: Int
    public var kind: SpanKind

    public init(_ start: Int, _ end: Int, _ kind: SpanKind) {
        self.start = start
        self.end = end
        self.kind = kind
    }
}

/// The highlight runs of a Quick Start snippet `block`: the session's spans
/// (code points) converted to UTF-16 offsets, empty or out-of-range ones
/// dropped, and ordered so that a higher-priority kind comes later and so
/// wins on overlap, as in the editor (``spanPriority``).
public func snippetRuns(_ block: QuickStartBlock) -> [SnippetRun] {
    let mapper = OffsetMapper(block.text)
    let rank = Dictionary(uniqueKeysWithValues: spanPriority.enumerated().map { ($1, $0) })
    let runs = block.spans
        .map { SnippetRun(mapper.toUTF16($0.start), mapper.toUTF16($0.end), $0.kind) }
        .filter { $0.start < $0.end }
    // A stable sort by priority (Kotlin's sortedBy is stable; Swift's sort isn't).
    return runs.enumerated()
        .sorted { (rank[$0.element.kind] ?? 0, $0.offset) < (rank[$1.element.kind] ?? 0, $1.offset) }
        .map(\.element)
}

/// A snippet's runs styled as the editor styles its text (the same
/// ``styleRuns(spans:playing:length:palette:)``), for drawing.
public func snippetStyleRuns(_ block: QuickStartBlock, palette: EditorPalette) -> [StyleRun] {
    styleRuns(spans: snippetRuns(block).map { PaintedSpan($0.start, $0.end, $0.kind) }, playing: nil,
              length: block.text.utf16.count, palette: palette)
}

/// The sizes a tour snippet is drawn at, in points: the editor's 15, and the
/// smallest it shrinks to so its longest line fits the box.
public enum SnippetFont {
    public static let preferred = 15.0
    public static let smallest = 11.0
}

/// The font size that fits `text`'s longest line in `width` points, in a
/// monospaced font whose characters are `advance` × the size wide: the
/// preferred size when it fits, else smaller in half-point steps, never below
/// ``SnippetFont/smallest`` (wider than that, the box scrolls sideways). Lines
/// never wrap: a wrapped chord line no longer sits over its lyric.
public func snippetFontSize(_ text: String, width: Double, advance: Double) -> Double {
    let columns = text.split(separator: "\n", omittingEmptySubsequences: false).map(\.count).max() ?? 0
    guard columns > 0, advance > 0, width > 0 else { return SnippetFont.preferred }
    let fits = (width / (Double(columns) * advance) * 2).rounded(.down) / 2
    return min(SnippetFont.preferred, max(SnippetFont.smallest, fits))
}

/// The "Show at startup" checkbox: the value the user just picked until the
/// session's settings echo it, then the settings' value, else the tour's own
/// (Android's `QuickStartRoute`).
public func quickStartShowsAtStartup(picked: Bool?, settings: SettingsState?, content: QuickStartContent?) -> Bool {
    picked ?? settings?.values.showQuickStartOnStartup ?? content?.showOnStartup ?? true
}

/// The tour's texts (Android's `strings_help.xml`).
public enum QuickStartTexts {
    public static let title = "Quick Start"
    public static let showAtStartup = "Show at startup"
    public static let previous = "Previous"
    public static let next = "Next"
    public static let done = "Done"
    public static let close = "Close the tour"

    /// "2 of 7".
    public static func pageOf(_ page: Int, _ count: Int) -> String { "\(page) of \(count)" }
}

/// How the app came up, sent as `app_started`'s `launch_kind`: the session
/// decides the startup screen from the first one (Android's `LaunchKind`).
public enum LaunchKind: String, Sendable {
    /// From the Home screen or the app switcher: may show Quick Start.
    case direct
    /// To open a song (from Files or another app): nothing over it.
    case document
    /// Anything else (CI's `-CNScreen` launches): nothing over it.
    case restore

    /// The kind of this launch: songs from Files waiting for the session make
    /// it a document launch; a `-CNScreen` hook (other than `quickstart`) a
    /// restore, so CI's screenshots aren't covered by the tour.
    public static func of(startScreen: String?, openingDocument: Bool) -> LaunchKind {
        if openingDocument { return .document }
        if let startScreen, startScreen != "quickstart" { return .restore }
        return .direct
    }
}

/// `date`'s local calendar day as ISO (`2026-10-30`), as Android's `LocalDates.iso`.
public func isoDay(_ date: Date, timeZone: TimeZone = .current) -> String {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = timeZone
    let parts = calendar.dateComponents([.year, .month, .day], from: date)
    return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
}

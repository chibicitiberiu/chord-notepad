import Foundation

// The song editor's look (Android's ui/editor/EditorStyles.kt and the
// editor's part of ui/theme/AppTheme.kt): the Tk desktop editor's colours in
// the light theme, readable variants of the same hues in the dark one, and
// the desktop's tag priority where spans overlap. Colours are RGBA values
// (``SheetColor``); the app turns them into UIColor and SwiftUI colours.

/// The editor's and the Edit ribbon's colours in one theme.
public struct EditorPalette: Sendable, Equatable {
    public var dark: Bool
    /// The text's background (Android's `surface`).
    public var background: SheetColor
    /// Plain text (`editorText`).
    public var text: SheetColor
    /// Valid chords (Tk "blue").
    public var chord: SheetColor
    /// Invalid chords (Tk "gray").
    public var chordInvalid: SheetColor
    /// `COLOR_DIRECTIVE_VALID`.
    public var directive: SheetColor
    /// Invalid directives (Tk "red").
    public var directiveInvalid: SheetColor
    /// Comments (Tk "gray").
    public var comment: SheetColor
    /// The sounding chord's background (Tk "yellow").
    public var playing: SheetColor
    /// The caret and the selection's tint (the primary colour).
    public var primary: SheetColor
    /// The Edit ribbon's background (`surface2`).
    public var ribbon: SheetColor
    /// Dividers and the notation control's border.
    public var line: SheetColor
    /// The ribbon's captions.
    public var ribbonText: SheetColor
    /// The unselected notation segment's text.
    public var muted: SheetColor
    /// The selected notation segment's background.
    public var primarySoft: SheetColor
    /// The unselected notation segment's background.
    public var surfaceLow: SheetColor

    public static let light = EditorPalette(
        dark: false,
        background: SheetColor(argb: 0xFFFB_FBFF),
        text: SheetColor(argb: 0xFF00_0000),
        chord: SheetColor(argb: 0xFF00_00FF),
        chordInvalid: SheetColor(argb: 0xFFBE_BEBE),
        directive: SheetColor(argb: 0xFF8B_4789),
        directiveInvalid: SheetColor(argb: 0xFFFF_0000),
        comment: SheetColor(argb: 0xFFBE_BEBE),
        playing: SheetColor(argb: 0xFFFF_FF00),
        primary: SheetColor(argb: 0xFF3F_51B5),
        ribbon: SheetColor(argb: 0xFFEC_EEF5),
        line: SheetColor(argb: 0xFFD5_D8E2),
        ribbonText: SheetColor(argb: 0xFF1A_1B20),
        muted: SheetColor(argb: 0xFF5C_5F6B),
        primarySoft: SheetColor(argb: 0xFFDD_E1FF),
        surfaceLow: SheetColor(argb: 0xFFF4_F5FA))

    public static let dark = EditorPalette(
        dark: true,
        background: SheetColor(argb: 0xFF12_1318),
        text: SheetColor(argb: 0xFFE3_E4EB),
        chord: SheetColor(argb: 0xFF8A_B4F8),
        chordInvalid: SheetColor(argb: 0xFF7F_848F),
        directive: SheetColor(argb: 0xFFD3_9BE0),
        directiveInvalid: SheetColor(argb: 0xFFFF_8A80),
        comment: SheetColor(argb: 0xFF7F_848F),
        playing: SheetColor(argb: 0xFF5A_4F00),
        primary: SheetColor(argb: 0xFFB6_C3FF),
        ribbon: SheetColor(argb: 0xFF20_2229),
        line: SheetColor(argb: 0xFF35_3842),
        ribbonText: SheetColor(argb: 0xFFE3_E4EB),
        muted: SheetColor(argb: 0xFFA3_A7B3),
        primarySoft: SheetColor(argb: 0xFF2E_3A72),
        surfaceLow: SheetColor(argb: 0xFF19_1B21))

    public static func forScheme(dark: Bool) -> EditorPalette { dark ? .dark : .light }

    /// How strongly a redundant directive is painted: the directive colour,
    /// faded (the desktop blends 45 %).
    public static let redundantAlpha = 0.45
    /// The empty editor's placeholder: the text colour, faded.
    public static let placeholderAlpha = 0.45
    /// The selection's background in the catalog's drawing: the primary
    /// colour at this alpha (UITextView draws the system's own).
    public static let selectionAlpha = 0.25

    /// The style of `kind`. Fields left nil keep what a lower-priority span
    /// set (a comment over a chord keeps its underline, as in Tk and Compose).
    public func style(_ kind: SpanKind) -> RunStyle {
        switch kind {
        case .chord: return RunStyle(color: chord, underline: true)
        case .chordInvalid: return RunStyle(color: chordInvalid, underline: true)
        case .directive: return RunStyle(color: directive, underline: false)
        case .directiveInvalid: return RunStyle(color: directiveInvalid, underline: true)
        case .directiveRedundant:
            return RunStyle(color: directive.withAlpha(Self.redundantAlpha), underline: false)
        case .comment: return RunStyle(color: comment)
        }
    }

    /// The sounding chord, painted over every other span.
    public var playingStyle: RunStyle { RunStyle(color: text, underline: true, background: playing) }
}

/// What a span sets on its text; nil fields leave the text (or a span under
/// it) as it is.
public struct RunStyle: Sendable, Hashable {
    public var color: SheetColor?
    public var underline: Bool?
    public var background: SheetColor?

    public init(color: SheetColor? = nil, underline: Bool? = nil, background: SheetColor? = nil) {
        self.color = color
        self.underline = underline
        self.background = background
    }

    /// `other` painted over this style.
    public func overlaid(by other: RunStyle) -> RunStyle {
        RunStyle(color: other.color ?? color, underline: other.underline ?? underline,
                 background: other.background ?? background)
    }

    /// Whether the style sets anything.
    public var isEmpty: Bool { color == nil && underline == nil && background == nil }
}

/// A styled part of the text: `[start, end)` in UTF-16 units.
public struct StyleRun: Sendable, Hashable {
    public var start: Int
    public var end: Int
    public var style: RunStyle

    public init(_ start: Int, _ end: Int, _ style: RunStyle) {
        self.start = start
        self.end = end
        self.style = style
    }
}

/// The span kinds in the desktop's tag priority: a later kind wins where
/// spans overlap (Tk raises later-created tags).
public let spanPriority: [SpanKind] = [
    .chord, .chordInvalid, .directive, .directiveInvalid, .directiveRedundant, .comment,
]

/// The painted spans and the sounding chord as runs that don't overlap, in
/// order, each with every style that covers it merged in priority order
/// (the playing chord last). Text outside every run has the plain style.
/// One function serves the UITextView (attributes on its text storage) and
/// the preview catalog (a SwiftUI `AttributedString`), so both look alike.
public func styleRuns(spans: [PaintedSpan], playing: UTF16Range?, length: Int,
                      palette: EditorPalette) -> [StyleRun] {
    var layers: [(UTF16Range, RunStyle)] = []
    for kind in spanPriority {
        let style = palette.style(kind)
        for span in spans where span.kind == kind {
            let r = UTF16Range(span.start, span.end).clamped(to: length)
            if !r.isEmpty { layers.append((r, style)) }
        }
    }
    if let playing {
        let r = playing.clamped(to: length)
        if !r.isEmpty { layers.append((r, palette.playingStyle)) }
    }
    if layers.isEmpty { return [] }
    var bounds = Set<Int>()
    for (r, _) in layers {
        bounds.insert(r.start)
        bounds.insert(r.end)
    }
    let points = bounds.sorted()
    var styles = [RunStyle?](repeating: nil, count: points.count - 1)
    for (r, style) in layers {
        var i = lowerBound(points, r.start)
        while i < styles.count && points[i] < r.end {
            styles[i] = (styles[i] ?? RunStyle()).overlaid(by: style)
            i += 1
        }
    }
    var runs: [StyleRun] = []
    for (i, style) in styles.enumerated() {
        guard let style, !style.isEmpty else { continue }
        if let last = runs.last, last.end == points[i], last.style == style {
            runs[runs.count - 1].end = points[i + 1]
        } else {
            runs.append(StyleRun(points[i], points[i + 1], style))
        }
    }
    return runs
}

/// The index of the first element of sorted `values` that is >= `value`.
func lowerBound(_ values: [Int], _ value: Int) -> Int {
    var lo = 0
    var hi = values.count
    while lo < hi {
        let mid = (lo + hi) >> 1
        if values[mid] < value { lo = mid + 1 } else { hi = mid }
    }
    return lo
}

/// The three families the editor offers (Android's, docs/ANDROID.md settings
/// visibility): on iOS the system's monospaced, default and serif designs.
public enum EditorFontKind: String, Sendable, CaseIterable {
    case monospace, sans, serif
}

/// The editor's font: the configured desktop family and size as iOS draws them.
public enum EditorFont {
    /// The desktop's default size, before `EditorState` arrives.
    public static let defaultPoints = 11
    /// Smallest and largest size (`MIN_FONT_SIZE`/`MAX_FONT_SIZE`; the session clamps too).
    public static let minPoints = 6
    public static let maxPoints = 72

    /// The family for a configured desktop font family. `TkFixedFont` and
    /// monospaced names map to monospace, sans serif names (and Tk's default
    /// UI font) to sans, serif names to serif; anything unknown keeps the
    /// desktop default, monospace.
    public static func kind(forFamily family: String) -> EditorFontKind {
        let f = family.lowercased()
        func any(_ names: [String]) -> Bool { names.contains { f.contains($0) } }
        if f.trimmingCharacters(in: .whitespaces).isEmpty { return .monospace }
        if any(["fixed", "mono", "courier", "consol", "menlo", "typewriter", "code"]) { return .monospace }
        if any(["sans", "arial", "helvetica", "verdana", "tahoma", "segoe", "ubuntu", "cantarell", "roboto",
                "tkdefaultfont", "tktextfont", "noto sans", "calibri"]) { return .sans }
        if any(["serif", "times", "georgia", "garamond", "palatino", "cambria", "book"]) { return .serif }
        return .monospace
    }

    /// The configured family to send for `kind`: `current` when it already
    /// maps to `kind`, else `TkFixedFont`, `Sans` or `Serif`.
    public static func configFamily(for kind: EditorFontKind, current: String) -> String {
        if Self.kind(forFamily: current) == kind { return current }
        switch kind {
        case .monospace: return "TkFixedFont"
        case .sans: return "Sans"
        case .serif: return "Serif"
        }
    }

    /// A desktop font size (points; Tk draws them at 96 DPI, 4/3 px per pt)
    /// in iOS points at the default text size, so the editor reads like the
    /// desktop's and Android's. The app scales it with Dynamic Type.
    public static func pointSize(_ points: Int) -> Double { Double(points) * 4 / 3 }

    /// The size a pinch of `zoom` (1: none) from `basePoints` asks for.
    public static func pinchSize(_ basePoints: Int, zoom: Double) -> Int {
        min(max(Int((Double(basePoints) * zoom).rounded()), minPoints), maxPoints)
    }
}

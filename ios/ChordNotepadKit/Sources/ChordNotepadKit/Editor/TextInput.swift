import Foundation

// What the editor does to text coming in and to the way it wraps: paste
// normalisation (Android's PasteNormalization.kt), chord-safe wrapping
// (ChordWrap.kt) and where the text scrolls to keep something in view
// (TextScroll.kt).

/// U+2060 WORD JOINER: no line break on either side, and it draws nothing.
public let wordJoiner: Unicode.Scalar = "\u{2060}"

/// The desktop's paste normalisation (`utils/text_normalization.py`,
/// `normalize_song_text`): CRLF and lone CR become LF, non-breaking spaces
/// become spaces, zero-width spaces, word joiners and BOMs are dropped. Keep
/// the two in step: `TextInputTests` lists the cases of
/// `tests/test_paste_normalization.py`.
public func normalizeSongText(_ text: String) -> String {
    var out = String.UnicodeScalarView()
    let scalars = Array(text.unicodeScalars)
    var i = 0
    while i < scalars.count {
        let c = scalars[i]
        switch c {
        case "\r":
            out.append("\n")
            if i + 1 < scalars.count && scalars[i + 1] == "\n" { i += 1 }
        case "\u{00A0}":
            out.append(" ")
        case "\u{200B}", "\u{FEFF}", wordJoiner:
            break
        default:
            out.append(c)
        }
        i += 1
    }
    return String(out)
}

/// Whether ``normalizeSongText(_:)`` would change `text`.
public func needsNormalizing(_ text: String) -> Bool {
    text.unicodeScalars.contains { ["\r", "\u{00A0}", "\u{200B}", "\u{FEFF}", wordJoiner].contains($0) }
}

/// Where a soft-wrapped line must not break so that a chord stays whole
/// (Android's L7: `D/F#` wrapped as `D/` and `F#`): the UTF-16 offsets inside
/// a chord span right after a `/`, `-` or `+`, which line breakers treat as
/// break opportunities. Sorted, no duplicates.
///
/// The app's TextKit layout manager refuses a break before these offsets, so
/// the song never holds a joiner; the catalog's SwiftUI text, which has no
/// such hook, draws ``JoinedText`` instead.
public func chordJoinPoints(_ text: String, spans: [PaintedSpan]) -> [Int] {
    let units = Array(text.utf16)
    var points = Set<Int>()
    for span in spans where span.kind == .chord || span.kind == .chordInvalid {
        let end = min(span.end, units.count)
        guard span.start + 1 < end else { continue }
        for i in (span.start + 1)..<end where breaksAfter.contains(units[i - 1]) {
            points.insert(i)
        }
    }
    return points.sorted()
}

/// `/`, `-` and `+` in UTF-16.
private let breaksAfter: Set<UInt16> = [0x2F, 0x2D, 0x2B]

/// Where the text gets join points: inside chords when it wraps, nowhere when
/// it doesn't (unwrapped, nothing can split a chord).
public func joinPoints(_ text: String, spans: [PaintedSpan], wordWrap: Bool) -> [Int] {
    wordWrap ? chordJoinPoints(text, spans: spans) : []
}

/// Whether a line may break before UTF-16 offset `offset`, given sorted `points`.
public func mayBreak(before offset: Int, points: [Int]) -> Bool {
    let i = lowerBound(points, offset)
    return !(i < points.count && points[i] == offset)
}

/// The song's offsets in the text as drawn with a ``wordJoiner`` before each
/// of `points` (``chordJoinPoints(_:spans:)``).
public struct JoinedText: Sendable, Equatable {
    public let points: [Int]

    public init(_ points: [Int]) {
        self.points = points
    }

    public var isEmpty: Bool { points.isEmpty }

    /// `text` as drawn.
    public func display(_ text: String) -> String {
        if points.isEmpty { return text }
        let units = Array(text.utf16)
        var out: [UInt16] = []
        out.reserveCapacity(units.count + points.count)
        var from = 0
        for p in points {
            if p > units.count { break }
            out.append(contentsOf: units[from..<p])
            out.append(UInt16(wordJoiner.value))
            from = p
        }
        out.append(contentsOf: units[from...])
        return String(decoding: out, as: UTF16.self)
    }

    /// Where the song's `offset` is in the drawn text: shifted by the joiners
    /// at or before it, so a character keeps its own place.
    public func toDisplay(_ offset: Int) -> Int {
        if points.isEmpty { return offset }
        var lo = 0
        var hi = points.count
        while lo < hi {
            let mid = (lo + hi) >> 1
            if points[mid] <= offset { lo = mid + 1 } else { hi = mid }
        }
        return offset + lo
    }
}

/// `text` without the word joiners a drawing of it holds.
public func withoutJoiners(_ text: String) -> String {
    String(String.UnicodeScalarView(text.unicodeScalars.filter { $0 != wordJoiner }))
}

// Where the song text scrolls to keep something in view, on either axis.
// Unwrapped (the default), the text scrolls sideways as well as up and down,
// so the sounding chord and the caret are followed horizontally too.
// Positions are in the scrolled content's points; a scroll `value` shows
// `[value, value + viewport)`.
public enum TextScroll {
    /// Where to scroll so the sounding chord at `[start, end)` shows: nil
    /// while it shows already, else with the chord a third of the way into
    /// the view (the desktop's `see`). An unmeasured view (`viewport` 0)
    /// doesn't scroll.
    public static func followChord(start: Double, end: Double, value: Double, viewport: Double,
                                   max: Double) -> Double? {
        if viewport <= 0 { return nil }
        if start >= value && end <= value + viewport { return nil }
        return Swift.min(Swift.max((start.rounded() - (viewport / 3).rounded(.down)), 0), Swift.max(max, 0))
    }

    /// Where to scroll, as little as needed, so the caret at `[start, end)`
    /// shows with `margin` around it: nil while it shows already.
    public static func followCursor(start: Double, end: Double, value: Double, viewport: Double, max: Double,
                                    margin: Double) -> Double? {
        if viewport <= 0 { return nil }
        let upper = Swift.max(max, 0)
        let target: Double
        if start - margin < value {
            target = (start - margin).rounded(.down)
        } else if end + margin > value + viewport {
            target = (end + margin).rounded(.up) - viewport
        } else {
            return nil
        }
        let clamped = Swift.min(Swift.max(target, 0), upper)
        return clamped == value ? nil : clamped
    }
}

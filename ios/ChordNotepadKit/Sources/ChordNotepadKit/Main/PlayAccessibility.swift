import Foundation

// VoiceOver in the Play tab: the frozen text as one element per chord, so a
// chord can be reached and played on its own (S0 issue 8: each line was one
// static text, and activating it hit the line's middle chord), and the other
// text on each line as plain text between them. Offsets are UTF-16, as the
// text view's.

/// One VoiceOver element of Play mode's text.
public struct PlayAccessibilityItem: Sendable, Equatable {
    public enum Kind: Sendable, Equatable {
        /// A chord: activating it does what a tap on it does (``PlayTap/onChord(_:)``).
        case chord
        /// Other text on a line (a lyric, a directive, a comment), read as it is.
        case text
    }

    public var kind: Kind
    public var start: Int
    public var end: Int
    /// What VoiceOver says: the chord as written, or the text without its surrounding blanks.
    public var label: String

    public init(_ kind: Kind, _ start: Int, _ end: Int, _ label: String) {
        self.kind = kind
        self.start = start
        self.end = end
        self.label = label
    }
}

/// The elements of `text` in reading order: line by line, each of
/// ``playableChords(_:)`` on its own, and every other non-blank run of a line
/// (before, between and after its chords) as text. Blank lines have none.
public func playAccessibilityItems(text: String, spans: [PaintedSpan]) -> [PlayAccessibilityItem] {
    let units = Array(text.utf16)
    let chords = playableChords(spans).filter { $0.end <= units.count }
    var items: [PlayAccessibilityItem] = []
    var next = 0  // the first chord not placed yet

    func addText(_ from: Int, _ to: Int) {
        var start = from
        var end = to
        while start < end, isBlank(units[start]) { start += 1 }
        while end > start, isBlank(units[end - 1]) { end -= 1 }
        if start < end { items.append(PlayAccessibilityItem(.text, start, end, string(units, start, end))) }
    }

    var lineStart = 0
    while lineStart <= units.count {
        var lineEnd = lineStart
        while lineEnd < units.count, units[lineEnd] != newline { lineEnd += 1 }
        var cursor = lineStart
        while next < chords.count, chords[next].start < lineEnd {
            let chord = chords[next]
            next += 1
            guard chord.start >= cursor else { continue }  // overlapping spans: the first wins
            addText(cursor, chord.start)
            items.append(PlayAccessibilityItem(.chord, chord.start, chord.end, string(units, chord.start, chord.end)))
            cursor = chord.end
        }
        addText(min(cursor, lineEnd), lineEnd)
        lineStart = lineEnd + 1
    }
    return items
}

private let newline = UInt16(0x0A)

private func isBlank(_ unit: UInt16) -> Bool {
    unit == 0x20 || unit == 0x09 || unit == 0x0D
}

private func string(_ units: [UInt16], _ start: Int, _ end: Int) -> String {
    String(decoding: units[start..<end], as: UTF16.self)
}

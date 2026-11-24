import Foundation

// The song editor's text arithmetic in UTF-16 units, the units of `NSRange`,
// `NSString` and `UITextView` (a port of Android's ui/editor/SpanShift.kt and
// text/TextEdits.kt). The session counts code points; ``OffsetMapper`` is the
// only conversion between the two.

/// A range `[start, end)` of UTF-16 units, `start <= end` (an `NSRange` as a
/// value the kit can test). A caret is an empty range.
public struct UTF16Range: Sendable, Hashable, CustomStringConvertible {
    public var start: Int
    public var end: Int

    /// The range between `a` and `b`, in either order.
    public init(_ a: Int, _ b: Int) {
        start = min(a, b)
        end = max(a, b)
    }

    /// A caret at `offset`.
    public init(caret offset: Int) {
        self.init(offset, offset)
    }

    public var length: Int { end - start }
    public var isEmpty: Bool { start == end }

    /// The range clamped to a text of `length` units.
    public func clamped(to length: Int) -> UTF16Range {
        UTF16Range(min(max(start, 0), length), min(max(end, 0), length))
    }

    public var description: String { "[\(start), \(end))" }
}

/// A highlight as the editor paints it: `[start, end)` in UTF-16 units of the
/// editor's current text.
public struct PaintedSpan: Sendable, Hashable {
    public var start: Int
    public var end: Int
    public var kind: SpanKind

    public init(_ start: Int, _ end: Int, _ kind: SpanKind) {
        self.start = start
        self.end = end
        self.kind = kind
    }
}

/// One edit as a single replaced range (UTF-16): the old text's
/// `[start, oldEnd)` became the new text's `[start, newEnd)`.
public struct TextChange: Sendable, Hashable {
    public var start: Int
    public var oldEnd: Int
    public var newEnd: Int

    public init(start: Int, oldEnd: Int, newEnd: Int) {
        self.start = start
        self.oldEnd = oldEnd
        self.newEnd = newEnd
    }

    /// How much later everything after the change sits now.
    public var delta: Int { newEnd - oldEnd }
}

/// The smallest single change that turns `old` into `new` (common prefix and
/// suffix), or nil when they are equal. Never splits a surrogate pair.
public func diffTexts(_ old: String, _ new: String) -> TextChange? {
    diffUnits(Array(old.utf16), Array(new.utf16))
}

/// ``diffTexts(_:_:)`` on UTF-16 code units.
public func diffUnits(_ old: [UInt16], _ new: [UInt16]) -> TextChange? {
    let minLength = min(old.count, new.count)
    var prefix = 0
    while prefix < minLength && old[prefix] == new[prefix] { prefix += 1 }
    if prefix == old.count && prefix == new.count { return nil }
    if prefix > 0 && UTF16.isLeadSurrogate(old[prefix - 1]) { prefix -= 1 }
    var suffix = 0
    while suffix < minLength - prefix && old[old.count - 1 - suffix] == new[new.count - 1 - suffix] { suffix += 1 }
    if suffix > 0 && UTF16.isTrailSurrogate(old[old.count - suffix]) { suffix -= 1 }
    return TextChange(start: prefix, oldEnd: old.count - suffix, newEnd: new.count - suffix)
}

extension Array where Element == PaintedSpan {
    /// The spans moved along with an edit, the way Tk text tags move: text
    /// after the change shifts, text typed at a span's edge stays outside it,
    /// text typed inside a span joins it, and a span whose text was removed
    /// disappears. Keeps the old highlighting roughly right until the
    /// session's next `HighlightState` replaces it.
    public func shifted(by change: TextChange) -> [PaintedSpan] {
        if isEmpty { return self }
        func startOf(_ x: Int) -> Int {
            if x < change.start { return x }
            if x >= change.oldEnd { return x + change.delta }
            return change.newEnd  // its first characters were replaced
        }
        func endOf(_ x: Int) -> Int {
            if x <= change.start { return x }
            if x >= change.oldEnd { return x + change.delta }
            return change.start  // its last characters were replaced
        }
        return compactMap { span in
            let start = startOf(span.start)
            let end = endOf(span.end)
            return end > start ? PaintedSpan(start, end, span.kind) : nil
        }
    }
}

/// A `TextEdited` in UTF-16 units of the text it applies to: replace
/// `[start, end)` with `replacement`, then select `selection`.
public struct UTF16Edit: Sendable, Hashable {
    public var start: Int
    public var end: Int
    public var replacement: String
    /// The caret in the new text.
    public var cursor: Int
    /// Where the selection starts in the new text when the edit selects
    /// (`TextEdited.anchor`); nil: a caret.
    public var anchor: Int?

    /// The selection after the edit.
    public var selection: UTF16Range { UTF16Range(anchor ?? cursor, cursor) }
}

extension TextEdited {
    /// This edit's code-point offsets converted for `text`, the view's text
    /// before the edit. Out-of-range offsets are clamped. The cursor and
    /// anchor are offsets into the new text: before the edit the old text's
    /// mapping holds, inside it the replacement's, after it the old text's
    /// shifted by the change in length.
    public func utf16(in text: String) -> UTF16Edit {
        let mapper = OffsetMapper(text)
        let startCP = min(max(start, 0), mapper.codePointLength)
        let endCP = min(max(end, startCP), mapper.codePointLength)
        let start16 = mapper.toUTF16(startCP)
        let end16 = mapper.toUTF16(endCP)
        let scalars = Array(replacement.unicodeScalars)
        func newOffset(_ cp: Int) -> Int {
            if cp <= startCP { return mapper.toUTF16(max(cp, 0)) }
            if cp <= startCP + scalars.count {
                return start16 + scalars[0..<(cp - startCP)].reduce(0) { $0 + UTF16.width($1) }
            }
            let oldCP = cp - scalars.count + (endCP - startCP)
            return mapper.toUTF16(oldCP) - (end16 - start16) + replacement.utf16.count
        }
        let newLength = mapper.utf16Length - (end16 - start16) + replacement.utf16.count
        func clamp(_ x: Int) -> Int { min(max(x, 0), newLength) }
        return UTF16Edit(start: start16, end: end16, replacement: replacement, cursor: clamp(newOffset(cursor)),
                         anchor: anchor.map { clamp(newOffset($0)) })
    }
}

extension Span {
    /// This span in UTF-16 units of the text `mapper` was built for (clamped to it).
    public func utf16Range(_ mapper: OffsetMapper) -> UTF16Range {
        let s = mapper.toUTF16(start)
        return UTF16Range(s, max(s, mapper.toUTF16(end)))
    }
}

/// UTF-16 helpers on `String`.
enum UTF16Text {
    /// `text` with `range` (UTF-16, clamped) replaced by `replacement`.
    static func replacing(_ text: String, _ range: UTF16Range, with replacement: String) -> String {
        var units = Array(text.utf16)
        let r = range.clamped(to: units.count)
        units.replaceSubrange(r.start..<r.end, with: Array(replacement.utf16))
        return String(decoding: units, as: UTF16.self)
    }

    /// The UTF-16 units `range` of `text` (clamped) as a string.
    static func substring(_ text: String, _ range: UTF16Range) -> String {
        let units = Array(text.utf16)
        let r = range.clamped(to: units.count)
        return String(decoding: units[r.start..<r.end], as: UTF16.self)
    }
}

/// Converts between the session's offsets (Unicode code points) and UTF-16
/// offsets (`NSString`, `NSRange`, `UITextView`) for one version of a text.
/// The only place in the app that does this conversion (a port of Android's
/// `text/OffsetMapper.kt`).
///
/// Text without supplementary characters (no surrogate pairs; nearly every
/// song) maps one to one and costs nothing. Otherwise the mapper keeps the
/// UTF-16 start of each pair and converts with a binary search.
///
/// A lone surrogate counts as one code point, as in Java and in Python (a
/// Swift `String` can't hold one, but `NSString` can, so ``init(utf16:)``
/// takes code units). Offsets outside the text are clamped to it; a UTF-16
/// offset in the middle of a pair maps to the code point the pair starts.
public struct OffsetMapper: Sendable, Equatable {
    /// Length of the text in UTF-16 units.
    public let utf16Length: Int
    // UTF-16 index of each surrogate pair's high half, ascending.
    private let pairStarts: [Int]

    /// A mapper for `text` as it is now (rebuild it after every change).
    public init(_ text: String) {
        self.init(utf16: text.utf16)
    }

    /// A mapper for a text given as UTF-16 code units.
    public init<Units: Collection>(utf16 units: Units) where Units.Element == UInt16 {
        var starts: [Int] = []
        var index = 0
        var previousHigh = false
        for unit in units {
            if previousHigh && OffsetMapper.isLowSurrogate(unit) {
                starts.append(index - 1)
                previousHigh = false
            } else {
                previousHigh = OffsetMapper.isHighSurrogate(unit)
            }
            index += 1
        }
        utf16Length = index
        pairStarts = starts
    }

    /// Length of the text in code points.
    public var codePointLength: Int { utf16Length - pairStarts.count }

    /// True when both offset systems agree for this text.
    public var isIdentity: Bool { pairStarts.isEmpty }

    /// The UTF-16 offset of code point `codePoint`.
    public func toUTF16(_ codePoint: Int) -> Int {
        let cp = min(max(codePoint, 0), codePointLength)
        if isIdentity { return cp }
        // Pair i sits at code point pairStarts[i] - i; count pairs before cp.
        var lo = 0
        var hi = pairStarts.count
        while lo < hi {
            let mid = (lo + hi) >> 1
            if pairStarts[mid] - mid < cp { lo = mid + 1 } else { hi = mid }
        }
        return cp + lo
    }

    /// The code-point offset of UTF-16 offset `utf16`.
    public func toCodePoint(_ utf16: Int) -> Int {
        let u = min(max(utf16, 0), utf16Length)
        if isIdentity { return u }
        // Each pair starting before u counts one code point fewer. That also
        // holds when u is mid-pair: it maps to the pair's own code point.
        var lo = 0
        var hi = pairStarts.count
        while lo < hi {
            let mid = (lo + hi) >> 1
            if pairStarts[mid] < u { lo = mid + 1 } else { hi = mid }
        }
        return u - lo
    }

    private static func isHighSurrogate(_ unit: UInt16) -> Bool { unit & 0xFC00 == 0xD800 }
    private static func isLowSurrogate(_ unit: UInt16) -> Bool { unit & 0xFC00 == 0xDC00 }
}

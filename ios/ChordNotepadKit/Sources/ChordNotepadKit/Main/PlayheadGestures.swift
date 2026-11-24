import Foundation

// Play mode's touch rules (Android's ui/play/PlayheadGestures.kt), as plain
// geometry: a tap on a chord moves the playhead there and plays it, a tap
// elsewhere moves it to the nearest chord (only while nothing plays), and a
// drag that starts on the playhead marker scrubs it chord by chord. Offsets
// are UTF-16, positions in the text's own points.

/// Where one chord sits in the text's layout: its UTF-16 range and the box
/// from its first to its last character on its line.
public struct ChordBox: Sendable, Equatable, Hashable {
    public var start: Int
    public var end: Int
    public var left: Double
    public var top: Double
    public var right: Double
    public var bottom: Double

    public init(_ start: Int, _ end: Int, left: Double, top: Double, right: Double, bottom: Double) {
        self.start = start
        self.end = end
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    }

    /// Whether (`x`, `y`) is inside the box, grown by `slop` on every side.
    public func contains(_ x: Double, _ y: Double, slop: Double = 0) -> Bool {
        x >= left - slop && x <= right + slop && y >= top - slop && y <= bottom + slop
    }
}

/// What a tap in Play mode does.
public enum PlayTap: Sendable, Equatable {
    /// The tap landed on a chord: move the playhead there and play it (`tap_chord_at`).
    case onChord(Int)
    /// The tap missed every chord: move the playhead to the nearest one (`set_playhead`).
    case nearest(Int)

    /// The chord's UTF-16 start either way.
    public var start: Int {
        switch self {
        case .onChord(let start), .nearest(let start): return start
        }
    }
}

/// Play mode's sizes, in points.
public enum PlayTouch {
    /// The playhead marker's grab strip, centred on it.
    public static let markerGrabWidth = 24.0
    /// A tap this close to a chord counts as on it.
    public static let chordSlop = 8.0
}

/// The chords the playhead can stop at: the valid chord spans, in text order.
public func playableChords(_ spans: [PaintedSpan]) -> [PaintedSpan] {
    spans.filter { $0.kind == .chord && $0.end > $0.start }.sorted { $0.start < $1.start }
}

/// The chord nearest to (`x`, `y`), preferring the same line: the distance is
/// the vertical gap × 4 plus the horizontal gap (zero inside a box). Nil
/// when there are no chords.
public func nearestChord(_ boxes: [ChordBox], _ x: Double, _ y: Double) -> ChordBox? {
    var best: ChordBox?
    var bestDistance = Double.infinity
    for box in boxes {
        let dy = y < box.top ? box.top - y : (y > box.bottom ? y - box.bottom : 0)
        let dx = x < box.left ? box.left - x : (x > box.right ? x - box.right : 0)
        let distance = dy * 4 + dx
        if distance < bestDistance {
            bestDistance = distance
            best = box
        }
    }
    return best
}

/// What a tap at (`x`, `y`) does: ``PlayTap/onChord(_:)`` when it lands on a
/// chord (within `slop`; where two grown boxes overlap, the nearer chord),
/// else ``PlayTap/nearest(_:)`` when `nearestOnMiss` (false while a song
/// plays, so a stray tap doesn't jump playback); nil without chords or for a
/// miss that does nothing.
public func resolveTap(_ boxes: [ChordBox], _ x: Double, _ y: Double, slop: Double,
                       nearestOnMiss: Bool = true) -> PlayTap? {
    if let hit = boxes.first(where: { $0.contains(x, y) })
        ?? nearestChord(boxes.filter { $0.contains(x, y, slop: slop) }, x, y) {
        return .onChord(hit.start)
    }
    guard nearestOnMiss else { return nil }
    return nearestChord(boxes, x, y).map { .nearest($0.start) }
}

/// Whether a touch at (`x`, `y`) grabs the playhead marker drawn before
/// `marker`: a strip `grabWidth` wide centred on the chord's left edge, from
/// `grabWidth` / 2 above the line (the marker's triangle) to its bottom.
public func grabsMarker(_ marker: ChordBox?, _ x: Double, _ y: Double, grabWidth: Double) -> Bool {
    guard let marker else { return false }
    return markerGrabBox(marker, grabWidth: grabWidth).contains(x, y)
}

/// The strip ``grabsMarker(_:_:_:grabWidth:)`` answers for, as a box.
public func markerGrabBox(_ marker: ChordBox, grabWidth: Double) -> ChordBox {
    let half = grabWidth / 2
    return ChordBox(marker.start, marker.end, left: marker.left - half, top: marker.top - half,
                    right: marker.left + half, bottom: marker.bottom + half / 2)
}

/// The chord a scrub at (`x`, `y`) moves the playhead to, or nil when it stays
/// on `current` (the start of the chord it's on now).
public func scrubTarget(_ boxes: [ChordBox], current: Int?, _ x: Double, _ y: Double) -> Int? {
    guard let start = nearestChord(boxes, x, y)?.start, start != current else { return nil }
    return start
}

/// The chord the playhead marker sits before: the playable chord that holds
/// `playhead` (UTF-16), else the first one after it, else none.
public func markerChord(_ chords: [PaintedSpan], playhead: Int?) -> PaintedSpan? {
    guard let playhead else { return nil }
    return chords.first { playhead >= $0.start && playhead < $0.end } ?? chords.first { $0.start >= playhead }
}

/// The directives a long-press explains in Play mode: the invalid (red) and
/// the redundant (faded) ones, in text order.
public func explainableDirectives(_ spans: [PaintedSpan]) -> [PaintedSpan] {
    spans.filter { ($0.kind == .directiveInvalid || $0.kind == .directiveRedundant) && $0.end > $0.start }
        .sorted { $0.start < $1.start }
}

/// The explainable directive under (`x`, `y`) (within `slop`), or nil.
public func explainableAt(_ boxes: [ChordBox], _ x: Double, _ y: Double, slop: Double) -> ChordBox? {
    boxes.first { $0.contains(x, y) } ?? boxes.first { $0.contains(x, y, slop: slop) }
}

/// The playhead marker before a chord (Android's `drawMarker`): a bar in the
/// primary colour the line's height just left of the chord, and a small
/// triangle pointing down onto its top. Points in the text's coordinates.
public struct PlayheadMarker: Sendable, Equatable {
    /// The bar: x, y, width, height (rounded ends: radius width / 2).
    public var bar: (x: Double, y: Double, width: Double, height: Double)
    /// The triangle's three corners.
    public var triangle: [(x: Double, y: Double)]

    public static let barWidth = 3.0
    public static let triangleHalfWidth = 5.5
    public static let triangleHeight = 7.0

    public init(before box: ChordBox) {
        let x = box.left - Self.barWidth - 0.5
        bar = (x, box.top, Self.barWidth, box.bottom - box.top)
        let cx = x + Self.barWidth / 2
        let top = box.top - Self.triangleHeight + 1
        triangle = [(cx - Self.triangleHalfWidth, top), (cx + Self.triangleHalfWidth, top), (cx, box.top + 1)]
    }

    public static func == (a: PlayheadMarker, b: PlayheadMarker) -> Bool {
        a.bar == b.bar && a.triangle.elementsEqual(b.triangle) { $0 == $1 }
    }
}

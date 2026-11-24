import Foundation

/// A pinch on the text in progress (Android's `pinchToZoomFont`): from the
/// size when two fingers came down, each new whole size goes to the session
/// as a step (`step_font_size`), so the session keeps (and saves) the size as
/// it does for Command-= and Settings. The model's size isn't read again
/// until the pinch ends: the session's `EditorState` comes back behind the
/// fingers.
public struct FontPinch: Sendable, Equatable {
    /// The size the pinch started from (nil: no pinch).
    public private(set) var base: Int?
    /// The size the steps sent so far add up to.
    public private(set) var sent = 0

    public init() {}

    /// Two fingers came down on a text of `points`.
    public mutating func began(points: Int) {
        base = points
        sent = points
    }

    /// The pinch's scale since it began (1: none): the step to send, or nil.
    public mutating func changed(scale: Double) -> Int? {
        guard let base, scale.isFinite, scale > 0 else { return nil }
        let target = EditorFont.pinchSize(base, zoom: scale)
        guard target != sent else { return nil }
        let step = target - sent
        sent = target
        return step
    }

    /// The fingers lifted (or the pinch was cancelled): the steps sent stay.
    public mutating func ended() {
        base = nil
    }
}

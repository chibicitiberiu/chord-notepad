import Foundation

// Pure layout and interaction math for the chord sheet strip, ported from
// Android's ui/chordsheet/ChordSheetGeometry.kt (and tested case for case).
// Everything is in content points (1 Tk px = 1 pt) unless a name says px.

extension SheetAnchor {
    /// Top-left corner of a `width` × `height` box whose anchor point is at
    /// (`x`, `y`), the way Tk places text and images.
    public func topLeft(x: Double, y: Double, width: Double, height: Double) -> (x: Double, y: Double) {
        (x - fx * width, y - fy * height)
    }
}

/// Following the playhead: the desktop's auto-scroll rule
/// (`ChordSheetViewModel.scroll_target`).
public enum ChordSheetScroll {
    /// Where the desktop parks the playhead after a snap (fraction of the viewport).
    public static let snapTo = 0.25
    /// Past this fraction of the viewport the playhead triggers a forward snap.
    public static let trigger = 0.70
    /// Smaller scroll changes are ignored.
    public static let epsilon = 0.5

    /// While the playhead sits between 25 % and 70 % of the viewport nothing
    /// moves; otherwise snap so it lands at 25 %, clamped to the content.
    ///
    /// - Returns: The new scroll offset (content x at the viewport's left
    ///   edge), or nil to leave the view alone.
    public static func target(playheadX: Double, viewportWidth: Double, currentScroll: Double,
                              contentWidth: Double) -> Double? {
        guard viewportWidth > 0 else { return nil }
        let relative = playheadX - currentScroll
        let low = snapTo * viewportWidth
        let high = trigger * viewportWidth
        if relative >= low && relative <= high { return nil }
        let maxScroll = max(contentWidth - viewportWidth, 0)
        let target = min(max(playheadX - low, 0), maxScroll)
        return abs(target - currentScroll) < epsilon ? nil : target
    }

    /// The target that keeps chord `index`'s slot centre in view, or nil
    /// (no such slot, or no need to move).
    public static func target(forChord index: Int?, in buffer: SheetBuffer, viewportWidth: Double,
                              currentScroll: Double) -> Double? {
        guard let index, let slot = buffer.slot(forChord: index) else { return nil }
        return target(playheadX: Double(slot.x) + Double(slot.width) / 2, viewportWidth: viewportWidth,
                      currentScroll: currentScroll, contentWidth: Double(buffer.contentWidth))
    }

    /// The scroll offset that keeps content under viewport x `anchorX` in
    /// place when the content width changes from `oldWidth` to `newWidth`
    /// (a zoom), clamped to the new content.
    public static func rescale(_ scroll: Double, anchorX: Double, oldWidth: Double, newWidth: Double,
                               viewportWidth: Double) -> Double {
        let maxScroll = max(newWidth - viewportWidth, 0)
        guard oldWidth > 0 else { return min(max(scroll, 0), maxScroll) }
        return min(max((scroll + anchorX) * (newWidth / oldWidth) - anchorX, 0), maxScroll)
    }

    /// The largest scroll offset for `contentWidth` in a `viewportWidth` viewport.
    public static func maxScroll(contentWidth: Double, viewportWidth: Double) -> Double {
        max(contentWidth - viewportWidth, 0)
    }

    /// Where the strip scrolls when a new buffer replaces `previous`, so the
    /// same music stays in view (Android's `ChordSheetStrip`): a zoom keeps
    /// the content under `focusX` (the pinch's focus, or the viewport's
    /// middle) in place, another view keeps the same fraction of the song,
    /// anything else (an edit, a height change) keeps the offset. Clamped.
    public static func afterNewBuffer(_ buffer: SheetBuffer, previous: SheetBuffer?, scroll: Double,
                                      focusX: Double?, viewportWidth: Double) -> Double {
        let newWidth = Double(buffer.contentWidth)
        let maxScroll = maxScroll(contentWidth: newWidth, viewportWidth: viewportWidth)
        guard let previous else { return min(max(scroll, 0), maxScroll) }
        let oldWidth = Double(previous.contentWidth)
        if previous.viewId == buffer.viewId && previous.zoom != buffer.zoom {
            return rescale(scroll, anchorX: focusX ?? viewportWidth / 2, oldWidth: oldWidth, newWidth: newWidth,
                           viewportWidth: viewportWidth)
        }
        if previous.viewId != buffer.viewId && oldWidth > 0 {
            return min(max(scroll / oldWidth * newWidth, 0), maxScroll)
        }
        return min(max(scroll, 0), maxScroll)
    }
}

/// Zooming by pinch: the desktop's zoom steps (`chord_sheet_viewmodel`).
public enum ChordSheetZoom {
    /// The zoom factor per +/- click (`_ZOOM_STEP`).
    public static let step = 1.2
    /// The desktop's zoom bounds.
    public static let minimum = 0.5
    public static let maximum = 2.5

    /// The number of zoom steps (each ×``step``) closest to a pinch's
    /// `scale`, limited to the steps that still change `currentZoom` within
    /// ``minimum``...``maximum``. Positive zooms in.
    public static func steps(forScale scale: Double, currentZoom: Double) -> Int {
        guard scale > 0, scale.isFinite else { return 0 }
        // Kotlin's roundToInt: halves round up.
        let raw = Int((log(scale) / log(step) + 0.5).rounded(.down))
        let upRoom = stepsUntil(maximum / currentZoom)
        let downRoom = stepsUntil(currentZoom / minimum)
        return min(max(raw, -downRoom), upRoom)
    }

    /// ``steps(forScale:currentZoom:)`` for a view that zooms; 0 (a pinch
    /// does nothing) where the core says it doesn't (`zoom_supported`).
    public static func pinchSteps(zoomSupported: Bool, scale: Double, currentZoom: Double) -> Int {
        zoomSupported ? steps(forScale: scale, currentZoom: currentZoom) : 0
    }

    /// Steps of ``step`` needed to cover `ratio` (the last one may be clamped).
    private static func stepsUntil(_ ratio: Double) -> Int {
        ratio <= 1 + 1e-6 ? 0 : Int((log(ratio) / log(step) - 1e-6).rounded(.up))
    }
}

extension SheetOpList {
    /// The right edge each text op may paint up to: the next text op's x (to
    /// the right) minus 2 pt, or +∞; +∞ for other ops. For the marker lane:
    /// the system font measures wider than the desktop font the lane
    /// estimated its label widths for (Android's `laneClipRights`).
    public func laneClipRights() -> [Double] {
        var xs: [Double] = []
        for op in ops {
            if case .text(let x, _, _, _, _, _, _, _) = op { xs.append(Double(x)) }
        }
        xs.sort()
        return ops.map { op in
            guard case .text(let x, _, _, _, _, _, _, _) = op else { return .infinity }
            let floor = Double(x) + 0.5
            guard let next = xs.first(where: { $0 > floor }) else { return .infinity }
            return next - 2
        }
    }
}

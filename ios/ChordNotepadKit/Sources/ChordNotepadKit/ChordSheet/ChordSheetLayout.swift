import Foundation

// The chord sheet's place on screen: the resizable split under the text
// (Android's ChordSheetSplit.kt), the pane's fixed parts (ChordSheetPane.kt)
// and when the strip follows the playhead. Points throughout (dp on Android).

/// The split between the text and the chord sheet below it.
public enum ChordSheetSplit {
    /// The smallest chord sheet the handle allows (header and a usable strip).
    public static let minimumHeight = 120.0
    /// The largest share of the window height the chord sheet may take.
    public static let maximumScreenFraction = 0.6
    /// The text keeps at least this much height, whatever the stored height.
    public static let minimumEditorHeight = 96.0
    /// Below this height the sheet is hidden instead (a phone in landscape).
    public static let minimumShownHeight = 80.0
    /// What sits between the text and the sheet: the handle (14) and 2 pt
    /// for rounding. The player is below the split, outside `available`.
    public static let reservedBelow = 16.0
    /// The height the session starts with (`constants.DEFAULT_CHORD_SHEET_HEIGHT`).
    public static let defaultHeight = 160
    /// A tablet's share of the window for a sheet still at ``defaultHeight``.
    public static let tabletDefaultFraction = 0.35
    /// The handle's height.
    public static let handleHeight = 14.0

    /// The height to aim for: the `stored` one, except that a sheet still at
    /// the phone-sized default takes ``tabletDefaultFraction`` of a tablet's
    /// window (a 160 pt strip under 1100 pt of mostly empty text looks lost).
    /// Once dragged, the stored height is the user's and is kept.
    public static func wantedHeight(stored: Int, windowWidth: Double, windowHeight: Double) -> Double {
        let tablet = min(windowWidth, windowHeight) >= 600
        if tablet && stored == defaultHeight {
            return max(Double(stored), windowHeight * tabletDefaultFraction)
        }
        return Double(stored)
    }

    /// The heights a drag may give the sheet with `available` points for the
    /// text and the sheet, in a `windowHeight` window.
    public static func dragRange(available: Double, windowHeight: Double) -> ClosedRange<Double> {
        let cap = min(windowHeight * maximumScreenFraction, available - minimumEditorHeight - reservedBelow)
        return min(minimumHeight, cap)...max(cap, min(minimumHeight, cap))
    }

    /// The sheet's height, or nil when there's no room for it (the text then
    /// keeps the screen).
    ///
    /// - Parameters:
    ///   - wanted: The height to aim for (``wantedHeight(stored:windowWidth:windowHeight:)``, or a drag's).
    ///   - available: The height left for the text and the sheet.
    ///   - windowHeight: The window's full height.
    public static func height(wanted: Double, available: Double, windowHeight: Double) -> Double? {
        let cap = min(windowHeight * maximumScreenFraction, available - minimumEditorHeight - reservedBelow)
        guard cap >= minimumShownHeight else { return nil }
        return min(max(wanted, min(minimumHeight, cap)), cap)
    }
}

/// The pane's fixed parts around the strip.
public enum ChordSheetPaneMetrics {
    /// The view tabs and zoom buttons.
    public static let headerHeight = 32.0
    /// The progress bar under the header.
    public static let progressHeight = 2.0
    /// The strip's inset from the pane's sides and bottom.
    public static let stripInset = 4.0
    /// The marker lane's height until the first buffer says otherwise (`marker_lane.LANE_HEIGHT`).
    public static let defaultLaneHeight = 20.0

    /// The strip's height in a pane `paneHeight` tall.
    public static func stripHeight(paneHeight: Double) -> Double {
        max(paneHeight - headerHeight - progressHeight - stripInset, 0)
    }

    /// The content height a buffer is fetched for: the strip without the
    /// marker lane, whole points (what `chord_sheet_buffer(height)` takes).
    public static func contentHeight(stripHeight: Double, laneHeight: Double = defaultLaneHeight) -> Int {
        max(Int(stripHeight - laneHeight), 0)
    }
}

/// When the strip scrolls to the playhead (Android's `ChordSheetStrip`): the
/// chord sounding whenever it, the sheet or the viewport changes; the
/// playhead's chord while nothing plays only when it moves (a tapped chord,
/// ⏮, a scrub), so a zoom or a scroll by hand stays put, and when the
/// first sheet appears.
public struct PlayheadFollower: Sendable, Equatable {
    private var currentIndex: Int?
    private var cursorIndex: Int?
    private var sheetID: Int?
    private var viewportWidth: Double?

    public init() {}

    /// Note what the strip shows now.
    ///
    /// - Returns: The chord to bring into view, or nil.
    public mutating func update(currentIndex: Int?, cursorIndex: Int?, sheetID: Int?,
                                viewportWidth: Double) -> Int? {
        defer {
            self.currentIndex = currentIndex
            self.cursorIndex = cursorIndex
            self.sheetID = sheetID
            self.viewportWidth = viewportWidth
        }
        if let currentIndex, currentIndex != self.currentIndex || sheetID != self.sheetID
            || viewportWidth != self.viewportWidth {
            return currentIndex
        }
        let sheetAppeared = self.sheetID == nil && sheetID != nil
        if currentIndex == nil, cursorIndex != self.cursorIndex || sheetAppeared {
            return cursorIndex
        }
        return nil
    }
}

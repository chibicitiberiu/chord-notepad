import Foundation

// The main screen's layout rules (Android's ui/main/ScreenLayout.kt), as plain
// functions of the window size in points, so they're tested on Linux.

/// The main screen's fixed sizes, in points (Android's dp).
public enum MainMetrics {
    /// The app bar's height, and the Edit ribbon's (`BAR_HEIGHT_DP`).
    public static let barHeight = 48.0
    /// The divider under the header.
    public static let dividerHeight = 1.0
    /// Below this smallest width the device is a phone (Android's sw600dp line).
    public static let phoneMaxSmallestWidth = 600.0
    /// With the keyboard up, the header collapses when less than this much
    /// height is left for the text.
    public static let minTextRoom = 170.0
    /// The player's height (divider, pill, buttons, status line).
    public static let playerHeight = 110.0
    /// The landscape column's drag handle, between the text and the column.
    public static let sideHandleWidth = 14.0
    /// The compact player's buttons in a row: six 38 pt side buttons, the
    /// 48 pt play button and 10 pt of padding on each side.
    public static let compactPlayerWidth = 6 * 38.0 + 48 + 2 * 10
    /// Slack over ``compactPlayerWidth`` for rounding.
    public static let compactPlayerSlack = 8.0
    /// The landscape chord sheet column's share of the width: bounds and default.
    public static let sideFractionMin = 0.3
    public static let sideFractionMax = 0.7
    public static let sideFractionDefault = 0.5
}

/// How the main screen is arranged for one window size, mode and chord sheet
/// setting.
public struct ScreenLayout: Sendable, Equatable {
    /// A phone (smallest width under 600 pt).
    public var phone: Bool
    public var landscape: Bool
    /// Phone landscape in Edit: the title, the tabs and the ribbon share one line.
    public var oneLineHeader: Bool
    /// Play mode with the chord sheet shown, below the text.
    public var sheetBelow: Bool
    /// Play mode in landscape with the chord sheet shown: text left, sheet and player right.
    public var sideBySide: Bool

    /// The player's small buttons (the narrow right-hand column).
    public var compactPlayer: Bool { sideBySide }

    /// The layout of a `width` × `height` window.
    public static func of(width: Double, height: Double, mode: AppMode, sheetVisible: Bool) -> ScreenLayout {
        let phone = min(width, height) < MainMetrics.phoneMaxSmallestWidth
        let landscape = width > height
        let sheetOn = mode == .play && sheetVisible
        return ScreenLayout(phone: phone, landscape: landscape,
                            oneLineHeader: phone && landscape && mode == .edit,
                            sheetBelow: sheetOn && !landscape, sideBySide: sheetOn && landscape)
    }

    /// The header's height above the text (the app bar, the ribbon in Edit
    /// unless it shares the bar's line, and the divider).
    public func headerHeight(mode: AppMode) -> Double {
        let rows = oneLineHeader || mode == .play ? 1.0 : 2.0
        return rows * MainMetrics.barHeight + MainMetrics.dividerHeight
    }
}

/// The title's widest in the one-line header of a window `width` wide (phone
/// landscape Edit): a fifth of the line, 96–200 pt, so the name, its • and
/// Rename stay there next to the ribbon.
public func oneLineTitleMaxWidth(_ width: Double) -> Double {
    min(max(width * 0.2, 96), 200)
}

/// Whether the header (app bar and ribbon) collapses so only the text shows:
/// in Edit mode with the keyboard up, when the text would get less than
/// ``MainMetrics/minTextRoom``. `textRoom` is the height the text has with the
/// header shown.
public func collapseHeader(mode: AppMode, keyboardVisible: Bool, textRoom: Double) -> Bool {
    mode == .edit && keyboardVisible && textRoom < MainMetrics.minTextRoom
}

/// The least share of a side-by-side row `rowWidth` wide the chord sheet
/// column may take: 30 %, or more when the compact player needs it for all
/// its buttons. The column gets its share of the row without the handle.
public func minSideFraction(_ rowWidth: Double) -> Double {
    let room = rowWidth - MainMetrics.sideHandleWidth
    if room <= 0 { return MainMetrics.sideFractionMin }
    return max(MainMetrics.sideFractionMin, (MainMetrics.compactPlayerWidth + MainMetrics.compactPlayerSlack) / room)
}

/// The landscape chord sheet column's share of the width, kept within `min`
/// (30 %, or ``minSideFraction(_:)``) and 70 % (or `min` when that's more).
public func clampSideFraction(_ fraction: Double, min lower: Double = MainMetrics.sideFractionMin) -> Double {
    if fraction.isNaN { return max(MainMetrics.sideFractionDefault, lower) }
    return Swift.min(Swift.max(fraction, lower), Swift.max(lower, MainMetrics.sideFractionMax))
}

/// The column's share after dragging its handle to `handleX` in a row
/// `rowWidth` wide (the column is right of the handle).
public func sideFractionAt(handleX: Double, rowWidth: Double) -> Double {
    rowWidth <= 0 ? MainMetrics.sideFractionDefault : clampSideFraction((rowWidth - handleX) / rowWidth)
}

/// Where the chord sheet's pane goes and how tall it is, for the main screen
/// in Play mode in a `width` × `height` window with the sheet shown: below the
/// text (the split's height for the stored one) or in the landscape column
/// (the window less the app bar and the compact player). The catalog's
/// recorded buffers and the screen both use this.
public enum MainSheetPane {
    /// The pane's height, or nil when the sheet isn't shown there.
    public static func height(width: Double, height: Double, stored: Int) -> Double? {
        let layout = ScreenLayout.of(width: width, height: height, mode: .play, sheetVisible: true)
        let header = layout.headerHeight(mode: .play)
        if layout.sideBySide {
            return height - header - MainMetrics.playerHeight
        }
        let available = height - header - MainMetrics.playerHeight
        let wanted = ChordSheetSplit.wantedHeight(stored: stored, windowWidth: width, windowHeight: height)
        return ChordSheetSplit.height(wanted: wanted, available: available, windowHeight: height)
    }

    /// The strip's content height (what a buffer is packed for) in that pane.
    public static func contentHeight(width: Double, height: Double, stored: Int) -> Int? {
        self.height(width: width, height: height, stored: stored).map {
            ChordSheetPaneMetrics.contentHeight(stripHeight: ChordSheetPaneMetrics.stripHeight(paneHeight: $0))
        }
    }
}

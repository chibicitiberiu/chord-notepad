package com.tibich.chordnotepad.ui.main

// The main screen's layout rules (docs/design/android-ui-spec.md and the
// agreed mockup), as plain functions of the window size, so they're tested
// without a device.

/** The app bar's height, and the Edit ribbon's. */
const val BAR_HEIGHT_DP = 48f

/** Below this smallest width the device is a phone (Android's sw600dp tablet line). */
const val PHONE_MAX_SMALLEST_WIDTH_DP = 600f

/**
 * With the keyboard up, the header collapses when less than this much height
 * is left for the text.
 */
const val MIN_TEXT_ROOM_DP = 170f

/** The landscape chord sheet column's width: share of the screen, bounds and default. */
const val SIDE_FRACTION_MIN = 0.3f
const val SIDE_FRACTION_MAX = 0.7f
const val SIDE_FRACTION_DEFAULT = 0.5f

/** How the main screen is arranged for one window size, mode and chord sheet setting. */
data class ScreenLayout(
    /** A phone (smallest width under 600 dp). */
    val phone: Boolean,
    val landscape: Boolean,
    /** Phone landscape in Edit: the tabs and the ribbon share one line, the title is hidden. */
    val oneLineHeader: Boolean,
    /** Play mode with the chord sheet shown, below the text. */
    val sheetBelow: Boolean,
    /** Play mode in landscape with the chord sheet shown: text left, sheet and player right. */
    val sideBySide: Boolean,
) {
    /** The player's small buttons (the narrow right-hand column). */
    val compactPlayer: Boolean get() = sideBySide

    companion object {
        /** The layout of a [widthDp] × [heightDp] window. */
        fun of(widthDp: Float, heightDp: Float, mode: AppMode, sheetVisible: Boolean): ScreenLayout {
            val phone = minOf(widthDp, heightDp) < PHONE_MAX_SMALLEST_WIDTH_DP
            val landscape = widthDp > heightDp
            val sheetOn = mode == AppMode.PLAY && sheetVisible
            return ScreenLayout(
                phone = phone,
                landscape = landscape,
                oneLineHeader = phone && landscape && mode == AppMode.EDIT,
                sheetBelow = sheetOn && !landscape,
                sideBySide = sheetOn && landscape,
            )
        }
    }
}

/**
 * Whether the header (app bar and ribbon) collapses so only the text shows:
 * in Edit mode with the keyboard up, when the text would get less than
 * [MIN_TEXT_ROOM_DP]. [textRoomDp] is the height the text has with the header shown.
 */
fun collapseHeader(mode: AppMode, imeVisible: Boolean, textRoomDp: Float): Boolean =
    mode == AppMode.EDIT && imeVisible && textRoomDp < MIN_TEXT_ROOM_DP

/** The landscape chord sheet column's share of the width, kept within 30–70 %. */
fun clampSideFraction(fraction: Float): Float =
    if (fraction.isNaN()) SIDE_FRACTION_DEFAULT else fraction.coerceIn(SIDE_FRACTION_MIN, SIDE_FRACTION_MAX)

/**
 * The column's share after dragging its handle to [handleX] px in a row
 * [rowWidth] px wide (the column is right of the handle).
 */
fun sideFractionAt(handleX: Float, rowWidth: Float): Float =
    if (rowWidth <= 0f) SIDE_FRACTION_DEFAULT else clampSideFraction((rowWidth - handleX) / rowWidth)

/** The ribbon's scroll edges: a fade on the left once scrolled, a fade and › while more is to the right. */
data class RibbonEdges(val fadeLeft: Boolean, val more: Boolean) {
    companion object {
        /** Within this many px of an end counts as at the end. */
        const val EPSILON_PX = 2

        /** The edges for scroll position [value] of [max] (0 when everything fits). */
        fun of(value: Int, max: Int): RibbonEdges =
            RibbonEdges(fadeLeft = value > EPSILON_PX, more = value < max - EPSILON_PX)
    }
}

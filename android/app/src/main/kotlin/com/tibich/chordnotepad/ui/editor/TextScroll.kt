package com.tibich.chordnotepad.ui.editor

import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

/*
 * Where the song text scrolls to keep something in view, for both axes. With
 * word wrap off (the default) the text scrolls sideways as well as up and
 * down, so the sounding chord and the cursor are followed horizontally too.
 * Positions are in the scrolled content's pixels; a scroll [value] shows
 * `[value, value + viewport)`.
 */

/**
 * Where to scroll so the sounding chord at `[start, end)` shows: null while it
 * shows already, else with the chord a third of the way into the view (the
 * desktop's `see` for a chord the song has moved on to). An unmeasured view
 * ([viewport] 0) doesn't scroll.
 */
fun followChordScroll(start: Float, end: Float, value: Int, viewport: Int, max: Int): Int? {
    if (viewport <= 0) return null
    if (start >= value && end <= value + viewport) return null
    return (start.roundToInt() - viewport / 3).coerceIn(0, max.coerceAtLeast(0))
}

/**
 * Where to scroll, as little as needed, so the cursor at `[start, end)` shows
 * with [margin] around it (typing at a line's end past the edge): null while
 * it shows already. A view narrower than the cursor and its margins puts the
 * cursor's start in view.
 */
fun followCursorScroll(start: Float, end: Float, value: Int, viewport: Int, max: Int, margin: Float): Int? {
    if (viewport <= 0) return null
    val upper = max.coerceAtLeast(0)
    val target = when {
        start - margin < value -> floor(start - margin).toInt()
        end + margin > value + viewport -> ceil(end + margin).toInt() - viewport
        else -> return null
    }
    val clamped = target.coerceIn(0, upper)
    return clamped.takeIf { it != value }
}

package io.github.chibicitiberiu.chordnotepad.ui.toolbar

import java.math.BigDecimal
import java.math.MathContext
import kotlin.math.floor

/**
 * The scrubber's drag rule, as on the desktop (`ui/scrubber.py`): every
 * [PIXELS_PER_STEP_DP] of horizontal travel from where the drag started is
 * one step of [INCREMENT]. The raw value goes to the session, which clamps
 * and snaps it with the same `ScrubScale` the desktop scrubber uses, so the
 * result is the desktop's.
 */
object ScrubberMath {
    /** `Scrubber.DEFAULT_PIXELS_PER_STEP` (4 px at 1 px = 1 dp). */
    const val PIXELS_PER_STEP_DP = 4f

    /** `drag_step` of `BPM_SCALE` and `MULTIPLIER_SCALE` (session/toolbar.py). */
    const val INCREMENT = 1.0

    /** Whole steps for a drag of [dx] pixels (floored, like Python's `//`). */
    fun steps(dx: Float, pixelsPerStep: Float): Int = floor(dx / pixelsPerStep).toInt()

    /** The value to send for a drag of [dx] pixels that started at [start]. */
    fun dragged(start: Double, dx: Float, pixelsPerStep: Float): Double =
        start + steps(dx, pixelsPerStep) * INCREMENT
}

/** The beats a bar may have (`MIN_BEATS`..`MAX_BEATS`, session/toolbar.py). */
val TIME_SIGNATURE_BEATS: List<Int> = (1..16).toList()

/** The beat units a time signature may have (`TIME_SIGNATURE_UNITS`). */
val TIME_SIGNATURE_UNITS: List<Int> = listOf(1, 2, 4, 8, 16)

/**
 * A percentage as the desktop shows it (`format_multiplier_pct`, Python's
 * `{:g}`): `100`, `87.5`, at most six significant digits.
 */
fun formatPct(pct: Double): String {
    if (pct.isNaN() || pct.isInfinite()) return pct.toString()
    val rounded = BigDecimal(pct).round(MathContext(6)).stripTrailingZeros()
    return if (rounded.signum() == 0) "0" else rounded.toPlainString()
}

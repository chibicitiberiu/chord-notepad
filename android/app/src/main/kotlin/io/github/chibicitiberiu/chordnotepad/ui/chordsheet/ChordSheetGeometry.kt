package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.ln
import kotlin.math.roundToInt

// Pure layout and interaction math for the chord sheet strip (JVM-tested).
// Everything is in content dp unless a name says px.

/**
 * Top-left corner of a [width] × [height] box whose [anchor] point is at
 * ([x], [y]), the way Tk places text and images.
 */
fun anchoredTopLeft(x: Float, y: Float, width: Float, height: Float, anchor: Anchor): Pair<Float, Float> =
    (x - anchor.fx * width) to (y - anchor.fy * height)

/** Where the desktop parks the playhead after a snap (fraction of the viewport). */
private const val SCROLL_SNAP_TO = 0.25f

/** Past this fraction of the viewport the playhead triggers a forward snap. */
private const val SCROLL_TRIGGER = 0.70f

/** Smaller scroll changes are ignored. */
private const val SCROLL_EPSILON = 0.5f

/**
 * The desktop's auto-scroll rule (`ChordSheetViewModel.scroll_target`): while
 * the playhead sits between 25 % and 70 % of the viewport nothing moves;
 * otherwise snap so it lands at 25 %, clamped to the content.
 *
 * @return the new scroll offset, or null to leave the view alone.
 */
fun scrollTarget(playheadX: Float, viewportWidth: Float, currentScroll: Float, contentWidth: Float): Float? {
    if (viewportWidth <= 0f) return null
    val relative = playheadX - currentScroll
    val low = SCROLL_SNAP_TO * viewportWidth
    val high = SCROLL_TRIGGER * viewportWidth
    if (relative in low..high) return null
    val maxScroll = (contentWidth - viewportWidth).coerceAtLeast(0f)
    val target = (playheadX - low).coerceIn(0f, maxScroll)
    return if (abs(target - currentScroll) < SCROLL_EPSILON) null else target
}

/** The desktop's zoom factor per +/- click (`chord_sheet_viewmodel._ZOOM_STEP`). */
const val ZOOM_STEP = 1.2

/** The desktop's zoom bounds. */
const val ZOOM_MIN = 0.5
const val ZOOM_MAX = 2.5

/**
 * The number of desktop zoom steps (each ×[ZOOM_STEP]) closest to a pinch's
 * [scale], limited to the steps that still change [currentZoom] within
 * [ZOOM_MIN]..[ZOOM_MAX]. Positive zooms in.
 */
fun zoomStepsForScale(scale: Float, currentZoom: Double): Int {
    if (scale <= 0f || !scale.isFinite()) return 0
    val raw = (ln(scale.toDouble()) / ln(ZOOM_STEP)).roundToInt()
    val upRoom = stepsUntil(ZOOM_MAX / currentZoom)
    val downRoom = stepsUntil(currentZoom / ZOOM_MIN)
    return raw.coerceIn(-downRoom, upRoom)
}

/** [zoomStepsForScale] for a view that zooms; 0 (a pinch does nothing) where the core says it doesn't. */
fun pinchZoomSteps(zoomSupported: Boolean, scale: Float, currentZoom: Double): Int =
    if (zoomSupported) zoomStepsForScale(scale, currentZoom) else 0

/** Steps of [ZOOM_STEP] needed to cover [ratio] (the last one may be clamped). */
private fun stepsUntil(ratio: Double): Int =
    if (ratio <= 1.0 + 1e-6) 0 else ceil(ln(ratio) / ln(ZOOM_STEP) - 1e-6).toInt()

/**
 * The scroll offset that keeps content under viewport x [anchorX] in place
 * when the content width changes from [oldWidth] to [newWidth] (a zoom),
 * clamped to the new content.
 */
fun rescaleScroll(scroll: Float, anchorX: Float, oldWidth: Float, newWidth: Float, viewportWidth: Float): Float {
    val maxScroll = (newWidth - viewportWidth).coerceAtLeast(0f)
    if (oldWidth <= 0f) return scroll.coerceIn(0f, maxScroll)
    return ((scroll + anchorX) * (newWidth / oldWidth) - anchorX).coerceIn(0f, maxScroll)
}

/**
 * The right edge each lane text op may paint up to: the next lane text op's
 * x (to the right) minus 2 dp, or +∞. Android's sans serif measures wider than
 * the desktop font the lane estimated label widths for (docs/ANDROID.md).
 * Non-text ops get +∞.
 */
fun laneClipRights(lane: OpList): FloatArray {
    val textXs = lane.ops.filterIsInstance<TextOp>().map { it.x }.sorted()
    return FloatArray(lane.size) { i ->
        val op = lane.ops[i] as? TextOp ?: return@FloatArray Float.POSITIVE_INFINITY
        val next = textXs.firstOrNull { it > op.x + 0.5f }
        if (next == null) Float.POSITIVE_INFINITY else next - 2f
    }
}

/**
 * A Tk colour string as ARGB, or null for none ("" or unknown names). Covers
 * `#rgb`, `#rrggbb` and the few names Tk renderers might use.
 */
fun parseTkColor(spec: String?): Int? {
    if (spec.isNullOrEmpty()) return null
    if (spec[0] == '#') {
        val hex = spec.substring(1)
        val rgb = when (hex.length) {
            6 -> hex.toIntOrNull(16)
            3 -> hex.toIntOrNull(16)?.let {
                val r = (it shr 8) and 0xF
                val g = (it shr 4) and 0xF
                val b = it and 0xF
                (r * 17 shl 16) or (g * 17 shl 8) or (b * 17)
            }
            else -> null
        } ?: return null
        return (0xFF shl 24) or rgb
    }
    return when (spec.lowercase()) {
        "black" -> 0xFF000000.toInt()
        "white" -> 0xFFFFFFFF.toInt()
        "red" -> 0xFFFF0000.toInt()
        "gray", "grey" -> 0xFFBEBEBE.toInt()
        else -> null
    }
}

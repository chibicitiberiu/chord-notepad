package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import android.content.res.AssetManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.text.PlatformTextStyle
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.graphics.scale
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.max
import kotlin.math.roundToInt

private const val TAG = "CNChordSheet"

/**
 * An [OpList] ready to draw: polyline and polygon paths built once (off Main),
 * plus the lane's per-label clip edges.
 */
class PreparedOps(val list: OpList, val clipRights: FloatArray? = null) {
    /** The path for each multi-point line and each polygon; null for other ops. */
    val paths: Array<Path?> = Array(list.size) { i ->
        when (val op = list.ops[i]) {
            is LineOp -> if (op.points.size > 4) polylinePath(op.points) else null
            is PolygonOp -> polygonPath(op.points, op.smooth)
            else -> null
        }
    }
}

/** A decoded buffer with everything drawing needs, prepared off Main. */
class PreparedSheet(val buffer: ChordSheetBuffer) {
    /** Content ops. */
    val content = PreparedOps(buffer.content)

    /** Marker lane ops, labels clipped short of the next one. */
    val lane = PreparedOps(buffer.lane, laneClipRights(buffer.lane))

    /** Gutter variants, by index. */
    val gutters: List<PreparedOps> = buffer.gutterVariants.map { PreparedOps(it) }

    /** Every colour string in the buffer, parsed. */
    val colors: Map<String, Color> = buildMap {
        for (s in buffer.strings) parseTkColor(s)?.let { put(s, Color(it)) }
    }

    /** Strip background. */
    val background: Color = colors[buffer.background] ?: Color.White

    /** Playhead highlight. */
    val highlight: Color = colors[buffer.highlight] ?: Color(0xFFFFE58A)

    /** The image keys the buffer uses (for [GlyphCache.preload]). */
    val imageKeys: Set<String> = buildSet {
        (listOf(buffer.content, buffer.lane) + buffer.gutterVariants).forEach { l ->
            l.ops.forEach { if (it is ImageOp) add(it.key) }
        }
    }

    /** The prepared gutter for content x [scrollX] at the viewport's left edge, or null. */
    fun gutterAt(scrollX: Float): PreparedOps? {
        return buffer.gutterVariantIndexAt(scrollX)?.let { gutters[it] }
    }
}

private fun polylinePath(points: FloatArray) = Path().apply {
    moveTo(points[0], points[1])
    var i = 2
    while (i < points.size) {
        lineTo(points[i], points[i + 1]); i += 2
    }
}

/** A polygon; smooth is Tk's quadratic B-spline through the edge midpoints. */
private fun polygonPath(points: FloatArray, smooth: Boolean) = Path().apply {
    val n = points.size / 2
    if (n < 2) return@apply
    if (!smooth || n < 3) {
        moveTo(points[0], points[1])
        for (i in 1 until n) lineTo(points[2 * i], points[2 * i + 1])
        close()
        return@apply
    }
    fun px(i: Int) = points[2 * (i % n)]
    fun py(i: Int) = points[2 * (i % n) + 1]
    moveTo((px(n - 1) + px(0)) / 2, (py(n - 1) + py(0)) / 2)
    for (i in 0 until n) {
        quadraticTo(px(i), py(i), (px(i) + px(i + 1)) / 2, (py(i) + py(i + 1)) / 2)
    }
    close()
}

/**
 * The six base clef/glyph PNGs (assets/chord_sheet/<asset>.png), scaled once
 * per (asset, pixel height) and kept. Thread-safe; [preload] runs off Main.
 */
class GlyphCache(private val assets: AssetManager) {
    private val bases = ConcurrentHashMap<String, Bitmap>()
    private val scaled = ConcurrentHashMap<Long, ImageBitmap>()
    private val missing = ConcurrentHashMap.newKeySet<String>()
    private val tints = ConcurrentHashMap<String, ColorFilter>()

    /** Decode and scale every image [keys] needs at [density]. */
    fun preload(keys: Collection<String>, density: Float) {
        for (key in keys) parseImageKey(key)?.let { image(it, density) }
    }

    /** The glyph for [key] at its pixel size, or null when the asset is missing. */
    fun image(key: ImageKey, density: Float): ImageBitmap? {
        val heightPx = max(1, (key.height * density).roundToInt())
        val cacheKey = (key.asset.hashCode().toLong() shl 32) or heightPx.toLong()
        scaled[cacheKey]?.let { return it }
        val base = base(key.asset) ?: return null
        val widthPx = max(1, (base.width.toFloat() * heightPx / base.height).roundToInt())
        return base.scale(widthPx, heightPx, filter = true).asImageBitmap()
            .also { scaled[cacheKey] = it }
    }

    /** The glyph's size in dp, as the renderers place it (`clef_assets.scaled_width`). */
    fun sizeDp(key: ImageKey): Size? {
        val base = base(key.asset) ?: return null
        val width = max(1, (base.width.toFloat() * key.height / base.height).roundToInt())
        return Size(width.toFloat(), key.height.toFloat())
    }

    /** SrcIn tint for a glyph colour (black ink → [color], alpha kept). */
    fun tint(color: String, parsed: Color): ColorFilter =
        tints.getOrPut(color) { ColorFilter.tint(parsed, BlendMode.SrcIn) }

    private fun base(asset: String): Bitmap? {
        bases[asset]?.let { return it }
        if (asset in missing) return null
        return try {
            assets.open("chord_sheet/$asset.png").use { BitmapFactory.decodeStream(it) }
                ?.also { bases[asset] = it }
        } catch (e: java.io.IOException) {
            null
        } ?: run {
            if (missing.add(asset)) Log.w(TAG, "Missing chord sheet glyph asset $asset")
            null
        }
    }
}

/**
 * Draws prepared ops into a [DrawScope] whose transform maps content dp to
 * pixels (`scale(density)`). Text goes through a [TextMeasurer] built for
 * density 1 and font scale 1, so a layout's size is in dp: the strip's
 * geometry is fixed by the renderers, so text ignores the system font scale.
 */
class SheetPainter(private val measurer: TextMeasurer, private val glyphs: GlyphCache) {
    private data class TextKey(val text: String, val size: Float, val bold: Boolean)

    private val layouts = HashMap<TextKey, TextLayoutResult>()
    private val strokes = HashMap<Pair<Float, StrokeJoin>, Stroke>()

    /** Ops drawn by the last [drawOps] calls since [resetCounter] (perf logging). */
    var drawnOps = 0
        private set

    /** Reset [drawnOps]. */
    fun resetCounter() {
        drawnOps = 0
    }

    /** The measured text box for [op], in dp. */
    fun measure(op: TextOp): TextLayoutResult {
        val key = TextKey(op.text, op.size, op.bold)
        layouts[key]?.let { return it }
        if (layouts.size > MAX_LAYOUTS) layouts.clear()
        return measurer.measure(
            op.text,
            style = TextStyle(
                fontFamily = FontFamily.SansSerif,
                fontWeight = if (op.bold) FontWeight.Bold else FontWeight.Normal,
                fontSize = (op.size * PT_TO_SP).sp,
                platformStyle = PlatformTextStyle(includeFontPadding = false),
            ),
            softWrap = false,
            maxLines = 1,
        ).also { layouts[key] = it }
    }

    /**
     * Draw the ops of [ops] that intersect content x `[left, right]`, in
     * order. [density] is px per dp (images are drawn unscaled at their pixel
     * size, for crisp glyphs).
     */
    fun DrawScope.drawOps(ops: PreparedOps, colors: Map<String, Color>, left: Float, right: Float, density: Float) {
        val list = ops.list
        for (i in 0 until list.size) {
            if (!list.intersects(i, left, right)) continue
            drawnOps++
            when (val op = list.ops[i]) {
                is RectOp -> {
                    colors[op.fill]?.let { drawRect(it, Offset(op.x, op.y), Size(op.w, op.h)) }
                    if (op.width > 0f) colors[op.outline]?.let {
                        drawRect(it, Offset(op.x, op.y), Size(op.w, op.h), style = stroke(op.width, StrokeJoin.Miter))
                    }
                }
                is OvalOp -> {
                    colors[op.fill]?.let { drawOval(it, Offset(op.x, op.y), Size(op.w, op.h)) }
                    if (op.width > 0f) colors[op.outline]?.let {
                        drawOval(it, Offset(op.x, op.y), Size(op.w, op.h), style = stroke(op.width, StrokeJoin.Round))
                    }
                }
                is LineOp -> {
                    val color = colors[op.fill] ?: Color.Black
                    val path = ops.paths[i]
                    if (path != null) {
                        drawPath(path, color, style = stroke(op.width, StrokeJoin.Round))
                    } else if (op.points.size == 4) {
                        val p = op.points
                        drawLine(color, Offset(p[0], p[1]), Offset(p[2], p[3]), strokeWidth = op.width, cap = StrokeCap.Butt)
                    }
                }
                is PolygonOp -> ops.paths[i]?.let { drawPath(it, colors[op.fill] ?: Color.Black) }
                is TextOp -> drawTextOp(op, colors, ops.clipRights?.get(i) ?: Float.POSITIVE_INFINITY)
                is ImageOp -> drawImageOp(op, density)
            }
        }
    }

    private fun DrawScope.drawTextOp(op: TextOp, colors: Map<String, Color>, clipRight: Float) {
        val layout = measure(op)
        val (x, y) = anchoredTopLeft(op.x, op.y, layout.size.width.toFloat(), layout.size.height.toFloat(), op.anchor)
        val color = colors[op.fill] ?: Color.Black
        if (clipRight.isFinite() && x + layout.size.width > clipRight) {
            clipRect(left = x - 1f, top = y - 1f, right = clipRight, bottom = y + layout.size.height + 1f) {
                drawText(layout, color, Offset(x, y))
            }
        } else {
            drawText(layout, color, Offset(x, y))
        }
    }

    private fun DrawScope.drawImageOp(op: ImageOp, density: Float) {
        val key = parseImageKey(op.key) ?: return
        val image = glyphs.image(key, density) ?: return
        val size = glyphs.sizeDp(key) ?: return
        val (x, y) = anchoredTopLeft(op.x, op.y, size.width, size.height, op.anchor)
        val filter = key.tint?.let(::tintFor)
        // Undo the dp scale so the pre-scaled bitmap maps 1:1 onto pixels.
        withTransform({ scale(1f / density, 1f / density, Offset.Zero) }) {
            drawImage(image, Offset((x * density).roundToInt().toFloat(), (y * density).roundToInt().toFloat()), colorFilter = filter)
        }
    }

    private fun tintFor(tint: String): ColorFilter? = parseTkColor(tint)?.let { glyphs.tint(tint, Color(it)) }

    private fun stroke(width: Float, join: StrokeJoin): Stroke =
        strokes.getOrPut(width to join) { Stroke(width, cap = StrokeCap.Butt, join = join) }

    private companion object {
        const val MAX_LAYOUTS = 4096
    }
}

package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import java.nio.BufferUnderflowException
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Decoder for the chord sheet op buffer, format version 1 (docs/ANDROID.md,
// "Chord sheet op buffer"; the Python side is src/chord_sheet/pack.py). Pure
// Kotlin: no Android or Compose types, so the JVM tests run it as is.

/** Tk text/image anchors, in their one-byte code order. [fx]/[fy] place the box. */
enum class Anchor(val fx: Float, val fy: Float) {
    NW(0f, 0f), N(0.5f, 0f), NE(1f, 0f),
    W(0f, 0.5f), CENTER(0.5f, 0.5f), E(1f, 0.5f),
    SW(0f, 1f), S(0.5f, 1f), SE(1f, 1f),
}

/** One draw op, in dp (Tk px). Colours are Tk colour strings; null means none. */
sealed interface DrawOp {
    /** The renderer's tags (`slot:<i>`, `marker-lane`, ...). */
    val tags: List<String>
}

/** A rectangle; fill and outline may each be absent. The outline is centred on the edge. */
data class RectOp(
    val x: Float, val y: Float, val w: Float, val h: Float,
    val fill: String?, val outline: String?, val width: Float,
    override val tags: List<String>,
) : DrawOp

/** The ellipse inscribed in the box; same fields as [RectOp]. */
data class OvalOp(
    val x: Float, val y: Float, val w: Float, val h: Float,
    val fill: String?, val outline: String?, val width: Float,
    override val tags: List<String>,
) : DrawOp

/** A polyline; [points] is `x0, y0, x1, y1, ...`. */
class LineOp(
    val fill: String?, val width: Float, val points: FloatArray,
    override val tags: List<String>,
) : DrawOp

/** A filled polygon; [smooth] means Tk's quadratic B-spline. */
class PolygonOp(
    val fill: String?, val smooth: Boolean, val points: FloatArray,
    override val tags: List<String>,
) : DrawOp

/** Single-line text; [size] in points, [anchor] places its box at ([x], [y]). */
data class TextOp(
    val x: Float, val y: Float, val text: String, val anchor: Anchor,
    val bold: Boolean, val size: Float, val fill: String?,
    override val tags: List<String>,
) : DrawOp

/** A clef/glyph image by key (`clef_treble:96`, `glyph_<name>:<h>[:<rrggbb>]`). */
data class ImageOp(
    val x: Float, val y: Float, val key: String, val anchor: Anchor,
    override val tags: List<String>,
) : DrawOp

/** One chord's box on the strip, for hit-testing and the playhead highlight. */
data class Slot(val chordIndex: Int, val x: Float, val width: Float) {
    /** Whether content x [cx] falls in this slot (edges included, as on the desktop). */
    operator fun contains(cx: Float): Boolean = cx >= x && cx <= x + width
}

/** The gutter variant shown for every scroll position past [startX]. */
data class GutterRun(val startX: Float, val variant: Int)

/**
 * A list of ops with their horizontal extents ([minX]/[maxX], conservative for
 * text and images, whose size isn't known before measuring), for culling.
 */
class OpList(val ops: List<DrawOp>) {
    /** Leftmost x each op can paint at. */
    val minX = FloatArray(ops.size)

    /** Rightmost x each op can paint at. */
    val maxX = FloatArray(ops.size)

    init {
        ops.forEachIndexed { i, op ->
            val (lo, hi) = horizontalExtent(op)
            minX[i] = lo
            maxX[i] = hi
        }
    }

    /** Number of ops. */
    val size: Int get() = ops.size

    /** Whether op [i] may paint anything between content x [left] and [right]. */
    fun intersects(i: Int, left: Float, right: Float): Boolean = maxX[i] >= left && minX[i] <= right

    /** Indices of the ops that intersect `[left, right]`, in paint order. */
    fun visibleIndices(left: Float, right: Float): List<Int> =
        ops.indices.filter { intersects(it, left, right) }
}

/** The buffer's version isn't one this app reads (a newer core). */
class UnsupportedChordSheetVersion(val version: Int) :
    IllegalArgumentException("Unsupported chord sheet buffer version $version")

/** The buffer is malformed (bad magic, truncated, unknown opcode, ...). */
class ChordSheetFormatException(message: String, cause: Throwable? = null) :
    IllegalArgumentException(message, cause)

/**
 * One chord-sheet view, decoded from the op buffer: everything the strip draws
 * for one (song, view, zoom, height). Immutable; decode once and keep it.
 *
 * Coordinates are dp (1 Tk px = 1 dp); text sizes are points (sp = pt × 4/3).
 */
class ChordSheetBuffer(
    val version: Int,
    val viewId: String,
    val background: String,
    val highlight: String,
    val zoom: Float,
    val height: Float,
    val contentWidth: Float,
    val contentHeight: Float,
    val gutterWidth: Float,
    val laneHeight: Float,
    val strings: List<String>,
    val slots: List<Slot>,
    val content: OpList,
    val lane: OpList,
    val gutterVariants: List<OpList>,
    val gutterRuns: List<GutterRun>,
) {
    /**
     * The gutter variant to draw when content x [scrollX] is at the viewport's
     * left edge: the variant of the last run with `startX < scrollX`, or null
     * when the view has no gutter.
     */
    fun gutterVariantAt(scrollX: Float): OpList? = gutterVariantIndexAt(scrollX)?.let { gutterVariants[it] }

    /** The index of [gutterVariantAt]'s variant, or null. */
    fun gutterVariantIndexAt(scrollX: Float): Int? {
        var found: Int? = null
        for (run in gutterRuns) {
            if (run.startX < scrollX) found = run.variant else break
        }
        return found
    }

    /** The slot under content x [cx], or null (the first match, as on the desktop). */
    fun slotAt(cx: Float): Slot? = slots.firstOrNull { cx in it }

    /** The slot drawn for chord [chordIndex], or null. */
    fun slotFor(chordIndex: Int): Slot? = slots.firstOrNull { it.chordIndex == chordIndex }

    companion object {
        /** The only format version this decoder reads. */
        const val FORMAT_VERSION = 1

        private const val NO_STRING = 0xFFFF
        private const val MIN_HEADER_SIZE = 48
        private val MAGIC = byteArrayOf('C'.code.toByte(), 'N'.code.toByte(), 'S'.code.toByte(), 'B'.code.toByte())

        /**
         * Decode [data].
         *
         * @throws UnsupportedChordSheetVersion for another format version.
         * @throws ChordSheetFormatException for anything malformed.
         */
        fun decode(data: ByteArray): ChordSheetBuffer {
            try {
                return Reader(data).readAll()
            } catch (e: BufferUnderflowException) {
                throw ChordSheetFormatException("Truncated chord sheet buffer", e)
            } catch (e: IndexOutOfBoundsException) {
                throw ChordSheetFormatException("Truncated chord sheet buffer", e)
            }
        }

        private class Reader(private val data: ByteArray) {
            private val buf: ByteBuffer = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
            private var pos = 0
            private var strings: List<String> = emptyList()

            fun readAll(): ChordSheetBuffer {
                if (data.size < 8 || !data.copyOfRange(0, 4).contentEquals(MAGIC)) {
                    throw ChordSheetFormatException("Not a chord sheet buffer")
                }
                val version = u16(4)
                if (version != FORMAT_VERSION) throw UnsupportedChordSheetVersion(version)
                val headerSize = u16(6)
                if (headerSize < MIN_HEADER_SIZE) throw ChordSheetFormatException("Header too short: $headerSize")
                val viewIdIndex = u16(8)
                val backgroundIndex = u16(10)
                val highlightIndex = u16(12)
                val zoom = f32(16)
                val height = f32(20)
                val contentWidth = f32(24)
                val contentHeight = f32(28)
                val gutterWidth = f32(32)
                val laneHeight = f32(36)
                val stringCount = count(u32(40))
                val slotCount = count(u32(44))

                pos = headerSize
                strings = List(stringCount) {
                    val length = readU16()
                    need(length)
                    String(data, pos, length, Charsets.UTF_8).also { pos += length }
                }
                val slots = List(slotCount) { Slot(count(readU32()), readF32(), readF32()) }
                val content = readOpList()
                val lane = readOpList()
                val variants = List(readU16()) { readOpList() }
                val runs = List(readU16()) {
                    val start = readF32()
                    val variant = readU16()
                    if (variant >= variants.size) throw ChordSheetFormatException("Gutter run names variant $variant")
                    GutterRun(start, variant)
                }
                if (pos != data.size) throw ChordSheetFormatException("Trailing bytes after the gutter runs")
                return ChordSheetBuffer(
                    version = version,
                    viewId = str(viewIdIndex) ?: "",
                    background = str(backgroundIndex) ?: "#ffffff",
                    highlight = str(highlightIndex) ?: "#ffe58a",
                    zoom = zoom, height = height,
                    contentWidth = contentWidth, contentHeight = contentHeight,
                    gutterWidth = gutterWidth, laneHeight = laneHeight,
                    strings = strings, slots = slots, content = content, lane = lane,
                    gutterVariants = variants, gutterRuns = runs,
                )
            }

            private fun readOpList(): OpList {
                val opCount = count(readU32())
                val byteLength = count(readU32())
                val end = pos + byteLength
                if (end > data.size) throw ChordSheetFormatException("Op list runs past the end")
                val ops = ArrayList<DrawOp>(opCount)
                repeat(opCount) { ops += readOp() }
                if (pos != end) throw ChordSheetFormatException("Op list length mismatch")
                return OpList(ops)
            }

            private fun readOp(): DrawOp {
                return when (val code = readU8()) {
                    1, 2 -> {
                        val x = readF32(); val y = readF32(); val w = readF32(); val h = readF32()
                        val fill = str(readU16()); val outline = str(readU16()); val width = readF32()
                        val tags = readTags()
                        if (code == 1) RectOp(x, y, w, h, fill, outline, width, tags)
                        else OvalOp(x, y, w, h, fill, outline, width, tags)
                    }
                    3 -> {
                        val fill = str(readU16()); val width = readF32()
                        val points = readPoints(readU16())
                        LineOp(fill, width, points, readTags())
                    }
                    4 -> {
                        val fill = str(readU16()); val smooth = readU8() != 0
                        val points = readPoints(readU16())
                        PolygonOp(fill, smooth, points, readTags())
                    }
                    5 -> {
                        val x = readF32(); val y = readF32()
                        val text = str(readU16()) ?: ""
                        val anchor = anchor(readU8()); val bold = readU8() != 0
                        val size = readF32(); val fill = str(readU16())
                        TextOp(x, y, text, anchor, bold, size, fill, readTags())
                    }
                    6 -> {
                        val x = readF32(); val y = readF32()
                        val key = str(readU16()) ?: ""
                        ImageOp(x, y, key, anchor(readU8()), readTags())
                    }
                    else -> throw ChordSheetFormatException("Unknown opcode $code at byte ${pos - 1}")
                }
            }

            private fun readTags(): List<String> {
                val n = readU8()
                if (n == 0) return emptyList()
                return List(n) { str(readU16()) ?: "" }
            }

            private fun readPoints(n: Int): FloatArray {
                need(8 * n)
                return FloatArray(2 * n) { readF32() }
            }

            private fun anchor(code: Int): Anchor =
                Anchor.entries.getOrNull(code) ?: throw ChordSheetFormatException("Unknown anchor $code")

            private fun str(index: Int): String? {
                if (index == NO_STRING) return null
                return strings.getOrNull(index) ?: throw ChordSheetFormatException("String index $index out of range")
            }

            private fun need(length: Int) {
                if (pos + length > data.size) throw ChordSheetFormatException("Truncated chord sheet buffer")
            }

            private fun count(value: Long): Int {
                if (value > data.size) throw ChordSheetFormatException("Count $value larger than the buffer")
                return value.toInt()
            }

            private fun u16(at: Int): Int = buf.getShort(at).toInt() and 0xFFFF
            private fun u32(at: Int): Long = buf.getInt(at).toLong() and 0xFFFFFFFFL
            private fun f32(at: Int): Float = buf.getFloat(at)

            private fun readU8(): Int = (data[pos++].toInt() and 0xFF)
            private fun readU16(): Int = u16(pos).also { pos += 2 }
            private fun readU32(): Long = u32(pos).also { pos += 4 }
            private fun readF32(): Float = f32(pos).also { pos += 4 }
        }
    }
}

/**
 * The x range op [op] can paint: exact for shapes (plus half the stroke),
 * generous for text and images, whose measured size isn't known here.
 */
internal fun horizontalExtent(op: DrawOp): Pair<Float, Float> = when (op) {
    is RectOp -> (op.x - op.width / 2) to (op.x + op.w + op.width / 2)
    is OvalOp -> (op.x - op.width / 2) to (op.x + op.w + op.width / 2)
    is LineOp -> pointsExtent(op.points, op.width / 2 + 1f)
    is PolygonOp -> pointsExtent(op.points, 1f)
    is TextOp -> {
        // Wider than any sans serif at this size: up to one em per character.
        val reach = op.text.length * op.size * PT_TO_SP + 4f
        (op.x - reach) to (op.x + reach)
    }
    is ImageOp -> {
        // Images are at most ~1.7 × their height wide (the whole notehead).
        val reach = 2f * (imageHeight(op.key) ?: 256) + 4f
        (op.x - reach) to (op.x + reach)
    }
}

private fun pointsExtent(points: FloatArray, pad: Float): Pair<Float, Float> {
    if (points.isEmpty()) return 0f to -1f
    var lo = Float.POSITIVE_INFINITY
    var hi = Float.NEGATIVE_INFINITY
    var i = 0
    while (i < points.size) {
        val x = points[i]
        if (x < lo) lo = x
        if (x > hi) hi = x
        i += 2
    }
    return (lo - pad) to (hi + pad)
}

/** sp per Tk point: Tk lays text out at 96 DPI, 4/3 px per point, and 1 Tk px = 1 dp. */
const val PT_TO_SP = 4f / 3f

/** An image key split into its parts (`chord_sheet.clef_assets.parse_image_key`). */
data class ImageKey(val asset: String, val height: Int, val tint: String?)

/** Parse an image op's key, or null when malformed. */
fun parseImageKey(key: String): ImageKey? {
    val parts = key.split(':')
    if (parts.size !in 2..3) return null
    val height = parts[1].toIntOrNull()?.takeIf { it > 0 } ?: return null
    val name = parts[0]
    if (!name.startsWith("clef_") && !name.startsWith("glyph_")) return null
    if (parts.size == 3) {
        if (!name.startsWith("glyph_")) return null
        val hex = parts[2].removePrefix("#")
        if (hex.length != 6 || hex.any { it.digitToIntOrNull(16) == null }) return null
        return ImageKey(name, height, "#" + hex.lowercase())
    }
    return ImageKey(name, height, null)
}

private fun imageHeight(key: String): Int? = parseImageKey(key)?.height

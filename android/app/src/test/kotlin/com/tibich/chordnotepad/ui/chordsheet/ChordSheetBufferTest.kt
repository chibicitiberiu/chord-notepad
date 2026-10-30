package com.tibich.chordnotepad.ui.chordsheet

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Decodes the buffers `android/tools/gen_chord_sheet_fixtures.py` packed with
 * `chord_sheet.pack` and compares them with what Python's reference decoder
 * read from the same bytes.
 */
class ChordSheetBufferTest {
    private val fixtures = listOf(
        "american_keyboard", "american_staff", "american_fret", "american_tab",
        "american_staff_z1728", "multikey_staff", "multikey_tab_z0833",
    )

    @Test
    fun `every fixture decodes to what Python's unpack read`() {
        for (name in fixtures) {
            val buffer = ChordSheetBuffer.decode(bytes(name))
            val expected = expected(name)
            fun f(key: String) = expected[key]!!.jsonPrimitive.double
            assertEquals(name, expected["view_id"]!!.jsonPrimitive.content, buffer.viewId)
            assertEquals(name, f("zoom"), buffer.zoom.toDouble(), 1e-9)
            assertEquals(name, f("height"), buffer.height.toDouble(), 1e-9)
            assertEquals(name, f("content_width"), buffer.contentWidth.toDouble(), 1e-9)
            assertEquals(name, f("content_height"), buffer.contentHeight.toDouble(), 1e-9)
            assertEquals(name, f("gutter_width"), buffer.gutterWidth.toDouble(), 1e-9)
            assertEquals(name, f("lane_height"), buffer.laneHeight.toDouble(), 1e-9)
            assertEquals(name, expected["background"]!!.jsonPrimitive.content, buffer.background)
            assertEquals(name, expected["highlight"]!!.jsonPrimitive.content, buffer.highlight)
            assertEquals(name, expected["string_count"]!!.jsonPrimitive.int, buffer.strings.size)
            assertEquals(name, expected["slot_count"]!!.jsonPrimitive.int, buffer.slots.size)
            assertSlot(expected["first_slot"]!!.jsonArray, buffer.slots.first())
            assertSlot(expected["last_slot"]!!.jsonArray, buffer.slots.last())
            assertEquals(name, f("slot_x_sum"), buffer.slots.sumOf { it.x.toDouble() }, 1e-3)

            assertList("$name content", expected["content"]!!.jsonObject, buffer.content)
            assertList("$name lane", expected["lane"]!!.jsonObject, buffer.lane)
            val variants = expected["gutter_variants"]!!.jsonArray
            assertEquals(name, variants.size, buffer.gutterVariants.size)
            variants.forEachIndexed { i, v -> assertList("$name gutter $i", v.jsonObject, buffer.gutterVariants[i]) }
            val runs = expected["gutter_runs"]!!.jsonArray.map { it.jsonArray }
            assertEquals(name, runs.size, buffer.gutterRuns.size)
            runs.forEachIndexed { i, run ->
                val start = if (run[0] is JsonNull) Float.NEGATIVE_INFINITY else run[0].jsonPrimitive.double.toFloat()
                assertEquals(GutterRun(start, run[1].jsonPrimitive.int), buffer.gutterRuns[i])
            }
        }
    }

    @Test
    fun `the 133-chord sample has one slot per chord in song order`() {
        val buffer = ChordSheetBuffer.decode(bytes("american_staff"))
        assertEquals(133, buffer.slots.size)
        assertEquals((0 until 133).toList(), buffer.slots.map { it.chordIndex })
        assertTrue(buffer.slots.zipWithNext().all { (a, b) -> a.x < b.x })
    }

    @Test
    fun `a newer format version is rejected without guessing`() {
        val data = bytes("multikey_staff").copyOf()
        ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putShort(4, 2)
        try {
            ChordSheetBuffer.decode(data)
            fail("version 2 decoded")
        } catch (e: UnsupportedChordSheetVersion) {
            assertEquals(2, e.version)
        }
    }

    @Test
    fun `malformed buffers raise ChordSheetFormatException`() {
        val good = bytes("multikey_staff")
        val badMagic = good.copyOf().also { it[0] = 'X'.code.toByte() }
        val truncated = good.copyOf(good.size - 3)
        val trailing = good + byteArrayOf(0)
        val empty = ByteArray(0)
        // The first content op's opcode: header, strings, slots, then u32 count + u32 length.
        val unknownOpcode = good.copyOf().also { it[firstOpOffset(good)] = 99 }
        for ((label, data) in listOf(
            "magic" to badMagic, "truncated" to truncated, "trailing" to trailing,
            "empty" to empty, "opcode" to unknownOpcode,
        )) {
            try {
                ChordSheetBuffer.decode(data)
                fail("$label decoded")
            } catch (_: ChordSheetFormatException) {
            }
        }
    }

    @Test
    fun `a later minor version's longer header is skipped`() {
        val good = bytes("multikey_staff")
        val headerSize = 48
        val longer = ByteArray(good.size + 8)
        good.copyInto(longer, 0, 0, headerSize)
        good.copyInto(longer, headerSize + 8, headerSize)
        ByteBuffer.wrap(longer).order(ByteOrder.LITTLE_ENDIAN).putShort(6, (headerSize + 8).toShort())
        val buffer = ChordSheetBuffer.decode(longer)
        assertEquals(ChordSheetBuffer.decode(good).content.size, buffer.content.size)
    }

    @Test
    fun `image keys parse like clef_assets parse_image_key`() {
        assertEquals(ImageKey("clef_treble", 96, null), parseImageKey("clef_treble:96"))
        assertEquals(ImageKey("glyph_accidental_sharp", 40, "#3a5a8a"), parseImageKey("glyph_accidental_sharp:40:3A5A8A"))
        assertNull(parseImageKey("clef_treble:96:3a5a8a"))
        assertNull(parseImageKey("clef_treble"))
        assertNull(parseImageKey("glyph_x:0"))
        assertNull(parseImageKey("glyph_x:12:zzzzzz"))
        assertNull(parseImageKey("other:12"))
    }

    private fun firstOpOffset(data: ByteArray): Int {
        val buf = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
        var pos = buf.getShort(6).toInt()
        repeat(buf.getInt(40)) { pos += 2 + (buf.getShort(pos).toInt() and 0xFFFF) }
        pos += 12 * buf.getInt(44)
        return pos + 8
    }

    private fun assertSlot(expected: JsonArray, slot: Slot) {
        assertEquals(expected[0].jsonPrimitive.int, slot.chordIndex)
        assertEquals(expected[1].jsonPrimitive.double, slot.x.toDouble(), 1e-9)
        assertEquals(expected[2].jsonPrimitive.double, slot.width.toDouble(), 1e-9)
    }

    private fun assertList(label: String, expected: JsonObject, list: OpList) {
        assertEquals(label, expected["count"]!!.jsonPrimitive.int, list.size)
        val histogram = list.ops.groupingBy { opName(it) }.eachCount()
        val expectedHistogram = expected["histogram"]!!.jsonObject.mapValues { it.value.jsonPrimitive.int }
        assertEquals(label, expectedHistogram, histogram)
        assertEquals(label, expected["tag_count"]!!.jsonPrimitive.int, list.ops.sumOf { it.tags.size })
        val sum = expected["coord_sum"]!!.jsonPrimitive.double
        assertEquals(label, sum, list.ops.sumOf(::coordSum), 1e-6 * maxOf(1.0, kotlin.math.abs(sum)))
        if (list.size > 0) {
            assertOp(label, expected["first"]!!.jsonObject, list.ops.first())
            assertOp(label, expected["last"]!!.jsonObject, list.ops.last())
        }
    }

    private fun assertOp(label: String, e: JsonObject, op: DrawOp) {
        assertEquals(label, e["op"]!!.jsonPrimitive.content, opName(op))
        assertEquals(label, e["tags"]!!.jsonArray.map { it.jsonPrimitive.content }, op.tags)
        fun d(key: String) = e[key]!!.jsonPrimitive.double
        fun s(key: String) = e[key]!!.let { if (it is JsonNull) null else it.jsonPrimitive.content }
        when (op) {
            is RectOp -> {
                assertEquals(listOf(d("x"), d("y"), d("w"), d("h"), d("width")),
                    listOf(op.x, op.y, op.w, op.h, op.width).map(Float::toDouble))
                assertEquals(listOf(s("fill"), s("outline")), listOf(op.fill, op.outline))
            }
            is OvalOp -> {
                assertEquals(listOf(d("x"), d("y"), d("w"), d("h"), d("width")),
                    listOf(op.x, op.y, op.w, op.h, op.width).map(Float::toDouble))
                assertEquals(listOf(s("fill"), s("outline")), listOf(op.fill, op.outline))
            }
            is LineOp -> {
                assertEquals(s("fill"), op.fill)
                assertEquals(d("width"), op.width.toDouble(), 0.0)
                assertEquals(points(e), op.points.map(Float::toDouble))
            }
            is PolygonOp -> {
                assertEquals(s("fill"), op.fill)
                assertEquals(e["smooth"]!!.jsonPrimitive.boolean, op.smooth)
                assertEquals(points(e), op.points.map(Float::toDouble))
            }
            is TextOp -> {
                assertEquals(listOf(d("x"), d("y"), d("size")), listOf(op.x, op.y, op.size).map(Float::toDouble))
                assertEquals(s("text"), op.text)
                assertEquals(s("anchor"), op.anchor.name.lowercase())
                assertEquals(e["bold"]!!.jsonPrimitive.boolean, op.bold)
                assertEquals(s("fill"), op.fill)
            }
            is ImageOp -> {
                assertEquals(listOf(d("x"), d("y")), listOf(op.x, op.y).map(Float::toDouble))
                assertEquals(s("key"), op.key)
                assertEquals(s("anchor"), op.anchor.name.lowercase())
            }
        }
    }

    private fun points(e: JsonObject) = e["points"]!!.jsonArray.flatMap { p -> p.jsonArray.map { it.jsonPrimitive.double } }

    private fun coordSum(op: DrawOp): Double = when (op) {
        is RectOp -> (op.x + op.y + op.w + op.h).toDouble() + op.width
        is OvalOp -> (op.x + op.y + op.w + op.h).toDouble() + op.width
        is LineOp -> op.width.toDouble() + op.points.sumOf { it.toDouble() }
        is PolygonOp -> op.points.sumOf { it.toDouble() }
        is TextOp -> op.x.toDouble() + op.y + op.size
        is ImageOp -> op.x.toDouble() + op.y
    }

    private fun opName(op: DrawOp) = when (op) {
        is RectOp -> "rect"
        is OvalOp -> "oval"
        is LineOp -> "line"
        is PolygonOp -> "polygon"
        is TextOp -> "text"
        is ImageOp -> "image"
    }

    companion object {
        fun bytes(name: String): ByteArray =
            ChordSheetBufferTest::class.java.getResourceAsStream("/chord_sheet/$name.bin")!!.use { it.readBytes() }

        fun expected(name: String): JsonObject {
            val text = ChordSheetBufferTest::class.java.getResourceAsStream("/chord_sheet/$name.json")!!
                .use { it.readBytes().decodeToString() }
            return Json.parseToJsonElement(text).jsonObject
        }
    }
}

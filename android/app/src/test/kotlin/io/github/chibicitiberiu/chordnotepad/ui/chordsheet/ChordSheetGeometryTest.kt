package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import io.github.chibicitiberiu.chordnotepad.bridge.ChordSheetState
import io.github.chibicitiberiu.chordnotepad.ui.chordsheet.ChordSheetBufferTest.Companion.bytes
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

class ChordSheetGeometryTest {
    private val staff = ChordSheetBuffer.decode(bytes("american_staff"))
    private val multiKey = ChordSheetBuffer.decode(bytes("multikey_staff"))

    // -- anchors ----------------------------------------------------------------

    @Test
    fun `anchors place the box like Tk`() {
        val w = 40f
        val h = 10f
        fun at(anchor: Anchor) = anchoredTopLeft(100f, 50f, w, h, anchor)
        assertEquals(100f to 50f, at(Anchor.NW))
        assertEquals(80f to 50f, at(Anchor.N))
        assertEquals(60f to 50f, at(Anchor.NE))
        assertEquals(100f to 45f, at(Anchor.W))
        assertEquals(80f to 45f, at(Anchor.CENTER))
        assertEquals(60f to 45f, at(Anchor.E))
        assertEquals(100f to 40f, at(Anchor.SW))
        assertEquals(80f to 40f, at(Anchor.S))
        assertEquals(60f to 40f, at(Anchor.SE))
    }

    @Test
    fun `anchor codes follow the format's order`() {
        assertEquals(listOf("NW", "N", "NE", "W", "CENTER", "E", "SW", "S", "SE"), Anchor.entries.map { it.name })
    }

    // -- hit-testing -------------------------------------------------------------

    @Test
    fun `a tap inside a slot auditions that chord, edges included`() {
        val slot = staff.slots[10]
        assertEquals(10, staff.slotAt(slot.x + slot.width / 2)!!.chordIndex)
        assertEquals(slot, staff.slotAt(slot.x + 0.01f))
        assertEquals(slot, staff.slotAt(slot.x + slot.width))
        // A shared edge goes to the earlier slot, as on the desktop (first match).
        assertEquals(staff.slots[9].x + staff.slots[9].width, slot.x)
        assertEquals(staff.slots[9], staff.slotAt(slot.x))
        assertNull(staff.slotAt(-1f))
        assertNull(staff.slotAt(staff.contentWidth + 100f))
        assertEquals(staff.slots[42], staff.slotFor(42))
        assertNull(staff.slotFor(10_000))
    }

    // -- gutter -------------------------------------------------------------------

    @Test
    fun `the gutter variant is the last run starting strictly before the scroll`() {
        val runs = multiKey.gutterRuns
        assertEquals(4, runs.size)
        assertEquals(Float.NEGATIVE_INFINITY, runs[0].startX)
        assertEquals(0, multiKey.gutterVariantIndexAt(0f))
        assertEquals(0, multiKey.gutterVariantIndexAt(runs[1].startX)) // strict <
        assertEquals(1, multiKey.gutterVariantIndexAt(runs[1].startX + 0.01f))
        assertEquals(2, multiKey.gutterVariantIndexAt(runs[2].startX + 1f))
        assertEquals(0, multiKey.gutterVariantIndexAt(runs[3].startX + 1f))
        assertEquals(0, multiKey.gutterVariantIndexAt(1e9f))
        assertTrue(multiKey.gutterVariantAt(runs[2].startX + 1f) === multiKey.gutterVariants[2])
    }

    @Test
    fun `views without a gutter have no variant`() {
        val fret = ChordSheetBuffer.decode(bytes("american_fret"))
        assertEquals(0f, fret.gutterWidth)
        assertNull(fret.gutterVariantAt(0f))
        // A static gutter is one variant everywhere.
        assertEquals(0, staff.gutterVariantIndexAt(-5f))
        assertEquals(0, staff.gutterVariantIndexAt(5000f))
    }

    // -- culling ------------------------------------------------------------------

    @Test
    fun `culling keeps every shape that reaches the viewport and few others`() {
        for (name in listOf("american_keyboard", "american_staff", "american_fret", "american_tab")) {
            val buffer = ChordSheetBuffer.decode(bytes(name))
            val left = 2000f
            val right = 2400f
            val visible = buffer.content.visibleIndices(left, right).toSet()
            buffer.content.ops.forEachIndexed { i, op ->
                val exact = exactExtent(op) ?: return@forEachIndexed
                if (exact.second >= left && exact.first <= right) {
                    assertTrue("$name op $i ($op) culled", i in visible)
                }
            }
            // A 400 dp window of a ~12,000 dp strip draws a small fraction (full-width
            // ops such as the staff lines always qualify).
            assertTrue("$name drew ${visible.size}/${buffer.content.size}", visible.size < buffer.content.size / 5)
        }
    }

    @Test
    fun `text and images are kept while any of them could show`() {
        val text = TextOp(100f, 0f, "Cmaj7", Anchor.E, false, 8f, "#000000", emptyList())
        val list = OpList(listOf(text, ImageOp(500f, 0f, "clef_treble:96", Anchor.NW, emptyList())))
        // Anchored east: the text paints left of x.
        assertTrue(list.intersects(0, 70f, 80f))
        assertTrue(list.intersects(1, 560f, 570f)) // the treble clef is 37 dp wide at 96
        assertTrue(!list.intersects(0, 300f, 400f))
    }

    private fun exactExtent(op: DrawOp): Pair<Float, Float>? = when (op) {
        is RectOp -> op.x to op.x + op.w
        is OvalOp -> op.x to op.x + op.w
        is LineOp -> xs(op.points)
        is PolygonOp -> xs(op.points)
        is TextOp, is ImageOp -> null
    }

    private fun xs(points: FloatArray): Pair<Float, Float> {
        var lo = Float.MAX_VALUE
        var hi = -Float.MAX_VALUE
        for (i in points.indices step 2) {
            lo = min(lo, points[i]); hi = max(hi, points[i])
        }
        return lo to hi
    }

    // -- lane labels ----------------------------------------------------------------

    @Test
    fun `lane labels clip short of the next label`() {
        val lane = staff.lane
        val clips = laneClipRights(lane)
        val texts = lane.ops.withIndex().filter { it.value is TextOp }
        val xs = texts.map { (it.value as TextOp).x }.sorted()
        for ((i, op) in texts) {
            val next = xs.firstOrNull { it > (op as TextOp).x + 0.5f }
            assertEquals(next?.minus(2f) ?: Float.POSITIVE_INFINITY, clips[i])
        }
        lane.ops.forEachIndexed { i, op -> if (op !is TextOp) assertEquals(Float.POSITIVE_INFINITY, clips[i]) }
    }

    // -- auto-scroll ------------------------------------------------------------------

    @Test
    fun `the playhead inside the comfortable band doesn't scroll`() {
        assertNull(scrollTarget(playheadX = 150f, viewportWidth = 400f, currentScroll = 0f, contentWidth = 5000f))
        assertNull(scrollTarget(100f, 400f, 0f, 5000f)) // exactly 25 %
        assertNull(scrollTarget(280f, 400f, 0f, 5000f)) // exactly 70 %
    }

    @Test
    fun `past 70 percent or behind 25 percent it snaps to 25 percent`() {
        assertEquals(200f, scrollTarget(300f, 400f, 0f, 5000f))
        assertEquals(900f, scrollTarget(1000f, 400f, 1200f, 5000f))
        // Clamped to the content's ends.
        assertEquals(0f, scrollTarget(50f, 400f, 300f, 5000f))
        assertEquals(4600f, scrollTarget(4990f, 400f, 3000f, 5000f))
        assertNull(scrollTarget(300f, 0f, 0f, 5000f))
        // Within half a dp of where it is: nothing to do.
        assertNull(scrollTarget(4990f, 400f, 4600f, 5000f))
    }

    // -- zoom -------------------------------------------------------------------------

    @Test
    fun `a pinch maps to the nearest number of desktop zoom steps`() {
        assertEquals(0, zoomStepsForScale(1.05f, 1.0))
        assertEquals(1, zoomStepsForScale(1.2f, 1.0))
        assertEquals(2, zoomStepsForScale(1.5f, 1.0))
        assertEquals(-1, zoomStepsForScale(0.8f, 1.0))
        assertEquals(-3, zoomStepsForScale(0.55f, 1.0))
        assertEquals(0, zoomStepsForScale(0f, 1.0))
        assertEquals(0, zoomStepsForScale(Float.NaN, 1.0))
    }

    @Test
    fun `zoom steps stop at the desktop bounds`() {
        // 1.0 → 2.5 is 5.03 steps of 1.2: 6 steps, the last clamped to 2.5.
        assertEquals(6, zoomStepsForScale(10f, 1.0))
        assertEquals(-4, zoomStepsForScale(0.01f, 1.0)) // 1.0 → 0.5 is 3.8 steps
        assertEquals(0, zoomStepsForScale(2f, 2.5))
        assertEquals(0, zoomStepsForScale(0.5f, 0.5))
        assertEquals(1, zoomStepsForScale(1.2f.pow(3), 2.4))
    }

    @Test
    fun `a pinch does nothing on a view that does not zoom`() {
        assertEquals(0, pinchZoomSteps(false, 2f, 1.0))
        assertEquals(2, pinchZoomSteps(true, 1.5f, 1.0))
    }

    @Test
    fun `a zoom keeps the music under the focus in place`() {
        // Content x 600 at viewport x 100 stays there when the strip doubles.
        assertEquals(1100f, rescaleScroll(500f, 100f, 5000f, 10000f, 400f))
        assertEquals(5f, rescaleScroll(10f, 0f, 5000f, 2500f, 400f))
        assertEquals(0f, rescaleScroll(10f, 300f, 5000f, 2500f, 400f)) // clamped to the start
        assertEquals(2100f, rescaleScroll(4600f, 200f, 5000f, 2500f, 400f)) // clamped to the end
    }

    // -- colours and requests ----------------------------------------------------------------

    @Test
    fun `Tk colours parse`() {
        assertEquals(0xFFFBFBF8.toInt(), parseTkColor("#fbfbf8"))
        assertEquals(0xFFFF8800.toInt(), parseTkColor("#f80"))
        assertEquals(0xFF000000.toInt(), parseTkColor("black"))
        assertNull(parseTkColor(""))
        assertNull(parseTkColor(null))
        assertNull(parseTkColor("#12345"))
        assertNull(parseTkColor("chartreuse"))
    }

    @Test
    fun `a request follows revision, view, zoom and height, not the playhead`() {
        val state = ChordSheetState(
            visible = true, height = 200, activeView = "staff", views = emptyList(),
            zoom = 1.0, zoomSupported = true, currentIndex = 3, songRevision = 7,
        )
        val request = SheetRequest.of(state, 130)
        assertEquals(SheetRequest(7, "staff", 1.0, 130), request)
        assertEquals(request, SheetRequest.of(state.copy(currentIndex = 9), 130))
        assertNull(SheetRequest.of(state.copy(visible = false), 130))
        assertNull(SheetRequest.of(state, 0))
        assertNull(SheetRequest.of(null, 130))
    }
}

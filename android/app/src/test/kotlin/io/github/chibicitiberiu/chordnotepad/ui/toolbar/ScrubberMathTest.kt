package io.github.chibicitiberiu.chordnotepad.ui.toolbar

import org.junit.Assert.assertEquals
import org.junit.Test

class ScrubberMathTest {
    @Test
    fun `steps floor like Python's floor division`() {
        assertEquals(0, ScrubberMath.steps(3f, 4f))
        assertEquals(1, ScrubberMath.steps(4f, 4f))
        assertEquals(2, ScrubberMath.steps(9.5f, 4f))
        assertEquals(-1, ScrubberMath.steps(-1f, 4f))
        assertEquals(-2, ScrubberMath.steps(-5f, 4f))
    }

    @Test
    fun `a drag moves from where it started`() {
        assertEquals(125.0, ScrubberMath.dragged(120.0, 20f, 4f), 0.0)
        assertEquals(97.5, ScrubberMath.dragged(100.5, -12f, 4f), 0.0)
    }

    @Test
    fun `percentages print like Python's g format`() {
        assertEquals("100", formatPct(100.0))
        assertEquals("87.5", formatPct(87.5))
        assertEquals("12.5", formatPct(12.5))
        assertEquals("133.333", formatPct(400.0 / 3))
        assertEquals("400", formatPct(400.0))
    }

    @Test
    fun `time signature choices match the session's`() {
        assertEquals((1..16).toList(), TIME_SIGNATURE_BEATS)
        assertEquals(listOf(1, 2, 4, 8, 16), TIME_SIGNATURE_UNITS)
    }
}

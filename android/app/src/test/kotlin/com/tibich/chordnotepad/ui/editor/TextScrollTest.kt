package com.tibich.chordnotepad.ui.editor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TextScrollTest {
    @Test
    fun `a chord in view doesn't scroll`() {
        assertNull(followChordScroll(100f, 140f, 0, 300, 1000))
        assertNull(followChordScroll(300f, 340f, 250, 300, 1000))
    }

    @Test
    fun `a chord out of view lands a third of the way in`() {
        // Off the right edge (the next chord on a long line).
        assertEquals(500 - 100, followChordScroll(500f, 540f, 0, 300, 1000))
        // Partly cut at the right edge counts as out of view.
        assertEquals(280 - 100, followChordScroll(280f, 320f, 0, 300, 1000))
        // The next line's first chord, scrolled sideways: back to the start.
        assertEquals(0, followChordScroll(12f, 30f, 400, 300, 1000))
        // Never past the end.
        assertEquals(1000, followChordScroll(1250f, 1290f, 0, 300, 1000))
    }

    @Test
    fun `an unmeasured view doesn't scroll`() {
        assertNull(followChordScroll(500f, 540f, 0, 0, 1000))
        assertNull(followCursorScroll(500f, 502f, 0, 0, 1000, 24f))
    }

    @Test
    fun `the cursor in view doesn't scroll`() {
        assertNull(followCursorScroll(100f, 102f, 0, 300, 1000, 24f))
        assertNull(followCursorScroll(274f, 276f, 0, 300, 1000, 24f))
    }

    @Test
    fun `typing past the right edge scrolls just enough`() {
        // Cursor at x 290 in a 300-wide view: needs 290 + 2 + 24 visible.
        assertEquals(16, followCursorScroll(290f, 292f, 0, 300, 1000, 24f))
        // One more character: a few pixels more.
        assertEquals(26, followCursorScroll(300f, 302f, 16, 300, 1000, 24f))
    }

    @Test
    fun `moving back past the left edge scrolls back`() {
        assertEquals(76, followCursorScroll(100f, 102f, 200, 300, 1000, 24f))
        // Home: back to the start.
        assertEquals(0, followCursorScroll(12f, 14f, 200, 300, 1000, 24f))
        // Already at 0 with the cursor in the left margin: nothing to do.
        assertNull(followCursorScroll(12f, 14f, 0, 300, 1000, 24f))
    }

    @Test
    fun `never scrolls past the end`() {
        assertEquals(1000, followCursorScroll(1290f, 1292f, 900, 300, 1000, 24f))
        assertNull(followCursorScroll(1290f, 1292f, 1000, 300, 1000, 24f))
    }
}

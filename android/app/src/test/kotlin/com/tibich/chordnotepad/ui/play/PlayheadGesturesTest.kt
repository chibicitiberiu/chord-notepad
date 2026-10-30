package com.tibich.chordnotepad.ui.play

import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.ui.editor.PaintedSpan
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlayheadGesturesTest {
    // Two lines of chords, 20 px tall: G (0..10) and C (50..60) on line 1, Em (5..25) on line 2.
    private val g = ChordBox(0, 1, 0f, 0f, 10f, 20f)
    private val c = ChordBox(8, 9, 50f, 0f, 60f, 20f)
    private val em = ChordBox(20, 22, 5f, 40f, 25f, 60f)
    private val boxes = listOf(g, c, em)

    @Test
    fun `a tap on a chord plays it, a tap elsewhere goes to the nearest`() {
        assertEquals(PlayTap.OnChord(8), resolveTap(boxes, 55f, 10f, slop = 4f))
        assertEquals(PlayTap.OnChord(8), resolveTap(boxes, 62f, 10f, slop = 4f))
        assertEquals(PlayTap.Nearest(8), resolveTap(boxes, 80f, 10f, slop = 4f))
        assertEquals(PlayTap.Nearest(0), resolveTap(boxes, 20f, 10f, slop = 4f))
        assertNull(resolveTap(emptyList(), 0f, 0f, 4f))
    }

    @Test
    fun `nearest prefers the same line`() {
        // Under C horizontally but on line 2's height: Em is on that line.
        assertEquals(em, nearestChord(boxes, 55f, 50f))
        // Between the lines, closer to line 1.
        assertEquals(c, nearestChord(boxes, 55f, 25f))
    }

    @Test
    fun `the marker is grabbed around its left edge only`() {
        assertTrue(grabsMarker(c, 50f, 10f, grabWidth = 24f))
        assertTrue(grabsMarker(c, 40f, -8f, grabWidth = 24f))
        assertFalse(grabsMarker(c, 70f, 10f, grabWidth = 24f))
        assertFalse(grabsMarker(c, 50f, 40f, grabWidth = 24f))
        assertFalse(grabsMarker(null, 50f, 10f, grabWidth = 24f))
    }

    @Test
    fun `a scrub moves chord by chord`() {
        assertNull(scrubTarget(boxes, current = 8, x = 52f, y = 5f))
        assertEquals(20, scrubTarget(boxes, current = 8, x = 10f, y = 45f))
        assertEquals(0, scrubTarget(boxes, current = 8, x = 2f, y = 5f))
    }

    @Test
    fun `the marker sits on the playhead's chord or the next one`() {
        val spans = listOf(
            PaintedSpan(30, 32, SpanKind.CHORD),
            PaintedSpan(0, 1, SpanKind.CHORD),
            PaintedSpan(10, 14, SpanKind.DIRECTIVE),
            PaintedSpan(5, 7, SpanKind.CHORD_INVALID),
        )
        val chords = playableChords(spans)
        assertEquals(listOf(0, 30), chords.map { it.start })
        assertEquals(0, markerChord(chords, 0)?.start)
        assertEquals(30, markerChord(chords, 31)?.start)
        assertEquals(30, markerChord(chords, 12)?.start)
        assertNull(markerChord(chords, 40))
        assertNull(markerChord(chords, null))
    }

    @Test
    fun `a long-press explains only red and faded directives`() {
        val spans = listOf(
            PaintedSpan(20, 28, SpanKind.DIRECTIVE_REDUNDANT),
            PaintedSpan(0, 8, SpanKind.DIRECTIVE_INVALID),
            PaintedSpan(9, 18, SpanKind.DIRECTIVE),
            PaintedSpan(30, 31, SpanKind.CHORD),
        )
        assertEquals(listOf(0, 20), explainableDirectives(spans).map { it.start })
        val red = ChordBox(0, 8, 0f, 0f, 80f, 20f)
        assertEquals(red, explainableAt(listOf(red), 82f, 10f, slop = 4f))
        assertNull(explainableAt(listOf(red), 90f, 10f, slop = 4f))
    }
}

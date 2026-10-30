package com.tibich.chordnotepad.ui.editor

import com.tibich.chordnotepad.bridge.SpanKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SpanShiftTest {
    private fun chord(start: Int, end: Int) = PaintedSpan(start, end, SpanKind.CHORD)

    @Test
    fun `diff finds the one changed range`() {
        assertNull(diffTexts("C G Am", "C G Am"))
        assertEquals(TextChange(2, 2, 3), diffTexts("C G", "C xG"))
        assertEquals(TextChange(2, 3, 2), diffTexts("C xG", "C G"))
        assertEquals(TextChange(0, 3, 2), diffTexts("C G", "Dm"))
        assertEquals(TextChange(3, 3, 6), diffTexts("C G", "C G Am"))
    }

    @Test
    fun `diff never splits a surrogate pair`() {
        // Same high surrogate, different low ones: the change starts at the pair.
        val change = diffTexts("a😀b", "a😁b")!!
        assertEquals(1, change.start)
        assertEquals(3, change.oldEnd)
    }

    @Test
    fun `spans after an insert shift, spans before stay`() {
        val spans = listOf(chord(0, 1), chord(4, 6))
        assertEquals(listOf(chord(0, 1), chord(6, 8)), spans.shiftedBy(TextChange(2, 2, 4)))
    }

    @Test
    fun `typing at a span edge stays outside it, inside joins it`() {
        val am = listOf(chord(4, 6))
        assertEquals(listOf(chord(5, 7)), am.shiftedBy(TextChange(4, 4, 5))) // before "Am"
        assertEquals(listOf(chord(4, 6)), am.shiftedBy(TextChange(6, 6, 7))) // after it
        assertEquals(listOf(chord(4, 7)), am.shiftedBy(TextChange(5, 5, 6))) // A|m
    }

    @Test
    fun `deleting a span's text removes or trims it`() {
        val am = listOf(chord(4, 6))
        assertEquals(emptyList<PaintedSpan>(), am.shiftedBy(TextChange(3, 7, 3)))
        assertEquals(listOf(chord(4, 5)), am.shiftedBy(TextChange(5, 6, 5)))
        assertEquals(listOf(chord(3, 4)), am.shiftedBy(TextChange(3, 5, 3)))
    }
}

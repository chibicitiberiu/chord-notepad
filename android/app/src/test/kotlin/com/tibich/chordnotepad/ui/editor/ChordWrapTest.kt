package com.tibich.chordnotepad.ui.editor

import com.tibich.chordnotepad.bridge.SpanKind
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ChordWrapTest {
    private fun chord(text: String, token: String, from: Int = 0): PaintedSpan {
        val start = text.indexOf(token, from)
        return PaintedSpan(start, start + token.length, SpanKind.CHORD)
    }

    @Test
    fun `a slash chord gets a joiner after the slash, plain chords none`() {
        // L7: D/F# wrapped as "D/" and "F#".
        val text = "G/B  C/E  D/F#  G/D\nword-word C"
        val spans = listOf(chord(text, "G/B"), chord(text, "C/E"), chord(text, "D/F#"), chord(text, "G/D"), chord(text, "C", 25))
        assertArrayEquals(intArrayOf(2, 7, 12, 18), chordJoinPoints(text, spans))
        // A hyphen in the lyrics isn't a chord's: it still wraps there.
        assertTrue(chordJoinPoints("word-word", emptyList()).isEmpty())
        val minus = "Bb-7 C+"
        assertArrayEquals(intArrayOf(3), chordJoinPoints(minus, listOf(chord(minus, "Bb-7"), chord(minus, "C+"))))
    }

    @Test
    fun `offsets move past the joiners before them`() {
        val text = "D/F# G/B"
        val joined = JoinedText(chordJoinPoints(text, listOf(chord(text, "D/F#"), chord(text, "G/B"))))
        val shown = joined.display(text)
        assertEquals("D/${WORD_JOINER}F# G/${WORD_JOINER}B", shown)
        // Every character keeps its own place in the drawn text.
        for (i in text.indices) assertEquals("at $i", text[i], shown[joined.toDisplay(i)])
        assertEquals(shown.length, joined.toDisplay(text.length))
        // Span starts and ends: D/F# is [0, 4) → [0, 5); G/B [5, 8) → [6, 10).
        assertEquals(listOf(0, 5, 6, 10), listOf(0, 4, 5, 8).map(joined::toDisplay))
        val none = JoinedText(IntArray(0))
        assertEquals(text, none.display(text))
        assertEquals(3, none.toDisplay(3))
    }

    @Test
    fun `a copy and a paste leave no joiners in the song`() {
        // The field copies the text as drawn; the joiners must not travel.
        assertEquals("G/B C", withoutJoiners("G/${WORD_JOINER}B C"))
        assertEquals("G/B", normalizeSongText("G/${WORD_JOINER}B"))
        assertTrue(needsNormalizing("G/${WORD_JOINER}B"))
    }

    @Test
    fun `a copied clip is rewritten only when it holds joiners`() {
        assertNull(joinerFreeTexts(listOf("G/B C", null)))
        assertEquals(listOf("D/F# G", "x", ""), joinerFreeTexts(listOf("D/${WORD_JOINER}F# G", "x", null)))
        // What the rewrite puts back doesn't trigger another one.
        assertNull(joinerFreeTexts(joinerFreeTexts(listOf("D/${WORD_JOINER}F#"))!!))
    }

    @Test
    fun `joiners are drawn only while the text wraps`() {
        val text = "D/F# G/B"
        val spans = listOf(chord(text, "D/F#"), chord(text, "G/B"))
        assertArrayEquals(intArrayOf(2, 7), joinPoints(text, spans, wordWrap = true))
        // Unwrapped, nothing can split a chord: the drawn text is the song's.
        assertTrue(joinPoints(text, spans, wordWrap = false).isEmpty())
    }
}

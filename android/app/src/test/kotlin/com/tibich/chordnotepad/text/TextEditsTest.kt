package com.tibich.chordnotepad.text

import com.tibich.chordnotepad.bridge.Span
import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.bridge.TextEdited
import com.tibich.chordnotepad.bridge.UndoPolicy
import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.random.Random

class TextEditsTest {
    private fun edit(start: Int, end: Int, replacement: String, cursor: Int) =
        TextEdited(textRevision = 1, start = start, end = end, replacement = replacement, undo = UndoPolicy.PLAIN, cursor = cursor)

    /** What Python does: splice code points, cursor in code points of the result. */
    private fun reference(text: String, e: TextEdited): Pair<String, Int> {
        val cps = text.codePoints().toArray()
        val out = StringBuilder()
        cps.take(e.start).forEach { out.appendCodePoint(it) }
        out.append(e.replacement)
        cps.drop(e.end).forEach { out.appendCodePoint(it) }
        val result = out.toString()
        return result to result.offsetByCodePoints(0, e.cursor)
    }

    private fun check(text: String, e: TextEdited) {
        val u = e.toUtf16(text)
        val (expectedText, expectedCursor) = reference(text, e)
        assertEquals(expectedText, applyEdit(text, u))
        assertEquals("cursor for $e on \"$text\"", expectedCursor, u.cursor)
    }

    @Test
    fun `insert after an emoji`() {
        // "😀 C" is 3 code points; insert "{bpm: 90}\n" at code point 2 (before C).
        val text = "😀 C"
        val e = edit(2, 2, "{bpm: 90}\n", cursor = 2 + 10)
        val u = e.toUtf16(text)
        assertEquals(3, u.start)
        assertEquals(3, u.end)
        assertEquals("😀 {bpm: 90}\nC", applyEdit(text, u))
        assertEquals(13, u.cursor)
    }

    @Test
    fun `whole-text replace (transpose) with emoji on both sides`() {
        val text = "C 🎸 G\n😀 Am"
        val replacement = "D 🎸 A\n😀 Bm"
        val cps = text.codePointCount(0, text.length)
        check(text, edit(0, cps, replacement, cursor = replacement.codePointCount(0, replacement.length)))
    }

    @Test
    fun `cursor before, inside and after the replacement`() {
        val text = "a😀b😀c"
        check(text, edit(2, 3, "X😀Y", cursor = 1)) // before
        check(text, edit(2, 3, "X😀Y", cursor = 4)) // inside, after the emoji
        check(text, edit(2, 3, "X😀Y", cursor = 6)) // after, past the second emoji
    }

    @Test
    fun `random edits match the code-point reference`() {
        val rnd = Random(7)
        repeat(500) {
            val text = randomText(rnd, rnd.nextInt(0, 30))
            val cps = text.codePointCount(0, text.length)
            val start = rnd.nextInt(0, cps + 1)
            val end = rnd.nextInt(start, cps + 1)
            val replacement = randomText(rnd, rnd.nextInt(0, 8))
            val newLength = cps - (end - start) + replacement.codePointCount(0, replacement.length)
            check(text, edit(start, end, replacement, cursor = rnd.nextInt(0, newLength + 1)))
        }
    }

    @Test
    fun `offsets past the end are clamped`() {
        val u = edit(5, 9, "x", cursor = 50).toUtf16("ab")
        assertEquals(2, u.start)
        assertEquals(2, u.end)
    }

    @Test
    fun `span ranges in UTF-16`() {
        val text = "😀 Am 😀 C"
        val m = OffsetMapper.of(text)
        val am = Span(2, 4, SpanKind.CHORD).toUtf16Range(m)
        assertEquals("Am", text.substring(am.start, am.end))
        val c = Span(7, 8, SpanKind.CHORD).toUtf16Range(m)
        assertEquals("C", text.substring(c.start, c.end))
    }
}

package com.tibich.chordnotepad.text

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class OffsetMapperTest {
    @Test
    fun `ascii and BMP text map one to one`() {
        val text = "Am  C/G  Ré  漢字\nG7"
        val m = OffsetMapper.of(text)
        assertTrue(m.isIdentity)
        assertEquals(text.length, m.codePointLength)
        for (i in 0..text.length) {
            assertEquals(i, m.toUtf16(i))
            assertEquals(i, m.toCodePoint(i))
        }
    }

    @Test
    fun `emoji takes two UTF-16 units but one code point`() {
        val text = "a😀b" // a(0) 😀(1,2) b(3)
        val m = OffsetMapper.of(text)
        assertFalse(m.isIdentity)
        assertEquals(4, m.utf16Length)
        assertEquals(3, m.codePointLength)
        assertEquals(listOf(0, 1, 3, 4), (0..3).map(m::toUtf16))
        assertEquals(listOf(0, 1, 1, 2, 3), (0..4).map(m::toCodePoint))
    }

    @Test
    fun `a UTF-16 offset inside a pair maps to the pair's code point`() {
        val m = OffsetMapper.of("😀😀")
        assertEquals(0, m.toCodePoint(1))
        assertEquals(1, m.toCodePoint(3))
    }

    @Test
    fun `flags and ZWJ sequences are several code points`() {
        val text = "🇷🇴 👩‍👩‍👧 C" // flag = 2 pairs; family = 3 pairs + 2 ZWJ
        val m = OffsetMapper.of(text)
        assertEquals(text.codePointCount(0, text.length), m.codePointLength)
        val cOffset = text.indexOf('C')
        assertEquals(cOffset, m.toUtf16(m.toCodePoint(cOffset)))
        assertEquals(text.codePointCount(0, cOffset), m.toCodePoint(cOffset))
    }

    @Test
    fun `lone surrogates count as one code point each, like Java and Python`() {
        val text = "x\uD83Dy\uDE00z" // a high and a low that aren't a pair
        val m = OffsetMapper.of(text)
        assertTrue(m.isIdentity)
        assertEquals(text.codePointCount(0, text.length), m.codePointLength)
    }

    @Test
    fun `out of range offsets are clamped`() {
        val m = OffsetMapper.of("a😀")
        assertEquals(0, m.toUtf16(-5))
        assertEquals(3, m.toUtf16(99))
        assertEquals(0, m.toCodePoint(-1))
        assertEquals(2, m.toCodePoint(99))
    }

    @Test
    fun `empty text`() {
        val m = OffsetMapper.of("")
        assertEquals(0, m.toUtf16(0))
        assertEquals(0, m.toCodePoint(0))
    }

    @Test
    fun `matches the JDK on random text with surrogate pairs`() {
        val rnd = Random(42)
        repeat(300) {
            val text = randomText(rnd, rnd.nextInt(0, 60))
            val m = OffsetMapper.of(text)
            val cps = text.codePointCount(0, text.length)
            assertEquals(cps, m.codePointLength)
            for (cp in 0..cps) {
                val u = text.offsetByCodePoints(0, cp)
                assertEquals("toUtf16($cp) in \"$text\"", u, m.toUtf16(cp))
                assertEquals("toCodePoint($u) in \"$text\"", cp, m.toCodePoint(u))
            }
        }
    }
}

/** Mixed ASCII, BMP and supplementary characters (and the odd lone surrogate). */
internal fun randomText(rnd: Random, length: Int): String = buildString {
    repeat(length) {
        when (rnd.nextInt(10)) {
            0, 1 -> appendCodePoint(0x1F600 + rnd.nextInt(0x40)) // emoji
            2 -> appendCodePoint(0x1D11E) // musical symbol G clef
            3 -> append('é')
            4 -> append('\n')
            else -> append('a' + rnd.nextInt(26))
        }
    }
}

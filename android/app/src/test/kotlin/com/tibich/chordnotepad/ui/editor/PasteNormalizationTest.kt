package com.tibich.chordnotepad.ui.editor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The cases of tests/test_paste_normalization.py (normalize_song_text). */
class PasteNormalizationTest {
    @Test
    fun `line endings become LF`() {
        assertEquals("[Chorus]\nC  G\n", normalizeSongText("[Chorus]\r\nC  G\r\n"))
        assertEquals("line one\nline two", normalizeSongText("line one\rline two"))
        assertEquals("a\nb\nc\n", normalizeSongText("a\r\nb\nc\r"))
    }

    @Test
    fun `non-breaking spaces become spaces, zero-width characters go`() {
        assertEquals("C  G", normalizeSongText("C \u00a0G"))
        assertEquals("Cm", normalizeSongText("\ufeffC\u200bm"))
    }

    @Test
    fun `plain text is unchanged`() {
        val text = "{title: Song}\n[Verse]\nC G Am F\nlyrics here 😀\n"
        assertEquals(text, normalizeSongText(text))
        assertFalse(needsNormalizing(text))
        assertTrue(needsNormalizing("a\r\n"))
    }
}

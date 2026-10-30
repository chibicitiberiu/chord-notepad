package com.tibich.chordnotepad.ui.help

import com.tibich.chordnotepad.bridge.QuickStartBlock
import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.bridge.Span
import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.ui.settings.Fixtures
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class QuickStartModelTest {
    @Test
    fun `the pager walks the pages and stops at the ends`() {
        var pager = QuickStartPager(3)
        assertTrue(pager.isFirst)
        assertFalse(pager.isLast)
        assertEquals(0, pager.previous().current)
        pager = pager.next().next()
        assertEquals(2, pager.current)
        assertTrue(pager.isLast)
        assertEquals(2, pager.next().current)
        assertEquals(1, pager.previous().current)
    }

    @Test
    fun `a restored index outside the tour is clamped`() {
        assertEquals(1, QuickStartPager(2, index = 9).current)
        assertEquals(0, QuickStartPager(2, index = -3).current)
        assertTrue(QuickStartPager(1).let { it.isFirst && it.isLast })
    }

    private fun snippet(text: String, vararg spans: Span) =
        QuickStartBlock(kind = "snippet", text = text, notation = "american", spans = spans.toList())

    @Test
    fun `snippet runs use UTF-16 offsets for code point spans`() {
        // The emoji is two UTF-16 units but one code point: "C" starts at 2 in Kotlin, 1 in Python.
        val block = snippet("🎵C Am", Span(1, 2, SpanKind.CHORD), Span(3, 5, SpanKind.CHORD))
        assertEquals(
            listOf(SnippetRun(2, 3, SpanKind.CHORD), SnippetRun(4, 6, SpanKind.CHORD)),
            snippetRuns(block),
        )
    }

    @Test
    fun `empty spans are dropped and higher priority kinds paint last`() {
        val block = snippet(
            "{bpm: 90} C",
            Span(10, 11, SpanKind.CHORD),
            Span(0, 9, SpanKind.DIRECTIVE),
            Span(4, 4, SpanKind.COMMENT),
            Span(0, 9, SpanKind.CHORD_INVALID),
        )
        val runs = snippetRuns(block)
        assertEquals(3, runs.size)
        // CHORD < CHORD_INVALID < DIRECTIVE in the editor's priority order.
        assertEquals(listOf(SpanKind.CHORD, SpanKind.CHORD_INVALID, SpanKind.DIRECTIVE), runs.map { it.kind })
    }

    private fun settings(show: Boolean): SettingsState =
        Fixtures.settings.let { it.copy(values = it.values.copy(showQuickStartOnStartup = show)) }

    @Test
    fun `the tour opens on its own only when the setting says so, decided once per process`() {
        assertEquals(QuickStartLaunch.Decision(open = false, decided = false), QuickStartLaunch.decide(null, false))
        assertEquals(QuickStartLaunch.Decision(open = true, decided = true), QuickStartLaunch.decide(settings(true), false))
        assertEquals(QuickStartLaunch.Decision(open = false, decided = true), QuickStartLaunch.decide(settings(false), false))
        // Already decided: turning the setting on later (Settings, the tour's own box) opens nothing.
        assertEquals(QuickStartLaunch.Decision(open = false, decided = true), QuickStartLaunch.decide(settings(true), true))
    }

    @Test
    fun `guide links stay inside the bundled origin or leave for the browser`() {
        assertTrue(HelpLinks.isInternal(HelpLinks.START_URL))
        assertTrue(HelpLinks.isInternal("https://appassets.androidplatform.net/assets/help/settings.html#voicings"))
        assertFalse(HelpLinks.isInternal("https://appassets.androidplatform.net/other/index.html"))
        assertFalse(HelpLinks.isInternal("https://example.com/assets/help/index.html"))
        assertTrue(HelpLinks.isExternal("https://github.com/chibicitiberiu/chord-notepad"))
        assertTrue(HelpLinks.isExternal("mailto:a@b.c"))
        assertFalse(HelpLinks.isExternal(HelpLinks.START_URL))
        assertFalse(HelpLinks.isExternal("file:///etc/passwd"))
    }
}

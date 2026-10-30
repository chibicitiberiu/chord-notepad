package com.tibich.chordnotepad.lifecycle

import android.content.Intent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.TimeZone

class AppLaunchTest {
    private val fromHistory = Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY
    private val newTask = Intent.FLAG_ACTIVITY_NEW_TASK

    @Test
    fun `launch kinds`() {
        assertEquals(LaunchKind.DIRECT, LaunchRules.classify(false, Intent.ACTION_MAIN, newTask))
        assertEquals(LaunchKind.DOCUMENT, LaunchRules.classify(false, Intent.ACTION_VIEW, 0))
        // Recents replays the intent that started the task: the user opened the app.
        assertEquals(LaunchKind.DIRECT, LaunchRules.classify(false, Intent.ACTION_VIEW, fromHistory))
        assertEquals(LaunchKind.DIRECT, LaunchRules.classify(false, null, fromHistory))
        // Recreated: never a startup screen, whatever the intent.
        assertEquals(LaunchKind.RESTORE, LaunchRules.classify(true, Intent.ACTION_MAIN, 0))
        assertEquals(LaunchKind.RESTORE, LaunchRules.classify(true, Intent.ACTION_VIEW, 0))
        // Anything else (no action, another action): no startup screen either.
        assertEquals(LaunchKind.RESTORE, LaunchRules.classify(false, null, 0))
        assertEquals(LaunchKind.RESTORE, LaunchRules.classify(false, Intent.ACTION_SEND, 0))
        assertEquals(listOf("direct", "document", "restore"), LaunchKind.entries.map { it.wire })
    }

    @Test
    fun `a file is opened once, never from recents or on recreation`() {
        assertTrue(LaunchRules.shouldOpen(false, Intent.ACTION_VIEW, 0, "content"))
        assertFalse(LaunchRules.shouldOpen(true, Intent.ACTION_VIEW, 0, "content"))
        assertFalse(LaunchRules.shouldOpen(false, Intent.ACTION_VIEW, fromHistory, "content"))
        assertFalse(LaunchRules.shouldOpen(false, Intent.ACTION_VIEW, 0, "file"))
        assertFalse(LaunchRules.shouldOpen(false, Intent.ACTION_VIEW, 0, null))
        assertFalse(LaunchRules.shouldOpen(false, Intent.ACTION_MAIN, 0, "content"))
    }

    @Test
    fun `local ISO dates`() {
        val utc = TimeZone.getTimeZone("UTC")
        val bucharest = TimeZone.getTimeZone("Europe/Bucharest")
        val lateEvening = 1_793_394_000_000L // 2026-10-30 21:00 UTC, 23:00 in Bucharest
        assertEquals("2026-10-30", LocalDates.iso(lateEvening, utc))
        assertEquals("2026-10-30", LocalDates.iso(lateEvening, bucharest))
        val later = lateEvening + 2 * 3_600_000L // 23:00 UTC, 01:00 the next day in Bucharest
        assertEquals("2026-10-30", LocalDates.iso(later, utc))
        assertEquals("2026-10-31", LocalDates.iso(later, bucharest))
        assertEquals("1970-01-01", LocalDates.iso(0L, utc))
    }

    @Test
    fun `an override changes what is sent`() {
        val facts = LaunchFacts("2026-10-30", "2026-10-30", false)
        val override = LaunchFactsOverride { _, f -> f.copy(today = "2026-11-06", canAskForSupport = true) }
        assertEquals(LaunchFacts("2026-11-06", "2026-10-30", true), override.adjust(null, facts))
    }
}

package io.github.chibicitiberiu.chordnotepad.ui.main

import io.github.chibicitiberiu.chordnotepad.bridge.DocumentState
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ModeControllerTest {
    private fun doc(id: String?, modified: Boolean = false, name: String = id ?: "Untitled") =
        DocumentState(displayName = name, isModified = modified, title = name, documentId = id)

    @Test
    fun `a saved song opens in Play, an untitled one in Edit`() {
        val saved = ModeController()
        saved.onDocument(doc("content://a"))
        assertEquals(AppMode.PLAY, saved.mode.value)

        val untitled = ModeController()
        untitled.onDocument(doc(null))
        assertEquals(AppMode.EDIT, untitled.mode.value)
    }

    @Test
    fun `an opened song switches to Play, a new one to Edit`() {
        val m = ModeController()
        m.onDocument(doc(null))
        m.expectOpen()
        m.onDocument(doc("content://a"))
        assertEquals(AppMode.PLAY, m.mode.value)

        m.expectNew()
        m.onDocument(doc(null))
        assertEquals(AppMode.EDIT, m.mode.value)
    }

    @Test
    fun `saving an untitled song keeps the mode`() {
        val m = ModeController()
        m.onDocument(doc(null))
        m.expectSave()
        m.onDocument(doc("content://saved"))
        assertEquals(AppMode.EDIT, m.mode.value)
    }

    @Test
    fun `a cancelled open followed by Save As doesn't switch`() {
        val m = ModeController()
        m.onDocument(doc(null))
        m.expectOpen()
        // The picker was cancelled: nothing arrived. Then Save As.
        m.expectSave()
        m.onDocument(doc("content://b"))
        assertEquals(AppMode.EDIT, m.mode.value)
    }

    @Test
    fun `the user's choice sticks over later document states of the same song`() {
        val m = ModeController()
        m.onDocument(doc("content://a"))
        m.select(AppMode.EDIT, PlaybackStatus.IDLE)
        m.onDocument(doc("content://a", modified = true))
        assertEquals(AppMode.EDIT, m.mode.value)
    }

    @Test
    fun `switching to Edit while playing or paused stops playback`() {
        val m = ModeController(AppMode.PLAY)
        assertTrue(m.select(AppMode.EDIT, PlaybackStatus.PLAYING))
        assertEquals(AppMode.EDIT, m.mode.value)
        m.select(AppMode.PLAY, PlaybackStatus.IDLE)
        assertTrue(m.select(AppMode.EDIT, PlaybackStatus.PAUSED))
        m.select(AppMode.PLAY, PlaybackStatus.IDLE)
        assertFalse(m.select(AppMode.EDIT, PlaybackStatus.IDLE))
        assertFalse(m.select(AppMode.PLAY, PlaybackStatus.PLAYING))
    }
}

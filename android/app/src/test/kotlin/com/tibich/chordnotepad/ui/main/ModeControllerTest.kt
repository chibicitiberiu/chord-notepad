package com.tibich.chordnotepad.ui.main

import com.tibich.chordnotepad.bridge.DocumentState
import com.tibich.chordnotepad.bridge.PlaybackStatus
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

    @Test
    fun `Open with into a running app switches to Play and counts the open`() {
        // P1: the Edit tab was kept, and nothing told the pages to close.
        val m = ModeController()
        m.onDocument(doc(null))
        m.select(AppMode.EDIT, PlaybackStatus.IDLE)
        assertEquals(0, m.opened.value)
        m.expectOpen()
        // The unsaved-changes question doesn't change the document: no open yet.
        m.onDocument(doc(null, modified = true))
        assertEquals(0, m.opened.value)
        m.onDocument(doc("content://a"))
        assertEquals(AppMode.PLAY, m.mode.value)
        assertEquals(1, m.opened.value)
        // Later changes of the same song aren't opens.
        m.onDocument(doc("content://a", modified = true))
        assertEquals(1, m.opened.value)
    }

    @Test
    fun `a cold start from Open with counts the open once`() {
        val m = ModeController()
        m.expectOpen()
        m.onDocument(doc("content://a"))
        assertEquals(AppMode.PLAY, m.mode.value)
        assertEquals(1, m.opened.value)
        // A rename (expectSave) changes the id but isn't an open.
        m.expectSave()
        m.onDocument(doc("content://b"))
        assertEquals(1, m.opened.value)
    }

    @Test
    fun `the saved tab comes back after process death, not after a rotation`() {
        // L13: a killed process restored the draft (untitled) in Edit, though Play was open.
        val fresh = ModeController()
        fresh.restore(AppMode.PLAY)
        fresh.onDocument(doc(null, modified = true))
        assertEquals(AppMode.PLAY, fresh.mode.value)

        val running = ModeController()
        running.onDocument(doc("content://a"))
        running.select(AppMode.EDIT, PlaybackStatus.IDLE)
        running.restore(AppMode.PLAY)
        assertEquals(AppMode.EDIT, running.mode.value)
    }

    @Test
    fun `Open with the song that is already open lands in Play too`() {
        // After "Don't save" the same song comes back unmodified, same id.
        val m = ModeController()
        m.onDocument(doc("content://t"))
        m.select(AppMode.EDIT, PlaybackStatus.IDLE)
        m.onDocument(doc("content://t", modified = true))
        m.expectOpen("content://t", doc("content://t", modified = true))
        assertEquals(AppMode.EDIT, m.mode.value)
        m.onDocument(doc("content://t"))
        assertEquals(AppMode.PLAY, m.mode.value)
        assertEquals(1, m.opened.value)

        // Unmodified already: no document state will come, so at once.
        m.select(AppMode.EDIT, PlaybackStatus.IDLE)
        m.expectOpen("content://t", doc("content://t"))
        assertEquals(AppMode.PLAY, m.mode.value)
        assertEquals(2, m.opened.value)
        // A save of the same song isn't an open.
        m.select(AppMode.EDIT, PlaybackStatus.IDLE)
        m.onDocument(doc("content://t", modified = true))
        m.expectSave()
        m.onDocument(doc("content://t"))
        assertEquals(AppMode.EDIT, m.mode.value)
    }
}

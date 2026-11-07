package com.tibich.chordnotepad.ui.main

import com.tibich.chordnotepad.bridge.PlaybackState
import com.tibich.chordnotepad.bridge.PlaybackStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlaybackUiTest {
    private fun state(status: PlaybackStatus, chord: Int? = null) = PlaybackState(status, chordIndex = chord)

    @Test
    fun `starting is playing before the first chord`() {
        assertEquals(true, state(PlaybackStatus.PLAYING).isStarting)
        assertEquals(false, state(PlaybackStatus.PLAYING, chord = 0).isStarting)
        assertEquals(false, state(PlaybackStatus.PAUSED).isStarting)
        assertEquals(false, state(PlaybackStatus.IDLE).isStarting)
        assertEquals(false, (null as PlaybackState?).isStarting)
    }

    @Test
    fun `the screen stays on only while playing or starting`() {
        assertEquals(true, keepScreenOn(state(PlaybackStatus.PLAYING)))
        assertEquals(true, keepScreenOn(state(PlaybackStatus.PLAYING, chord = 3)))
        assertEquals(false, keepScreenOn(state(PlaybackStatus.PAUSED, chord = 3)))
        assertEquals(false, keepScreenOn(state(PlaybackStatus.IDLE)))
        assertEquals(false, keepScreenOn(null))
    }

    @Test
    fun `snackbars stay in Edit, Play uses the status line and clears the player`() {
        assertEquals(true, statusSnackbarsShown(AppMode.EDIT))
        assertEquals(false, statusSnackbarsShown(AppMode.PLAY))
        assertEquals(0f, snackbarClearanceDp(AppMode.EDIT, false))
        assertEquals(PLAYER_HEIGHT_DP, snackbarClearanceDp(AppMode.PLAY, false))
        assertEquals(0f, snackbarClearanceDp(AppMode.PLAY, true))
    }

    @Test
    fun `a stopped song's status is no snackbar in Edit`() {
        // L14: Edit while playing stops the song; its "Bar 5/8" came up in Edit.
        assertFalse(statusSnackbarAllowed(AppMode.EDIT, nowMs = 10_400, stoppedAtMs = 10_000))
        assertTrue(statusSnackbarAllowed(AppMode.EDIT, nowMs = 12_000, stoppedAtMs = 10_000))
        assertTrue(statusSnackbarAllowed(AppMode.EDIT, nowMs = 5, stoppedAtMs = null))
        assertFalse(statusSnackbarAllowed(AppMode.PLAY, nowMs = 12_000, stoppedAtMs = null))
    }
}

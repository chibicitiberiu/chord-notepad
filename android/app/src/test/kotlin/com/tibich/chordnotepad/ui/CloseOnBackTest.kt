package com.tibich.chordnotepad.ui

import androidx.activity.OnBackPressedCallback
import androidx.activity.OnBackPressedDispatcher
import androidx.core.util.Consumer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CloseOnBackTest {
    private var fallbacks = 0
    private var asked = 0
    private val enabledChanges = mutableListOf<Boolean>()
    private val dispatcher = OnBackPressedDispatcher({ fallbacks++ }, Consumer { enabledChanges += it })
    private var modified = false

    private fun install() = CloseOnBackCallback(dispatcher, { modified }) { asked++ }
        .also(dispatcher::addCallback)

    @Test
    fun `becoming modified doesn't re-register the window callback`() {
        // L1: the window callback is registered again whenever the dispatcher
        // goes from no enabled callback to one, which puts it above the
        // keyboard's. Typing the first character must not cause that.
        install()
        val before = enabledChanges.toList()
        modified = true
        modified = false
        modified = true
        assertEquals(before, enabledChanges)
        assertTrue(dispatcher.hasEnabledCallbacks())
    }

    @Test
    fun `modified asks about the changes`() {
        install()
        modified = true
        dispatcher.onBackPressed()
        assertEquals(1, asked)
        assertEquals(0, fallbacks)
    }

    @Test
    fun `unmodified falls through to the system and stays enabled`() {
        val callback = install()
        dispatcher.onBackPressed()
        assertEquals(0, asked)
        assertEquals(1, fallbacks)
        assertTrue(callback.isEnabled)
        dispatcher.onBackPressed()
        assertEquals(2, fallbacks)
    }

    @Test
    fun `unmodified falls through to an older callback before the system`() {
        var older = 0
        dispatcher.addCallback(object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                older++
            }
        })
        install()
        dispatcher.onBackPressed()
        assertEquals(1, older)
        assertEquals(0, fallbacks)
    }

    @Test
    fun `a newer callback (the drawer, a sheet) still wins`() {
        install()
        var drawer = 0
        dispatcher.addCallback(object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                drawer++
            }
        })
        modified = true
        dispatcher.onBackPressed()
        assertEquals(1, drawer)
        assertEquals(0, asked)
    }
}

package com.tibich.chordnotepad.ui

import androidx.compose.ui.input.key.Key
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ShortcutsTest {
    @Test
    fun `the desktop's window shortcuts`() {
        assertEquals(Shortcut.NEW, shortcutFor(Key.N, ctrl = true, shift = false))
        assertEquals(Shortcut.OPEN, shortcutFor(Key.O, ctrl = true, shift = false))
        assertEquals(Shortcut.SAVE, shortcutFor(Key.S, ctrl = true, shift = false))
        assertEquals(Shortcut.SAVE_AS, shortcutFor(Key.S, ctrl = true, shift = true))
        assertEquals(Shortcut.FONT_BIGGER, shortcutFor(Key.Equals, ctrl = true, shift = false))
        assertEquals(Shortcut.FONT_BIGGER, shortcutFor(Key.Plus, ctrl = true, shift = true))
        assertEquals(Shortcut.FONT_SMALLER, shortcutFor(Key.Minus, ctrl = true, shift = false))
        assertEquals(Shortcut.FONT_RESET, shortcutFor(Key.Zero, ctrl = true, shift = false))
    }

    @Test
    fun `F1 opens the user guide with or without modifiers`() {
        assertEquals(Shortcut.HELP, shortcutFor(Key.F1, ctrl = false, shift = false))
        assertEquals(Shortcut.HELP, shortcutFor(Key.F1, ctrl = true, shift = true))
    }

    @Test
    fun `plain keys and the text field's own shortcuts pass through`() {
        assertNull(shortcutFor(Key.S, ctrl = false, shift = false))
        assertNull(shortcutFor(Key.Z, ctrl = true, shift = false))
        assertNull(shortcutFor(Key.A, ctrl = true, shift = false))
    }

    @Test
    fun `undo and redo are taken before the soft keyboard`() {
        // B11: Gboard answered Ctrl+Z by deleting a character.
        assertEquals(EditShortcut.UNDO, editShortcutFor(Key.Z, ctrl = true, shift = false))
        assertEquals(EditShortcut.REDO, editShortcutFor(Key.Z, ctrl = true, shift = true))
        assertEquals(EditShortcut.REDO, editShortcutFor(Key.Y, ctrl = true, shift = false))
        assertNull(editShortcutFor(Key.Z, ctrl = false, shift = false))
        assertNull(editShortcutFor(Key.Y, ctrl = true, shift = true))
        assertNull(editShortcutFor(Key.C, ctrl = true, shift = false))
    }
}

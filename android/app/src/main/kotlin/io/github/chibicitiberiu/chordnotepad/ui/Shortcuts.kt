package io.github.chibicitiberiu.chordnotepad.ui

import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEvent
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.isCtrlPressed
import androidx.compose.ui.input.key.isShiftPressed
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.type

/** The desktop's window shortcuts that M4 covers (main_window.py, `bind_all`), and F1 for the User Guide. */
enum class Shortcut { NEW, OPEN, SAVE, SAVE_AS, FONT_BIGGER, FONT_SMALLER, FONT_RESET, HELP }

/**
 * The shortcut for a key pressed with these modifiers, or null. Undo, redo,
 * cut, copy, paste and select all are the text field's own.
 */
fun shortcutFor(key: Key, ctrl: Boolean, shift: Boolean): Shortcut? {
    if (key == Key.F1) return Shortcut.HELP
    if (!ctrl) return null
    return when (key) {
        Key.N -> Shortcut.NEW
        Key.O -> Shortcut.OPEN
        Key.S -> if (shift) Shortcut.SAVE_AS else Shortcut.SAVE
        // Ctrl+= is the same key as Ctrl++ on most layouts.
        Key.Plus, Key.Equals, Key.NumPadAdd -> Shortcut.FONT_BIGGER
        Key.Minus, Key.NumPadSubtract -> Shortcut.FONT_SMALLER
        Key.Zero, Key.NumPad0 -> Shortcut.FONT_RESET
        else -> null
    }
}

/** Run the shortcut for [event] (key down only; F1 calls [onHelp]); true if there was one. */
fun MainActions.handleShortcut(event: KeyEvent, onHelp: () -> Unit = {}): Boolean {
    if (event.type != KeyEventType.KeyDown) return false
    val shortcut = shortcutFor(event.key, event.isCtrlPressed, event.isShiftPressed) ?: return false
    when (shortcut) {
        Shortcut.NEW -> newDocument()
        Shortcut.OPEN -> openDocument()
        Shortcut.SAVE -> save()
        Shortcut.SAVE_AS -> saveAs()
        Shortcut.FONT_BIGGER -> stepFontSize(1)
        Shortcut.FONT_SMALLER -> stepFontSize(-1)
        Shortcut.FONT_RESET -> resetFontSize()
        Shortcut.HELP -> onHelp()
    }
    return true
}

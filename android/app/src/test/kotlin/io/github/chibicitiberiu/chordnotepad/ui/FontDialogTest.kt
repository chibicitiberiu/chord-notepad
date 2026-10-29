package io.github.chibicitiberiu.chordnotepad.ui

import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorFontKind
import io.github.chibicitiberiu.chordnotepad.ui.editor.fontKindFor
import org.junit.Assert.assertEquals
import org.junit.Test

class FontDialogTest {
    @Test
    fun `the configured family is kept when it already is the chosen kind`() {
        assertEquals("TkFixedFont", configFamilyFor(EditorFontKind.MONOSPACE, "TkFixedFont"))
        assertEquals("Consolas", configFamilyFor(EditorFontKind.MONOSPACE, "Consolas"))
        assertEquals("Times New Roman", configFamilyFor(EditorFontKind.SERIF, "Times New Roman"))
    }

    @Test
    fun `another kind sends a family that maps back to it`() {
        for (kind in EditorFontKind.entries) {
            for (current in listOf("TkFixedFont", "Sans", "Serif", "Arial")) {
                assertEquals(kind, fontKindFor(configFamilyFor(kind, current)))
            }
        }
        assertEquals("TkFixedFont", configFamilyFor(EditorFontKind.MONOSPACE, "Arial"))
        assertEquals("Sans", configFamilyFor(EditorFontKind.SANS, "TkFixedFont"))
        assertEquals("Serif", configFamilyFor(EditorFontKind.SERIF, "TkFixedFont"))
    }

    @Test
    fun `sizes are the desktop's 6 to 72`() {
        assertEquals(6, FONT_SIZES.first)
        assertEquals(72, FONT_SIZES.last)
    }
}

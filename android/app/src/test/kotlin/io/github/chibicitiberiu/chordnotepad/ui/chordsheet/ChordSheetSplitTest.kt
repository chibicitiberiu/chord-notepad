package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ChordSheetSplitTest {
    @Test
    fun `plenty of room keeps the stored height`() {
        assertEquals(220f, chordSheetHeightDp(220f, availableDp = 700f, windowHeightDp = 890f)!!, 0.01f)
    }

    @Test
    fun `never more than 60 percent of the window`() {
        assertEquals(534f, chordSheetHeightDp(900f, availableDp = 900f, windowHeightDp = 890f)!!, 0.01f)
    }

    @Test
    fun `the editor keeps its minimum when the keyboard takes the room`() {
        // 330 dp left (keyboard up): 330 - 120 (editor) - 56 (below) = 154 for the sheet.
        assertEquals(154f, chordSheetHeightDp(300f, availableDp = 330f, windowHeightDp = 890f)!!, 0.01f)
    }

    @Test
    fun `no room for a usable sheet hides it`() {
        assertNull(chordSheetHeightDp(220f, availableDp = 250f, windowHeightDp = 890f))
    }
}

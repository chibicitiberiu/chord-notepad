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
        // 330 dp left (keyboard up): 330 - 96 (editor) - 56 (below) = 178 for the sheet.
        assertEquals(178f, chordSheetHeightDp(300f, availableDp = 330f, windowHeightDp = 890f)!!, 0.01f)
    }

    @Test
    fun `a short sheet is still shown above the hide limit (phone in landscape)`() {
        // 250 dp left: 250 - 96 - 56 = 98, below the usual 120 minimum but shown.
        assertEquals(98f, chordSheetHeightDp(348f, availableDp = 250f, windowHeightDp = 411f)!!, 0.01f)
    }

    @Test
    fun `no room for a usable sheet hides it`() {
        assertNull(chordSheetHeightDp(220f, availableDp = 220f, windowHeightDp = 890f))
    }
}

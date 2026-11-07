package com.tibich.chordnotepad.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class KeyboardSafeDialogTest {
    @Test
    fun `the dialog fits the room above the keyboard`() {
        // L4: phone landscape with the keyboard up leaves about 115 dp; the
        // field went under the keyboard with the stock dialog.
        assertEquals(DialogShape.SIDE, dialogShape(914f, 115f))
        // Phone portrait with the keyboard, a tablet with it, no keyboard.
        assertEquals(DialogShape.ROOMY, dialogShape(411f, 500f))
        assertEquals(DialogShape.ROOMY, dialogShape(1280f, 420f))
        assertEquals(DialogShape.TIGHT, dialogShape(1280f, 300f))
        // Too narrow to put the buttons beside the field: tight, scrolling.
        assertEquals(DialogShape.TIGHT, dialogShape(360f, 200f))
        assertEquals(DialogShape.SIDE, dialogShape(480f, 239f))
        assertEquals(DialogShape.TIGHT, dialogShape(480f, 240f))
    }
}

package com.tibich.chordnotepad.ui.main

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenLayoutTest {
    @Test
    fun `phone portrait in Edit has a two-line header and no chord sheet`() {
        val l = ScreenLayout.of(360f, 640f, AppMode.EDIT, sheetVisible = true)
        assertTrue(l.phone)
        assertFalse(l.oneLineHeader)
        assertFalse(l.sheetBelow)
        assertFalse(l.sideBySide)
    }

    @Test
    fun `phone landscape in Edit puts tabs and ribbon on one line`() {
        assertTrue(ScreenLayout.of(640f, 360f, AppMode.EDIT, true).oneLineHeader)
        // Play has no ribbon: the normal app bar, with the title.
        assertFalse(ScreenLayout.of(640f, 360f, AppMode.PLAY, true).oneLineHeader)
        // Tablets keep the two-line header in landscape.
        assertFalse(ScreenLayout.of(1280f, 800f, AppMode.EDIT, true).oneLineHeader)
    }

    @Test
    fun `the chord sheet is a Play-mode view, below in portrait and beside in landscape`() {
        assertTrue(ScreenLayout.of(360f, 640f, AppMode.PLAY, true).sheetBelow)
        assertFalse(ScreenLayout.of(360f, 640f, AppMode.PLAY, false).sheetBelow)
        val side = ScreenLayout.of(1280f, 800f, AppMode.PLAY, true)
        assertTrue(side.sideBySide)
        assertTrue(side.compactPlayer)
        assertFalse(side.sheetBelow)
        assertTrue(ScreenLayout.of(640f, 360f, AppMode.PLAY, true).sideBySide)
        assertFalse(ScreenLayout.of(640f, 360f, AppMode.PLAY, false).sideBySide)
    }

    @Test
    fun `the header collapses only in Edit with the keyboard up and little room`() {
        assertTrue(collapseHeader(AppMode.EDIT, imeVisible = true, textRoomDp = 120f))
        assertFalse(collapseHeader(AppMode.EDIT, imeVisible = true, textRoomDp = 170f))
        assertFalse(collapseHeader(AppMode.EDIT, imeVisible = false, textRoomDp = 50f))
        assertFalse(collapseHeader(AppMode.PLAY, imeVisible = true, textRoomDp = 50f))
    }

    @Test
    fun `the side column stays within 30 to 70 percent`() {
        assertEquals(0.5f, clampSideFraction(Float.NaN))
        assertEquals(0.3f, clampSideFraction(0.1f))
        assertEquals(0.7f, clampSideFraction(0.95f))
        assertEquals(0.4f, sideFractionAt(handleX = 600f, rowWidth = 1000f), 1e-6f)
        assertEquals(0.7f, sideFractionAt(handleX = 10f, rowWidth = 1000f))
        assertEquals(SIDE_FRACTION_DEFAULT, sideFractionAt(5f, 0f))
    }

    @Test
    fun `ribbon edges show the fades and the chevron`() {
        assertEquals(RibbonEdges(fadeLeft = false, more = false), RibbonEdges.of(0, 0))
        assertEquals(RibbonEdges(fadeLeft = false, more = true), RibbonEdges.of(0, 200))
        assertEquals(RibbonEdges(fadeLeft = true, more = true), RibbonEdges.of(100, 200))
        assertEquals(RibbonEdges(fadeLeft = true, more = false), RibbonEdges.of(199, 200))
    }
}

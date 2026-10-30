package com.tibich.chordnotepad.ui.chordsheet

import androidx.compose.ui.graphics.Color
import com.tibich.chordnotepad.ui.theme.AppColors
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ChordSheetThemeTest {
    private fun lum(c: Color) = (maxOf(c.red, c.green, c.blue) + minOf(c.red, c.green, c.blue)) / 2f

    @Test
    fun `light keeps the buffer's colours`() {
        val c = Color(0xFF22323A)
        assertEquals(c, themedSheetColor("#22323a", c, AppColors.Light))
    }

    @Test
    fun `dark lightens the hands' bars to the spec's colours`() {
        assertEquals(Color(0xFF78A6D8), themedSheetColor("#2a6f8a", Color(0xFF2A6F8A), AppColors.Dark))
        assertEquals(Color(0xFFD09A6C), themedSheetColor("#8A5A3A", Color(0xFF8A5A3A), AppColors.Dark))
    }

    @Test
    fun `dark flips neutral inks and keeps hues readable`() {
        val ink = themedSheetColor("#22323a", Color(0xFF22323A), AppColors.Dark)
        assertTrue(lum(ink) > 0.7f)
        val grid = themedSheetColor("#b9c2c7", Color(0xFFB9C2C7), AppColors.Dark)
        assertTrue(lum(grid) < 0.4f)
        val voice = themedSheetColor("#a04848", Color(0xFFA04848), AppColors.Dark)
        assertTrue(lum(voice) >= 0.65f)
        assertTrue(voice.red > voice.green)
    }
}

class ChordSheetPaperTest {
    @Test
    fun `the strip's paper is the sheet surface in both themes`() {
        assertEquals(AppColors.Light.surfaceLow, themedSheetColor("#fbfbf8", Color(0xFFFBFBF8), AppColors.Light))
        assertEquals(AppColors.Dark.surfaceLow, themedSheetColor("#FBFBF8", Color(0xFFFBFBF8), AppColors.Dark))
    }
}

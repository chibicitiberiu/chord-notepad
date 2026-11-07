package com.tibich.chordnotepad.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScrollHintTest {
    @Test
    fun `the fade shows while there is more below`() {
        // L9: rows ending exactly at the edge gave no hint.
        assertTrue(moreBelow(0, 300))
        assertTrue(moreBelow(297, 300))
        assertFalse(moreBelow(298, 300))
        assertFalse(moreBelow(0, 0))
    }
}

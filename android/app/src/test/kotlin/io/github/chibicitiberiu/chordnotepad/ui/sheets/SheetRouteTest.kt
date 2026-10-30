package io.github.chibicitiberiu.chordnotepad.ui.sheets

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SheetRouteTest {
    @Test
    fun `instrument sheet goes families, family, back to families, closed`() {
        val families = SheetRoute.Instrument()
        val guitar = families.open(3)
        assertEquals(SheetRoute.Instrument(3), guitar)
        assertEquals(families, guitar.back())
        assertEquals(SheetRoute.None, families.back())
    }

    @Test
    fun `the speed dialog goes back to the speed sheet`() {
        assertEquals(SheetRoute.Speed(), SheetRoute.Speed(manual = true).back())
        assertEquals(SheetRoute.None, SheetRoute.Speed().back())
        assertEquals(SheetRoute.None, SheetRoute.Voicing.back())
    }

    @Test
    fun `routes survive a rotation`() {
        val all = listOf(
            SheetRoute.None, SheetRoute.SongDefaults, SheetRoute.Voicing, SheetRoute.Instrument(),
            SheetRoute.Instrument(15), SheetRoute.Speed(), SheetRoute.Speed(true), SheetRoute.Insert,
            SheetRoute.Rename, SheetRoute.Transpose(true), SheetRoute.Transpose(false), SheetRoute.Identify,
        )
        for (r in all) assertEquals(r, SheetRoute.restore(r.save()))
        assertEquals(SheetRoute.None, SheetRoute.restore("nonsense"))
    }

    @Test
    fun `typed speed is a whole percentage from 25 to 400`() {
        assertEquals(125, parseSpeedPct("125"))
        assertEquals(125, parseSpeedPct(" 125 % "))
        assertEquals(25, parseSpeedPct("25"))
        assertEquals(400, parseSpeedPct("400"))
        assertNull(parseSpeedPct("24"))
        assertNull(parseSpeedPct("401"))
        assertNull(parseSpeedPct("1.5"))
        assertNull(parseSpeedPct("-50"))
        assertNull(parseSpeedPct(""))
        assertNull(parseSpeedPct("abc"))
        assertNull(parseSpeedPct("99999999999"))
    }

    @Test
    fun `the slider snaps to 5 percent steps`() {
        assertEquals(125, snapSpeedPct(123.4f))
        assertEquals(25, snapSpeedPct(10f))
        assertEquals(400, snapSpeedPct(420f))
    }

    @Test
    fun `the speed badge shows the factor when not 100 percent`() {
        assertNull(speedBadge(100.0))
        assertEquals("1.25×", speedBadge(125.0))
        assertEquals("0.5×", speedBadge(50.0))
        assertEquals("2×", speedBadge(200.0))
        assertEquals("0.25×", speedBadge(25.0))
    }

    @Test
    fun `song defaults pill and what Write into song can do`() {
        assertEquals("90 · 3/4 · G", SongDefaults.summaryOf("90", "3/4", "G"))
        assertEquals("120 · 4/4", SongDefaults.summaryOf("120", "4/4", ""))
        val allSet = SongDefaults(
            SongDefaultValue("90", true, 0), SongDefaultValue("3/4", true, 10), SongDefaultValue("G", true, 22), "",
        )
        assertEquals(false, allSet.anythingToWrite)
        assertTrue(allSet.copy(time = SongDefaultValue("4/4", false)).anythingToWrite)
        // An empty default key writes nothing.
        assertEquals(false, allSet.copy(key = SongDefaultValue("", false)).anythingToWrite)
        // While a song plays or is paused nothing can be written.
        val unset = allSet.copy(time = SongDefaultValue("4/4", false))
        assertTrue(unset.canWrite)
        assertEquals(false, unset.copy(lockedReason = "Stop playback").canWrite)
        assertEquals("{bpm: 90}", directiveCode(SongDefaultKind.TEMPO, "90"))
        assertEquals("{time: 3/4}", directiveCode(SongDefaultKind.TIME, "3/4"))
    }
}

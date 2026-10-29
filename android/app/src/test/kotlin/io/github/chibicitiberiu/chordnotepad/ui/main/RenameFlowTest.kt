package io.github.chibicitiberiu.chordnotepad.ui.main

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RenameFlowTest {
    @Test
    fun `the field starts with the name without its extension`() {
        assertEquals("Amazing Grace", renameFieldText("Amazing Grace.txt"))
        assertEquals("Untitled", renameFieldText("Untitled"))
        assertEquals("song.v2", renameFieldText("song.v2.cho"))
    }

    @Test
    fun `the file name keeps the document's extension`() {
        assertEquals("Hymn.txt", renamedFileName(" Hymn ", "Amazing Grace.txt"))
        assertEquals("Hymn.cho", renamedFileName("Hymn", "old.cho"))
        assertEquals("Hymn.txt", renamedFileName("Hymn", "Untitled"))
        assertEquals("Hymn.pro", renamedFileName("Hymn.pro", "old.txt"))
        assertEquals("", renamedFileName("  ", "old.txt"))
    }

    @Test
    fun `problems disable Rename`() {
        assertEquals(RenameProblem.EMPTY, renameProblem(" ", "a.txt"))
        assertEquals(RenameProblem.BAD_CHARACTER, renameProblem("a/b", "a.txt"))
        assertEquals(RenameProblem.UNCHANGED, renameProblem("a", "a.txt"))
        assertNull(renameProblem("b", "a.txt"))
    }

    @Test
    fun `a refused rename offers Save As with the typed name`() {
        val f = RenameFailure(name = "Hymn", reason = "This storage can't rename files.", canSaveAs = true)
        assertEquals("Hymn", f.name)
    }
}

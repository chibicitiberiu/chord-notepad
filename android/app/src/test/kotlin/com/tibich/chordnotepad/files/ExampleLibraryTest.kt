package com.tibich.chordnotepad.files

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class ExampleLibraryTest {
    @get:Rule val tmp = TemporaryFolder()

    private val assets = mapOf("x.txt" to "one".toByteArray(), "a.txt" to "two".toByteArray())
    private val dir by lazy { File(tmp.root, "examples") }
    private val library by lazy {
        ExampleLibrary({ listOf("x.txt", "notes.md", "a.txt", "img.png") }, { assets.getValue(it) }, dir)
    }

    @Test
    fun `names keeps only txt files, sorted`() {
        assertEquals(listOf("a.txt", "x.txt"), library.names())
    }

    @Test
    fun `the first tap writes the copy`() {
        val file = library.copyFor("x.txt", null)
        assertEquals(File(dir, "x.txt"), file)
        assertArrayEquals("one".toByteArray(), file.readBytes())
    }

    @Test
    fun `a tap on an unchanged copy returns it and leaves it alone`() {
        val first = library.copyFor("x.txt", null)
        first.setLastModified(1_000_000_000L)
        val again = library.copyFor("x.txt", null)
        assertEquals(first, again)
        assertEquals(1_000_000_000L, again.lastModified())
        assertEquals(listOf("x.txt"), dir.list()!!.toList())
    }

    @Test
    fun `an edited copy gives a numbered one`() {
        library.copyFor("x.txt", null).writeText("edited")
        val second = library.copyFor("x.txt", null)
        assertEquals("x (2).txt", second.name)
        assertArrayEquals("one".toByteArray(), second.readBytes())
    }

    @Test
    fun `an edited first copy and a pristine second reopen the second`() {
        library.copyFor("x.txt", null).writeText("edited")
        val second = library.copyFor("x.txt", null)
        assertEquals(second, library.copyFor("x.txt", null))
        assertEquals(setOf("x.txt", "x (2).txt"), dir.list()!!.toSet())
    }

    @Test
    fun `two edited copies give the third`() {
        library.copyFor("x.txt", null).writeText("edited")
        library.copyFor("x.txt", null).writeText("edited too")
        assertEquals("x (3).txt", library.copyFor("x.txt", null).name)
    }

    @Test
    fun `the skipped id is passed over even when identical`() {
        val first = library.copyFor("x.txt", null)
        val next = library.copyFor("x.txt", library.idFor(first))
        assertEquals("x (2).txt", next.name)
        assertArrayEquals("one".toByteArray(), first.readBytes())
    }

    @Test
    fun `ids are non-canonical and stable`() {
        val id = library.idFor(library.fileFor("x.txt"))
        assertTrue(id, id.startsWith("file:/"))
        assertEquals(File(dir, "x.txt").toURI().toASCIIString(), id)
        assertEquals(id, library.idFor(library.copyFor("x.txt", null)))
        assertEquals(id, library.idFor(library.copyFor("x.txt", null)))
    }

    @Test
    fun `a name with spaces has an escaped id`() {
        val id = library.idFor(File(dir, "x (2).txt"))
        assertTrue(id, "%20" in id && ' ' !in id)
    }
}

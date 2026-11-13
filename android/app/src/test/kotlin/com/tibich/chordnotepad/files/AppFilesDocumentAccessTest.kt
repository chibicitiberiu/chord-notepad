package com.tibich.chordnotepad.files

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.FileNotFoundException

class AppFilesDocumentAccessTest {
    @get:Rule val tmp = TemporaryFolder()

    private val delegate = FakeDocumentAccess()
    private val root by lazy { File(tmp.root, "examples").also { it.mkdirs() } }
    private val access by lazy { AppFilesDocumentAccess(root, "Examples", delegate) }

    private fun idOf(file: File) = file.toURI().toASCIIString()

    private fun make(name: String, text: String): String {
        File(root, name).writeText(text)
        return idOf(File(root, name))
    }

    @Test
    fun `reads and writes round trip`() {
        val id = make("x.txt", "hello world")
        assertEquals("hello world", access.openInput(id).use { it.readBytes().decodeToString() })
        access.openOutput(id).use { it.write("hi".toByteArray()) }
        assertArrayEquals("hi".toByteArray(), File(root, "x.txt").readBytes())
        assertEquals(2L, access.size(id))
    }

    @Test
    fun `a missing file has no info and can't be read`() {
        val id = idOf(File(root, "gone.txt"))
        assertNull(access.query(id))
        try {
            access.openInput(id)
            fail("expected FileNotFoundException")
        } catch (e: FileNotFoundException) {
            // expected
        }
    }

    @Test
    fun `the location reads name and label`() {
        val id = make("x.txt", "a")
        val info = access.query(id)!!
        assertEquals("x.txt (Examples)", describeLocation(info, info.displayName!!))
    }

    @Test
    fun `grants are always held and nothing reaches the delegate`() {
        val id = make("x.txt", "a")
        assertTrue(access.canWrite(id))
        assertTrue(access.hasPersistedGrant(id))
        assertTrue(access.supportsRename(id))
        access.persistGrant(id)
        access.releaseGrant(id)
        assertTrue(delegate.grants.isEmpty())
        assertTrue(delegate.released.isEmpty())
    }

    @Test
    fun `rename moves the file and returns the new id`() {
        val id = make("x.txt", "a")
        val renamed = access.rename(id, "y.txt")
        assertEquals(idOf(File(root, "y.txt")), renamed)
        assertFalse(File(root, "x.txt").exists())
        assertEquals("a", File(root, "y.txt").readText())
    }

    @Test
    fun `rename onto an existing name is refused and keeps both files`() {
        val id = make("x.txt", "one")
        make("y.txt", "two")
        try {
            access.rename(id, "y.txt")
            fail("expected IllegalStateException")
        } catch (e: IllegalStateException) {
            // expected
        }
        assertEquals("one", File(root, "x.txt").readText())
        assertEquals("two", File(root, "y.txt").readText())
    }

    @Test
    fun `rename of a missing file or to a path is refused`() {
        try {
            access.rename(idOf(File(root, "gone.txt")), "y.txt")
            fail("expected FileNotFoundException")
        } catch (e: FileNotFoundException) {
            // expected
        }
        val id = make("x.txt", "a")
        try {
            access.rename(id, "../escape.txt")
            fail("expected IllegalArgumentException")
        } catch (e: IllegalArgumentException) {
            // expected
        }
        assertTrue(File(root, "x.txt").exists())
    }

    @Test
    fun `other ids go to the delegate`() {
        delegate.add("content://d/1", "a.txt", "remote")
        assertEquals("remote", access.openInput("content://d/1").use { it.readBytes().decodeToString() })
        assertEquals("a.txt", access.query("content://d/1")!!.displayName)
        assertTrue(access.hasPersistedGrant("content://d/1"))
        val outside = File(tmp.root, "elsewhere.txt")
        delegate.add(idOf(outside), "elsewhere.txt", "outside")
        assertEquals("outside", access.openInput(idOf(outside)).use { it.readBytes().decodeToString() })
    }

    @Test
    fun `escapes, hosts and queries are not owned and don't throw`() {
        val inside = make("x.txt", "a")
        val escape = idOf(File(root, "x.txt")).replace("/x.txt", "/../x.txt")
        for (id in listOf(escape, "file://host/${root.path}/x.txt", "$inside?q=1", "file:%zz", "file:")) {
            delegate.add(id, "d.txt", "delegated")
            assertEquals(id, "delegated", access.openInput(id).use { it.readBytes().decodeToString() })
        }
    }
}

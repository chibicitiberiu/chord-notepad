package com.tibich.chordnotepad.files

import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.DocumentStoreException
import com.tibich.chordnotepad.bridge.PickMode
import com.tibich.chordnotepad.bridge.RenameUnsupportedException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.FileNotFoundException
import java.io.File
import java.io.InputStream
import java.io.OutputStream

/** In-memory documents and grants. */
class FakeDocumentAccess : DocumentAccess {
    val content = mutableMapOf<String, ByteArray>()
    val names = mutableMapOf<String, String>()
    val grants = mutableSetOf<String>()
    val released = mutableListOf<String>()
    val denied = mutableSetOf<String>()
    /** Documents whose provider can't rename them. */
    val noRename = mutableSetOf<String>()

    fun add(id: String, name: String, text: String = "", granted: Boolean = true) {
        content[id] = text.toByteArray()
        names[id] = name
        if (granted) grants += id
    }

    override fun openInput(id: String): InputStream {
        if (id in denied) throw SecurityException("denied")
        return ByteArrayInputStream(content[id] ?: throw FileNotFoundException(id))
    }

    override fun openOutput(id: String): OutputStream {
        if (id in denied) throw SecurityException("denied")
        if (id !in content) throw FileNotFoundException("gone")
        return object : ByteArrayOutputStream() {
            override fun close() {
                content[id] = toByteArray() // truncating write
            }
        }
    }

    override fun query(id: String): DocumentInfo? =
        names[id]?.let { DocumentInfo(it, "com.example.docs", id.substringAfterLast('/'), "Example") }

    override fun hasPersistedGrant(id: String) = id in grants

    override fun persistGrant(id: String) {
        grants += id
    }

    override fun releaseGrant(id: String) {
        grants -= id
        released += id
    }

    override fun supportsRename(id: String) = id in names && id !in noRename

    /** Like ExternalStorageProvider: a path-like id that changes, a clash refused. */
    override fun rename(id: String, displayName: String): String? {
        if (id in denied) throw SecurityException("denied")
        if (id !in names) throw FileNotFoundException(id)
        val renamed = id.substringBeforeLast('/') + "/" + displayName
        val folder = id.substringBeforeLast('/')
        val clash = names.any { (other, name) -> other != id && name == displayName && other.startsWith("$folder/") }
        if (clash || (renamed != id && renamed in names)) throw IllegalStateException("Already exists")
        content[renamed] = content.remove(id)!!
        names.remove(id)
        names[renamed] = displayName
        grants -= id
        return renamed
    }
}

class SafDocumentStoreTest {
    @get:Rule val tmp = TemporaryFolder()

    private val access = FakeDocumentAccess()
    private val recentFile by lazy { RecentDocumentsFile(File(tmp.root, "recent.json")) }
    private val store by lazy { SafDocumentStore(access, recentFile, maxRecent = 3) }

    private fun ids(json: String) = Json.parseToJsonElement(json).jsonArray.map { it.jsonObject.getValue("id").jsonPrimitive.content }

    private fun expectError(fragment: String, block: () -> Unit) {
        try {
            block()
            fail("expected DocumentStoreException")
        } catch (e: DocumentStoreException) {
            assertTrue("'${e.message}' should contain '$fragment'", fragment in e.message!!)
        }
    }

    @Test
    fun `reads raw UTF-8, leaving normalization to Python`() {
        access.add("content://d/1", "a.txt", "﻿C  G\r\nAm F 😀")
        assertEquals("﻿C  G\r\nAm F 😀", store.readText("content://d/1"))
    }

    @Test
    fun `read errors use the desktop wording`() {
        access.add("content://d/bad", "bad.txt")
        access.content["content://d/bad"] = byteArrayOf(0x41, 0xC3.toByte(), 0x28) // invalid UTF-8
        expectError("Cannot read file (encoding issue): bad.txt (Example)") { store.readText("content://d/bad") }
        expectError("File not found: ") { store.readText("content://d/missing") }
        access.add("content://d/locked", "locked.txt")
        access.denied += "content://d/locked"
        expectError("Permission denied: locked.txt (Example)") { store.readText("content://d/locked") }
    }

    @Test
    fun `writes replace the old content`() {
        access.add("content://d/1", "a.txt", "a much longer old text")
        store.writeText("content://d/1", "G 😀")
        assertEquals("G 😀", access.content.getValue("content://d/1").decodeToString())
        store.writeBytes("content://d/1", byteArrayOf(1, 2))
        assertArrayEquals(byteArrayOf(1, 2), access.content.getValue("content://d/1"))
        access.denied += "content://d/1"
        expectError("Permission denied") { store.writeText("content://d/1", "x") }
        expectError("Failed to write file") { store.writeText("content://d/gone", "x") }
    }

    @Test
    fun `rename returns the new ref, keeps the grant and moves the recent entry`() {
        access.add("content://d/1", "a.txt", "C G")
        access.add("content://d/2", "b.txt")
        store.addRecent("content://d/2", "b.txt", "b.txt")
        store.addRecent("content://d/1", "a.txt", "a.txt")
        val json = Json.parseToJsonElement(store.rename("content://d/1", "Tune.txt")).jsonObject
        assertEquals("content://d/Tune.txt", json.getValue("id").jsonPrimitive.content)
        assertEquals("Tune.txt", json.getValue("display_name").jsonPrimitive.content)
        assertEquals("C G", access.content.getValue("content://d/Tune.txt").decodeToString())
        assertTrue("content://d/Tune.txt" in access.grants)
        assertEquals(listOf("content://d/Tune.txt", "content://d/2"), ids(store.recent()))
    }

    @Test
    fun `rename failures`() {
        access.add("content://d/1", "a.txt")
        access.add("content://d/2", "b.txt")
        access.noRename += "content://d/2"
        try {
            store.rename("content://d/2", "x.txt")
            fail("expected RenameUnsupportedException")
        } catch (e: RenameUnsupportedException) {
            assertTrue(e.message!!, "can't rename" in e.message!!)
        }
        expectError("Couldn't rename to b.txt") { store.rename("content://d/1", "b.txt") }
        access.denied += "content://d/1"
        expectError("Permission denied: a.txt (Example)") { store.rename("content://d/1", "c.txt") }
        expectError("can't rename") { store.rename("content://d/missing", "c.txt") }
    }

    @Test
    fun `availability follows the provider`() {
        access.add("content://d/1", "a.txt")
        assertTrue(store.isAvailable("content://d/1"))
        assertFalse(store.isAvailable("content://d/2"))
    }

    @Test
    fun `recent list, newest first, no duplicates, capped, grants of dropped entries released`() {
        for (i in 1..4) access.add("content://d/$i", "$i.txt")
        store.addRecent("content://d/1", "1.txt", "1.txt")
        store.addRecent("content://d/2", "2.txt", "2.txt")
        store.addRecent("content://d/1", "1.txt", "1.txt")
        store.addRecent("content://d/3", "3.txt", "3.txt")
        store.addRecent("content://d/4", "4.txt", "4.txt")
        assertEquals(listOf("content://d/4", "content://d/3", "content://d/1"), ids(store.recent()))
        assertEquals(listOf("content://d/2"), access.released)
    }

    @Test
    fun `recent prunes revoked grants and deleted documents, for good`() {
        for (i in 1..3) access.add("content://d/$i", "$i.txt")
        for (i in 3 downTo 1) store.addRecent("content://d/$i", "$i.txt", "$i.txt")
        access.grants -= "content://d/2" // revoked in system settings
        access.names -= "content://d/3" // deleted in the provider
        assertEquals(listOf("content://d/1"), ids(store.recent()))
        access.grants += "content://d/2"
        assertEquals(listOf("content://d/1"), ids(store.recent()))
        assertEquals(listOf("content://d/1"), recentFile.load().map { it.id })
    }

    @Test
    fun `recent JSON has the DocumentRef shape`() {
        access.add("content://d/1", "a.txt")
        store.addRecent("content://d/1", "a.txt", "a.txt (Example)")
        val item = Json.parseToJsonElement(store.recent()).jsonArray.single().jsonObject
        assertEquals(setOf("id", "display_name", "location"), item.keys)
    }

    @Test
    fun `a smaller cap trims on the next read`() {
        for (i in 1..3) {
            access.add("content://d/$i", "$i.txt")
            store.addRecent("content://d/$i", "$i.txt", "$i.txt")
        }
        store.setMaxRecent(1)
        assertEquals(listOf("content://d/3"), ids(store.recent()))
    }

    @Test
    fun `the open document keeps its grant even with a zero cap`() {
        access.add("content://d/1", "1.txt")
        store.setMaxRecent(0)
        store.addRecent("content://d/1", "1.txt", "1.txt")
        assertTrue(access.hasPersistedGrant("content://d/1"))
        assertEquals(emptyList<String>(), ids(store.recent()))
    }

    @Test
    fun `adopt persists the grant except for exports`() {
        access.add("content://d/song", "song.txt", granted = false)
        access.add("content://d/song.mid", "song.mid", granted = false)
        assertEquals(DocumentRef("content://d/song", "song.txt", "song.txt (Example)"), store.adopt("content://d/song", PickMode.SAVE))
        assertTrue(access.hasPersistedGrant("content://d/song"))
        store.adopt("content://d/song.mid", PickMode.EXPORT_MIDI)
        assertFalse(access.hasPersistedGrant("content://d/song.mid"))
    }

    @Test
    fun `describe gives the ref as JSON, or null when unreachable`() {
        access.add("content://d/1", "a.txt")
        assertEquals(
            Json.parseToJsonElement("""{"id": "content://d/1", "display_name": "a.txt", "location": "a.txt (Example)"}"""),
            Json.parseToJsonElement(store.describe("content://d/1")!!),
        )
        assertEquals(null, store.describe("content://d/gone"))
    }

    @Test
    fun `a corrupt recent file reads as empty`() {
        File(tmp.root, "recent.json").writeText("{not json")
        assertEquals(emptyList<DocumentRef>(), recentFile.load())
    }
}

class DocumentLocationsTest {
    @Test
    fun `local storage shows the path`() {
        val info = DocumentInfo("song.txt", "com.android.externalstorage.documents", "primary:Music/song.txt", "Files")
        assertEquals("Internal storage/Music/song.txt", describeLocation(info, "song.txt"))
        val sd = info.copy(documentId = "1A2B-3C4D:Songs/a.txt")
        assertEquals("Storage 1A2B-3C4D/Songs/a.txt", describeLocation(sd, "a.txt"))
    }

    @Test
    fun `other providers show name and provider`() {
        val info = DocumentInfo("song.txt", "com.example.cloud", "opaque123", "Cloud")
        assertEquals("song.txt (Cloud)", describeLocation(info, "song.txt"))
        assertEquals("song.txt", describeLocation(info.copy(providerLabel = null), "song.txt"))
    }

    @Test
    fun `fallback names from URIs`() {
        assertEquals(
            "song.txt",
            fallbackName("content://com.android.externalstorage.documents/document/primary%3AMusic%2Fsong.txt"),
        )
        assertEquals("42", fallbackName("content://media/external/file/42"))
    }
}

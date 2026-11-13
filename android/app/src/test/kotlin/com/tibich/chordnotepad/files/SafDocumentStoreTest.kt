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
    /** Sizes the provider reports (none: unknown). */
    val sizes = mutableMapOf<String, Long>()
    /** Documents granted read only (Open with). */
    val readOnly = mutableSetOf<String>()
    /** Grants that can't be persisted (an Open with grant without the persistable flag). */
    val notPersistable = mutableSetOf<String>()
    /** Providers by document (none: `com.example.docs`). */
    val authorities = mutableMapOf<String, String>()
    /**
     * Documents renamed under the same id. With [revokesOnRename] the
     * framework then revokes the "old" (same) URI, as for Downloads' `msf:`
     * documents; without, the provider answered null and the grant stays.
     */
    val keepsIdOnRename = mutableSetOf<String>()
    var revokesOnRename = false
    /** Documents the app can no longer reach (grant revoked by the provider). */
    val revoked = mutableSetOf<String>()
    /** Clashes get " (1)" like FileSystemProvider's buildUniqueFile, instead of a refusal. */
    var uniqueNamesOnClash = false
    /** `DocumentsContract.renameDocument` returning null (a swallowed failure). */
    val renameReturnsNull = mutableSetOf<String>()
    val renameCalls = mutableListOf<String>()

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
        if (id in revoked) null
        else names[id]?.let { DocumentInfo(it, authorities[id] ?: "com.example.docs", id.substringAfterLast('/'), "Example") }

    override fun size(id: String): Long? = sizes[id]

    override fun canWrite(id: String) = id !in readOnly

    override fun hasPersistedGrant(id: String) = id in grants

    override fun persistGrant(id: String) {
        if (id !in notPersistable) grants += id
    }

    override fun releaseGrant(id: String) {
        grants -= id
        released += id
    }

    override fun supportsRename(id: String) = id in names && id !in noRename

    /** Like ExternalStorageProvider: a path-like id that changes, a clash refused. */
    override fun rename(id: String, displayName: String): String? {
        renameCalls += id
        if (id in denied) throw SecurityException("denied")
        if (id !in names) throw FileNotFoundException(id)
        if (id in renameReturnsNull) return null
        if (id in keepsIdOnRename) {
            names[id] = displayName
            if (revokesOnRename) {
                grants -= id
                revoked += id
            }
            return id
        }
        val folder = id.substringBeforeLast('/')
        fun taken(name: String) = names.any { (other, n) -> other != id && n == name && other.startsWith("$folder/") }
        var name = displayName
        if (taken(name) && uniqueNamesOnClash) {
            name = displayName.substringBeforeLast('.') + " (1)." + displayName.substringAfterLast('.')
        }
        val renamed = "$folder/$name"
        if (taken(name) || (renamed != id && renamed in names)) throw IllegalStateException("Already exists")
        content[renamed] = content.remove(id)!!
        names.remove(id)
        names[renamed] = name
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
    fun `reads the bytes as they are, leaving decoding and normalization to Python`() {
        // C4: Python decodes (UTF-8, Windows-1252, a BOM), so a Latin-1 file opens.
        access.add("content://d/1", "a.txt")
        val latin1 = byteArrayOf(0xC9.toByte(), 0x74, 0xE9.toByte(), 0x0D, 0x0A, 0x41)
        access.content["content://d/1"] = latin1
        assertArrayEquals(latin1, store.readBytes("content://d/1"))
    }

    @Test
    fun `read errors use the desktop wording`() {
        expectError("File not found: ") { store.readBytes("content://d/missing") }
        access.add("content://d/locked", "locked.txt")
        access.denied += "content://d/locked"
        expectError("Permission denied: locked.txt (Example)") { store.readBytes("content://d/locked") }
    }

    @Test
    fun `a recent file that has gone is named from its entry and leaves the list`() {
        // B4: "File not found: 75" (the msf: id), and the entry stayed.
        access.add("content://d/75", "fntest.txt")
        access.add("content://d/other", "other.txt")
        store.addRecent("content://d/other", "other.txt", "other.txt (Example)")
        store.addRecent("content://d/75", "fntest.txt", "fntest.txt (Downloads)")
        access.content.remove("content://d/75")
        access.names.remove("content://d/75")
        expectError("File not found: fntest.txt (Downloads)") { store.readBytes("content://d/75") }
        assertEquals(listOf("content://d/other"), ids(store.recent()))
        assertFalse(access.hasPersistedGrant("content://d/75"))
    }

    @Test
    fun `reads stop at 5 MB, by the provider's size or by the bytes read`() {
        val limit = SafDocumentStore.MAX_READ_BYTES
        access.add("content://d/big", "big.txt")
        access.sizes["content://d/big"] = limit + 1L
        expectError("File too large to open (over 5 MB): big.txt (Example)") { store.readBytes("content://d/big") }
        // No size from the provider (or a wrong one): the read itself stops.
        access.add("content://d/huge", "huge.txt")
        access.content["content://d/huge"] = ByteArray(limit + 1) { 'a'.code.toByte() }
        expectError("File too large to open (over 5 MB): huge.txt (Example)") { store.readBytes("content://d/huge") }
        access.sizes["content://d/huge"] = 10
        expectError("File too large") { store.readBytes("content://d/huge") }
        access.content["content://d/huge"] = ByteArray(limit) { 'a'.code.toByte() }
        access.sizes.remove("content://d/huge")
        assertEquals(limit, store.readBytes("content://d/huge").size)
    }

    @Test
    fun `write access as the provider grants it`() {
        access.add("content://d/1", "a.txt")
        access.add("content://d/2", "b.txt")
        access.readOnly += "content://d/2"
        assertTrue(store.canWrite("content://d/1"))
        assertFalse(store.canWrite("content://d/2"))
    }

    @Test
    fun `an opened file whose grant can't be kept leaves the recent list`() {
        access.add("content://d/view", "v.txt", granted = false)
        access.notPersistable += "content://d/view"
        val ref = store.adopt("content://d/view", PickMode.OPEN)
        store.addRecent(ref.id, ref.displayName, ref.location)
        assertEquals(emptyList<String>(), ids(store.recent()))
    }

    @Test
    fun `an example copy stays in the recent list until its file is deleted`() {
        val root = File(tmp.root, "examples").also { it.mkdirs() }
        val file = File(root, "x.txt").also { it.writeText("song") }
        val id = file.toURI().toASCIIString()
        val appStore = SafDocumentStore(AppFilesDocumentAccess(root, "Examples", access), recentFile, maxRecent = 3)
        val ref = appStore.refFor(id)!!
        assertEquals("x.txt (Examples)", ref.location)
        appStore.addRecent(ref.id, ref.displayName, ref.location)
        assertEquals(listOf(id), ids(appStore.recent()))
        file.delete()
        assertEquals(emptyList<String>(), ids(appStore.recent()))
    }

    @Test
    fun `writes replace the old content`() {
        access.add("content://d/1", "a.txt", "a much longer old text")
        store.writeBytes("content://d/1", "G 😀".toByteArray())
        assertEquals("G 😀", access.content.getValue("content://d/1").decodeToString())
        store.writeBytes("content://d/1", byteArrayOf(1, 2))
        assertArrayEquals(byteArrayOf(1, 2), access.content.getValue("content://d/1"))
        access.denied += "content://d/1"
        expectError("Permission denied") { store.writeBytes("content://d/1", byteArrayOf(1)) }
        expectError("Failed to write file") { store.writeBytes("content://d/gone", byteArrayOf(1)) }
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

    private val downloads = "content://com.android.providers.downloads.documents/document"

    private fun ref(json: String) = Json.parseToJsonElement(json).jsonObject.let {
        DocumentRef(
            it.getValue("id").jsonPrimitive.content,
            it.getValue("display_name").jsonPrimitive.content,
            it.getValue("location").jsonPrimitive.content,
        )
    }

    @Test
    fun `a MediaStore file from Downloads is never renamed, so its grant and recent entry stay`() {
        val id = "$downloads/msf:33"
        access.add(id, "rb_dl.txt", "C G")
        access.authorities[id] = SafDocumentStore.DOWNLOADS_AUTHORITY
        access.keepsIdOnRename += id
        access.revokesOnRename = true // what would happen
        store.addRecent(id, "rb_dl.txt", "rb_dl.txt (Example)")
        try {
            store.rename(id, "Tune.txt")
            fail("expected RenameUnsupportedException")
        } catch (e: RenameUnsupportedException) {
            assertTrue(e.message!!, "Files opened from Downloads can't be renamed here" in e.message!!)
            assertTrue(e.message!!, "rb_dl.txt" in e.message!!)
            assertFalse(e.message!!, "Permission" in e.message!!)
        }
        assertEquals(emptyList<String>(), access.renameCalls)
        assertEquals("rb_dl.txt", access.names.getValue(id))
        assertTrue(access.hasPersistedGrant(id))
        assertEquals(listOf(id), ids(store.recent()))
    }

    @Test
    fun `Downloads documents that aren't MediaStore files still rename`() {
        // A DownloadManager id: the provider answers null, DocumentsContract
        // gives the same URI back and the grant stays.
        val id = "$downloads/42"
        access.add(id, "old.txt")
        access.authorities[id] = SafDocumentStore.DOWNLOADS_AUTHORITY
        access.keepsIdOnRename += id
        store.addRecent(id, "old.txt", "old.txt (Example)")
        val ref = ref(store.rename(id, "new.txt"))
        assertEquals(DocumentRef(id, "new.txt", "new.txt (Example)"), ref)
        assertTrue(access.hasPersistedGrant(id))
        assertEquals(listOf(ref), recentFile.load())
        assertEquals(listOf(id), ids(store.recent()))
    }

    @Test
    fun `a rename that costs the grant says so and keeps nothing unreadable`() {
        // Any provider that answers with the same id gets its grant revoked.
        access.add("content://d/1", "a.txt")
        access.keepsIdOnRename += "content://d/1"
        access.revokesOnRename = true
        store.addRecent("content://d/1", "a.txt", "a.txt (Example)")
        try {
            store.rename("content://d/1", "b.txt")
            fail("expected DocumentStoreException")
        } catch (e: RenameUnsupportedException) {
            fail("the rename went through; this isn't 'can't rename'")
        } catch (e: DocumentStoreException) {
            assertEquals(
                "Renamed to b.txt, but Android took away Chord Notepad's access to the file. " +
                    "Open it again (Open…) to keep working on it.",
                e.message,
            )
        }
        assertEquals(emptyList<String>(), ids(store.recent()))
    }

    @Test
    fun `a rename that keeps the id keeps the grant and shows the new name`() {
        access.add("content://d/1", "a.txt")
        access.add("content://d/2", "z.txt")
        access.keepsIdOnRename += "content://d/1"
        store.addRecent("content://d/1", "a.txt", "a.txt (Example)")
        store.addRecent("content://d/2", "z.txt", "z.txt (Example)")
        assertEquals(DocumentRef("content://d/1", "b.txt", "b.txt (Example)"), ref(store.rename("content://d/1", "b.txt")))
        assertTrue(access.hasPersistedGrant("content://d/1"))
        assertEquals(listOf("content://d/2", "content://d/1"), ids(store.recent()))
        assertEquals("b.txt", recentFile.load().last().displayName)
    }

    @Test
    fun `a clash the provider resolves gives the name it made`() {
        access.uniqueNamesOnClash = true
        access.add("content://d/a.txt", "a.txt", "C")
        access.add("content://d/Tune.txt", "Tune.txt", "G")
        store.addRecent("content://d/a.txt", "a.txt", "a.txt")
        val ref = ref(store.rename("content://d/a.txt", "Tune.txt"))
        assertEquals(DocumentRef("content://d/Tune (1).txt", "Tune (1).txt", "Tune (1).txt (Example)"), ref)
        assertEquals("G", access.content.getValue("content://d/Tune.txt").decodeToString())
        assertEquals(listOf(ref), recentFile.load())
    }

    @Test
    fun `a provider answering null changes nothing`() {
        access.add("content://d/1", "a.txt")
        access.renameReturnsNull += "content://d/1"
        store.addRecent("content://d/1", "a.txt", "a.txt (Example)")
        expectError("Couldn't rename a.txt (Example) to b.txt.") { store.rename("content://d/1", "b.txt") }
        assertTrue(access.hasPersistedGrant("content://d/1"))
        assertEquals(listOf(DocumentRef("content://d/1", "a.txt", "a.txt (Example)")), recentFile.load())
    }

    @Test
    fun `the Downloads rule matches only MediaStore files of the Downloads provider`() {
        fun info(authority: String, docId: String?) = DocumentInfo("a.txt", authority, docId, null)
        val dl = SafDocumentStore.DOWNLOADS_AUTHORITY
        assertTrue(SafDocumentStore.renameRevokesAccess(info(dl, "msf:33")))
        assertFalse(SafDocumentStore.renameRevokesAccess(info(dl, "42")))
        assertFalse(SafDocumentStore.renameRevokesAccess(info(dl, "raw:/storage/emulated/0/Download/a.txt")))
        assertFalse(SafDocumentStore.renameRevokesAccess(info(dl, null)))
        assertFalse(SafDocumentStore.renameRevokesAccess(info("com.android.externalstorage.documents", "msf:33")))
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

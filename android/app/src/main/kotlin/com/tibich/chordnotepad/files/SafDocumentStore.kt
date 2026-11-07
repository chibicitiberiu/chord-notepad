package com.tibich.chordnotepad.files

import android.util.Log
import com.tibich.chordnotepad.bridge.BridgeCodec
import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.DocumentStoreBridge
import com.tibich.chordnotepad.bridge.DocumentStoreException
import com.tibich.chordnotepad.bridge.PickMode
import com.tibich.chordnotepad.bridge.RenameUnsupportedException
import kotlinx.serialization.builtins.ListSerializer
import java.io.ByteArrayOutputStream
import java.io.FileNotFoundException
import java.io.IOException
import java.io.InputStream

/**
 * The Android `DocumentStore`: documents are content URIs from the Storage
 * Access Framework. The UI launches the pickers and hands the result to
 * [adopt]; this class only does I/O by URI and keeps the recent list.
 *
 * Python calls the [DocumentStoreBridge] methods on its session thread
 * (blocking I/O is fine there). Text is returned raw: normalization stays in
 * Python. Error messages follow the desktop's `FileService` wording.
 *
 * @param maxRecent Initial cap of the recent list; Python sets the configured
 *   one with [setMaxRecent].
 */
class SafDocumentStore(
    private val access: DocumentAccess,
    private val recentFile: RecentDocumentsFile,
    maxRecent: Int = DEFAULT_MAX_RECENT,
) : DocumentStoreBridge {
    private val lock = Any()
    private var maxRecent = maxRecent.coerceAtLeast(0)
    private val refListSerializer = ListSerializer(DocumentRef.serializer())

    // -- UI side ----------------------------------------------------------------

    /**
     * Take a document the picker returned: persist its grant (not for MIDI
     * exports, which are written once) and describe it. Does provider I/O;
     * call it off the main thread.
     */
    fun adopt(id: String, mode: PickMode): DocumentRef {
        if (mode != PickMode.EXPORT_MIDI) access.persistGrant(id)
        return refFor(id) ?: DocumentRef(id, fallbackName(id), fallbackName(id))
    }

    /**
     * Whether the app may write [id] (Open with may grant read only). Does
     * provider I/O; call it off the main thread.
     */
    fun canWrite(id: String): Boolean = access.canWrite(id)

    /** A ref for a document the app can still reach (draft restore), or null. */
    fun refFor(id: String): DocumentRef? {
        val info = access.query(id) ?: return null
        val name = info.displayName ?: fallbackName(id)
        return DocumentRef(id, name, describeLocation(info, name))
    }

    // -- Python side ------------------------------------------------------------

    override fun readBytes(id: String): ByteArray {
        // A song is a few kilobytes; this keeps a huge file (Open with any
        // .txt) from exhausting memory. The provider's size can be missing or
        // wrong, so the read itself stops at the limit too.
        val declared = access.size(id)
        if (declared != null && declared > MAX_READ_BYTES) throw tooLarge(id)
        return try {
            access.openInput(id).use { readAtMost(it, MAX_READ_BYTES) }
        } catch (e: FileNotFoundException) {
            // Named before it leaves the recent list, which has its name (B4).
            val error = DocumentStoreException("File not found: ${where(id)}", e)
            forgetRecent(id)
            throw error
        } catch (e: SecurityException) {
            throw DocumentStoreException("Permission denied: ${where(id)}", e)
        } catch (e: IOException) {
            throw DocumentStoreException("Failed to read file: ${e.message}", e)
        } ?: throw tooLarge(id)
    }

    override fun writeBytes(id: String, data: ByteArray) {
        try {
            access.openOutput(id).use { it.write(data) }
        } catch (e: SecurityException) {
            throw DocumentStoreException("Permission denied: ${where(id)}", e)
        } catch (e: IOException) {
            throw DocumentStoreException("Failed to write file: ${e.message}", e)
        }
    }

    override fun isAvailable(id: String): Boolean = access.query(id) != null

    override fun recent(): String = BridgeCodec.json.encodeToString(refListSerializer, recentDocuments())

    override fun addRecent(id: String, displayName: String, location: String) {
        synchronized(lock) {
            val ref = DocumentRef(id, displayName, location)
            store(listOf(ref) + recentFile.load().filter { it.id != id })
        }
    }

    /** Drop [id] from the recent list (a document that's gone) and release its grant. */
    private fun forgetRecent(id: String) {
        synchronized(lock) {
            val saved = recentFile.load()
            if (saved.none { it.id == id }) return
            access.releaseGrant(id)
            try {
                recentFile.save(saved.filter { it.id != id })
            } catch (e: IOException) {
                Log.w(TAG, "Can't save the recent list", e)
            }
        }
    }

    override fun setMaxRecent(count: Int) {
        synchronized(lock) { maxRecent = count.coerceAtLeast(0) }
    }

    override fun describe(id: String): String? =
        refFor(id)?.let { BridgeCodec.json.encodeToString(DocumentRef.serializer(), it) }

    override fun rename(id: String, displayName: String): String {
        if (!access.supportsRename(id)) {
            throw RenameUnsupportedException("${where(id)} is stored where Chord Notepad can't rename it.")
        }
        val before = access.query(id)
        if (before != null && renameRevokesAccess(before)) {
            throw RenameUnsupportedException(
                "Files opened from Downloads can't be renamed here: Android would take away " +
                    "Chord Notepad's access to ${before.displayName ?: fallbackName(id)}. To rename it " +
                    "in place, open it from the device's storage instead.",
            )
        }
        val renamed = try {
            access.rename(id, displayName)
        } catch (e: UnsupportedOperationException) {
            throw RenameUnsupportedException("${where(id)} is stored where Chord Notepad can't rename it.", e)
        } catch (e: FileNotFoundException) {
            throw DocumentStoreException("File not found: ${where(id)}", e)
        } catch (e: SecurityException) {
            throw DocumentStoreException("Permission denied: ${where(id)}", e)
        } catch (e: IllegalStateException) {
            // Providers report a name in use this way (and other refusals).
            throw DocumentStoreException("Couldn't rename to $displayName: ${e.message}", e)
        } catch (e: IllegalArgumentException) {
            throw DocumentStoreException("Couldn't rename to $displayName: ${e.message}", e)
        } ?: throw DocumentStoreException("Couldn't rename ${where(id)} to $displayName.")
        // The provider granted the new URI for this run; keep it across restarts.
        if (renamed != id) access.persistGrant(renamed)
        // The name is the provider's (it may add " (1)" or replace characters).
        // No ref means the rename went through but took the app's access with
        // it (a provider that answers with the same id, whose grants the
        // framework then revokes): say so, rather than keep a ref nothing can
        // read. The recent list drops the old entry on its next read.
        val ref = refFor(renamed) ?: throw DocumentStoreException(
            "Renamed to $displayName, but Android took away Chord Notepad's access to the file. " +
                "Open it again (Open…) to keep working on it.",
        )
        if (renamed != id && !access.hasPersistedGrant(renamed)) {
            Log.w(TAG, "The renamed document's grant isn't persisted; it leaves the recent list on restart")
        }
        synchronized(lock) {
            val saved = recentFile.load()
            if (saved.any { it.id == id }) store(saved.map { if (it.id == id) ref else it })
        }
        return BridgeCodec.json.encodeToString(DocumentRef.serializer(), ref)
    }

    /**
     * The recent list, newest first, without documents whose grant was
     * revoked or that the provider no longer has (those are dropped for good).
     */
    fun recentDocuments(): List<DocumentRef> = synchronized(lock) {
        val saved = recentFile.load()
        val kept = saved.filter { access.hasPersistedGrant(it.id) && isAvailable(it.id) }
        if (kept != saved || kept.size > maxRecent) store(kept) else kept
    }

    // Caps the list, releases the grants of what fell off, saves; returns what
    // was kept. The newest entry keeps its grant even when the cap is 0: it's
    // the document the user has open.
    private fun store(items: List<DocumentRef>): List<DocumentRef> {
        val kept = items.take(maxRecent)
        val keep = kept.mapTo(HashSet()) { it.id }
        items.firstOrNull()?.let { keep += it.id }
        items.drop(maxRecent).filter { it.id !in keep }.forEach { access.releaseGrant(it.id) }
        try {
            recentFile.save(kept)
        } catch (e: IOException) {
            Log.w(TAG, "Can't save the recent list", e)
        }
        return kept
    }

    private fun tooLarge(id: String) =
        DocumentStoreException("File too large to open (over ${MAX_READ_BYTES / MB} MB): ${where(id)}")

    // The stream's bytes, or null if there are more than [limit].
    private fun readAtMost(input: InputStream, limit: Int): ByteArray? {
        val out = ByteArrayOutputStream()
        val buffer = ByteArray(BUFFER_BYTES)
        while (true) {
            val n = input.read(buffer)
            if (n < 0) return out.toByteArray()
            if (out.size() + n > limit) return null
            out.write(buffer, 0, n)
        }
    }

    // Where a document is, for a message: the provider's answer, else the
    // recent entry's (a file that's gone: "fntest.txt (Downloads)", not
    // "75", its id), else a name made from the id.
    private fun where(id: String): String {
        val described = try {
            refFor(id)?.location
        } catch (e: RuntimeException) {
            null
        }
        return described ?: synchronized(lock) { recentFile.load().firstOrNull { it.id == id }?.location } ?: fallbackName(id)
    }

    companion object {
        const val DOWNLOADS_AUTHORITY = "com.android.providers.downloads.documents"

        /**
         * Whether renaming the document would cost the app its grant. The
         * Downloads provider renames a MediaStore-backed file (`msf:<id>`) and
         * answers with the same id (MediaStore keeps the row); the framework
         * (`DocumentsProvider.callUnchecked`, METHOD_RENAME_DOCUMENT) then
         * grants the "new" URI and revokes every grant on the old one, the
         * persisted one too, and they are the same URI. Seen on API 36; the
         * app can't take the grant back without the picker.
         */
        fun renameRevokesAccess(info: DocumentInfo): Boolean =
            info.authority == DOWNLOADS_AUTHORITY && info.documentId?.startsWith("msf:") == true

        /** The desktop's default `max_recent_files`. */
        const val DEFAULT_MAX_RECENT = 10

        /** The largest document [readBytes] reads (5 MB). */
        const val MAX_READ_BYTES = 5 * 1024 * 1024
        private const val MB = 1024 * 1024
        private const val BUFFER_BYTES = 64 * 1024
        private const val TAG = "CNDocuments"
    }
}

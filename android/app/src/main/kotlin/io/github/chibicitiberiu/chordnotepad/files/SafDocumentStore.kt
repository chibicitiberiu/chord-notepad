package io.github.chibicitiberiu.chordnotepad.files

import android.util.Log
import io.github.chibicitiberiu.chordnotepad.bridge.BridgeCodec
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentStoreBridge
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentStoreException
import io.github.chibicitiberiu.chordnotepad.bridge.PickMode
import kotlinx.serialization.builtins.ListSerializer
import java.io.FileNotFoundException
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.CodingErrorAction

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

    /** A ref for a document the app can still reach (draft restore), or null. */
    fun refFor(id: String): DocumentRef? {
        val info = access.query(id) ?: return null
        val name = info.displayName ?: fallbackName(id)
        return DocumentRef(id, name, describeLocation(info, name))
    }

    // -- Python side ------------------------------------------------------------

    override fun readText(id: String): String {
        val bytes = try {
            access.openInput(id).use { it.readBytes() }
        } catch (e: FileNotFoundException) {
            throw DocumentStoreException("File not found: ${where(id)}", e)
        } catch (e: SecurityException) {
            throw DocumentStoreException("Permission denied: ${where(id)}", e)
        } catch (e: IOException) {
            throw DocumentStoreException("Failed to read file: ${e.message}", e)
        }
        return try {
            Charsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes))
                .toString()
        } catch (e: CharacterCodingException) {
            throw DocumentStoreException("Cannot read file (encoding issue): ${where(id)}", e)
        }
    }

    override fun writeText(id: String, text: String) = writeBytes(id, text.toByteArray(Charsets.UTF_8))

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

    override fun setMaxRecent(count: Int) {
        synchronized(lock) { maxRecent = count.coerceAtLeast(0) }
    }

    override fun describe(id: String): String? =
        refFor(id)?.let { BridgeCodec.json.encodeToString(DocumentRef.serializer(), it) }

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

    private fun where(id: String): String = try {
        refFor(id)?.location ?: fallbackName(id)
    } catch (e: RuntimeException) {
        fallbackName(id)
    }

    companion object {
        /** The desktop's default `max_recent_files`. */
        const val DEFAULT_MAX_RECENT = 10
        private const val TAG = "CNDocuments"
    }
}

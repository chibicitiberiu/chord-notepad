package io.github.chibicitiberiu.chordnotepad.files

import java.io.InputStream
import java.io.OutputStream

/**
 * What a document provider tells about a document.
 *
 * @property displayName The provider's name for it (`song.txt`), if any.
 * @property authority The provider's authority.
 * @property documentId `DocumentsContract.getDocumentId`, for document URIs.
 * @property providerLabel The provider app's label, e.g. `Drive`.
 */
data class DocumentInfo(
    val displayName: String?,
    val authority: String,
    val documentId: String?,
    val providerLabel: String?,
)

/**
 * The platform calls [SafDocumentStore] needs, by document id (a content URI
 * string). [ContentResolverDocumentAccess] in the app; fakes in JVM tests.
 */
interface DocumentAccess {
    /** Open for reading. Throws `FileNotFoundException`/`SecurityException`/`IOException`. */
    fun openInput(id: String): InputStream

    /** Open for writing, truncating the old content. Throws like [openInput]. */
    fun openOutput(id: String): OutputStream

    /** The document's metadata, or null if it's gone or no longer accessible. */
    fun query(id: String): DocumentInfo?

    /** Whether the app holds a persisted read grant for it. */
    fun hasPersistedGrant(id: String): Boolean

    /** Keep the picker's grant across restarts (write too, when it was granted). */
    fun persistGrant(id: String)

    /** Give a persisted grant back (the document left the recent list). */
    fun releaseGrant(id: String)

    /** Whether the provider says it can rename the document (`FLAG_SUPPORTS_RENAME`). */
    fun supportsRename(id: String): Boolean

    /**
     * Rename the document to [displayName]; returns its id afterwards (it may
     * change), or null when the provider refused. Throws
     * `FileNotFoundException`/`SecurityException`/`IllegalStateException`/
     * `UnsupportedOperationException` like `DocumentsContract.renameDocument`.
     */
    fun rename(id: String, displayName: String): String?
}

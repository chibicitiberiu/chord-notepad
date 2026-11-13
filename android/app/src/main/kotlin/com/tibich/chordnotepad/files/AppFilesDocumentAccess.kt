package com.tibich.chordnotepad.files

import java.io.File
import java.io.FileInputStream
import java.io.FileNotFoundException
import java.io.FileOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.URI
import java.net.URISyntaxException

/**
 * Documents the app keeps in its own storage ([root], the example copies) as
 * plain files, by `file:` id; every other id goes to [delegate]. Such
 * documents need no grant: they are always readable, writable and remembered.
 *
 * @param label Shown after the name in messages (`song.txt (Examples)`).
 */
class AppFilesDocumentAccess(
    root: File,
    private val label: String,
    private val delegate: DocumentAccess,
) : DocumentAccess {
    private val root = root.canonicalFile

    /** The file [id] names when it lies directly inside the root, else null. */
    private fun fileOf(id: String): File? {
        if (!id.startsWith("file:")) return null
        return try {
            val uri = URI(id)
            if (uri.rawAuthority != null || uri.rawQuery != null || uri.rawFragment != null) return null
            val file = File(uri)
            file.takeIf { it.canonicalFile.parentFile == root }
        } catch (e: IllegalArgumentException) {
            null
        } catch (e: URISyntaxException) {
            null
        }
    }

    override fun openInput(id: String): InputStream =
        fileOf(id)?.let { FileInputStream(it) } ?: delegate.openInput(id)

    override fun openOutput(id: String): OutputStream =
        fileOf(id)?.let { FileOutputStream(it) } ?: delegate.openOutput(id)

    override fun query(id: String): DocumentInfo? {
        val file = fileOf(id) ?: return delegate.query(id)
        if (!file.isFile) return null
        return DocumentInfo(file.name, authority = "", documentId = null, providerLabel = label)
    }

    override fun size(id: String): Long? = fileOf(id)?.length() ?: delegate.size(id)

    override fun canWrite(id: String): Boolean = if (fileOf(id) != null) true else delegate.canWrite(id)

    override fun hasPersistedGrant(id: String): Boolean =
        if (fileOf(id) != null) true else delegate.hasPersistedGrant(id)

    override fun persistGrant(id: String) {
        if (fileOf(id) == null) delegate.persistGrant(id)
    }

    override fun releaseGrant(id: String) {
        if (fileOf(id) == null) delegate.releaseGrant(id)
    }

    override fun supportsRename(id: String): Boolean =
        if (fileOf(id) != null) true else delegate.supportsRename(id)

    override fun rename(id: String, displayName: String): String? {
        val src = fileOf(id) ?: return delegate.rename(id, displayName)
        if (!src.isFile) throw FileNotFoundException(id)
        val target = File(src.parentFile, displayName)
        require(displayName.isNotEmpty() && target.canonicalFile.parentFile == root) { "Not a file name: $displayName" }
        if (target == src) return id
        // renameTo replaces an existing file on Linux; a clash is refused instead.
        if (target.exists()) throw IllegalStateException("A file named $displayName already exists")
        if (!src.renameTo(target)) return null
        return target.toURI().toASCIIString()
    }
}

package com.tibich.chordnotepad.files

import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import android.util.Log
import androidx.core.net.toUri
import java.io.FileNotFoundException
import java.io.InputStream
import java.io.OutputStream

/** [DocumentAccess] through the app's `ContentResolver`. */
class ContentResolverDocumentAccess(context: Context) : DocumentAccess {
    private val app = context.applicationContext
    private val resolver: ContentResolver = app.contentResolver

    override fun openInput(id: String): InputStream =
        resolver.openInputStream(id.toUri()) ?: throw FileNotFoundException(id)

    override fun openOutput(id: String): OutputStream {
        val uri = id.toUri()
        // "wt" truncates; not every provider accepts it, and plain "w" doesn't
        // truncate on some, so try the truncating modes first.
        var last: Exception? = null
        for (mode in OUTPUT_MODES) {
            try {
                resolver.openOutputStream(uri, mode)?.let { return it }
            } catch (e: FileNotFoundException) {
                last = e
            } catch (e: IllegalArgumentException) {
                last = e
            } catch (e: UnsupportedOperationException) {
                last = e
            }
        }
        throw (last as? FileNotFoundException) ?: FileNotFoundException("Can't open $id for writing: $last")
    }

    override fun query(id: String): DocumentInfo? = try {
        val uri = id.toUri()
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (!c.moveToFirst()) return@use null
            val name = if (c.isNull(0)) null else c.getString(0)
            val authority = uri.authority.orEmpty()
            val docId = if (DocumentsContract.isDocumentUri(app, uri)) DocumentsContract.getDocumentId(uri) else null
            DocumentInfo(name, authority, docId, providerLabel(authority))
        }
    } catch (e: Exception) {
        // Providers throw all sorts for a missing or revoked document.
        Log.i(TAG, "Document unavailable: $id ($e)")
        null
    }

    override fun hasPersistedGrant(id: String): Boolean {
        val uri = id.toUri()
        return resolver.persistedUriPermissions.any { it.uri == uri && it.isReadPermission }
    }

    override fun persistGrant(id: String) {
        val uri = id.toUri()
        try {
            resolver.takePersistableUriPermission(uri, READ_WRITE)
        } catch (e: SecurityException) {
            try {
                resolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            } catch (e2: SecurityException) {
                // The picker's grant still works until the app restarts.
                Log.w(TAG, "Can't persist the grant for $id", e2)
            }
        }
    }

    override fun releaseGrant(id: String) {
        val uri = id.toUri()
        for (flags in listOf(READ_WRITE, Intent.FLAG_GRANT_READ_URI_PERMISSION)) {
            try {
                resolver.releasePersistableUriPermission(uri, flags)
                return
            } catch (e: SecurityException) {
                // Not held with these flags; try the next.
            }
        }
    }

    override fun supportsRename(id: String): Boolean = try {
        val uri = id.toUri()
        DocumentsContract.isDocumentUri(app, uri) &&
            resolver.query(uri, arrayOf(DocumentsContract.Document.COLUMN_FLAGS), null, null, null)?.use { c ->
                c.moveToFirst() && !c.isNull(0) &&
                    (c.getInt(0) and DocumentsContract.Document.FLAG_SUPPORTS_RENAME) != 0
            } == true
    } catch (e: Exception) {
        Log.i(TAG, "Can't read the flags of $id ($e)")
        false
    }

    override fun rename(id: String, displayName: String): String? =
        DocumentsContract.renameDocument(resolver, id.toUri(), displayName)?.toString()

    private fun providerLabel(authority: String): String? = try {
        val pm = app.packageManager
        pm.resolveContentProvider(authority, 0)?.loadLabel(pm)?.toString()
    } catch (e: RuntimeException) {
        null
    }

    private companion object {
        const val TAG = "CNDocuments"
        const val READ_WRITE = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        val OUTPUT_MODES = listOf("wt", "rwt", "w")
    }
}

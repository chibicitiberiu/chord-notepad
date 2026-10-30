package com.tibich.chordnotepad.files

import android.util.Log
import com.tibich.chordnotepad.bridge.BridgeCodec
import com.tibich.chordnotepad.bridge.DocumentRef
import kotlinx.serialization.SerializationException
import kotlinx.serialization.builtins.ListSerializer
import java.io.File
import java.io.IOException

/**
 * The recent-documents list as a small JSON file (in filesDir). Writes are
 * atomic (temp file, then rename), so a crash never leaves half a list.
 */
class RecentDocumentsFile(private val file: File) {
    private val serializer = ListSerializer(DocumentRef.serializer())

    /** The saved list; empty if there's none or it can't be read. */
    fun load(): List<DocumentRef> {
        if (!file.isFile) return emptyList()
        return try {
            BridgeCodec.json.decodeFromString(serializer, file.readText())
        } catch (e: IOException) {
            Log.w(TAG, "Can't read $file", e)
            emptyList()
        } catch (e: SerializationException) {
            Log.w(TAG, "Ignoring a corrupt $file", e)
            emptyList()
        }
    }

    /** Replace the saved list. */
    fun save(items: List<DocumentRef>) {
        file.parentFile?.mkdirs()
        val tmp = File(file.path + ".tmp")
        tmp.writeText(BridgeCodec.json.encodeToString(serializer, items))
        if (!tmp.renameTo(file)) throw IOException("Can't replace $file")
    }

    private companion object {
        const val TAG = "CNRecent"
    }
}

package io.github.chibicitiberiu.chordnotepad.files

private const val EXTERNAL_STORAGE_AUTHORITY = "com.android.externalstorage.documents"

/**
 * The user-facing location of a document, for status and error messages.
 *
 * Local storage documents get their path (`Internal storage/Music/song.txt`);
 * anything else gets its name and provider (`song.txt (Drive)`), since
 * provider document ids are opaque.
 */
fun describeLocation(info: DocumentInfo, displayName: String): String {
    val docId = info.documentId
    if (info.authority == EXTERNAL_STORAGE_AUTHORITY && docId != null && ':' in docId) {
        val volume = docId.substringBefore(':')
        val path = docId.substringAfter(':')
        val root = if (volume == "primary") "Internal storage" else "Storage $volume"
        return if (path.isEmpty()) root else "$root/$path"
    }
    val label = info.providerLabel?.takeIf { it.isNotBlank() }
    return if (label != null) "$displayName ($label)" else displayName
}

/** A name for a document whose provider gives none: the URI's last segment, decoded. */
fun fallbackName(id: String): String {
    val last = id.trimEnd('/').substringAfterLast('/')
    val decoded = try {
        java.net.URLDecoder.decode(last.replace("+", "%2B"), "UTF-8")
    } catch (e: IllegalArgumentException) {
        last
    }
    return decoded.substringAfterLast('/').substringAfterLast(':').ifEmpty { id }
}

package com.tibich.chordnotepad.files

import java.io.File
import java.io.IOException

/**
 * The example songs bundled as assets, and their private copies under [dir]
 * (the drawer's Examples sheet). Pure JVM: [list] and [read] stand in for the
 * `AssetManager`.
 *
 * @param list The asset names (any order, any extension).
 * @param read The bytes of one asset.
 * @param dir Where the copies live (`filesDir/examples`).
 */
class ExampleLibrary(
    private val list: () -> List<String>,
    private val read: (String) -> ByteArray,
    private val dir: File,
) {
    /** The example file names (`*.txt`), sorted. */
    fun names(): List<String> = list().filter { it.endsWith(".txt") }.sorted()

    /** The copy of [name] in [dir], without checking it exists. */
    fun fileFor(name: String): File = File(dir, name)

    /**
     * The document id of [file]: a `file:` URI built from the path as given,
     * never from a canonical path (ids are compared as strings).
     */
    fun idFor(file: File): String = file.toURI().toASCIIString()

    /**
     * The copy to open for [name]: the first of `x.txt`, `x (2).txt`,
     * `x (3).txt`... that doesn't exist (written now) or is byte-identical to
     * the asset. A copy whose id is [skipId] (the open document, when it has
     * unsaved edits) is passed over even when identical.
     *
     * @throws IOException when the asset can't be read or the copy not written.
     */
    @Throws(IOException::class)
    fun copyFor(name: String, skipId: String?): File {
        if (!dir.isDirectory && !dir.mkdirs() && !dir.isDirectory) throw IOException("Can't create $dir")
        val bytes = read(name)
        val stem = name.substringBeforeLast('.')
        val ext = name.substringAfterLast('.', "")
        var n = 1
        while (true) {
            val candidate = fileFor(if (n == 1) name else "$stem ($n)" + if (ext.isEmpty()) "" else ".$ext")
            if (!candidate.exists()) {
                candidate.writeBytes(bytes)
                return candidate
            }
            if (idFor(candidate) != skipId && candidate.readBytes().contentEquals(bytes)) return candidate
            n++
        }
    }
}

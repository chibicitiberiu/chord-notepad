package com.tibich.chordnotepad.res

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * The string resources as aapt2 reads them: an unescaped `"` is a quoting
 * mark and is dropped from the text (B5': the rename hint lost its `"`), so
 * a literal one must be written `\"`.
 */
class StringResourcesTest {
    private val resDir = File("src/main/res")

    private fun strings(): List<Pair<String, String>> {
        val files = resDir.walkTopDown().filter { it.isFile && it.parentFile.name.startsWith("values") && it.extension == "xml" }.toList()
        assertTrue("no string resources under ${resDir.absolutePath}", files.isNotEmpty())
        val builder = DocumentBuilderFactory.newInstance().newDocumentBuilder()
        return files.flatMap { file ->
            val doc = builder.parse(file)
            val nodes = doc.getElementsByTagName("string")
            (0 until nodes.length).map { i ->
                val node = nodes.item(i)
                "${file.name}:${node.attributes.getNamedItem("name")?.nodeValue}" to node.textContent
            }
        }
    }

    @Test
    fun `no string has a bare double quote`() {
        val bad = strings().filter { (_, text) ->
            // A value wrapped whole in quotes is aapt's way to keep spaces: allowed.
            val inner = if (text.length >= 2 && text.startsWith('"') && text.endsWith('"')) text.substring(1, text.length - 1) else text
            Regex("""(?<!\\)"""").containsMatchIn(inner)
        }
        assertTrue("unescaped \" in: ${bad.map { it.first }}", bad.isEmpty())
    }
}

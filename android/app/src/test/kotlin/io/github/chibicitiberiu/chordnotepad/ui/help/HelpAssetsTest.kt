package io.github.chibicitiberiu.chordnotepad.ui.help

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** The generated User Guide (`buildAndroidHelp`, `-t android`): it is there and self-contained. */
class HelpAssetsTest {
    private val dir: File? = System.getProperty("cn.helpDir")?.let(::File)

    private fun pages(): List<File> {
        assumeTrue("cn.helpDir not set", dir != null)
        assertTrue("the help build left no $dir", dir!!.isDirectory)
        return dir.walkTopDown().filter { it.isFile && it.extension == "html" }.toList()
    }

    @Test
    fun `the guide has an index and the pages it links`() {
        val html = pages()
        assertTrue(File(dir, "index.html").isFile)
        for (name in listOf("settings.html", "shortcuts.html", "getting_started.html")) {
            assertTrue("missing $name", html.any { it.name == name })
        }
    }

    @Test
    fun `no page links to a file URL or an absolute filesystem path`() {
        for (page in pages()) {
            val text = page.readText()
            assertFalse("${page.name} has a file:// link", "file://" in text)
            assertFalse("${page.name} has an absolute href", Regex("""(href|src)="/[^/]""").containsMatchIn(text))
            assertFalse("${page.name} names the build checkout", "/home/" in text || "/tmp/" in text)
        }
    }

    @Test
    fun `this is the android guide`() {
        val settings = File(dir, "settings.html").readText()
        // Android-only wording from help/settings.rst; the desktop build has Tools > Settings instead.
        assertTrue("Add voicing" in settings)
    }
}

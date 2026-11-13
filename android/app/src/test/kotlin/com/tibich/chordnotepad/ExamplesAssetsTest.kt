package com.tibich.chordnotepad

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** The generated `assets/examples` (`copyExamples`) is the repo's example songs. */
class ExamplesAssetsTest {
    private val generated: File? = System.getProperty("cn.examplesDir")?.let(::File)
    private val source: File? = System.getProperty("cn.examplesSrc")?.let(::File)

    private fun txt(dir: File) = dir.listFiles { f -> f.isFile && f.extension == "txt" }!!.sortedBy { it.name }

    @Test
    fun `the generated examples are the repo's examples`() {
        assumeTrue("cn.examplesDir/cn.examplesSrc not set", generated != null && source != null)
        assertTrue("the examples build left no $generated", generated!!.isDirectory)
        val expected = txt(source!!)
        assertTrue(expected.isNotEmpty())
        val actual = txt(generated)
        assertEquals(expected.map { it.name }, actual.map { it.name })
        for ((e, a) in expected.zip(actual)) assertArrayEquals(e.name, e.readBytes(), a.readBytes())
    }
}

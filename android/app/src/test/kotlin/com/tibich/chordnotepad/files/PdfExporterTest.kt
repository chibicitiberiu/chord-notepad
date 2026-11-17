package com.tibich.chordnotepad.files

import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.DocumentStoreException
import com.tibich.chordnotepad.bridge.PaintPdfRequest
import com.tibich.chordnotepad.bridge.PdfLayout
import com.tibich.chordnotepad.bridge.PdfLine
import com.tibich.chordnotepad.bridge.PdfPage
import com.tibich.chordnotepad.bridge.PdfRun
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.OutputStream

class PdfExporterTest {
    /** Records what is painted; writes "PDF:<pages>" as the document. */
    private class RecordingCanvas : PdfCanvas {
        val calls = mutableListOf<String>()
        var closed = false

        override fun startPage(number: Int, width: Int, height: Int) {
            calls += "page $number ${width}x$height"
        }

        override fun drawText(text: String, x: Float, y: Float, size: Float, color: Int) {
            calls += "'$text' at $x,$y $size #%06X".format(color and 0xFFFFFF)
        }

        override fun finishPage() {
            calls += "end"
        }

        override fun writeTo(out: OutputStream) = out.write("PDF:${calls.count { it.startsWith("page") }}".toByteArray())

        override fun close() {
            closed = true
        }
    }

    private fun page(footer: String, vararg lines: PdfLine) = PdfPage(lines.toList(), footer, 290.0)

    private val layout = PdfLayout(
        pageWidth = 595.28, pageHeight = 841.89, fontSize = 9.5, lineHeight = 12.94, smallFontSize = 8.0,
        title = "Song", titleX = 42.52, titleY = 51.07, footerY = 797.03, pageCount = 2,
        pages = listOf(
            page("1 / 2", PdfLine(76.0, listOf(PdfRun(42.52, "Key: A", true), PdfRun(102.52, "A D", false)))),
            page("2 / 2", PdfLine(76.0, listOf(PdfRun(42.52, "la la", false)))),
        ),
    )

    private val request = PaintPdfRequest(4, DocumentRef("content://d/song.pdf", "song.pdf", "Downloads/song.pdf"), layout)

    @Test
    fun `every page of the layout, at its size, with the positions as given`() {
        val canvas = RecordingCanvas()
        paintPdf(layout, canvas)
        assertEquals(
            listOf(
                "page 1 595x842",
                "'Song' at 42.52,51.07 8.0 #7A7F8A",
                "'1 / 2' at 290.0,797.03 8.0 #7A7F8A",
                "'Key: A' at 42.52,76.0 9.5 #7A7F8A",
                "'A D' at 102.52,76.0 9.5 #1F2328",
                "end",
                "page 2 595x842",
                "'Song' at 42.52,51.07 8.0 #7A7F8A",
                "'2 / 2' at 290.0,797.03 8.0 #7A7F8A",
                "'la la' at 42.52,76.0 9.5 #1F2328",
                "end",
            ),
            canvas.calls,
        )
    }

    @Test
    fun `letter pages are 612 by 792`() {
        val canvas = RecordingCanvas()
        paintPdf(layout.copy(pageWidth = 612.0, pageHeight = 792.0), canvas)
        assertEquals("page 1 612x792", canvas.calls.first())
    }

    @Test
    fun `export writes the pages to the picked document and answers empty`() {
        val written = mutableMapOf<String, ByteArray>()
        val canvas = RecordingCanvas()
        val exporter = PdfExporter(write = { id, block ->
            written[id] = ByteArrayOutputStream().also(block).toByteArray()
        }, newCanvas = { canvas })
        assertEquals("", exporter.export(request))
        assertEquals("PDF:2", String(written.getValue("content://d/song.pdf")))
        assertTrue(canvas.closed)
    }

    @Test
    fun `a write that fails answers with its reason`() {
        val canvas = RecordingCanvas()
        val exporter = PdfExporter(write = { _, _ ->
            throw DocumentStoreException("Permission denied: song.pdf (Downloads)")
        }, newCanvas = { canvas })
        assertEquals("Permission denied: song.pdf (Downloads)", exporter.export(request))
        assertTrue(canvas.closed)
    }

    @Test
    fun `paper follows the country`() {
        assertEquals("letter", paperFor("US"))
        assertEquals("letter", paperFor("ca"))
        assertEquals("a4", paperFor("RO"))
        assertEquals("a4", paperFor("GB"))
        assertEquals("a4", paperFor(""))
        assertEquals("a4", paperFor(null))
    }
}

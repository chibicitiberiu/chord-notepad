package com.tibich.chordnotepad.files

import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.util.Log
import com.tibich.chordnotepad.bridge.DocumentStoreException
import com.tibich.chordnotepad.bridge.PaintPdfRequest
import com.tibich.chordnotepad.bridge.PdfLayout
import java.io.IOException
import java.io.OutputStream
import kotlin.math.roundToInt

/**
 * The countries (ISO 3166 codes) that use Letter paper, CLDR's list; the
 * same as the core's `print_layout.LETTER_TERRITORIES`.
 */
val LETTER_COUNTRIES = setOf("BZ", "CA", "CL", "CO", "CR", "GT", "MX", "NI", "PA", "PH", "PR", "SV", "US", "VE")

/** `export_pdf`'s page size for [country] (the locale's): `letter` or `a4`. */
fun paperFor(country: String?): String = if ((country ?: "").uppercase() in LETTER_COUNTRIES) "letter" else "a4"

/** The colours the pages are painted in (ARGB), the desktop's (`pdf_export.py`). */
object PdfColors {
    /** The song's text: near-black. */
    const val TEXT = 0xFF1F2328.toInt()
    /** A directive's label. */
    const val DIM = 0xFF7A7F8A.toInt()
    /** The header (the song's name) and the footer (`1 / 3`). */
    const val HEADER = 0xFF7A7F8A.toInt()
}

/** What [paintPdf] paints on: [AndroidPdfCanvas] in the app, a recorder in JVM tests. */
interface PdfCanvas {
    /** Start page [number] (from 1), [width] by [height] points. */
    fun startPage(number: Int, width: Int, height: Int)

    /** Draw [text] from [x] on the baseline [y] (points from the top-left corner), [size] points, ARGB [color]. */
    fun drawText(text: String, x: Float, y: Float, size: Float, color: Int)

    /** Finish the page started last. */
    fun finishPage()

    /** Write the finished pages as a PDF. */
    fun writeTo(out: OutputStream)

    /** Free the document. */
    fun close()
}

/**
 * Paint [layout] on [canvas], one page each: the header and the footer small
 * and grey, then the runs, labels dim. Every position comes from the layout.
 */
fun paintPdf(layout: PdfLayout, canvas: PdfCanvas) {
    val width = layout.pageWidth.roundToInt()
    val height = layout.pageHeight.roundToInt()
    val small = layout.smallFontSize.toFloat()
    val size = layout.fontSize.toFloat()
    layout.pages.forEachIndexed { index, page ->
        canvas.startPage(index + 1, width, height)
        canvas.drawText(layout.title, layout.titleX.toFloat(), layout.titleY.toFloat(), small, PdfColors.HEADER)
        canvas.drawText(page.footer, page.footerX.toFloat(), layout.footerY.toFloat(), small, PdfColors.HEADER)
        for (line in page.lines) {
            for (run in line.runs) {
                canvas.drawText(run.text, run.x.toFloat(), line.y.toFloat(), size, if (run.dim) PdfColors.DIM else PdfColors.TEXT)
            }
        }
        canvas.finishPage()
    }
}

/**
 * Android's [PdfDocument], whose page canvas counts in points. The system
 * monospace (0.6 em, as the layout counts), unhinted with fractional
 * advances, so a run's columns don't round off.
 */
class AndroidPdfCanvas : PdfCanvas {
    private val document = PdfDocument()
    private var page: PdfDocument.Page? = null
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.SUBPIXEL_TEXT_FLAG or Paint.LINEAR_TEXT_FLAG).apply {
        typeface = Typeface.MONOSPACE
    }

    override fun startPage(number: Int, width: Int, height: Int) {
        page = document.startPage(PdfDocument.PageInfo.Builder(width, height, number).create())
    }

    override fun drawText(text: String, x: Float, y: Float, size: Float, color: Int) {
        paint.textSize = size
        paint.color = color
        page?.canvas?.drawText(text, x, y, paint)
    }

    override fun finishPage() {
        page?.let(document::finishPage)
        page = null
    }

    override fun writeTo(out: OutputStream) = document.writeTo(out)

    override fun close() = document.close()
}

/**
 * Answers a `PaintPdfRequest`: paints its layout and writes it to the picked
 * document. Provider I/O: call [export] off the main thread.
 *
 * @param write Replaces a document's content with what the block writes
 *   (`SafDocumentStore.writeWith`, which says why it failed).
 * @param newCanvas A fresh canvas for each export.
 */
class PdfExporter(
    private val write: (id: String, block: (OutputStream) -> Unit) -> Unit,
    private val newCanvas: () -> PdfCanvas = ::AndroidPdfCanvas,
) {
    /** Paint and write [request]'s pages: "" when written, else why not (the request's answer). */
    fun export(request: PaintPdfRequest): String {
        val canvas = newCanvas()
        return try {
            paintPdf(request.layout, canvas)
            write(request.ref.id) { out -> canvas.writeTo(out) }
            ""
        } catch (e: DocumentStoreException) {
            Log.w(TAG, "Can't write the PDF to ${request.ref.location}", e)
            e.message ?: e.toString()
        } catch (e: IOException) {
            Log.w(TAG, "Can't write the PDF to ${request.ref.location}", e)
            "Failed to write file: ${e.message}"
        } finally {
            canvas.close()
        }
    }

    private companion object {
        const val TAG = "CNPdf"
    }
}

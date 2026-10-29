package io.github.chibicitiberiu.chordnotepad.ui.editor

import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import org.junit.Assert.assertEquals
import org.junit.Test

class EditorLookTest {
    @Test
    fun `desktop font families map to the three Android ones`() {
        assertEquals(EditorFontKind.MONOSPACE, fontKindFor("TkFixedFont"))
        assertEquals(EditorFontKind.MONOSPACE, fontKindFor(""))
        assertEquals(EditorFontKind.MONOSPACE, fontKindFor("DejaVu Sans Mono"))
        assertEquals(EditorFontKind.MONOSPACE, fontKindFor("Courier New"))
        assertEquals(EditorFontKind.SANS, fontKindFor("DejaVu Sans"))
        assertEquals(EditorFontKind.SANS, fontKindFor("Arial"))
        assertEquals(EditorFontKind.SERIF, fontKindFor("Times New Roman"))
        assertEquals(EditorFontKind.SERIF, fontKindFor("Noto Serif"))
        assertEquals(EditorFontKind.MONOSPACE, fontKindFor("Some Unknown Font"))
    }

    @Test
    fun `points become sp at Tk's 96 DPI`() {
        assertEquals(16f, editorFontSizeSp(12), 0.001f)
        assertEquals(14.667f, editorFontSizeSp(11), 0.001f)
    }

    @Test
    fun `span kinds paint in the desktop's tag priority`() {
        assertEquals(
            listOf(SpanKind.CHORD, SpanKind.CHORD_INVALID, SpanKind.DIRECTIVE, SpanKind.DIRECTIVE_INVALID, SpanKind.COMMENT),
            SpanStyles.map { it.first },
        )
        assertEquals(SpanKind.entries.toSet(), SpanStyles.map { it.first }.toSet())
    }

    @Test
    fun `a pinch scales the font size, clamped`() {
        assertEquals(11, pinchFontSize(11, 1f))
        assertEquals(22, pinchFontSize(11, 2f))
        assertEquals(6, pinchFontSize(11, 0.1f))
        assertEquals(72, pinchFontSize(40, 3f))
    }
}

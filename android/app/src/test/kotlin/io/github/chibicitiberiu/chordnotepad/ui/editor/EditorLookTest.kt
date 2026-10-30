package io.github.chibicitiberiu.chordnotepad.ui.editor

import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import io.github.chibicitiberiu.chordnotepad.ui.theme.AppColors
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
            listOf(
                SpanKind.CHORD, SpanKind.CHORD_INVALID, SpanKind.DIRECTIVE, SpanKind.DIRECTIVE_INVALID,
                SpanKind.DIRECTIVE_REDUNDANT, SpanKind.COMMENT,
            ),
            SpanStyles.map { it.first },
        )
        assertEquals(SpanKind.entries.toSet(), SpanStyles.map { it.first }.toSet())
    }

    @Test
    fun `a redundant directive is the directive colour, faded, in both themes`() {
        for (styles in listOf(SpanStyles, spanStylesFor(AppColors.Light), spanStylesFor(AppColors.Dark))) {
            val byKind = styles.toMap()
            assertEquals(
                byKind.getValue(SpanKind.DIRECTIVE).color.copy(alpha = REDUNDANT_ALPHA),
                byKind.getValue(SpanKind.DIRECTIVE_REDUNDANT).color,
            )
        }
    }

    @Test
    fun `a pinch scales the font size, clamped`() {
        assertEquals(11, pinchFontSize(11, 1f))
        assertEquals(22, pinchFontSize(11, 2f))
        assertEquals(6, pinchFontSize(11, 0.1f))
        assertEquals(72, pinchFontSize(40, 3f))
    }

    @Test
    fun `the configured family is kept when it already is the chosen kind`() {
        assertEquals("TkFixedFont", configFamilyFor(EditorFontKind.MONOSPACE, "TkFixedFont"))
        assertEquals("Consolas", configFamilyFor(EditorFontKind.MONOSPACE, "Consolas"))
        assertEquals("Times New Roman", configFamilyFor(EditorFontKind.SERIF, "Times New Roman"))
    }

    @Test
    fun `another kind sends a family that maps back to it`() {
        for (kind in EditorFontKind.entries) {
            for (current in listOf("TkFixedFont", "Sans", "Serif", "Arial")) {
                assertEquals(kind, fontKindFor(configFamilyFor(kind, current)))
            }
        }
        assertEquals("TkFixedFont", configFamilyFor(EditorFontKind.MONOSPACE, "Arial"))
        assertEquals("Sans", configFamilyFor(EditorFontKind.SANS, "TkFixedFont"))
        assertEquals("Serif", configFamilyFor(EditorFontKind.SERIF, "TkFixedFont"))
    }
}

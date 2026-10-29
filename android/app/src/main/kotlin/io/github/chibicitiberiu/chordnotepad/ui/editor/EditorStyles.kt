package io.github.chibicitiberiu.chordnotepad.ui.editor

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextDecoration
import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind

// The desktop editor's look (src/constants.py, src/ui/text_editor.py), which
// the port keeps as is: Tk's named colours, black text on white.

/** Tk "blue": valid chords. */
val ChordBlue = Color(0xFF0000FF)

/** Tk "gray" (X11 #BEBEBE): invalid chords and comments. */
val TkGray = Color(0xFFBEBEBE)

/** `COLOR_DIRECTIVE_VALID`. */
val DirectivePurple = Color(0xFF8B4789)

/** Tk "red": invalid directives. */
val TkRed = Color(0xFFFF0000)

/** Tk "yellow": the chord that is sounding. */
val PlayingYellow = Color(0xFFFFFF00)

/** The editor's text and background. */
val EditorText = Color.Black
val EditorBackground = Color.White

/**
 * The style of each span kind, in the desktop's tag priority order: a later
 * entry wins where spans overlap (Tk raises later-created tags).
 */
val SpanStyles: List<Pair<SpanKind, SpanStyle>> = listOf(
    SpanKind.CHORD to SpanStyle(color = ChordBlue, textDecoration = TextDecoration.Underline),
    SpanKind.CHORD_INVALID to SpanStyle(color = TkGray, textDecoration = TextDecoration.Underline),
    SpanKind.DIRECTIVE to SpanStyle(color = DirectivePurple, textDecoration = TextDecoration.None),
    SpanKind.DIRECTIVE_INVALID to SpanStyle(color = TkRed, textDecoration = TextDecoration.Underline),
    SpanKind.COMMENT to SpanStyle(color = TkGray),
)

/** The playing chord, painted above every other span (the desktop raises its tag). */
val PlayingStyle = SpanStyle(
    color = Color.Black,
    background = PlayingYellow,
    textDecoration = TextDecoration.Underline,
)

/** Paint order: lower first, so higher-priority kinds win on overlap. */
val SpanPriority: Map<SpanKind, Int> = SpanStyles.mapIndexed { i, (kind, _) -> kind to i }.toMap()

/** The three families Android offers for the editor (docs/ANDROID_PORT_PLAN.md, settings visibility). */
enum class EditorFontKind(val family: FontFamily) {
    MONOSPACE(FontFamily.Monospace),
    SANS(FontFamily.SansSerif),
    SERIF(FontFamily.Serif),
}

/**
 * The Android family for a configured desktop font family. `TkFixedFont`
 * and monospaced names map to Monospace, sans serif names (and Tk's
 * default UI font) to Sans, serif names to Serif; anything unknown keeps
 * the desktop default, Monospace.
 */
fun fontKindFor(family: String): EditorFontKind {
    val f = family.lowercase()
    return when {
        f.isBlank() -> EditorFontKind.MONOSPACE
        listOf("fixed", "mono", "courier", "consol", "menlo", "typewriter", "code").any { it in f } ->
            EditorFontKind.MONOSPACE
        listOf("sans", "arial", "helvetica", "verdana", "tahoma", "segoe", "ubuntu", "cantarell", "roboto",
            "tkdefaultfont", "tktextfont", "noto sans", "calibri").any { it in f } -> EditorFontKind.SANS
        listOf("serif", "times", "georgia", "garamond", "palatino", "cambria", "book").any { it in f } ->
            EditorFontKind.SERIF
        else -> EditorFontKind.MONOSPACE
    }
}

/**
 * A desktop font size (points; Tk renders them at 96 DPI, 4/3 px per pt) in
 * sp, so the editor reads the same size as the desktop's at 1 px = 1 dp.
 */
fun editorFontSizeSp(points: Int): Float = points * 4f / 3f

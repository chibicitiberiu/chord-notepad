package io.github.chibicitiberiu.chordnotepad.text

import io.github.chibicitiberiu.chordnotepad.bridge.Span
import io.github.chibicitiberiu.chordnotepad.bridge.TextEdited

/**
 * A [TextEdited] in UTF-16 terms, ready for `TextFieldState.edit {}`:
 * `replace(start, end, replacement)`, then `selection = TextRange(cursor)`.
 *
 * @property start Start of the replaced range in the old text.
 * @property end End of the replaced range in the old text.
 * @property cursor Cursor position in the new text.
 */
data class Utf16Edit(val start: Int, val end: Int, val replacement: String, val cursor: Int)

/**
 * Converts this edit's code-point offsets for [text], the view's text before
 * the edit; [mapper] must be [text]'s. Out-of-range offsets are clamped.
 */
fun TextEdited.toUtf16(text: CharSequence, mapper: OffsetMapper = OffsetMapper.of(text)): Utf16Edit {
    val startCp = start.coerceIn(0, mapper.codePointLength)
    val endCp = end.coerceIn(startCp, mapper.codePointLength)
    val start16 = mapper.toUtf16(startCp)
    val end16 = mapper.toUtf16(endCp)
    val replacementCps = replacement.codePointCount(0, replacement.length)
    val cursor16 = when {
        // Before the edit: the old text's mapping still holds.
        cursor <= startCp -> mapper.toUtf16(cursor)
        // Inside the replacement.
        cursor <= startCp + replacementCps ->
            start16 + replacement.offsetByCodePoints(0, cursor - startCp)
        // After it: map in the old text, then shift by the length change.
        else -> {
            val oldCp = cursor - replacementCps + (endCp - startCp)
            mapper.toUtf16(oldCp) - (end16 - start16) + replacement.length
        }
    }
    return Utf16Edit(start16, end16, replacement, cursor16)
}

/** Applies [edit] to [text]; the plain-string form of what the editor does. */
fun applyEdit(text: String, edit: Utf16Edit): String =
    text.substring(0, edit.start) + edit.replacement + text.substring(edit.end)

/** A range `[start, end)` in UTF-16 units. */
data class Utf16Range(val start: Int, val end: Int)

/** This span in UTF-16 units of the text [mapper] was built for (clamped to it). */
fun Span.toUtf16Range(mapper: OffsetMapper): Utf16Range {
    val s = mapper.toUtf16(start)
    return Utf16Range(s, mapper.toUtf16(end).coerceAtLeast(s))
}

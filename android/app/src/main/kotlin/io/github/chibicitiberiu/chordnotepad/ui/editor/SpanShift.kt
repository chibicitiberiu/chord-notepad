package io.github.chibicitiberiu.chordnotepad.ui.editor

import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind

/**
 * A highlight as the editor paints it: `[start, end)` in UTF-16 units of the
 * editor's current text.
 */
data class PaintedSpan(val start: Int, val end: Int, val kind: SpanKind)

/**
 * One edit as a single replaced range (UTF-16): the old text's
 * `[start, oldEnd)` became the new text's `[start, newEnd)`.
 */
data class TextChange(val start: Int, val oldEnd: Int, val newEnd: Int) {
    /** How much later everything after the change sits now. */
    val delta: Int get() = newEnd - oldEnd
}

/**
 * The smallest single change that turns [old] into [new] (common prefix and
 * suffix), or null when they are equal. Never splits a surrogate pair.
 */
fun diffTexts(old: CharSequence, new: CharSequence): TextChange? {
    val minLen = minOf(old.length, new.length)
    var prefix = 0
    while (prefix < minLen && old[prefix] == new[prefix]) prefix++
    if (prefix == old.length && prefix == new.length) return null
    if (prefix > 0 && Character.isHighSurrogate(old[prefix - 1])) prefix--
    var suffix = 0
    while (suffix < minLen - prefix && old[old.length - 1 - suffix] == new[new.length - 1 - suffix]) suffix++
    if (suffix > 0 && Character.isLowSurrogate(old[old.length - suffix])) suffix--
    return TextChange(prefix, old.length - suffix, new.length - suffix)
}

/**
 * Moves painted spans along with an edit, the way Tk text tags move: text
 * after the change shifts, text typed at a span's edge stays outside it,
 * text typed inside a span joins it, and a span whose text was removed
 * disappears. Keeps the old highlighting roughly right until the session's
 * next `HighlightState` replaces it (about half a second after typing stops).
 */
fun List<PaintedSpan>.shiftedBy(change: TextChange): List<PaintedSpan> {
    if (isEmpty()) return this
    fun startOf(x: Int) = when {
        x < change.start -> x
        x >= change.oldEnd -> x + change.delta
        else -> change.newEnd // its first characters were replaced
    }
    fun endOf(x: Int) = when {
        x <= change.start -> x
        x >= change.oldEnd -> x + change.delta
        else -> change.start // its last characters were replaced
    }
    return mapNotNull { s ->
        val start = startOf(s.start)
        val end = endOf(s.end)
        if (end > start) PaintedSpan(start, end, s.kind) else null
    }
}

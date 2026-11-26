package com.tibich.chordnotepad.ui.help

import com.tibich.chordnotepad.bridge.QuickStartBlock
import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.text.OffsetMapper
import com.tibich.chordnotepad.ui.editor.SpanPriority

/**
 * Which page of the Quick Start tour is showing. Immutable; [next] and
 * [previous] stop at the ends, as the desktop dialog's buttons do.
 *
 * @property pageCount Number of pages (at least 1).
 * @property index The current page, 0-based.
 */
data class QuickStartPager(val pageCount: Int, val index: Int = 0) {
    init {
        require(pageCount >= 1) { "a tour has pages" }
    }

    /** The page, clamped into the tour. */
    val current: Int get() = index.coerceIn(0, pageCount - 1)

    /** True on the first page (Previous is disabled). */
    val isFirst: Boolean get() = current == 0

    /** True on the last page (Next becomes Done). */
    val isLast: Boolean get() = current == pageCount - 1

    /** The pager one page on (the same on the last page). */
    fun next(): QuickStartPager = copy(index = (current + 1).coerceAtMost(pageCount - 1))

    /** The pager one page back (the same on the first page). */
    fun previous(): QuickStartPager = copy(index = (current - 1).coerceAtLeast(0))
}

/** A snippet's font size (sp): the editor's 15, and the smallest it shrinks to so its longest line fits. */
const val SNIPPET_FONT_SP = 15f
const val SNIPPET_FONT_MIN_SP = 11f

/**
 * The font size (sp) that fits [text]'s longest line in [width], in a
 * monospaced font whose characters are [advance] wide per sp (both in the
 * same unit, pixels say): [SNIPPET_FONT_SP] when it fits, else smaller in
 * half steps, never below [SNIPPET_FONT_MIN_SP] (wider than that, the box
 * scrolls sideways). Lines never wrap: a wrapped chord line no longer sits
 * over its lyric. iOS has the same rule (`snippetFontSize`).
 */
fun snippetFontSize(text: String, width: Float, advance: Float): Float {
    val columns = text.split('\n').maxOfOrNull { it.codePointCount(0, it.length) } ?: 0
    if (columns == 0 || advance <= 0f || width <= 0f) return SNIPPET_FONT_SP
    val fits = kotlin.math.floor(width / (columns * advance) * 2f) / 2f
    return fits.coerceIn(SNIPPET_FONT_MIN_SP, SNIPPET_FONT_SP)
}

/** A highlighted run of a snippet in UTF-16 units, ready for an `AnnotatedString`. */
data class SnippetRun(val start: Int, val end: Int, val kind: SpanKind)

/**
 * The highlight runs of a Quick Start snippet [block]: the session's spans
 * (Unicode code points) converted to UTF-16 offsets, empty or out-of-range
 * ones dropped, and ordered so that a higher-priority kind comes later and so
 * wins on overlap, like in the editor.
 */
fun snippetRuns(block: QuickStartBlock): List<SnippetRun> {
    val mapper = OffsetMapper.of(block.text)
    return block.spans
        .map { SnippetRun(mapper.toUtf16(it.start), mapper.toUtf16(it.end), it.kind) }
        .filter { it.start < it.end }
        .sortedBy { SpanPriority[it.kind] ?: 0 }
}

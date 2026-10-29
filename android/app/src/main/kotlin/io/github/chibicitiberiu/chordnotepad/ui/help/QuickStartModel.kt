package io.github.chibicitiberiu.chordnotepad.ui.help

import io.github.chibicitiberiu.chordnotepad.bridge.QuickStartBlock
import io.github.chibicitiberiu.chordnotepad.bridge.SettingsState
import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import io.github.chibicitiberiu.chordnotepad.text.OffsetMapper
import io.github.chibicitiberiu.chordnotepad.ui.editor.SpanPriority

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

/** First-run rule for the tour. */
object QuickStartLaunch {
    /**
     * Whether to open the tour on its own now: the setting says so and it has
     * not been shown since this process started. The settings state arrives
     * from the session shortly after launch; until then (null) the answer is
     * no, and the caller asks again when it comes.
     *
     * @param settings The latest settings state, or null before it is known.
     * @param shownThisProcess Whether the tour was already auto-shown (or dismissed) since the process started.
     */
    fun shouldAutoShow(settings: SettingsState?, shownThisProcess: Boolean): Boolean =
        !shownThisProcess && settings?.values?.showQuickStartOnStartup == true
}

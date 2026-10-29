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
    /** What to do with the latest settings: [open] the tour now, and whether the once-per-process [decided] flag is now set. */
    data class Decision(val open: Boolean, val decided: Boolean)

    /**
     * Decide once per process, when the settings first arrive: open the tour
     * if the setting says so. Turning the setting on later (Settings, or the
     * tour's own "Show at startup" box) must not open it again at once.
     * The settings state comes from the session shortly after launch; until
     * then (null) nothing is decided and the caller asks again when it comes.
     *
     * @param settings The latest settings state, or null before it is known.
     * @param decided Whether this process already decided.
     */
    fun decide(settings: SettingsState?, decided: Boolean): Decision {
        if (decided || settings == null) return Decision(open = false, decided = decided)
        return Decision(open = settings.values.showQuickStartOnStartup, decided = true)
    }
}

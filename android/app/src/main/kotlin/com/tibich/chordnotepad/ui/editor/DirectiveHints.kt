package com.tibich.chordnotepad.ui.editor

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.tibich.chordnotepad.bridge.DirectiveHint
import com.tibich.chordnotepad.bridge.SessionRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.launch

/** How long the cursor rests before its directive hint is asked for. */
const val HINT_DEBOUNCE_MS = 150L

/** How long a long-pressed directive's explanation stays up in Play mode. */
const val EXPLAIN_SHOWN_MS = 6000L

/**
 * What a directive hint shows: the [reason] (invalid, or has no effect; ""
 * for a valid directive), in the error colour when [error], then the
 * [syntax], one line per directive a half-typed keyword could become. Each
 * example in [syntax] is kept whole when the text wraps (its spaces are
 * non-breaking), with " · " between them.
 */
data class HintCard(val reason: String, val error: Boolean, val syntax: String) {
    companion object {
        /** The card for [hint]; null when there is no directive there. */
        fun of(hint: DirectiveHint): HintCard? {
            if (hint.syntax.isEmpty()) return null
            return HintCard(hint.message, hint.message.isNotEmpty() && !hint.redundant, wrapFriendly(hint.syntax))
        }

        /** [syntax] with every example's own spaces non-breaking. */
        fun wrapFriendly(syntax: String): String =
            syntax.lines().filter { it.isNotEmpty() }.joinToString("\n") { line ->
                line.split(EXAMPLE_SEPARATOR).joinToString(EXAMPLE_SEPARATOR) { it.replace(' ', ' ') }
            }

        private const val EXAMPLE_SEPARATOR = " · "
    }
}

/** A long-pressed directive's explanation (Play mode): [card] for the directive at code points `[start, end)`. */
data class ExplainedDirective(val card: HintCard, val start: Int, val end: Int)

/**
 * The directive hints on Android, as plain state (tested on the JVM):
 *
 * - Edit mode: while the cursor rests inside a directive (or one being
 *   typed), [strip] is its hint, for the strip above the keyboard; null
 *   otherwise. The cursor comes in debounced ([bind]); each rest asks the
 *   session once (`request_directive_hint`, through [request]).
 * - Play mode: a long-press on a red or faded directive asks for it
 *   ([explain]); [explained] is its reason and syntax until [dismiss].
 *
 * Replies for an offset nobody is waiting for any more are dropped. The
 * repository keeps only the latest reply and doesn't repeat an equal one,
 * so the last reply is kept here too and reused when the cursor comes back
 * to its offset. Main thread only.
 */
class DirectiveHintController(private val request: (Int) -> Unit) {
    /** The Edit-mode hint strip, or null. */
    var strip: HintCard? by mutableStateOf(null)
        private set

    /** The Play-mode explanation of a long-pressed directive, or null. */
    var explained: ExplainedDirective? by mutableStateOf(null)
        private set

    private var cursor: Int? = null
    private var explaining: Int? = null
    private var last: DirectiveHint? = null

    /**
     * The cursor rested at code point [offset]; null when there's no cursor
     * to hint for (Play mode, the text isn't focused, or a range is selected),
     * which hides the strip at once.
     */
    fun onCursor(offset: Int?) {
        cursor = offset
        if (offset == null) {
            strip = null
            return
        }
        last?.takeIf { it.offset == offset }?.let { strip = HintCard.of(it) }
        request(offset)
    }

    /** New highlighting (detection caught up): ask again, a directive's reason may have changed. */
    fun onHighlight() {
        cursor?.let(request)
    }

    /** Explain the directive starting at code point [offset] (a long-press in Play mode). */
    fun explain(offset: Int) {
        explaining = offset
        last?.takeIf { it.offset == offset }?.let(::showExplained)
        request(offset)
    }

    /** Hide the explanation. */
    fun dismiss() {
        explaining = null
        explained = null
    }

    /** The session's reply to `request_directive_hint`. */
    fun onHint(hint: DirectiveHint) {
        last = hint
        if (hint.offset == cursor) strip = HintCard.of(hint)
        if (hint.offset == explaining) showExplained(hint)
    }

    private fun showExplained(hint: DirectiveHint) {
        val card = HintCard.of(hint)
        explained = card?.takeIf { it.reason.isNotEmpty() }?.let { ExplainedDirective(it, hint.start, hint.end) }
    }
}

/**
 * Feed [this] in [scope] (main thread): [cursor] (code points, null for no
 * cursor) debounced by [HINT_DEBOUNCE_MS] (a null at once), and the
 * repository's hint replies and highlighting.
 */
@OptIn(FlowPreview::class)
fun DirectiveHintController.bind(scope: CoroutineScope, repository: SessionRepository, cursor: Flow<Int?>): Job =
    scope.launch {
        launch {
            cursor.distinctUntilChanged()
                .debounce { if (it == null) 0L else HINT_DEBOUNCE_MS }
                .collect(::onCursor)
        }
        launch { repository.directiveHint.filterNotNull().collect(::onHint) }
        launch { repository.highlight.filterNotNull().collect { onHighlight() } }
    }

/**
 * Where the explanation card's top goes, in the text's pixels: under the
 * directive (`[anchorTop, anchorBottom]`) with a [gap], or above it when it
 * would run past the visible part's bottom ([viewBottom]) and fits under its
 * top ([viewTop]).
 */
fun explainCardTop(anchorTop: Float, anchorBottom: Float, cardHeight: Float, viewTop: Float, viewBottom: Float, gap: Float): Float {
    val below = anchorBottom + gap
    val above = anchorTop - gap - cardHeight
    return if (below + cardHeight > viewBottom && above >= viewTop) above else below
}

package com.tibich.chordnotepad.ui.editor

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.text.TextRange
import com.tibich.chordnotepad.bridge.HighlightState
import com.tibich.chordnotepad.bridge.PlaybackState
import com.tibich.chordnotepad.bridge.SessionCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.bridge.Span
import com.tibich.chordnotepad.bridge.TextEdited
import com.tibich.chordnotepad.bridge.UndoPolicy
import com.tibich.chordnotepad.text.OffsetMapper
import com.tibich.chordnotepad.text.toUtf16
import com.tibich.chordnotepad.text.toUtf16Range
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.launch

/**
 * Which version of the text the editor shows, in the session's terms: the
 * `client_token` of the `set_text` that sent it (a user edit), or the
 * `text_revision` of the session's own edit (token 0).
 */
data class TextIdentity(val clientToken: Int, val revision: Int?) {
    /** Whether [state]'s spans were computed for exactly this text. */
    fun accepts(state: HighlightState): Boolean =
        state.clientToken == clientToken && (revision == null || state.textRevision == revision)
}

/** The sounding chord, as the editor paints it and scrolls to it. */
data class PlayingChord(val start: Int, val end: Int, val chordIndex: Int?, val bar: Int)

/**
 * The editor's model, app-scoped so rotation and a recreated activity lose
 * nothing: the [TextFieldState], the highlighting painted over it and the
 * text exchange with the session. Main thread only.
 *
 * - User edits (typing, paste, undo) go to the session with `set_text` and
 *   an increasing client token ([observeText], [syncNow]).
 * - The session's own edits arrive as [TextEdited] and are applied inside
 *   `TextFieldState.edit {}` per their undo policy ([applyEdit]); they are
 *   not sent back.
 * - A [HighlightState] is painted only when it was computed for the text the
 *   editor shows ([TextIdentity.accepts]); until then the old spans move with
 *   the edits ([shiftedBy]).
 */
class EditorController(
    private val commands: SessionCommands,
    /** The editor's text, selection and undo history. */
    val state: TextFieldState = TextFieldState(),
) {
    /** The highlight spans painted now (UTF-16 offsets of the current text). */
    var spans: List<PaintedSpan> by mutableStateOf(emptyList())
        private set

    /** The chord that is sounding, or null. */
    var playing: PlayingChord? by mutableStateOf(null)
        private set

    /** The current text's identity, for picking the right `HighlightState`. */
    var identity: TextIdentity = TextIdentity(0, null)
        private set

    /**
     * Test seam: called inside [applyEdit]'s `edit {}` with the text being
     * committed, standing in for the snapshot collector that runs there on a
     * device (a JVM test has no such collector).
     */
    internal var beforeCommit: ((String) -> Unit)? = null

    // The text the session has, as far as the editor knows.
    private var syncedText: String = state.text.toString()
    // The text `spans` are laid out for.
    private var paintedText: String = syncedText
    private var lastToken = 0
    private var latestHighlight: HighlightState? = null
    private var appliedHighlight: HighlightState? = null
    private var latestPlayback: PlaybackState? = null

    /** The editor's text now (for the draft kept across process death). */
    fun currentText(): String = state.text.toString()

    /**
     * The editor's text changed (the snapshot collector calls this after
     * every change): move the painted spans and send user edits.
     */
    fun observeText(text: String) {
        if (text != paintedText) {
            diffTexts(paintedText, text)?.let { spans = spans.shiftedBy(it) }
            paintedText = text
        }
        if (text != syncedText) sendUserText(text)
    }

    /**
     * Send the text now if the session doesn't have it yet. Called before a
     * command that depends on the text (play, save, a tap), so it reaches the
     * session first, as the desktop's `set_text` before Play does.
     */
    fun syncNow() = observeText(currentText())

    /** Apply one of the session's edits per its undo policy, without echoing it back. */
    @OptIn(ExperimentalFoundationApi::class)
    fun applyEdit(edit: TextEdited) {
        val before = currentText()
        val unsent = before != syncedText
        val e = edit.toUtf16(before)
        val after = before.substring(0, e.start) + e.replacement + before.substring(e.end)
        // Bookkeeping first: committing the edit can run the snapshot
        // collector (observeText) before `edit {}` returns, and it must find
        // the new text already synced and painted for, or it would send the
        // session's own edit back as a user edit (and the highlight for it
        // would never match).
        if (paintedText != before) diffTexts(paintedText, before)?.let { spans = spans.shiftedBy(it) }
        spans = spans.shiftedBy(TextChange(e.start, e.end, e.start + e.replacement.length))
        paintedText = after
        if (!unsent) {
            syncedText = after
            identity = TextIdentity(0, edit.textRevision)
        }
        state.edit {
            // Where the device's snapshot collector can already see the new text.
            beforeCommit?.invoke(after)
            replace(e.start, e.end, e.replacement)
            selection = TextRange(e.cursor.coerceIn(0, length))
        }
        // `edit {}` records one undo step of its own (never merged): right for
        // `group` (transpose, capo) and close enough for `plain`.
        if (edit.undo == UndoPolicy.RESET) state.undoState.clearHistory()
        if (unsent) {
            // The user typed after the session last heard from the editor;
            // the editor's text wins, the session re-syncs to it.
            sendUserText(currentText())
        }
        repaintHighlight()
        repaintPlaying()
    }

    /** The session's latest highlighting. */
    fun onHighlight(state: HighlightState) {
        latestHighlight = state
        repaintHighlight()
    }

    /** The session's latest playback state. */
    fun onPlayback(state: PlaybackState?) {
        latestPlayback = state
        repaintPlaying()
    }

    /** The code-point offset of UTF-16 offset [utf16] in the current text. */
    fun codePointAt(utf16: Int): Int = OffsetMapper.of(state.text).toCodePoint(utf16)

    /** The cursor (selection start) as a code-point offset, after syncing the text. */
    fun cursorCodePoint(): Int {
        syncNow()
        return codePointAt(state.selection.min)
    }

    /** A tap at UTF-16 offset [utf16]: play the chord there, if any (the session decides). */
    fun tapAt(utf16: Int) {
        syncNow()
        commands.tapChordAt(codePointAt(utf16))
    }

    private fun sendUserText(text: String) {
        lastToken += 1
        identity = TextIdentity(lastToken, null)
        syncedText = text
        commands.setText(text, lastToken)
    }

    private fun repaintHighlight() {
        val hs = latestHighlight ?: return
        if (hs === appliedHighlight || !identity.accepts(hs)) return
        val text = currentText()
        // Typed but not observed yet: the spans are for the previous text.
        if (text != syncedText) return
        val mapper = OffsetMapper.of(text)
        spans = hs.spans.map { it.painted(mapper) }.filter { it.end > it.start }
        paintedText = text
        appliedHighlight = hs
    }

    private fun repaintPlaying() {
        val span = latestPlayback?.playingSpan
        playing = span?.let {
            val r = it.toUtf16Range(OffsetMapper.of(state.text))
            PlayingChord(r.start, r.end, latestPlayback?.chordIndex, latestPlayback?.bar ?: 0)
        }
    }

    private fun Span.painted(mapper: OffsetMapper): PaintedSpan {
        val r = toUtf16Range(mapper)
        return PaintedSpan(r.start, r.end, kind)
    }
}

/**
 * Keep [this] editor in step with the session in [scope] (main thread): the
 * editor's own changes go out, the session's edits, highlighting and playback
 * come in. Runs as long as [scope]; app-scoped in the app, so the session's
 * edits are applied even while no activity is on screen.
 */
fun EditorController.bind(scope: CoroutineScope, repository: SessionRepository): Job = scope.launch {
    launch { snapshotFlow { state.text.toString() }.collect(::observeText) }
    launch { repository.textEdits.collect(::applyEdit) }
    launch { repository.highlight.filterNotNull().collect(::onHighlight) }
    launch { repository.playback.collect(::onPlayback) }
}

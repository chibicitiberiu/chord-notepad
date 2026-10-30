package com.tibich.chordnotepad.ui.editor

import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.runtime.snapshots.Snapshot
import com.tibich.chordnotepad.bridge.HighlightState
import com.tibich.chordnotepad.bridge.PlaybackState
import com.tibich.chordnotepad.bridge.PlaybackStatus
import com.tibich.chordnotepad.bridge.SessionCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.bridge.Span
import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.bridge.TextEdited
import com.tibich.chordnotepad.bridge.UndoPolicy
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/** The repository's flows drive the editor; its own edits go out as `set_text`. */
@OptIn(ExperimentalCoroutinesApi::class)
class EditorWiringTest {
    @Test
    fun `session output reaches the editor and user edits reach the session`() = runTest(UnconfinedTestDispatcher()) {
        val sent = mutableListOf<String>()
        val repository = SessionRepository()
        val state = TextFieldState()
        val editor = EditorController(SessionCommands({ c, _ -> sent += c }), state)
        val job = editor.bind(this, repository)

        repository.publish(TextEdited(1, 0, 0, "C G", UndoPolicy.RESET, 3))
        repository.publish(HighlightState(1, 0, listOf(Span(0, 1, SpanKind.CHORD), Span(2, 3, SpanKind.CHORD))))
        assertEquals("C G", state.text.toString())
        assertEquals(2, editor.spans.size)
        repository.publish(PlaybackState(PlaybackStatus.PLAYING, Span(2, 3, SpanKind.CHORD), 1, 1, 1))
        assertEquals(PlayingChord(2, 3, 1, 1), editor.playing)

        Snapshot.sendApplyNotifications()
        runCurrent()
        assertEquals(emptyList<String>(), sent) // the session's edit isn't echoed back

        state.edit { append(" Am") }
        Snapshot.sendApplyNotifications()
        runCurrent()
        assertEquals(listOf("set_text"), sent)
        job.cancel()
    }
}

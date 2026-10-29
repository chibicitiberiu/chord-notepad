package io.github.chibicitiberiu.chordnotepad.ui.editor

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.ui.text.TextRange
import io.github.chibicitiberiu.chordnotepad.bridge.HighlightState
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackState
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.bridge.Span
import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import io.github.chibicitiberiu.chordnotepad.bridge.TextEdited
import io.github.chibicitiberiu.chordnotepad.bridge.UndoPolicy
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalFoundationApi::class)
class EditorControllerTest {
    private val sent = mutableListOf<Pair<String, JsonObject>>()
    private val commands = SessionCommands({ c, args -> sent += c to Json.parseToJsonElement(args).jsonObject })
    private val state = TextFieldState()
    private val editor = EditorController(commands, state)

    /** What the user does: an edit in the field, then the snapshot collector's call. */
    private fun type(at: Int, text: String) {
        state.edit { replace(at, at, text) }
        editor.observeText(state.text.toString())
    }

    private fun setTexts() = sent.filter { it.first == "set_text" }.map {
        it.second.getValue("text").jsonPrimitive.content to it.second.getValue("client_token").jsonPrimitive.int
    }

    private fun chord(start: Int, end: Int) = Span(start, end, SpanKind.CHORD)

    @Test
    fun `user edits go to the session with increasing tokens`() {
        type(0, "C G")
        type(3, " Am")
        assertEquals(listOf("C G" to 1, "C G Am" to 2), setTexts())
        assertEquals(TextIdentity(2, null), editor.identity)
        editor.syncNow() // nothing new: nothing sent
        assertEquals(2, setTexts().size)
    }

    @Test
    fun `stale highlight states are dropped, the matching one is painted`() {
        type(0, "C G")
        type(3, " Am")
        editor.onHighlight(HighlightState(textRevision = 1, clientToken = 1, spans = listOf(chord(0, 1))))
        assertEquals(emptyList<PaintedSpan>(), editor.spans)
        editor.onHighlight(HighlightState(2, 2, listOf(chord(0, 1), chord(2, 3), chord(4, 6))))
        assertEquals(listOf(0 to 1, 2 to 3, 4 to 6), editor.spans.map { it.start to it.end })
    }

    @Test
    fun `painted spans move with typing until the next highlight`() {
        type(0, "C G")
        editor.onHighlight(HighlightState(1, 1, listOf(chord(0, 1), chord(2, 3))))
        type(0, "Am ")
        assertEquals(listOf(3 to 4, 5 to 6), editor.spans.map { it.start to it.end })
    }

    @Test
    fun `a group edit is one undo step and isn't echoed back`() {
        type(0, "C G")
        val before = sent.size
        editor.applyEdit(TextEdited(textRevision = 2, start = 0, end = 3, replacement = "D A", undo = UndoPolicy.GROUP, cursor = 3))
        assertEquals("D A", state.text.toString())
        assertEquals(TextRange(3), state.selection)
        editor.observeText(state.text.toString()) // the collector sees the edit
        assertEquals(before, sent.size)
        assertEquals(TextIdentity(0, 2), editor.identity)
        state.undoState.undo()
        assertEquals("C G", state.text.toString())
    }

    @Test
    fun `a reset edit clears the undo history`() {
        type(0, "C G")
        editor.applyEdit(TextEdited(5, 0, 3, "Em", UndoPolicy.RESET, 2))
        assertEquals("Em", state.text.toString())
        assertFalse(state.undoState.canUndo)
    }

    @Test
    fun `a plain insert puts the cursor after it`() {
        type(0, "C G")
        editor.applyEdit(TextEdited(2, 2, 2, "Am ", UndoPolicy.PLAIN, 5))
        assertEquals("C Am G", state.text.toString())
        assertEquals(TextRange(5), state.selection)
        assertTrue(state.undoState.canUndo)
    }

    @Test
    fun `highlight for a session edit is taken by revision, even if it arrives first`() {
        type(0, "C G")
        val hs = HighlightState(textRevision = 2, clientToken = 0, spans = listOf(chord(0, 1), chord(2, 3)))
        editor.onHighlight(hs) // delivered before the edit was applied
        assertEquals(emptyList<PaintedSpan>(), editor.spans)
        editor.applyEdit(TextEdited(2, 0, 3, "D A", UndoPolicy.GROUP, 3))
        assertEquals(listOf(0 to 1, 2 to 3), editor.spans.map { it.start to it.end })
        // Older session revisions don't match.
        editor.onHighlight(HighlightState(1, 0, emptyList()))
        assertEquals(2, editor.spans.size)
    }

    @Test
    fun `typing the session hasn't seen wins over a session edit`() {
        type(0, "C G")
        state.edit { append("!") } // typed, not observed yet
        editor.applyEdit(TextEdited(2, 0, 0, "{bpm: 90}\n", UndoPolicy.PLAIN, 10))
        assertEquals("{bpm: 90}\nC G!", state.text.toString())
        assertEquals("{bpm: 90}\nC G!" to 2, setTexts().last())
        assertEquals(TextIdentity(2, null), editor.identity)
    }

    @Test
    fun `taps and the cursor are sent as code points`() {
        type(0, "😀 C G") // an emoji is two UTF-16 units, one code point
        editor.tapAt(3)
        assertEquals(2, sent.last { it.first == "tap_chord_at" }.second.getValue("offset").jsonPrimitive.int)
        state.edit { selection = TextRange(5) }
        assertEquals(4, editor.cursorCodePoint())
    }

    @Test
    fun `a tap sends unsent text first`() {
        type(0, "C G")
        state.edit { append(" Am") }
        editor.tapAt(5)
        assertEquals(listOf("set_text", "tap_chord_at"), sent.takeLast(2).map { it.first })
    }

    @Test
    fun `the playing chord is converted to UTF-16 and cleared when idle`() {
        type(0, "😀 C G")
        editor.onPlayback(PlaybackState(PlaybackStatus.PLAYING, chord(4, 5), chordIndex = 1, bar = 1, totalBars = 2))
        assertEquals(PlayingChord(5, 6, 1, 1), editor.playing)
        editor.onPlayback(PlaybackState(PlaybackStatus.IDLE))
        assertNull(editor.playing)
    }
}

package com.tibich.chordnotepad.ui.editor

import com.tibich.chordnotepad.bridge.DirectiveHint
import com.tibich.chordnotepad.bridge.HighlightState
import com.tibich.chordnotepad.bridge.SessionRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The hint strip (Edit) and the long-press explanation (Play), without a device. */
class DirectiveHintControllerTest {
    private val bpm = "{bpm: 120} · {bpm: +10}"
    private fun hint(offset: Int, syntax: String = bpm, message: String = "", redundant: Boolean = false) =
        DirectiveHint(offset, 0, 10, "bpm", syntax, message, redundant)

    @Test
    fun `the strip shows the hint for where the cursor rests and goes when it leaves`() {
        val asked = mutableListOf<Int>()
        val c = DirectiveHintController { asked += it }
        c.onCursor(3)
        assertEquals(listOf(3), asked)
        c.onHint(hint(3))
        assertEquals(HintCard("", false, "{bpm: 120} · {bpm: +10}"), c.strip)
        c.onCursor(20)
        c.onHint(DirectiveHint(20, 20, 20, "", "", ""))
        assertNull(c.strip)
    }

    @Test
    fun `an invalid directive's reason is an error, a redundant one's isn't`() {
        val c = DirectiveHintController {}
        c.onCursor(3)
        c.onHint(hint(3, message = "Tempo must be 20-400"))
        assertEquals(true, c.strip?.error)
        assertEquals("Tempo must be 20-400", c.strip?.reason)
        c.onHint(hint(3, message = "Has no effect: replaced by {bpm: 90} on line 2", redundant = true))
        assertEquals(false, c.strip?.error)
    }

    @Test
    fun `a stale reply is dropped and no cursor hides the strip at once`() {
        val c = DirectiveHintController {}
        c.onCursor(3)
        c.onHint(hint(2))
        assertNull(c.strip)
        c.onHint(hint(3))
        c.onCursor(null)
        assertNull(c.strip)
    }

    @Test
    fun `coming back to an offset reuses its reply, which the repository won't repeat`() {
        val c = DirectiveHintController {}
        c.onCursor(3)
        c.onHint(hint(3))
        c.onCursor(null)
        c.onCursor(3)
        assertEquals("", c.strip?.reason)
    }

    @Test
    fun `half-typed keywords give one syntax line per candidate`() {
        val card = HintCard.of(hint(2, syntax = "{label: verse}\n{loop: verse} · {loop: verse 3}"))
        assertEquals("{label: verse}\n{loop: verse} · {loop: verse 3}", card?.syntax)
    }

    @Test
    fun `a long-press explains only a directive with a reason`() {
        val asked = mutableListOf<Int>()
        val c = DirectiveHintController { asked += it }
        c.explain(0)
        assertEquals(listOf(0), asked)
        c.onHint(DirectiveHint(0, 0, 8, "bpm", bpm, "Tempo must be 20-400"))
        assertEquals(ExplainedDirective(HintCard("Tempo must be 20-400", true, HintCard.wrapFriendly(bpm)), 0, 8), c.explained)
        c.dismiss()
        assertNull(c.explained)
        // A late reply after dismissing doesn't bring it back.
        c.onHint(DirectiveHint(0, 0, 8, "bpm", bpm, "Tempo must be 20-400"))
        assertNull(c.explained)
        c.explain(0) // the same reply again: shown from the one kept
        assertEquals("Tempo must be 20-400", c.explained?.card?.reason)
        c.dismiss()
        c.explain(30)
        c.onHint(DirectiveHint(30, 30, 40, "key", "{key: G}", ""))
        assertNull(c.explained)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun `cursor moves are debounced into one request`() = runTest(StandardTestDispatcher()) {
        val asked = mutableListOf<Int>()
        val repository = SessionRepository()
        val c = DirectiveHintController { asked += it }
        val cursor = MutableStateFlow<Int?>(null)
        val job = c.bind(this, repository, cursor)
        runCurrent()
        for (offset in 1..5) {
            cursor.value = offset
            advanceTimeBy(HINT_DEBOUNCE_MS / 3)
        }
        advanceTimeBy(HINT_DEBOUNCE_MS + 1)
        assertEquals(listOf(5), asked)
        repository.publish(hint(5))
        runCurrent()
        assertEquals("", c.strip?.reason)
        // New highlighting asks again for the same place (a reason may have changed).
        repository.publish(HighlightState(1, 0, emptyList()))
        runCurrent()
        assertEquals(listOf(5, 5), asked)
        cursor.value = null
        runCurrent()
        assertNull(c.strip)
        job.cancel()
    }

    @Test
    fun `the card goes under the directive, or above it at the bottom of the view`() {
        assertEquals(126f, explainCardTop(100f, 120f, 60f, viewTop = 0f, viewBottom = 800f, gap = 6f))
        assertEquals(714f, explainCardTop(780f, 800f, 60f, viewTop = 0f, viewBottom = 820f, gap = 6f))
        // No room above either: under it, and the view scrolls.
        assertEquals(36f, explainCardTop(10f, 30f, 60f, viewTop = 0f, viewBottom = 80f, gap = 6f))
    }
}

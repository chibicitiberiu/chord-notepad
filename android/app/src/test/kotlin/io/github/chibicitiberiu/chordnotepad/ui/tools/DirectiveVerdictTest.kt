package io.github.chibicitiberiu.chordnotepad.ui.tools

import io.github.chibicitiberiu.chordnotepad.bridge.DirectiveCheck
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DirectiveVerdictTest {
    private val answer = mapOf("value" to "999")

    private fun check(
        fields: Map<String, String> = answer,
        errors: Map<String, String> = emptyMap(),
        formError: String = "",
        requestId: Int = 3,
    ) = DirectiveCheck("bpm", requestId, fields, errors, formError)

    @Test
    fun `no reply yet disables Insert and shows nothing`() {
        assertEquals(DirectiveVerdict(false, emptyList()), DirectiveVerdict.of("bpm", 3, answer, null, true))
    }

    @Test
    fun `a clean reply for the current fields enables Insert`() {
        assertTrue(DirectiveVerdict.of("bpm", 3, answer, check(), true).canInsert)
    }

    @Test
    fun `an error keeps Insert disabled and is shown once the user changed something`() {
        val bad = check(errors = mapOf("value" to "BPM must be between 20 and 300."))
        val shown = DirectiveVerdict.of("bpm", 3, answer, bad, showErrors = true)
        assertFalse(shown.canInsert)
        assertEquals(listOf("BPM must be between 20 and 300."), shown.messages)
        assertEquals(emptyList<String>(), DirectiveVerdict.of("bpm", 3, answer, bad, showErrors = false).messages)
    }

    @Test
    fun `a form-level error is shown too`() {
        val v = DirectiveVerdict.of("bpm", 3, answer, check(formError = "Nope"), true)
        assertFalse(v.canInsert)
        assertEquals(listOf("Nope"), v.messages)
    }

    @Test
    fun `a late reply for older fields or another request is ignored`() {
        val stale = check(fields = mapOf("value" to "99"))
        assertFalse(DirectiveVerdict.of("bpm", 3, answer, stale, true).canInsert)
        assertFalse(DirectiveVerdict.of("bpm", 4, answer, check(), true).canInsert)
        assertFalse(DirectiveVerdict.of("label", 3, answer, check(), true).canInsert)
    }
}

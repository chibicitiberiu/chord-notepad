package io.github.chibicitiberiu.chordnotepad.bridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Invalid-directive reasons on spans, and the `DirectiveHint` reply. */
class DirectiveHintTest {
    @Test
    fun `an invalid directive span carries its reason`() {
        val out = BridgeCodec.decode(
            "HighlightState",
            """{"text_revision": 1, "client_token": 0, "spans": [
               {"start": 0, "end": 8, "kind": "directive_invalid", "message": "Tempo must be 20-400"},
               {"start": 9, "end": 10, "kind": "chord", "message": ""}]}""",
        )
        assertTrue(out is HighlightState)
        assertEquals(
            listOf(
                Span(0, 8, SpanKind.DIRECTIVE_INVALID, "Tempo must be 20-400"),
                Span(9, 10, SpanKind.CHORD),
            ),
            (out as HighlightState).spans,
        )
    }

    @Test
    fun `a directive hint decodes`() {
        val out = BridgeCodec.decode(
            "DirectiveHint",
            """{"offset": 2, "start": 0, "end": 8, "keyword": "bpm",
               "syntax": "{bpm: 120} · {bpm: +10}", "message": "Tempo must be 20-400"}""",
        )
        assertEquals(DirectiveHint(2, 0, 8, "bpm", "{bpm: 120} · {bpm: +10}", "Tempo must be 20-400"), out)
    }
}

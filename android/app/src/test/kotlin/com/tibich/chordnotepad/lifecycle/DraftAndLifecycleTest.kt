package com.tibich.chordnotepad.lifecycle

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.SessionCommands
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DraftAndLifecycleTest {
    private val sent = mutableListOf<Pair<String, JsonElement>>()
    private val commands = SessionCommands({ c, a -> sent += c to Json.parseToJsonElement(a) })

    @Test
    fun `nothing worth saving, or too big`() {
        assertNull(DraftPolicy.toSave(null, "p"))
        assertNull(DraftPolicy.toSave(Draft("", null, false), "p"))
        assertNull(DraftPolicy.toSave(Draft("x".repeat(11), null, true), "p", maxChars = 10))
        assertEquals(SavedDraft("p", Draft("", "content://a", false)), DraftPolicy.toSave(Draft("", "content://a", false), "p"))
    }

    @Test
    fun `restore only after process death`() {
        val saved = SavedDraft("old-process", Draft("C G", null, true))
        assertNull(DraftPolicy.toRestore(saved, "old-process")) // rotation: same process
        assertEquals(saved.draft, DraftPolicy.toRestore(saved, "new-process"))
        assertNull(DraftPolicy.toRestore(null, "new-process"))
    }

    @Test
    fun `restore sends the text with its document`() {
        val ref = DocumentRef("content://a", "a.txt", "a.txt")
        DraftPolicy.restore(Draft("C G", "content://a", false), { ref }, commands)
        assertEquals("restore_draft", sent.single().first)
        assertEquals(
            Json.parseToJsonElement(
                """{"text": "C G", "document": {"id": "content://a", "display_name": "a.txt", "location": "a.txt"},
                   "modified": false}""",
            ),
            sent.single().second,
        )
    }

    @Test
    fun `an unreachable document is dropped and the text kept as unsaved`() {
        DraftPolicy.restore(Draft("C G", "content://gone", false), { null }, commands)
        assertEquals(
            Json.parseToJsonElement("""{"text": "C G", "document": null, "modified": true}"""),
            sent.single().second,
        )
    }

    @Test
    fun `process start and stop reach the session`() {
        val hooks = AppLifecycleHooks(commands)
        val owner = object : LifecycleOwner {
            override val lifecycle: Lifecycle get() = error("unused")
        }
        hooks.onStart(owner)
        hooks.onStop(owner)
        assertEquals(listOf("app_foreground", "app_background"), sent.map { it.first })
    }
}

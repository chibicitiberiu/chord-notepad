package io.github.chibicitiberiu.chordnotepad.ui.requests

import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.ConfirmDiscardRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.bridge.MenuItem
import io.github.chibicitiberiu.chordnotepad.bridge.PickDocumentRequest
import io.github.chibicitiberiu.chordnotepad.bridge.PickMode
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRequest
import io.github.chibicitiberiu.chordnotepad.files.OPEN_MIME_TYPES
import io.github.chibicitiberiu.chordnotepad.files.PickerLaunch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RequestControllerTest {
    private val pending = MutableStateFlow<SessionRequest?>(null)
    private val sent = mutableListOf<Pair<String, JsonElement>>()
    private val adopted = mutableListOf<Pair<String, PickMode>>()
    private var adoptFails = false
    private val offMain = mutableListOf<() -> Unit>()

    // Answering clears the pending request, as SessionRepository.requestAnswered does.
    private val commands = SessionCommands(
        submitter = { command, args -> sent += command to Json.parseToJsonElement(args) },
        onResponded = { id -> pending.update { if (it?.requestId == id) null else it } },
    )

    private fun controller() = RequestController(
        pending = pending,
        commands = commands,
        adopt = { uri, mode ->
            adopted += uri to mode
            if (adoptFails) throw SecurityException("revoked")
            DocumentRef(uri, "song.txt", "Downloads/song.txt")
        },
        runOffMain = { offMain += it },
    )

    private fun assertResponded(json: String) {
        val (command, args) = sent.removeAt(0)
        assertEquals("respond", command)
        assertEquals(Json.parseToJsonElement(json), args)
    }

    private fun runOffMain() {
        offMain.toList().forEach { it() }
        offMain.clear()
    }

    @Test
    fun `each request kind gets its presentation`() {
        assertEquals(RequestPresentation.Dialog(ConfirmDiscardRequest(1)), presentationOf(ConfirmDiscardRequest(1)))
        val pick = PickDocumentRequest(2, PickMode.OPEN, "")
        assertEquals(RequestPresentation.Picker(pick), presentationOf(pick))
        val capo = CapoChoiceRequest(3, listOf(MenuItem("Piano", "piano")), "piano")
        assertEquals(RequestPresentation.Dialog(capo), presentationOf(capo))
        val directive = InsertDirectiveRequest(4, "bpm", emptyList(), "american")
        assertEquals(RequestPresentation.Dialog(directive), presentationOf(directive))
    }

    @Test
    fun `open launches the picker once and answers with the adopted ref`() {
        val c = controller()
        pending.value = PickDocumentRequest(7, PickMode.OPEN, "")
        assertEquals(PickerLaunch.Open(OPEN_MIME_TYPES), c.onPending(pending.value))
        // A recreated activity sees the same request again: no second picker.
        assertNull(c.onPending(pending.value))
        assertNull(c.takePickerLaunch())

        c.onPicked("content://docs/song")
        assertTrue(sent.isEmpty()) // adopting does provider I/O: off the main thread
        runOffMain()
        assertEquals(listOf("content://docs/song" to PickMode.OPEN), adopted)
        assertResponded(
            """{"request_id": 7, "value": {"id": "content://docs/song", "display_name": "song.txt",
                "location": "Downloads/song.txt"}}""",
        )
        assertNull(pending.value)
    }

    @Test
    fun `save and export create documents with the suggested names`() {
        val c = controller()
        pending.value = PickDocumentRequest(1, PickMode.SAVE, "song.txt")
        assertEquals(PickerLaunch.Create("text/plain", "song.txt"), c.takePickerLaunch())
        c.onPicked(null)
        pending.value = PickDocumentRequest(2, PickMode.EXPORT_MIDI, "song.mid")
        assertEquals(PickerLaunch.Create("audio/midi", "song.mid"), c.takePickerLaunch())
        c.onPicked("content://docs/song.mid")
        runOffMain()
        assertEquals(listOf("content://docs/song.mid" to PickMode.EXPORT_MIDI), adopted)
    }

    @Test
    fun `backing out of the picker cancels with null`() {
        val c = controller()
        pending.value = PickDocumentRequest(3, PickMode.SAVE, "Untitled.txt")
        c.onPending(pending.value)
        c.onPicked(null)
        assertResponded("""{"request_id": 3, "value": null}""")
        assertTrue(offMain.isEmpty())
        assertNull(pending.value)
    }

    @Test
    fun `a document that can't be adopted answers null`() {
        val c = controller()
        adoptFails = true
        pending.value = PickDocumentRequest(4, PickMode.OPEN, "")
        c.onPending(pending.value)
        c.onPicked("content://docs/gone")
        runOffMain()
        assertResponded("""{"request_id": 4, "value": null}""")
    }

    @Test
    fun `a stale picker result is ignored`() {
        val c = controller()
        // Nothing pending (the process died while the picker was open).
        c.onPicked("content://docs/song")
        // A pick request the picker wasn't launched for.
        pending.value = PickDocumentRequest(5, PickMode.OPEN, "")
        c.onPicked("content://docs/song")
        runOffMain()
        assertTrue(sent.isEmpty())
        assertTrue(adopted.isEmpty())
    }

    @Test
    fun `a new pick request gets its own picker`() {
        val c = controller()
        pending.value = PickDocumentRequest(1, PickMode.OPEN, "")
        c.takePickerLaunch()
        c.onPicked(null)
        pending.value = PickDocumentRequest(2, PickMode.OPEN, "")
        assertEquals(PickerLaunch.Open(OPEN_MIME_TYPES), c.onPending(pending.value))
    }

    @Test
    fun `unsaved changes answers save, discard or cancel`() {
        val c = controller()
        for ((choice, value) in listOf(DiscardChoice.SAVE to "save", DiscardChoice.DISCARD to "discard", DiscardChoice.CANCEL to "cancel")) {
            val request = ConfirmDiscardRequest(10)
            pending.value = request
            assertNull(c.onPending(request)) // a dialog, not a picker
            assertTrue(sent.isEmpty())
            c.answerDiscard(request, choice)
            assertResponded("""{"request_id": 10, "value": "$value"}""")
            assertNull(pending.value)
        }
        // Dismissing the dialog is Cancel.
        pending.value = ConfirmDiscardRequest(11)
        c.answerDiscard(ConfirmDiscardRequest(11), null)
        assertResponded("""{"request_id": 11, "value": "cancel"}""")
    }

    @Test
    fun `capo and directive requests wait for their dialogs, then answer`() {
        val c = controller()
        val capo = CapoChoiceRequest(20, listOf(MenuItem("Standard", "guitar:standard")), "guitar:standard")
        pending.value = capo
        assertNull(c.onPending(capo)) // a dialog: nothing sent yet
        assertTrue(sent.isEmpty())
        c.answerCapo(capo, "guitar:standard")
        assertResponded("""{"request_id": 20, "value": "guitar:standard"}""")
        assertNull(pending.value)

        val label = InsertDirectiveRequest(21, "label", listOf("verse"), "american")
        pending.value = label
        assertNull(c.onPending(label))
        assertTrue(sent.isEmpty())
        c.answerDirective(label, mapOf("label" to "chorus"))
        assertResponded("""{"request_id": 21, "value": {"label": "chorus"}}""")
        assertNull(pending.value)

        // Cancel answers null.
        pending.value = CapoChoiceRequest(22, capo.options, capo.default)
        c.answerCapo(pending.value as CapoChoiceRequest, null)
        assertResponded("""{"request_id": 22, "value": null}""")
        pending.value = InsertDirectiveRequest(23, "bpm", emptyList(), "american")
        c.answerDirective(pending.value as InsertDirectiveRequest, null)
        assertResponded("""{"request_id": 23, "value": null}""")
    }

    @Test
    fun `cancel answers every kind with null or cancel`() {
        val c = controller()
        c.cancel(ConfirmDiscardRequest(1))
        assertResponded("""{"request_id": 1, "value": "cancel"}""")
        c.cancel(PickDocumentRequest(2, PickMode.OPEN, ""))
        assertResponded("""{"request_id": 2, "value": null}""")
    }

    @Test
    fun `nothing pending does nothing`() {
        assertNull(controller().onPending(null))
        assertTrue(sent.isEmpty())
    }
}

package io.github.chibicitiberiu.chordnotepad.ui.tools

import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.CommandSubmitter
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.bridge.MenuItem
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.bridge.Selection
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ToolFormsTest {
    @Test
    fun `no selection is the whole song`() {
        assertNull(selectionOf("C G Am F", 3, 3))
        assertNull(selectionOf("", 0, 0))
    }

    @Test
    fun `a selection maps to code points, either direction`() {
        assertEquals(Selection(2, 6), selectionOf("C G Am F", 2, 6))
        assertEquals(Selection(2, 6), selectionOf("C G Am F", 6, 2))
        // An emoji is two UTF-16 units but one code point.
        val text = "🎸 C G Am"
        assertEquals(Selection(2, 5), selectionOf(text, 3, 6))
        assertEquals(Selection(0, 1), selectionOf(text, 0, 2))
        // Both ends inside the same pair select nothing.
        assertNull(selectionOf(text, 0, 1))
    }

    @Test
    fun `transpose steps stay within -11 and +11`() {
        var form = TransposeForm()
        repeat(15) { form = form.up() }
        assertEquals(11, form.semitones)
        repeat(30) { form = form.down() }
        assertEquals(-11, form.semitones)
    }

    @Test
    fun `each directive kind answers with the fields the session takes`() {
        val keys = listOf("C", "G", "D")
        assertEquals(mapOf("value" to "+20"), DirectiveForm.initial(DirectiveKind.BPM, keys).copy(bpm = "+20").answer())
        assertEquals(
            mapOf("beats" to "3", "unit" to "8"),
            DirectiveForm.initial(DirectiveKind.TIME, keys).copy(beats = 3, unit = 8).answer(),
        )
        assertEquals(mapOf("beats" to "4", "unit" to "4"), DirectiveForm.initial(DirectiveKind.TIME, keys).answer())
        assertEquals(mapOf("key" to "C"), DirectiveForm.initial(DirectiveKind.KEY, keys).answer())
        assertEquals(mapOf("label" to "verse"), DirectiveForm.initial(DirectiveKind.LABEL, keys).copy(label = "verse").answer())
        assertEquals(mapOf("label" to "@start", "count" to "2"), DirectiveForm.initial(DirectiveKind.LOOP, keys).answer())
    }

    @Test
    fun `values go as typed, Python checks them`() {
        // Not trimmed or validated here: "abc" and a duplicate label reach the session as they are.
        val form = DirectiveForm(DirectiveKind.BPM, bpm = " abc ")
        assertEquals(mapOf("value" to " abc "), form.answer())
    }

    @Test
    fun `loop count stays within 1 and 100`() {
        var form = DirectiveForm(DirectiveKind.LOOP)
        repeat(5) { form = form.fewerRepeats() }
        assertEquals(1, form.count)
        repeat(200) { form = form.moreRepeats() }
        assertEquals(100, form.count)
    }

    @Test
    fun `a form survives save and restore`() {
        val form = DirectiveForm(DirectiveKind.LOOP, loopLabel = "chorus", count = 7, bpm = "90")
        assertEquals(form, DirectiveForm.restore(form.save()))
        assertNull(DirectiveForm.restore(listOf("nonsense")))
    }

    @Test
    fun `directive kinds by wire name`() {
        assertEquals(DirectiveKind.TIME, DirectiveKind.of("time"))
        assertNull(DirectiveKind.of("capo"))
    }

    @Test
    fun `loop targets are the start then the labels`() {
        val request = InsertDirectiveRequest(1, "loop", listOf("chorus", "verse"), "american")
        assertEquals(listOf("@start", "chorus", "verse"), loopChoices(request))
        assertEquals(listOf("@start"), loopChoices(request.copy(existingLabels = emptyList())))
    }

    @Test
    fun `keys come from the request's notation`() {
        val am = listOf("C", "D")
        val eu = listOf("Do", "Re")
        assertEquals(am, keyChoices("american", am, eu, listOf("X")))
        assertEquals(eu, keyChoices("european", am, eu, listOf("X")))
        assertEquals(listOf("X"), keyChoices("european", null, null, listOf("X")))
        assertEquals(emptyList<String>(), keyChoices("american", null, null, null))
    }

    @Test
    fun `capo starts on the default voicing, else the first`() {
        val options = listOf(MenuItem("Standard", "g:std"), MenuItem("Drop D", "g:dropd"))
        assertEquals("g:dropd", initialCapoChoice(CapoChoiceRequest(1, options, "g:dropd")))
        assertEquals("g:std", initialCapoChoice(CapoChoiceRequest(1, options, "piano")))
        assertNull(initialCapoChoice(CapoChoiceRequest(1, emptyList(), "")))
    }

    // -- the commands the Tools menu sends -----------------------------------------

    private val sent = mutableListOf<Pair<String, JsonElement>>()
    private var text: CharSequence = "C G Am F"
    private var sel = 0 to 0
    private var syncs = 0

    private fun tools(): ToolActions {
        val submitter = CommandSubmitter { command, args -> sent += command to Json.parseToJsonElement(args) }
        return ToolActions(
            commands = SessionCommands(submitter),
            screen = ScreenCommands(submitter),
            sync = { syncs++ },
            selectionNow = { Triple(text, sel.first, sel.second) },
            cursorNow = { 4 },
        )
    }

    private fun assertSent(command: String, json: String) {
        val (c, args) = sent.removeAt(0)
        assertEquals(command, c)
        assertEquals(Json.parseToJsonElement(json), args)
    }

    @Test
    fun `transpose sends the selection in code points, or null`() {
        val t = tools()
        t.transpose(2, t.selection())
        assertSent("transpose", """{"semitones": 2, "selection": null}""")
        text = "🎸 C G Am"
        sel = 3 to 6
        t.transpose(-1, t.selection())
        assertSent("transpose", """{"semitones": -1, "selection": [2, 5]}""")
        assertTrue(syncs >= 2) // the text goes first
    }

    @Test
    fun `insert, capo, convert and the identifier's insert`() {
        val t = tools()
        t.insertDirective(DirectiveKind.LABEL)
        assertSent("request_insert_directive", """{"kind": "label", "at": 4}""")
        sel = 2 to 6
        t.suggestCapo()
        assertSent("request_suggest_capo", """{"selection": [2, 6]}""")
        t.convertNotation("european")
        assertSent("convert_notation", """{"target": "european"}""")
        t.insertChord("Am7")
        assertSent("insert_chord", """{"at": 4, "chord": "Am7"}""")
    }
}

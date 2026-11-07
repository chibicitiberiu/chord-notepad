package com.tibich.chordnotepad.ui.tools

import com.tibich.chordnotepad.bridge.CapoChoiceRequest
import com.tibich.chordnotepad.bridge.CommandSubmitter
import com.tibich.chordnotepad.bridge.InsertDirectiveRequest
import com.tibich.chordnotepad.bridge.MenuItem
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.Selection
import com.tibich.chordnotepad.bridge.SessionCommands
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
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
        assertEquals(DirectiveKind.CAPO, DirectiveKind.of("capo"))
        assertNull(DirectiveKind.of("chord"))
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
        // C5: the request's own list (majors and minors with a signature) comes first.
        val withKeys = InsertDirectiveRequest(1, "key", emptyList(), "american", keyOptions = listOf("C", "Am", "Cb"))
        assertEquals(listOf("C", "Am", "Cb"), keyChoices(withKeys, am, eu, listOf("X")))
        assertEquals(am, keyChoices(InsertDirectiveRequest(1, "key", emptyList(), "american"), am, eu, listOf("X")))
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
        // P2: with the cursor, so the session keeps it on its line and column.
        assertSent("transpose", """{"semitones": 2, "selection": null, "cursor": 4}""")
        text = "🎸 C G Am"
        sel = 3 to 6
        t.transpose(-1, t.selection())
        assertSent("transpose", """{"semitones": -1, "selection": [2, 5], "cursor": 4}""")
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
        assertSent("convert_notation", """{"target": "european", "cursor": 4}""")
        t.insertChord("Am7")
        assertSent("insert_chord", """{"at": 4, "chord": "Am7"}""")
    }

    @Test
    fun `a restored or changed directive field puts the cursor at the end`() {
        // L6: after a rotation the field had the cursor at 0, so "Z" typed "Zabc".
        assertEquals(TextFieldValue("abc", TextRange(3)), fieldValueFor(null, "abc"))
        val typing = TextFieldValue("abc", TextRange(1, 2))
        assertEquals(typing, fieldValueFor(typing, "abc"))
        assertEquals(TextFieldValue("95", TextRange(2)), fieldValueFor(typing, "95"))
        // The saver keeps the selection across the rotation itself.
        val saved = with(TextFieldValue.Saver) { androidx.compose.runtime.saveable.SaverScope { true }.save(typing) }
        assertEquals(typing, TextFieldValue.Saver.restore(saved!!))
    }
}

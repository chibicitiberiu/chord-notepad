package io.github.chibicitiberiu.chordnotepad.ui.identifier

import io.github.chibicitiberiu.chordnotepad.bridge.CommandSubmitter
import io.github.chibicitiberiu.chordnotepad.bridge.IdentifierNote
import io.github.chibicitiberiu.chordnotepad.bridge.IdentifierState
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class IdentifierTest {
    private val piano = PianoKeyboard()

    @Test
    fun `two octaves from C4, 14 white and 10 black keys`() {
        assertEquals(24, piano.keys.size)
        assertEquals(14, piano.keys.count { !it.isBlack })
        assertEquals((60..83).toSet(), piano.keys.map { it.midi }.toSet())
        val c4 = piano.keys.first()
        assertEquals(PianoKey("C", 4, 60, false, 0f, 1f), c4)
        val b5 = piano.keys.filter { !it.isBlack }.last()
        assertEquals(Triple("B", 5, 83), Triple(b5.name, b5.octave, b5.midi))
        val black = piano.keys.filter { it.isBlack }.map { "${it.name}${it.octave}" }
        assertEquals(listOf("C#4", "D#4", "F#4", "G#4", "A#4", "C#5", "D#5", "F#5", "G#5", "A#5"), black)
    }

    @Test
    fun `midi numbers`() {
        assertEquals(60, PianoKeyboard.midiOf(0, 4))
        assertEquals(69, PianoKeyboard.midiOf(9, 4))
        assertEquals(72, PianoKeyboard.midiOf(0, 5))
    }

    @Test
    fun `hit testing puts black keys on top`() {
        // 14 white keys of 30 px, 120 px tall, like the desktop.
        val w = 420f
        val h = 120f
        fun at(x: Float, y: Float) = piano.keyAt(x, y, w, h)?.let { "${it.name}${it.octave}" }
        assertEquals("C4", at(5f, 100f))
        assertEquals("C4", at(5f, 10f)) // left of C#'s edge (21 px)
        assertEquals("C#4", at(25f, 10f))
        assertEquals("C4", at(25f, 100f)) // below C#: still C
        assertEquals("D4", at(35f, 100f))
        assertEquals("E4", at(75f, 10f)) // no black key between E and F
        assertEquals("F#5", at(7 * 30f + 3.7f * 30f + 5f, 30f))
        assertEquals("B5", at(419f, 100f))
        assertNull(at(-1f, 10f))
        assertNull(at(420f, 10f))
        assertNull(at(10f, 120f))
    }

    @Test
    fun `selected keys by midi, notes off the keyboard skipped`() {
        assertEquals(setOf("C", "E", "G"), piano.selected(listOf(60, 64, 67, 100)).map { it.name }.toSet())
    }

    // -- the screen's model ------------------------------------------------------------

    private val sent = mutableListOf<Pair<String, JsonElement>>()
    private val inserted = mutableListOf<String>()
    private val model = IdentifierModel(
        ScreenCommands(CommandSubmitter { c, a -> sent += c to Json.parseToJsonElement(a) }),
        insertAtCursor = { inserted += it },
    )

    private fun assertSent(command: String, json: String) {
        val (c, args) = sent.removeAt(0)
        assertEquals(command, c)
        assertEquals(Json.parseToJsonElement(json), args)
    }

    private fun state(text: String, vararg candidates: String) = IdentifierState(
        notes = listOf(IdentifierNote("C", 4, 60)),
        notesText = text,
        candidates = candidates.toList(),
    )

    @Test
    fun `opening clears, keys toggle and play`() {
        model.open()
        assertSent("identifier_clear", "{}")
        val e4 = piano.keys.first { it.midi == 64 }
        model.tapKey(e4)
        assertSent("identifier_toggle_note", """{"note": "E", "octave": 4}""")
        model.pressKey(e4)
        assertSent("play_note", """{"note": "E", "octave": 4}""")
    }

    @Test
    fun `the field follows a key tap but not the session while typing`() {
        model.tapKey(piano.keys.first())
        model.onState(state("C4"))
        assertEquals("C4", model.typed)
        sent.clear()

        model.type("C E")
        assertSent("identifier_set_notes_text", """{"text": "C E"}""")
        // The state for the typed text doesn't rewrite the field.
        model.onState(state("C4 E4"))
        assertEquals("C E", model.typed)
        // Same text again sends nothing.
        model.type("C E")
        assertTrue(sent.isEmpty())
    }

    @Test
    fun `candidates play when picked and insert at the cursor`() {
        model.insert()
        assertTrue(inserted.isEmpty()) // nothing picked
        model.pick("C")
        assertSent("play_identified_chord", """{"chord": "C"}""")
        model.insert()
        model.insert("Am7") // double tap
        assertEquals(listOf("C", "Am7"), inserted)
    }

    @Test
    fun `a pick that is no longer a candidate is dropped, clear resets`() {
        model.pick("C")
        model.onState(state("C4", "C", "Am7"))
        assertEquals("C", model.picked)
        model.onState(state("D4", "Dm"))
        assertNull(model.picked)
        model.type("C")
        model.clear()
        assertEquals("", model.typed)
        assertEquals("identifier_clear", sent.last().first)
    }
}

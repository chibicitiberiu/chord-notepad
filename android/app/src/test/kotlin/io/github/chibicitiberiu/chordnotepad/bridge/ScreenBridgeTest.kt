package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** The M5 screens' DTOs and commands against bridge_schema.json, and their wire forms. */
class ScreenBridgeTest {
    private fun schema(): JsonObject {
        val file = System.getProperty("cn.bridgeSchema")?.let(::File)
        assumeTrue("bridge_schema.json not generated", file != null && file.isFile)
        return Json.parseToJsonElement(file!!.readText()).jsonObject
    }

    private fun KSerializer<*>.names(): Set<String> =
        (0 until descriptor.elementsCount).map(descriptor::getElementName).toSet()

    @Test
    fun `nested value types match the schema`() {
        val types = schema().getValue("types").jsonObject
        val values = mapOf(
            "IdentifierNote" to IdentifierNote.serializer(),
            "SettingsValues" to SettingsValues.serializer(),
            "VoicingGroup" to VoicingGroup.serializer(),
            "VoicingPreset" to VoicingPreset.serializer(),
            "QuickStartPage" to QuickStartPage.serializer(),
            "QuickStartBlock" to QuickStartBlock.serializer(),
        )
        for ((name, serializer) in values) {
            val fields = types.getValue(name).jsonObject.getValue("fields").jsonObject.keys
            assertEquals("fields of $name", fields, serializer.names())
        }
    }

    @Test
    fun `Python accepts every screen command Kotlin sends`() {
        val python = schema().getValue("commands").jsonArray.map { it.jsonPrimitive.content }.toSet()
        assertEquals(emptySet<String>(), ScreenCommandNames.ALL - python)
    }

    @Test
    fun `screen outputs decode`() {
        val identifier = BridgeCodec.decode(
            "IdentifierState",
            """{"notes":[{"name":"C","octave":4,"midi":60}],"notes_text":"C","typed_text_error":null,
               "candidates":["C5"],"message":null}""",
        ) as IdentifierState
        assertEquals(60, identifier.notes.single().midi)
        assertNull(identifier.message)

        val editor = BridgeCodec.decode(
            "VoicingEditorState",
            """{"active":true,"revision":3,"groups":[{"model":"fretboard","label":"Fretboard",
               "names":["Bass"]}],"invalid":[],"presets":[{"label":"Guitar","group":"fretboard"}],
               "selected":"Bass","model":"fretboard","values":{"max_fret":"12","allow_barres":true},
               "field_errors":{"max_fret":"Must be a whole number"},"form_errors":[],"hints":{},
               "dirty":false}""",
        ) as VoicingEditorState
        assertEquals(JsonPrimitive("12"), editor.values["max_fret"])
        assertEquals(setOf("max_fret"), editor.fieldErrors.keys)

        val tour = BridgeCodec.decode(
            "QuickStartContent",
            """{"pages":[{"title":"Hi","blocks":[{"kind":"snippet","text":"C","notation":"american",
               "spans":[{"start":0,"end":1,"kind":"chord"}],"image":null}]}],"show_on_startup":true}""",
        ) as QuickStartContent
        assertEquals(SpanKind.CHORD, tour.pages.single().blocks.single().spans.single().kind)

        val repository = SessionRepository()
        repository.publish(editor)
        repository.publish(identifier)
        repository.publish(tour)
        assertEquals(editor, repository.voicingEditor.value)
        assertEquals(identifier, repository.identifier.value)
        assertTrue(repository.quickStart.value!!.showOnStartup)
    }

    @Test
    fun `screen commands use the AppSession parameter names`() {
        val sent = mutableListOf<Pair<String, JsonElement>>()
        val commands = ScreenCommands { command, args -> sent += command to Json.parseToJsonElement(args) }
        fun assertSent(command: String, json: String) {
            val (c, args) = sent.removeAt(0)
            assertEquals(command, c)
            assertEquals(Json.parseToJsonElement(json), args)
        }

        commands.identifierToggleNote("C#", 4)
        assertSent("identifier_toggle_note", """{"note":"C#","octave":4}""")
        commands.identifierSetNotesText("C E G")
        assertSent("identifier_set_notes_text", """{"text":"C E G"}""")
        commands.playNote("A", 3)
        assertSent("play_note", """{"note":"A","octave":3}""")
        commands.playIdentifiedChord("Am")
        assertSent("play_identified_chord", """{"chord":"Am"}""")
        commands.insertChord(4, "Am")
        assertSent("insert_chord", """{"at":4,"chord":"Am"}""")

        val values = SettingsValues("TkFixedFont", 11, "american", "", true, 10, 120, 4, 4)
        commands.saveSettings(values)
        assertSent(
            "save_settings",
            """{"values":{"font_family":"TkFixedFont","font_size":11,"notation":"american","key":"",
               "show_quick_start_on_startup":true,"max_recent_files":10,"bpm":120,
               "time_signature_beats":4,"time_signature_unit":4}}""",
        )
        commands.saveSettings(null)
        assertSent("save_settings", """{"values":null}""")
        commands.setVoicingValues(JsonObject(mapOf("max_fret" to JsonPrimitive("14"))))
        assertSent("set_voicing_values", """{"values":{"max_fret":"14"}}""")
        commands.removeVoicingRecord(1)
        assertSent("remove_voicing_record", """{"index":1,"field_id":"voices"}""")
        commands.loadVoicingPreset(VoicingPreset("SATB Choir", "ensemble"))
        assertSent("load_voicing_preset", """{"group":"ensemble","label":"SATB Choir"}""")
        commands.renameVoicing("A", "B")
        assertSent("rename_voicing", """{"old":"A","new":"B"}""")
    }
}

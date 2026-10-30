package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.VoicingEditorState
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The schema-driven voicing form against what Python sends (fixtures from a real session). */
class VoicingFormTest {
    private val schema = Fixtures.schema

    private fun formOf(state: VoicingEditorState) =
        buildForm(schema.form(state.model)!!, state.values, state.fieldErrors, state.hints)

    private fun List<FormItem>.fields(): List<FieldItem> = flatMap {
        when (it) {
            is FormItem.Stack -> it.fields
            is FormItem.Grid -> it.fields
            is FormItem.Range -> listOf(it.low, it.high)
            else -> emptyList()
        }
    }

    @Test
    fun `the schema reads models, texts, help and every model's form`() {
        assertEquals(listOf("fretboard", "ensemble", "piano"), schema.models.map { it.model })
        assertEquals(listOf("fretboard", "piano", "ensemble"), schema.treeGroups.map { it.model })
        assertEquals("Name", schema.text("name_label"))
        assertEquals("Remove voicing '{name}'?", schema.text("remove_confirm"))
        assertTrue(schema.help.getValue("name").contains("the player's Voicing sheet"))
        assertEquals(setOf("fretboard", "ensemble", "piano"), schema.forms.keys)
        // Unknown models fall back to the piano form, as in Python.
        assertEquals("piano", schema.form("harp")!!.model)
    }

    @Test
    fun `every field kind and section kind of the schema is known to Kotlin`() {
        val kinds = mutableSetOf<FieldKind>()
        val sections = mutableSetOf<SectionKind>()
        fun walk(s: SectionSpec) {
            sections += s.kind
            (s.fields + s.rows.flatMap { it.fields }).forEach { f ->
                kinds += f.kind
                f.columns.forEach { kinds += it.kind }
            }
            s.groups.forEach(::walk)
        }
        schema.forms.values.flatMap { it.sections }.forEach(::walk)
        assertEquals(FieldKind.entries.toSet(), kinds)
        assertEquals(SectionKind.entries.toSet(), sections)
    }

    @Test
    fun `fretboard form - field list per kind, values from the state`() {
        val items = formOf(Fixtures.fretboardInvalid)
        val fields = items.fields().associateBy { it.spec.id }
        assertEquals(FieldKind.PITCH_LIST, fields.getValue("tuning").spec.kind)
        assertEquals("E2 A2 X9 G3", fields.getValue("tuning").text)
        assertEquals(FieldKind.INT, fields.getValue("max_fret").spec.kind)
        assertEquals(5.0, fields.getValue("max_fret").spec.min)
        assertEquals(24.0, fields.getValue("max_fret").spec.max)
        assertEquals(FieldKind.BOOL, fields.getValue("allow_barres").spec.kind)
        assertTrue(fields.getValue("allow_barres").checked)
        assertEquals(FieldKind.FLOAT, fields.getValue("weight:open_string_bonus").spec.kind)
        // The weights are a grid with a titled, blurbed header.
        val header = items.filterIsInstance<FormItem.Header>().single()
        assertEquals("Weights", header.title)
        assertTrue(header.blurb!!.startsWith("Each weight"))
        assertTrue(items.filterIsInstance<FormItem.Grid>().any { g -> g.fields.any { it.spec.id == "weight:open_string_bonus" } })
    }

    @Test
    fun `field errors and hints go to their field`() {
        val fields = formOf(Fixtures.fretboardInvalid).fields().associateBy { it.spec.id }
        assertEquals("Not a valid note name", fields.getValue("tuning").error)
        assertEquals("(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4)", fields.getValue("tuning").hint)
        assertNull(fields.getValue("max_fret").error)
        assertNull(fields.getValue("max_fret").hint)
        assertEquals(1, Fixtures.fretboardInvalid.formErrors.size)
    }

    @Test
    fun `ensemble form - records rows with cell errors from error_path, hint with a count`() {
        val items = formOf(Fixtures.ensemble)
        val records = items.filterIsInstance<FormItem.Records>().single()
        assertEquals("voices", records.spec.id)
        assertEquals(listOf("name", "low", "high", "staff"), records.spec.columns.map { it.id })
        assertEquals(2, records.rows.size)
        // min_items 2, max_items 8: may add, may not remove.
        assertTrue(records.canAdd)
        assertFalse(records.canRemove)
        val row1 = records.rows[1].cells.associateBy { it.spec.id }
        assertEquals("H9", row1.getValue("low").text)
        assertEquals("Not a valid note name", row1.getValue("low").error)
        assertNull(records.rows[0].cells.first { it.spec.id == "low" }.error)
        // staff is a choice whose value is null: "Auto".
        assertEquals("Auto", row1.getValue("staff").choice!!.label)
        assertEquals("voice:1:low", records.spec.cellErrorKey(1, "low"))
        val fields = items.fields().associateBy { it.spec.id }
        assertEquals(FieldKind.INT_LIST, fields.getValue("max_spacing").spec.kind)
        assertEquals("(comma-separated, 1 values expected)", fields.getValue("max_spacing").hint)
        assertEquals(FieldKind.FLOAT_OR_LIST, fields.getValue("movement").spec.kind)
        // The nested groups (doubling, omit, inversion) are titled sub-grids.
        val subTitles = items.filterIsInstance<FormItem.Header>().filter { it.level == 1 }.map { it.title }
        assertEquals(3, subTitles.size)
        assertTrue(Fixtures.ensemble.formErrors.single().contains("low < high"))
    }

    @Test
    fun `piano form - range rows of low and high pitch fields, a grid with a group`() {
        val items = formOf(Fixtures.piano)
        val ranges = items.filterIsInstance<FormItem.Range>()
        assertEquals(listOf("lh_range", "rh_range", "bass_range", "rh_low_anchor"), ranges.map { it.key.removePrefix("r:") })
        assertEquals("Left hand", ranges[0].label)
        assertEquals("range:lh_range:low", ranges[0].low.spec.id)
        assertEquals(FieldKind.PITCH, ranges[0].high.spec.kind)
        assertTrue(ranges[0].low.text.isNotEmpty())
        val fields = items.fields().associateBy { it.spec.id }
        assertEquals(0.5, fields.getValue("rh_center").spec.step)
        assertTrue(fields.keys.any { it.startsWith("nested:omit:") })
        assertTrue(items.fields().all { it.error == null })
    }

    @Test
    fun `edits become set_voicing_values payloads keyed by field id`() {
        assertEquals(JsonObject(mapOf("tuning" to JsonPrimitive("E2 A2"))), VoicingEdits.text("tuning", "E2 A2"))
        assertEquals(JsonObject(mapOf("allow_barres" to JsonPrimitive(false))), VoicingEdits.bool("allow_barres", false))
        assertEquals(JsonObject(mapOf("x" to JsonNull)), VoicingEdits.choice("x", JsonNull))
        val rows = Fixtures.ensemble.values.getValue("voices").asRecords()
        val payload = VoicingEdits.cell("voices", rows, 1, "low", JsonPrimitive("G2"))
        val sent = payload.getValue("voices").jsonArray
        assertEquals(2, sent.size)
        assertEquals("G2", sent[1].jsonObject.getValue("low").jsonPrimitive.content)
        assertEquals("Voice 2", sent[1].jsonObject.getValue("name").jsonPrimitive.content)
        assertEquals(rows[0], sent[0])
        assertEquals(setOf("voices"), payload.keys)
    }

    @Test
    fun `pending edits show until a state echoes them`() {
        val pending = PendingEdits()
        val state = JsonObject(mapOf("tuning" to JsonPrimitive("E2"), "max_fret" to JsonPrimitive("12")))
        pending.record(VoicingEdits.text("tuning", "E2 A"))
        pending.record(VoicingEdits.text("tuning", "E2 A2"))
        assertEquals("E2 A2", pending.applyTo(state).getValue("tuning").jsonPrimitive.content)
        // The reply to the first keystroke doesn't undo the second.
        pending.onState(JsonObject(mapOf("tuning" to JsonPrimitive("E2 A"))))
        assertEquals("E2 A2", pending.applyTo(state).getValue("tuning").jsonPrimitive.content)
        pending.onState(JsonObject(mapOf("tuning" to JsonPrimitive("E2 A2"))))
        assertTrue(pending.isEmpty)
    }

    @Test
    fun `a second cell edit builds on the first before the state echoes it`() {
        val pending = PendingEdits()
        val state = Fixtures.ensemble.values
        val first = VoicingEdits.cell("voices", pending.applyTo(state).getValue("voices").asRecords(), 0, "low", JsonPrimitive("C3"))
        pending.record(first)
        val second = VoicingEdits.cell("voices", pending.applyTo(state).getValue("voices").asRecords(), 1, "low", JsonPrimitive("G2"))
        val rows = (second.getValue("voices") as JsonArray).map { it.jsonObject.getValue("low").jsonPrimitive.content }
        assertEquals(listOf("C3", "G2"), rows)
    }

    @Test
    fun `steppers move by the field's step within its range, never parse rules`() {
        val fields = formOf(Fixtures.piano).fields().associateBy { it.spec.id }
        val center = fields.getValue("rh_center").spec
        assertEquals("63.5", stepNumber(center, "63.0", 1))
        assertEquals("127.0", stepNumber(center, "127", 3))
        val maxNotes = fields.getValue("max_notes_per_hand").spec
        assertEquals("1", stepNumber(maxNotes, "1", -1))
        assertEquals("5", stepNumber(maxNotes, "4", 1))
        val weight = formOf(Fixtures.fretboardInvalid).fields().first { it.spec.id == "weight:open_string_bonus" }.spec
        assertEquals("0.6", stepNumber(weight, "0.5", 1))
        assertEquals("-0.1", stepNumber(weight, "0", -1))
        assertNull(stepNumber(weight, "abc", 1))
    }
}

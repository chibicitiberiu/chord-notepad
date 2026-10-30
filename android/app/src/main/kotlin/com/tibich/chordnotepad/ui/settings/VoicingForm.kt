package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.VoicingEditorState
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.math.BigDecimal
import java.math.RoundingMode

// The voicing form as a flat list of items to draw, built from the schema and
// the editor state, plus the payloads the edits send. No rule of a voicing is
// checked here: values go to Python as typed and the errors and hints come
// back in VoicingEditorState.

/** One input with what it shows now. */
data class FieldItem(
    val spec: FieldSpec,
    /** The current value (state values plus edits not echoed yet). */
    val value: JsonElement?,
    /** Python's error for this field (or records cell), or null. */
    val error: String?,
    /** Python's hint ("N values expected"), or null. */
    val hint: String?,
) {
    /** What a text field shows. */
    val text: String get() = value.asFieldText()

    /** What a switch shows. */
    val checked: Boolean get() = value.asFieldBool()

    /** The option a choice field shows (the first one when the value matches none). */
    val choice: ChoiceOption?
        get() = spec.choices.firstOrNull { it.value == (value ?: JsonNull) } ?: spec.choices.firstOrNull()
}

/** One row of a records field. */
data class RecordRow(val index: Int, val cells: List<FieldItem>)

/** What the form draws, top to bottom. */
sealed interface FormItem {
    /** Stable key (for lists and for resetting local text). */
    val key: String

    /** A section or group title and its blurb (either may be missing, not both). */
    data class Header(override val key: String, val title: String?, val blurb: String?, val level: Int) : FormItem

    /** Fields one under another (a `stack` section). */
    data class Stack(override val key: String, val fields: List<FieldItem>) : FormItem

    /** Number fields in a two-column grid where there's room (a `grid` section or group). */
    data class Grid(override val key: String, val fields: List<FieldItem>) : FormItem

    /** A labelled pair of (low, high) pitch fields (a `range_table` row). */
    data class Range(override val key: String, val label: String, val help: String, val low: FieldItem, val high: FieldItem) :
        FormItem

    /** A records field: rows of [FieldSpec.columns], add and remove buttons. */
    data class Records(
        override val key: String,
        val spec: FieldSpec,
        val rows: List<RecordRow>,
        val canAdd: Boolean,
        val canRemove: Boolean,
        /** An error for the field as a whole (e.g. too few rows), or null. */
        val error: String?,
    ) : FormItem
}

/**
 * The form of [form] with [values] (the editor state's values with local
 * edits applied, see [PendingEdits]), [errors] and [hints] from the state.
 */
fun buildForm(form: FormSpec, values: JsonObject, errors: JsonObject, hints: JsonObject): List<FormItem> {
    val out = mutableListOf<FormItem>()
    fun item(spec: FieldSpec) = FieldItem(spec, values[spec.id], errors.text(spec.id), hints.text(spec.id))

    fun section(section: SectionSpec, level: Int) {
        if (section.title != null || section.blurb != null) {
            out += FormItem.Header("h:${section.id}", section.title, section.blurb, level)
        }
        when (section.kind) {
            SectionKind.STACK -> if (section.fields.isNotEmpty()) {
                out += FormItem.Stack("s:${section.id}", section.fields.map(::item))
            }
            SectionKind.GRID -> if (section.fields.isNotEmpty()) {
                out += FormItem.Grid("g:${section.id}", section.fields.map(::item))
            }
            SectionKind.TABLE -> for (spec in section.fields) {
                if (spec.kind == FieldKind.RECORDS) out += records(spec, values, errors)
                else out += FormItem.Stack("s:${section.id}:${spec.id}", listOf(item(spec)))
            }
            SectionKind.RANGE_TABLE -> for (row in section.rows) {
                val (low, high) = row.fields.let { it.getOrNull(0) to it.getOrNull(1) }
                if (low != null && high != null) {
                    out += FormItem.Range("r:${row.id}", row.label, row.help, item(low), item(high))
                }
            }
            SectionKind.GROUPS -> Unit
        }
        for (group in section.groups) section(group, level + 1)
    }

    for (s in form.sections) section(s, 0)
    return out
}

private fun records(spec: FieldSpec, values: JsonObject, errors: JsonObject): FormItem.Records {
    val rows = values[spec.id].asRecords()
    return FormItem.Records(
        key = "t:${spec.id}",
        spec = spec,
        rows = rows.mapIndexed { index, row ->
            RecordRow(index, spec.columns.map { column ->
                FieldItem(column, row[column.id], errors.text(spec.cellErrorKey(index, column.id)), null)
            })
        },
        canAdd = spec.maxItems == null || rows.size < spec.maxItems,
        canRemove = spec.minItems == null || rows.size > spec.minItems,
        error = errors.text(spec.id),
    )
}

private fun JsonObject.text(key: String): String? =
    (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content?.takeIf { it.isNotBlank() }

/** The payloads of form edits (`set_voicing_values {values}`), keyed by field id. */
object VoicingEdits {
    /** A typed value (every kind but bool, choice and records goes as the text typed). */
    fun text(fieldId: String, text: String): JsonObject = JsonObject(mapOf(fieldId to JsonPrimitive(text)))

    /** A switch. */
    fun bool(fieldId: String, checked: Boolean): JsonObject = JsonObject(mapOf(fieldId to JsonPrimitive(checked)))

    /** A choice, by the option's value (may be JSON null). */
    fun choice(fieldId: String, value: JsonElement): JsonObject = JsonObject(mapOf(fieldId to value))

    /**
     * A records cell: the whole list goes back (Python merges top-level keys),
     * [rows] being what the form shows now.
     */
    fun cell(fieldId: String, rows: List<JsonObject>, index: Int, column: String, value: JsonElement): JsonObject {
        val updated = rows.mapIndexed { i, row ->
            if (i == index) JsonObject(row + (column to value)) else row
        }
        return JsonObject(mapOf(fieldId to JsonArray(updated)))
    }
}

/**
 * Form edits sent but not echoed by a [VoicingEditorState] yet, so a quick
 * second edit (two cells of one records field) builds on the first rather
 * than on the stale state. An edit is dropped once a state shows the same
 * value; [clear] drops them all (another voicing, a preset, a model switch)
 * and [clear] with a field id drops one (rows added or removed by Python).
 */
class PendingEdits {
    private val pending = LinkedHashMap<String, JsonElement>()

    /** Remember the edit [payload] (a `set_voicing_values` argument). */
    fun record(payload: JsonObject) {
        pending.putAll(payload)
    }

    /** A state arrived: forget the edits it already shows. */
    fun onState(values: JsonObject) {
        pending.entries.removeAll { (id, value) -> values[id] == value }
    }

    /** Forget every edit. */
    fun clear() = pending.clear()

    /** Forget the edit of [fieldId]. */
    fun clear(fieldId: String) {
        pending.remove(fieldId)
    }

    /** [values] with the edits not echoed yet on top. */
    fun applyTo(values: JsonObject): JsonObject = if (pending.isEmpty()) values else JsonObject(values + pending)

    /** Whether nothing is waiting. */
    val isEmpty: Boolean get() = pending.isEmpty()
}

/**
 * The spinner step of a number field: [text] moved by [steps] × the field's
 * step, kept within its min/max. Null when [text] isn't a plain number (the
 * buttons are then disabled; Python reports what's wrong with it).
 */
fun stepNumber(spec: FieldSpec, text: String, steps: Int): String? {
    val current = text.trim().toBigDecimalOrNull() ?: return null
    val step = BigDecimal.valueOf(spec.step ?: 1.0)
    var next = current + step.multiply(BigDecimal(steps))
    spec.min?.let { next = next.max(BigDecimal.valueOf(it)) }
    spec.max?.let { next = next.min(BigDecimal.valueOf(it)) }
    return if (spec.kind == FieldKind.INT) {
        next.setScale(0, RoundingMode.HALF_UP).toPlainString()
    } else {
        next.stripTrailingZeros().let { if (it.scale() < 1) it.setScale(1) else it }.toPlainString()
    }
}

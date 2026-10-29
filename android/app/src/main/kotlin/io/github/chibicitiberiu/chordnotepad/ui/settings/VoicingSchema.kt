package io.github.chibicitiberiu.chordnotepad.ui.settings

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject

// The voicings editor's form schema (src/settings_forms/voicing_form.py,
// `editor_schema("android")`), read once into typed Kotlin. Only the shape is
// read here: what a field accepts is Python's business (values go back as
// typed, errors come back in VoicingEditorState).

/** How a field is edited (`KIND_*` in voicing_form.py). */
enum class FieldKind(val wire: String) {
    TEXT("text"),
    INT("int"),
    FLOAT("float"),
    BOOL("bool"),
    CHOICE("choice"),
    PITCH("pitch"),
    PITCH_LIST("pitch_list"),
    INT_LIST("int_list"),
    FLOAT_OR_LIST("float_or_list"),
    RECORDS("records"),
    ;

    /** Whether the field is a number with a spinner range ([FieldSpec.min] etc. are hints). */
    val numeric: Boolean get() = this == INT || this == FLOAT

    companion object {
        /** The kind named [wire]; an unknown kind is edited as plain text. */
        fun of(wire: String?): FieldKind = entries.firstOrNull { it.wire == wire } ?: TEXT
    }
}

/** How a section lays out its fields (`SECTION_*` in voicing_form.py). */
enum class SectionKind(val wire: String) {
    STACK("stack"),
    GRID("grid"),
    TABLE("table"),
    RANGE_TABLE("range_table"),
    GROUPS("groups"),
    ;

    companion object {
        /** The kind named [wire]; unknown kinds stack their fields. */
        fun of(wire: String?): SectionKind = entries.firstOrNull { it.wire == wire } ?: STACK
    }
}

/** One option of a choice field; [value] may be JSON null (the staff's "Auto"). */
data class ChoiceOption(val value: JsonElement, val label: String)

/**
 * One input of a form, or a column of a records field.
 *
 * @property min Spinner lower bound (a hint; Python reports what's really wrong).
 * @property errorPath For records: the error key of a cell, `voice:{index}:{column}`.
 */
data class FieldSpec(
    val id: String,
    val kind: FieldKind,
    val label: String,
    val help: String,
    val default: JsonElement,
    val min: Double? = null,
    val max: Double? = null,
    val step: Double? = null,
    val choices: List<ChoiceOption> = emptyList(),
    val columns: List<FieldSpec> = emptyList(),
    val errorPath: String? = null,
    val minItems: Int? = null,
    val maxItems: Int? = null,
    val addLabel: String? = null,
    val addHelp: String? = null,
    val removeLabel: String? = null,
    val removeHelp: String? = null,
) {
    /** The error key of records cell ([index], [column]); the field id itself for other fields. */
    fun cellErrorKey(index: Int, column: String): String =
        (errorPath ?: "$id:{index}:{column}").replace("{index}", index.toString()).replace("{column}", column)
}

/** A labelled row of a `range_table` section: two pitch fields (low, high). */
data class RangeRow(val id: String, val label: String, val help: String, val fields: List<FieldSpec>)

/**
 * A form section. Its inputs are [fields], except a `range_table` ([rows]) and
 * a `groups` section ([groups], titled grids); a grid may also have [groups]
 * under its own fields.
 */
data class SectionSpec(
    val id: String,
    val kind: SectionKind,
    val title: String?,
    val blurb: String?,
    val fields: List<FieldSpec> = emptyList(),
    val rows: List<RangeRow> = emptyList(),
    val columns: List<String> = emptyList(),
    val groups: List<SectionSpec> = emptyList(),
)

/** One model's form. */
data class FormSpec(val model: String, val title: String, val sections: List<SectionSpec>)

/** A model choice (`models` / `tree_groups`). */
data class ModelOption(val model: String, val label: String)

/**
 * Everything the voicings editor draws with (`VoicingEditorSchema.schema`).
 *
 * @property texts Fixed strings: buttons, the confirmation dialogs
 *   (`remove_confirm` takes `{name}`), the placeholder.
 * @property help Help of the header controls (`name`, `model`, `load`, `tree_add`, `tree_remove`).
 */
data class EditorSchema(
    val version: Int,
    val models: List<ModelOption>,
    val treeGroups: List<ModelOption>,
    val texts: Map<String, String>,
    val help: Map<String, String>,
    val forms: Map<String, FormSpec>,
) {
    /** A fixed text; [fallback] if the schema has none. Trailing colons (`Name:`) are dropped. */
    fun text(key: String, fallback: String = ""): String = (texts[key] ?: fallback).removeSuffix(":")

    /** The form of [model]; unknown models get the piano form, as in Python. */
    fun form(model: String?): FormSpec? = forms[model] ?: forms["piano"]

    companion object {
        /** Read `VoicingEditorSchema.schema`. */
        fun parse(json: JsonObject): EditorSchema = EditorSchema(
            version = json.int("version") ?: 0,
            models = json.list("models").map { it.modelOption("value") },
            treeGroups = json.list("tree_groups").map { it.modelOption("model") },
            texts = json.strings("texts"),
            help = json.strings("help"),
            forms = (json["forms"] as? JsonObject).orEmpty().mapValues { (model, form) ->
                val o = form.jsonObject
                FormSpec(model, o.str("title") ?: model, o.list("sections").map(::parseSection))
            },
        )
    }
}

private fun parseSection(json: JsonObject): SectionSpec = SectionSpec(
    id = json.str("id").orEmpty(),
    kind = SectionKind.of(json.str("kind")),
    title = json.str("title"),
    blurb = json.str("blurb"),
    fields = json.list("fields").map(::parseField),
    rows = json.list("rows").map { row ->
        RangeRow(row.str("id").orEmpty(), row.str("label").orEmpty(), row.str("help").orEmpty(),
            row.list("fields").map(::parseField))
    },
    columns = (json["columns"] as? JsonArray).orEmpty().mapNotNull { (it as? JsonPrimitive)?.content },
    groups = json.list("groups").map(::parseSection),
)

private fun parseField(json: JsonObject): FieldSpec = FieldSpec(
    id = json.str("id").orEmpty(),
    kind = FieldKind.of(json.str("kind")),
    label = json.str("label").orEmpty(),
    help = json.str("help").orEmpty(),
    default = json["default"] ?: JsonNull,
    min = json.double("min"),
    max = json.double("max"),
    step = json.double("step"),
    choices = json.list("choices").map { ChoiceOption(it["value"] ?: JsonNull, it.str("label").orEmpty()) },
    columns = json.list("columns").map(::parseField),
    errorPath = json.str("error_path"),
    minItems = json.int("min_items"),
    maxItems = json.int("max_items"),
    addLabel = json.str("add_label"),
    addHelp = json.str("add_help"),
    removeLabel = json.str("remove_label"),
    removeHelp = json.str("remove_help"),
)

private fun JsonObject.str(key: String): String? = (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content

private fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.intOrNull

private fun JsonObject.double(key: String): Double? = (this[key] as? JsonPrimitive)?.doubleOrNull

private fun JsonObject.list(key: String): List<JsonObject> =
    (this[key] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }

private fun JsonObject.strings(key: String): Map<String, String> =
    (this[key] as? JsonObject).orEmpty().mapNotNull { (k, v) ->
        (v as? JsonPrimitive)?.takeIf { it.isString }?.let { k to it.content }
    }.toMap()

private fun JsonObject.modelOption(key: String) = ModelOption(str(key).orEmpty(), str("label").orEmpty())

/** A form value as the text its field shows (JSON null and non-strings as written). */
fun JsonElement?.asFieldText(): String = when (this) {
    null, JsonNull -> ""
    is JsonPrimitive -> content
    else -> toString()
}

/** A form value as a switch state. */
fun JsonElement?.asFieldBool(): Boolean = (this as? JsonPrimitive)?.booleanOrNull ?: false

/** A records value as its rows (anything else: no rows). */
fun JsonElement?.asRecords(): List<JsonObject> = (this as? JsonArray)?.mapNotNull { it as? JsonObject }.orEmpty()


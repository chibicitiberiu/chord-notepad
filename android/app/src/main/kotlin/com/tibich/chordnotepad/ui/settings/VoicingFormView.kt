package com.tibich.chordnotepad.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** What the voicing form sends: edits, and rows added to, moved in or removed from a records field. */
interface FormActions {
    /** A `set_voicing_values` payload ([VoicingEdits]). */
    fun edit(payload: JsonObject)

    /** Records cell ([index], [column]) of [fieldId] changed to [value]. */
    fun editCell(fieldId: String, index: Int, column: String, value: JsonElement)

    /** Add a row to records field [fieldId]. */
    fun addRecord(fieldId: String)

    /** Remove row [index] of records field [fieldId]. */
    fun removeRecord(index: Int, fieldId: String)

    /** Move row [index] of records field [fieldId] by [offset] rows (-1 up, +1 down). */
    fun moveRecord(index: Int, offset: Int, fieldId: String)
}

/**
 * The voicing form: every [FormItem] of [buildForm], drawn by kind. [formKey]
 * names the voicing and model (the fields reset when it changes), [wide]
 * puts grids in two columns and records in a table.
 */
@Composable
fun VoicingFormItems(items: List<FormItem>, formKey: String, wide: Boolean, actions: FormActions) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (item in items) {
            when (item) {
                is FormItem.Header -> SectionTitle(item.title, item.blurb, item.level)
                is FormItem.Stack -> for (field in item.fields) FieldInput(field, "$formKey:${field.spec.id}", actions, Modifier.fillMaxWidth())
                is FormItem.Grid -> FieldGrid(item.fields, formKey, wide, actions)
                is FormItem.Range -> RangeInput(item, formKey, actions)
                is FormItem.Records -> RecordsInput(item, formKey, wide, actions)
            }
        }
    }
}

@Composable
private fun FieldGrid(fields: List<FieldItem>, formKey: String, wide: Boolean, actions: FormActions) {
    if (!wide) {
        for (field in fields) FieldInput(field, "$formKey:${field.spec.id}", actions, Modifier.fillMaxWidth())
        return
    }
    for (pair in fields.chunked(2)) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
            for (field in pair) {
                FieldInput(field, "$formKey:${field.spec.id}", actions, Modifier.weight(1f))
            }
            if (pair.size == 1) Spacer(Modifier.weight(1f))
        }
    }
}

/** The supporting text of a field: Python's error, else its hint and help. */
private fun supportingOf(field: FieldItem, withHelp: Boolean = true): String? =
    field.error ?: listOfNotNull(field.hint, field.spec.help.takeIf { withHelp && it.isNotBlank() })
        .joinToString("\n").ifEmpty { null }

/**
 * One field of the form; [onValue] overrides where the edit goes (a records
 * cell). A [cell] (of a records row) is narrow: a number has no − and +
 * buttons (it is typed) and the label stays on one line.
 */
@Composable
private fun FieldInput(
    field: FieldItem,
    key: String,
    actions: FormActions,
    modifier: Modifier = Modifier,
    withHelp: Boolean = true,
    cell: Boolean = false,
    onValue: ((JsonElement) -> Unit)? = null,
) {
    val labelLines = if (cell) 1 else Int.MAX_VALUE
    val spec = field.spec
    val send: (JsonElement) -> Unit =
        onValue ?: { actions.edit(JsonObject(mapOf(spec.id to it))) }
    when (spec.kind) {
        FieldKind.BOOL -> Column(modifier) {
            SwitchRow(spec.label, field.checked, { send(JsonPrimitive(it)) }, supportingOf(field, withHelp))
        }
        FieldKind.CHOICE -> DropdownField(
            label = spec.label,
            selected = field.choice,
            options = spec.choices,
            optionLabel = { it?.label.orEmpty() },
            onSelect = { option -> option?.let { send(it.value) } },
            supporting = supportingOf(field, withHelp),
            isError = field.error != null,
            modifier = modifier,
        )
        FieldKind.INT, FieldKind.FLOAT -> StateTextField(
            value = field.text,
            onValueChange = { send(JsonPrimitive(it)) },
            label = spec.label,
            key = key,
            supporting = supportingOf(field, withHelp),
            isError = field.error != null,
            keyboardType = if (spec.kind == FieldKind.INT) KeyboardType.Number else KeyboardType.Decimal,
            trailing = if (cell) null else {
                {
                    StepperButtons(
                        spec.label,
                        canDown = field.enabled && canStep(spec, field.text, -1),
                        canUp = field.enabled && canStep(spec, field.text, 1),
                    ) { delta ->
                        stepNumber(spec, field.text, delta)?.let { send(JsonPrimitive(it)) }
                    }
                }
            },
            enabled = field.enabled,
            labelMaxLines = labelLines,
            modifier = modifier,
        )
        else -> StateTextField(
            value = field.text,
            onValueChange = { send(JsonPrimitive(it)) },
            label = spec.label,
            key = key,
            supporting = supportingOf(field, withHelp),
            isError = field.error != null,
            enabled = field.enabled,
            labelMaxLines = labelLines,
            modifier = modifier,
        )
    }
}

@Composable
private fun RangeInput(item: FormItem.Range, formKey: String, actions: FormActions) {
    Column(Modifier.fillMaxWidth().padding(top = 4.dp)) {
        Text(item.label, style = MaterialTheme.typography.bodyLarge)
        if (item.help.isNotBlank()) {
            Text(item.help, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
            for (field in listOf(item.low, item.high)) {
                FieldInput(field, "$formKey:${field.spec.id}", actions, Modifier.weight(1f), withHelp = false)
            }
        }
    }
}

@Composable
private fun RecordsInput(item: FormItem.Records, formKey: String, wide: Boolean, actions: FormActions) {
    val spec = item.spec
    // Each column's help once, above the rows.
    for (column in spec.columns) {
        if (column.help.isNotBlank()) {
            Text(
                "${column.label}: ${column.help}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    item.error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
    for (row in item.rows) {
        val cell: @Composable (FieldItem, Modifier) -> Unit = { field, modifier ->
            FieldInput(
                field = field,
                key = "$formKey:${spec.id}:${row.index}:${field.spec.id}",
                actions = actions,
                modifier = modifier,
                withHelp = false,
                cell = true,
                onValue = { actions.editCell(spec.id, row.index, field.spec.id, it) },
            )
        }
        val buttons: @Composable () -> Unit = {
            IconButton(onClick = { actions.moveRecord(row.index, -1, spec.id) }, enabled = row.canMoveUp) {
                Icon(SettingsIcons.ArrowUpward, contentDescription = spec.moveUpHelp ?: "Move up")
            }
            IconButton(onClick = { actions.moveRecord(row.index, 1, spec.id) }, enabled = row.canMoveDown) {
                Icon(SettingsIcons.ArrowDownward, contentDescription = spec.moveDownHelp ?: "Move down")
            }
            IconButton(onClick = { actions.removeRecord(row.index, spec.id) }, enabled = item.canRemove) {
                Icon(SettingsIcons.Close, contentDescription = spec.removeHelp ?: spec.removeLabel)
            }
        }
        if (wide) RecordTableRow(row, cell, buttons) else RecordCard(row, cell, buttons)
    }
    OutlinedButton(onClick = { actions.addRecord(spec.id) }, enabled = item.canAdd) {
        Icon(SettingsIcons.Add, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
        Spacer(Modifier.width(ButtonDefaults.IconSpacing))
        Text(spec.addLabel ?: spec.label)
    }
    spec.addHelp?.let {
        Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/**
 * A records row as one line of a table (tablets): the columns side by side,
 * weighted by width, then the row's [buttons] (move up, move down, remove).
 */
@Composable
private fun RecordTableRow(row: RecordRow, cell: @Composable (FieldItem, Modifier) -> Unit, buttons: @Composable () -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        for (field in row.cells) {
            val width = when {
                field.spec.id == "name" -> 2f
                field.spec.kind.numeric -> 1.5f
                else -> 1f
            }
            cell(field, Modifier.weight(width))
        }
        buttons()
    }
}

/**
 * A records row as a card (phones): its number and [buttons], the name, then
 * the other text columns two per line and each number (the gap) on a line
 * of its own.
 */
@Composable
private fun RecordCard(row: RecordRow, cell: @Composable (FieldItem, Modifier) -> Unit, buttons: @Composable () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(start = 12.dp, end = 4.dp, bottom = 12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${row.index + 1}",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f),
                )
                buttons()
            }
            Column(Modifier.padding(end = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                val (first, rest) = row.cells.firstOrNull() to row.cells.drop(1)
                first?.let { cell(it, Modifier.fillMaxWidth()) }
                val (numbers, texts) = rest.partition { it.spec.kind.numeric }
                for (pair in texts.chunked(2)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (field in pair) cell(field, Modifier.weight(1f))
                        if (pair.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
                for (field in numbers) cell(field, Modifier.fillMaxWidth())
            }
        }
    }
}

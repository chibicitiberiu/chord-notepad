package com.tibich.chordnotepad.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.VoicingEditorState
import com.tibich.chordnotepad.bridge.VoicingPreset
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/**
 * Settings › Voicings: the voicings grouped by model, each group's built-ins
 * first (read-only, with a lock), and the selected one's form. Both side by
 * side when [split], else the list, and the form once a voicing is picked
 * ([SettingsNav.voicingDetail]).
 */
@Composable
fun VoicingsPage(schema: EditorSchema?, view: EditorView?, detail: Boolean, split: Boolean, controller: SettingsController) {
    if (schema == null || view == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    if (split) {
        Row(Modifier.fillMaxSize()) {
            VoicingList(schema, view.state, controller, Modifier.width(280.dp).fillMaxHeight())
            VerticalDivider()
            VoicingDetail(schema, view, wide = true, controller, Modifier.weight(1f))
        }
    } else if (detail && view.state.selected != null) {
        VoicingDetail(schema, view, wide = false, controller, Modifier.fillMaxSize())
    } else {
        VoicingList(schema, view.state, controller, Modifier.fillMaxSize())
    }
}

/**
 * The voicings grouped by model, each group's built-ins first (muted, with a
 * lock; tapping one shows it read-only), invalid ones marked; Add voicing
 * opens a menu of what the new one starts as ([AddVoicingButton]).
 */
@Composable
private fun VoicingList(schema: EditorSchema, state: VoicingEditorState, controller: SettingsController, modifier: Modifier) {
    Column(modifier.verticalScroll(rememberScrollState()).padding(vertical = 8.dp)) {
        AddVoicingButton(schema, state.addPresets(), controller::addVoicingFrom, Modifier.padding(horizontal = 16.dp))
        schema.help["tree_add"]?.let { HelpLine(it, Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) }
        if (state.invalid.isNotEmpty()) {
            ErrorBanner(listOf(stringResource(R.string.voicings_invalid_banner)), Modifier.padding(16.dp))
        }
        val builtin = state.showsBuiltin
        for (group in state.groups) {
            Box(Modifier.padding(horizontal = 16.dp)) { SectionTitle(group.label, level = 1) }
            if (group.names.isEmpty() && group.builtins.isEmpty()) {
                HelpLine(stringResource(R.string.voicings_empty_group), Modifier.padding(horizontal = 16.dp))
            }
            for (label in group.builtins) {
                val selected = builtin && state.model == group.model && label == state.selected
                ListItem(
                    headlineContent = {
                        Text(
                            label,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    },
                    trailingContent = {
                        Icon(
                            SettingsIcons.Lock,
                            contentDescription = stringResource(R.string.voicings_builtin),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    },
                    colors = ListItemDefaults.colors(
                        containerColor = if (selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface,
                    ),
                    modifier = Modifier.clickable { controller.selectBuiltin(group.model, label) },
                )
            }
            for (name in group.names) {
                val invalid = name in state.invalid
                val selected = !builtin && name == state.selected
                ListItem(
                    headlineContent = { Text(name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    supportingContent = if (invalid) {
                        { Text(stringResource(R.string.voicings_invalid), color = MaterialTheme.colorScheme.error) }
                    } else null,
                    leadingContent = if (invalid) {
                        { Icon(SettingsIcons.Error, contentDescription = null, tint = MaterialTheme.colorScheme.error) }
                    } else null,
                    colors = ListItemDefaults.colors(
                        containerColor = if (selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface,
                    ),
                    modifier = Modifier.clickable { controller.selectVoicing(name) },
                )
            }
        }
    }
}

/**
 * The selected voicing: name, model, remove, then the form, scrolling under
 * the errors banner ([FormErrorsBanner]). A built-in shows read-only: its
 * name as text with Copy to a new voicing, the model and the form greyed,
 * no remove.
 */
@Composable
private fun VoicingDetail(schema: EditorSchema, view: EditorView, wide: Boolean, controller: SettingsController, modifier: Modifier) {
    val state = view.state
    val name = state.selected
    if (name == null) {
        Box(modifier.padding(24.dp), contentAlignment = Alignment.Center) {
            Text(schema.text("placeholder"), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        return
    }
    val form = schema.form(state.model)
    if (form == null) {
        // A voicing of a model a newer version added: read-only, no form
        // (editing it here would rewrite it as another model); the session's
        // note says so. It can still be renamed or removed.
        if (state.readOnly) NewerVersionDetail(schema, name, state.formErrors, controller, modifier)
        return
    }
    val builtin = state.showsBuiltin
    val items = remember(form, view.values, state.fieldErrors, state.hints, builtin) {
        buildForm(form, view.values, state.fieldErrors, state.hints, enabled = !builtin)
    }
    val focus = LocalFocusManager.current
    val actions = remember(controller) {
        object : FormActions {
            override fun edit(payload: JsonObject) = controller.edit(payload)
            override fun editCell(fieldId: String, index: Int, column: String, value: JsonElement) =
                controller.editCell(fieldId, index, column, value)
            override fun addRecord(fieldId: String) = controller.addRecord(fieldId)
            override fun removeRecord(index: Int, fieldId: String) = controller.removeRecord(index, fieldId)
            override fun moveRecord(index: Int, offset: Int, fieldId: String) =
                controller.moveRecord(index, offset, fieldId)
            override fun duplicateRecord(index: Int, fieldId: String) =
                controller.duplicateRecord(index, fieldId)
        }
    }
    Column(modifier) {
        FormErrorsBanner(schema, state, name)
        Column(
            Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
                .widthIn(max = 900.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (builtin) {
                BuiltinName(schema, name, wide) {
                    controller.addVoicingFrom(VoicingPreset(name, state.model.orEmpty()))
                }
            } else {
                NameField(schema, name) {
                    focus.clearFocus()
                    controller.askRename(name)
                }
            }
            DropdownField(
                label = schema.text("model_label"),
                selected = schema.models.firstOrNull { it.model == state.model },
                options = schema.models,
                optionLabel = { it?.label.orEmpty() },
                onSelect = { option ->
                    focus.clearFocus()
                    option?.let { controller.askModel(it.model) }
                },
                supporting = schema.help["model"],
                enabled = !builtin,
                modifier = Modifier.fillMaxWidth(),
            )
            if (!builtin) {
                TextButton(onClick = { controller.askRemove(name) }) {
                    Icon(SettingsIcons.Delete, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
                    Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                    Text(stringResource(R.string.voicings_remove))
                }
            }
            HorizontalDivider(Modifier.padding(top = 8.dp))
            VoicingFormItems(items, "$name:${state.model}:$builtin", wide, actions)
        }
    }
}

/** A voicing of a model a newer version added: its name, the note, and Remove. */
@Composable
private fun NewerVersionDetail(
    schema: EditorSchema,
    name: String,
    notes: List<String>,
    controller: SettingsController,
    modifier: Modifier,
) {
    val focus = LocalFocusManager.current
    Column(
        modifier.padding(16.dp).widthIn(max = 900.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        NameField(schema, name) {
            focus.clearFocus()
            controller.askRename(name)
        }
        notes.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        TextButton(onClick = { controller.askRemove(name) }) {
            Icon(SettingsIcons.Delete, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
            Spacer(Modifier.width(ButtonDefaults.IconSpacing))
            Text(stringResource(R.string.voicings_remove))
        }
    }
}

/**
 * "Fix these errors to apply changes", above the form (it doesn't scroll
 * away), with the errors that span fields under it; the fields with errors
 * are red. It shows once the errors have stood for [DRAFT_SAVE_DELAY_MS]
 * (an edit rests, not every keystroke) and goes as soon as they are fixed.
 */
@Composable
private fun FormErrorsBanner(schema: EditorSchema, state: VoicingEditorState, name: String) {
    val hasErrors = state.hasErrors
    var shown by remember(name) { mutableStateOf(hasErrors) }
    LaunchedEffect(name, hasErrors) {
        if (!hasErrors) {
            shown = false
        } else if (!shown) {
            delay(DRAFT_SAVE_DELAY_MS)
            shown = true
        }
    }
    if (shown && hasErrors) {
        ErrorBanner(
            state.formErrors,
            Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp).widthIn(max = 900.dp),
            title = schema.text("errors_banner", "Fix these errors to apply changes"),
        )
    }
}

/** The voicing's name; tapping it (or the pencil) opens the rename dialog. */
@Composable
private fun NameField(schema: EditorSchema, name: String, onRename: () -> Unit) {
    Box(Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = name,
            onValueChange = {},
            readOnly = true,
            singleLine = true,
            label = { Text(schema.text("name_label")) },
            supportingText = schema.help["name"]?.let { { Text(it) } },
            trailingIcon = {
                IconButton(onClick = onRename) { Icon(SettingsIcons.Edit, stringResource(R.string.voicings_rename)) }
            },
            modifier = Modifier.fillMaxWidth(),
        )
        Box(
            Modifier
                .matchParentSize()
                // Not the pencil (48 dp) nor the supporting text: the field's box only.
                .padding(top = 8.dp, end = 48.dp, bottom = 24.dp)
                .clickable(onClickLabel = stringResource(R.string.voicings_rename), onClick = onRename),
        )
    }
}

/**
 * A built-in's name, as plain text with a lock, and Copy to a new voicing
 * ([onCopy]); beside it when [wide], under it on a phone.
 */
@Composable
private fun BuiltinName(schema: EditorSchema, name: String, wide: Boolean, onCopy: () -> Unit) {
    val title: @Composable (Modifier) -> Unit = { modifier ->
        Column(modifier) {
            Text(
                schema.text("name_label"),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    SettingsIcons.Lock,
                    contentDescription = stringResource(R.string.voicings_builtin),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp),
                )
                Text(name, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
        }
    }
    val copy: @Composable () -> Unit = {
        FilledTonalButton(onClick = onCopy) {
            Icon(SettingsIcons.ContentCopy, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
            Spacer(Modifier.width(ButtonDefaults.IconSpacing))
            Text(stringResource(R.string.voicings_copy_builtin))
        }
    }
    if (wide) {
        Row(
            Modifier.fillMaxWidth().padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            title(Modifier.weight(1f))
            copy()
        }
    } else {
        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            title(Modifier)
            copy()
        }
    }
}

/**
 * Add voicing: a menu of what the new voicing starts as ([presets], from
 * [addPresets]): a blank of each model, then the built-ins by model and the
 * user's own voicings, each group under its title.
 */
@Composable
private fun AddVoicingButton(
    schema: EditorSchema,
    presets: List<VoicingPreset>,
    onPick: (VoicingPreset) -> Unit,
    modifier: Modifier = Modifier,
) {
    var open by remember { mutableStateOf(false) }
    Box(modifier) {
        FilledTonalButton(onClick = { open = true }) {
            Icon(SettingsIcons.Add, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
            Spacer(Modifier.width(ButtonDefaults.IconSpacing))
            Text(stringResource(R.string.voicings_add))
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            val custom = stringResource(R.string.voicings_preset_custom)
            presets.groupBy { it.group }.entries.forEachIndexed { i, (group, entries) ->
                if (i > 0) HorizontalDivider()
                // The blanks say what they are ("Blank piano"); the others get their group's title.
                if (group != BLANK_GROUP) {
                    val title = schema.treeGroups.firstOrNull { it.model == group }?.label ?: custom
                    Text(
                        title,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    )
                }
                for (preset in entries) {
                    DropdownMenuItem(
                        text = { Text(preset.label) },
                        onClick = {
                            open = false
                            onPick(preset)
                        },
                    )
                }
            }
        }
    }
}

/** An error card: [title] (if any) over [messages]. */
@Composable
fun ErrorBanner(messages: List<String>, modifier: Modifier = Modifier, title: String? = null) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        ),
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(SettingsIcons.Error, contentDescription = null)
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                title?.let { Text(it, style = MaterialTheme.typography.titleSmall) }
                for (message in messages) Text(message, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun HelpLine(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier,
    )
}


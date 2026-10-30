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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
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
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/**
 * Settings › Voicings: the list of custom voicings grouped by model, and the
 * selected one's form. Both side by side when [split], else the list, and
 * the form once a voicing is picked ([SettingsNav.voicingDetail]).
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

/** The voicings grouped by model, invalid ones marked; "+" adds one. */
@Composable
private fun VoicingList(schema: EditorSchema, state: VoicingEditorState, controller: SettingsController, modifier: Modifier) {
    Column(modifier.verticalScroll(rememberScrollState()).padding(vertical = 8.dp)) {
        FilledTonalButton(onClick = controller::addVoicing, modifier = Modifier.padding(horizontal = 16.dp)) {
            Icon(SettingsIcons.Add, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
            Spacer(Modifier.width(ButtonDefaults.IconSpacing))
            Text(stringResource(R.string.voicings_add))
        }
        schema.help["tree_add"]?.let { HelpLine(it, Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) }
        if (state.invalid.isNotEmpty()) {
            ErrorBanner(listOf(stringResource(R.string.voicings_invalid_banner)), Modifier.padding(16.dp))
        }
        for (group in state.groups) {
            Box(Modifier.padding(horizontal = 16.dp)) { SectionTitle(group.label, level = 1) }
            if (group.names.isEmpty()) {
                HelpLine(stringResource(R.string.voicings_empty_group), Modifier.padding(horizontal = 16.dp))
            }
            for (name in group.names) {
                val invalid = name in state.invalid
                val selected = name == state.selected
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

/** The selected voicing: name, model, Load config, remove, the form errors, then the form. */
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
    val form = schema.form(state.model) ?: return
    val items = remember(form, view.values, state.fieldErrors, state.hints) {
        buildForm(form, view.values, state.fieldErrors, state.hints)
    }
    val focus = LocalFocusManager.current
    val actions = remember(controller) {
        object : FormActions {
            override fun edit(payload: JsonObject) = controller.edit(payload)
            override fun editCell(fieldId: String, index: Int, column: String, value: JsonElement) =
                controller.editCell(fieldId, index, column, value)
            override fun addRecord(fieldId: String) = controller.addRecord(fieldId)
            override fun removeRecord(index: Int, fieldId: String) = controller.removeRecord(index, fieldId)
        }
    }
    Column(
        modifier
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
            .widthIn(max = 900.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        NameField(schema, name) {
            focus.clearFocus()
            controller.askRename(name)
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
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            PresetButton(schema, state.presets) {
                focus.clearFocus()
                controller.askPreset(it)
            }
            TextButton(onClick = { controller.askRemove(name) }) {
                Icon(SettingsIcons.Delete, contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
                Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                Text(stringResource(R.string.voicings_remove))
            }
        }
        schema.help["load"]?.let { HelpLine(it) }
        if (state.formErrors.isNotEmpty()) ErrorBanner(state.formErrors)
        HorizontalDivider(Modifier.padding(top = 8.dp))
        VoicingFormItems(items, "$name:${state.model}", wide, actions)
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

/** Load config: a menu of the presets, built-ins by model then the user's own voicings. */
@Composable
private fun PresetButton(schema: EditorSchema, presets: List<VoicingPreset>, onPick: (VoicingPreset) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { open = true }) { Text(schema.text("load_button")) }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            val custom = stringResource(R.string.voicings_preset_custom)
            presets.groupBy { it.group }.entries.forEachIndexed { i, (group, entries) ->
                if (i > 0) HorizontalDivider()
                val title = schema.treeGroups.firstOrNull { it.model == group }?.label ?: custom
                Text(
                    title,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                )
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

/** Errors that span fields (Python's form errors), at the top of the form. */
@Composable
fun ErrorBanner(messages: List<String>, modifier: Modifier = Modifier) {
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


package io.github.chibicitiberiu.chordnotepad.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

// Small form controls shared by the Settings pages and the voicing form.

/**
 * A text field over a [value] that lives elsewhere (the draft, or the voicing
 * form's state plus edits not echoed yet). What the user types stays as typed
 * (even when it isn't valid); [value] replaces it only when it becomes
 * something this field didn't send (a stepper, a preset, a model switch).
 * Values it sent are remembered until [value] catches up with the text, so a
 * late echo of an earlier keystroke never undoes a later one. [key] resets it
 * (another voicing).
 */
@Composable
fun StateTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    key: Any? = null,
    supporting: String? = null,
    isError: Boolean = false,
    keyboardType: KeyboardType = KeyboardType.Text,
    trailing: (@Composable () -> Unit)? = null,
) {
    var text by rememberSaveable(key) { mutableStateOf(value) }
    val sent = remember(key) { mutableSetOf<String>() }
    LaunchedEffect(value) {
        when {
            value == text -> sent.clear()
            value !in sent -> {
                text = value
                sent.clear()
            }
        }
    }
    OutlinedTextField(
        value = text,
        onValueChange = {
            text = it
            sent += it
            onValueChange(it)
        },
        label = { Text(label) },
        supportingText = supporting?.let { { Text(it) } },
        isError = isError,
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        trailingIcon = trailing,
        modifier = modifier,
    )
}

/** − and + buttons for a number field (hints only; [onStep] gets −1 or +1). */
@Composable
fun StepperButtons(label: String, enabled: Boolean, onStep: (Int) -> Unit) {
    Row {
        IconButton(onClick = { onStep(-1) }, enabled = enabled) {
            Icon(SettingsIcons.Remove, stringResource(R.string.settings_decrease, label))
        }
        IconButton(onClick = { onStep(1) }, enabled = enabled) {
            Icon(SettingsIcons.Add, stringResource(R.string.settings_increase, label))
        }
    }
}

/** A read-only field that opens a menu of [options] ([label] of each). */
@Composable
fun <T> DropdownField(
    label: String,
    selected: T,
    options: List<T>,
    optionLabel: (T) -> String,
    onSelect: (T) -> Unit,
    modifier: Modifier = Modifier,
    supporting: String? = null,
    isError: Boolean = false,
) {
    var open by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedTextField(
            value = optionLabel(selected),
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            supportingText = supporting?.let { { Text(it) } },
            isError = isError,
            singleLine = true,
            trailingIcon = { Icon(AppIcons.ArrowDropDown, contentDescription = null) },
            modifier = Modifier.fillMaxWidth(),
        )
        // The field itself would take the tap for focus; this layer opens the menu.
        Box(
            Modifier
                .matchParentSize()
                .padding(top = 8.dp)
                .clickable(role = Role.DropdownList, onClickLabel = label) { open = true },
        )
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for (option in options) {
                DropdownMenuItem(
                    text = { Text(optionLabel(option)) },
                    onClick = {
                        open = false
                        onSelect(option)
                    },
                )
            }
        }
    }
}

/** A switch with its label and supporting text; the whole row toggles. */
@Composable
fun SwitchRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit, supporting: String? = null) {
    Row(
        Modifier
            .fillMaxWidth()
            .toggleable(value = checked, role = Role.Switch, onValueChange = onChange)
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyLarge)
            supporting?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Switch(checked = checked, onCheckedChange = null)
    }
}

/** A section title, with an optional grey blurb under it. */
@Composable
fun SectionTitle(title: String?, blurb: String? = null, level: Int = 0) {
    Column(Modifier.fillMaxWidth().padding(top = if (level == 0) 20.dp else 12.dp, bottom = 4.dp)) {
        title?.let {
            Text(
                it,
                style = if (level == 0) MaterialTheme.typography.titleMedium else MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        blurb?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

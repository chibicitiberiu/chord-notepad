package com.tibich.chordnotepad.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.ui.editor.EditorFontKind

/** Settings › General: font, chord notation, default key, quick start, recent files. */
@Composable
fun GeneralPage(draft: SettingsDraft, limits: SettingsState, invalid: Set<NumberSetting>, controller: SettingsController) {
    val fontLabels = EditorFontKind.entries.associateWith { fontKindLabel(it) }
    PageColumn {
        DropdownField(
            label = stringResource(R.string.settings_font_family),
            selected = draft.fontKind,
            options = EditorFontKind.entries,
            optionLabel = { fontLabels.getValue(it) },
            onSelect = { kind -> controller.updateDraft { it.copy(fontKind = kind) } },
            supporting = stringResource(R.string.settings_font_family_help),
            modifier = Modifier.fillMaxWidth(),
        )
        NumberSettingField(
            NumberSetting.FONT_SIZE, R.string.settings_font_size, null,
            draft, limits, invalid, controller, Modifier.fillMaxWidth(),
        )
        Text(stringResource(R.string.settings_notation), style = MaterialTheme.typography.bodyLarge)
        val notations = listOf(AMERICAN to R.string.settings_notation_american, EUROPEAN to R.string.settings_notation_european)
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            notations.forEachIndexed { i, (value, label) ->
                SegmentedButton(
                    selected = draft.notation == value,
                    onClick = { controller.setNotation(value) },
                    shape = SegmentedButtonDefaults.itemShape(i, notations.size),
                ) { Text(stringResource(label)) }
            }
        }
        HelpText(stringResource(R.string.settings_notation_help))
        val none = stringResource(R.string.settings_key_none)
        DropdownField(
            label = stringResource(R.string.settings_default_key),
            selected = draft.key,
            options = listOf("") + keysFor(draft.notation, limits),
            optionLabel = { it.ifEmpty { none } },
            onSelect = { key -> controller.updateDraft { it.copy(key = key) } },
            supporting = stringResource(R.string.settings_default_key_help),
            modifier = Modifier.fillMaxWidth(),
        )
        SwitchRow(
            label = stringResource(R.string.settings_quick_start),
            checked = draft.showQuickStartOnStartup,
            onChange = { show -> controller.updateDraft { it.copy(showQuickStartOnStartup = show) } },
            supporting = stringResource(R.string.settings_quick_start_help),
        )
        NumberSettingField(
            NumberSetting.MAX_RECENT_FILES, R.string.settings_recent_files, R.string.settings_recent_files_help,
            draft, limits, invalid, controller, Modifier.fillMaxWidth(),
        )
    }
}

/** Settings › Playback: default BPM and time signature. */
@Composable
fun PlaybackPage(draft: SettingsDraft, limits: SettingsState, invalid: Set<NumberSetting>, controller: SettingsController) {
    PageColumn {
        NumberSettingField(
            NumberSetting.BPM, R.string.settings_default_bpm, R.string.settings_default_bpm_help,
            draft, limits, invalid, controller, Modifier.fillMaxWidth(),
        )
        Text(stringResource(R.string.settings_time_signature), style = MaterialTheme.typography.bodyLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
            NumberSettingField(
                NumberSetting.TIME_SIGNATURE_BEATS, R.string.settings_beats, null,
                draft, limits, invalid, controller, Modifier.weight(1f),
            )
            DropdownField(
                label = stringResource(R.string.settings_beat_unit),
                selected = draft.timeSignatureUnit,
                options = limits.timeSignatureUnits,
                optionLabel = { it.toString() },
                onSelect = { unit -> controller.updateDraft { it.copy(timeSignatureUnit = unit) } },
                modifier = Modifier.weight(1f),
            )
        }
        HelpText(stringResource(R.string.settings_time_signature_help))
    }
}

/** A scrolling column of fields, not wider than a comfortable form. */
@Composable
fun PageColumn(content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
            .widthIn(max = 640.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) { content() }
}

@Composable
private fun HelpText(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 16.dp),
    )
}

/** A whole-number setting with − / + buttons; text out of range shows an error and blocks Save. */
@Composable
private fun NumberSettingField(
    setting: NumberSetting,
    label: Int,
    help: Int?,
    draft: SettingsDraft,
    limits: SettingsState,
    invalid: Set<NumberSetting>,
    controller: SettingsController,
    modifier: Modifier = Modifier,
) {
    val range = setting.range(limits)
    val value = setting.get(draft)
    val error = setting in invalid
    val name = stringResource(label)
    StateTextField(
        value = value.toString(),
        onValueChange = { controller.setNumber(setting, it) },
        label = name,
        key = setting,
        isError = error,
        supporting = when {
            error -> stringResource(R.string.settings_number_range, range.first, range.last)
            help != null -> stringResource(help)
            else -> null
        },
        keyboardType = KeyboardType.Number,
        trailing = {
            StepperButtons(name, enabled = true) { delta ->
                controller.setNumber(setting, (value + delta).coerceIn(range).toString())
            }
        },
        modifier = modifier,
    )
}

@Composable
private fun fontKindLabel(kind: EditorFontKind): String = stringResource(
    when (kind) {
        EditorFontKind.MONOSPACE -> R.string.font_monospace
        EditorFontKind.SANS -> R.string.font_sans
        EditorFontKind.SERIF -> R.string.font_serif
    },
)

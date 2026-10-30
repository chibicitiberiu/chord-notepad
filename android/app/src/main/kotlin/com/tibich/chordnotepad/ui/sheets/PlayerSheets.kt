package com.tibich.chordnotepad.ui.sheets

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.ui.icons.IconTints
import com.tibich.chordnotepad.ui.icons.MdiIcon
import com.tibich.chordnotepad.ui.menus.FamilyRow
import com.tibich.chordnotepad.ui.menus.VoicingGroup
import com.tibich.chordnotepad.ui.menus.VoicingGroupKind
import com.tibich.chordnotepad.ui.menus.programParts
import com.tibich.chordnotepad.ui.theme.appColors

/** A radio mark: filled in the primary colour when [on], else a grey ring. */
@Composable
fun RadioMark(on: Boolean) {
    MdiIcon(
        if (on) R.drawable.mdi_radiobox_marked else R.drawable.mdi_radiobox_blank,
        if (on) appColors.primary else IconTints.Off,
    )
}

/**
 * Voicing: Piano, Fretted, Ensembles and Your voicings with radio rows.
 * Choosing one applies it at once (the sheet stays, Done closes it).
 * **Edit voicings…** opens Settings › Voicings.
 */
@Composable
fun VoicingPickerSheet(
    groups: List<VoicingGroup>,
    onChoose: (String) -> Unit,
    onEditVoicings: () -> Unit,
    onDismiss: () -> Unit,
) {
    PickerSheet(
        title = stringResource(R.string.menu_voicing),
        subtitle = stringResource(R.string.voicing_subtitle),
        onDismiss = onDismiss,
        actions = {
            SheetTextButton(stringResource(R.string.voicing_edit), onEditVoicings, leading = {
                MdiIcon(R.drawable.mdi_pencil, appColors.primary, size = 18.dp)
            })
            ActionsSpacer()
            SheetDoneButton(stringResource(R.string.sheet_done), onDismiss)
        },
    ) {
        for (group in groups) {
            SheetSection(stringResource(group.kind.title))
            for (choice in group.choices) {
                SheetRow(
                    choice.label,
                    onClick = { if (!choice.selected) onChoose(choice.value) },
                    leading = { RadioMark(choice.selected) },
                    role = Role.RadioButton,
                )
            }
        }
    }
}

private val VoicingGroupKind.title: Int
    get() = when (this) {
        VoicingGroupKind.PIANO -> R.string.voicing_group_piano
        VoicingGroupKind.FRETTED -> R.string.voicing_group_fretted
        VoicingGroupKind.ENSEMBLES -> R.string.voicing_group_ensembles
        VoicingGroupKind.YOURS -> R.string.voicing_group_yours
    }

/**
 * Instrument, two levels: the 16 General MIDI families (a dot on the
 * current one, its instrument on the right), then a family's 8 programs with
 * their numbers; ← (and Back) goes back to the families, Done closes.
 *
 * @param family The open family's index, or null for the families.
 */
@Composable
fun InstrumentPickerSheet(
    families: List<FamilyRow>,
    family: Int?,
    onOpenFamily: (Int) -> Unit,
    onBack: () -> Unit,
    onChoose: (Int) -> Unit,
    onDismiss: () -> Unit,
    onDone: () -> Unit = onDismiss,
) {
    val colors = appColors
    val open = family?.let { families.getOrNull(it) }
    PickerSheet(
        title = open?.name ?: stringResource(R.string.menu_instrument),
        onDismiss = onDismiss,
        leading = if (open != null) {
            {
                Box(
                    Modifier.size(36.dp).clip(CircleShape)
                        .clickable(onClickLabel = stringResource(R.string.instrument_back), role = Role.Button, onClick = onBack),
                    contentAlignment = Alignment.Center,
                ) { MdiIcon(R.drawable.mdi_arrow_left, colors.text, size = 22.dp) }
            }
        } else null,
        actions = {
            ActionsSpacer()
            SheetDoneButton(stringResource(R.string.sheet_done), onDone)
        },
    ) {
        if (open == null) {
            families.forEachIndexed { index, f ->
                val current = f.programs.firstOrNull { it.selected }?.let { programParts(it).first }
                SheetRow(
                    f.name,
                    onClick = { onOpenFamily(index) },
                    leading = {
                        Box(Modifier.size(24.dp), contentAlignment = Alignment.Center) {
                            MdiIcon(
                                if (f.isCurrent) R.drawable.mdi_circle else R.drawable.mdi_circle_outline,
                                if (f.isCurrent) colors.primary else colors.grip,
                                size = 12.dp,
                            )
                        }
                    },
                    sub = if (f.isCurrent) current else null,
                    trailing = { MdiIcon(R.drawable.mdi_chevron_right, IconTints.Off, size = 20.dp) },
                )
            }
        } else {
            for (program in open.programs) {
                val (name, number) = programParts(program)
                SheetRow(
                    name,
                    onClick = { if (!program.selected) onChoose(program.program) },
                    leading = { RadioMark(program.selected) },
                    sub = number,
                    role = Role.RadioButton,
                )
            }
        }
    }
}

/**
 * Playback speed: the value in large type, a 12.5–400 % slider (5 % steps;
 * the session gets each new value), then Reset, Manual… and Done.
 *
 * @param pct The session's speed.
 */
@Composable
fun SpeedSheet(pct: Double, onSpeed: (Double) -> Unit, onReset: () -> Unit, onManual: () -> Unit, onDismiss: () -> Unit) {
    val colors = appColors
    // The thumb follows the finger; the session's value takes over when it changes.
    var dragged by remember { mutableStateOf<Double?>(null) }
    LaunchedEffect(pct) { if (dragged?.let { Math.abs(it - pct) < 0.01 } == true) dragged = null }
    val shown = dragged ?: pct
    PickerSheet(
        title = stringResource(R.string.speed_title),
        onDismiss = onDismiss,
        trailing = {
            Text("${speedPctText(shown)}%", fontSize = 20.sp, fontWeight = FontWeight.Medium, color = colors.primary)
        },
        actions = {
            SheetTextButton(stringResource(R.string.speed_reset), onReset)
            SheetTextButton(stringResource(R.string.speed_manual), onManual)
            ActionsSpacer()
            SheetDoneButton(stringResource(R.string.sheet_done), onDismiss)
        },
    ) {
        Slider(
            value = shown.toFloat().coerceIn(SPEED_MIN_PCT.toFloat(), SPEED_MAX_PCT.toFloat()),
            onValueChange = { v ->
                val snapped = snapSpeedPct(v)
                if (dragged != snapped) {
                    dragged = snapped
                    onSpeed(snapped)
                }
            },
            valueRange = SPEED_MIN_PCT.toFloat()..SPEED_MAX_PCT.toFloat(),
            colors = SliderDefaults.colors(thumbColor = colors.primary, activeTrackColor = colors.primary, inactiveTrackColor = colors.primarySoft),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("${speedPctText(SPEED_MIN_PCT)}%", fontSize = 11.sp, color = colors.muted)
            Text("${speedPctText(SPEED_MAX_PCT)}%", fontSize = 11.sp, color = colors.muted)
        }
    }
}

/** The small dialog Manual… opens: a number field, 12.5–400, checked before OK. */
@Composable
fun SpeedDialog(pct: Double, onApply: (Double) -> Unit, onDismiss: () -> Unit) {
    val colors = appColors
    val initial = speedPctText(pct)
    var field by remember { mutableStateOf(TextFieldValue(initial, TextRange(0, initial.length))) }
    var showError by rememberSaveable { mutableStateOf(false) }
    val focus = remember { FocusRequester() }
    val ok = {
        val v = parseSpeedPct(field.text)
        if (v == null) showError = true else onApply(v)
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = colors.surfaceHigh,
        title = { Text(stringResource(R.string.speed_title)) },
        text = {
            OutlinedTextField(
                value = field,
                onValueChange = {
                    field = it
                    showError = false
                },
                singleLine = true,
                suffix = { Text("%") },
                isError = showError,
                supportingText = {
                    Text(stringResource(if (showError) R.string.speed_manual_error else R.string.speed_manual_hint))
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { ok() }),
                modifier = Modifier.width(160.dp).focusRequester(focus),
            )
            LaunchedEffect(Unit) { focus.requestFocus() }
        },
        confirmButton = { TextButton(onClick = ok) { Text(stringResource(android.R.string.ok)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

/** One entry of the Insert sheet: the directive kind's wire name, icon, tint, label and code. */
data class InsertEntry(val kind: String, val icon: Int, val label: Int, val code: String)

/** Insert's entries, in the spec's order. */
val INSERT_ENTRIES: List<InsertEntry> = listOf(
    InsertEntry("bpm", R.drawable.mdi_metronome, R.string.insert_tempo, "{bpm}"),
    InsertEntry("time", R.drawable.ic_time_signature, R.string.insert_time, "{time}"),
    InsertEntry("key", R.drawable.mdi_music_clef_treble, R.string.insert_key, "{key}"),
    InsertEntry("capo", R.drawable.ic_capo, R.string.insert_capo, "{capo}"),
    InsertEntry("label", R.drawable.mdi_label, R.string.insert_label, "{label}"),
    InsertEntry("loop", R.drawable.mdi_repeat, R.string.insert_loop, "{loop}"),
)

private fun tintOf(kind: String) = when (kind) {
    "bpm" -> IconTints.Tempo
    "time" -> IconTints.Time
    "key" -> IconTints.Key
    "capo" -> IconTints.Capo
    "label" -> IconTints.Label
    else -> IconTints.Loop
}

/** ＋ Insert: Tempo, Time signature, Key, Capo, Label and Loop, each showing its directive. */
@Composable
fun InsertSheet(onInsert: (String) -> Unit, onDismiss: () -> Unit) {
    PickerSheet(
        title = stringResource(R.string.ribbon_insert),
        onDismiss = onDismiss,
        actions = {
            ActionsSpacer()
            SheetTextButton(stringResource(android.R.string.cancel), onDismiss)
        },
    ) {
        for (entry in INSERT_ENTRIES) {
            SheetRow(
                stringResource(entry.label),
                onClick = { onInsert(entry.kind) },
                leading = { MdiIcon(entry.icon, tintOf(entry.kind)) },
                sub = entry.code,
                subMonospace = true,
            )
        }
    }
}
